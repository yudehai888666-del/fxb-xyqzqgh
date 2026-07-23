import importlib

from flask import current_app
from werkzeug.security import generate_password_hash

from app import create_app, repositories
from app.services import student_goals
from app.services.intelligence_collection import CollectionError, validate_public_url
from app.services.student_matching import build_student_intelligence_report


def create_user(role, username):
    return repositories.create_user(
        {
            "username": username,
            "display_name": username,
            "password_hash": generate_password_hash(
                "password123", method="pbkdf2:sha256:600000"
            ),
            "role": role,
        }
    )


def test_seed_career_knowledge_creates_shipbuilding_and_computing_drafts(app):
    seed = importlib.import_module("scripts.seed_career_knowledge")
    with app.app_context():
        admin_id = create_user("admin", "seed-admin")
        result = seed.seed_career_knowledge(
            current_app.config["DATABASE"], admin_id, admin_id
        )
        jobs = {row["name"]: row for row in repositories.list_knowledge_jobs()}
        assert result["jobs"] == 12
        assert jobs["船舶设计工程师"]["job_family"] == "造船"
        assert jobs["后端开发工程师"]["job_family"] == "计算机"
        assert jobs["船舶设计工程师"]["status"] == "草稿"
        second_result = seed.seed_career_knowledge(
            current_app.config["DATABASE"], admin_id, admin_id
        )
        assert second_result["jobs"] == 0


def test_seed_career_knowledge_does_not_overwrite_published_job(app):
    seed = importlib.import_module("scripts.seed_career_knowledge")
    with app.app_context():
        admin_id = create_user("admin", "published-seed-admin")
        seed.seed_career_knowledge(current_app.config["DATABASE"], admin_id, admin_id)
        job = next(
            row for row in repositories.list_knowledge_jobs()
            if row["name"] == "船舶设计工程师"
        )
        repositories.update_knowledge_status("job", job["id"], "已发布")
        from app.db import get_db

        get_db().execute(
            "UPDATE knowledge_jobs SET development_direction = ? WHERE id = ?",
            ("已审核方向", job["id"]),
        )
        get_db().commit()

        seed.seed_career_knowledge(current_app.config["DATABASE"], admin_id, admin_id)
        unchanged = next(
            row for row in repositories.list_knowledge_jobs() if row["id"] == job["id"]
        )
        assert unchanged["development_direction"] == "已审核方向"


def test_seed_career_knowledge_does_not_attach_drafts_to_published_job(app):
    seed = importlib.import_module("scripts.seed_career_knowledge")
    with app.app_context():
        admin_id = create_user("admin", "published-link-seed-admin")
        job_id = repositories.create_knowledge_job({"name": "船舶设计工程师"})
        repositories.update_knowledge_status("job", job_id, "已发布")

        seed.seed_career_knowledge(current_app.config["DATABASE"], admin_id, admin_id)

        from app.db import get_db

        link_count = get_db().execute(
            "SELECT COUNT(*) FROM job_skill_links WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
        assert link_count == 0


def login(client, username):
    return client.post(
        "/login", data={"username": username, "password": "password123"}
    )


def make_auth_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "intelligence-test-secret",
            "AUTH_DISABLED": False,
            "DATABASE": tmp_path / "intelligence.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
            "GENERATED_DIR": tmp_path / "generated",
            "BACKUP_DIR": tmp_path / "backups",
        }
    )


def test_knowledge_graph_stores_major_job_skill_links(app):
    with app.app_context():
        major_id = repositories.create_knowledge_major(
            {"name": "经济学", "source_name": "专业目录"}
        )
        job_id = repositories.create_knowledge_job(
            {
                "name": "数据分析师",
                "industry_name": "数字经济",
                "development_direction": "数据驱动决策需求增长",
            }
        )
        skill_id = repositories.create_knowledge_skill(
            {"name": "SQL", "skill_type": "工具技能"}
        )
        repositories.create_major_job_link(
            {"major_id": major_id, "job_id": job_id, "relevance_level": "高度相关"}
        )
        repositories.create_job_skill_link(
            {
                "job_id": job_id,
                "skill_id": skill_id,
                "importance_level": "核心",
                "proficiency_level": "熟练",
            }
        )

        graph = repositories.list_knowledge_graph_links()
        assert len(graph) == 1
        assert graph[0]["major_name"] == "经济学"
        assert graph[0]["job_name"] == "数据分析师"
        assert "SQL（核心 / 熟练）" in graph[0]["skills"]


