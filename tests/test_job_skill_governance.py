import sqlite3
from datetime import date, timedelta

import pytest

from app import create_app, repositories
from app.db import get_db
from app.services.student_matching import build_student_intelligence_report
from tests.employment_factories import (
    create_published_job_and_skill,
    create_source,
    create_user,
)


def governed_link_data(actor_id, source_id, job_id, skill_id, **overrides):
    data = {
        "job_id": job_id,
        "skill_id": skill_id,
        "importance_level": "核心",
        "proficiency_level": "熟练",
        "source_id": source_id,
        "evidence_note": "测试岗位样本中频繁要求 SQL",
        "confidence_level": "中",
        "sample_size": 120,
        "last_verified_at": "2026-07-15",
        "next_check_at": (date.today() + timedelta(days=365)).isoformat(),
        "owner_user_id": actor_id,
        "reviewer_user_id": actor_id,
        "limitation_note": "测试样本，仅验证流程，不代表真实市场",
    }
    data.update(overrides)
    return data


def find_link_id(job_id, skill_id):
    return get_db().execute(
        "SELECT id FROM job_skill_links WHERE job_id = ? AND skill_id = ?",
        (job_id, skill_id),
    ).fetchone()["id"]


def create_published_governed_link(actor_id, source_id, job_id, skill_id):
    link_id = repositories.create_job_skill_link(
        governed_link_data(actor_id, source_id, job_id, skill_id), actor_id
    )
    repositories.submit_job_skill_link(link_id)
    repositories.review_job_skill_link(link_id, "已发布")
    return link_id


def test_job_skill_link_requires_governance_before_submission(app):
    with app.app_context():
        actor_id = create_user()
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill()
        repositories.create_job_skill_link({"job_id": job_id, "skill_id": skill_id})
        link_id = find_link_id(job_id, skill_id)
        with pytest.raises(ValueError, match="提交前请补齐"):
            repositories.submit_job_skill_link(link_id)
        repositories.create_job_skill_link(
            governed_link_data(actor_id, source_id, job_id, skill_id), actor_id
        )
        repositories.submit_job_skill_link(link_id)
        assert repositories.get_job_skill_link(link_id)["status"] == "待审核"


def test_only_published_governed_link_enters_student_report(app):
    with app.app_context():
        actor_id = create_user(username="report-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试经营分析师", "测试统计"
        )
        student_id = repositories.create_student(
            {
                "name": "证据过滤学生",
                "gender": "女",
                "enrollment_year": 2026,
                "current_term": "大二下",
                "school": "示例大学",
                "major": "经济学",
            }
        )
        repositories.upsert_student_job_target(
            student_id, {"job_id": job_id, "priority": 1}
        )
        repositories.create_job_skill_link(
            governed_link_data(
                actor_id,
                source_id,
                job_id,
                skill_id,
                evidence_note="测试证据",
                sample_size=30,
                limitation_note="测试数据",
            ),
            actor_id,
        )
        link_id = find_link_id(job_id, skill_id)
        report = build_student_intelligence_report(repositories.get_student(student_id))
        assert report["jobs"][0]["skills"] == []
        repositories.submit_job_skill_link(link_id)
        repositories.review_job_skill_link(link_id, "已发布")
        report = build_student_intelligence_report(repositories.get_student(student_id))
        assert report["jobs"][0]["skills"][0]["name"] == "测试统计"


def test_expired_link_is_excluded_and_published_edit_returns_to_draft(app):
    with app.app_context():
        actor_id = create_user(username="expiry-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试过期岗位", "测试过期技能"
        )
        repositories.create_job_skill_link(
            governed_link_data(
                actor_id,
                source_id,
                job_id,
                skill_id,
                last_verified_at="2025-01-01",
                next_check_at="2026-01-01",
            ),
            actor_id,
        )
        link_id = find_link_id(job_id, skill_id)
        repositories.submit_job_skill_link(link_id)
        repositories.review_job_skill_link(link_id, "已发布")
        assert repositories.list_job_skill_requirements(job_id) == []

        repositories.create_job_skill_link(
            governed_link_data(
                actor_id,
                source_id,
                job_id,
                skill_id,
                evidence_note="编辑后的证据",
                next_check_at="2026-12-01",
            ),
            actor_id,
        )
        assert repositories.get_job_skill_link(link_id)["status"] == "草稿"


