import sqlite3

import pytest

from app import repositories
from app.db import get_db


def test_create_and_list_student(app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "张同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "college": "信息学院",
                "major": "计算机类",
                "city": "上海",
                "phone": "13800000000",
            }
        )
        students = repositories.list_students()

    assert student_id == 1
    assert len(students) == 1
    assert students[0].name == "张同学"
    assert students[0].service_stage == "信息收集"


def test_create_parent_contact_under_student(app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "李同学",
                "gender": "男",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "机械类",
            }
        )
        parent_id = repositories.create_parent_contact(
            student_id,
            {
                "name": "李女士",
                "relationship": "母亲",
                "phone": "13900000000",
                "communication_method": "微信",
            },
        )
        parents = repositories.list_parent_contacts(student_id)

    assert parent_id == 1
    assert len(parents) == 1
    assert parents[0].relationship == "母亲"
    assert parents[0].questionnaire_status == "未填写"


def test_parent_questionnaire_rejects_parent_contact_from_another_student(app):
    with app.app_context():
        first_student_id = repositories.create_student(
            {
                "name": "赵同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "数学类",
            }
        )
        second_student_id = repositories.create_student(
            {
                "name": "陈同学",
                "gender": "男",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "物理类",
            }
        )
        parent_id = repositories.create_parent_contact(
            first_student_id,
            {
                "name": "赵先生",
                "relationship": "父亲",
            },
        )

        with pytest.raises(sqlite3.IntegrityError):
            get_db().execute(
                """
                INSERT INTO parent_questionnaires (
                    student_id, parent_contact_id, family_resources
                )
                VALUES (?, ?, ?)
                """,
                (second_student_id, parent_id, "家庭支持稳定"),
            )
