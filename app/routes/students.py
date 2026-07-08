from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.get("")
def list_view():
    return render_template("students/list.html", students=repositories.list_students())


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
    )
