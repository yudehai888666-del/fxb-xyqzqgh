import importlib
import inspect
import sqlite3

from app import repositories
from tests.employment_factories import create_login_user


def _published_job(app, name="软件工程师", family="技术/研发"):
    with app.app_context():
        admin_id = create_login_user("admin", "crawler-admin")
        job_id = repositories.create_knowledge_job(
            {"name": name, "industry_name": "互联网", "job_family": family},
            admin_id,
        )
        repositories.update_knowledge_status("job", job_id, "已发布")
        return admin_id, job_id, str(app.config["DATABASE"])


def test_crawler_defaults_to_flask_application_database():
    crawler = importlib.import_module("scripts.career_crawler")
    signature = inspect.signature(crawler.crawl_and_store)
    assert signature.parameters["db_path"].default == "instance/academic_planning.sqlite3"
    assert crawler.DEFAULT_DB_PATH.name == "academic_planning.sqlite3"


def test_crawl_and_store_writes_snapshot_and_breakdowns(app, monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    admin_id, job_id, db_path = _published_job(app)

    def fake_fetch(job_name, city, max_pages, config, logger):
        assert job_name == "软件工程师"
        assert city == "北京"
        assert max_pages == 2
        return [
            {
                "salary": "15k-25k",
                "education": "本科",
                "experience": "3-5年",
                "city": "北京",
                "description": "Python MySQL Docker 微服务",
            },
            {
                "salary": "20k-30k",
                "education": "硕士",
                "experience": "5-10年",
                "city": "北京",
                "description": "Python Redis Kubernetes",
            },
            {
                "salary": "面议",
                "education": "不限",
                "experience": "不限",
                "city": "北京",
                "description": "Java Git Linux",
            },
        ]

    monkeypatch.setattr(crawler, "fetch_platform_posts", fake_fetch)
    result = crawler.crawl_and_store(
        "软件工程师",
        city="北京",
        max_pages=2,
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )

    assert result["status"] == "inserted"
    assert result["job_id"] == job_id
    assert result["observed_posting_count"] == 3
    assert result["sample_size"] == 2
    assert result["salary_min"] == 17500
    assert result["salary_median"] == 22500
    assert result["salary_max"] == 27500

    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        snapshot = db.execute(
            "SELECT * FROM employment_market_snapshots WHERE id = ?",
            (result["snapshot_id"],),
        ).fetchone()
        assert snapshot["status"] == "草稿"
        assert snapshot["data_classification"] == "测试数据"
        assert snapshot["source_id"]
        breakdowns = db.execute(
            "SELECT dimension_type, label, value FROM employment_market_breakdowns WHERE snapshot_id = ?",
            (result["snapshot_id"],),
        ).fetchall()
    labels = {(row["dimension_type"], row["label"]) for row in breakdowns}
    assert ("学历", "本科") in labels
    assert ("经验", "3-5年") in labels
    assert ("地区", "北京") in labels
    assert ("热门技能", "Python") in labels


def test_crawl_and_store_skips_existing_draft_snapshot(app, monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    admin_id, job_id, db_path = _published_job(app, name="数据分析师", family="数据/算法")
    monkeypatch.setattr(
        crawler,
        "fetch_platform_posts",
        lambda *_args, **_kwargs: [
            {
                "salary": "10k-15k",
                "education": "本科",
                "experience": "1-3年",
                "city": "上海",
                "description": "Python SQL Pandas",
            }
        ],
    )

    first = crawler.crawl_and_store(
        "数据分析师",
        city="上海",
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )
    second = crawler.crawl_and_store(
        "数据分析师",
        city="上海",
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )

    assert first["status"] == "inserted"
    assert second == {
        "status": "skipped",
        "reason": "existing_pending_snapshot",
        "job_id": job_id,
        "snapshot_id": first["snapshot_id"],
    }