def test_exam_edits_create_versioned_snapshots(app):
    with app.app_context():
        exam_id = repositories.create_exam_information(
            {
                "exam_name": "大学英语四级",
                "official_url": "https://example.test/cet4",
                "next_check_at": "2026-09-01",
                "change_summary": "首次录入",
            }
        )
        repositories.update_exam_information(
            exam_id,
            {
                "exam_name": "大学英语四级",
                "official_url": "https://example.test/cet4",
                "exam_date": "2026-12-12",
                "next_check_at": "2026-10-01",
                "change_summary": "补充考试日期",
            },
        )

        exam = repositories.get_exam_information(exam_id)
        revisions = repositories.list_exam_revisions(exam_id)
        assert exam["version"] == 2
        assert exam["status"] == "草稿"
        assert [row["version"] for row in revisions] == [2, 1]
        assert revisions[0]["change_summary"] == "补充考试日期"
        assert '"exam_date": "2026-12-12"' in revisions[0]["snapshot_json"]


def test_teacher_can_enter_but_only_admin_can_publish_knowledge(tmp_path):
    app = make_auth_app(tmp_path)
    teacher_client = app.test_client()
    admin_client = app.test_client()
    with app.app_context():
        create_user("teacher", "teacher")
        create_user("admin", "admin")

    login(teacher_client, "teacher")
    response = teacher_client.post(
        "/knowledge/majors", data={"name": "法学", "source_name": "专业目录"}
    )
    assert response.status_code == 302
    with app.app_context():
        major = repositories.list_knowledge_majors()[0]
        assert major["status"] == "草稿"

    assert teacher_client.post(
        f"/knowledge/major/{major['id']}/status", data={"status": "已发布"}
    ).status_code == 403
    login(admin_client, "admin")
    assert admin_client.post(
        f"/knowledge/major/{major['id']}/status", data={"status": "已发布"}
    ).status_code == 302
    with app.app_context():
        assert repositories.list_knowledge_majors()[0]["status"] == "已发布"


def test_exam_requires_governance_fields_before_review_and_admin_publishes(tmp_path):
    app = make_auth_app(tmp_path)
    teacher_client = app.test_client()
    admin_client = app.test_client()
    with app.app_context():
        teacher_id = create_user("teacher", "teacher")
        admin_id = create_user("admin", "admin")

    login(teacher_client, "teacher")
    response = teacher_client.post(
        "/exams/new",
        data={
            "exam_name": "教师资格考试",
            "collector_user_id": teacher_id,
            "change_summary": "首次录入",
        },
    )
    exam_id = int(response.headers["Location"].rstrip("/").split("/")[-1])
    incomplete = teacher_client.post(f"/exams/{exam_id}/submit")
    assert "error=" in incomplete.headers["Location"]

    teacher_client.post(
        f"/exams/{exam_id}/edit",
        data={
            "exam_name": "教师资格考试",
            "official_url": "https://example.test/ntce",
            "reviewer_user_id": admin_id,
            "execution_owner_user_id": teacher_id,
            "next_check_at": "2026-08-01",
            "change_summary": "补齐责任链和官方来源",
        },
    )
    assert teacher_client.post(f"/exams/{exam_id}/submit").status_code == 302
    with app.app_context():
        assert repositories.get_exam_information(exam_id)["status"] == "待审核"

    assert teacher_client.post(
        f"/exams/{exam_id}/review", data={"status": "已发布"}
    ).status_code == 403
    login(admin_client, "admin")
    assert admin_client.post(
        f"/exams/{exam_id}/review", data={"status": "已发布"}
    ).status_code == 302
    with app.app_context():
        assert repositories.get_exam_information(exam_id)["status"] == "已发布"


def public_resolver(host, port):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


def private_resolver(host, port):
    return [(2, 1, 6, "", ("127.0.0.1", port))]


def synthetic_resolver(host, port):
    return [(2, 1, 6, "", ("198.18.0.216", port))]


