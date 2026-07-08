from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories
from app.services.uploads import save_upload

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

    questionnaire = repositories.get_parent_questionnaire(student_id)
    parent_contact = None
    if questionnaire is None:
        parent_contact = repositories.get_primary_parent_contact(student_id)

    return render_template(
        "questionnaires/parent.html",
        student=student,
        questionnaire=questionnaire,
        parent_contact=parent_contact,
    )


@questionnaires_bp.route("/materials", methods=("GET", "POST"))
def materials(student_id):
    student = require_student(student_id)
    error = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            material = request.files.get("material")
            if material and material.filename:
                try:
                    stored_filename = save_upload(student_id, material)
                except ValueError as exc:
                    error = str(exc)
                else:
                    repositories.create_material(
                        student_id,
                        {
                            "uploader_type": request.form.get("uploader_type", ""),
                            "category": request.form.get("category", "其他材料"),
                            "original_filename": material.filename,
                            "stored_filename": stored_filename,
                        },
                    )
        elif action == "disclaimer":
            repositories.confirm_disclaimer(
                student_id,
                {
                    "signer_type": request.form.get("signer_type", ""),
                    "signer_name": request.form.get("signer_name", ""),
                    "reason": request.form.get("reason", ""),
                },
            )
            return redirect(url_for("questionnaires.materials", student_id=student_id))

    return render_template(
        "questionnaires/materials.html",
        student=student,
        materials=repositories.list_materials(student_id),
        disclaimers=repositories.list_disclaimers(student_id),
        error=error,
    )
