from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = PROJECT_ROOT / "instance"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
GENERATED_DIR = PROJECT_ROOT / "generated"


class Config:
    SECRET_KEY = "local-dev-academic-planning"
    DATABASE = INSTANCE_DIR / "academic_planning.sqlite3"
    UPLOAD_DIR = UPLOAD_DIR
    GENERATED_DIR = GENERATED_DIR
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