def test_collection_url_validation_blocks_private_networks_and_unsafe_ports():
    assert validate_public_url("https://example.test/report", public_resolver).hostname == "example.test"
    for url, resolver in (
        ("http://127.0.0.1/report", private_resolver),
        ("https://user:pass@example.test/report", public_resolver),
        ("https://example.test:8443/report", public_resolver),
        ("file:///etc/passwd", public_resolver),
    ):
        try:
            validate_public_url(url, resolver)
        except CollectionError:
            pass
        else:
            raise AssertionError(f"unsafe URL was accepted: {url}")
    assert validate_public_url(
        "https://example.test/report", synthetic_resolver, allow_synthetic_egress=True
    ).hostname == "example.test"
    try:
        validate_public_url(
            "http://198.18.0.216/report", synthetic_resolver,
            allow_synthetic_egress=True,
        )
    except CollectionError:
        pass
    else:
        raise AssertionError("direct synthetic egress IP was accepted")


def test_source_snapshots_detect_content_changes(app):
    with app.app_context():
        source_id = repositories.create_intelligence_source(
            {"name": "公开就业数据", "url": "https://example.test/jobs"}
        )
        _, first_status = repositories.record_intelligence_snapshot(
            source_id,
            {"http_status": 200, "content_hash": "hash-a", "content_excerpt": "第一版"},
        )
        _, unchanged_status = repositories.record_intelligence_snapshot(
            source_id,
            {"http_status": 200, "content_hash": "hash-a", "content_excerpt": "第一版"},
        )
        _, changed_status = repositories.record_intelligence_snapshot(
            source_id,
            {"http_status": 200, "content_hash": "hash-b", "content_excerpt": "第二版"},
        )

        assert (first_status, unchanged_status, changed_status) == ("首次采集", "无变化", "有变化")
        source = repositories.get_intelligence_source(source_id)
        assert source["last_content_hash"] == "hash-b"
        assert source["last_change_status"] == "有变化"
        assert len(repositories.list_intelligence_snapshots(source_id)) == 3


def test_industry_trend_requires_evidence_source_reviewer_and_check_date(tmp_path):
    app = make_auth_app(tmp_path)
    teacher_client = app.test_client()
    admin_client = app.test_client()
    with app.app_context():
        teacher_id = create_user("teacher", "teacher")
        admin_id = create_user("admin", "admin")
        industry_id = repositories.create_industry({"name": "数字经济"}, teacher_id)
        source_id = repositories.create_intelligence_source(
            {"name": "公开统计", "url": "https://example.test/stat"}, admin_id
        )

    login(teacher_client, "teacher")
    response = teacher_client.post(
        "/industry-trends",
        data={"industry_id": industry_id, "title": "数据岗位需求变化"},
    )
    assert response.status_code == 302
    with app.app_context():
        trend_id = repositories.list_industry_trends()[0]["id"]
    incomplete = teacher_client.post(f"/industry-trends/{trend_id}/submit")
    assert "error=" in incomplete.headers["Location"]

    with app.app_context():
        complete_id = repositories.create_industry_trend(
            {
                "industry_id": industry_id,
                "title": "人工智能带动数据治理能力需求",
                "evidence_summary": "公开统计文本显示相关岗位要求发生变化",
                "source_id": source_id,
                "reviewer_user_id": admin_id,
                "next_check_at": "2026-10-01",
            },
            teacher_id,
        )
    assert teacher_client.post(f"/industry-trends/{complete_id}/submit").status_code == 302
    with app.app_context():
        assert repositories.get_industry_trend(complete_id)["status"] == "待审核"
    assert teacher_client.post(
        f"/industry-trends/{complete_id}/review", data={"status": "已发布"}
    ).status_code == 403
    login(admin_client, "admin")
    assert admin_client.post(
        f"/industry-trends/{complete_id}/review", data={"status": "已发布"}
    ).status_code == 302
    with app.app_context():
        assert repositories.get_industry_trend(complete_id)["status"] == "已发布"


