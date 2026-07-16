from app import repositories
from tests.employment_factories import (
    confirmed_test_report,
    create_and_confirm_second_report,
    create_test_data_plan,
)


def test_employment_plan_requires_explicit_confirmed_report(client, app):
    student_id, confirmed_report_id = confirmed_test_report(app)
    response = client.post(
        f"/students/{student_id}/planning/generate",
        data={"intelligence_report_id": confirmed_report_id},
    )
    assert response.status_code == 302
    with app.app_context():
        document = repositories.list_planning_documents(student_id)[0]
        assert document["intelligence_report_id"] == confirmed_report_id


def test_plan_keeps_selected_report_when_new_report_is_created(app):
    student_id, first_report_id = confirmed_test_report(app)
    with app.app_context():
        document_id = repositories.create_planning_document(
            student_id,
            {
                "title": "就业规划",
                "content_markdown": "# 就业规划",
                "intelligence_report_id": first_report_id,
            },
        )
        create_and_confirm_second_report(student_id)
        assert repositories.get_planning_document(document_id)["intelligence_report_id"] == first_report_id


def test_test_data_plan_stays_internal_and_cannot_export(client, app):
    student_id, report_id, document_id = create_test_data_plan(app)
    visibility = client.post(
        f"/students/{student_id}/planning/documents/{document_id}/visibility",
        data={"visibility": "学生可见"},
    )
    export = client.post(f"/students/{student_id}/planning/documents/{document_id}/export/pdf")
    assert visibility.status_code == 409
    assert export.status_code == 409
