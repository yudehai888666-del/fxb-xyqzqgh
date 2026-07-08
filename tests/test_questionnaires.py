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


def test_parent_questionnaire_reuses_primary_parent_contact(client, app):
    with app.app_context():
        student_id = create_sample_student()
        non_primary_parent_id = repositories.create_parent_contact(
            student_id,
            {
                "name": "王先生",
                "relationship": "父亲",
                "phone": "13800000002",
                "communication_method": "电话",
                "is_primary_decision_maker": False,
            },
        )
        primary_parent_id = repositories.create_parent_contact(
            student_id,
            {
                "name": "王女士",
                "relationship": "母亲",
                "phone": "13900000002",
                "communication_method": "微信",
                "is_primary_decision_maker": True,
            },
        )

    client.post(
        f"/students/{student_id}/parent-questionnaire",
        data={
            "parent_name": "王女士",
            "relationship": "母亲",
            "parent_phone": "13900000002",
            "communication_method": "微信",
            "family_resources": "家庭支持稳定",
            "target_priorities": "保研优先",
            "parent_observations": "执行力需要支持",
            "current_concerns": "科研经历不足",
            "investment_willingness": "愿意投入",
        },
        follow_redirects=True,
    )

    with app.app_context():
        questionnaire = repositories.get_parent_questionnaire(student_id)

    assert questionnaire["parent_contact_id"] == primary_parent_id
    assert questionnaire["parent_contact_id"] != non_primary_parent_id


def test_parent_questionnaire_updates_reused_parent_contact(client, app):
    with app.app_context():
        student_id = create_sample_student()
        parent_id = repositories.create_parent_contact(
            student_id,
            {
                "name": "旧姓名",
                "relationship": "旧关系",
                "phone": "13000000000",
                "communication_method": "电话",
                "is_primary_decision_maker": True,
            },
        )

    client.post(
        f"/students/{student_id}/parent-questionnaire",
        data={
            "parent_name": "王女士",
            "relationship": "母亲",
            "parent_phone": "13900000003",
            "communication_method": "微信",
            "family_resources": "家庭支持稳定",
            "target_priorities": "保研第一",
            "parent_observations": "目标感较强",
            "current_concerns": "成绩波动",
            "investment_willingness": "愿意投入科研项目",
        },
        follow_redirects=True,
    )

    with app.app_context():
        questionnaire = repositories.get_parent_questionnaire(student_id)
        parent = repositories.list_parent_contacts(student_id)[0]

    assert questionnaire["parent_contact_id"] == parent_id
    assert questionnaire["parent_name"] == "王女士"
    assert questionnaire["relationship"] == "母亲"
    assert questionnaire["parent_phone"] == "13900000003"
    assert questionnaire["communication_method"] == "微信"
    assert parent.name == "王女士"
    assert parent.relationship == "母亲"
    assert parent.phone == "13900000003"
    assert parent.communication_method == "微信"
    assert parent.questionnaire_status == "已填写"


def test_parent_questionnaire_prefills_existing_primary_parent_contact(client, app):
    with app.app_context():
        student_id = create_sample_student()
        repositories.create_parent_contact(
            student_id,
            {
                "name": "王女士",
                "relationship": "母亲",
                "phone": "13900000004",
                "communication_method": "微信",
                "is_primary_decision_maker": True,
            },
        )

    response = client.get(f"/students/{student_id}/parent-questionnaire")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'value="王女士"' in html
    assert 'value="13900000004"' in html


def test_parent_questionnaire_blank_optional_contact_fields_do_not_erase_existing_contact(
    client, app
):
    with app.app_context():
        student_id = create_sample_student()
        repositories.create_parent_contact(
            student_id,
            {
                "name": "王女士",
                "relationship": "母亲",
                "phone": "13900000005",
                "communication_method": "微信",
                "is_primary_decision_maker": True,
            },
        )

    client.post(
        f"/students/{student_id}/parent-questionnaire",
        data={
            "parent_name": "王女士",
            "relationship": "母亲",
            "parent_phone": "",
            "communication_method": "",
            "family_resources": "家庭支持稳定",
            "target_priorities": "保研第一",
            "parent_observations": "目标清晰",
            "current_concerns": "时间分配",
            "investment_willingness": "愿意投入",
        },
        follow_redirects=True,
    )

    with app.app_context():
        parent = repositories.list_parent_contacts(student_id)[0]
        questionnaire = repositories.get_parent_questionnaire(student_id)

    assert parent.phone == "13900000005"
    assert parent.communication_method == "微信"
    assert questionnaire["parent_phone"] == "13900000005"
    assert questionnaire["communication_method"] == "微信"
