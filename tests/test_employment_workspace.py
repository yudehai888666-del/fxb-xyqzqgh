from app import employment_repository, repositories
from app.services import employment_analysis
from tests.employment_factories import (
    advancement_student,
    configured_employment_student,
    create_login_user,
    create_published_job_and_skill,
    employment_student,
    login,
    make_auth_app,
)


def test_employment_workspace_has_six_deep_linkable_tabs(client, app):
    student_id = employment_student(app)
    page = client.get(f"/students/{student_id}/employment?tab=market")
    text = page.get_data(as_text=True)
    assert page.status_code == 200
    for label in ("目标岗位", "技能差距", "市场情报", "证书与考试", "老师结论", "报告版本"):
        assert label in text
    assert 'aria-current="page"' in text
    assert 'aria-label="就业情报工作区"' in text


def test_missing_student_employment_workspace_is_404(client):
    assert client.get("/students/999999/employment").status_code == 404


def test_advancement_student_cannot_write_employment_data(tmp_path):
    auth_app = make_auth_app(tmp_path)
    client = auth_app.test_client()
    with auth_app.app_context():
        create_login_user("admin", "admin")
    student_id = advancement_student(auth_app)
    login(client, "admin")
    response = client.post(
        f"/students/{student_id}/employment/analysis",
        data={
            "suitability_summary": "文本",
            "risk_summary": "文本",
            "action_recommendations": "文本",
            "limitation_note": "文本",
        },
    )
    assert response.status_code == 409


def test_skill_gap_uses_only_governed_requirements(client, app):
    student_id, published_link_id, draft_link_id = configured_employment_student(app)
    with app.app_context():
        workspace = employment_analysis.build_workspace(student_id)
    skill_names = [skill["name"] for job in workspace["jobs"] for skill in job["skills"]]
    assert published_link_id != draft_link_id
    assert "已审核技能" in skill_names
    assert "草稿技能" not in skill_names
    page = client.get(f"/students/{student_id}/employment?tab=skills")
    text = page.get_data(as_text=True)
    assert 'role="img"' in text
    assert 'aria-label="当前水平' in text
    assert "<table" in text


def test_market_charts_have_table_fallback_and_safe_source_links(client, app):
    from tests.employment_factories import complete_employment_student

    student_id, _ = complete_employment_student(app)
    page = client.get(f"/students/{student_id}/employment?tab=market")
    text = page.get_data(as_text=True)
    assert 'class="employment-chart-table"' in text
    assert "<table" in text
    assert 'target="_blank"' not in text or 'rel="noopener"' in text


def test_analysis_draft_persists_and_unknown_tab_is_404(tmp_path):
    auth_app = make_auth_app(tmp_path, "analysis-auth")
    client = auth_app.test_client()
    with auth_app.app_context():
        create_login_user("admin", "admin")
    student_id = employment_student(auth_app)
    login(client, "admin")
    saved = client.post(
        f"/students/{student_id}/employment/analysis",
        data={
            "suitability_summary": "适合原因",
            "risk_summary": "主要风险",
            "action_recommendations": "行动建议",
            "limitation_note": "测试数据限制",
        },
    )
    assert saved.status_code == 302
    with auth_app.app_context():
        assert employment_repository.get_analysis_draft(student_id)["risk_summary"] == "主要风险"
    assert client.get(f"/students/{student_id}/employment?tab=unknown").status_code == 404


def test_collaborator_cannot_write_employment_workspace(tmp_path):
    auth_app = make_auth_app(tmp_path, "collaborator-auth")
    client = auth_app.test_client()
    with auth_app.app_context():
        collaborator_id = create_login_user("collaborator", "collab")
    student_id = employment_student(auth_app)
    with auth_app.app_context():
        repositories.assign_student_access(student_id, collaborator_id, "编辑")
    login(client, "collab")
    response = client.post(
        f"/students/{student_id}/employment/analysis",
        data={
            "suitability_summary": "越权",
            "risk_summary": "越权",
            "action_recommendations": "越权",
            "limitation_note": "越权",
        },
    )
    assert response.status_code == 403


def test_target_validation_and_existing_exam_plan_reuse(tmp_path):
    auth_app = make_auth_app(tmp_path, "target-exam-auth")
    client = auth_app.test_client()
    with auth_app.app_context():
        admin_id = create_login_user("admin", "admin")
        job_id, _ = create_published_job_and_skill("测试目标岗位", "测试目标技能")
        exam_id = repositories.create_exam_information(
            {
                "exam_name": "测试资格考试",
                "official_url": "https://example.test/exam",
                "reviewer_user_id": admin_id,
                "next_check_at": "2026-10-15",
                "limitation_note": "测试考试信息，不代表真实考试安排",
            },
            admin_id,
        )
    student_id = employment_student(auth_app)
    login(client, "admin")
    assert client.post(
        f"/students/{student_id}/employment/targets",
        data={"job_id": job_id, "priority": 4},
    ).status_code == 400
    assert client.post(
        f"/students/{student_id}/employment/exams",
        data={"exam_id": exam_id, "priority": 1},
    ).status_code == 400
    with auth_app.app_context():
        repositories.update_exam_status(exam_id, "已发布")
    saved = client.post(
        f"/students/{student_id}/employment/exams",
        data={
            "exam_id": exam_id,
            "priority": 1,
            "purpose": "就业资格",
            "preparation_status": "准备中",
            "personal_deadline": "2026-09-01",
            "next_action": "完成报名",
            "owner_user_id": admin_id,
        },
    )
    assert saved.status_code == 302
    assert "tab=exams" in saved.headers["Location"]
    assert "测试资格考试" in client.get(saved.headers["Location"]).get_data(as_text=True)
