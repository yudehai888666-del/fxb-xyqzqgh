import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "GENERATED_DIR": tmp_path / "generated",
            "UPLOAD_DIR": tmp_path / "uploads",
            "BACKUP_DIR": tmp_path / "backups",
            "PUBLIC_BASE_URL": "https://questionnaire.example.test",
            "AUTH_DISABLED": True,
            "SECRET_KEY": "test-secret-key",
        }
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()
