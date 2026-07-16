from pathlib import Path

from flask import current_app


def _positive_int(value, field_name):
    try:
        safe_value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive integer")
    if safe_value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return safe_value


def save_planning_markdown(student_id, document_id, title, content_markdown):
    safe_student_id = _positive_int(student_id, "student_id")
    safe_document_id = _positive_int(document_id, "document_id")
    relative_path = Path("plans") / f"student-{safe_student_id}" / f"plan-{safe_document_id}.md"
    destination = Path(current_app.config["GENERATED_DIR"]) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content_markdown, encoding="utf-8")
    return relative_path.as_posix()
