import pytest

from app import employment_repository, repositories
from tests.employment_factories import create_market_prerequisites


def market_data(actor_id, source_id, job_id):
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
        "evidence_summary": "功能测试招聘市场摘要",
        "limitation_note": "合成测试样本，不代表真实招聘市场",
        "owner_user_id": actor_id,
        "reviewer_user_id": actor_id,
        "next_check_at": "2026-10-15",
        "data_classification": "测试数据",
    }


def test_market_snapshot_stores_governed_test_data_and_breakdowns(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        snapshot_id = employment_repository.create_market_snapshot(
            market_data(actor_id, source_id, job_id),
            [
                {
                    "dimension_type": "学历",
                    "label": "本科",
                    "value": 72,
                    "unit": "%",
                    "sample_size": 120,
                    "sort_order": 1,
                },
                {
                    "dimension_type": "热门技能",
                    "label": "SQL",
                    "value": 68,
                    "unit": "%",
                    "sample_size": 120,
                    "sort_order": 1,
                },
            ],
            actor_id=actor_id,
        )
        snapshot = employment_repository.get_market_snapshot(snapshot_id)
        assert snapshot["data_classification"] == "测试数据"
        assert [
            row["label"]
            for row in employment_repository.list_market_breakdowns(snapshot_id)
        ] == ["本科", "SQL"]


def test_market_submission_rejects_zero_sample_size(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        data = market_data(actor_id, source_id, job_id)
        data["sample_size"] = 0
        snapshot_id = employment_repository.create_market_snapshot(data, [], actor_id)
        with pytest.raises(ValueError, match="正样本量"):
            employment_repository.submit_market_snapshot(snapshot_id)


def test_published_market_snapshot_cannot_be_edited(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        data = market_data(actor_id, source_id, job_id)
        snapshot_id = employment_repository.create_market_snapshot(data, [], actor_id)
        employment_repository.submit_market_snapshot(snapshot_id)
        employment_repository.review_market_snapshot(snapshot_id, "已发布")
        with pytest.raises(ValueError, match="不可修改"):
            employment_repository.update_market_snapshot(
                snapshot_id, {**data, "region": "北京"}, [], actor_id
            )


def test_published_market_snapshot_cannot_be_resubmitted(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        snapshot_id = employment_repository.create_market_snapshot(
            market_data(actor_id, source_id, job_id), [], actor_id
        )
        employment_repository.submit_market_snapshot(snapshot_id)
        employment_repository.review_market_snapshot(snapshot_id, "已发布")
        with pytest.raises(ValueError, match="草稿或已退回"):
            employment_repository.submit_market_snapshot(snapshot_id)


def test_real_market_snapshot_requires_a_linked_source_snapshot(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        data = market_data(actor_id, source_id, job_id)
        data.update({"data_classification": "真实数据", "source_snapshot_id": None})
        with pytest.raises(ValueError, match="真实数据必须关联来源快照"):
            employment_repository.create_market_snapshot(data, [], actor_id)


def test_real_market_snapshot_with_valid_evidence_can_be_submitted(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        source_snapshot_id = repositories.record_intelligence_snapshot(
            source_id,
            {
                "http_status": 200,
                "content_hash": "market",
                "content_excerpt": "公开岗位样本",
            },
            actor_id,
        )[0]
        data = market_data(actor_id, source_id, job_id)
        data.update(
            {
                "data_classification": "真实数据",
                "source_snapshot_id": source_snapshot_id,
                "sample_size": 10,
                "observed_posting_count": 13,
                "evidence_summary": "1 个公开来源，10 条有效月薪样本。",
            }
        )
        snapshot_id = employment_repository.create_market_snapshot(data, [], actor_id)
        employment_repository.submit_market_snapshot(snapshot_id)
        assert employment_repository.get_market_snapshot(snapshot_id)["status"] == "待审核"


def test_real_market_submission_rejects_snapshot_from_another_source(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        other_source_id = repositories.create_intelligence_source(
            {"name": "另一个公开来源", "url": "https://example.test/other"}, actor_id
        )
        source_snapshot_id = repositories.record_intelligence_snapshot(
            other_source_id,
            {
                "http_status": 200,
                "content_hash": "other-market",
                "content_excerpt": "其他公开岗位样本",
            },
            actor_id,
        )[0]
        data = market_data(actor_id, source_id, job_id)
        data.update(
            {
                "data_classification": "真实数据",
                "source_snapshot_id": source_snapshot_id,
            }
        )
        snapshot_id = employment_repository.create_market_snapshot(data, [], actor_id)
        with pytest.raises(ValueError, match="真实数据必须关联来源快照"):
            employment_repository.submit_market_snapshot(snapshot_id)
