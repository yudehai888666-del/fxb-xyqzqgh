from app.routes.dashboard import dashboard_bp
from app.routes.planning import planning_bp
from app.routes.questionnaires import questionnaires_bp
from app.routes.replanning import replanning_bp
from app.routes.invitations import invitations_bp
from app.routes.students import students_bp
from app.routes.teacher_notes import teacher_notes_bp
from app.routes.auth import auth_bp
from app.routes.files import files_bp
from app.routes.intelligence import intelligence_bp
from app.routes.matching import matching_bp
from app.routes.goals import goals_bp
from app.routes.employment import employment_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(teacher_notes_bp)
    app.register_blueprint(planning_bp)
    app.register_blueprint(replanning_bp)
    app.register_blueprint(invitations_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(intelligence_bp)
    app.register_blueprint(matching_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(employment_bp)
