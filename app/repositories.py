from .db import get_db
from .models import ParentContact, Student


def row_to_student(row):
    return Student(
        id=row["id"],
        name=row["name"],
        gender=row["gender"],
        enrollment_year=row["enrollment_year"],
        current_term=row["current_term"],
        school=row["school"],
        college=row["college"],
        major=row["major"],
        city=row["city"],
        phone=row["phone"],
        service_stage=row["service_stage"],
        responsible_teacher=row["responsible_teacher"],
    )


def row_to_parent_contact(row):
    return ParentContact(
        id=row["id"],
        student_id=row["student_id"],
        name=row["name"],
        relationship=row["relationship"],
        phone=row["phone"],
        communication_method=row["communication_method"],
        is_primary_decision_maker=bool(row["is_primary_decision_maker"]),
        questionnaire_status=row["questionnaire_status"],
    )


def create_student(data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO students (
            name, gender, enrollment_year, current_term, school, college,
            major, city, phone, service_stage, responsible_teacher
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data["gender"],
            int(data["enrollment_year"]),
            data["current_term"],
            data["school"],
            data.get("college", ""),
            data["major"],
            data.get("city", ""),
            data.get("phone", ""),
            data.get("service_stage", "信息收集"),
            data.get("responsible_teacher", "本人"),
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_students():
    rows = get_db().execute(
        "SELECT * FROM students ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    return [row_to_student(row) for row in rows]


def get_student(student_id):
    row = get_db().execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    return row_to_student(row) if row else None


def create_parent_contact(student_id, data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO parent_contacts (
            student_id, name, relationship, phone, communication_method,
            is_primary_decision_maker
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            data["name"],
            data["relationship"],
            data.get("phone", ""),
            data.get("communication_method", ""),
            1 if data.get("is_primary_decision_maker", True) else 0,
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_parent_contacts(student_id):
    rows = get_db().execute(
        "SELECT * FROM parent_contacts WHERE student_id = ? ORDER BY id",
        (student_id,),
    ).fetchall()
    return [row_to_parent_contact(row) for row in rows]
