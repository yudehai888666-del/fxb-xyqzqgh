from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".txt",
}


def save_upload(student_id, file_storage):
    safe_original = secure_filename(file_storage.filename)
    suffix = f".{safe_original.rsplit('.', 1)[-1].lower()}" if "." in safe_original else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("不支持的文件类型")

    stored_name = f"student-{student_id}-{uuid4().hex}-{safe_original}"
    file_storage.save(current_app.config["UPLOAD_DIR"] / stored_name)
    return stored_name
