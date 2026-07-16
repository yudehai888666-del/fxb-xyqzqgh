from app import repositories


def test_student_detail_shows_existing_planning_documents(client, app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "可见同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "法学",
            }
        )
        document_id = repositories.create_planning_document(
            student_id,
            {
                "title": "可见同学大学四年初步规划",
                "content_markdown": "# 可见同学大学四年初步规划",
                "file_path": "plans/student-1/plan-1.md",
            },
        )

    response = client.get(f"/students/{student_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "形成、确认并交付规划书" in html
    assert "可见同学大学四年初步规划" in html
    assert "老师内部" in html
    assert f"/students/{student_id}/planning/documents/{document_id}" in html
    assert "V1 · 草稿" in html


def test_planning_visibility_can_be_updated(client, app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "权限同学",
                "gender": "男",
                "enrollment_year": 2026,
                "current_term": "大一上",
                "school": "示例大学",
                "major": "经济学",
            }
        )
        document_id = repositories.create_planning_document(
            student_id,
            {"title": "权限规划", "content_markdown": "# 规划"},
        )

    response = client.post(
        f"/students/{student_id}/planning/documents/{document_id}/visibility",
        data={"visibility": "学生与家长可见"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert repositories.get_planning_document(document_id)["visibility"] == "学生与家长可见"

    detail = client.get(f"/students/{student_id}/planning/documents/{document_id}")
    html = detail.get_data(as_text=True)
    assert "可见范围" in html
    assert "当前仅作为发布标记" in html
    assert "不会立即将规划书发送或公开" in html


def test_planning_visibility_rejects_invalid_value(client, app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "越权同学",
                "gender": "女",
                "enrollment_year": 2026,
                "current_term": "大一上",
                "school": "示例大学",
                "major": "法学",
            }
        )
        document_id = repositories.create_planning_document(
            student_id,
            {"title": "越权规划", "content_markdown": "# 规划"},
        )

    response = client.post(
        f"/students/{student_id}/planning/documents/{document_id}/visibility",
        data={"visibility": "公开"},
    )
    assert response.status_code == 400
