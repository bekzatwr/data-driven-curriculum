"""Consistent local SQLite backup, including committed WAL data. Never overwrite a file."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time

from ..config import Settings


def backup_database(source: Path, destination: Path, *, timeout: float = 30.0) -> dict:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source database does not exist: {source}")
    if source == destination:
        raise ValueError("Backup destination must differ from source")
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve a new destination exclusively. A failed attempt removes only its own file.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("Backup timed out; source database was not changed")

    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer, pages=256, progress=progress, sleep=0.05)
                # Produce a self-contained file, even when the source uses WAL.
                writer.execute("PRAGMA journal_mode=DELETE")
                integrity = [r[0] for r in writer.execute("PRAGMA integrity_check")]
                if integrity != ["ok"] or writer.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("Backup integrity verification failed")
                version = writer.execute("PRAGMA user_version").fetchone()[0]
        return {"source": str(source), "backup": str(destination), "bytes": destination.stat().st_size,
                "schema_version": version, "integrity": "ok"}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Settings.from_env().database_path,
                        help="Existing database (default: DATABASE_PATH)")
    parser.add_argument("--output", type=Path, required=True, help="New backup file; existing files are refused")
    args = parser.parse_args()
    try:
        result = backup_database(args.source, args.output)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Backup failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