def test_job_skill_repository_rejects_invalid_governance_values(app):
    with app.app_context():
        actor_id = create_user(username="validation-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试验证岗位", "测试验证技能"
        )
        with pytest.raises(ValueError, match="confidence"):
            repositories.create_job_skill_link(
                governed_link_data(
                    actor_id,
                    source_id,
                    job_id,
                    skill_id,
                    confidence_level="极高",
                )
            )
        with pytest.raises(ValueError, match="sample"):
            repositories.create_job_skill_link(
                governed_link_data(
                    actor_id, source_id, job_id, skill_id, sample_size=-1
                )
            )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("last_verified_at", "2026-7-15"),
        ("last_verified_at", "2026-02-30"),
        ("next_check_at", "永不过期"),
        ("next_check_at", "2026/10/15"),
    ),
)
def test_job_skill_link_rejects_malformed_iso_dates_on_write(app, field, value):
    with app.app_context():
        suffix = abs(hash((field, value)))
        actor_id = create_user(username=f"date-write-{suffix}")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            f"测试日期岗位-{suffix}", f"测试日期技能-{suffix}"
        )
        data = governed_link_data(actor_id, source_id, job_id, skill_id)
        data[field] = value
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            repositories.create_job_skill_link(data, actor_id)


def test_job_skill_link_rejects_reversed_verification_dates(app):
    with app.app_context():
        actor_id = create_user(username="date-order-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试日期顺序岗位", "测试日期顺序技能"
        )
        with pytest.raises(ValueError, match="不得早于"):
            repositories.create_job_skill_link(
                governed_link_data(
                    actor_id,
                    source_id,
                    job_id,
                    skill_id,
                    last_verified_at="2026-10-16",
                    next_check_at="2026-10-15",
                ),
                actor_id,
            )


def test_submit_and_publish_revalidate_dates_after_external_changes(app):
    with app.app_context():
        actor_id = create_user(username="date-lifecycle-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试日期复验岗位", "测试日期复验技能"
        )
        link_id = repositories.create_job_skill_link(
            governed_link_data(actor_id, source_id, job_id, skill_id), actor_id
        )
        get_db().execute(
            "UPDATE job_skill_links SET next_check_at = '永不过期' WHERE id = ?",
            (link_id,),
        )
        get_db().commit()
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            repositories.submit_job_skill_link(link_id)

        get_db().execute(
            "UPDATE job_skill_links SET next_check_at = ? WHERE id = ?",
            ((date.today() + timedelta(days=365)).isoformat(), link_id),
        )
        get_db().commit()
        repositories.submit_job_skill_link(link_id)
        get_db().execute(
            "UPDATE job_skill_links SET last_verified_at = 'not-a-date' WHERE id = ?",
            (link_id,),
        )
        get_db().commit()
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            repositories.review_job_skill_link(link_id, "已发布")


@pytest.mark.parametrize(
    "corruption_sql",
    (
        "UPDATE job_skill_links SET evidence_note = '' WHERE id = ?",
        "UPDATE job_skill_links SET source_id = NULL, source_url = '' WHERE id = ?",
        "UPDATE job_skill_links SET confidence_level = '' WHERE id = ?",
        "UPDATE job_skill_links SET last_verified_at = 'not-a-date' WHERE id = ?",
        "UPDATE job_skill_links SET last_verified_at = '0000-01-01' WHERE id = ?",
        "UPDATE job_skill_links SET next_check_at = '永不过期' WHERE id = ?",
        "UPDATE job_skill_links SET sample_size = -1 WHERE id = ?",
        "UPDATE job_skill_links SET sample_size = 'not-an-integer' WHERE id = ?",
        "UPDATE job_skill_links SET owner_user_id = NULL WHERE id = ?",
        "UPDATE job_skill_links SET reviewer_user_id = NULL WHERE id = ?",
        "UPDATE job_skill_links SET limitation_note = '' WHERE id = ?",
    ),
)
def test_final_requirement_query_revalidates_governance(app, corruption_sql):
    with app.app_context():
        suffix = abs(hash(corruption_sql))
        actor_id = create_user(username=f"boundary-admin-{suffix}")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            f"测试边界岗位-{suffix}", f"测试边界技能-{suffix}"
        )
        link_id = create_published_governed_link(
            actor_id, source_id, job_id, skill_id
        )
        assert len(repositories.list_job_skill_requirements(job_id)) == 1
        get_db().execute("PRAGMA ignore_check_constraints = ON")
        get_db().execute(corruption_sql, (link_id,))
        get_db().execute("PRAGMA ignore_check_constraints = OFF")
        get_db().commit()
        assert repositories.list_job_skill_requirements(job_id) == []