def test_market_snapshot_routes_allow_teacher_submit_and_admin_publish(tmp_path):
    from app import employment_repository

    app = make_auth_app(tmp_path)
    teacher_client = app.test_client()
    admin_client = app.test_client()
    with app.app_context():
        teacher_id = create_user("teacher", "teacher")
        admin_id = create_user("admin", "admin")
        source_id = repositories.create_intelligence_source(
            {"name": "测试就业来源", "url": "https://example.test/market"},
            admin_id,
        )
        job_id = repositories.create_knowledge_job({"name": "就业测试岗位"})
        repositories.update_knowledge_status("job", job_id, "已发布")

    login(teacher_client, "teacher")
    response = teacher_client.post(
        "/employment-market",
        data={
            "job_id": job_id,
            "region": "上海",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "observed_posting_count": 150,
            "sample_size": 120,
            "salary_min": 8000,
            "salary_median": 12000,
            "salary_max": 18000,
            "currency": "CNY",
            "salary_period": "月",
            "source_id": source_id,
            "evidence_summary": "功能测试招聘市场摘要",
            "limitation_note": "合成测试样本，不代表真实招聘市场",
            "owner_user_id": teacher_id,
            "reviewer_user_id": admin_id,
            "next_check_at": "2026-10-15",
            "data_classification": "测试数据",
            "breakdown_type": ["学历"],
            "breakdown_label": ["本科"],
            "breakdown_value": ["72"],
            "breakdown_unit": ["%"],
            "breakdown_sample_size": ["120"],
        },
    )
    assert response.status_code == 302
    with app.app_context():
        snapshot_id = employment_repository.list_market_snapshots()[0]["id"]

    assert teacher_client.post(f"/employment-market/{snapshot_id}/submit").status_code == 302
    assert teacher_client.post(
        f"/employment-market/{snapshot_id}/review", data={"status": "已发布"}
    ).status_code == 403

    login(admin_client, "admin")
    assert admin_client.post(
        f"/employment-market/{snapshot_id}/review", data={"status": "已发布"}
    ).status_code == 302
    with app.app_context():
        assert employment_repository.get_market_snapshot(snapshot_id)["status"] == "已发布"


def test_market_snapshot_routes_only_allow_admin_or_teacher_to_create_or_submit(tmp_path):
    from app import employment_repository

    app = make_auth_app(tmp_path)
    admin_client = app.test_client()
    teacher_client = app.test_client()
    collaborator_client = app.test_client()
    with app.app_context():
        admin_id = create_user("admin", "market-admin")
        teacher_id = create_user("teacher", "market-teacher")
        create_user("collaborator", "market-collaborator")
        source_id = repositories.create_intelligence_source(
            {"name": "授权测试来源", "url": "https://example.test/market-access"},
            admin_id,
        )
        job_id = repositories.create_knowledge_job({"name": "授权测试岗位"})
        repositories.update_knowledge_status("job", job_id, "已发布")

    def market_form_data(owner_user_id, reviewer_user_id):
        return {
            "job_id": job_id,
            "region": "上海",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "observed_posting_count": 150,
            "sample_size": 120,
            "salary_min": 8000,
            "salary_median": 12000,
            "salary_max": 18000,
            "currency": "CNY",
            "salary_period": "月",
            "source_id": source_id,
            "evidence_summary": "授权测试招聘市场摘要",
            "limitation_note": "合成测试样本，不代表真实招聘市场",
            "owner_user_id": owner_user_id,
            "reviewer_user_id": reviewer_user_id,
            "next_check_at": "2026-10-15",
            "data_classification": "测试数据",
        }

    login(teacher_client, "market-teacher")
    assert teacher_client.post(
        "/employment-market", data=market_form_data(teacher_id, admin_id)
    ).status_code == 302
    with app.app_context():
        teacher_snapshot_id = employment_repository.list_market_snapshots()[0]["id"]

    login(collaborator_client, "market-collaborator")
    assert collaborator_client.post(
        "/employment-market", data=market_form_data(teacher_id, admin_id)
    ).status_code == 403
    assert collaborator_client.post(
        f"/employment-market/{teacher_snapshot_id}/submit"
    ).status_code == 403

    assert teacher_client.post(
        f"/employment-market/{teacher_snapshot_id}/submit"
    ).status_code == 302

    login(admin_client, "market-admin")
    assert admin_client.post(
        "/employment-market", data=market_form_data(admin_id, admin_id)
    ).status_code == 302
    with app.app_context():
        admin_snapshot_id = employment_repository.list_market_snapshots()[0]["id"]
    assert admin_client.post(
        f"/employment-market/{admin_snapshot_id}/submit"
    ).status_code == 302


