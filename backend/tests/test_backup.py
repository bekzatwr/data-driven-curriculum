from contextlib import closing
from dataclasses import replace
import json
import sqlite3
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from backend.app.db.backup import backup_database
from backend.app.main import create_app
from .conftest import send_import


def test_live_wal_backup_keeps_data_plans_and_reviews(client, sample, settings, tmp_path):
    dataset_id = send_import(client, sample).json()["dataset_id"]
    backup = tmp_path / "backup.sqlite3"
    # Keep the WAL connection open so copying only the main file would lose the new rows.
    with closing(sqlite3.connect(settings.database_path)) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("PRAGMA wal_autocheckpoint=0")
        live.execute("INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("plan1", dataset_id, "7A", "2026-11-09", "test-v1", "{}", "{}", "{}", "{}", 0))
        live.execute("INSERT INTO plan_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     ("review1", "plan1", dataset_id, "2026-09-01", "2026-09-30", "{}", 1, "", "{}", "test-v1", "2026-11-09"))
        live.commit()
        assert settings.database_path.with_name(settings.database_path.name + "-wal").stat().st_size > 0
        result = backup_database(settings.database_path, backup)
        assert result["integrity"] == "ok" and result["schema_version"] == 1
        with closing(sqlite3.connect(backup)) as saved:
            assert saved.execute("SELECT count(*) FROM plans").fetchone()[0] == 1
            assert saved.execute("SELECT count(*) FROM plan_reviews").fetchone()[0] == 1
            assert saved.execute("PRAGMA foreign_key_check").fetchall() == []
            assert saved.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert not backup.with_name(backup.name + "-wal").exists()
    # Recovery to a new path through the same API, then a real application startup.
    restored = tmp_path / "restored.sqlite3"
    backup_database(backup, restored)
    with TestClient(create_app(replace(settings, database_path=restored))) as recovered:
        assert recovered.get(f"/api/datasets/{dataset_id}").status_code == 200
        assert recovered.get(f"/api/datasets/{dataset_id}/results").json()["total"] == 5


def test_existing_destination_and_source_never_overwritten(client, sample, settings, tmp_path):
    send_import(client, sample)
    target = tmp_path / "existing.db"
    target.write_bytes(b"keep this file")
    with pytest.raises(FileExistsError):
        backup_database(settings.database_path, target)
    assert target.read_bytes() == b"keep this file"
    with pytest.raises(ValueError):
        backup_database(settings.database_path, settings.database_path)
    assert client.get("/api/datasets").json()["total"] == 1


def test_missing_or_invalid_source_leaves_no_destination(tmp_path):
    source, target = tmp_path / "missing.db", tmp_path / "backup.db"
    with pytest.raises(FileNotFoundError):
        backup_database(source, target)
    assert not source.exists() and not target.exists()
    source.write_bytes(b"this is not SQLite")
    with pytest.raises(sqlite3.DatabaseError):
        backup_database(source, target)
    assert not target.exists()


def test_cli_backup_and_refusal_exit_status(client, sample, settings, tmp_path):
    send_import(client, sample)
    command = [sys.executable, "-m", "backend.app.db.backup", "--source", str(settings.database_path),
               "--output", str(tmp_path / "cli.db")]
    done = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(done.stdout)["integrity"] == "ok"
    duplicate = subprocess.run(command, capture_output=True, text=True)
    assert duplicate.returncode == 1 and "Backup failed" in duplicate.stderr
