from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3

import pytest

from backend.app.db import Store
from backend.app.validation import validate_upload
from .conftest import payload


def test_storage_rolls_back_on_mid_import_failure(settings, sample):
    store = Store(settings.database_path)
    store.initialize()
    upload = validate_upload(*payload(sample), settings)
    # Bypass validation to force a real database failure after dataset/topics have been inserted.
    broken = replace(upload, results=[*upload.results, upload.results[0]])
    with pytest.raises(sqlite3.IntegrityError):
        store.save_upload(broken)
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM topics").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0
    assert store.save_upload(upload)[1] is True


def test_simultaneous_repeated_import_creates_one_dataset(settings, sample):
    store = Store(settings.database_path)
    store.initialize()
    upload = validate_upload(*payload(sample), settings)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: store.save_upload(upload), range(4)))
    assert sum(created for _, created in results) == 1
    assert len({dataset["id"] for dataset, _ in results}) == 1
    assert store.list_datasets()["total"] == 1


def test_schema_initialization_and_foreign_keys(settings):
    store = Store(settings.database_path)
    store.initialize()
    store.initialize()
    with store.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"datasets", "topics", "results", "plans", "plan_reviews"} <= tables
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        db.execute("PRAGMA user_version=2")
    with pytest.raises(RuntimeError, match="newer"):
        store.initialize()