@pytest.mark.parametrize(
    ("field", "sql_value"),
    (
        ("evidence_note", "char(9)"),
        ("evidence_note", "char(28)"),
        ("evidence_note", "char(31)"),
        ("source_url", "char(10)"),
        ("source_url", "char(29)"),
        ("limitation_note", "char(13)"),
        ("limitation_note", "char(30)"),
    ),
)
def test_final_requirement_query_rejects_whitespace_only_text(
    app, field, sql_value
):
    with app.app_context():
        actor_id = create_user(username=f"whitespace-{field}")
        job_id, skill_id = create_published_job_and_skill(
            f"测试空白岗位-{field}", f"测试空白技能-{field}"
        )
        data = governed_link_data(actor_id, None, job_id, skill_id)
        data["source_url"] = "https://example.test/legacy-source"
        link_id = repositories.create_job_skill_link(data, actor_id)
        repositories.submit_job_skill_link(link_id)
        repositories.review_job_skill_link(link_id, "已发布")
        get_db().execute(
            f"UPDATE job_skill_links SET {field} = {sql_value} WHERE id = ?",
            (link_id,),
        )
        get_db().commit()
        assert repositories.list_job_skill_requirements(job_id) == []


@pytest.mark.parametrize("sql_value", ("-1", "'not-an-integer'"))
def test_submit_and_publish_revalidate_sample_size_after_external_changes(
    app, sql_value
):
    with app.app_context():
        suffix = "negative" if sql_value == "-1" else "text"
        actor_id = create_user(username=f"sample-lifecycle-{suffix}")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            f"测试样本复验岗位-{suffix}", f"测试样本复验技能-{suffix}"
        )
        link_id = repositories.create_job_skill_link(
            governed_link_data(actor_id, source_id, job_id, skill_id), actor_id
        )
        get_db().execute("PRAGMA ignore_check_constraints = ON")
        get_db().execute(
            f"UPDATE job_skill_links SET sample_size = {sql_value} WHERE id = ?",
            (link_id,),
        )
        get_db().execute("PRAGMA ignore_check_constraints = OFF")
        get_db().commit()
        with pytest.raises(ValueError, match="sample"):
            repositories.submit_job_skill_link(link_id)

        get_db().execute(
            "UPDATE job_skill_links SET sample_size = 0 WHERE id = ?", (link_id,)
        )
        get_db().commit()
        repositories.submit_job_skill_link(link_id)
        get_db().execute("PRAGMA ignore_check_constraints = ON")
        get_db().execute(
            f"UPDATE job_skill_links SET sample_size = {sql_value} WHERE id = ?",
            (link_id,),
        )
        get_db().execute("PRAGMA ignore_check_constraints = OFF")
        get_db().commit()
        with pytest.raises(ValueError, match="sample"):
            repositories.review_job_skill_link(link_id, "已发布")


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("source_id", "source"),
        ("owner_user_id", "owner"),
        ("reviewer_user_id", "reviewer"),
    ),
)
def test_job_skill_reference_ids_must_exist(app, field, message):
    with app.app_context():
        actor_id = create_user(username=f"reference-{field}")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            f"测试引用岗位-{field}", f"测试引用技能-{field}"
        )
        data = governed_link_data(actor_id, source_id, job_id, skill_id)
        data[field] = 999999
        with pytest.raises(ValueError, match=message):
            repositories.create_job_skill_link(data, actor_id)


def test_review_cannot_publish_draft_or_incomplete_relationship(app):
    with app.app_context():
        job_id, skill_id = create_published_job_and_skill(
            "测试不完整岗位", "测试不完整技能"
        )
        link_id = repositories.create_job_skill_link(
            {"job_id": job_id, "skill_id": skill_id}
        )
        with pytest.raises(ValueError, match="待审核"):
            repositories.review_job_skill_link(link_id, "已发布")
        assert repositories.get_job_skill_link(link_id)["status"] == "草稿"
        assert repositories.list_job_skill_requirements(job_id) == []


