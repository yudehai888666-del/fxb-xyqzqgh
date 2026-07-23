import json

import pytest

from app import employment_repository, repositories
from app.db import get_db
from app.services import employment_analysis, intelligence_reports
from tests.employment_factories import (
    complete_employment_student,
    create_login_user,
    employment_student,
    login,
    make_auth_app,
)


def create_ready_real_market_student(app):
    student_id, _ = complete_employment_student(app)
    with app.app_context():
        actor = repositories.get_user_by_username("workspace-admin")
        target = repositories.list_student_job_targets(student_id)[0]
        source_id = employment_repository.list_market_snapshots(target["job_id"])[0]["source_id"]
        source_snapshot_id = get_db().execute(
            """INSERT INTO intelligence_source_snapshots
               (source_id, http_status, content_hash, content_excerpt, created_by)
               VALUES (?, 200, 'report-real-source', '公开岗位样本摘要', ?)""",
            (source_id, actor["id"]),
        ).lastrowid
        get_db().execute(
            """UPDATE intelligence_sources
               SET compliance_note = '已完成公开数据合规审查', is_active = 1
               WHERE id = ?""",
            (source_id,),
        )
        get_db().execute(
            """UPDATE employment_market_snapshots
               SET data_classification = '真实数据', source_snapshot_id = ?,
                   evidence_summary = '公开招聘岗位抽样',
                   limitation_note = '公开招聘样本，不代表全市场'
               WHERE job_id = ?""",
            (source_snapshot_id, target["job_id"]),
        )
        get_db().execute(
            """UPDATE student_job_targets
               SET target_note = '路径：专业推荐'
               WHERE student_id = ? AND job_id = ?""",
            (student_id, target["job_id"]),
        )
        get_db().execute(
            """UPDATE knowledge_jobs
               SET development_direction = '工程能力提升与项目协同。典型路径，不承诺固定年限、薪资或必然晋升。'
               WHERE id = ?""",
            (target["job_id"],),
        )
        get_db().commit()
    return student_id


def test_report_generation_freezes_data_and_increments_versions(app):
    student_id, skill_id = complete_employment_student(app)
    with app.app_context():
        first_id = intelligence_reports.generate(student_id, actor_id=None)
        first_before = employment_repository.get_intelligence_report(first_id)["snapshot_json"]
        repositories.upsert_student_skill_assessment(
            student_id,
            {"skill_id": skill_id, "current_level": 4, "evidence_note": "更新后的证据"},
        )
        second_id = intelligence_reports.generate(student_id, actor_id=None)
        first_after = employment_repository.get_intelligence_report(first_id)["snapshot_json"]
        second = employment_repository.get_intelligence_report(second_id)
        assert first_before == first_after
        assert employment_repository.get_intelligence_report(first_id)["data_classification"] == "测试数据"
        assert second["version"] == 2
        assert json.loads(first_before)["student"]["id"] == student_id


def test_real_report_freezes_target_path_market_evidence_and_development_direction(app):
    student_id = create_ready_real_market_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=1)
        report = employment_repository.get_intelligence_report(report_id)
        payload = json.loads(report["snapshot_json"])
    assert report["data_classification"] == "真实数据"
    assert payload["career_positioning"]["mode"] == "专业推荐"
    assert payload["development_directions"][0]["text"].endswith(
        "典型路径，不承诺固定年限、薪资或必然晋升。"
    )
    assert payload["market_snapshots"][0]["record"]["source_snapshot_id"]


def test_inactive_source_is_not_current_evidence_or_real_report_data(app):
    student_id = create_ready_real_market_student(app)
    with app.app_context():
        target = repositories.list_student_job_targets(student_id)[0]
        snapshot = employment_repository.list_market_snapshots(target["job_id"])[0]
        get_db().execute(
            "UPDATE intelligence_sources SET is_active = 0 WHERE id = ?",
            (snapshot["source_id"],),
        )
        get_db().commit()
        workspace = employment_analysis.build_workspace(student_id)
        assert workspace["market_snapshots"] == []
        assert intelligence_reports._report_classification({
            "market_snapshots": [{"record": snapshot}],
        }) == "测试数据"
        with pytest.raises(intelligence_reports.ReportNotReady):
            intelligence_reports.generate(student_id, actor_id=1)


def test_report_detail_renders_frozen_real_market_evidence(client, app):
    student_id = create_ready_real_market_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=1)
        get_db().execute(
            "UPDATE knowledge_jobs SET development_direction = '不应出现在冻结报告中'"
        )
        get_db().commit()
    text = client.get(
        f"/students/{student_id}/employment/reports/{report_id}"
    ).get_data(as_text=True)
    assert "路径：专业推荐" in text
    assert "公开招聘岗位抽样" in text
    assert "公开招聘样本，不代表全市场" in text
    assert "真实数据" in text
    assert "工程能力提升与项目协同。典型路径，不承诺固定年限、薪资或必然晋升。" in text
    assert "不应出现在冻结报告中" not in text


def test_generation_rolls_back_when_readiness_changes(app, monkeypatch):
    student_id, _ = complete_employment_student(app)
    monkeypatch.setattr(
        "app.services.intelligence_reports.employment_analysis.report_readiness",
        lambda student_id: {"ready": False, "blocking": ["第一目标缺少市场快照"], "warnings": []},
    )
    with app.app_context(), pytest.raises(intelligence_reports.ReportNotReady):
        intelligence_reports.generate(student_id, actor_id=None)
    with app.app_context():
        assert employment_repository.list_intelligence_reports(student_id, "就业") == []


def test_confirmation_and_voiding_change_status_without_changing_snapshot(app):
    student_id, _ = complete_employment_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=None)
        frozen = employment_repository.get_intelligence_report(report_id)["snapshot_json"]
        intelligence_reports.confirm(report_id, student_id, actor_id=None)
        assert employment_repository.get_intelligence_report(report_id)["status"] == "已确认"
        with pytest.raises(ValueError, match="作废原因不能为空"):
            intelligence_reports.void(report_id, student_id, "", actor_id=None)
        intelligence_reports.void(report_id, student_id, "依据需要重新审核", actor_id=None)
        report = employment_repository.get_intelligence_report(report_id)
        assert report["status"] == "已作废"
        assert report["snapshot_json"] == frozen


def test_report_detail_rejects_report_owned_by_another_student(client, app):
    student_id, _ = complete_employment_student(app)
    other_id = employment_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=None)
    assert client.get(f"/students/{other_id}/employment/reports/{report_id}").status_code == 404


def test_report_detail_print_view_contains_test_data_and_limitations(client, app):
    student_id, _ = complete_employment_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=None)
    report_text = client.get(
        f"/students/{student_id}/employment/reports/{report_id}"
    ).get_data(as_text=True)
    assert "测试数据，仅用于功能验证" in report_text
    assert "数据局限" in report_text


def test_collaborator_cannot_generate_report(tmp_path):
    auth_app = make_auth_app(tmp_path, "report-collaborator")
    client = auth_app.test_client()
    with auth_app.app_context():
        collaborator_id = create_login_user("collaborator", "collab")
    student_id, _ = complete_employment_student(auth_app)
    with auth_app.app_context():
        repositories.assign_student_access(student_id, collaborator_id, "编辑")
    login(client, "collab")
    assert client.post(f"/students/{student_id}/employment/reports").status_code == 403
