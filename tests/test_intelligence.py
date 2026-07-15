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


def test_student_matching_calculates_weighted_skill_gap_and_published_trends(app):
    with app.app_context():
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
        repositories.create_job_skill_link(
            {"job_id": job_id, "skill_id": sql_id, "importance_level": "核心", "proficiency_level": "熟练"}
        )
        repositories.create_job_skill_link(
            {"job_id": job_id, "skill_id": stats_id, "importance_level": "重要", "proficiency_level": "掌握"}
        )
        repositories.upsert_student_skill_assessment(
            student_id, {"skill_id": sql_id, "current_level": 2, "evidence_note": "课程项目"}
        )
        repositories.upsert_student_skill_assessment(
            student_id, {"skill_id": stats_id, "current_level": 2, "evidence_note": "统计学成绩"}
        )
        industry_id = repositories.create_industry({"name": "数字经济"})
        repositories.update_industry_status(industry_id, "已发布")
        trend_id = repositories.create_industry_trend(
            {
                "industry_id": industry_id, "title": "数据治理岗位增长",
                "affected_jobs": "数据分析师", "evidence_summary": "公开数据证据",
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
        repositories.create_job_skill_link(
            {"job_id": job_id, "skill_id": skill_id, "importance_level": "核心", "proficiency_level": "掌握"}
        )

    login(client, "admin")
    assert client.post(
        f"/students/{student_id}/intelligence-report/targets",
        data={"job_id": job_id, "priority": 1, "target_note": "第一方向"},
    ).status_code == 302
    assert client.post(
        f"/students/{student_id}/intelligence-report/skills",
        data={"skill_id": skill_id, "current_level": 1, "evidence_note": "访谈作业"},
    ).status_code == 302
    page = client.get(f"/students/{student_id}/employment")
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
             "reviewer_user_id": admin_id, "next_check_at": "2026-08-01"}, admin_id
        )
        repositories.update_exam_status(exam_id, "已发布")
    login(client, "admin")
    response = client.post(
        f"/students/{student_id}/intelligence-report/exams",
        data={"exam_id": exam_id, "priority": 1, "purpose": "满足毕业要求",
              "preparation_status": "准备中", "personal_deadline": "2026-09-01",
              "next_action": "完成报名", "owner_user_id": admin_id},
    )
    assert response.status_code == 302
    page = client.get(f"/students/{student_id}/employment").get_data(as_text=True)
    assert "这名学生需要参加的考试" in page
    assert "大学英语四级" in page
    assert "完成报名" in page