def test_submit_only_accepts_draft_or_returned_relationship(app):
    with app.app_context():
        actor_id = create_user(username="submit-state-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试提交状态岗位", "测试提交状态技能"
        )
        link_id = repositories.create_job_skill_link(
            governed_link_data(actor_id, source_id, job_id, skill_id), actor_id
        )
        repositories.submit_job_skill_link(link_id)
        repositories.review_job_skill_link(link_id, "已发布")
        with pytest.raises(ValueError, match="草稿或已退回"):
            repositories.submit_job_skill_link(link_id)
        assert repositories.get_job_skill_link(link_id)["status"] == "已发布"

        repositories.review_job_skill_link(link_id, "已过期")
        with pytest.raises(ValueError, match="草稿或已退回"):
            repositories.submit_job_skill_link(link_id)
        assert repositories.get_job_skill_link(link_id)["status"] == "已过期"


def test_existing_job_skill_rows_migrate_to_draft_idempotently(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    legacy = sqlite3.connect(database)
    legacy.execute(
        """
        CREATE TABLE job_skill_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            importance_level TEXT NOT NULL DEFAULT '核心',
            proficiency_level TEXT NOT NULL DEFAULT '掌握',
            evidence_note TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id, skill_id)
        )
        """
    )
    legacy.execute("INSERT INTO job_skill_links (job_id, skill_id) VALUES (1, 1)")
    legacy.commit()
    legacy.close()

    config = {
        "TESTING": True,
        "DATABASE": database,
        "UPLOAD_DIR": tmp_path / "uploads",
        "GENERATED_DIR": tmp_path / "generated",
        "BACKUP_DIR": tmp_path / "backups",
        "SECRET_KEY": "migration-test",
        "AUTH_DISABLED": True,
    }
    migrated_app = create_app(config)
    create_app(config)
    with migrated_app.app_context():
        columns = {
            row["name"]
            for row in get_db().execute("PRAGMA table_info(job_skill_links)")
        }
        row = get_db().execute("SELECT * FROM job_skill_links").fetchone()
        assert {
            "source_id",
            "confidence_level",
            "sample_size",
            "last_verified_at",
            "next_check_at",
            "owner_user_id",
            "reviewer_user_id",
            "status",
            "limitation_note",
        } <= columns
        assert row["status"] == "草稿"

        actor_id = create_user(username="legacy-reference-admin")
        source_id = create_source(actor_id)
        job_id = repositories.create_knowledge_job({"name": "旧库岗位"})
        skill_id = repositories.create_knowledge_skill({"name": "旧库技能"})
        for field in ("source_id", "owner_user_id", "reviewer_user_id"):
            data = governed_link_data(actor_id, source_id, job_id, skill_id)
            data[field] = 999999
            with pytest.raises(ValueError):
                repositories.create_job_skill_link(data, actor_id)


def test_job_skill_submit_and_review_routes_enforce_roles(tmp_path):
    from tests.test_intelligence import create_user as create_auth_user
    from tests.test_intelligence import login, make_auth_app

    auth_app = make_auth_app(tmp_path)
    teacher_client = auth_app.test_client()
    admin_client = auth_app.test_client()
    with auth_app.app_context():
        teacher_id = create_auth_user("teacher", "link-teacher")
        admin_id = create_auth_user("admin", "link-admin")
        source_id = create_source(admin_id)
        job_id, skill_id = create_published_job_and_skill(
            "测试路由岗位", "测试路由技能"
        )
        repositories.create_job_skill_link(
            governed_link_data(
                teacher_id,
                source_id,
                job_id,
                skill_id,
                reviewer_user_id=admin_id,
            ),
            teacher_id,
        )
        link_id = find_link_id(job_id, skill_id)

    login(teacher_client, "link-teacher")
    assert teacher_client.post(
        f"/knowledge/job-skill-links/{link_id}/submit"
    ).status_code == 302
    assert teacher_client.post(
        f"/knowledge/job-skill-links/{link_id}/review", data={"status": "已发布"}
    ).status_code == 403
    login(admin_client, "link-admin")
    assert admin_client.post(
        f"/knowledge/job-skill-links/{link_id}/review", data={"status": "已发布"}
    ).status_code == 302
    with auth_app.app_context():
        assert repositories.get_job_skill_link(link_id)["status"] == "已发布"

    page = admin_client.get("/knowledge").get_data(as_text=True)
    assert "测试数据，不代表真实市场" in page
    for field in (
        "source_id",
        "confidence_level",
        "sample_size",
        "last_verified_at",
        "next_check_at",
        "owner_user_id",
        "reviewer_user_id",
        "limitation_note",
    ):
        assert f'name="{field}"' in page
    assert "测试路由岗位" in page
