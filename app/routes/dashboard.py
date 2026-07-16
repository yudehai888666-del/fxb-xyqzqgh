from flask import Blueprint, g, render_template

from app import repositories
from app.services.student_workflow import build_student_workflow

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def dashboard():
    students = repositories.list_students(g.get("current_user"))
    recent_students = students[:5]
    return render_template(
        "dashboard.html",
        students=recent_students,
        total_students=len(students),
        workflows={student.id: build_student_workflow(student.id) for student in recent_students},
    )
