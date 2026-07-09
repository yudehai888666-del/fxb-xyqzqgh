from pathlib import Path

from flask import current_app


def save_planning_markdown(student_id, document_id, title, content_markdown):
    relative_path = Path("plans") / f"student-{student_id}" / f"plan-{document_id}.md"
    destination = Path(current_app.config["GENERATED_DIR"]) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content_markdown, encoding="utf-8")
    return relative_path.as_posix()
