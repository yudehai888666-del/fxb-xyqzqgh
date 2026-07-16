import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone

from app import employment_repository
from app.db import get_db
from app.services import employment_analysis


class ReportNotReady(ValueError):
    def __init__(self, blocking):
        self.blocking = blocking
        super().__init__("；".join(blocking))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def to_plain(value):
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if hasattr(value, "keys") and not isinstance(value, dict):
        return {key: to_plain(value[key]) for key in value.keys()}
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def _snapshot_payload(workspace, generated_at):
    return to_plain({
        "schema_version": 1,
        "calculation_version": "employment-match-v1",
        "generated_at": generated_at,
        "student": {
            "id": workspace["student"].id,
            "name": workspace["student"].name,
            "school": workspace["student"].school,
            "major": workspace["student"].major,
        },
        "goal_profile": dict(workspace["goal_profile"]),
        "targets": [dict(row) for row in workspace["targets"]],
        "jobs": workspace["jobs"],
        "market_snapshots": workspace["market_snapshots"],
        "trends": [dict(row) for row in workspace["trends"]],
        "exam_plans": [dict(row) for row in workspace["exam_plans"]],
        "teacher_analysis": dict(workspace["analysis_draft"]),
        "warnings": workspace["readiness"]["warnings"],
    })


def generate(student_id, actor_id):
    employment_analysis.require_active_employment_goal(student_id)
    readiness = employment_analysis.report_readiness(student_id)
    if not readiness["ready"]:
        raise ReportNotReady(readiness["blocking"])
    workspace = employment_analysis.build_workspace(student_id)
    payload = _snapshot_payload(workspace, utc_now())
    snapshot_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        version = employment_repository.next_report_version(student_id, "就业")
        report_id = employment_repository.insert_intelligence_report(
            student_id, "就业", version, "测试数据", snapshot_json, actor_id
        )
        db.commit()
        return report_id
    except Exception:
        db.rollback()
        raise


def confirm(report_id, student_id, actor_id):
    report = employment_repository.get_intelligence_report(report_id)
    if report is None or report["student_id"] != student_id:
        raise LookupError("报告不存在")
    if report["status"] != "待确认":
        raise ValueError("只有待确认报告可以确认")
    employment_repository.set_report_confirmed(report_id, actor_id)


def void(report_id, student_id, reason, actor_id):
    report = employment_repository.get_intelligence_report(report_id)
    reason = reason.strip()
    if report is None or report["student_id"] != student_id:
        raise LookupError("报告不存在")
    if report["status"] == "已作废" or not reason:
        raise ValueError("作废原因不能为空，且报告不能重复作废")
    employment_repository.set_report_voided(report_id, reason, actor_id)
