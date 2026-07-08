from flask import Flask

from app.config import Config
from app.db import close_db
from app.routes import register_blueprints


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    app.config["DATABASE"].parent.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)

    register_blueprints(app)
    app.teardown_appcontext(close_db)

    return app
