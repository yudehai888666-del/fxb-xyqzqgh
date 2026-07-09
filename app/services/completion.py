from app import repositories


STUDENT_QUESTIONNAIRE_FIELDS = (
    "adaptation_status",
    "academic_status",
    "weak_subjects",
    "tutoring_needs",
    "interests_strengths",
    "future_intentions",
    "motivation_status",
)

PARENT_QUESTIONNAIRE_FIELDS = (
    "family_resources",
    "target_priorities",
    "parent_observations",
    "current_concerns",
    "investment_willingness",
)

TEACHER_NOTES_FIELDS = (
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


def row_has_substantive_text(row, fields):
    if row is None:
        return False

    return any(str(row[field]).strip() for field in fields if row[field] is not None)


def get_student_completion(student_id):
    has_student_questionnaire = row_has_substantive_text(
        repositories.get_student_questionnaire(student_id),
        STUDENT_QUESTIONNAIRE_FIELDS,
    )
    has_parent_questionnaire = row_has_substantive_text(
        repositories.get_parent_questionnaire(student_id),
        PARENT_QUESTIONNAIRE_FIELDS,
    )
    has_materials = bool(repositories.list_materials(student_id))
    has_disclaimers = bool(repositories.list_disclaimers(student_id))
    has_teacher_notes = row_has_substantive_text(
        repositories.get_teacher_notes(student_id),
        TEACHER_NOTES_FIELDS,
    )

    return {
        "student_questionnaire": "已填写" if has_student_questionnaire else "未填写",
        "parent_questionnaire": "已填写" if has_parent_questionnaire else "未填写",
        "materials": "已上传材料" if has_materials else "未上传材料",
        "disclaimer": "已确认免责" if has_disclaimers else "未确认免责",
        "teacher_notes": "已填写" if has_teacher_notes else "未填写",
        "ready_for_ai": (
            has_student_questionnaire
            and has_parent_questionnaire
            and has_teacher_notes
            and (has_materials or has_disclaimers)
        ),
    }
