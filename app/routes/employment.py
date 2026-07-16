from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from app import employment_repository, repositories
from app.auth import role_required
from app.services import employment_analysis


employment_bp = Blueprint(
    "employment", __name__, url_prefix="/students/<int:student_id>/employment"
)

TABS = {
    "targets": "employment/_targets.html",
    "skills": "employment/_skills.html",
    "market": "employment/_market.html",
    "exams": "employment/_exams.html",
    "analysis": "employment/_analysis.html",
    "reports": "employment/_reports.html",
}


def _guard(student_id):
    if repositories.get_student(student_id) is None:
        abort(404)
    try:
        employment_analysis.require_active_employment_goal(student_id)
    except employment_analysis.InactiveGoalPath as exc:
        abort(409, description=str(exc))


def _audit(action, student_id, details=""):
    repositories.create_audit_log(
        g.current_user["id"], action, "student", student_id, details,
        request.remote_addr or "",
    )


@employment_bp.get("")
def workspace(student_id):
    _guard(student_id)
    tab = request.args.get("tab", "targets")
    if tab not in TABS:
        abort(404)
    can_edit = g.current_user and g.current_user["role"] in ("admin", "teacher")
    return render_template(
        "employment/workspace.html",
        workspace=employment_analysis.build_workspace(student_id),
        active_tab=tab,
        active_partial=TABS[tab],
        available_jobs=repositories.list_published_jobs(),
        available_skills=repositories.list_published_skills(),
        available_exams=repositories.list_published_exams(),
        users=repositories.list_users() if can_edit else [],
    )


@employment_bp.post("/targets")
@role_required("admin", "teacher")
def save_target(student_id):
    _guard(student_id)
    try:
        job_id = int(request.form.get("job_id", ""))
        priority = int(request.form.get("priority", ""))
    except ValueError:
        abort(400)
    if priority not in (1, 2, 3) or job_id not in {
        row["id"] for row in repositories.list_published_jobs()
    }:
        abort(400)
    repositories.upsert_student_job_target(student_id, request.form, g.current_user["id"])
    _audit("set_student_job_target", student_id, f"job={job_id},priority={priority}")
    return redirect(url_for("employment.workspace", student_id=student_id, tab="targets"))


@employment_bp.post("/skills")
@role_required("admin", "teacher")
def save_skill(student_id):
    _guard(student_id)
    try:
        skill_id = int(request.form.get("skill_id", ""))
        level = int(request.form.get("current_level", ""))
    except ValueError:
        abort(400)
    if level not in range(5) or skill_id not in {
        row["id"] for row in repositories.list_published_skills()
    }:
        abort(400)
    repositories.upsert_student_skill_assessment(student_id, request.form, g.current_user["id"])
    _audit("assess_student_skill", student_id, f"skill={skill_id},level={level}")
    return redirect(url_for("employment.workspace", student_id=student_id, tab="skills"))


@employment_bp.post("/exams")
@role_required("admin", "teacher")
def save_exam(student_id):
    _guard(student_id)
    try:
        exam_id = int(request.form.get("exam_id", ""))
        priority = int(request.form.get("priority", ""))
    except ValueError:
        abort(400)
    if priority not in (1, 2, 3) or exam_id not in {
        row["id"] for row in repositories.list_published_exams()
    }:
        abort(400)
    repositories.upsert_student_exam_plan(student_id, request.form, g.current_user["id"])
    _audit("set_student_exam_plan", student_id, f"exam={exam_id},priority={priority}")
    return redirect(url_for("employment.workspace", student_id=student_id, tab="exams"))


@employment_bp.post("/analysis")
@role_required("admin", "teacher")
def save_analysis(student_id):
    _guard(student_id)
    employment_repository.upsert_analysis_draft(
        student_id, request.form, g.current_user["id"]
    )
    _audit("update_employment_analysis", student_id)
    return redirect(url_for("employment.workspace", student_id=student_id, tab="analysis"))
