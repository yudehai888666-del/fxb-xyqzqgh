import hashlib
import importlib
import inspect
import logging
import sqlite3

import pytest

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


def _approved_source(app, admin_id, crawler):
    platform = next(platform for platform in crawler.load_config()["platforms"] if platform["enabled"])
    with app.app_context():
        return repositories.create_intelligence_source(
            {
                "name": platform["name"],
                "url": platform["url"],
                "source_kind": platform["source_kind"],
                "collection_mode": platform.get("collection_mode", "公开网页"),
                "compliance_note": "已批准采集该公开招聘列表页面。",
                "owner_user_id": admin_id,
                "reviewer_user_id": admin_id,
            },
            admin_id,
        )


def _sample_post(job_name, city="上海"):
    return {
        "company": "示例科技",
        "title": job_name,
        "salary": "15k-25k",
        "education": "本科",
        "experience": "1-3年",
        "city": city,
        "description": "Python MySQL Docker",
    }


def _response_snapshot(source_id, content_hash="sample", excerpt="1 条公开岗位样本"):
    return {
        "source_id": source_id,
        "http_status": 200,
        "content_hash": content_hash,
        "content_excerpt": excerpt,
    }


def test_crawler_defaults_to_flask_application_database():
    crawler = importlib.import_module("scripts.career_crawler")
    signature = inspect.signature(crawler.crawl_and_store)
    assert signature.parameters["db_path"].default == "instance/academic_planning.sqlite3"
    assert crawler.DEFAULT_DB_PATH.name == "academic_planning.sqlite3"


def test_deduplicate_posts_uses_company_title_city_salary_and_description():
    crawler = importlib.import_module("scripts.career_crawler")
    posts = [
        {"company": "船厂A", "title": "船舶设计工程师", "city": "上海", "salary": "15k-25k", "description": "CAD CAE 船体结构"},
        {"company": "船厂A", "title": "船舶设计工程师", "city": "上海", "salary": "15k-25k", "description": "CAD CAE 船体结构"},
    ]

    assert len(crawler.deduplicate_posts(posts, crawler.load_config())) == 1


def test_salary_parser_excludes_bonus_equity_and_confidential_terms():
    crawler = importlib.import_module("scripts.career_crawler")

    for salary in ("15k-25k·13薪", "15k-25k 年终奖", "15k-25k+股权", "15k-25k 期权", "面议", "薪资保密"):
        assert crawler.parse_salary_to_monthly(salary) is None


