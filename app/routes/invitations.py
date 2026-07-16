from datetime import datetime
from io import BytesIO
import json
import socket
import subprocess

import qrcode
import qrcode.image.svg
from flask import Blueprint, abort, current_app, make_response, redirect, render_template, request, url_for

from app import repositories


invitations_bp = Blueprint("invitations", __name__)

QUESTION_LABELS = {
    "student": (
        ("adaptation_status", "适应情况"),
        ("academic_status", "学业情况"),
        ("weak_subjects", "薄弱科目"),
        ("tutoring_needs", "辅导需求"),
        ("interests_strengths", "兴趣与优势"),
        ("future_intentions", "未来意向"),
        ("motivation_status", "动力状态"),
    ),
    "parent": (
        ("parent_name", "家长姓名"),
        ("relationship", "与学生关系"),
        ("parent_phone", "联系电话"),
        ("communication_method", "沟通方式"),
        ("family_resources", "家庭资源"),
        ("target_priorities", "目标优先级"),
        ("parent_observations", "家长对孩子的观察"),
        ("current_concerns", "当前担忧"),
        ("investment_willingness", "投入意愿"),
    ),
}


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


def invitation_state(invitation):
    if invitation is None:
        return "无效"
    if invitation["status"] != "有效":
        return invitation["status"]
    if datetime.fromisoformat(invitation["expires_at"]) <= datetime.now():
        return "已过期"
    return "有效"


def local_network_ip():
    for interface in ("en0", "en1"):
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", interface],
                capture_output=True,
                check=False,
                text=True,
                timeout=1,
            )
            address = result.stdout.strip()
            if address.startswith(("192.168.", "10.")) or address.startswith("172."):
                return address
        except (OSError, subprocess.SubprocessError):
            pass
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.connect(("8.8.8.8", 80))
        return connection.getsockname()[0]
    except OSError:
        return ""
    finally:
        connection.close()


def public_invitation_url(token):
    configured = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    if configured:
        return f"{configured}{url_for('invitations.fill', token=token)}"
    if request.host.split(":", 1)[0] in ("127.0.0.1", "localhost"):
        network_ip = local_network_ip()
        if network_ip:
            return f"http://{network_ip}:5050{url_for('invitations.fill', token=token)}"
    return url_for("invitations.fill", token=token, _external=True)


@invitations_bp.get("/students/<int:student_id>/invitations")
def manage(student_id):
    student = require_student(student_id)
    invitations = repositories.list_questionnaire_invitations(student_id)
    latest = {}
    for invitation in invitations:
        latest.setdefault(invitation["questionnaire_type"], invitation)
    invitation_urls = {
        kind: public_invitation_url(invitation["token"])
        for kind, invitation in latest.items()
        if invitation_state(invitation) == "有效"
    }
    return render_template(
        "invitations/manage.html",
        student=student,
        invitations=latest,
        invitation_state=invitation_state,
        invitation_urls=invitation_urls,
        network_ip=local_network_ip(),
    )


@invitations_bp.post("/students/<int:student_id>/invitations/<questionnaire_type>/create")
def create(student_id, questionnaire_type):
    require_student(student_id)
    if questionnaire_type not in ("student", "parent"):
        abort(404)
    repositories.create_questionnaire_invitation(student_id, questionnaire_type)
    return redirect(url_for("invitations.manage", student_id=student_id))


@invitations_bp.post("/students/<int:student_id>/invitations/<int:invitation_id>/revoke")
def revoke(student_id, invitation_id):
    require_student(student_id)
    invitation = repositories.get_questionnaire_invitation_by_id(invitation_id)
    if invitation is None or invitation["student_id"] != student_id:
        abort(404)
    repositories.revoke_questionnaire_invitation(invitation_id, student_id)
    return redirect(url_for("invitations.manage", student_id=student_id))


@invitations_bp.get("/students/<int:student_id>/questionnaire-results/<questionnaire_type>")
def results(student_id, questionnaire_type):
    student = require_student(student_id)
    if questionnaire_type not in QUESTION_LABELS:
        abort(404)
    submissions = repositories.list_questionnaire_submissions(
        student_id, questionnaire_type
    )
    parsed = [
        {"record": row, "answers": json.loads(row["answers_json"])}
        for row in submissions
    ]
    if not parsed:
        current = (
            repositories.get_student_questionnaire(student_id)
            if questionnaire_type == "student"
            else repositories.get_parent_questionnaire(student_id)
        )
        if current is not None:
            parsed.append(
                {
                    "record": {
                        "id": "历史",
                        "submitted_at": current["submitted_at"],
                    },
                    "answers": dict(current),
                    "legacy": True,
                }
            )
    return render_template(
        "invitations/results.html",
        student=student,
        questionnaire_type=questionnaire_type,
        questionnaire_title=("学生问卷" if questionnaire_type == "student" else "家长问卷"),
        labels=QUESTION_LABELS[questionnaire_type],
        submissions=parsed,
    )


@invitations_bp.get("/invite/<token>/qr.svg")
def qr_code(token):
    invitation = repositories.get_questionnaire_invitation(token)
    if invitation_state(invitation) != "有效":
        abort(404)
    invitation_url = public_invitation_url(token)
    image = qrcode.make(
        invitation_url,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=8,
        border=2,
    )
    output = BytesIO()
    image.save(output)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "image/svg+xml"
    response.headers["Cache-Control"] = "no-store"
    return response


@invitations_bp.route("/invite/<token>", methods=("GET", "POST"))
def fill(token):
    invitation = repositories.get_questionnaire_invitation(token)
    state = invitation_state(invitation)
    if state != "有效":
        return render_template("invitations/status.html", state=state), 410

    student = require_student(invitation["student_id"])
    if request.method == "POST":
        repositories.create_questionnaire_submission(
            student.id,
            invitation["id"],
            invitation["questionnaire_type"],
            request.form,
        )
        if invitation["questionnaire_type"] == "student":
            repositories.save_student_questionnaire(student.id, request.form)
        else:
            repositories.save_parent_questionnaire(student.id, request.form)
        repositories.mark_invitation_submitted(invitation["id"])
        return render_template(
            "invitations/status.html", state="提交成功", student=student
        )

    repositories.mark_invitation_opened(invitation["id"])
    if invitation["questionnaire_type"] == "student":
        return render_template(
            "questionnaires/student.html",
            student=student,
            questionnaire=repositories.get_student_questionnaire(student.id),
            public_invite=True,
        )
    questionnaire = repositories.get_parent_questionnaire(student.id)
    return render_template(
        "questionnaires/parent.html",
        student=student,
        questionnaire=questionnaire,
        parent_contact=(
            None
            if questionnaire is not None
            else repositories.get_primary_parent_contact(student.id)
        ),
        public_invite=True,
    )
