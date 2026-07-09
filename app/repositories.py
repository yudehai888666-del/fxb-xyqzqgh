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


def save_student_questionnaire(student_id, data):
    db = get_db()
    db.execute(
        """
        INSERT INTO student_questionnaires (
            student_id, adaptation_status, academic_status, weak_subjects,
            tutoring_needs, interests_strengths, future_intentions,
            motivation_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            adaptation_status = excluded.adaptation_status,
            academic_status = excluded.academic_status,
            weak_subjects = excluded.weak_subjects,
            tutoring_needs = excluded.tutoring_needs,
            interests_strengths = excluded.interests_strengths,
            future_intentions = excluded.future_intentions,
            motivation_status = excluded.motivation_status,
            submitted_at = CURRENT_TIMESTAMP
        """,
        (
            student_id,
            data.get("adaptation_status", ""),
            data.get("academic_status", ""),
            data.get("weak_subjects", ""),
            data.get("tutoring_needs", ""),
            data.get("interests_strengths", ""),
            data.get("future_intentions", ""),
            data.get("motivation_status", ""),
        ),
    )
    db.commit()


def get_student_questionnaire(student_id):
    return get_db().execute(
        "SELECT * FROM student_questionnaires WHERE student_id = ?",
        (student_id,),
    ).fetchone()


def get_primary_parent_contact(student_id):
    row = get_db().execute(
        """
        SELECT *
        FROM parent_contacts
        WHERE student_id = ?
        ORDER BY is_primary_decision_maker DESC, id
        LIMIT 1
        """,
        (student_id,),
    ).fetchone()
    return row_to_parent_contact(row) if row else None


def get_or_create_primary_parent(student_id, data):
    parent = get_primary_parent_contact(student_id)
    if parent:
        return parent.id

    return create_parent_contact(
        student_id,
        {
            "name": data.get("parent_name", ""),
            "relationship": data.get("relationship", ""),
            "phone": data.get("parent_phone", ""),
            "communication_method": data.get("communication_method", ""),
            "is_primary_decision_maker": True,
        },
    )


def update_parent_contact_for_questionnaire(student_id, parent_contact_id, data):
    get_db().execute(
        """
        UPDATE parent_contacts
        SET
            name = COALESCE(NULLIF(?, ''), name),
            relationship = COALESCE(NULLIF(?, ''), relationship),
            phone = COALESCE(NULLIF(?, ''), phone),
            communication_method = COALESCE(NULLIF(?, ''), communication_method),
            questionnaire_status = '已填写',
            updated_at = CURRENT_TIMESTAMP
        WHERE student_id = ? AND id = ?
        """,
        (
            data.get("parent_name", ""),
            data.get("relationship", ""),
            data.get("parent_phone", ""),
            data.get("communication_method", ""),
            student_id,
            parent_contact_id,
        ),
    )


def save_parent_questionnaire(student_id, data):
    db = get_db()
    parent_contact_id = get_or_create_primary_parent(student_id, data)
    update_parent_contact_for_questionnaire(student_id, parent_contact_id, data)
    db.execute(
        """
        INSERT INTO parent_questionnaires (
            student_id, parent_contact_id, family_resources, target_priorities,
            parent_observations, current_concerns, investment_willingness
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(parent_contact_id) DO UPDATE SET
            student_id = excluded.student_id,
            family_resources = excluded.family_resources,
            target_priorities = excluded.target_priorities,
            parent_observations = excluded.parent_observations,
            current_concerns = excluded.current_concerns,
            investment_willingness = excluded.investment_willingness,
            submitted_at = CURRENT_TIMESTAMP
        """,
        (
            student_id,
            parent_contact_id,
            data.get("family_resources", ""),
            data.get("target_priorities", ""),
            data.get("parent_observations", ""),
            data.get("current_concerns", ""),
            data.get("investment_willingness", ""),
        ),
    )
    db.commit()


