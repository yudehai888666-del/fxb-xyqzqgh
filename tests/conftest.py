import pytest

from app import create_app
from app.db import init_db


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
        }
    )
    with app.app_context():
        init_db()
    return app


@pytest.fixture
def client(app):
    return app.test_client()
