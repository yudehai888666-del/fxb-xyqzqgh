from pathlib import Path

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
