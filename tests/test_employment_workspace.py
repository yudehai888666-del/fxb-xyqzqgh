from app import employment_repository, repositories
from app.services import employment_analysis
from tests.employment_factories import (
    advancement_student,
    configured_employment_student,
    create_login_user,
    create_published_job_and_skill,
    create_source,
    create_user,
    employment_student,
    login,
    make_auth_app,
)


def test_employment_workspace_has_seven_deep_linkable_tabs(client, app):
    student_id = employment_student(app)
    page = client.get(f"/students/{student_id}/employment?tab=market")
    text = page.get_data(as_text=True)
    assert page.status_code == 200
    for label in ("目标岗位", "技能差距", "市场情报", "证书与考试", "老师结论", "报告版本", "专业探索"):
        assert label in text
    assert 'aria-current="page"' in text
    assert 'aria-label="就业情报工作区"' in text


def _create_explore_records(app):
    with app.app_context():
        actor_id = create_user("explore-admin", "admin")
        source_id = create_source(actor_id)
        student_id = employment_student(app)
        major_id = repositories.create_knowledge_major({"name": "经济学"}, actor_id)
        repositories.update_knowledge_status("major", major_id, "已发布")
        core_job_id = repositories.create_knowledge_job(
            {
                "name": "商业分析师",
                "industry_name": "互联网服务",
                "development_direction": "数据分析、经营诊断、增长策略与跨部门业务决策支持。",
            },
            actor_id,
        )
        related_job_id = repositories.create_knowledge_job(
            {
                "name": "产品运营",
                "industry_name": "数字平台",
                "development_direction": "围绕用户增长、活动策略和产品迭代形成运营闭环。",
            },
            actor_id,
        )
        draft_job_id = repositories.create_knowledge_job({"name": "未发布岗位"}, actor_id)
        for job_id in (core_job_id, related_job_id):
            repositories.update_knowledge_status("job", job_id, "已发布")
        repositories.create_major_job_link(
            {
                "major_id": major_id,
                "job_id": core_job_id,
                "relevance_level": "核心",
                "evidence_note": "经济学核心就业方向",
            },
            actor_id,
        )
        repositories.create_major_job_link(
            {
                "major_id": major_id,
                "job_id": related_job_id,
                "relevance_level": "相关",
                "evidence_note": "经济学相关岗位",
            },
            actor_id,
        )
        repositories.create_major_job_link(
            {"major_id": major_id, "job_id": draft_job_id, "relevance_level": "核心"},
            actor_id,
        )
        skill_id = repositories.create_knowledge_skill(
            {"name": "SQL分析", "skill_type": "工具软件"},
            actor_id,
        )
        draft_skill_id = repositories.create_knowledge_skill(
            {"name": "草稿关系技能", "skill_type": "专业技能"},
            actor_id,
        )
        repositories.update_knowledge_status("skill", skill_id, "已发布")
        repositories.update_knowledge_status("skill", draft_skill_id, "已发布")
        common = {
            "job_id": core_job_id,
            "source_id": source_id,
            "evidence_note": "招聘样本显示为核心能力",
            "confidence_level": "高",
            "sample_size": 80,
            "last_verified_at": "2026-07-01",
            "next_check_at": "2026-10-01",
            "owner_user_id": actor_id,
            "reviewer_user_id": actor_id,
            "limitation_note": "测试数据",
        }
        published_link_id = repositories.create_job_skill_link(
            {**common, "skill_id": skill_id, "importance_level": "核心", "proficiency_level": "熟练"},
            actor_id,
        )
        repositories.create_job_skill_link({**common, "skill_id": draft_skill_id}, actor_id)
        repositories.submit_job_skill_link(published_link_id)
        repositories.review_job_skill_link(published_link_id, "已发布")
        for period_end, salary_min, salary_max in (
            ("2026-05-31", 7000, 12000),
            ("2026-06-30", 9000, 15000),
        ):
            snapshot_id = employment_repository.create_market_snapshot(
                {
                    "job_id": core_job_id,
                    "region": "上海",
                    "period_start": period_end[:8] + "01",
                    "period_end": period_end,
                    "observed_posting_count": 160,
                    "sample_size": 80,
                    "salary_min": salary_min,
                    "salary_median": 12000,
                    "salary_max": salary_max,
                    "source_id": source_id,
                    "evidence_summary": "测试招聘薪资样本",
                    "limitation_note": "测试数据",
                    "owner_user_id": actor_id,
                    "reviewer_user_id": actor_id,
                    "next_check_at": "2026-10-01",
                },
                [],
                actor_id,
            )
            employment_repository.submit_market_snapshot(snapshot_id)
            employment_repository.review_market_snapshot(snapshot_id, "已发布")
        repositories.upsert_student_job_target(
            student_id, {"job_id": core_job_id, "priority": 1}, actor_id
        )
        repositories.upsert_student_skill_assessment(
            student_id,
            {"skill_id": skill_id, "current_level": 2, "evidence_note": "课程项目"},
            actor_id,
        )
        create_login_user("admin", "explore-login-admin")
        return student_id, core_job_id, related_job_id


def test_major_explore_repository_returns_latest_market_and_skill_counts(app):
    student_id, core_job_id, related_job_id = _create_explore_records(app)
    with app.app_context():
        rows = repositories.list_major_job_links_with_market("经济学")
    assert student_id
    assert [row["job_id"] for row in rows] == [core_job_id, related_job_id]
    assert rows[0]["relevance_level"] == "核心"
    assert rows[0]["skill_count"] == 1
    assert rows[0]["salary_min"] == 9000
    assert rows[0]["salary_max"] == 15000
    assert rows[0]["region"] == "上海"
    assert rows[1]["salary_min"] is None


def test_explore_tab_renders_major_jobs_market_and_skills(tmp_path):
    auth_app = make_auth_app(tmp_path, "explore-auth")
    client = auth_app.test_client()
    student_id, _, _ = _create_explore_records(auth_app)
    login(client, "explore-login-admin")
    page = client.get(f"/students/{student_id}/employment?tab=explore")
    text = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "专业探索" in text
    assert "商业分析师" in text
    assert "产品运营" in text
    assert "9~15 k/月" in text
    assert "已设为目标" in text
    assert "加入目标岗位" in text
    assert "SQL分析" in text
    assert "工具软件" in text
    assert "未评估" not in text
    assert 'class="level-dots"' in text
    assert client.get(f"/students/{student_id}/employment/explore-data").status_code == 200


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
