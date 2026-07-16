import hashlib
import mimetypes
from pathlib import Path
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
    original_filename = file_storage.filename or ""
    suffix = (
        f".{original_filename.rsplit('.', 1)[-1].lower()}"
        if "." in original_filename
        else ""
    )
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("不支持的文件类型")

    safe_original = secure_filename(original_filename)
    if not safe_original.endswith(suffix):
        safe_stem = secure_filename(original_filename.rsplit(".", 1)[0]) or "material"
        safe_original = f"{safe_stem}{suffix}"

    stored_name = f"student-{student_id}-{uuid4().hex}-{safe_original}"
    file_storage.save(current_app.config["UPLOAD_DIR"] / stored_name)
    return stored_name


def inspect_stored_file(path, original_filename=""):
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "size_bytes": file_path.stat().st_size,
        "sha256": digest.hexdigest(),
        "mime_type": mimetypes.guess_type(original_filename or file_path.name)[0]
        or "application/octet-stream",
    }
