from app import repositories


def create_sample_student():
    return repositories.create_student(
        {
            "name": "王同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "经济学院",
            "major": "经济学",
            "city": "上海",
            "phone": "13800000001",
        }
    )


def test_student_questionnaire_save(client, app):
    with app.app_context():
        student_id = create_sample_student()

    client.post(
        f"/students/{student_id}/student-questionnaire",
        data={
            "adaptation_status": "适应良好，社团参与积极",
            "academic_status": "绩点稳定在专业前20%",
            "weak_subjects": "高等数学需要加强",
            "tutoring_needs": "希望每周一次学习复盘",
            "interests_strengths": "数据分析和英语表达较强",
            "future_intentions": "保研优先，考研备选",
            "motivation_status": "目标明确但执行节奏不稳",
        },
        follow_redirects=True,
    )

    with app.app_context():
        row = repositories.get_student_questionnaire(student_id)

    assert row["future_intentions"] == "保研优先，考研备选"


def test_parent_questionnaire_creates_primary_parent(client, app):
    with app.app_context():
        student_id = create_sample_student()

    client.post(
        f"/students/{student_id}/parent-questionnaire",
        data={
            "parent_name": "王女士",
            "relationship": "母亲",
            "parent_phone": "13900000001",
            "communication_method": "微信",
            "family_resources": "家庭支持稳定，可提供升学规划资源",
            "target_priorities": "保研第一，考研第二，就业第三",
            "parent_observations": "孩子自驱力较强，但容易焦虑",
            "current_concerns": "担心专业排名和科研经历不足",
            "investment_willingness": "愿意投入竞赛、科研和语言培训",
        },
        follow_redirects=True,
    )

    with app.app_context():
        parents = repositories.list_parent_contacts(student_id)
        questionnaire = repositories.get_parent_questionnaire(student_id)

    assert parents[0].questionnaire_status == "已填写"
    assert questionnaire["target_priorities"] == "保研第一，考研第二，就业第三"
