from app import repositories


def get_student_completion(student_id):
    has_student_questionnaire = repositories.get_student_questionnaire(student_id) is not None
    has_parent_questionnaire = repositories.get_parent_questionnaire(student_id) is not None
    has_materials = bool(repositories.list_materials(student_id))
    has_disclaimers = bool(repositories.list_disclaimers(student_id))
    has_teacher_notes = repositories.get_teacher_notes(student_id) is not None

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
