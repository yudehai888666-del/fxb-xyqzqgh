from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from app import repositories
from app.auth import role_required
from app.services.student_matching import build_student_intelligence_report


matching_bp = Blueprint("matching", __name__)


def _get_student_or_404(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@matching_bp.get("/students/<int:student_id>/intelligence-report")
def report(student_id):
    student = _get_student_or_404(student_id)
    return render_template(
        "matching/report.html",
        report=build_student_intelligence_report(student),
        available_jobs=repositories.list_published_jobs(),
        available_skills=repositories.list_published_skills(),
        available_exams=repositories.list_published_exams(),
        exam_plans=repositories.list_student_exam_plans(student_id),
        users=repositories.list_users() if g.current_user and g.current_user["role"] in ("admin", "teacher") else [],
        message=request.args.get("message", ""),
        error=request.args.get("error", ""),
    )


@matching_bp.post("/students/<int:student_id>/intelligence-report/targets")
@role_required("admin", "teacher")
def save_target(student_id):
    _get_student_or_404(student_id)
    try:
        job_id = int(request.form.get("job_id", ""))
        priority = int(request.form.get("priority", "1"))
    except ValueError:
        abort(400)
    if priority not in (1, 2, 3) or job_id not in {row["id"] for row in repositories.list_published_jobs()}:
        abort(400)
    repositories.upsert_student_job_target(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(
        g.current_user["id"], "set_student_job_target", "student", student_id,
        f"job={job_id},priority={priority}", request.remote_addr or "",
    )
    return redirect(url_for("matching.report", student_id=student_id, message="目标岗位已更新"))


@matching_bp.post("/students/<int:student_id>/intelligence-report/skills")
@role_required("admin", "teacher")
def save_skill_assessment(student_id):
    _get_student_or_404(student_id)
    try:
        skill_id = int(request.form.get("skill_id", ""))
        current_level = int(request.form.get("current_level", ""))
    except ValueError:
        abort(400)
    if current_level not in range(5) or skill_id not in {row["id"] for row in repositories.list_published_skills()}:
        abort(400)
    repositories.upsert_student_skill_assessment(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(
        g.current_user["id"], "assess_student_skill", "student", student_id,
        f"skill={skill_id},level={current_level}", request.remote_addr or "",
    )
    return redirect(url_for("matching.report", student_id=student_id, message="技能评估已更新"))


@matching_bp.post("/students/<int:student_id>/intelligence-report/exams")
@role_required("admin", "teacher")
def save_exam_plan(student_id):
    _get_student_or_404(student_id)
    try:
        exam_id = int(request.form.get("exam_id", ""))
        priority = int(request.form.get("priority", "1"))
    except ValueError:
        abort(400)
    if priority not in (1, 2, 3) or exam_id not in {row["id"] for row in repositories.list_published_exams()}:
        abort(400)
    repositories.upsert_student_exam_plan(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(
        g.current_user["id"], "set_student_exam_plan", "student", student_id,
        f"exam={exam_id},priority={priority}", request.remote_addr or "",
    )
    return redirect(url_for("matching.report", student_id=student_id, message="学生考试计划已更新"))
