import pytest

from backend.app.errors import ApiError
from backend.app.review_inputs import validate_review_structure


def valid_input():
    return {"followup_dataset_id": "followup", "started_on": "2026-10-01", "completed_on": "2026-10-20",
            "actual_hours_by_topic": {"t1": 0, "t2": 3}, "identity_mapping_confirmed": True, "comment": ""}


def test_review_input_keeps_actual_hours_and_confirmation():
    payload = valid_input()
    payload["identity_mapping_confirmed"] = False
    result = validate_review_structure(payload, {"t1", "t2"})
    assert result.actual_hours_by_topic == {"t1": 0, "t2": 3}
    assert result.identity_mapping_confirmed is False  # Must not be silently converted to consent.


@pytest.mark.parametrize("patch", [
    {"actual_hours_by_topic": {"t1": 1.5, "t2": 3}}, {"actual_hours_by_topic": {"t1": -1, "t2": 3}},
    {"actual_hours_by_topic": {"t1": True, "t2": 3}}, {"actual_hours_by_topic": {"t1": "2", "t2": 3}},
    {"actual_hours_by_topic": {"t1": 1}}, {"actual_hours_by_topic": {"t1": 1, "t2": 3, "extra": 2}},
    {"actual_hours_by_topic": {"t1": 1, " t1 ": 2, "t2": 3}},
    {"completed_on": "2026-09-01"}, {"started_on": "01.10.2026"}, {"started_on": 0},
    {"identity_mapping_confirmed": "false"}, {"unexpected": 1},
])
def test_review_input_rejects_invalid_structure(patch):
    with pytest.raises(ApiError) as exc:
        validate_review_structure({**valid_input(), **patch}, {"t1", "t2"})
    assert exc.value.status == 422 and exc.value.code == "INVALID_REVIEW"
