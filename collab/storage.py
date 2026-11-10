"""Комментарии к темам, учебникам и планам. Та же SQLite, что и наборы: попадает в общий бэкап."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SCHEMA = """
CREATE TABLE IF NOT EXISTS collab_comments (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_school TEXT NOT NULL DEFAULT '',
    author_role TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'human',
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS collab_comments_target
    ON collab_comments (dataset_id, target_type, target_id, created_at);
"""

FIELDS = ("id", "dataset_id", "target_type", "target_id", "author_name", "author_school",
          "author_role", "kind", "text", "created_at")


class CommentStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.executescript(SCHEMA)

    def add(self, dataset_id, *, target_type, target_id, author_name, author_school, author_role, kind, text):
        row = {
            "id": str(uuid4()), "dataset_id": dataset_id, "target_type": target_type, "target_id": target_id,
            "author_name": author_name, "author_school": author_school, "author_role": author_role,
            "kind": kind, "text": text, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute(f"INSERT INTO collab_comments ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                       tuple(row[f] for f in FIELDS))
        return row

    def list(self, dataset_id, *, target_type=None, target_id=None, limit=500):
        query = f"SELECT {', '.join(FIELDS)} FROM collab_comments WHERE dataset_id = ?"
        params: list = [dataset_id]
        if target_type:
            query += " AND target_type = ?"
            params.append(target_type)
        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            total = db.execute(query.replace(f"SELECT {', '.join(FIELDS)}", "SELECT COUNT(*)", 1), params).fetchone()[0]
            rows = db.execute(query + " ORDER BY created_at DESC, id LIMIT ?", [*params, limit]).fetchall()
        return {"items": [dict(zip(FIELDS, r)) for r in rows], "total": total}
