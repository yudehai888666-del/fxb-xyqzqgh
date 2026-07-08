import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
        }
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()
