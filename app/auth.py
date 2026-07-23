import secrets
from functools import wraps
from pathlib import Path

import click
from flask import abort, g, redirect, request, session, url_for
from werkzeug.security import generate_password_hash

from app import repositories


PUBLIC_ENDPOINTS = {"auth.login", "invitations.fill", "invitations.qr_code", "static"}


def ensure_secret_key(app):
    if app.config.get("SECRET_KEY"):
        return
    secret_path = Path(app.config["DATABASE"]).parent / ".secret-key"
    if secret_path.exists():
        secret = secret_path.read_text(encoding="utf-8").strip()
    else:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32)
        secret_path.write_text(secret, encoding="utf-8")
        secret_path.chmod(0o600)
    app.config["SECRET_KEY"] = secret


def register_auth(app):
    ensure_secret_key(app)

    @app.before_request
    def load_and_protect_user():
        g.current_user = None
        if app.config.get("LOCAL_ADMIN_MODE") and request.endpoint != "static":
            g.current_user = repositories.get_first_active_admin()
            if g.current_user is None:
                abort(503, "本地免登录模式需要至少一个启用的管理员账号")
        else:
            user_id = session.get("user_id")
            if user_id is not None:
                user = repositories.get_user(user_id)
                if user is not None and user["is_active"]:
                    g.current_user = user
                else:
                    session.clear()
        if app.config.get("AUTH_DISABLED") or request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if g.current_user is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        student_id = (request.view_args or {}).get("student_id")
        if student_id is not None and not repositories.user_can_access_student(
            g.current_user, student_id, require_edit=request.method != "GET"
        ):
            abort(403)
        return None

    @app.context_processor
    def inject_current_user():
        return {"current_user": g.get("current_user")}

    @app.cli.command("create-admin")
    @click.option("--username", default="admin", show_default=True)
    @click.option("--display-name", default="系统管理员", show_default=True)
    @click.option("--password", default="", help="留空时生成随机密码")
    def create_admin_command(username, display_name, password):
        if repositories.get_user_by_username(username):
            raise click.ClickException("用户名已存在")
        generated_password = password or secrets.token_urlsafe(12)
        repositories.create_user(
            {"username": username, "display_name": display_name,
             "password_hash": generate_password_hash(generated_password, method="pbkdf2:sha256:600000"), "role": "admin"}
        )
        click.echo(f"管理员已创建：{username}")
        if not password:
            click.echo(f"一次性初始密码：{generated_password}")


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.current_user is None or g.current_user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
