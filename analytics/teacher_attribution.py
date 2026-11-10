"""Completeness of teacher IDs in selected, validated assessment records."""


def summarize_teacher_attribution(records):
    """Partition unique pupils by teacher-ID presence without mutating records.

    The caller applies cohort filters first. Both pre and post rows count;
    ``student_id`` has the dataset-wide identity guaranteed by CSV validation.
    A pupil is fully attributed when every selected row has a nonblank ID,
    partially attributed when some do, and unattributed when none do. Different
    nonblank IDs still mean full attribution: presence does not verify a
    teacher's identity, assignment, or continuity between assessments.

    None, empty strings, and whitespace-only strings are missing. A literal
    ID such as "Не указан" is present. The share is fully attributed pupils /
    all selected pupils, or None when there are no pupils. Work and storage
    are linear in the number of input rows; iterators need only one pass.
    """
    students_with_id = set()
    students_without_id = set()
    missing_rows = 0
    for row in records:
        teacher_id = row.get("teacher_id")
        if teacher_id is None or not teacher_id.strip():
            students_without_id.add(row["student_id"])
            missing_rows += 1
        else:
            students_with_id.add(row["student_id"])

    partial = len(students_with_id & students_without_id)
    fully = len(students_with_id) - partial
    unattributed = len(students_without_id) - partial
    students = fully + partial + unattributed
    return {
        "fully_attributed_students": fully,
        "partially_attributed_students": partial,
        "unattributed_students": unattributed,
        "fully_attributed_student_share": fully / students if students else None,
        "missing_teacher_rows": missing_rows,
    }
