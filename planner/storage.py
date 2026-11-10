import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from .contracts import SavedPlan


class SnapshotStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS aidana_plan_snapshots (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)')

    def save(self, snapshot, *, response_factory=None):
        result = {**snapshot, 'plan_id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat()}
        # Validate the complete transport contract and serialize before any write.
        result = SavedPlan.model_validate(result).model_dump(mode='json', exclude_unset=True)
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        # The API prepares its response bytes here, not after the transaction commits.
        response = response_factory(result) if response_factory is not None else result
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('INSERT INTO aidana_plan_snapshots VALUES (?, ?)',
                       (result['plan_id'], encoded))
        return response

    def get(self, plan_id):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            row = db.execute('SELECT snapshot FROM aidana_plan_snapshots WHERE id=?', (plan_id,)).fetchone()
        return json.loads(row[0]) if row else None
