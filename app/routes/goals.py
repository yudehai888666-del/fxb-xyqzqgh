from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from app import repositories
from app.auth import role_required
from app.services import student_goals


goals_bp = Blueprint("goals", __name__, url_prefix="/students/<int:student_id>")


def _student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@goals_bp.get("/stage-two")
def stage_two(student_id):
    _student(student_id)
    endpoint, values = student_goals.stage_two_endpoint(student_id)
    return redirect(url_for(endpoint, **values))


@goals_bp.route("/goals/confirm", methods=("GET", "POST"))
@role_required("admin", "teacher")
def confirm(student_id):
    student = _student(student_id)
    if student_goals.get_goal_profile(student_id) is not None:
        return redirect(url_for("goals.stage_two", student_id=student_id))
    if request.method == "POST":
        try:
            student_goals.confirm_existing_goal(
                student_id, request.form, g.current_user["id"]
            )
        except student_goals.GoalValidationError as exc:
            return (
                render_template(
                    "goals/confirm.html",
                    student=student,
                    form=request.form,
                    error=str(exc),
                ),
                400,
            )
        repositories.create_audit_log(
            g.current_user["id"], "confirm_student_goal", "student", student_id
        )
        return redirect(url_for("goals.stage_two", student_id=student_id))
    return render_template(
        "goals/confirm.html", student=student, form={}, error=""
    )


@goals_bp.post("/goals/change")
@role_required("admin", "teacher")
def change(student_id):
    _student(student_id)
    try:
        replanning_id = int(request.form.get("replanning_id", ""))
        student_goals.change_goal(
            student_id,
            request.form,
            replanning_id,
            g.current_user["id"],
        )
    except (ValueError, student_goals.GoalValidationError) as exc:
        return redirect(
            url_for("replanning.list_view", student_id=student_id, error=str(exc))
        )
    repositories.create_audit_log(
        g.current_user["id"],
        "change_student_goal",
        "student",
        student_id,
        f"replanning={replanning_id}",
    )
    return redirect(url_for("goals.stage_two", student_id=student_id))


@goals_bp.get("/advancement")
def advancement(student_id):
    student = _student(student_id)
    profile = student_goals.get_goal_profile(student_id)
    if profile is None or profile["primary_goal"] != "升学":
        return redirect(url_for("goals.stage_two", student_id=student_id))
    return render_template(
        "advancement/overview.html",
        student=student,
        goal_profile=profile,
        student_questionnaire=repositories.get_student_questionnaire(student_id),
        parent_questionnaire=repositories.get_parent_questionnaire(student_id),
        teacher_notes=repositories.get_teacher_notes(student_id),
        exam_plans=repositories.list_student_exam_plans(student_id),
    )
