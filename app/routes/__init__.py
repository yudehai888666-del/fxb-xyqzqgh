from app.routes.dashboard import dashboard_bp
from app.routes.planning import planning_bp
from app.routes.questionnaires import questionnaires_bp
from app.routes.replanning import replanning_bp
from app.routes.students import students_bp
from app.routes.teacher_notes import teacher_notes_bp


def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(teacher_notes_bp)
    app.register_blueprint(planning_bp)
    app.register_blueprint(replanning_bp)
