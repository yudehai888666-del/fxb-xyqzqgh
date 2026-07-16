import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    schema_path = Path(__file__).with_name("schema.sql")
    db = get_db()
    db.executescript(schema_path.read_text(encoding="utf-8"))
    _run_lightweight_migrations(db)
    db.commit()


def _add_column_if_missing(db, table, column, definition):
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _run_lightweight_migrations(db):
    teacher_note_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(teacher_notes)").fetchall()
    }
    if "combined_notes" not in teacher_note_columns:
        db.execute(
            "ALTER TABLE teacher_notes ADD COLUMN combined_notes TEXT NOT NULL DEFAULT ''"
        )

    planning_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(planning_documents)")
    }
    if "version" not in planning_columns:
        db.execute(
            "ALTER TABLE planning_documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1"
        )
    if "visibility" not in planning_columns:
        db.execute(
            "ALTER TABLE planning_documents ADD COLUMN visibility TEXT NOT NULL DEFAULT '老师内部'"
        )

    material_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(materials)")
    }
    if "visibility" not in material_columns:
        db.execute(
            "ALTER TABLE materials ADD COLUMN visibility TEXT NOT NULL DEFAULT '老师内部'"
        )

    job_skill_columns = {
        "source_id": "INTEGER",
        "confidence_level": "TEXT NOT NULL DEFAULT ''",
        "sample_size": "INTEGER NOT NULL DEFAULT 0",
        "last_verified_at": "TEXT NOT NULL DEFAULT ''",
        "next_check_at": "TEXT NOT NULL DEFAULT ''",
        "owner_user_id": "INTEGER",
        "reviewer_user_id": "INTEGER",
        "status": "TEXT NOT NULL DEFAULT '草稿'",
        "limitation_note": "TEXT NOT NULL DEFAULT ''",
    }
    for column, definition in job_skill_columns.items():
        _add_column_if_missing(db, "job_skill_links", column, definition)

    _add_column_if_missing(
        db, "exam_information", "limitation_note", "TEXT NOT NULL DEFAULT ''"
    )
    _add_column_if_missing(
        db, "industry_trends", "limitation_note", "TEXT NOT NULL DEFAULT ''"
    )

    db.execute(
        """
        INSERT OR IGNORE INTO student_files (
            student_id, source_type, source_id, category, original_filename,
            storage_area, storage_key, version, visibility
        )
        SELECT student_id, 'material', id, category, original_filename,
               'uploads', stored_filename, 1, visibility
        FROM materials
        """
    )
    db.execute(
        """
        INSERT OR IGNORE INTO student_files (
            student_id, source_type, source_id, category, original_filename,
            storage_area, storage_key, version, visibility
        )
        SELECT student_id, 'planning_document', id, '规划文档', title || '.md',
               'generated', file_path, version, visibility
        FROM planning_documents
        WHERE file_path != ''
        """
    )
