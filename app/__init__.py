from pathlib import Path

from flask import Flask, request

from app.config import Config
from app.auth import register_auth
from app.db import close_db, init_db
from app.routes import register_blueprints
from app.services.backups import register_backup_commands
from app import repositories
from app.services.student_workflow import build_student_workflow


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    app.config["DATABASE"].parent.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    Path(app.config["GENERATED_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BACKUP_DIR"]).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    register_blueprints(app)
    register_auth(app)
    register_backup_commands(app)

    @app.context_processor
    def inject_student_workspace():
        student_id = (request.view_args or {}).get("student_id")
        if student_id is None:
            return {}
        student = repositories.get_student(student_id)
        if student is None:
            return {}
        return {
            "workspace_student": student,
            "student_workflow": build_student_workflow(student_id),
        }
    return app
