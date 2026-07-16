from pathlib import Path

import pytest

from app.services.planning_files import save_planning_markdown


def test_save_planning_markdown_writes_student_file(app):
    content = "# 测试规划\n\n正文"
    with app.app_context():
        relative_path = save_planning_markdown(3, 9, "测试规划", content)

    expected = Path(app.config["GENERATED_DIR"]) / relative_path
    assert relative_path == "plans/student-3/plan-9.md"
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == content


def test_create_app_creates_generated_dir(app):
    assert Path(app.config["GENERATED_DIR"]).exists()


@pytest.mark.parametrize("student_id", ["../bad", 0, -1])
def test_save_planning_markdown_rejects_unsafe_student_id(app, student_id):
    with app.app_context():
        with pytest.raises(ValueError, match="student_id must be a positive integer"):
            save_planning_markdown(student_id, 1, "x", "# x")


@pytest.mark.parametrize("document_id", ["../bad", 0, -1])
def test_save_planning_markdown_rejects_unsafe_document_id(app, document_id):
    with app.app_context():
        with pytest.raises(ValueError, match="document_id must be a positive integer"):
            save_planning_markdown(1, document_id, "x", "# x")
