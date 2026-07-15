import pytest

from app import repositories
from app.db import get_db, init_db
from app.services import student_goals
from app import create_app
from werkzeug.security import generate_password_hash


STUDENT = {
    "name": "目标测试学生", "gender": "女", "enrollment_year": 2026,
    "current_term": "大二下", "school": "示例大学", "college": "商学院",
    "major": "经济学", "city": "上海", "phone": "",
    "service_stage": "信息收集", "responsible_teacher": "测试老师",
}


def test_create_student_with_goal_records_profile_and_initial_change(app):
    with app.app_context():
        student_id = student_goals.create_student_with_goal(
            STUDENT,
            {"primary_goal": "就业", "alternate_goal": "升学", "decision_reason": "大二开始准备就业"},
            actor_id=None,
        )
        profile = student_goals.get_goal_profile(student_id)
        changes = get_db().execute(
            "SELECT * FROM student_goal_changes WHERE student_id = ?", (student_id,)
        ).fetchall()
        assert profile["primary_goal"] == "就业"
        assert profile["alternate_goal"] == "升学"
        assert changes[0]["change_type"] == "首次确认"
        assert changes[0]["from_primary_goal"] == ""


def test_same_primary_and_alternate_goal_rolls_back_student_creation(app):
    with app.app_context(), pytest.raises(student_goals.GoalValidationError):
        student_goals.create_student_with_goal(
            STUDENT,
            {"primary_goal": "就业", "alternate_goal": "就业", "decision_reason": "重复"},
            actor_id=None,
        )
    with app.app_context():
        assert repositories.list_students() == []


def test_goal_change_requires_confirmed_replanning_case(app):
    with app.app_context():
        student_id = student_goals.create_student_with_goal(
            STUDENT, {"primary_goal": "就业", "alternate_goal": "", "decision_reason": "初始"}, None
        )
        case_id = repositories.create_replanning_case(student_id, {"original_goal": "就业", "new_primary_goal": "升学"})
        with pytest.raises(student_goals.GoalValidationError, match="重规划记录必须已确认"):
            student_goals.change_goal(
                student_id,
                {"primary_goal": "升学", "alternate_goal": "就业", "decision_reason": "准备考研"},
                case_id,
                None,
            )


def test_confirmed_replanning_changes_current_goal_and_preserves_history(app):
    with app.app_context():
        student_id = student_goals.create_student_with_goal(
            STUDENT, {"primary_goal": "就业", "alternate_goal": "", "decision_reason": "初始就业"}, None
        )
        case_id = repositories.create_replanning_case(
            student_id, {"original_goal": "就业", "new_primary_goal": "升学", "trigger_event": "学生确认考研"}
        )
        repositories.update_replanning_status(case_id, "已确认")
        student_goals.change_goal(
            student_id,
            {"primary_goal": "升学", "alternate_goal": "就业", "decision_reason": "正式切换考研"},
            case_id,
            None,
        )
        profile = student_goals.get_goal_profile(student_id)
        changes = get_db().execute(
            "SELECT * FROM student_goal_changes WHERE student_id = ? ORDER BY id", (student_id,)
        ).fetchall()
        assert profile["primary_goal"] == "升学"
        assert [row["change_type"] for row in changes] == ["首次确认", "目标变更"]
        assert changes[-1]["replanning_id"] == case_id


def test_goal_schema_initialization_is_idempotent(app):
    with app.app_context():
        init_db()
        init_db()
        tables = {row["name"] for row in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        assert {"student_goal_profiles", "student_goal_changes"} <= tables
