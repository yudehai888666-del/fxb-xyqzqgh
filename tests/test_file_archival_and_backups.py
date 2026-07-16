from io import BytesIO
from pathlib import Path

from app import repositories
from app.services.backups import create_backup, restore_backup, verify_backup


def create_student(name="归档同学"):
    return repositories.create_student(
        {
            "name": name,
            "gender": "女",
            "enrollment_year": 2026,
            "current_term": "大一上",
            "school": "示例大学",
            "major": "法学",
        }
    )


def test_uploaded_material_is_registered_in_unified_archive(client, app):
    with app.app_context():
        student_id = create_student()

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "upload",
            "uploader_type": "老师",
            "category": "成绩单",
            "visibility": "学生可见",
            "material": (BytesIO(b"score details"), "score.txt"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302

    with app.app_context():
        files = repositories.list_student_files(student_id)
    assert len(files) == 1
    assert files[0]["source_type"] == "material"
    assert files[0]["category"] == "成绩单"
    assert files[0]["visibility"] == "学生可见"
    assert files[0]["size_bytes"] == len(b"score details")
    assert len(files[0]["sha256"]) == 64


def test_planning_documents_receive_increasing_versions(app):
    with app.app_context():
        student_id = create_student()
        first = repositories.create_planning_document(
            student_id, {"title": "初步规划", "content_markdown": "# V1"}
        )
        second = repositories.create_planning_document(
            student_id, {"title": "初步规划", "content_markdown": "# V2"}
        )
        assert repositories.get_planning_document(first)["version"] == 1
        assert repositories.get_planning_document(second)["version"] == 2
        assert repositories.get_planning_document(second)["visibility"] == "老师内部"


def test_backup_verifies_and_restores_database_and_files(app, tmp_path):
    with app.app_context():
        student_id = create_student("备份同学")

    upload_file = Path(app.config["UPLOAD_DIR"]) / "material.txt"
    generated_file = Path(app.config["GENERATED_DIR"]) / "plan.md"
    upload_file.write_text("材料", encoding="utf-8")
    generated_file.write_text("规划", encoding="utf-8")

    archive = create_backup(
        app.config["DATABASE"],
        app.config["UPLOAD_DIR"],
        app.config["GENERATED_DIR"],
        app.config["BACKUP_DIR"],
    )
    manifest = verify_backup(archive)
    assert "data/database.sqlite3" in manifest["files"]
    assert "data/uploads/material.txt" in manifest["files"]

    restored = tmp_path / "restored"
    restore_backup(
        archive,
        restored / "database.sqlite3",
        restored / "uploads",
        restored / "generated",
    )
    assert (restored / "uploads/material.txt").read_text(encoding="utf-8") == "材料"
    assert (restored / "generated/plan.md").read_text(encoding="utf-8") == "规划"
