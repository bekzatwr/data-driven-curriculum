"""Operator-only command: prepare one synthetic report without enabling HTTP writes.

Run once via the container shell; stdout contains the public report/export URLs.
Existing snapshots are reused. This is not an API and never loads external files.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analytics.demo import demo_files
from backend.app.config import Settings
from backend.app.db import Store
from backend.app.validation import validate_upload
from planner.contracts import SavedPlan
from planner.models import SaveRequest
from planner.service import save_plan
from planner.storage import SnapshotStore
from collab.storage import CommentStore
from collab.security import RateStore

COMMENT = "Bundled synthetic public demonstration (operator prepared)"


def prepare_report(settings):
    store = Store(settings.database_path, demo_only=True)
    store.initialize()
    snapshots = SnapshotStore(settings.database_path)
    CommentStore(settings.database_path)
    RateStore(settings.database_path)
    upload = validate_upload(*demo_files(), settings, source_type="demo")
    dataset, _ = store.save_upload(upload)
    with store.connect() as db:
        row = db.execute(
            "SELECT snapshot FROM aidana_plan_snapshots "
            "WHERE json_extract(snapshot, '$.dataset_id') = ? "
            "AND json_extract(snapshot, '$.comment') = ? ORDER BY id LIMIT 1",
            (dataset["id"], COMMENT),
        ).fetchone()
    plan = SavedPlan.model_validate_json(row[0]).model_dump(mode="json", exclude_unset=True) if row else save_plan(
        store, snapshots, dataset["id"], SaveRequest(class_id="7A", comment=COMMENT))
    return {"dataset_id": dataset["id"], "plan_id": plan["plan_id"], "synthetic_data_only": True,
            "report_url": "/api/plans/" + plan["plan_id"],
            "csv_url": "/api/plans/" + plan["plan_id"] + "/export.csv"}


if __name__ == "__main__":
    print(json.dumps(prepare_report(Settings.from_env()), ensure_ascii=False))
