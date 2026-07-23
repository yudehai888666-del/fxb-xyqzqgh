from datetime import date
from typing import Any, Mapping, Optional

from app import employment_repository, repositories
from app.services import student_goals
from app.services.student_matching import (
    LEVEL_LABELS,
    REQUIRED_LEVELS,
    build_student_intelligence_report,
)


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


def _salary_label(row):
    if row["salary_min"] is None or row["salary_max"] is None:
        return "暂无薪资数据"
    return f"{row['salary_min'] // 1000}~{row['salary_max'] // 1000} k/月"


def _current_real_snapshots(job_id, filters):
    snapshots = []
    active_sources = {}
    minimum_salary = filters.get("minimum_salary", "").strip()
    try:
        minimum_salary_value = int(minimum_salary) if minimum_salary else None
    except ValueError:
        minimum_salary_value = None
    for row in employment_repository.list_market_snapshots(job_id):
        if (row["status"] != "已发布" or row["data_classification"] != "真实数据"
                or row["sample_size"] <= 0 or row["next_check_at"] < date.today().isoformat()):
            continue
        source_id = row["source_id"]
        if source_id not in active_sources:
            source = repositories.get_intelligence_source(source_id)
            active_sources[source_id] = bool(source and source["is_active"])
        if not active_sources[source_id]:
            continue
        if filters.get("city", "").strip() and row["region"] != filters["city"].strip():
            continue
        if minimum_salary_value and (row["salary_min"] or 0) < minimum_salary_value:
            continue
        breakdowns = _breakdown_groups(row)
        for field, dimension in (("degree", "学历"), ("experience", "经验")):
            requested = filters.get(field, "").strip()
            if requested and not any(item["label"] == requested for item in breakdowns[dimension]):
                break
        else:
            snapshots.append({"record": row, "breakdowns": breakdowns})
    return snapshots


def build_career_positioning(
        student_id: int, filters: Optional[Mapping[str, str]] = None
) -> dict[str, Any]:
    """Build teacher-facing career options from reviewed, current real evidence."""
    require_active_employment_goal(student_id)
    student = repositories.get_student(student_id)
    if student is None:
        raise ValueError("学生不存在")
    normalized_filters = {key: str(value or "") for key, value in (filters or {}).items()}
    candidates = [dict(row) for row in repositories.list_ranked_major_job_candidates(
        student_id, student.major, limit=3
    )]
    warnings = []
    if not candidates:
        warnings.append("该专业暂无同时具备已审核真实市场数据与当前技能证据的推荐岗位。")

    selected_job = None
    selected_job_id = normalized_filters.get("job_id", "").strip()
    if selected_job_id:
        try:
            selected_job = next(
                (dict(row) for row in repositories.list_published_jobs()
                 if row["id"] == int(selected_job_id)),
                None,
            )
        except ValueError:
            selected_job = None
        if selected_job is None:
            warnings.append("个人计划选择的岗位未发布或不存在。")
    personal_snapshots = _current_real_snapshots(
        selected_job["id"], normalized_filters
    ) if selected_job else []
    if selected_job and not personal_snapshots:
        warnings.append("该个人计划暂无符合条件的已审核真实市场证据。")
    if selected_job:
        selected_job["skills"] = [
            dict(row) for row in repositories.list_job_skill_requirements(selected_job["id"])
        ]
        selected_job["market_snapshots"] = personal_snapshots
    return {
        "professional_candidates": candidates,
        "selected_job": selected_job,
        "data_warnings": warnings,
        "filters": normalized_filters,
    }


def _explore_jobs(student, target_ids, assessments):
    assessment_map = {row["skill_id"]: row for row in assessments}
    jobs = []
    for row in repositories.list_major_job_links_with_market(student.major):
        job = dict(row)
        job["salary_label"] = _salary_label(row)
        job["is_targeted"] = job["job_id"] in target_ids
        job["skills"] = []
        for requirement in repositories.list_job_skill_requirements(job["job_id"]):
            required_level = REQUIRED_LEVELS.get(requirement["proficiency_level"], 2)
            assessment = assessment_map.get(requirement["skill_id"])
            current_level = assessment["current_level"] if assessment else 0
            job["skills"].append(
                {
                    "skill_id": requirement["skill_id"],
                    "name": requirement["skill_name"],
                    "type": requirement["skill_type"],
                    "importance": requirement["importance_level"],
                    "required_label": LEVEL_LABELS[required_level],
                    "current_label": LEVEL_LABELS[current_level],
                    "gap": max(required_level - current_level, 0),
                }
            )
        jobs.append(job)
    return jobs


def build_workspace(student_id, career_filters=None):
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
        "skill_assessments": matching["assessments"],
        "explore": _explore_jobs(student, target_ids, matching["assessments"]),
        "career_positioning": build_career_positioning(student_id, career_filters),
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
