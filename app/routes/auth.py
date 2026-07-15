from urllib.parse import urlparse

from flask import Blueprint, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import repositories
from app.auth import role_required


auth_bp = Blueprint("auth", __name__)
ROLE_LABELS = {"admin": "管理员", "teacher": "负责老师", "collaborator": "协作老师"}


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    if g.current_user is not None:
        return redirect(url_for("dashboard.dashboard"))
    error = ""
    if request.method == "POST":
        user = repositories.get_user_by_username(request.form.get("username", ""))
        if user is None or not user["is_active"] or not check_password_hash(
            user["password_hash"], request.form.get("password", "")
        ):
            error = "用户名或密码错误"
        else:
            session.clear()
            session["user_id"] = user["id"]
            repositories.update_user_last_login(user["id"])
            repositories.create_audit_log(user["id"], "login", "user", user["id"], ip_address=request.remote_addr or "")
            next_url = request.args.get("next", "")
            if next_url and not urlparse(next_url).netloc and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard.dashboard"))
    return render_template("auth/login.html", error=error)


@auth_bp.post("/logout")
def logout():
    if g.current_user is not None:
        repositories.create_audit_log(g.current_user["id"], "logout", "user", g.current_user["id"], ip_address=request.remote_addr or "")
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/admin/users", methods=("GET", "POST"))
@role_required("admin")
def users():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        if not username or not display_name or len(password) < 8 or role not in ROLE_LABELS:
            error = "请完整填写账号信息，密码至少8位"
        elif repositories.get_user_by_username(username):
            error = "用户名已存在"
        else:
            user_id = repositories.create_user({"username": username, "display_name": display_name, "password_hash": generate_password_hash(password, method="pbkdf2:sha256:600000"), "role": role})
            repositories.create_audit_log(g.current_user["id"], "create_user", "user", user_id, f"role={role}", request.remote_addr or "")
            return redirect(url_for("auth.users"))
    return render_template("auth/users.html", users=repositories.list_users(), role_labels=ROLE_LABELS, error=error)


@auth_bp.post("/admin/users/<int:user_id>/active")
@role_required("admin")
def update_user_active(user_id):
    user = repositories.get_user(user_id)
    if user is not None and user["id"] != g.current_user["id"]:
        repositories.set_user_active(user_id, request.form.get("is_active") == "1")
    return redirect(url_for("auth.users"))


@auth_bp.route("/students/<int:student_id>/access", methods=("GET", "POST"))
@role_required("admin")
def student_access(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        return redirect(url_for("students.list_view"))
    if request.method == "POST":
        user_id = int(request.form.get("user_id", "0"))
        access_level = request.form.get("access_level", "编辑")
        if repositories.get_user(user_id) and access_level in ("查看", "编辑"):
            repositories.assign_student_access(student_id, user_id, access_level)
            repositories.create_audit_log(g.current_user["id"], "assign_student", "student", student_id, f"user={user_id},level={access_level}", request.remote_addr or "")
        return redirect(url_for("auth.student_access", student_id=student_id))
    return render_template("auth/student_access.html", student=student, users=repositories.list_users(), assignments=repositories.list_student_access(student_id))


@auth_bp.post("/students/<int:student_id>/access/<int:user_id>/revoke")
@role_required("admin")
def revoke_student_access(student_id, user_id):
    repositories.revoke_student_access(student_id, user_id)
    return redirect(url_for("auth.student_access", student_id=student_id))
