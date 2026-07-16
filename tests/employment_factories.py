from werkzeug.security import generate_password_hash

from app import create_app, employment_repository, repositories
from app.db import get_db
from app.services import student_goals


def create_user(username="evidence-admin", role="admin"):
    return repositories.create_user(
        {
            "username": username,
            "display_name": username,
            "password_hash": "test-only-hash",
            "role": role,
        }
    )


def create_source(actor_id):
    return repositories.create_intelligence_source(
        {
            "name": f"测试来源-{actor_id}",
            "url": f"https://example.test/source-{actor_id}",
        },
        actor_id,
    )


def create_published_job_and_skill(
    job_name="测试数据分析师", skill_name="测试SQL"
):
    job_id = repositories.create_knowledge_job(
        {"name": job_name, "industry_name": "测试产业"}
    )
    skill_id = repositories.create_knowledge_skill(
        {"name": skill_name, "skill_type": "工具技能"}
    )
    repositories.update_knowledge_status("job", job_id, "已发布")
    repositories.update_knowledge_status("skill", skill_id, "已发布")
    return job_id, skill_id


def create_market_prerequisites():
    actor_id = create_user(username="market-admin")
    source_id = create_source(actor_id)
    job_id, _ = create_published_job_and_skill("测试就业岗位", "测试市场技能")
    return actor_id, source_id, job_id


def goal_student(app, primary_goal, name):
    with app.app_context():
        return student_goals.create_student_with_goal(
            {
                "name": name,
                "gender": "女",
                "enrollment_year": 2024,
                "current_term": "大二下",
                "school": "示例大学",
                "college": "商学院",
                "major": "经济学",
                "city": "上海",
                "responsible_teacher": "测试老师",
            },
            {
                "primary_goal": primary_goal,
                "alternate_goal": "升学" if primary_goal == "就业" else "就业",
                "decision_reason": "功能测试目标分流",
            },
            actor_id=None,
        )


def employment_student(app):
    return goal_student(app, "就业", "就业工作区学生")


def advancement_student(app):
    return goal_student(app, "升学", "升学工作区学生")


def configured_employment_student(app):
    with app.app_context():
        actor_id = create_user(username="workspace-admin")
        source_id = create_source(actor_id)
        job_id, published_skill_id = create_published_job_and_skill(
            "测试经营分析师", "已审核技能"
        )
        draft_skill_id = repositories.create_knowledge_skill(
            {"name": "草稿技能", "skill_type": "工具技能"}
        )
        repositories.update_knowledge_status("skill", draft_skill_id, "已发布")
        student_id = student_goals.create_student_with_goal(
            {
                "name": "完整就业工作区学生",
                "gender": "女",
                "enrollment_year": 2024,
                "current_term": "大二下",
                "school": "示例大学",
                "major": "经济学",
            },
            {"primary_goal": "就业", "alternate_goal": "升学", "decision_reason": "准备就业"},
            actor_id,
        )
        repositories.upsert_student_job_target(
            student_id, {"job_id": job_id, "priority": 1}, actor_id
        )
        common = {
            "job_id": job_id,
            "source_id": source_id,
            "evidence_note": "测试关系证据",
            "confidence_level": "中",
            "sample_size": 120,
            "last_verified_at": "2026-07-15",
            "next_check_at": "2026-10-15",
            "owner_user_id": actor_id,
            "reviewer_user_id": actor_id,
            "limitation_note": "测试数据，不代表真实市场",
        }
        repositories.create_job_skill_link({**common, "skill_id": published_skill_id}, actor_id)
        repositories.create_job_skill_link({**common, "skill_id": draft_skill_id}, actor_id)
        rows = get_db().execute(
            "SELECT id, skill_id FROM job_skill_links WHERE job_id = ?", (job_id,)
        ).fetchall()
        link_ids = {row["skill_id"]: row["id"] for row in rows}
        repositories.submit_job_skill_link(link_ids[published_skill_id])
        repositories.review_job_skill_link(link_ids[published_skill_id], "已发布")
        return student_id, link_ids[published_skill_id], link_ids[draft_skill_id]


def make_auth_app(tmp_path, name="employment-auth"):
    return create_app({
        "TESTING": True,
        "AUTH_DISABLED": False,
        "SECRET_KEY": "employment-test",
        "DATABASE": tmp_path / f"{name}.sqlite3",
        "UPLOAD_DIR": tmp_path / f"{name}-uploads",
        "GENERATED_DIR": tmp_path / f"{name}-generated",
        "BACKUP_DIR": tmp_path / f"{name}-backups",
    })


def create_login_user(role, username):
    return repositories.create_user({
        "username": username,
        "display_name": username,
        "password_hash": generate_password_hash(
            "password123", method="pbkdf2:sha256:600000"
        ),
        "role": role,
    })


def login(client, username):
    return client.post("/login", data={"username": username, "password": "password123"})


def complete_employment_student(app):
    student_id, published_link_id, _ = configured_employment_student(app)
    with app.app_context():
        actor = repositories.get_user_by_username("workspace-admin")
        link = repositories.get_job_skill_link(published_link_id)
        target = repositories.list_student_job_targets(student_id)[0]
        snapshot_id = employment_repository.create_market_snapshot(
            {
                "job_id": target["job_id"],
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
                "source_id": link["source_id"],
                "evidence_summary": "功能测试招聘摘要",
                "limitation_note": "测试数据，仅用于功能验证，不代表真实市场",
                "owner_user_id": actor["id"],
                "reviewer_user_id": actor["id"],
                "next_check_at": "2026-10-15",
                "data_classification": "测试数据",
            },
            [{
                "dimension_type": "热门技能",
                "label": "已审核技能",
                "value": 68,
                "unit": "%",
                "sample_size": 120,
                "sort_order": 1,
            }],
            actor["id"],
        )
        employment_repository.submit_market_snapshot(snapshot_id)
        employment_repository.review_market_snapshot(snapshot_id, "已发布")
        repositories.upsert_student_skill_assessment(
            student_id,
            {
                "skill_id": link["skill_id"],
                "current_level": 2,
                "evidence_note": "课程项目证据",
            },
            actor["id"],
        )
        employment_repository.upsert_analysis_draft(
            student_id,
            {
                "suitability_summary": "专业基础与岗位相关",
                "risk_summary": "缺少真实项目经历",
                "action_recommendations": "优先完成 SQL 项目",
                "limitation_note": "全部市场数据为功能测试数据",
            },
            actor["id"],
        )
        return student_id, link["skill_id"]
