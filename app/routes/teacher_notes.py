from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

teacher_notes_bp = Blueprint(
    "teacher_notes", __name__, url_prefix="/students/<int:student_id>/teacher-notes"
)


@teacher_notes_bp.route("", methods=("GET", "POST"))
def edit(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)

    if request.method == "POST":
        repositories.save_teacher_notes(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))

    return render_template(
        "teacher_notes/edit.html",
        student=student,
        notes=repositories.get_teacher_notes(student_id),
    )
