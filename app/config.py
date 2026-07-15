from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = PROJECT_ROOT / "instance"
UPLOAD_DIR = PROJECT_ROOT / "uploads"
GENERATED_DIR = PROJECT_ROOT / "generated"
BACKUP_DIR = PROJECT_ROOT / "backups"


class Config:
    SECRET_KEY = os.environ.get("ACADEMIC_PLANNING_SECRET_KEY")
    DATABASE = INSTANCE_DIR / "academic_planning.sqlite3"
    UPLOAD_DIR = UPLOAD_DIR
    GENERATED_DIR = GENERATED_DIR
    BACKUP_DIR = BACKUP_DIR
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    PUBLIC_BASE_URL = os.environ.get("ACADEMIC_PLANNING_PUBLIC_BASE_URL", "")
    AUTH_DISABLED = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    ALLOW_SYNTHETIC_EGRESS = os.environ.get("CODEX_CI") == "1"