def test_collaborator_can_view_market_snapshots_but_not_create(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        create_user("collaborator", "collab")

    login(client, "collab")
    assert client.get("/employment-market").status_code == 200
    assert client.post("/employment-market", data={}).status_code == 403


def test_teacher_can_view_collection_form_but_only_admin_can_run_it(tmp_path, monkeypatch):
    app = make_auth_app(tmp_path)
    teacher = app.test_client()
    admin = app.test_client()
    with app.app_context():
        admin_id = create_user("admin", "collector-admin")
        create_user("teacher", "collector-teacher")
        job_id = repositories.create_knowledge_job({"name": "船舶设计工程师"}, admin_id)
        repositories.update_knowledge_status("job", job_id, "已发布")
    login(teacher, "collector-teacher")
    assert teacher.get("/employment-market/collect").status_code == 200
    assert teacher.post(
        "/employment-market/collect", data={"job_id": job_id, "city": "上海"}
    ).status_code == 403

    calls = []

    def collect(**kwargs):
        calls.append(kwargs)
        return {"status": "inserted", "snapshot_id": 9}

    monkeypatch.setattr("app.routes.intelligence.crawl_and_store", collect)
    login(admin, "collector-admin")
    assert admin.post(
        "/employment-market/collect",
        data={"job_id": job_id, "city": "上海", "max_pages": "1"},
    ).status_code == 302
    assert calls == [{
        "job_name": "船舶设计工程师",
        "city": "上海",
        "max_pages": 1,
        "db_path": str(app.config["DATABASE"]),
        "owner_user_id": admin_id,
        "reviewer_user_id": admin_id,
    }]
    with app.app_context():
        from app.db import get_db

        audit = get_db().execute(
            "SELECT target_type, target_id, details FROM audit_logs "
            "WHERE action = 'collect_employment_market'"
        ).fetchone()
    assert tuple(audit) == (
        "employment_market_collection",
        job_id,
        f"job_id={job_id},city=上海,outcome=inserted",
    )


def test_collection_rejects_invalid_requests_and_redacts_crawler_failures(tmp_path, monkeypatch):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        admin_id = create_user("admin", "collection-validation-admin")
        published_job_id = repositories.create_knowledge_job(
            {"name": "已发布采集岗位"}, admin_id
        )
        repositories.update_knowledge_status("job", published_job_id, "已发布")
        draft_job_id = repositories.create_knowledge_job(
            {"name": "草稿采集岗位"}, admin_id
        )
    login(client, "collection-validation-admin")

    calls = []
    monkeypatch.setattr(
        "app.routes.intelligence.crawl_and_store",
        lambda **kwargs: calls.append(kwargs),
    )
    invalid_requests = (
        {"job_id": draft_job_id, "city": "上海", "max_pages": "1"},
        {"job_id": published_job_id, "city": "不支持城市", "max_pages": "1"},
        {"job_id": published_job_id, "city": "上海", "max_pages": "4"},
    )
    for data in invalid_requests:
        assert client.post("/employment-market/collect", data=data).status_code == 302
    assert calls == []
    response = client.post(
        "/employment-market/collect", data=invalid_requests[0], follow_redirects=True
    )
    assert "请选择已发布岗位" in response.get_data(as_text=True)

    def fail_collection(**_kwargs):
        raise RuntimeError("internal crawler traceback and credentials")

    monkeypatch.setattr("app.routes.intelligence.crawl_and_store", fail_collection)
    response = client.post(
        "/employment-market/collect",
        data={"job_id": published_job_id, "city": "上海", "max_pages": "1"},
        follow_redirects=True,
    )
    assert "采集暂未完成，请查看审计记录后重试" in response.get_data(as_text=True)
    assert "internal crawler traceback and credentials" not in response.get_data(as_text=True)
    with app.app_context():
        from app.db import get_db

        audit = get_db().execute(
            "SELECT details FROM audit_logs WHERE action = 'collect_employment_market' "
            "ORDER BY id DESC"
        ).fetchone()
    assert audit[0] == f"job_id={published_job_id},city=上海,outcome=failed"


def test_only_admin_configures_sources_but_teacher_can_run_collection(tmp_path, monkeypatch):
    app = make_auth_app(tmp_path)
    teacher_client = app.test_client()
    admin_client = app.test_client()
    with app.app_context():
        create_user("teacher", "teacher")
        create_user("admin", "admin")
        source_id = repositories.create_intelligence_source(
            {"name": "已批准数据源", "url": "https://example.test/public"}
        )
    login(teacher_client, "teacher")
    assert teacher_client.post(
        "/intelligence-sources",
        data={"name": "越权来源", "url": "https://example.test/other"},
    ).status_code == 403

    monkeypatch.setattr(
        "app.routes.intelligence.collect_source",
        lambda source_id, actor_id: (9, "无变化", ""),
    )
    assert teacher_client.post(
        f"/intelligence-sources/{source_id}/collect"
    ).status_code == 302

    monkeypatch.setattr(
        "app.routes.intelligence.validate_public_url", lambda url: None
    )
    login(admin_client, "admin")
    assert admin_client.post(
        "/intelligence-sources",
        data={"name": "管理员来源", "url": "https://example.test/admin"},
    ).status_code == 302


def publish_knowledge(kind, record_id):
    repositories.update_knowledge_status(kind, record_id, "已发布")


def publish_job_skill_requirement(job_id, skill_id, actor_id, **overrides):
    data = {
        "job_id": job_id,
        "skill_id": skill_id,
        "importance_level": "核心",
        "proficiency_level": "掌握",
        "evidence_note": "测试岗位技能证据",
        "source_url": f"https://example.test/jobs/{job_id}/skills/{skill_id}",
        "confidence_level": "中",
        "sample_size": 30,
        "last_verified_at": "2026-07-15",
        "next_check_at": "2099-12-31",
        "owner_user_id": actor_id,
        "reviewer_user_id": actor_id,
        "limitation_note": "仅供自动化测试，不代表真实市场",
    }
    data.update(overrides)
    link_id = repositories.create_job_skill_link(data, actor_id)
    repositories.submit_job_skill_link(link_id)
    repositories.review_job_skill_link(link_id, "已发布")
    return link_id


def test_student_matching_calculates_weighted_skill_gap_and_published_trends(app):
    with app.app_context():
        actor_id = create_user("admin", "matching-admin")
        student_id = repositories.create_student(
            {
                "name": "匹配测试学生", "gender": "女", "enrollment_year": 2026,
                "current_term": "大一上", "school": "示例大学", "major": "经济学",
            }
        )
        major_id = repositories.create_knowledge_major({"name": "经济学"})
        job_id = repositories.create_knowledge_job(
            {"name": "数据分析师", "industry_name": "数字经济"}
        )
        sql_id = repositories.create_knowledge_skill({"name": "SQL"})
        stats_id = repositories.create_knowledge_skill({"name": "统计分析"})
        for kind, record_id in (("major", major_id), ("job", job_id),
                                ("skill", sql_id), ("skill", stats_id)):
            publish_knowledge(kind, record_id)
        repositories.create_major_job_link({"major_id": major_id, "job_id": job_id})
        publish_job_skill_requirement(
            job_id, sql_id, actor_id, importance_level="核心", proficiency_level="熟练"
        )
        publish_job_skill_requirement(
            job_id, stats_id, actor_id, importance_level="重要", proficiency_level="掌握"
        )
        repositories.upsert_student_skill_assessment(
            student_id, {"skill_id": sql_id, "current_level": 2, "evidence_note": "课程项目"}
        )
        repositories.upsert_student_skill_assessment(
            student_id, {"skill_id": stats_id, "current_level": 2, "evidence_note": "统计学成绩"}
        )
        industry_id = repositories.create_industry({"name": "数字经济"})
        repositories.update_industry_status(industry_id, "已发布")
        source_id = repositories.create_intelligence_source(
            {"name": "公开趋势来源", "url": "https://example.test/trends"},
            actor_id,
        )
        trend_id = repositories.create_industry_trend(
            {
                "industry_id": industry_id, "title": "数据治理岗位增长",
                "affected_jobs": "数据分析师",
                "evidence_summary": "公开数据证据",
                "limitation_note": "测试趋势，不代表真实市场",
                "source_id": source_id,
                "reviewer_user_id": actor_id,
                "next_check_at": "2099-12-31",
            }
        )
        repositories.update_industry_trend_status(trend_id, "已发布")

        report = build_student_intelligence_report(repositories.get_student(student_id))
        assert len(report["jobs"]) == 1
        assert report["jobs"][0]["score"] == 80
        assert report["jobs"][0]["coverage"] == 100
        assert report["jobs"][0]["gaps"][0]["name"] == "SQL"
        assert report["jobs"][0]["gaps"][0]["gap"] == 1
        assert report["trends"][0]["title"] == "数据治理岗位增长"


def test_unpublished_jobs_and_skills_do_not_enter_student_report(app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "可信过滤学生", "gender": "男", "enrollment_year": 2026,
                "current_term": "大一上", "school": "示例大学", "major": "法学",
            }
        )
        draft_job_id = repositories.create_knowledge_job({"name": "草稿岗位"})
        repositories.upsert_student_job_target(student_id, {"job_id": draft_job_id, "priority": 1})
        report = build_student_intelligence_report(repositories.get_student(student_id))
        assert report["jobs"] == []
        assert len(report["unpublished_targets"]) == 1
        assert report["data_ready"] is False


