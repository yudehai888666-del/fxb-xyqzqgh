import json

import pytest

from app import employment_repository, repositories
from app.services import intelligence_reports
from tests.employment_factories import (
    complete_employment_student,
    create_login_user,
    employment_student,
    login,
    make_auth_app,
)


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
        assert second["version"] == 2
        assert json.loads(first_before)["student"]["id"] == student_id


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
