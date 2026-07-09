from app import repositories


def create_student():
    return repositories.create_student(
        {
            "name": "规划同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "信息学院",
            "major": "计算机类",
        }
    )


def test_create_and_list_planning_documents(app):
    with app.app_context():
        student_id = create_student()
        document_id = repositories.create_planning_document(
            student_id,
            {
                "title": "规划同学大学四年初步规划",
                "content_markdown": "# 初步规划\n\n测试内容",
            },
        )
        documents = repositories.list_planning_documents(student_id)
        document = repositories.get_planning_document(document_id)

    assert document_id == 1
    assert len(documents) == 1
    assert documents[0]["title"] == "规划同学大学四年初步规划"
    assert document["status"] == "草稿"
    assert document["content_markdown"].startswith("# 初步规划")


def test_update_planning_document_file_path(app):
    with app.app_context():
        student_id = create_student()
        document_id = repositories.create_planning_document(
            student_id,
            {
                "title": "文件路径测试",
                "content_markdown": "# 文件路径测试",
            },
        )
        repositories.update_planning_document_file_path(
            document_id,
            "plans/student-1/plan-1.md",
        )
        document = repositories.get_planning_document(document_id)

    assert document["file_path"] == "plans/student-1/plan-1.md"
