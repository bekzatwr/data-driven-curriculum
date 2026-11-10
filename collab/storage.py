"""Комментарии к темам, учебникам и планам. Та же SQLite, что и наборы: попадает в общий бэкап."""
import sqlite3
import json
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.errors import ApiError

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
CREATE INDEX IF NOT EXISTS collab_comments_recent
    ON collab_comments (dataset_id, created_at DESC, id);
"""

FIELDS = ("id", "dataset_id", "target_type", "target_id", "author_name", "author_school",
          "author_role", "kind", "text", "created_at")


@dataclass(frozen=True)
class CommentLimits:
    total: int = 5000
    per_dataset: int = 1000
    bytes: int = 8 * 1024 * 1024
    database_bytes: int = 64 * 1024 * 1024


def validate_target(db, dataset_id, target_type, target_id):
    if not db.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone():
        raise ApiError(404, "DATASET_NOT_FOUND", "Набор данных не найден.")
    exists = False
    if target_type == "dataset":
        # Existing PR4 anchors are scoped to this dataset, never another one.
        exists = target_id in {dataset_id, "overview", "teachers"}
    elif target_type == "topic":
        exists = db.execute("SELECT 1 FROM topics WHERE dataset_id=? AND topic_id=?",
                            (dataset_id, target_id)).fetchone()
    elif target_type in {"class", "teacher", "textbook"}:
        column = {"class": "class_id", "teacher": "teacher_id", "textbook": "textbook_id"}[target_type]
        exists = db.execute(f"SELECT 1 FROM results WHERE dataset_id=? AND {column}=? LIMIT 1",
                            (dataset_id, target_id)).fetchone()
    elif target_type in {"plan", "plan_topic"}:
        plan_id, separator, topic_id = target_id.partition(":") if target_type == "plan_topic" else (target_id, "", "")
        row = db.execute("SELECT snapshot FROM aidana_plan_snapshots WHERE id=?", (plan_id,)).fetchone()
        if row:
            snapshot = json.loads(row[0])
            exists = snapshot["dataset_id"] == dataset_id
            if target_type == "plan_topic":
                exists = exists and separator and any(item["topic_id"] == topic_id for item in snapshot["items"])
    if not exists:
        # Same response for nonexistent targets and objects from a different dataset.
        raise ApiError(404, "COMMENT_TARGET_NOT_FOUND", "Цель комментария не найдена в этом наборе.")


class CommentStore:
    def __init__(self, path, limits=None):
        self.path = Path(path)
        self.limits = limits or CommentLimits()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.executescript(SCHEMA)

    def add(self, dataset_id, *, target_type, target_id, author_name, author_school, author_role, kind, text,
            response_factory=None):
        row = {
            "id": str(uuid4()), "dataset_id": dataset_id, "target_type": target_type, "target_id": target_id,
            "author_name": author_name, "author_school": author_school, "author_role": author_role,
            "kind": kind, "text": text, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # Build the complete transport response before opening the write transaction.
        from .api import Comment
        row = Comment.model_validate(row).model_dump(mode="json")
        json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8")
        response = response_factory(row) if response_factory else row
        row_bytes = sum(len(value.encode("utf-8")) for value in row.values())
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            validate_target(db, dataset_id, target_type, target_id)
            size_expression = "+".join(f"length(CAST({field} AS BLOB))" for field in FIELDS)
            count, used = db.execute(f"SELECT COUNT(*), COALESCE(SUM({size_expression}),0) FROM collab_comments").fetchone()
            dataset_count = db.execute("SELECT COUNT(*) FROM collab_comments WHERE dataset_id=?", (dataset_id,)).fetchone()[0]
            allocated = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
            wal = Path(str(self.path) + "-wal")
            allocated += wal.stat().st_size if wal.exists() else 0
            if (count >= self.limits.total or dataset_count >= self.limits.per_dataset
                    or used + row_bytes > self.limits.bytes
                    or allocated + row_bytes + 8192 > self.limits.database_bytes):
                raise ApiError(409, "COMMENT_QUOTA_EXCEEDED", "Лимит хранения комментариев достигнут. Обратитесь к администратору.")
            db.execute(f"INSERT INTO collab_comments ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                       tuple(row[f] for f in FIELDS))
        return response

    def list(self, dataset_id, *, target_type=None, target_id=None, limit=500):
        limit = min(500, max(1, int(limit)))
        query = f"SELECT {', '.join(FIELDS)} FROM collab_comments WHERE dataset_id = ?"
        params: list = [dataset_id]
        if target_type:
            query += " AND target_type = ?"
            params.append(target_type)
        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            # A stable snapshot for total + items during concurrent writes.
            db.execute("BEGIN")
            total = db.execute(query.replace(f"SELECT {', '.join(FIELDS)}", "SELECT COUNT(*)", 1), params).fetchone()[0]
            rows = db.execute(query + " ORDER BY created_at DESC, id LIMIT ?", [*params, limit]).fetchall()
        return {"items": [dict(zip(FIELDS, r)) for r in rows], "total": total}
