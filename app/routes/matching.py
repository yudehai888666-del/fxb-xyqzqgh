from flask import Blueprint, abort, g, redirect, request, url_for

from app import repositories
from app.auth import role_required


matching_bp = Blueprint("matching", __name__)


def _get_student_or_404(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@matching_bp.get("/students/<int:student_id>/intelligence-report")
def report(student_id):
    _get_student_or_404(student_id)
    return redirect(url_for("goals.stage_two", student_id=student_id))


@matching_bp.post("/students/<int:student_id>/intelligence-report/targets")
@role_required("admin", "teacher")
def save_target(student_id):
    _get_student_or_404(student_id)
    return redirect(url_for("employment.save_target", student_id=student_id), code=307)


@matching_bp.post("/students/<int:student_id>/intelligence-report/skills")
@role_required("admin", "teacher")
def save_skill_assessment(student_id):
    _get_student_or_404(student_id)
    return redirect(url_for("employment.save_skill", student_id=student_id), code=307)


@matching_bp.post("/students/<int:student_id>/intelligence-report/exams")
@role_required("admin", "teacher")
def save_exam_plan(student_id):
    _get_student_or_404(student_id)
    return redirect(url_for("employment.save_exam", student_id=student_id), code=307)
