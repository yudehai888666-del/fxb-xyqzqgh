from datetime import date

from app import employment_repository, repositories
from app.services import student_goals
from app.services.student_matching import build_student_intelligence_report


class InactiveGoalPath(RuntimeError):
    pass


def require_active_employment_goal(student_id):
    profile = student_goals.get_goal_profile(student_id)
    if profile is None or profile["primary_goal"] != "就业":
        raise InactiveGoalPath("该学生当前不在就业路径")
    return profile


def _breakdown_groups(snapshot):
    groups = {key: [] for key in ("学历", "经验", "热门技能", "地区")}
    for row in employment_repository.list_market_breakdowns(snapshot["id"]):
        groups[row["dimension_type"]].append(dict(row))
    for rows in groups.values():
        maximum = max((row["value"] for row in rows), default=0)
        for row in rows:
            row["bar_percent"] = round(row["value"] / maximum * 100) if maximum else 0
    return groups


def build_workspace(student_id):
    profile = require_active_employment_goal(student_id)
    student = repositories.get_student(student_id)
    matching = build_student_intelligence_report(student)
    targets = repositories.list_student_job_targets(student_id)
    target_ids = {row["job_id"] for row in targets}
    target_jobs = [row for row in matching["jobs"] if row["job"]["id"] in target_ids]
    snapshots = []
    for job_result in target_jobs:
        for snapshot in employment_repository.list_current_market_snapshots(
            job_result["job"]["id"]
        ):
            snapshots.append({"record": snapshot, "breakdowns": _breakdown_groups(snapshot)})
    all_exam_plans = repositories.list_student_exam_plans(student_id)
    today = date.today().isoformat()
    current_exam_plans = [
        row for row in all_exam_plans
        if row["exam_status"] == "已发布"
        and row["next_check_at"] >= today
        and row["official_url"] and row["reviewer_user_id"] and row["limitation_note"]
    ]
    return {
        "student": student,
        "goal_profile": profile,
        "targets": targets,
        "jobs": target_jobs,
        "trends": matching["trends"],
        "market_snapshots": snapshots,
        "exam_plans": current_exam_plans,
        "excluded_exam_plans": [
            row for row in all_exam_plans if row not in current_exam_plans
        ],
        "analysis_draft": employment_repository.get_analysis_draft(student_id),
        "readiness": report_readiness(student_id),
    }


def report_readiness(student_id):
    require_active_employment_goal(student_id)
    blocking = []
    warnings = []
    targets = repositories.list_student_job_targets(student_id)
    primary = next((row for row in targets if row["priority"] == 1), None)
    if primary is None:
        blocking.append("请设置第一目标岗位")
    else:
        requirements = repositories.list_job_skill_requirements(primary["job_id"])
        if not requirements:
            blocking.append("第一目标缺少已审核且未过期的岗位技能关系")
        assessments = {
            row["skill_id"]: row
            for row in repositories.list_student_skill_assessments(student_id)
        }
        missing_core = [
            row["skill_name"] for row in requirements
            if row["importance_level"] == "核心" and row["skill_id"] not in assessments
        ]
        if missing_core:
            blocking.append("核心技能尚未评估：" + "、".join(missing_core))
        zero_without_note = [
            row["skill_name"] for row in requirements
            if row["importance_level"] == "核心"
            and row["skill_id"] in assessments
            and assessments[row["skill_id"]]["current_level"] == 0
            and not assessments[row["skill_id"]]["evidence_note"].strip()
        ]
        if zero_without_note:
            blocking.append("零级核心技能必须明确记录无证据：" + "、".join(zero_without_note))
        if not employment_repository.list_current_market_snapshots(primary["job_id"]):
            blocking.append("第一目标缺少已审核且未过期的市场快照")
    draft = employment_repository.get_analysis_draft(student_id)
    for field, label in (
        ("suitability_summary", "适合原因"),
        ("risk_summary", "主要风险"),
        ("action_recommendations", "行动建议"),
        ("limitation_note", "限制说明"),
    ):
        if draft is None or not draft[field].strip():
            blocking.append(f"老师结论缺少{label}")
    today = date.today().isoformat()
    for plan in repositories.list_student_exam_plans(student_id):
        if (plan["exam_status"] != "已发布"
                or plan["next_check_at"] < today
                or not plan["official_url"] or not plan["reviewer_user_id"]
                or not plan["limitation_note"]):
            warnings.append(f"考试信息不可引用：{plan['exam_name']}")
    for target in targets:
        if target["priority"] == 1:
            continue
        if not repositories.list_job_skill_requirements(target["job_id"]):
            warnings.append(f"第{target['priority']}目标缺少已审核技能关系")
        if not employment_repository.list_current_market_snapshots(target["job_id"]):
            warnings.append(f"第{target['priority']}目标缺少市场快照")
    return {"ready": not blocking, "blocking": blocking, "warnings": warnings}
