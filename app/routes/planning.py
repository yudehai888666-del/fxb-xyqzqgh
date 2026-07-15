from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)

from app import repositories
from app.services.completion import get_student_completion
from app.services.planning_files import save_planning_markdown
from app.services.uploads import inspect_stored_file
from app.services.planning_exports import export_planning_docx, export_planning_pdf
from app.services.planning_generator import build_planning_context, generate_initial_plan

planning_bp = Blueprint("planning", __name__, url_prefix="/students/<int:student_id>/planning")
VALID_VISIBILITIES = ("老师内部", "学生可见", "家长可见", "学生与家长可见")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@planning_bp.route("/generate", methods=("GET", "POST"))
def generate(student_id):
    student = require_student(student_id)
    completion = get_student_completion(student_id)
    documents = repositories.list_planning_documents(student_id)

    if request.method == "POST":
        if not completion["ready_for_ai"]:
            return (
                render_template(
                    "planning/generate.html",
                    student=student,
                    completion=completion,
                    documents=documents,
                    error="信息仍需补充，暂不能生成初步规划。",
                ),
                400,
            )

        document_id = None
        relative_path = None
        try:
            draft = generate_initial_plan(build_planning_context(student_id))
            document_id = repositories.create_planning_document(student_id, draft)
            relative_path = save_planning_markdown(
                student_id,
                document_id,
                draft["title"],
                draft["content_markdown"],
            )
            repositories.update_planning_document_file_path(document_id, relative_path)
            document = repositories.get_planning_document(document_id)
            metadata = inspect_stored_file(
                Path(current_app.config["GENERATED_DIR"]) / relative_path,
                f"{draft['title']}.md",
            )
            repositories.archive_student_file(
                student_id,
                {
                    "source_type": "planning_document",
                    "source_id": document_id,
                    "category": "规划文档",
                    "original_filename": f"{draft['title']}.md",
                    "storage_area": "generated",
                    "storage_key": relative_path,
                    "version": document["version"],
                    "visibility": document["visibility"],
                    **metadata,
                },
            )
        except Exception:
            if relative_path:
                try:
                    (Path(current_app.config["GENERATED_DIR"]) / relative_path).unlink(
                        missing_ok=True
                    )
                except Exception:
                    pass
            if document_id:
                try:
                    repositories.delete_planning_document(document_id)
                except Exception:
                    pass
            return (
                render_template(
                    "planning/generate.html",
                    student=student,
                    completion=completion,
                    documents=documents,
                    error="生成初步规划失败，请稍后重试。",
                ),
                500,
            )
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
        documents=documents,
        error="",
    )


@planning_bp.get("/documents/<int:document_id>")
def detail(student_id, document_id):
    student = require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id:
        abort(404)
    return render_template("planning/detail.html", student=student, document=document)


@planning_bp.post("/documents/<int:document_id>/visibility")
def update_visibility(student_id, document_id):
    require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id:
        abort(404)
    visibility = request.form.get("visibility", "").strip()
    if visibility not in VALID_VISIBILITIES:
        abort(400)
    repositories.update_planning_document_visibility(document_id, visibility)
    return redirect(
        url_for("planning.detail", student_id=student_id, document_id=document_id)
    )


@planning_bp.route("/documents/<int:document_id>/edit", methods=("GET", "POST"))
def edit(student_id, document_id):
    student = require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id:
        abort(404)
    if request.method == "POST":
        content = request.form.get("content_markdown", "").strip()
        if not content:
            return render_template("planning/edit.html", student=student, document=document, error="规划内容不能为空"), 400
        new_id = repositories.create_planning_document(student_id, {"title": request.form.get("title", document["title"]).strip() or document["title"], "content_markdown": content, "visibility": document["visibility"]})
        path = save_planning_markdown(student_id, new_id, document["title"], content)
        repositories.update_planning_document_file_path(new_id, path)
        new_doc = repositories.get_planning_document(new_id)
        metadata = inspect_stored_file(Path(current_app.config["GENERATED_DIR"]) / path, f"{new_doc['title']}.md")
        repositories.archive_student_file(student_id, {"source_type": "planning_document", "source_id": new_id, "category": "规划文档", "original_filename": f"{new_doc['title']}.md", "storage_area": "generated", "storage_key": path, "version": new_doc["version"], "visibility": new_doc["visibility"], **metadata})
        return redirect(url_for("planning.detail", student_id=student_id, document_id=new_id))
    return render_template("planning/edit.html", student=student, document=document, error="")


@planning_bp.post("/documents/<int:document_id>/confirm")
def confirm(student_id, document_id):
    require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id:
        abort(404)
    repositories.confirm_planning_document(document_id)
    return redirect(url_for("planning.detail", student_id=student_id, document_id=document_id))


@planning_bp.post("/documents/<int:document_id>/export/<file_format>")
def export(student_id, document_id, file_format):
    student = require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id or file_format not in ("docx", "pdf"):
        abort(404)
    destination = export_planning_docx(student, document) if file_format == "docx" else export_planning_pdf(student, document)
    relative = destination.relative_to(Path(current_app.config["GENERATED_DIR"])).as_posix()
    metadata = inspect_stored_file(destination, destination.name)
    repositories.archive_student_file(student_id, {"source_type": f"planning_export_{file_format}", "source_id": document_id, "category": f"规划文档{file_format.upper()}", "original_filename": destination.name, "storage_area": "generated", "storage_key": relative, "version": document["version"], "visibility": document["visibility"], **metadata})
    return redirect(url_for("files.center", student_id=student_id))
