from flask import Blueprint

questionnaires_bp = Blueprint(
    "questionnaires", __name__, url_prefix="/students/<int:student_id>"
)
