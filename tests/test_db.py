from app import create_app
from app.db import get_db


def test_homepage_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Academic Planning" in response.data


def test_schema_creates_students_table(app):
    with app.app_context():
        row = get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'students'"
        ).fetchone()

    assert row["name"] == "students"


def test_create_app_initializes_schema_without_manual_init(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "fresh.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
        }
    )

    with app.app_context():
        row = get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'students'"
        ).fetchone()

    assert row["name"] == "students"
