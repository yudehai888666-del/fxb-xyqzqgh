from datetime import datetime, timedelta

from app import repositories
from app.db import get_db


def create_student():
    return repositories.create_student(
        {
            "name": "邀请同学",
            "gender": "女",
            "enrollment_year": 2026,
            "current_term": "大一上",
            "school": "示例大学",
            "major": "计算机科学",
        }
    )


def test_teacher_can_generate_two_distinct_invitation_qr_codes(client, app):
    with app.app_context():
        student_id = create_student()

    for kind in ("student", "parent"):
        response = client.post(f"/students/{student_id}/invitations/{kind}/create")
        assert response.status_code == 302

    with app.app_context():
        invitations = repositories.list_questionnaire_invitations(student_id)
        assert len(invitations) == 2
        assert len({row["token"] for row in invitations}) == 2
        token = invitations[0]["token"]

    response = client.get(f"/invite/{token}/qr.svg")
    assert response.status_code == 200
    assert response.content_type == "image/svg+xml"
    assert b"<svg" in response.data

    manage = client.get(f"/students/{student_id}/invitations")
    assert "https://questionnaire.example.test/invite/" in manage.get_data(as_text=True)


def test_student_and_parent_can_submit_simultaneously_with_separate_tokens(client, app):
    with app.app_context():
        student_id = create_student()
        student_invite = repositories.create_questionnaire_invitation(student_id, "student")
        parent_invite = repositories.create_questionnaire_invitation(student_id, "parent")

    student_page = client.get(f"/invite/{student_invite['token']}")
    parent_page = client.get(f"/invite/{parent_invite['token']}")
    assert student_page.status_code == 200
    assert parent_page.status_code == 200
    assert "主导航" not in student_page.get_data(as_text=True)
    assert "老师已收到" not in student_page.get_data(as_text=True)

    student_response = client.post(
        f"/invite/{student_invite['token']}",
        data={"academic_status": "绩点3.7", "future_intentions": "保研"},
    )
    parent_response = client.post(
        f"/invite/{parent_invite['token']}",
        data={
            "parent_name": "王女士",
            "relationship": "母亲",
            "family_resources": "支持学业规划",
        },
    )
    assert student_response.status_code == 200
    assert parent_response.status_code == 200
    assert "提交成功" in student_response.get_data(as_text=True)

    with app.app_context():
        assert repositories.get_student_questionnaire(student_id)["academic_status"] == "绩点3.7"
        assert repositories.get_parent_questionnaire(student_id)["parent_name"] == "王女士"
        assert repositories.get_questionnaire_invitation(student_invite["token"])["status"] == "已提交"
        assert repositories.get_questionnaire_invitation(parent_invite["token"])["status"] == "已提交"
        student_submissions = repositories.list_questionnaire_submissions(student_id, "student")
        parent_submissions = repositories.list_questionnaire_submissions(student_id, "parent")
        assert len(student_submissions) == 1
        assert len(parent_submissions) == 1

    assert client.get(f"/invite/{student_invite['token']}").status_code == 410
    assert client.get(f"/invite/{parent_invite['token']}").status_code == 410

    result_page = client.get(
        f"/students/{student_id}/questionnaire-results/student"
    )
    assert result_page.status_code == 200
    assert "原始提交记录" in result_page.get_data(as_text=True)
    assert "绩点3.7" in result_page.get_data(as_text=True)

    with app.app_context():
        repositories.save_student_questionnaire(
            student_id, {"academic_status": "老师修改后"}
        )
    result_page = client.get(
        f"/students/{student_id}/questionnaire-results/student"
    )
    assert "绩点3.7" in result_page.get_data(as_text=True)
    assert "老师修改后" not in result_page.get_data(as_text=True)


def test_revoked_and_expired_invitations_cannot_be_used(client, app):
    with app.app_context():
        student_id = create_student()
        revoked = repositories.create_questionnaire_invitation(student_id, "student")
        repositories.revoke_questionnaire_invitation(revoked["id"], student_id)
        expired = repositories.create_questionnaire_invitation(student_id, "parent")
        get_db().execute(
            "UPDATE questionnaire_invitations SET expires_at = ? WHERE id = ?",
            ((datetime.now() - timedelta(days=1)).isoformat(), expired["id"]),
        )
        get_db().commit()

    assert client.get(f"/invite/{revoked['token']}").status_code == 410
    assert client.get(f"/invite/{expired['token']}").status_code == 410


def test_regenerating_invitation_revokes_previous_token(client, app):
    with app.app_context():
        student_id = create_student()
        old = repositories.create_questionnaire_invitation(student_id, "student")
        new = repositories.create_questionnaire_invitation(student_id, "student")
        assert repositories.get_questionnaire_invitation(old["token"])["status"] == "已作废"
        assert repositories.get_questionnaire_invitation(new["token"])["status"] == "有效"

    assert client.get(f"/invite/{old['token']}").status_code == 410
    assert client.get(f"/invite/{new['token']}").status_code == 200
