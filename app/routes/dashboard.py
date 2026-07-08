from flask import Blueprint, render_template

from app import repositories

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def dashboard():
    students = repositories.list_students()
    return render_template(
        "dashboard.html",
        students=students[:5],
        total_students=len(students),
    )