def test_fetch_records_sanitized_error_payload_and_stops_page(monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    html = "<html><title>公开岗位</title><body>完整职位描述不应进入快照</body></html>"
    calls = []

    def fake_get(url, config, logger):
        calls.append(url)
        return 429, html, ""

    monkeypatch.setattr(crawler, "_http_get", fake_get)
    posts, payloads = crawler.fetch_approved_posts(
        "后端开发工程师",
        "上海",
        3,
        crawler.load_config(),
        logging.getLogger("test_crawler"),
        [{
            **next(platform for platform in crawler.load_config()["platforms"] if platform["enabled"]),
            "source_id": 7,
        }],
    )

    assert posts == []
    assert len(calls) == 1
    assert payloads == [{
        "source_id": 7,
        "http_status": 429,
        "content_hash": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "page_title": "公开岗位",
        "content_excerpt": "公开页面采集失败：HTTP 429，停止当前页面采集",
        "content_bytes": len(html.encode("utf-8")),
        "error_message": "HTTP 429，停止当前页面采集",
    }]


def test_crawl_writes_real_draft_linked_to_source_snapshot(app, monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    admin_id, job_id, db_path = _published_job(app, name="后端开发工程师", family="计算机")
    source_id = _approved_source(app, admin_id, crawler)
    monkeypatch.setattr(
        crawler,
        "fetch_approved_posts",
        lambda *args: ([_sample_post("后端开发工程师")] * 10, [_response_snapshot(source_id, "a", "10 条公开岗位样本")]),
    )

    result = crawler.crawl_and_store(
        "后端开发工程师",
        city="上海",
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )

    assert result["status"] == "inserted"
    assert result["job_id"] == job_id
    assert result["confidence_level"] == "中"
    assert result["observed_posting_count"] == 1
    assert result["sample_size"] == 1

    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        snapshot = db.execute(
            "SELECT * FROM employment_market_snapshots WHERE id = ?",
            (result["snapshot_id"],),
        ).fetchone()
        assert snapshot["status"] == "草稿"
        assert snapshot["data_classification"] == "真实数据"
        assert snapshot["source_id"] == source_id
        assert snapshot["source_snapshot_id"]
        source_snapshot = db.execute(
            "SELECT * FROM intelligence_source_snapshots WHERE id = ?",
            (snapshot["source_snapshot_id"],),
        ).fetchone()
        assert source_snapshot["source_id"] == source_id
        assert source_snapshot["content_excerpt"] == "10 条公开岗位样本"
        breakdowns = db.execute(
            "SELECT dimension_type, label FROM employment_market_breakdowns WHERE snapshot_id = ?",
            (result["snapshot_id"],),
        ).fetchall()
    labels = {(row["dimension_type"], row["label"]) for row in breakdowns}
    assert ("学历", "本科") in labels
    assert ("经验", "1-3年") in labels
    assert ("地区", "上海") in labels
    assert ("热门技能", "Python") in labels


def test_crawl_requires_matching_approved_source_before_request(app, monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    admin_id, _job_id, db_path = _published_job(app, name="无来源测试岗位")
    monkeypatch.setattr(
        crawler,
        "fetch_approved_posts",
        lambda *_args: pytest.fail("must not request an unapproved source"),
    )

    with pytest.raises(ValueError, match="已启用且具备合规说明的数据源"):
        crawler.crawl_and_store(
            "无来源测试岗位",
            city="上海",
            db_path=db_path,
            owner_user_id=admin_id,
            reviewer_user_id=admin_id,
        )

    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM intelligence_sources").fetchone()[0] == 0


def test_low_confidence_saves_source_snapshots_without_market_draft(app, monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    admin_id, _job_id, db_path = _published_job(app, name="低置信度测试岗位")
    source_id = _approved_source(app, admin_id, crawler)
    monkeypatch.setattr(
        crawler,
        "fetch_approved_posts",
        lambda *args: ([_sample_post("低置信度测试岗位")], [{
            **_response_snapshot(source_id, "low", "0 条公开岗位样本"),
            "error_message": "页面需要登录",
        }]),
    )

    result = crawler.crawl_and_store(
        "低置信度测试岗位",
        city="上海",
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )

    assert result == {"status": "insufficient_confidence", "confidence_level": "低"}
    with sqlite3.connect(db_path) as db:
        snapshot = db.execute(
            "SELECT error_message FROM intelligence_source_snapshots WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        assert snapshot[0] == "页面需要登录"
        assert db.execute("SELECT COUNT(*) FROM employment_market_snapshots").fetchone()[0] == 0


def test_crawl_and_store_skips_existing_draft_snapshot(app, monkeypatch):
    crawler = importlib.import_module("scripts.career_crawler")
    admin_id, job_id, db_path = _published_job(app, name="数据分析师", family="数据/算法")
    source_id = _approved_source(app, admin_id, crawler)
    monkeypatch.setattr(
        crawler,
        "fetch_approved_posts",
        lambda *_args, **_kwargs: ([_sample_post("数据分析师")], [_response_snapshot(source_id, "data")]),
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


@pytest.mark.parametrize("city", ("大连", "青岛", "南通", "舟山", "镇江"))
def test_crawl_and_store_accepts_new_supported_cities(app, monkeypatch, city):
    crawler = importlib.import_module("scripts.career_crawler")
    assert city not in crawler.load_config()["city_codes"]
    admin_id, _job_id, db_path = _published_job(app, name=f"{city}测试岗位")
    source_id = _approved_source(app, admin_id, crawler)
    monkeypatch.setattr(
        crawler,
        "fetch_approved_posts",
        lambda *_args, **_kwargs: ([_sample_post(f"{city}测试岗位", city)], [_response_snapshot(source_id, city)]),
    )

    result = crawler.crawl_and_store(
        f"{city}测试岗位",
        city=city,
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )

    assert result["status"] == "inserted"


@pytest.mark.parametrize("city", ("大连", "青岛", "南通", "舟山", "镇江"))
def test_new_city_normalization_preserves_aggregate_city_label(app, monkeypatch, city):
    crawler = importlib.import_module("scripts.career_crawler")
    assert crawler._extract_city(f"{city}市") == city
    admin_id, _job_id, db_path = _published_job(app, name=f"{city}归一化测试岗位")
    source_id = _approved_source(app, admin_id, crawler)
    monkeypatch.setattr(
        crawler,
        "fetch_approved_posts",
        lambda *_args, **_kwargs: ([_sample_post(f"{city}归一化测试岗位", f"{city}市")], [_response_snapshot(source_id, f"{city}-normalized")]),
    )

    result = crawler.crawl_and_store(
        f"{city}归一化测试岗位",
        city=city,
        db_path=db_path,
        owner_user_id=admin_id,
        reviewer_user_id=admin_id,
    )

    with sqlite3.connect(db_path) as db:
        labels = {
            row[0]
            for row in db.execute(
                """
                SELECT label FROM employment_market_breakdowns
                WHERE snapshot_id = ? AND dimension_type = '地区'
                """,
                (result["snapshot_id"],),
            )
        }
    assert labels == {city}
