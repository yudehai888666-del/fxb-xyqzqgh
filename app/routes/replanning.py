from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories
from app.services.replanning_generator import generate_replanning_agreement

replanning_bp = Blueprint(
    "replanning", __name__, url_prefix="/students/<int:student_id>/replanning"
)


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@replanning_bp.get("")
def list_view(student_id):
    student = require_student(student_id)
    cases = repositories.list_replanning_cases(student_id)
    return render_template("replanning/list.html", student=student, cases=cases)


@replanning_bp.route("/new", methods=("GET", "POST"))
def new(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        data = request.form.to_dict()
        data["agreement_terms"] = generate_replanning_agreement(student, data)
        case_id = repositories.create_replanning_case(student_id, data)
        return redirect(
            url_for("replanning.detail", student_id=student_id, case_id=case_id)
        )

    return render_template("replanning/new.html", student=student, form={})


@replanning_bp.get("/<int:case_id>")
def detail(student_id, case_id):
    student = require_student(student_id)
    case = repositories.get_replanning_case(case_id)
    if case is None or case["student_id"] != student_id:
        abort(404)
    return render_template("replanning/detail.html", student=student, case=case)


VALID_STATUSES = ("草稿", "已确认", "执行中", "已完成", "已取消")


@replanning_bp.post("/<int:case_id>/status")
def update_status(student_id, case_id):
    require_student(student_id)
    case = repositories.get_replanning_case(case_id)
    if case is None or case["student_id"] != student_id:
        abort(404)
    new_status = request.form.get("status", "").strip()
    if new_status not in VALID_STATUSES:
        abort(400)
    repositories.update_replanning_status(case_id, new_status)
    return redirect(url_for("replanning.detail", student_id=student_id, case_id=case_id))
