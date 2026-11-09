import json
import sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone


class SnapshotStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS aidana_plan_snapshots (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)')

    def save(self, snapshot):
        result = {**snapshot, 'plan_id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat()}
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('INSERT INTO aidana_plan_snapshots VALUES (?, ?)',
                       (result['plan_id'], json.dumps(result, ensure_ascii=False, allow_nan=False)))
        return result

    def get(self, plan_id):
        with sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute('SELECT snapshot FROM aidana_plan_snapshots WHERE id=?', (plan_id,)).fetchone()
        return json.loads(row[0]) if row else None
