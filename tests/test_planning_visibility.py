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
    assert "已有规划草稿" in html
    assert "可见同学大学四年初步规划" in html
    assert "plans/student-1/plan-1.md" in html
    assert f"/students/{student_id}/planning/documents/{document_id}" in html
