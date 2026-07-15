from werkzeug.security import generate_password_hash

from app import create_app, repositories


def make_auth_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "auth-test-secret",
            "AUTH_DISABLED": False,
            "DATABASE": tmp_path / "auth.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
            "GENERATED_DIR": tmp_path / "generated",
            "BACKUP_DIR": tmp_path / "backups",
        }
    )


def create_user(role, username):
    return repositories.create_user(
        {
            "username": username,
            "display_name": username,
            "password_hash": generate_password_hash("password123", method="pbkdf2:sha256:600000"),
            "role": role,
        }
    )


def create_student(name):
    return repositories.create_student(
        {
            "name": name,
            "gender": "女",
            "enrollment_year": 2026,
            "current_term": "大一上",
            "school": "示例大学",
            "major": "法学",
        }
    )


def login(client, username):
    return client.post(
        "/login",
        data={"username": username, "password": "password123"},
    )


def test_backend_requires_login_but_public_invitation_remains_accessible(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        student_id = create_student("公开问卷同学")
        invitation = repositories.create_questionnaire_invitation(student_id, "student")

    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert client.get(f"/invite/{invitation['token']}").status_code == 200


def test_admin_can_access_all_students_and_manage_users(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        create_user("admin", "admin")
        student_id = create_student("管理员可见")

    assert login(client, "admin").status_code == 302
    assert client.get(f"/students/{student_id}").status_code == 200
    assert client.get("/admin/users").status_code == 200


def test_teacher_only_sees_assigned_students(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        teacher_id = create_user("teacher", "teacher")
        assigned_id = create_student("已授权学生")
        hidden_id = create_student("未授权学生")
        repositories.assign_student_access(assigned_id, teacher_id, "编辑")

    login(client, "teacher")
    page = client.get("/students").get_data(as_text=True)
    assert "已授权学生" in page
    assert "未授权学生" not in page
    assert client.get(f"/students/{assigned_id}").status_code == 200
    assert client.get(f"/students/{hidden_id}").status_code == 403
    assert client.get("/admin/users").status_code == 403


def test_read_only_assignment_blocks_changes(tmp_path):
    app = make_auth_app(tmp_path)
    client = app.test_client()
    with app.app_context():
        user_id = create_user("collaborator", "viewer")
        student_id = create_student("只读学生")
        repositories.assign_student_access(student_id, user_id, "查看")

    login(client, "viewer")
    assert client.get(f"/students/{student_id}").status_code == 200
    response = client.post(
        f"/students/{student_id}/student-questionnaire",
        data={"academic_status": "不应保存"},
    )
    assert response.status_code == 403
