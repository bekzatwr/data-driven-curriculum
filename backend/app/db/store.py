import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..errors import ApiError
from ..validation import RESULT_FIELDS, TOPIC_FIELDS, ValidatedUpload, canonical


class Store:
    """One short-lived SQLite connection per operation; no global shared connection."""
    def __init__(self, path: Path, demo_only=False):
        self.path = Path(path)
        self.demo_only = demo_only

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Database schema is newer than this server; do not downgrade it.")
            db.execute("PRAGMA journal_mode=WAL")
            if version == 0:
                db.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))

    def ping(self):
        with self.connect() as db:
            return db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None

    @staticmethod
    def _dataset(row):
        return {
            "id": row["id"], "metadata": json.loads(row["metadata_json"]),
            "counts": json.loads(row["counts_json"]), "content_hash": row["content_hash"],
            "source_type": row["source_type"], "created_at": row["created_at"],
        }

    def save_upload(self, upload: ValidatedUpload):
        # A write lock covers duplicate lookup and insertion, including concurrent requests.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM datasets WHERE content_hash = ?", (upload.content_hash,)).fetchone()
            if existing:
                return self._dataset(existing), False
            dataset_id = str(uuid4())
            now = datetime.now(timezone.utc).isoformat()
            db.execute("INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?)", (
                dataset_id, canonical(upload.metadata), upload.source_type,
                upload.content_hash, now, canonical(upload.counts),
            ))
            db.executemany(
                f"INSERT INTO topics(dataset_id,{','.join(TOPIC_FIELDS)}) VALUES ({','.join('?' for _ in range(1 + len(TOPIC_FIELDS)))})",
                [(dataset_id, *(r[field] for field in TOPIC_FIELDS)) for r in upload.topics],
            )
            db.executemany(
                f"INSERT INTO results(dataset_id,{','.join(RESULT_FIELDS)}) VALUES ({','.join('?' for _ in range(1 + len(RESULT_FIELDS)))})",
                [(dataset_id, *(r[field] for field in RESULT_FIELDS)) for r in upload.results],
            )
            row = db.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
            return self._dataset(row), True

    def get_dataset(self, dataset_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if row is None or (self.demo_only and row["source_type"] != "demo"):
            raise ApiError(404, "DATASET_NOT_FOUND", "Набор данных не найден.")
        return self._dataset(row)

    def list_datasets(self, limit=50, offset=0):
        condition = "WHERE source_type = 'demo'" if self.demo_only else ""
        with self.connect() as db:
            total = db.execute(f"SELECT COUNT(*) FROM datasets {condition}").fetchone()[0]
            rows = db.execute(
                f"SELECT * FROM datasets {condition} ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return {"items": [self._dataset(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def get_topics(self, dataset_id):
        self.get_dataset(dataset_id)
        with self.connect() as db:
            rows = db.execute("SELECT * FROM topics WHERE dataset_id=? ORDER BY topic_order", (dataset_id,)).fetchall()
        return [{**{key: row[key] for key in TOPIC_FIELDS}, "is_locked": bool(row["is_locked"])} for row in rows]

    def list_results(self, dataset_id, *, class_ids=None, textbook_ids=None,
                     topic_id=None, stage=None, test_version=None, limit=1000, offset=0):
        self.get_dataset(dataset_id)
        where, params = ["dataset_id = ?"], [dataset_id]
        for name, values in (("class_id", class_ids), ("textbook_id", textbook_ids)):
            if values:
                where.append(f"{name} IN ({','.join('?' for _ in values)})")
                params.extend(values)
        for name, value in (("topic_id", topic_id), ("stage", stage), ("test_version", test_version)):
            if value is not None:
                where.append(f"{name} = ?")
                params.append(value)
        condition = " AND ".join(where)
        with self.connect() as db:
            total = db.execute(f"SELECT COUNT(*) FROM results WHERE {condition}", params).fetchone()[0]
            rows = db.execute(
                f"SELECT {','.join(RESULT_FIELDS)} FROM results WHERE {condition} "
                "ORDER BY student_id, topic_id, stage LIMIT ? OFFSET ?", [*params, limit, offset],
            ).fetchall()
        return {"dataset_id": dataset_id, "items": [dict(x) for x in rows], "total": total, "limit": limit, "offset": offset}

    def load_results(self, dataset_id, **filters):
        """Internal team API: all validated records (at most 10,000), no pagination loss."""
        return self.list_results(dataset_id, limit=10_000, **filters)["items"]

    def get_filters(self, dataset_id):
        self.get_dataset(dataset_id)
        with self.connect() as db:
            classes = [dict(x) for x in db.execute(
                "SELECT class_id AS id, school_id, COUNT(DISTINCT student_id) AS student_count "
                "FROM results WHERE dataset_id=? GROUP BY class_id, school_id ORDER BY class_id", (dataset_id,))]
            books = [x[0] for x in db.execute(
                "SELECT DISTINCT textbook_id FROM results WHERE dataset_id=? ORDER BY textbook_id", (dataset_id,))]
            versions = [dict(x) for x in db.execute(
                "SELECT DISTINCT topic_id, test_version, max_score FROM results WHERE dataset_id=? "
                "ORDER BY topic_id, test_version", (dataset_id,))]
        return {"dataset_id": dataset_id, "classes": classes,
                "textbooks": [{"id": x, "label": x} for x in books],
                "topics": self.get_topics(dataset_id), "test_versions": versions}
