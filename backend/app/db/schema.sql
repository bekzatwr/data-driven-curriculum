CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    metadata_json TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('upload', 'demo')),
    content_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    counts_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    topic_id TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    topic_order INTEGER NOT NULL,
    current_hours INTEGER NOT NULL CHECK(current_hours >= 0),
    min_hours INTEGER NOT NULL CHECK(min_hours >= 0),
    max_hours INTEGER NOT NULL,
    importance INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 3),
    is_locked INTEGER NOT NULL CHECK(is_locked IN (0,1)),
    PRIMARY KEY(dataset_id, topic_id),
    UNIQUE(dataset_id, topic_order),
    CHECK(min_hours <= current_hours AND current_hours <= max_hours)
);
CREATE TABLE IF NOT EXISTS results (
    dataset_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    school_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    teacher_id TEXT,
    textbook_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    test_version TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('pre', 'post')),
    score REAL NOT NULL CHECK(score >= 0),
    max_score REAL NOT NULL CHECK(max_score > 0 AND score <= max_score),
    tested_at TEXT NOT NULL,
    PRIMARY KEY(dataset_id, student_id, topic_id, stage),
    FOREIGN KEY(dataset_id, topic_id) REFERENCES topics(dataset_id, topic_id)
);
CREATE INDEX IF NOT EXISTS results_class_idx ON results(dataset_id, class_id, topic_id, stage);
CREATE INDEX IF NOT EXISTS results_book_idx ON results(dataset_id, textbook_id, topic_id);
-- Storage contract for Aidana. No planner or report endpoints are implemented here.
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    class_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    thresholds TEXT NOT NULL,
    constraints_snapshot TEXT NOT NULL,
    metrics_snapshot TEXT NOT NULL,
    hours_snapshot TEXT NOT NULL,
    manually_edited INTEGER NOT NULL DEFAULT 0 CHECK(manually_edited IN (0,1))
);
-- P1 storage only; business logic and endpoints belong to the respective team modules.
CREATE TABLE IF NOT EXISTS plan_reviews (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    followup_dataset_id TEXT NOT NULL REFERENCES datasets(id),
    started_on TEXT NOT NULL,
    completed_on TEXT NOT NULL,
    actual_hours_by_topic TEXT NOT NULL,
    identity_mapping_confirmed INTEGER NOT NULL CHECK(identity_mapping_confirmed IN (0,1)),
    comment TEXT NOT NULL DEFAULT '',
    metrics_snapshot TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(started_on <= completed_on)
);
PRAGMA user_version = 1;
