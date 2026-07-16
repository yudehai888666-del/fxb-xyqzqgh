from datetime import datetime, timedelta
import json
from secrets import token_urlsafe

from .db import get_db
from .models import ParentContact, Student


def create_user(data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO users (username, display_name, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (
            data["username"].strip(),
            data["display_name"].strip(),
            data["password_hash"],
            data["role"],
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    return get_db().execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()


def list_users():
    return get_db().execute(
        "SELECT * FROM users ORDER BY is_active DESC, display_name, id"
    ).fetchall()


def update_user_last_login(user_id):
    db = get_db()
    db.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    db.commit()


def set_user_active(user_id, is_active):
    db = get_db()
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
    db.commit()


def assign_student_access(student_id, user_id, access_level="编辑"):
    db = get_db()
    db.execute(
        """
        INSERT INTO student_access (student_id, user_id, access_level)
        VALUES (?, ?, ?)
        ON CONFLICT(student_id, user_id) DO UPDATE SET access_level = excluded.access_level
        """,
        (student_id, user_id, access_level),
    )
    db.commit()


def revoke_student_access(student_id, user_id):
    db = get_db()
    db.execute(
        "DELETE FROM student_access WHERE student_id = ? AND user_id = ?",
        (student_id, user_id),
    )
    db.commit()


def list_student_access(student_id):
    return get_db().execute(
        """
        SELECT sa.*, u.username, u.display_name, u.role, u.is_active
        FROM student_access sa JOIN users u ON u.id = sa.user_id
        WHERE sa.student_id = ? ORDER BY u.display_name
        """,
        (student_id,),
    ).fetchall()


def user_can_access_student(user, student_id, require_edit=False):
    if user is None:
        return False
    if user["role"] == "admin":
        return True
    row = get_db().execute(
        "SELECT access_level FROM student_access WHERE student_id = ? AND user_id = ?",
        (student_id, user["id"]),
    ).fetchone()
    if row is None:
        return False
    return not require_edit or row["access_level"] == "编辑"


def create_audit_log(user_id, action, target_type="", target_id=None, details="", ip_address=""):
    db = get_db()
    db.execute(
        """
        INSERT INTO audit_logs (user_id, action, target_type, target_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, action, target_type, target_id, details, ip_address),
    )
    db.commit()


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


def create_student(data, commit=True):
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
            data["name"], data["gender"], int(data["enrollment_year"]),
            data["current_term"], data["school"], data.get("college", ""),
            data["major"], data.get("city", ""), data.get("phone", ""),
            data.get("service_stage", "信息收集"),
            data.get("responsible_teacher", "本人"),
        ),
    )
    if commit:
        db.commit()
    return cursor.lastrowid


def list_students(user=None):
    if user is None or user["role"] == "admin":
        rows = get_db().execute(
            "SELECT * FROM students ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    else:
        rows = get_db().execute(
            """
            SELECT s.* FROM students s
            JOIN student_access sa ON sa.student_id = s.id
            WHERE sa.user_id = ?
            ORDER BY s.updated_at DESC, s.id DESC
            """,
            (user["id"],),
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
    version = db.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM planning_documents WHERE student_id = ?",
        (student_id,),
    ).fetchone()[0]
    cursor = db.execute(
        """
        INSERT INTO planning_documents (
            student_id, title, status, content_markdown, file_path, version, visibility
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            data["title"],
            data.get("status", "草稿"),
            data["content_markdown"],
            data.get("file_path", ""),
            data.get("version", version),
            data.get("visibility", "老师内部"),
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


def update_planning_document_visibility(document_id, visibility):
    db = get_db()
    db.execute(
        """
        UPDATE planning_documents
        SET visibility = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
        WHERE id = ?
        """,
        (visibility, document_id),
    )
    db.execute(
        """
        UPDATE student_files SET visibility = ?
        WHERE source_type = 'planning_document' AND source_id = ?
        """,
        (visibility, document_id),
    )
    db.commit()


def confirm_planning_document(document_id):
    db = get_db()
    db.execute(
        """
        UPDATE planning_documents
        SET status = '已确认', updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
        WHERE id = ? AND status = '草稿'
        """,
        (document_id,),
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
        "combined_notes",
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
            service_suggestions, ai_generation_focus, combined_notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            combined_notes = excluded.combined_notes,
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
            values["combined_notes"],
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
            student_id, uploader_type, original_filename, stored_filename, category,
            visibility
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            data["uploader_type"],
            data["original_filename"],
            data["stored_filename"],
            data.get("category", "其他材料"),
            data.get("visibility", "老师内部"),
        ),
    )
    db.commit()
    return cursor.lastrowid


def archive_student_file(student_id, data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO student_files (
            student_id, source_type, source_id, category, original_filename,
            storage_area, storage_key, mime_type, size_bytes, sha256, version,
            visibility, is_current
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_type, source_id) DO UPDATE SET
            storage_key = excluded.storage_key,
            mime_type = excluded.mime_type,
            size_bytes = excluded.size_bytes,
            sha256 = excluded.sha256,
            visibility = excluded.visibility
        """,
        (
            student_id,
            data["source_type"],
            data["source_id"],
            data["category"],
            data["original_filename"],
            data["storage_area"],
            data["storage_key"],
            data.get("mime_type", ""),
            data.get("size_bytes", 0),
            data.get("sha256", ""),
            data.get("version", 1),
            data.get("visibility", "老师内部"),
            1 if data.get("is_current", True) else 0,
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_student_files(student_id, include_deleted=False):
    deleted_filter = "" if include_deleted else "AND deleted_at IS NULL"
    return get_db().execute(
        f"""
        SELECT * FROM student_files
        WHERE student_id = ? {deleted_filter}
        ORDER BY created_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()


def get_student_file(file_id):
    return get_db().execute(
        "SELECT * FROM student_files WHERE id = ?", (file_id,)
    ).fetchone()


def update_student_file_visibility(file_id, visibility):
    db = get_db()
    file_record = get_student_file(file_id)
    if file_record is None:
        return
    db.execute("UPDATE student_files SET visibility = ? WHERE id = ?", (visibility, file_id))
    if file_record["source_type"] == "material":
        db.execute("UPDATE materials SET visibility = ? WHERE id = ?", (visibility, file_record["source_id"]))
    elif file_record["source_type"] == "planning_document":
        db.execute("UPDATE planning_documents SET visibility = ? WHERE id = ?", (visibility, file_record["source_id"]))
    db.commit()


def soft_delete_student_file(file_id):
    db = get_db()
    db.execute(
        "UPDATE student_files SET deleted_at = CURRENT_TIMESTAMP, is_current = 0 WHERE id = ?",
        (file_id,),
    )
    db.commit()


def create_questionnaire_invitation(student_id, questionnaire_type, valid_days=7):
    if questionnaire_type not in ("student", "parent"):
        raise ValueError("invalid questionnaire type")
    db = get_db()
    db.execute(
        """
        UPDATE questionnaire_invitations SET status = '已作废'
        WHERE student_id = ? AND questionnaire_type = ? AND status = '有效'
        """,
        (student_id, questionnaire_type),
    )
    token = token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=valid_days)).isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO questionnaire_invitations (
            student_id, questionnaire_type, token, expires_at
        ) VALUES (?, ?, ?, ?)
        """,
        (student_id, questionnaire_type, token, expires_at),
    )
    db.commit()
    return get_questionnaire_invitation_by_id(cursor.lastrowid)


def get_questionnaire_invitation_by_id(invitation_id):
    return get_db().execute(
        "SELECT * FROM questionnaire_invitations WHERE id = ?", (invitation_id,)
    ).fetchone()


def get_questionnaire_invitation(token):
    return get_db().execute(
        "SELECT * FROM questionnaire_invitations WHERE token = ?", (token,)
    ).fetchone()


def list_questionnaire_invitations(student_id):
    return get_db().execute(
        """
        SELECT * FROM questionnaire_invitations
        WHERE student_id = ? ORDER BY created_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()


def mark_invitation_opened(invitation_id):
    db = get_db()
    db.execute(
        """
        UPDATE questionnaire_invitations
        SET opened_at = COALESCE(opened_at, CURRENT_TIMESTAMP)
        WHERE id = ?
        """,
        (invitation_id,),
    )
    db.commit()


def mark_invitation_submitted(invitation_id):
    db = get_db()
    db.execute(
        """
        UPDATE questionnaire_invitations
        SET status = '已提交', submitted_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (invitation_id,),
    )
    db.commit()


def revoke_questionnaire_invitation(invitation_id, student_id):
    db = get_db()
    db.execute(
        """
        UPDATE questionnaire_invitations SET status = '已作废'
        WHERE id = ? AND student_id = ? AND status = '有效'
        """,
        (invitation_id, student_id),
    )
    db.commit()


def create_questionnaire_submission(student_id, invitation_id, questionnaire_type, answers):
    if questionnaire_type not in ("student", "parent"):
        raise ValueError("invalid questionnaire type")
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO questionnaire_submissions (
            student_id, invitation_id, questionnaire_type, answers_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            invitation_id,
            questionnaire_type,
            json.dumps(dict(answers), ensure_ascii=False),
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_questionnaire_submissions(student_id, questionnaire_type):
    return get_db().execute(
        """
        SELECT * FROM questionnaire_submissions
        WHERE student_id = ? AND questionnaire_type = ?
        ORDER BY submitted_at DESC, id DESC
        """,
        (student_id, questionnaire_type),
    ).fetchall()


def get_questionnaire_submission(submission_id):
    return get_db().execute(
        "SELECT * FROM questionnaire_submissions WHERE id = ?", (submission_id,)
    ).fetchone()


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


REPLANNING_FIELDS = (
    "original_goal",
    "trigger_event",
    "trigger_reason",
    "responsibility_type",
    "new_primary_goal",
    "new_secondary_goal",
    "new_third_goal",
    "original_service_scope",
    "completed_work",
    "new_service_scope",
    "fee_adjustment_type",
    "additional_fee",
    "refund_or_credit",
    "fee_notes",
    "agreement_terms",
    "status",
)


def create_replanning_case(student_id, data):
    db = get_db()
    values = {field: data.get(field, "") for field in REPLANNING_FIELDS}
    values["status"] = values["status"] or "草稿"
    cursor = db.execute(
        """
        INSERT INTO replanning_cases (
            student_id, original_goal, trigger_event, trigger_reason,
            responsibility_type, new_primary_goal, new_secondary_goal,
            new_third_goal, original_service_scope, completed_work,
            new_service_scope, fee_adjustment_type, additional_fee,
            refund_or_credit, fee_notes, agreement_terms, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            values["original_goal"],
            values["trigger_event"],
            values["trigger_reason"],
            values["responsibility_type"],
            values["new_primary_goal"],
            values["new_secondary_goal"],
            values["new_third_goal"],
            values["original_service_scope"],
            values["completed_work"],
            values["new_service_scope"],
            values["fee_adjustment_type"],
            values["additional_fee"],
            values["refund_or_credit"],
            values["fee_notes"],
            values["agreement_terms"],
            values["status"],
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_replanning_case(case_id):
    return get_db().execute(
        "SELECT * FROM replanning_cases WHERE id = ?",
        (case_id,),
    ).fetchone()


def list_replanning_cases(student_id):
    return get_db().execute(
        """
        SELECT *
        FROM replanning_cases
        WHERE student_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()


def update_replanning_status(case_id, status):
    db = get_db()
    db.execute(
        """
        UPDATE replanning_cases
        SET status = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
        WHERE id = ?
        """,
        (status, case_id),
    )
    db.commit()


KNOWLEDGE_STATUS_VALUES = ("草稿", "待审核", "已发布", "已退回")
KNOWLEDGE_TABLES = {
    "major": "knowledge_majors",
    "job": "knowledge_jobs",
    "skill": "knowledge_skills",
}


def create_knowledge_major(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO knowledge_majors (
            name, discipline_category, degree_level, description,
            source_url, source_name, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"].strip(), data.get("discipline_category", "").strip(),
            data.get("degree_level", "本科").strip() or "本科",
            data.get("description", "").strip(), data.get("source_url", "").strip(),
            data.get("source_name", "").strip(), created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def create_knowledge_job(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO knowledge_jobs (
            name, industry_name, job_family, description, development_direction,
            source_url, source_name, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"].strip(), data.get("industry_name", "").strip(),
            data.get("job_family", "").strip(), data.get("description", "").strip(),
            data.get("development_direction", "").strip(),
            data.get("source_url", "").strip(), data.get("source_name", "").strip(),
            created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def create_knowledge_skill(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO knowledge_skills (
            name, skill_type, description, source_url, source_name, created_by
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"].strip(), data.get("skill_type", "专业技能").strip() or "专业技能",
            data.get("description", "").strip(), data.get("source_url", "").strip(),
            data.get("source_name", "").strip(), created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_knowledge_majors():
    return get_db().execute(
        "SELECT * FROM knowledge_majors ORDER BY name"
    ).fetchall()


def list_knowledge_jobs():
    return get_db().execute(
        "SELECT * FROM knowledge_jobs ORDER BY industry_name, name"
    ).fetchall()


def list_knowledge_skills():
    return get_db().execute(
        "SELECT * FROM knowledge_skills ORDER BY skill_type, name"
    ).fetchall()


def update_knowledge_status(kind, record_id, status):
    table = KNOWLEDGE_TABLES.get(kind)
    if table is None or status not in KNOWLEDGE_STATUS_VALUES:
        raise ValueError("invalid knowledge status update")
    db = get_db()
    db.execute(
        f"UPDATE {table} SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, record_id),
    )
    db.commit()


def create_major_job_link(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO major_job_links (
            major_id, job_id, relevance_level, evidence_note, source_url, created_by
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(major_id, job_id) DO UPDATE SET
            relevance_level = excluded.relevance_level,
            evidence_note = excluded.evidence_note,
            source_url = excluded.source_url
        """,
        (
            int(data["major_id"]), int(data["job_id"]),
            data.get("relevance_level", "相关").strip() or "相关",
            data.get("evidence_note", "").strip(), data.get("source_url", "").strip(),
            created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def _validate_job_skill_references(db, source_id, owner_user_id, reviewer_user_id):
    references = (
        (source_id, "intelligence_sources", "source"),
        (owner_user_id, "users", "owner"),
        (reviewer_user_id, "users", "reviewer"),
    )
    for record_id, table, label in references:
        if record_id is not None and db.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (record_id,)
        ).fetchone() is None:
            raise ValueError(f"invalid job skill {label}")


def _parse_job_skill_date(value, label):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{label} must use a valid YYYY-MM-DD date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must use a valid YYYY-MM-DD date")
    return parsed


def _validate_job_skill_dates(last_verified_at, next_check_at):
    last_verified = _parse_job_skill_date(last_verified_at, "last_verified_at")
    next_check = _parse_job_skill_date(next_check_at, "next_check_at")
    if last_verified and next_check and next_check < last_verified:
        raise ValueError("下次复核日期不得早于最近核查日期")


def _validate_job_skill_sample_size(sample_size):
    if not isinstance(sample_size, int) or sample_size < 0:
        raise ValueError("invalid sample size")


def create_job_skill_link(data, created_by=None):
    confidence_level = data.get("confidence_level", "").strip()
    if confidence_level not in ("", "低", "中", "高"):
        raise ValueError("invalid confidence level")
    sample_size = int(data.get("sample_size") or 0)
    if sample_size < 0:
        raise ValueError("invalid sample size")
    db = get_db()
    source_id = _optional_int(data.get("source_id"))
    owner_user_id = _optional_int(data.get("owner_user_id"))
    reviewer_user_id = _optional_int(data.get("reviewer_user_id"))
    last_verified_at = data.get("last_verified_at", "").strip()
    next_check_at = data.get("next_check_at", "").strip()
    _validate_job_skill_dates(last_verified_at, next_check_at)
    _validate_job_skill_references(
        db, source_id, owner_user_id, reviewer_user_id
    )
    db.execute(
        """
        INSERT INTO job_skill_links (
            job_id, skill_id, importance_level, proficiency_level,
            evidence_note, source_url, source_id, confidence_level,
            sample_size, last_verified_at, next_check_at, owner_user_id,
            reviewer_user_id, status, limitation_note, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '草稿', ?, ?)
        ON CONFLICT(job_id, skill_id) DO UPDATE SET
            importance_level = excluded.importance_level,
            proficiency_level = excluded.proficiency_level,
            evidence_note = excluded.evidence_note,
            source_url = excluded.source_url,
            source_id = excluded.source_id,
            confidence_level = excluded.confidence_level,
            sample_size = excluded.sample_size,
            last_verified_at = excluded.last_verified_at,
            next_check_at = excluded.next_check_at,
            owner_user_id = excluded.owner_user_id,
            reviewer_user_id = excluded.reviewer_user_id,
            status = '草稿',
            limitation_note = excluded.limitation_note,
            created_by = excluded.created_by
        """,
        (
            int(data["job_id"]), int(data["skill_id"]),
            data.get("importance_level", "核心").strip() or "核心",
            data.get("proficiency_level", "掌握").strip() or "掌握",
            data.get("evidence_note", "").strip(), data.get("source_url", "").strip(),
            source_id, confidence_level, sample_size,
            last_verified_at, next_check_at,
            owner_user_id, reviewer_user_id,
            data.get("limitation_note", "").strip(), created_by,
        ),
    )
    link_id = db.execute(
        "SELECT id FROM job_skill_links WHERE job_id = ? AND skill_id = ?",
        (int(data["job_id"]), int(data["skill_id"])),
    ).fetchone()["id"]
    db.commit()
    return link_id


def get_job_skill_link(link_id):
    return get_db().execute(
        """
        SELECT js.*, j.name AS job_name, s.name AS skill_name,
               source.name AS source_name,
               source.url AS configured_source_url,
               owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name
        FROM job_skill_links js
        JOIN knowledge_jobs j ON j.id = js.job_id
        JOIN knowledge_skills s ON s.id = js.skill_id
        LEFT JOIN intelligence_sources source ON source.id = js.source_id
        LEFT JOIN users owner ON owner.id = js.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = js.reviewer_user_id
        WHERE js.id = ?
        """,
        (link_id,),
    ).fetchone()


def list_job_skill_links():
    return get_db().execute(
        """
        SELECT js.*, j.name AS job_name, s.name AS skill_name,
               source.name AS source_name,
               source.url AS configured_source_url,
               owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name
        FROM job_skill_links js
        JOIN knowledge_jobs j ON j.id = js.job_id
        JOIN knowledge_skills s ON s.id = js.skill_id
        LEFT JOIN intelligence_sources source ON source.id = js.source_id
        LEFT JOIN users owner ON owner.id = js.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = js.reviewer_user_id
        ORDER BY j.name, s.name
        """
    ).fetchall()


def _validate_job_skill_governance(link):
    _validate_job_skill_references(
        get_db(), link["source_id"], link["owner_user_id"], link["reviewer_user_id"]
    )
    required = (
        link["evidence_note"],
        link["source_id"] or link["source_url"],
        link["confidence_level"],
        link["last_verified_at"],
        link["next_check_at"],
        link["owner_user_id"],
        link["reviewer_user_id"],
        link["limitation_note"],
    )
    if not all(required):
        raise ValueError(
            "提交前请补齐证据、来源、置信度、责任人、复核日期和限制说明"
        )
    _validate_job_skill_sample_size(link["sample_size"])
    _validate_job_skill_dates(link["last_verified_at"], link["next_check_at"])


def submit_job_skill_link(link_id):
    link = get_job_skill_link(link_id)
    if link is None:
        raise ValueError("岗位技能关系不存在")
    if link["status"] not in ("草稿", "已退回"):
        raise ValueError("只有草稿或已退回的岗位技能关系可提交审核")
    _validate_job_skill_governance(link)
    db = get_db()
    db.execute("UPDATE job_skill_links SET status = '待审核' WHERE id = ?", (link_id,))
    db.commit()


def review_job_skill_link(link_id, status):
    if status not in ("已发布", "已退回", "已过期"):
        raise ValueError("invalid relationship status")
    link = get_job_skill_link(link_id)
    if link is None:
        raise ValueError("岗位技能关系不存在")
    if status in ("已发布", "已退回") and link["status"] != "待审核":
        raise ValueError("岗位技能关系必须先处于待审核状态")
    if status == "已过期" and link["status"] != "已发布":
        raise ValueError("只有已发布的岗位技能关系可标记为已过期")
    if status == "已发布":
        _validate_job_skill_governance(link)
    db = get_db()
    db.execute("UPDATE job_skill_links SET status = ? WHERE id = ?", (status, link_id))
    db.commit()


def list_knowledge_graph_links():
    return get_db().execute(
        """
        SELECT mj.id, m.name AS major_name, m.status AS major_status,
               j.id AS job_id, j.name AS job_name, j.industry_name,
               j.development_direction, j.status AS job_status,
               mj.relevance_level, mj.evidence_note,
               GROUP_CONCAT(
                   s.name || '（' || js.importance_level || ' / ' || js.proficiency_level || '）',
                   '、'
               ) AS skills
        FROM major_job_links mj
        JOIN knowledge_majors m ON m.id = mj.major_id
        JOIN knowledge_jobs j ON j.id = mj.job_id
        LEFT JOIN job_skill_links js ON js.job_id = j.id
        LEFT JOIN knowledge_skills s ON s.id = js.skill_id
        GROUP BY mj.id
        ORDER BY m.name, j.name
        """
    ).fetchall()


EXAM_FIELDS = (
    "exam_name", "category", "region", "official_url", "source_name",
    "registration_start", "registration_end", "exam_date", "summary",
    "limitation_note",
    "collector_user_id", "reviewer_user_id", "execution_owner_user_id",
    "next_check_at",
)


def _optional_int(value):
    return int(value) if value not in (None, "") else None


def _exam_values(data):
    values = {}
    for field in EXAM_FIELDS:
        if field.endswith("_user_id"):
            values[field] = _optional_int(data.get(field))
        else:
            values[field] = str(data.get(field, "")).strip()
    values["region"] = values["region"] or "全国"
    return values


def _save_exam_revision(db, exam_id, version, values, change_summary, created_by):
    snapshot = dict(values)
    snapshot["status"] = "草稿"
    db.execute(
        """
        INSERT INTO exam_information_revisions (
            exam_information_id, version, snapshot_json, change_summary, created_by
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (exam_id, version, json.dumps(snapshot, ensure_ascii=False), change_summary, created_by),
    )


def create_exam_information(data, created_by=None):
    values = _exam_values(data)
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO exam_information (
            exam_name, category, region, official_url, source_name,
            registration_start, registration_end, exam_date, summary,
            limitation_note,
            collector_user_id, reviewer_user_id, execution_owner_user_id,
            next_check_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(values[field] for field in EXAM_FIELDS) + (created_by,),
    )
    exam_id = cursor.lastrowid
    _save_exam_revision(
        db, exam_id, 1, values, data.get("change_summary", "首次录入").strip() or "首次录入", created_by
    )
    db.commit()
    return exam_id


def get_exam_information(exam_id):
    return get_db().execute(
        """
        SELECT e.*, collector.display_name AS collector_name,
               reviewer.display_name AS reviewer_name,
               owner.display_name AS execution_owner_name
        FROM exam_information e
        LEFT JOIN users collector ON collector.id = e.collector_user_id
        LEFT JOIN users reviewer ON reviewer.id = e.reviewer_user_id
        LEFT JOIN users owner ON owner.id = e.execution_owner_user_id
        WHERE e.id = ?
        """,
        (exam_id,),
    ).fetchone()


def list_exam_information():
    return get_db().execute(
        """
        SELECT e.*, collector.display_name AS collector_name,
               reviewer.display_name AS reviewer_name,
               owner.display_name AS execution_owner_name
        FROM exam_information e
        LEFT JOIN users collector ON collector.id = e.collector_user_id
        LEFT JOIN users reviewer ON reviewer.id = e.reviewer_user_id
        LEFT JOIN users owner ON owner.id = e.execution_owner_user_id
        ORDER BY CASE e.status WHEN '待审核' THEN 0 WHEN '草稿' THEN 1 ELSE 2 END,
                 e.next_check_at, e.updated_at DESC
        """
    ).fetchall()


def update_exam_information(exam_id, data, created_by=None):
    values = _exam_values(data)
    db = get_db()
    existing = db.execute(
        "SELECT version FROM exam_information WHERE id = ?", (exam_id,)
    ).fetchone()
    if existing is None:
        return False
    version = existing["version"] + 1
    assignments = ", ".join(f"{field} = ?" for field in EXAM_FIELDS)
    db.execute(
        f"""
        UPDATE exam_information SET {assignments}, version = ?, status = '草稿',
            updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """,
        tuple(values[field] for field in EXAM_FIELDS) + (version, exam_id),
    )
    _save_exam_revision(
        db, exam_id, version, values,
        data.get("change_summary", "信息更新").strip() or "信息更新", created_by,
    )
    db.commit()
    return True


def update_exam_status(exam_id, status):
    if status not in ("草稿", "待审核", "已发布", "已退回", "已过期"):
        raise ValueError("invalid exam status")
    db = get_db()
    db.execute(
        "UPDATE exam_information SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, exam_id),
    )
    db.commit()


def list_exam_revisions(exam_id):
    return get_db().execute(
        """
        SELECT r.*, u.display_name AS creator_name
        FROM exam_information_revisions r
        LEFT JOIN users u ON u.id = r.created_by
        WHERE r.exam_information_id = ?
        ORDER BY r.version DESC
        """,
        (exam_id,),
    ).fetchall()


def create_industry(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO industries (
            name, category, scope, description, owner_user_id,
            reviewer_user_id, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"].strip(), data.get("category", "").strip(),
            data.get("scope", "全国").strip() or "全国",
            data.get("description", "").strip(),
            _optional_int(data.get("owner_user_id")),
            _optional_int(data.get("reviewer_user_id")), created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_industries():
    return get_db().execute(
        """
        SELECT i.*, owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name
        FROM industries i
        LEFT JOIN users owner ON owner.id = i.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = i.reviewer_user_id
        ORDER BY i.name
        """
    ).fetchall()


def update_industry_status(industry_id, status):
    if status not in KNOWLEDGE_STATUS_VALUES:
        raise ValueError("invalid industry status")
    db = get_db()
    db.execute(
        "UPDATE industries SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, industry_id),
    )
    db.commit()


def create_intelligence_source(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO intelligence_sources (
            name, url, source_kind, collection_mode, update_frequency,
            owner_user_id, reviewer_user_id, compliance_note, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"].strip(), data["url"].strip(),
            data.get("source_kind", "政府与公共机构").strip(),
            data.get("collection_mode", "公开网页").strip(),
            data.get("update_frequency", "每月").strip(),
            _optional_int(data.get("owner_user_id")),
            _optional_int(data.get("reviewer_user_id")),
            data.get("compliance_note", "").strip(), created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_intelligence_source(source_id):
    return get_db().execute(
        """
        SELECT s.*, owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name
        FROM intelligence_sources s
        LEFT JOIN users owner ON owner.id = s.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = s.reviewer_user_id
        WHERE s.id = ?
        """,
        (source_id,),
    ).fetchone()


def list_intelligence_sources():
    return get_db().execute(
        """
        SELECT s.*, owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name,
               (SELECT COUNT(*) FROM intelligence_source_snapshots ss
                WHERE ss.source_id = s.id) AS snapshot_count
        FROM intelligence_sources s
        LEFT JOIN users owner ON owner.id = s.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = s.reviewer_user_id
        ORDER BY s.is_active DESC,
                 CASE s.last_change_status WHEN '有变化' THEN 0 WHEN '采集失败' THEN 1 ELSE 2 END,
                 s.name
        """
    ).fetchall()


def record_intelligence_snapshot(source_id, data, created_by=None):
    db = get_db()
    source = db.execute(
        "SELECT last_content_hash FROM intelligence_sources WHERE id = ?", (source_id,)
    ).fetchone()
    if source is None:
        raise ValueError("source not found")
    content_hash = data.get("content_hash", "")
    error_message = data.get("error_message", "")
    is_changed = bool(content_hash and source["last_content_hash"] and
                      content_hash != source["last_content_hash"])
    if error_message:
        change_status = "采集失败"
    elif not source["last_content_hash"]:
        change_status = "首次采集"
    elif is_changed:
        change_status = "有变化"
    else:
        change_status = "无变化"
    cursor = db.execute(
        """
        INSERT INTO intelligence_source_snapshots (
            source_id, http_status, content_hash, page_title, content_excerpt,
            content_bytes, is_changed, error_message, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id, data.get("http_status"), content_hash,
            data.get("page_title", ""), data.get("content_excerpt", ""),
            data.get("content_bytes", 0), 1 if is_changed else 0,
            error_message, created_by,
        ),
    )
    if error_message:
        db.execute(
            """
            UPDATE intelligence_sources SET last_fetch_at = CURRENT_TIMESTAMP,
                last_change_status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (change_status, error_message, source_id),
        )
    else:
        db.execute(
            """
            UPDATE intelligence_sources SET last_fetch_at = CURRENT_TIMESTAMP,
                last_content_hash = ?, last_change_status = ?, last_error = '',
                updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """,
            (content_hash, change_status, source_id),
        )
    db.commit()
    return cursor.lastrowid, change_status


def list_intelligence_snapshots(source_id, limit=20):
    return get_db().execute(
        """
        SELECT ss.*, u.display_name AS creator_name
        FROM intelligence_source_snapshots ss
        LEFT JOIN users u ON u.id = ss.created_by
        WHERE ss.source_id = ? ORDER BY ss.fetched_at DESC, ss.id DESC LIMIT ?
        """,
        (source_id, int(limit)),
    ).fetchall()


def create_industry_trend(data, created_by=None):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO industry_trends (
            industry_id, title, trend_type, region, direction_summary,
            employment_impact, affected_jobs, affected_majors, evidence_summary,
            limitation_note, source_id, source_url, published_at, next_check_at,
            owner_user_id, reviewer_user_id, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(data["industry_id"]), data["title"].strip(),
            data.get("trend_type", "产业方向").strip(),
            data.get("region", "全国").strip() or "全国",
            data.get("direction_summary", "").strip(),
            data.get("employment_impact", "").strip(),
            data.get("affected_jobs", "").strip(),
            data.get("affected_majors", "").strip(),
            data.get("evidence_summary", "").strip(),
            data.get("limitation_note", "").strip(),
            _optional_int(data.get("source_id")), data.get("source_url", "").strip(),
            data.get("published_at", "").strip(), data.get("next_check_at", "").strip(),
            _optional_int(data.get("owner_user_id")),
            _optional_int(data.get("reviewer_user_id")), created_by,
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_industry_trends():
    return get_db().execute(
        """
        SELECT t.*, i.name AS industry_name, s.name AS source_name,
               s.url AS configured_source_url, owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name
        FROM industry_trends t
        JOIN industries i ON i.id = t.industry_id
        LEFT JOIN intelligence_sources s ON s.id = t.source_id
        LEFT JOIN users owner ON owner.id = t.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = t.reviewer_user_id
        ORDER BY CASE t.status WHEN '待审核' THEN 0 WHEN '草稿' THEN 1 ELSE 2 END,
                 t.updated_at DESC
        """
    ).fetchall()


def get_industry_trend(trend_id):
    return get_db().execute(
        """
        SELECT t.*, i.name AS industry_name, s.name AS source_name,
               s.url AS configured_source_url, owner.display_name AS owner_name,
               reviewer.display_name AS reviewer_name
        FROM industry_trends t
        JOIN industries i ON i.id = t.industry_id
        LEFT JOIN intelligence_sources s ON s.id = t.source_id
        LEFT JOIN users owner ON owner.id = t.owner_user_id
        LEFT JOIN users reviewer ON reviewer.id = t.reviewer_user_id
        WHERE t.id = ?
        """,
        (trend_id,),
    ).fetchone()


def update_industry_trend_status(trend_id, status):
    if status not in ("草稿", "待审核", "已发布", "已退回", "已过期"):
        raise ValueError("invalid trend status")
    db = get_db()
    db.execute(
        "UPDATE industry_trends SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, trend_id),
    )
    db.commit()


def list_published_jobs():
    return get_db().execute(
        "SELECT * FROM knowledge_jobs WHERE status = '已发布' ORDER BY industry_name, name"
    ).fetchall()


def list_published_skills():
    return get_db().execute(
        "SELECT * FROM knowledge_skills WHERE status = '已发布' ORDER BY skill_type, name"
    ).fetchall()


def upsert_student_job_target(student_id, data, created_by=None):
    db = get_db()
    db.execute(
        """
        INSERT INTO student_job_targets (
            student_id, job_id, priority, target_note, created_by
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(student_id, job_id) DO UPDATE SET
            priority = excluded.priority, target_note = excluded.target_note,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            student_id, int(data["job_id"]), int(data.get("priority", 1)),
            data.get("target_note", "").strip(), created_by,
        ),
    )
    db.commit()


def list_student_job_targets(student_id):
    return get_db().execute(
        """
        SELECT t.*, j.name AS job_name, j.industry_name, j.job_family,
               j.development_direction, j.status AS job_status
        FROM student_job_targets t
        JOIN knowledge_jobs j ON j.id = t.job_id
        WHERE t.student_id = ? ORDER BY t.priority, j.name
        """,
        (student_id,),
    ).fetchall()


def upsert_student_skill_assessment(student_id, data, assessed_by=None):
    level = int(data.get("current_level", 0))
    if level < 0 or level > 4:
        raise ValueError("invalid skill level")
    db = get_db()
    db.execute(
        """
        INSERT INTO student_skill_assessments (
            student_id, skill_id, current_level, evidence_note, assessed_by
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(student_id, skill_id) DO UPDATE SET
            current_level = excluded.current_level,
            evidence_note = excluded.evidence_note,
            assessed_by = excluded.assessed_by,
            assessed_at = CURRENT_TIMESTAMP
        """,
        (
            student_id, int(data["skill_id"]), level,
            data.get("evidence_note", "").strip(), assessed_by,
        ),
    )
    db.commit()


def list_student_skill_assessments(student_id):
    return get_db().execute(
        """
        SELECT a.*, s.name AS skill_name, s.skill_type, s.status AS skill_status,
               u.display_name AS assessor_name
        FROM student_skill_assessments a
        JOIN knowledge_skills s ON s.id = a.skill_id
        LEFT JOIN users u ON u.id = a.assessed_by
        WHERE a.student_id = ? ORDER BY s.skill_type, s.name
        """,
        (student_id,),
    ).fetchall()


def list_student_candidate_jobs(student_id, student_major):
    return get_db().execute(
        """
        SELECT DISTINCT j.*,
               t.priority,
               CASE WHEN t.job_id IS NOT NULL THEN '目标岗位' ELSE '专业关联' END AS path_source
        FROM knowledge_jobs j
        LEFT JOIN student_job_targets t
          ON t.job_id = j.id AND t.student_id = ?
        LEFT JOIN major_job_links mj ON mj.job_id = j.id
        LEFT JOIN knowledge_majors m ON m.id = mj.major_id AND m.status = '已发布'
        WHERE j.status = '已发布'
          AND (t.job_id IS NOT NULL OR m.name = ? OR ? LIKE '%' || m.name || '%')
        ORDER BY COALESCE(t.priority, 9), j.name
        """,
        (student_id, student_major, student_major),
    ).fetchall()


def list_job_skill_requirements(job_id):
    return get_db().execute(
        """
        SELECT js.*, s.name AS skill_name, s.skill_type
        FROM job_skill_links js
        JOIN knowledge_skills s ON s.id = js.skill_id
        LEFT JOIN intelligence_sources source ON source.id = js.source_id
        JOIN users owner ON owner.id = js.owner_user_id
        JOIN users reviewer ON reviewer.id = js.reviewer_user_id
        WHERE js.job_id = ? AND s.status = '已发布'
          AND js.status = '已发布'
          AND TRIM(
              js.evidence_note,
              char(9, 10, 11, 12, 13, 28, 29, 30, 31, 32, 133, 160, 5760, 8192, 8193,
                   8194, 8195, 8196, 8197, 8198, 8199, 8200, 8201, 8202,
                   8232, 8233, 8239, 8287, 12288)
          ) != ''
          AND (
              (js.source_id IS NOT NULL AND source.id IS NOT NULL)
              OR (
                  js.source_id IS NULL
                  AND TRIM(
                      js.source_url,
                      char(9, 10, 11, 12, 13, 28, 29, 30, 31, 32, 133, 160, 5760, 8192,
                           8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200,
                           8201, 8202, 8232, 8233, 8239, 8287, 12288)
                  ) != ''
              )
          )
          AND js.confidence_level IN ('低', '中', '高')
          AND typeof(js.sample_size) = 'integer'
          AND js.sample_size >= 0
          AND date(js.last_verified_at) = js.last_verified_at
          AND date(js.next_check_at) = js.next_check_at
          AND substr(js.last_verified_at, 1, 4) BETWEEN '0001' AND '9999'
          AND substr(js.next_check_at, 1, 4) BETWEEN '0001' AND '9999'
          AND date(js.next_check_at) >= date(js.last_verified_at)
          AND date(js.next_check_at) >= date('now')
          AND TRIM(
              js.limitation_note,
              char(9, 10, 11, 12, 13, 28, 29, 30, 31, 32, 133, 160, 5760, 8192, 8193,
                   8194, 8195, 8196, 8197, 8198, 8199, 8200, 8201, 8202,
                   8232, 8233, 8239, 8287, 12288)
          ) != ''
        ORDER BY CASE js.importance_level WHEN '核心' THEN 0 WHEN '重要' THEN 1 ELSE 2 END,
                 s.name
        """,
        (job_id,),
    ).fetchall()


def list_published_industry_trends():
    return get_db().execute(
        """
        SELECT t.*, i.name AS industry_name, s.name AS source_name,
               s.url AS configured_source_url
        FROM industry_trends t
        JOIN industries i ON i.id = t.industry_id
        LEFT JOIN intelligence_sources s ON s.id = t.source_id
        WHERE t.status = '已发布' AND i.status = '已发布'
          AND date(t.next_check_at) >= date('now')
          AND t.evidence_summary != '' AND t.limitation_note != ''
          AND t.reviewer_user_id IS NOT NULL
          AND (t.source_id IS NOT NULL OR t.source_url != '')
        ORDER BY t.published_at DESC, t.updated_at DESC
        """
    ).fetchall()


def list_published_exams():
    return get_db().execute(
        """
        SELECT * FROM exam_information
        WHERE status = '已发布'
        ORDER BY exam_date, exam_name
        """
    ).fetchall()


def upsert_student_exam_plan(student_id, data, created_by=None):
    priority = int(data.get("priority", 1))
    if priority not in (1, 2, 3):
        raise ValueError("invalid exam priority")
    db = get_db()
    db.execute(
        """
        INSERT INTO student_exam_plans (
            student_id, exam_id, purpose, priority, preparation_status,
            personal_deadline, next_action, owner_user_id, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id, exam_id) DO UPDATE SET
            purpose = excluded.purpose, priority = excluded.priority,
            preparation_status = excluded.preparation_status,
            personal_deadline = excluded.personal_deadline,
            next_action = excluded.next_action,
            owner_user_id = excluded.owner_user_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            student_id, int(data["exam_id"]), data.get("purpose", "").strip(),
            priority, data.get("preparation_status", "未开始").strip() or "未开始",
            data.get("personal_deadline", "").strip(),
            data.get("next_action", "").strip(),
            _optional_int(data.get("owner_user_id")), created_by,
        ),
    )
    db.commit()


def list_student_exam_plans(student_id):
    return get_db().execute(
        """
        SELECT p.*, e.exam_name, e.category, e.region, e.official_url,
               e.registration_start, e.registration_end, e.exam_date,
               e.summary, e.source_name, e.next_check_at, e.limitation_note,
               e.collector_user_id, e.reviewer_user_id, e.execution_owner_user_id,
               e.status AS exam_status,
               owner.display_name AS owner_name
        FROM student_exam_plans p
        JOIN exam_information e ON e.id = p.exam_id
        LEFT JOIN users owner ON owner.id = p.owner_user_id
        WHERE p.student_id = ?
        ORDER BY p.priority, e.exam_date, e.exam_name
        """,
        (student_id,),
    ).fetchall()
