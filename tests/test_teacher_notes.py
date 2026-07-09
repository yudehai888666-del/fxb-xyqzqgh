from app import repositories


def create_sample_student():
    return repositories.create_student(
        {
            "name": "张同学",
            "gender": "女",
            "enrollment_year": "2024",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "商学院",
            "major": "金融学",
            "city": "上海",
            "phone": "13800000000",
            "service_stage": "信息收集",
            "responsible_teacher": "王老师",
        }
    )


def test_teacher_notes_save(client, app):
    with app.app_context():
        student_id = create_sample_student()

    response = client.post(
        f"/students/{student_id}/teacher-notes",
        data={
            "source_channel": "家长首次咨询",
            "consultation_stage": "初诊",
            "core_request": "希望明确保研路径",
            "family_student_conflict": "家长目标高，学生暂时观望",
            "resource_match_level": "家庭支持较强",
            "goal_feasibility": "保研需要观察大一绩点",
            "execution_risk": "执行需要老师持续跟进",
            "academic_risk": "数学基础需要补强",
            "transfer_feasibility": "暂不建议转专业",
            "service_suggestions": "先做学业节奏管理",
            "ai_generation_focus": "保研第一，考研第二，就业第三",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        notes = repositories.get_teacher_notes(student_id)
        assert notes["goal_feasibility"] == "保研需要观察大一绩点"
        assert notes["ai_generation_focus"] == "保研第一，考研第二，就业第三"
