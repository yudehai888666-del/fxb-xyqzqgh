from app.db import get_db


def get_profile(student_id):
    return get_db().execute(
        "SELECT * FROM student_goal_profiles WHERE student_id = ?", (student_id,)
    ).fetchone()


def insert_profile(student_id, primary_goal, alternate_goal, reason, actor_id):
    get_db().execute(
        """INSERT INTO student_goal_profiles
           (student_id, primary_goal, alternate_goal, decision_reason, confirmed_by)
           VALUES (?, ?, ?, ?, ?)""",
        (student_id, primary_goal, alternate_goal, reason, actor_id),
    )


def update_profile(student_id, primary_goal, alternate_goal, reason):
    get_db().execute(
        """UPDATE student_goal_profiles
           SET primary_goal = ?, alternate_goal = ?, decision_reason = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE student_id = ?""",
        (primary_goal, alternate_goal, reason, student_id),
    )


def insert_change(student_id, change_type, old_profile, primary_goal,
                  alternate_goal, reason, replanning_id, actor_id):
    get_db().execute(
        """INSERT INTO student_goal_changes
           (student_id, change_type, from_primary_goal, to_primary_goal,
            from_alternate_goal, to_alternate_goal, change_reason,
            replanning_id, changed_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            student_id, change_type,
            old_profile["primary_goal"] if old_profile else "", primary_goal,
            old_profile["alternate_goal"] if old_profile else "", alternate_goal,
            reason, replanning_id, actor_id,
        ),
    )
