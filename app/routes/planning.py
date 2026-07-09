from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories
from app.services.completion import get_student_completion
from app.services.planning_files import save_planning_markdown
from app.services.planning_generator import build_planning_context, generate_initial_plan

planning_bp = Blueprint("planning", __name__, url_prefix="/students/<int:student_id>/planning")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@planning_bp.route("/generate", methods=("GET", "POST"))
def generate(student_id):
    student = require_student(student_id)
    completion = get_student_completion(student_id)

    if request.method == "POST":
        if not completion["ready_for_ai"]:
            return (
                render_template(
                    "planning/generate.html",
                    student=student,
                    completion=completion,
                    error="信息仍需补充，暂不能生成初步规划。",
                ),
                400,
            )

        draft = generate_initial_plan(build_planning_context(student_id))
        document_id = repositories.create_planning_document(student_id, draft)
        relative_path = save_planning_markdown(
            student_id,
            document_id,
            draft["title"],
            draft["content_markdown"],
        )
        repositories.update_planning_document_file_path(document_id, relative_path)
        return redirect(
            url_for(
                "planning.detail",
                student_id=student_id,
                document_id=document_id,
            )
        )

    return render_template(
        "planning/generate.html",
        student=student,
        completion=completion,
        error="",
    )


@planning_bp.get("/documents/<int:document_id>")
def detail(student_id, document_id):
    student = require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id:
        abort(404)
    return render_template("planning/detail.html", student=student, document=document)