def test_admin_can_set_target_and_skill_then_view_visual_report(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        admin_id = create_user("admin", "admin")
        student_id = student_goals.create_student_with_goal(
            {
                "name": "图文报告学生", "gender": "女", "enrollment_year": 2026,
                "current_term": "大一上", "school": "示例大学", "major": "工商管理",
            },
            {"primary_goal": "就业", "alternate_goal": "", "decision_reason": "准备就业"},
            admin_id,
        )
        job_id = repositories.create_knowledge_job({"name": "产品经理", "industry_name": "互联网"})
        skill_id = repositories.create_knowledge_skill({"name": "用户研究"})
        publish_knowledge("job", job_id)
        publish_knowledge("skill", skill_id)
        publish_job_skill_requirement(
            job_id, skill_id, admin_id, importance_level="核心", proficiency_level="掌握"
        )

    login(client, "admin")
    legacy_target = client.post(
        f"/students/{student_id}/intelligence-report/targets",
        data={"job_id": job_id, "priority": 1, "target_note": "第一方向"},
    )
    assert legacy_target.status_code == 307
    assert client.post(
        f"/students/{student_id}/employment/targets",
        data={"job_id": job_id, "priority": 1, "target_note": "第一方向"},
    ).status_code == 302
    legacy_skill = client.post(
        f"/students/{student_id}/intelligence-report/skills",
        data={"skill_id": skill_id, "current_level": 1, "evidence_note": "访谈作业"},
    )
    assert legacy_skill.status_code == 307
    assert client.post(
        f"/students/{student_id}/employment/skills",
        data={"skill_id": skill_id, "current_level": 1, "evidence_note": "访谈作业"},
    ).status_code == 302
    page = client.get(f"/students/{student_id}/employment?tab=skills")
    text = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "目标与职业情报" in text
    assert "产品经理" in text
    assert "50%" in text
    assert "用户研究" in text


def test_published_exam_is_assigned_inside_student_planning_workflow(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        admin_id = create_user("admin", "admin")
        student_id = student_goals.create_student_with_goal(
            {"name": "考试流程学生", "gender": "女", "enrollment_year": 2026,
             "current_term": "大一上", "school": "示例大学", "major": "英语"},
            {"primary_goal": "就业", "alternate_goal": "", "decision_reason": "就业准备"},
            admin_id,
        )
        exam_id = repositories.create_exam_information(
            {"exam_name": "大学英语四级", "official_url": "https://example.test/cet",
             "reviewer_user_id": admin_id, "next_check_at": "2026-08-01",
             "limitation_note": "测试考试，不代表真实考试安排"}, admin_id
        )
        repositories.update_exam_status(exam_id, "已发布")
    login(client, "admin")
    response = client.post(
        f"/students/{student_id}/intelligence-report/exams",
        data={"exam_id": exam_id, "priority": 1, "purpose": "满足毕业要求",
              "preparation_status": "准备中", "personal_deadline": "2026-09-01",
              "next_action": "完成报名", "owner_user_id": admin_id},
    )
    assert response.status_code == 307
    response = client.post(
        f"/students/{student_id}/employment/exams",
        data={"exam_id": exam_id, "priority": 1, "purpose": "满足毕业要求",
              "preparation_status": "准备中", "personal_deadline": "2026-09-01",
              "next_action": "完成报名", "owner_user_id": admin_id},
    )
    assert response.status_code == 302
    page = client.get(f"/students/{student_id}/employment").get_data(as_text=True)
    page = client.get(f"/students/{student_id}/employment?tab=exams").get_data(as_text=True)
    assert "大学英语四级" in page
    assert "完成报名" in page
