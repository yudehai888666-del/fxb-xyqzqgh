from flask import Blueprint, abort, g, render_template, request

from app import repositories
from app.services.student_matching import build_student_intelligence_report


employment_bp = Blueprint(
    "employment", __name__, url_prefix="/students/<int:student_id>/employment"
)


@employment_bp.get("")
def workspace(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return render_template(
        "matching/report.html",
        report=build_student_intelligence_report(student),
        available_jobs=repositories.list_published_jobs(),
        available_skills=repositories.list_published_skills(),
        available_exams=repositories.list_published_exams(),
        exam_plans=repositories.list_student_exam_plans(student_id),
        users=(
            repositories.list_users()
            if g.current_user
            and g.current_user["role"] in ("admin", "teacher")
            else []
        ),
        message=request.args.get("message", ""),
        error=request.args.get("error", ""),
    )
