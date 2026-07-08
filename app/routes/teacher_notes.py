from flask import Blueprint

teacher_notes_bp = Blueprint(
    "teacher_notes", __name__, url_prefix="/students/<int:student_id>/teacher-notes"
)