def get_parent_questionnaire(student_id):
    return get_db().execute(
        """
        SELECT
            pq.*,
            pc.name AS parent_name,
            pc.relationship,
            pc.phone AS parent_phone,
            pc.communication_method
        FROM parent_questionnaires pq
        JOIN parent_contacts pc
            ON pc.student_id = pq.student_id
            AND pc.id = pq.parent_contact_id
        WHERE pq.student_id = ?
        ORDER BY pq.submitted_at DESC, pq.id DESC
        LIMIT 1
        """,
        (student_id,),
    ).fetchone()


def create_planning_document(student_id, data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO planning_documents (
            student_id, title, status, content_markdown, file_path
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            student_id,
            data["title"],
            data.get("status", "草稿"),
            data["content_markdown"],
            data.get("file_path", ""),
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_planning_document(document_id):
    return get_db().execute(
        "SELECT * FROM planning_documents WHERE id = ?",
        (document_id,),
    ).fetchone()


def list_planning_documents(student_id):
    return get_db().execute(
        """
        SELECT *
        FROM planning_documents
        WHERE student_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()


def update_planning_document_file_path(document_id, file_path):
    db = get_db()
    db.execute(
        """
        UPDATE planning_documents
        SET file_path = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
        WHERE id = ?
        """,
        (file_path, document_id),
    )
    db.commit()


def delete_planning_document(document_id):
    db = get_db()
    db.execute("DELETE FROM planning_documents WHERE id = ?", (document_id,))
    db.commit()


def save_teacher_notes(student_id, data):
    fields = (
        "source_channel",
        "consultation_stage",
        "core_request",
        "family_student_conflict",
        "resource_match_level",
        "goal_feasibility",
        "execution_risk",
        "academic_risk",
        "transfer_feasibility",
        "service_suggestions",
        "ai_generation_focus",
    )
    existing = get_teacher_notes(student_id)
    values = {
        field: data[field] if field in data else (existing[field] if existing else "")
        for field in fields
    }

    db = get_db()
    db.execute(
        """
        INSERT INTO teacher_notes (
            student_id, source_channel, consultation_stage, core_request,
            family_student_conflict, resource_match_level, goal_feasibility,
            execution_risk, academic_risk, transfer_feasibility,
            service_suggestions, ai_generation_focus
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            source_channel = excluded.source_channel,
            consultation_stage = excluded.consultation_stage,
            core_request = excluded.core_request,
            family_student_conflict = excluded.family_student_conflict,
            resource_match_level = excluded.resource_match_level,
            goal_feasibility = excluded.goal_feasibility,
            execution_risk = excluded.execution_risk,
            academic_risk = excluded.academic_risk,
            transfer_feasibility = excluded.transfer_feasibility,
            service_suggestions = excluded.service_suggestions,
            ai_generation_focus = excluded.ai_generation_focus,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            student_id,
            values["source_channel"],
            values["consultation_stage"],
            values["core_request"],
            values["family_student_conflict"],
            values["resource_match_level"],
            values["goal_feasibility"],
            values["execution_risk"],
            values["academic_risk"],
            values["transfer_feasibility"],
            values["service_suggestions"],
            values["ai_generation_focus"],
        ),
    )
    db.commit()


def get_teacher_notes(student_id):
    return get_db().execute(
        "SELECT * FROM teacher_notes WHERE student_id = ?",
        (student_id,),
    ).fetchone()


def create_material(student_id, data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO materials (
            student_id, uploader_type, original_filename, stored_filename, category
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            student_id,
            data["uploader_type"],
            data["original_filename"],
            data["stored_filename"],
            data.get("category", "其他材料"),
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_materials(student_id):
    return get_db().execute(
        """
        SELECT *
        FROM materials
        WHERE student_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()


def confirm_disclaimer(student_id, data):
    db = get_db()
    signer_type = data["signer_type"].strip()
    signer_name = data["signer_name"].strip()
    reason = data["reason"].strip()
    cursor = db.execute(
        """
        INSERT INTO disclaimers (
            student_id, signer_type, signer_name, reason
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            signer_type,
            signer_name,
            reason,
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_disclaimers(student_id):
    return get_db().execute(
        """
        SELECT *
        FROM disclaimers
        WHERE student_id = ?
        ORDER BY confirmed_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()
