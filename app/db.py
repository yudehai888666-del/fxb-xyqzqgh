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


def _run_lightweight_migrations(db):
    teacher_note_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(teacher_notes)").fetchall()
    }
    if "combined_notes" not in teacher_note_columns:
        db.execute(
            "ALTER TABLE teacher_notes ADD COLUMN combined_notes TEXT NOT NULL DEFAULT ''"
        )
