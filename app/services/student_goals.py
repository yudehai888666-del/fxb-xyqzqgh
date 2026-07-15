from app import goal_repository, repositories
from app.db import get_db

VALID_GOALS = ("升学", "就业")


class GoalValidationError(ValueError):
    pass


def _validated(data):
    primary = data.get("primary_goal", "").strip()
    alternate = data.get("alternate_goal", "").strip()
    reason = data.get("decision_reason", "").strip()
    if primary not in VALID_GOALS:
        raise GoalValidationError("请选择升学或就业作为当前主目标")
    if alternate not in ("", *VALID_GOALS):
        raise GoalValidationError("备选方向无效")
    if alternate == primary:
        raise GoalValidationError("备选方向不能与主目标相同")
    if not reason:
        raise GoalValidationError("请填写目标确认理由")
    return primary, alternate, reason


def get_goal_profile(student_id):
    return goal_repository.get_profile(student_id)


def create_student_with_goal(student_data, goal_data, actor_id):
    primary, alternate, reason = _validated(goal_data)
    db = get_db()
    try:
        student_id = repositories.create_student(student_data, commit=False)
        goal_repository.insert_profile(student_id, primary, alternate, reason, actor_id)
        goal_repository.insert_change(
            student_id, "首次确认", None, primary, alternate, reason, None, actor_id
        )
        db.commit()
        return student_id
    except Exception:
        db.rollback()
        raise


def confirm_existing_goal(student_id, goal_data, actor_id):
    if goal_repository.get_profile(student_id) is not None:
        raise GoalValidationError("该学生已经确认主目标")
    primary, alternate, reason = _validated(goal_data)
    db = get_db()
    try:
        goal_repository.insert_profile(student_id, primary, alternate, reason, actor_id)
        goal_repository.insert_change(
            student_id, "首次确认", None, primary, alternate, reason, None, actor_id
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def change_goal(student_id, goal_data, replanning_id, actor_id):
    old = goal_repository.get_profile(student_id)
    case = repositories.get_replanning_case(replanning_id)
    if old is None:
        raise GoalValidationError("请先完成首次目标确认")
    if case is None or case["student_id"] != student_id or case["status"] != "已确认":
        raise GoalValidationError("重规划记录必须已确认")
    primary, alternate, reason = _validated(goal_data)
    if primary == old["primary_goal"] and alternate == old["alternate_goal"]:
        raise GoalValidationError("目标没有发生变化")
    db = get_db()
    try:
        goal_repository.update_profile(student_id, primary, alternate, reason)
        goal_repository.insert_change(
            student_id, "目标变更", old, primary, alternate, reason, replanning_id, actor_id
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def stage_two_endpoint(student_id):
    profile = get_goal_profile(student_id)
    if profile is None:
        return "goals.confirm", {"student_id": student_id}
    if profile["primary_goal"] == "升学":
        return "goals.advancement", {"student_id": student_id}
    return "employment.workspace", {"student_id": student_id}
