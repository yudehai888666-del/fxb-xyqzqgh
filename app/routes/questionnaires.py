from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

questionnaires_bp = Blueprint("questionnaires", __name__, url_prefix="/students/<int:student_id>")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@questionnaires_bp.route("/student-questionnaire", methods=("GET", "POST"))
def student_questionnaire(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        repositories.save_student_questionnaire(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))

    return render_template(
        "questionnaires/student.html",
        student=student,
        questionnaire=repositories.get_student_questionnaire(student_id),
    )


@questionnaires_bp.route("/parent-questionnaire", methods=("GET", "POST"))
def parent_questionnaire(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        repositories.save_parent_questionnaire(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))

    return render_template(
        "questionnaires/parent.html",
        student=student,
        questionnaire=repositories.get_parent_questionnaire(student_id),
    )
