import hashlib
from pathlib import Path

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, send_file, url_for

from app import repositories


files_bp = Blueprint("files", __name__, url_prefix="/students/<int:student_id>/files")
VALID_VISIBILITIES = ("老师内部", "学生可见", "家长可见", "学生与家长可见")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


def resolve_storage_path(record):
    roots = {
        "uploads": Path(current_app.config["UPLOAD_DIR"]),
        "generated": Path(current_app.config["GENERATED_DIR"]),
    }
    root = roots.get(record["storage_area"])
    if root is None:
        abort(404)
    root = root.resolve()
    path = (root / record["storage_key"]).resolve()
    if root != path and root not in path.parents:
        abort(404)
    return path


def integrity_status(record):
    path = resolve_storage_path(record)
    if not path.is_file():
        return "文件缺失"
    if not record["sha256"]:
        return "待校验"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return "校验通过" if digest == record["sha256"] else "校验失败"


@files_bp.get("")
def center(student_id):
    student = require_student(student_id)
    records = repositories.list_student_files(student_id)
    return render_template(
        "files/center.html",
        student=student,
        files=[{"record": row, "integrity": integrity_status(row)} for row in records],
        visibilities=VALID_VISIBILITIES,
    )


@files_bp.get("/<int:file_id>/download")
def download(student_id, file_id):
    require_student(student_id)
    record = repositories.get_student_file(file_id)
    if record is None or record["student_id"] != student_id or record["deleted_at"]:
        abort(404)
    path = resolve_storage_path(record)
    if not path.is_file():
        abort(404)
    if record["sha256"] and integrity_status(record) != "校验通过":
        abort(409)
    repositories.create_audit_log(g.current_user["id"] if g.current_user else None, "download_file", "student_file", file_id, record["original_filename"], request.remote_addr or "")
    return send_file(path, as_attachment=True, download_name=record["original_filename"])


@files_bp.post("/<int:file_id>/visibility")
def visibility(student_id, file_id):
    require_student(student_id)
    record = repositories.get_student_file(file_id)
    if record is None or record["student_id"] != student_id:
        abort(404)
    value = request.form.get("visibility", "")
    if value not in VALID_VISIBILITIES:
        abort(400)
    repositories.update_student_file_visibility(file_id, value)
    return redirect(url_for("files.center", student_id=student_id))


@files_bp.post("/<int:file_id>/delete")
def delete(student_id, file_id):
    require_student(student_id)
    record = repositories.get_student_file(file_id)
    if record is None or record["student_id"] != student_id:
        abort(404)
    repositories.soft_delete_student_file(file_id)
    repositories.create_audit_log(g.current_user["id"] if g.current_user else None, "soft_delete_file", "student_file", file_id, record["original_filename"], request.remote_addr or "")
    return redirect(url_for("files.center", student_id=student_id))
