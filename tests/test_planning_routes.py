from pathlib import Path

from app import repositories


def create_student(name="规划同学"):
    return repositories.create_student(
        {
            "name": name,
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "信息学院",
            "major": "计算机类",
            "city": "上海",
            "phone": "13800000008",
            "service_stage": "信息收集",
            "responsible_teacher": "王老师",
        }
    )


def seed_ready_student():
    student_id = create_student()
    repositories.save_student_questionnaire(
        student_id,
        {
            "adaptation_status": "适应良好",
            "academic_status": "成绩稳定",
            "weak_subjects": "数学",
            "tutoring_needs": "学习复盘",
            "interests_strengths": "表达能力强",
            "future_intentions": "保研优先",
            "motivation_status": "目标明确",
        },
    )
    repositories.save_parent_questionnaire(
        student_id,
        {
            "parent_name": "赵女士",
            "relationship": "母亲",
            "parent_phone": "13900000008",
            "communication_method": "微信",
            "family_resources": "家庭支持稳定",
            "target_priorities": "保研第一",
            "parent_observations": "孩子自驱力较强",
            "current_concerns": "科研经历不足",
            "investment_willingness": "愿意投入",
        },
    )
    repositories.save_teacher_notes(
        student_id,
        {
            "source_channel": "家长咨询",
            "consultation_stage": "初诊",
            "core_request": "明确保研路径",
            "family_student_conflict": "目标基本一致",
            "resource_match_level": "支持较强",
            "goal_feasibility": "需要保持绩点",
            "execution_risk": "需要阶段复盘",
            "academic_risk": "数学基础需观察",
            "transfer_feasibility": "暂不转专业",
            "service_suggestions": "先做学业节奏管理",
            "ai_generation_focus": "保研路径",
        },
    )
    repositories.confirm_disclaimer(
        student_id,
        {
            "signer_type": "家长",
            "signer_name": "赵女士",
            "reason": "当前材料暂缺，先基于已填写信息生成规划。",
        },
    )
    return student_id


def test_generate_page_requires_ready_student(client, app):
    with app.app_context():
        student_id = create_student("未完成同学")

    response = client.get(f"/students/{student_id}/planning/generate")

    assert response.status_code == 200
    assert "信息仍需补充" in response.get_data(as_text=True)
    assert "生成初步规划" in response.get_data(as_text=True)


def test_generate_initial_planning_document(client, app):
    with app.app_context():
        student_id = seed_ready_student()

    response = client.post(
        f"/students/{student_id}/planning/generate",
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "规划同学大学四年初步规划" in body
    assert "信息依据与免责声明" in body
    assert "目标风险、备选路径与责任边界" in body

    with app.app_context():
        documents = repositories.list_planning_documents(student_id)
        generated_path = Path(app.config["GENERATED_DIR"]) / documents[0]["file_path"]

    assert len(documents) == 1
    assert documents[0]["file_path"] == (
        f"plans/student-{student_id}/plan-{documents[0]['id']}.md"
    )
    assert generated_path.exists()


def test_post_generate_rejects_unready_student_without_document(client, app):
    with app.app_context():
        student_id = create_student("未完成同学")

    response = client.post(f"/students/{student_id}/planning/generate")

    assert response.status_code == 400
    assert "信息仍需补充" in response.get_data(as_text=True)
    with app.app_context():
        assert repositories.list_planning_documents(student_id) == []


def test_post_generate_cleans_document_when_markdown_save_fails(
    client,
    app,
    monkeypatch,
):
    def fail_save(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr("app.routes.planning.save_planning_markdown", fail_save)
    with app.app_context():
        student_id = seed_ready_student()

    response = client.post(f"/students/{student_id}/planning/generate")

    assert response.status_code == 500
    assert "生成初步规划失败" in response.get_data(as_text=True)
    with app.app_context():
        assert repositories.list_planning_documents(student_id) == []


def test_post_generate_cleans_document_and_file_when_file_path_update_fails(
    client,
    app,
    monkeypatch,
):
    def fail_update(*args, **kwargs):
        raise RuntimeError("db fail")

    monkeypatch.setattr(
        "app.routes.planning.repositories.update_planning_document_file_path",
        fail_update,
    )
    with app.app_context():
        student_id = seed_ready_student()
        generated_dir = Path(app.config["GENERATED_DIR"])

    response = client.post(f"/students/{student_id}/planning/generate")

    assert response.status_code == 500
    assert "生成初步规划失败" in response.get_data(as_text=True)
    with app.app_context():
        assert repositories.list_planning_documents(student_id) == []
    assert list(generated_dir.glob("plans/student-*/plan-*.md")) == []
