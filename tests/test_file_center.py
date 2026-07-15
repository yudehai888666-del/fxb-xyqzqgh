import hashlib

from app import repositories


def create_student():
    return repositories.create_student(
        {"name": "文件同学", "gender": "男", "enrollment_year": 2026,
         "current_term": "大一上", "school": "示例大学", "major": "数学"}
    )


def archive_file(app, student_id, content=b"safe content", key="safe.txt"):
    path = app.config["UPLOAD_DIR"] / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    with app.app_context():
        return repositories.archive_student_file(
            student_id,
            {"source_type": "test", "source_id": 999, "category": "成绩单",
             "original_filename": "成绩单.txt", "storage_area": "uploads", "storage_key": key,
             "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        )


def test_file_center_downloads_verified_file(client, app):
    with app.app_context():
        student_id = create_student()
    file_id = archive_file(app, student_id)
    page = client.get(f"/students/{student_id}/files")
    assert page.status_code == 200
    assert "校验通过" in page.get_data(as_text=True)
    response = client.get(f"/students/{student_id}/files/{file_id}/download")
    assert response.status_code == 200
    assert response.data == b"safe content"
    assert "attachment" in response.headers["Content-Disposition"]


def test_tampered_file_is_blocked(client, app):
    with app.app_context():
        student_id = create_student()
    file_id = archive_file(app, student_id)
    (app.config["UPLOAD_DIR"] / "safe.txt").write_bytes(b"tampered")
    assert client.get(f"/students/{student_id}/files/{file_id}/download").status_code == 409


def test_soft_deleted_file_disappears_and_cannot_download(client, app):
    with app.app_context():
        student_id = create_student()
    file_id = archive_file(app, student_id)
    response = client.post(f"/students/{student_id}/files/{file_id}/delete")
    assert response.status_code == 302
    assert "成绩单.txt" not in client.get(f"/students/{student_id}/files").get_data(as_text=True)
    assert client.get(f"/students/{student_id}/files/{file_id}/download").status_code == 404
