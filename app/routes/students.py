from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from app import repositories
from app.services.completion import get_student_completion
from app.services.student_workflow import build_student_workflow

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.get("")
def list_view():
    students = repositories.list_students(g.get("current_user"))
    return render_template(
        "students/list.html", students=students,
        workflows={student.id: build_student_workflow(student.id) for student in students},
    )


@students_bp.route("/new", methods=("GET", "POST"))
def new():
    if request.method == "POST":
        form = request.form
        try:
            int(form.get("enrollment_year", ""))
        except ValueError:
            return (
                render_template(
                    "students/new.html",
                    error="入学年份必须是有效年份",
                    form=form,
                ),
                400,
            )

        student_id = repositories.create_student(request.form)
        if g.get("current_user") is not None and g.current_user["role"] != "admin":
            repositories.assign_student_access(student_id, g.current_user["id"], "编辑")
        return redirect(url_for("students.detail", student_id=student_id))

    return render_template("students/new.html", form={})


@students_bp.get("/<int:student_id>")
def detail(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)

    return render_template(
        "students/detail.html",
        student=student,
        parents=repositories.list_parent_contacts(student_id),
        completion=get_student_completion(student_id),
        planning_documents=repositories.list_planning_documents(student_id),
        replanning_cases=repositories.list_replanning_cases(student_id),
        job_targets=repositories.list_student_job_targets(student_id),
        skill_assessments=repositories.list_student_skill_assessments(student_id),
        exam_plans=repositories.list_student_exam_plans(student_id),
    )
