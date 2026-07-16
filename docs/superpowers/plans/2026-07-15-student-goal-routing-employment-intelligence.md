# Student Goal Routing and Employment Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add goal-based student routing and deliver a versioned, evidence-governed employment intelligence workspace for employment-oriented students without disturbing the existing six-stage workflow.

**Architecture:** Keep student identity, permissions, questionnaires, files, planning, and replanning shared. Add a small goal-routing domain, a focused employment repository/service pair, and an immutable intelligence-report snapshot service; route advancement students to a separate guided skeleton and employment students to a six-tab workspace. Store operational data in normalized SQLite tables and freeze confirmed student reports as immutable JSON.

**Tech Stack:** Python 3, Flask, SQLite, Jinja, native CSS/JavaScript, pytest, existing Word/PDF export stack.

## Global Constraints

- Work from `/Users/yu/Desktop/学业规划`; never reset, clean, or overwrite the existing dirty worktree.
- Before implementation, use `using-git-worktrees` to create an isolated `codex/` worktree that contains a non-destructive snapshot of the current working files.
- The current verification baseline is `.venv/bin/python -m pytest -q` → `85 passed`.
- Preserve the stage order: information collection → target and intelligence → diagnostic interview → planning → execution review → replanning.
- New students require one primary goal: `升学` or `就业`; the optional alternate goal must differ from the primary goal.
- This increment creates only records classified as `测试数据`; it does not integrate real official sources or scrape commercial recruitment sites.
- Test-data reports remain teacher-internal and cannot be exported as real business reports.
- Preserve `/students/<id>/intelligence-report` as a compatibility route.
- Use the existing white-card, light-gray background, blue-button, approximately 8px-radius design system.
- Do not add a charting dependency; use accessible HTML/CSS or lightweight SVG with table fallbacks.
- Add every new SQLite field to both `app/schema.sql` and the idempotent migration path in `app/db.py`.
- Use TDD: observe each targeted test fail before writing implementation code.
- Each commit command below assumes the isolated implementation worktree and stages only the listed task files.

---

## Execution Preflight

Use the `using-git-worktrees` skill before Task 1. In the isolated worktree:

```bash
git status --short --branch
.venv/bin/python -m pytest -q
```

Expected: the isolated snapshot contains the current application features, and the suite reports `85 passed` before new tests are added. If the count differs, stop and reconcile the snapshot instead of coding against an incomplete baseline.

## File and Responsibility Map

### New Python modules

- `app/goal_repository.py`: SQL access for current goal profiles and immutable goal changes.
- `app/services/student_goals.py`: goal validation, atomic creation/confirmation/change, and route selection.
- `app/employment_repository.py`: SQL access for governed job-skill links, market snapshots, analysis drafts, and student report records.
- `app/services/employment_analysis.py`: report-ready calculations, completeness checks, and chart data.
- `app/services/intelligence_reports.py`: transactional immutable snapshot generation, confirmation, and voiding.
- `app/routes/goals.py`: initial goal confirmation, goal change, stage-two dispatcher, and advancement skeleton.
- `app/routes/employment.py`: employment workspace tabs and student-level write endpoints.

### New templates

- `app/templates/goals/confirm.html`: initial goal confirmation for migrated students.
- `app/templates/advancement/overview.html`: advancement-path guided skeleton.
- `app/templates/employment/workspace.html`: shared employment workspace frame and tab navigation.
- `app/templates/employment/_targets.html`: target job form and current priorities.
- `app/templates/employment/_skills.html`: relationship graph, skill assessments, and gap chart.
- `app/templates/employment/_market.html`: market snapshot cards, distributions, evidence, and limitations.
- `app/templates/employment/_exams.html`: student exam plan reuse.
- `app/templates/employment/_analysis.html`: editable teacher analysis draft.
- `app/templates/employment/_reports.html`: version list, readiness checklist, and generation actions.
- `app/templates/employment/report_detail.html`: immutable version rendering and confirmation/void actions.
- `app/templates/intelligence/market_snapshots.html`: common-library market snapshot list.
- `app/templates/intelligence/market_snapshot_form.html`: governed test-snapshot entry form.

### New tests

- `tests/test_student_goals.py`: goal model, transaction, routes, permissions, and routing.
- `tests/employment_factories.py`: deterministic test-only builders shared by employment-domain tests.
- `tests/test_job_skill_governance.py`: job-skill evidence lifecycle.
- `tests/test_employment_market.py`: market snapshot lifecycle and chart breakdowns.
- `tests/test_employment_workspace.py`: six-tab workspace, current-goal write guard, and analysis calculations.
- `tests/test_intelligence_reports.py`: readiness checks, immutable versions, status changes, and permissions.
- `tests/test_planning_intelligence_reference.py`: confirmed report selection, fixed reference, visibility, and export restrictions.

### Existing files modified

- `app/schema.sql`, `app/db.py`: new tables, columns, indexes, and existing-database migration.
- `app/repositories.py`: add an optional commit flag to student creation and a report-reference field to planning-document creation.
- `app/routes/__init__.py`: register goal and employment blueprints.
- `app/routes/students.py`, `app/templates/students/new.html`, `app/templates/students/detail.html`: goal-aware student creation and stage-two entry.
- `app/routes/matching.py`: compatibility redirect while retaining existing POST aliases where needed.
- `app/routes/intelligence.py`, `app/templates/intelligence/knowledge.html`: governance and market-snapshot administration.
- `app/services/student_matching.py`: consume only governed, current job-skill relationships.
- `app/services/student_workflow.py`, `app/templates/students/_workspace_nav.html`: goal-aware stage-two URL and progress summary.
- `app/routes/planning.py`, `app/services/planning_generator.py`, `app/templates/planning/generate.html`, `app/templates/planning/detail.html`: explicit intelligence-report selection and frozen reference.
- `app/static/styles.css`: tab workspace, charts, evidence blocks, print, and narrow-screen rules.

---

### Task 1: Goal Domain, Schema, and Atomic Transactions

**Files:**
- Create: `app/goal_repository.py`
- Create: `app/services/student_goals.py`
- Create: `tests/test_student_goals.py`
- Modify: `app/schema.sql`
- Modify: `app/db.py`
- Modify: `app/repositories.py`

**Interfaces:**
- Produces: `student_goals.create_student_with_goal(student_data, goal_data, actor_id) -> int`
- Produces: `student_goals.confirm_existing_goal(student_id, goal_data, actor_id) -> None`
- Produces: `student_goals.change_goal(student_id, goal_data, replanning_id, actor_id) -> None`
- Produces: `student_goals.get_goal_profile(student_id) -> sqlite3.Row | None`
- Produces: `student_goals.stage_two_endpoint(student_id) -> tuple[str, dict]`

- [ ] **Step 1: Write failing domain tests**

Add these tests to `tests/test_student_goals.py`:

```python
import pytest

from app import repositories
from app.db import get_db
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
```

- [ ] **Step 2: Run the new tests and observe failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_student_goals.py -q
```

Expected: collection fails because `app.services.student_goals` does not exist.

- [ ] **Step 3: Add exact schema objects and migrations**

Add to `app/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS student_goal_profiles (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    primary_goal TEXT NOT NULL CHECK(primary_goal IN ('升学', '就业')),
    alternate_goal TEXT NOT NULL DEFAULT '' CHECK(alternate_goal IN ('', '升学', '就业')),
    decision_reason TEXT NOT NULL,
    confirmed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(alternate_goal = '' OR alternate_goal != primary_goal)
);

CREATE TABLE IF NOT EXISTS student_goal_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL CHECK(change_type IN ('首次确认', '目标变更')),
    from_primary_goal TEXT NOT NULL DEFAULT '',
    to_primary_goal TEXT NOT NULL CHECK(to_primary_goal IN ('升学', '就业')),
    from_alternate_goal TEXT NOT NULL DEFAULT '',
    to_alternate_goal TEXT NOT NULL DEFAULT '',
    change_reason TEXT NOT NULL,
    replanning_id INTEGER REFERENCES replanning_cases(id) ON DELETE RESTRICT,
    changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_student_goal_changes_student
ON student_goal_changes(student_id, changed_at DESC, id DESC);
```

No `ALTER TABLE students` is required. `init_db()` already executes the full schema before `_run_lightweight_migrations`, so the new tables are idempotently created for existing databases. Add this migration assertion to `tests/test_student_goals.py`:

```python
from app.db import init_db


def test_goal_schema_initialization_is_idempotent(app):
    with app.app_context():
        init_db()
        init_db()
        tables = {row["name"] for row in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        assert {"student_goal_profiles", "student_goal_changes"} <= tables
```

- [ ] **Step 4: Implement repository and service transaction boundaries**

Modify `repositories.create_student` to accept `commit=True` and use this complete function body:

```python
def create_student(data, commit=True):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO students (
            name, gender, enrollment_year, current_term, school, college,
            major, city, phone, service_stage, responsible_teacher
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
```

Create `app/goal_repository.py` with these public functions:

```python
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
```

Create `app/services/student_goals.py` with validation and transaction logic:

```python
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
```

- [ ] **Step 5: Run goal-domain tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_student_goals.py -q
```

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add app/schema.sql app/db.py app/repositories.py app/goal_repository.py app/services/student_goals.py tests/test_student_goals.py
git commit -m "feat: add student goal domain"
```

---

### Task 2: Goal-Aware Student Intake, Routing, and Advancement Skeleton

**Files:**
- Create: `app/routes/goals.py`
- Create: `app/routes/employment.py`
- Create: `app/templates/goals/confirm.html`
- Create: `app/templates/advancement/overview.html`
- Modify: `app/routes/__init__.py`
- Modify: `app/routes/students.py`
- Modify: `app/routes/matching.py`
- Modify: `app/services/student_workflow.py`
- Modify: `app/templates/students/new.html`
- Modify: `app/templates/students/detail.html`
- Modify: `app/templates/students/_workspace_nav.html`
- Modify: `app/templates/replanning/list.html`
- Modify: `tests/test_student_goals.py`
- Modify: `tests/test_student_workflow.py`

**Interfaces:**
- Consumes: all `student_goals` functions from Task 1.
- Produces: endpoint `goals.stage_two` as the only template-facing stage-two dispatcher.
- Produces: `student_workflow["stage2_url"]` and goal-aware stage-two summary.

- [ ] **Step 1: Write failing route and permission tests**

Append to `tests/test_student_goals.py`:

```python
def test_new_student_requires_primary_goal(client):
    response = client.post("/students/new", data=STUDENT)
    assert response.status_code == 400
    assert "请选择升学或就业" in response.get_data(as_text=True)


def test_stage_two_dispatches_by_goal(client, app):
    with app.app_context():
        employment_id = student_goals.create_student_with_goal(
            STUDENT, {"primary_goal": "就业", "alternate_goal": "升学", "decision_reason": "就业准备"}, None
        )
        advancement_data = {**STUDENT, "name": "升学测试学生"}
        advancement_id = student_goals.create_student_with_goal(
            advancement_data, {"primary_goal": "升学", "alternate_goal": "", "decision_reason": "准备考研"}, None
        )
        undecided_id = repositories.create_student({**STUDENT, "name": "待确认学生"})
    assert client.get(f"/students/{employment_id}/stage-two").headers["Location"].endswith(f"/students/{employment_id}/employment")
    assert client.get(f"/students/{advancement_id}/stage-two").headers["Location"].endswith(f"/students/{advancement_id}/advancement")
    assert client.get(f"/students/{undecided_id}/stage-two").headers["Location"].endswith(f"/students/{undecided_id}/goals/confirm")


def test_old_intelligence_url_uses_stage_two_dispatcher(client, app):
    with app.app_context():
        student_id = repositories.create_student(STUDENT)
    response = client.get(f"/students/{student_id}/intelligence-report")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/students/{student_id}/stage-two")
```

Add these authenticated-test helpers and permission test in the same file:

```python
from werkzeug.security import generate_password_hash

from app import create_app


def make_auth_app(tmp_path):
    return create_app({
        "TESTING": True, "AUTH_DISABLED": False, "SECRET_KEY": "goal-test",
        "DATABASE": tmp_path / "goal.sqlite3",
        "UPLOAD_DIR": tmp_path / "uploads", "GENERATED_DIR": tmp_path / "generated",
        "BACKUP_DIR": tmp_path / "backups",
    })


def create_login_user(role, username):
    return repositories.create_user({
        "username": username, "display_name": username,
        "password_hash": generate_password_hash("password123", method="pbkdf2:sha256:600000"),
        "role": role,
    })


def login(client, username):
    return client.post("/login", data={"username": username, "password": "password123"})


def test_collaborator_cannot_confirm_or_change_goal_even_with_edit_access(tmp_path):
    auth_app = make_auth_app(tmp_path)
    client = auth_app.test_client()
    with auth_app.app_context():
        collaborator_id = create_login_user("collaborator", "collab")
        undecided_id = repositories.create_student(STUDENT)
        employment_id = student_goals.create_student_with_goal(
            {**STUDENT, "name": "已有目标学生"},
            {"primary_goal": "就业", "alternate_goal": "", "decision_reason": "初始就业"},
            actor_id=None,
        )
        repositories.assign_student_access(undecided_id, collaborator_id, "编辑")
        repositories.assign_student_access(employment_id, collaborator_id, "编辑")
    login(client, "collab")
    confirm = client.post(
        f"/students/{undecided_id}/goals/confirm",
        data={"primary_goal": "升学", "alternate_goal": "", "decision_reason": "准备考研"},
    )
    change = client.post(
        f"/students/{employment_id}/goals/change",
        data={"primary_goal": "升学", "alternate_goal": "就业", "decision_reason": "方向变化", "replanning_id": "1"},
    )
    assert confirm.status_code == 403
    assert change.status_code == 403
```

- [ ] **Step 2: Run the targeted tests and observe missing routes**

Run:

```bash
.venv/bin/python -m pytest tests/test_student_goals.py tests/test_student_workflow.py -q
```

Expected: failures for missing goal and employment endpoints and missing `stage2_url`.

- [ ] **Step 3: Implement the dispatcher, confirmation, and advancement routes**

Create `app/routes/goals.py`:

```python
from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from app import repositories
from app.auth import role_required
from app.services import student_goals

goals_bp = Blueprint("goals", __name__, url_prefix="/students/<int:student_id>")


def _student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@goals_bp.get("/stage-two")
def stage_two(student_id):
    _student(student_id)
    endpoint, values = student_goals.stage_two_endpoint(student_id)
    return redirect(url_for(endpoint, **values))


@goals_bp.route("/goals/confirm", methods=("GET", "POST"))
@role_required("admin", "teacher")
def confirm(student_id):
    student = _student(student_id)
    if student_goals.get_goal_profile(student_id) is not None:
        return redirect(url_for("goals.stage_two", student_id=student_id))
    if request.method == "POST":
        try:
            student_goals.confirm_existing_goal(student_id, request.form, g.current_user["id"])
        except student_goals.GoalValidationError as exc:
            return render_template("goals/confirm.html", student=student, form=request.form, error=str(exc)), 400
        repositories.create_audit_log(g.current_user["id"], "confirm_student_goal", "student", student_id)
        return redirect(url_for("goals.stage_two", student_id=student_id))
    return render_template("goals/confirm.html", student=student, form={}, error="")


@goals_bp.post("/goals/change")
@role_required("admin", "teacher")
def change(student_id):
    _student(student_id)
    try:
        replanning_id = int(request.form.get("replanning_id", ""))
        student_goals.change_goal(student_id, request.form, replanning_id, g.current_user["id"])
    except (ValueError, student_goals.GoalValidationError) as exc:
        return redirect(url_for("replanning.list_view", student_id=student_id, error=str(exc)))
    repositories.create_audit_log(g.current_user["id"], "change_student_goal", "student", student_id, f"replanning={replanning_id}")
    return redirect(url_for("goals.stage_two", student_id=student_id))


@goals_bp.get("/advancement")
def advancement(student_id):
    student = _student(student_id)
    profile = student_goals.get_goal_profile(student_id)
    if profile is None or profile["primary_goal"] != "升学":
        return redirect(url_for("goals.stage_two", student_id=student_id))
    return render_template(
        "advancement/overview.html", student=student, goal_profile=profile,
        student_questionnaire=repositories.get_student_questionnaire(student_id),
        parent_questionnaire=repositories.get_parent_questionnaire(student_id),
        teacher_notes=repositories.get_teacher_notes(student_id),
        exam_plans=repositories.list_student_exam_plans(student_id),
    )
```

Register `goals_bp` and `employment_bp` in `app/routes/__init__.py`. Create an interim `app/routes/employment.py` that keeps the existing report functional until Task 5 replaces its body:

```python
from flask import Blueprint, abort, g, render_template, request

from app import repositories
from app.services.student_matching import build_student_intelligence_report

employment_bp = Blueprint("employment", __name__, url_prefix="/students/<int:student_id>/employment")


@employment_bp.get("")
def workspace(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return render_template(
        "matching/report.html",
        report=build_student_intelligence_report(student),
        available_jobs=repositories.list_published_jobs(),
        available_skills=repositories.list_published_skills(),
        available_exams=repositories.list_published_exams(),
        exam_plans=repositories.list_student_exam_plans(student_id),
        users=repositories.list_users() if g.current_user and g.current_user["role"] in ("admin", "teacher") else [],
        message=request.args.get("message", ""), error=request.args.get("error", ""),
    )
```

- [ ] **Step 4: Make student creation and navigation goal-aware**

In `app/routes/students.py`, replace direct creation with:

```python
try:
    student_id = student_goals.create_student_with_goal(
        request.form, request.form, g.current_user["id"] if g.get("current_user") else None
    )
except student_goals.GoalValidationError as exc:
    return render_template("students/new.html", error=str(exc), form=request.form), 400
```

Add these controls to `app/templates/students/new.html` inside `.form-grid`:

```html
<label><span>当前主目标</span><select name="primary_goal" required>
  <option value="">请选择</option>
  <option value="升学" {{ 'selected' if form.get('primary_goal') == '升学' else '' }}>升学</option>
  <option value="就业" {{ 'selected' if form.get('primary_goal') == '就业' else '' }}>就业</option>
</select></label>
<label><span>备选方向（可选）</span><select name="alternate_goal">
  <option value="">无</option>
  <option value="升学" {{ 'selected' if form.get('alternate_goal') == '升学' else '' }}>升学</option>
  <option value="就业" {{ 'selected' if form.get('alternate_goal') == '就业' else '' }}>就业</option>
</select></label>
<label class="span-2"><span>目标确认理由</span><textarea name="decision_reason" rows="3" required>{{ form.get('decision_reason', '') }}</textarea></label>
```

In `build_student_workflow`, add the goal profile and endpoint:

```python
goal_profile = student_goals.get_goal_profile(student_id)
stage2_url = f"/students/{student_id}/stage-two"
if goal_profile is None:
    stage2 = "in_progress" if stage1 == "completed" else "pending"
    stage2_summary = "主目标待老师确认"
elif goal_profile["primary_goal"] == "就业":
    stage2_summary = f"就业路径 · {len(targets)}个岗位目标 · {len(skills)}项技能"
else:
    stage2_summary = "升学路径 · 专项模块待配置"
```

Return `stage2_url` and `goal_profile` in the workflow dictionary. Replace every hard-coded `matching.report` stage-two link in `students/detail.html` and `_workspace_nav.html` with `student_workflow.stage2_url`. Add `goals.`, `employment.`, and `matching.` to the stage-two active-endpoint condition.

Create the confirmation and advancement templates with the existing page heading, student workspace nav, white `.panel` cards, a clearly labeled primary/alternate goal, questionnaire intent summaries, and the exact copy `升学专项模块尚未配置`.

At the top of `app/templates/replanning/list.html`, render redirected goal-change failures:

```html
{% if request.args.get('error') %}<div class="form-error" role="alert">{{ request.args.get('error') }}</div>{% endif %}
```

For an `已确认` replanning case, render a goal-change form containing `replanning_id`, `primary_goal`, `alternate_goal`, and `decision_reason`; do not show it for draft, running, completed, or cancelled cases.

Change `matching.report` GET to:

```python
@matching_bp.get("/students/<int:student_id>/intelligence-report")
def report(student_id):
    _get_student_or_404(student_id)
    return redirect(url_for("goals.stage_two", student_id=student_id))
```

Keep the existing matching POST routes temporarily as compatibility aliases until Task 5 points their forms at the new employment endpoints.

- [ ] **Step 5: Run route and workflow tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_student_goals.py tests/test_student_workflow.py tests/test_routes_students.py tests/test_intelligence.py -q
```

Expected: all selected tests pass after updating old intelligence-route assertions to expect the compatibility redirect.

- [ ] **Step 6: Commit Task 2**

```bash
git add app/routes/goals.py app/routes/employment.py app/routes/__init__.py app/routes/students.py app/routes/matching.py app/services/student_workflow.py app/templates/goals app/templates/advancement app/templates/students/new.html app/templates/students/detail.html app/templates/students/_workspace_nav.html app/templates/replanning/list.html tests/test_student_goals.py tests/test_student_workflow.py tests/test_routes_students.py tests/test_intelligence.py
git commit -m "feat: route students by primary goal"
```

---

### Task 3: Governed Job-Skill Evidence Lifecycle

**Files:**
- Create: `tests/employment_factories.py`
- Create: `tests/test_job_skill_governance.py`
- Modify: `app/schema.sql`
- Modify: `app/db.py`
- Modify: `app/repositories.py`
- Modify: `app/routes/intelligence.py`
- Modify: `app/services/student_matching.py`
- Modify: `app/templates/intelligence/knowledge.html`
- Modify: `tests/test_intelligence.py`

**Interfaces:**
- Produces: `repositories.get_job_skill_link(link_id)`.
- Produces: `repositories.submit_job_skill_link(link_id)`.
- Produces: `repositories.review_job_skill_link(link_id, status)`.
- Changes: `repositories.list_job_skill_requirements(job_id)` returns only published, unexpired governed relationships.

- [ ] **Step 1: Write failing governance tests**

Create `tests/employment_factories.py`:

```python
from app import repositories


def create_user(username="evidence-admin", role="admin"):
    return repositories.create_user({
        "username": username, "display_name": username,
        "password_hash": "test-only-hash", "role": role,
    })


def create_source(actor_id):
    return repositories.create_intelligence_source(
        {"name": f"测试来源-{actor_id}", "url": f"https://example.test/source-{actor_id}"},
        actor_id,
    )


def create_published_job_and_skill(job_name="测试数据分析师", skill_name="测试SQL"):
    job_id = repositories.create_knowledge_job({"name": job_name, "industry_name": "测试产业"})
    skill_id = repositories.create_knowledge_skill({"name": skill_name, "skill_type": "工具技能"})
    repositories.update_knowledge_status("job", job_id, "已发布")
    repositories.update_knowledge_status("skill", skill_id, "已发布")
    return job_id, skill_id
```

Create `tests/test_job_skill_governance.py`:

```python
import pytest

from app import repositories
from app.db import get_db
from app.services.student_matching import build_student_intelligence_report
from tests.employment_factories import create_published_job_and_skill, create_source, create_user


def test_job_skill_link_requires_governance_before_submission(app):
    with app.app_context():
        actor_id = create_user()
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill()
        repositories.create_job_skill_link({"job_id": job_id, "skill_id": skill_id})
        link_id = get_db().execute(
            "SELECT id FROM job_skill_links WHERE job_id = ? AND skill_id = ?",
            (job_id, skill_id),
        ).fetchone()["id"]
        with pytest.raises(ValueError, match="提交前请补齐"):
            repositories.submit_job_skill_link(link_id)
        repositories.create_job_skill_link({
            "job_id": job_id, "skill_id": skill_id,
            "importance_level": "核心", "proficiency_level": "熟练",
            "source_id": source_id, "evidence_note": "测试岗位样本中频繁要求 SQL",
            "confidence_level": "中", "sample_size": 120,
            "last_verified_at": "2026-07-15", "next_check_at": "2026-10-15",
            "owner_user_id": actor_id, "reviewer_user_id": actor_id,
            "limitation_note": "测试样本，仅验证流程，不代表真实市场",
        }, actor_id)
        repositories.submit_job_skill_link(link_id)
        assert repositories.get_job_skill_link(link_id)["status"] == "待审核"


def test_only_published_governed_link_enters_student_report(app):
    with app.app_context():
        actor_id = create_user(username="report-admin")
        source_id = create_source(actor_id)
        job_id, skill_id = create_published_job_and_skill("测试经营分析师", "测试统计")
        student_id = repositories.create_student({
            "name": "证据过滤学生", "gender": "女", "enrollment_year": 2026,
            "current_term": "大二下", "school": "示例大学", "major": "经济学",
        })
        repositories.upsert_student_job_target(student_id, {"job_id": job_id, "priority": 1})
        repositories.create_job_skill_link({
            "job_id": job_id, "skill_id": skill_id, "source_id": source_id,
            "evidence_note": "测试证据", "confidence_level": "中", "sample_size": 30,
            "last_verified_at": "2026-07-15", "next_check_at": "2026-10-15",
            "owner_user_id": actor_id, "reviewer_user_id": actor_id,
            "limitation_note": "测试数据",
        }, actor_id)
        link_id = get_db().execute(
            "SELECT id FROM job_skill_links WHERE job_id = ? AND skill_id = ?", (job_id, skill_id)
        ).fetchone()["id"]
        assert build_student_intelligence_report(repositories.get_student(student_id))["jobs"][0]["skills"] == []
        repositories.submit_job_skill_link(link_id)
        repositories.review_job_skill_link(link_id, "已发布")
        assert build_student_intelligence_report(repositories.get_student(student_id))["jobs"][0]["skills"][0]["name"] == "测试统计"
```

- [ ] **Step 2: Run tests and observe governance failures**

```bash
.venv/bin/python -m pytest tests/test_job_skill_governance.py tests/test_intelligence.py -q
```

Expected: failures for missing columns and lifecycle functions.

- [ ] **Step 3: Add governed fields and idempotent column migration**

Add these columns to the `job_skill_links` definition in `app/schema.sql`:

```sql
source_id INTEGER REFERENCES intelligence_sources(id) ON DELETE SET NULL,
confidence_level TEXT NOT NULL DEFAULT '' CHECK(confidence_level IN ('', '低', '中', '高')),
sample_size INTEGER NOT NULL DEFAULT 0 CHECK(sample_size >= 0),
last_verified_at TEXT NOT NULL DEFAULT '',
next_check_at TEXT NOT NULL DEFAULT '',
owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
reviewer_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回', '已过期')),
limitation_note TEXT NOT NULL DEFAULT ''
```

In `app/db.py`, add a helper and call it once per new column:

```python
def _add_column_if_missing(db, table, column, definition):
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
```

Use SQLite-compatible migration definitions without `REFERENCES` or `CHECK` where ALTER limitations would make existing-data migration unsafe; enforce the same values in repository validation. Existing rows must receive `status='草稿'`.

- [ ] **Step 4: Implement submission, review, filtering, and UI fields**

Extend `create_job_skill_link` to write every governed field and reset an edited published link to `草稿`. Implement:

```python
def submit_job_skill_link(link_id):
    link = get_job_skill_link(link_id)
    if link is None:
        raise ValueError("岗位技能关系不存在")
    required = (
        link["evidence_note"], link["source_id"] or link["source_url"],
        link["confidence_level"], link["last_verified_at"], link["next_check_at"],
        link["owner_user_id"], link["reviewer_user_id"], link["limitation_note"],
    )
    if not all(required):
        raise ValueError("提交前请补齐证据、来源、置信度、责任人、复核日期和限制说明")
    get_db().execute("UPDATE job_skill_links SET status = '待审核' WHERE id = ?", (link_id,))
    get_db().commit()


def review_job_skill_link(link_id, status):
    if status not in ("已发布", "已退回", "已过期"):
        raise ValueError("invalid relationship status")
    get_db().execute("UPDATE job_skill_links SET status = ? WHERE id = ?", (status, link_id))
    get_db().commit()
```

Change `list_job_skill_requirements` to require `js.status = '已发布'` and `(js.next_check_at = '' OR js.next_check_at >= date('now'))`.

Add teacher/admin submit and admin-only review routes under `/knowledge/job-skill-links/<id>/submit` and `/review`. Extend the relationship form and graph table with the governed fields, source select, responsible users, status, and explicit test-data limitation copy.

- [ ] **Step 5: Run governance and matching tests**

```bash
.venv/bin/python -m pytest tests/test_job_skill_governance.py tests/test_intelligence.py -q
```

Expected: all tests pass; any old matching fixture now explicitly publishes its relationship.

- [ ] **Step 6: Commit Task 3**

```bash
git add app/schema.sql app/db.py app/repositories.py app/routes/intelligence.py app/services/student_matching.py app/templates/intelligence/knowledge.html tests/employment_factories.py tests/test_job_skill_governance.py tests/test_intelligence.py
git commit -m "feat: govern job skill evidence"
```

---

### Task 4: Employment Market Snapshot Library

**Files:**
- Create: `app/employment_repository.py`
- Create: `app/templates/intelligence/market_snapshots.html`
- Create: `app/templates/intelligence/market_snapshot_form.html`
- Create: `tests/test_employment_market.py`
- Modify: `tests/employment_factories.py`
- Modify: `app/schema.sql`
- Modify: `app/routes/intelligence.py`
- Modify: `app/templates/base.html`

**Interfaces:**
- Produces: `employment_repository.create_market_snapshot(data, breakdowns, actor_id) -> int`.
- Produces: `employment_repository.get_market_snapshot(snapshot_id)`.
- Produces: `employment_repository.list_market_snapshots(job_id=None)`.
- Produces: `employment_repository.list_current_market_snapshots(job_id)`.
- Produces: `employment_repository.submit_market_snapshot(snapshot_id)` and `review_market_snapshot(snapshot_id, status)`.

- [ ] **Step 1: Write failing snapshot and breakdown tests**

Add to `tests/employment_factories.py`:

```python
def create_market_prerequisites():
    actor_id = create_user(username="market-admin")
    source_id = create_source(actor_id)
    job_id, _ = create_published_job_and_skill("测试就业岗位", "测试市场技能")
    return actor_id, source_id, job_id
```

Create `tests/test_employment_market.py` with:

```python
from app import employment_repository
from tests.employment_factories import create_market_prerequisites


def test_market_snapshot_stores_governed_test_data_and_breakdowns(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        snapshot_id = employment_repository.create_market_snapshot(
            {
                "job_id": job_id, "region": "上海",
                "period_start": "2026-06-01", "period_end": "2026-06-30",
                "observed_posting_count": 150, "sample_size": 120,
                "salary_min": 8000, "salary_median": 12000, "salary_max": 18000,
                "currency": "CNY", "salary_period": "月",
                "source_id": source_id, "evidence_summary": "功能测试招聘市场摘要",
                "limitation_note": "合成测试样本，不代表真实招聘市场",
                "owner_user_id": actor_id, "reviewer_user_id": actor_id,
                "next_check_at": "2026-10-15", "data_classification": "测试数据",
            },
            [
                {"dimension_type": "学历", "label": "本科", "value": 72, "unit": "%", "sample_size": 120, "sort_order": 1},
                {"dimension_type": "热门技能", "label": "SQL", "value": 68, "unit": "%", "sample_size": 120, "sort_order": 1},
            ],
            actor_id=actor_id,
        )
        snapshot = employment_repository.get_market_snapshot(snapshot_id)
        assert snapshot["data_classification"] == "测试数据"
        assert [row["label"] for row in employment_repository.list_market_breakdowns(snapshot_id)] == ["本科", "SQL"]
```

Add these lifecycle tests in the same file:

```python
import pytest


def market_data(actor_id, source_id, job_id):
    return {
        "job_id": job_id, "region": "上海",
        "period_start": "2026-06-01", "period_end": "2026-06-30",
        "observed_posting_count": 150, "sample_size": 120,
        "salary_min": 8000, "salary_median": 12000, "salary_max": 18000,
        "currency": "CNY", "salary_period": "月", "source_id": source_id,
        "evidence_summary": "功能测试招聘市场摘要",
        "limitation_note": "合成测试样本，不代表真实招聘市场",
        "owner_user_id": actor_id, "reviewer_user_id": actor_id,
        "next_check_at": "2026-10-15", "data_classification": "测试数据",
    }


def test_market_submission_rejects_zero_sample_size(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        data = market_data(actor_id, source_id, job_id)
        data["sample_size"] = 0
        snapshot_id = employment_repository.create_market_snapshot(data, [], actor_id)
        with pytest.raises(ValueError, match="正样本量"):
            employment_repository.submit_market_snapshot(snapshot_id)


def test_published_market_snapshot_cannot_be_edited(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        data = market_data(actor_id, source_id, job_id)
        snapshot_id = employment_repository.create_market_snapshot(data, [], actor_id)
        employment_repository.submit_market_snapshot(snapshot_id)
        employment_repository.review_market_snapshot(snapshot_id, "已发布")
        with pytest.raises(ValueError, match="不可修改"):
            employment_repository.update_market_snapshot(snapshot_id, {**data, "region": "北京"}, [], actor_id)


def test_real_classification_is_locked_in_this_increment(app):
    with app.app_context():
        actor_id, source_id, job_id = create_market_prerequisites()
        data = market_data(actor_id, source_id, job_id)
        data["data_classification"] = "真实数据"
        with pytest.raises(ValueError, match="只能录入测试数据"):
            employment_repository.create_market_snapshot(data, [], actor_id)
```

- [ ] **Step 2: Run tests and observe missing repository failure**

```bash
.venv/bin/python -m pytest tests/test_employment_market.py -q
```

Expected: import fails for `app.employment_repository`.

- [ ] **Step 3: Add exact market tables**

Add to `app/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS employment_market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES knowledge_jobs(id) ON DELETE CASCADE,
    region TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    observed_posting_count INTEGER NOT NULL CHECK(observed_posting_count >= 0),
    sample_size INTEGER NOT NULL CHECK(sample_size >= 0),
    salary_min INTEGER,
    salary_median INTEGER,
    salary_max INTEGER,
    currency TEXT NOT NULL DEFAULT 'CNY',
    salary_period TEXT NOT NULL DEFAULT '月',
    source_id INTEGER NOT NULL REFERENCES intelligence_sources(id) ON DELETE RESTRICT,
    source_snapshot_id INTEGER REFERENCES intelligence_source_snapshots(id) ON DELETE SET NULL,
    evidence_summary TEXT NOT NULL,
    limitation_note TEXT NOT NULL,
    data_classification TEXT NOT NULL DEFAULT '测试数据' CHECK(data_classification IN ('测试数据', '真实数据')),
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reviewer_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT '草稿' CHECK(status IN ('草稿', '待审核', '已发布', '已退回', '已过期')),
    next_check_at TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employment_market_breakdowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES employment_market_snapshots(id) ON DELETE CASCADE,
    dimension_type TEXT NOT NULL CHECK(dimension_type IN ('学历', '经验', '热门技能', '地区')),
    label TEXT NOT NULL,
    value REAL NOT NULL CHECK(value >= 0),
    unit TEXT NOT NULL DEFAULT '%',
    sample_size INTEGER NOT NULL DEFAULT 0 CHECK(sample_size >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(snapshot_id, dimension_type, label)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshot_job_status
ON employment_market_snapshots(job_id, status, period_end DESC);
```

- [ ] **Step 4: Implement repository lifecycle and administration pages**

In `app/employment_repository.py`, use this transaction pattern; add the corresponding SELECT list/get functions using the same column names:

```python
from app.db import get_db

BREAKDOWN_TYPES = ("学历", "经验", "热门技能", "地区")


def _market_values(data):
    if data.get("data_classification", "测试数据") != "测试数据":
        raise ValueError("本阶段只能录入测试数据")
    if not data.get("period_start") or not data.get("period_end") or data["period_start"] > data["period_end"]:
        raise ValueError("统计周期无效")
    salaries = [int(data[key]) for key in ("salary_min", "salary_median", "salary_max") if data.get(key) not in (None, "")]
    if salaries and salaries != sorted(salaries):
        raise ValueError("薪资最低值、中位值和最高值顺序无效")
    return (
        int(data["job_id"]), data["region"].strip(), data["period_start"], data["period_end"],
        int(data.get("observed_posting_count", 0)), int(data.get("sample_size", 0)),
        int(data["salary_min"]) if data.get("salary_min") else None,
        int(data["salary_median"]) if data.get("salary_median") else None,
        int(data["salary_max"]) if data.get("salary_max") else None,
        data.get("currency", "CNY"), data.get("salary_period", "月"),
        int(data["source_id"]), int(data["source_snapshot_id"]) if data.get("source_snapshot_id") else None,
        data.get("evidence_summary", "").strip(), data.get("limitation_note", "").strip(),
        "测试数据", int(data["owner_user_id"]), int(data["reviewer_user_id"]),
        data.get("next_check_at", "").strip(),
    )


def create_market_snapshot(data, breakdowns, actor_id):
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO employment_market_snapshots
               (job_id, region, period_start, period_end, observed_posting_count,
                sample_size, salary_min, salary_median, salary_max, currency,
                salary_period, source_id, source_snapshot_id, evidence_summary,
                limitation_note, data_classification, owner_user_id,
                reviewer_user_id, next_check_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*_market_values(data), actor_id),
        )
        snapshot_id = cursor.lastrowid
        for row in breakdowns:
            if row["dimension_type"] not in BREAKDOWN_TYPES or not row["label"].strip():
                raise ValueError("市场分布维度无效")
            db.execute(
                """INSERT INTO employment_market_breakdowns
                   (snapshot_id, dimension_type, label, value, unit, sample_size, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (snapshot_id, row["dimension_type"], row["label"].strip(),
                 float(row["value"]), row.get("unit", "%"),
                 int(row.get("sample_size", 0)), int(row.get("sort_order", 0))),
            )
        db.commit()
        return snapshot_id
    except Exception:
        db.rollback()
        raise


def submit_market_snapshot(snapshot_id):
    row = get_market_snapshot(snapshot_id)
    if row is None:
        raise ValueError("市场快照不存在")
    required = (row["sample_size"] > 0, row["source_id"], row["evidence_summary"],
                row["limitation_note"], row["owner_user_id"], row["reviewer_user_id"], row["next_check_at"])
    if not all(required):
        raise ValueError("提交前请补齐正样本量、来源、证据、责任人、复核日期和限制说明")
    db = get_db()
    db.execute("UPDATE employment_market_snapshots SET status = '待审核' WHERE id = ?", (snapshot_id,))
    db.commit()


def review_market_snapshot(snapshot_id, status):
    if status not in ("已发布", "已退回", "已过期"):
        raise ValueError("invalid market snapshot status")
    db = get_db()
    db.execute("UPDATE employment_market_snapshots SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, snapshot_id))
    db.commit()


def list_current_market_snapshots(job_id):
    return get_db().execute(
        """SELECT ms.*, j.name AS job_name, s.name AS source_name, s.url AS source_url,
                  owner.display_name AS owner_name, reviewer.display_name AS reviewer_name
           FROM employment_market_snapshots ms
           JOIN knowledge_jobs j ON j.id = ms.job_id
           JOIN intelligence_sources s ON s.id = ms.source_id
           JOIN users owner ON owner.id = ms.owner_user_id
           JOIN users reviewer ON reviewer.id = ms.reviewer_user_id
           WHERE ms.job_id = ? AND ms.status = '已发布'
             AND ms.sample_size > 0 AND ms.next_check_at >= date('now')
           ORDER BY ms.period_end DESC, ms.id DESC""",
        (job_id,),
    ).fetchall()
```

`update_market_snapshot` must call `get_market_snapshot` first and raise `ValueError("已发布市场快照不可修改")` unless status is `草稿` or `已退回`.

Add routes:

```text
GET|POST /employment-market
GET|POST /employment-market/<id>/edit
POST     /employment-market/<id>/submit
POST     /employment-market/<id>/review
```

Teacher/admin can create, edit, and submit. Only admin can review to `已发布`, `已退回`, or `已过期`. The form must render four breakdown groups as repeated rows named `breakdown_type`, `breakdown_label`, `breakdown_value`, `breakdown_unit`, and `breakdown_sample_size`; parse them with `request.form.getlist` and reject partially filled rows.

Use this exact parser in `app/routes/intelligence.py`:

```python
def _market_breakdowns(form):
    columns = [
        form.getlist("breakdown_type"), form.getlist("breakdown_label"),
        form.getlist("breakdown_value"), form.getlist("breakdown_unit"),
        form.getlist("breakdown_sample_size"),
    ]
    if len({len(column) for column in columns}) != 1:
        raise ValueError("市场分布行不完整")
    rows = []
    for index, values in enumerate(zip(*columns)):
        dimension, label, value, unit, sample_size = (item.strip() for item in values)
        if not any((dimension, label, value, unit, sample_size)):
            continue
        if not all((dimension, label, value)):
            raise ValueError("市场分布行不完整")
        rows.append({"dimension_type": dimension, "label": label, "value": float(value),
                     "unit": unit or "%", "sample_size": int(sample_size or 0), "sort_order": index})
    return rows
```

Add a simple “就业市场快照” link in the existing backend intelligence navigation, not in the global student workflow navigation.

- [ ] **Step 5: Run market lifecycle tests**

```bash
.venv/bin/python -m pytest tests/test_employment_market.py tests/test_intelligence.py -q
```

Expected: all tests pass, including role restrictions and published immutability.

- [ ] **Step 6: Commit Task 4**

```bash
git add app/schema.sql app/employment_repository.py app/routes/intelligence.py app/templates/intelligence/market_snapshots.html app/templates/intelligence/market_snapshot_form.html app/templates/base.html tests/employment_factories.py tests/test_employment_market.py tests/test_intelligence.py
git commit -m "feat: add governed employment market snapshots"
```

---

### Task 5: Six-Tab Employment Workspace and Current Analysis Draft

**Files:**
- Modify: `app/routes/employment.py`
- Create: `app/services/employment_analysis.py`
- Create: `app/templates/employment/workspace.html`
- Create: `app/templates/employment/_targets.html`
- Create: `app/templates/employment/_skills.html`
- Create: `app/templates/employment/_market.html`
- Create: `app/templates/employment/_exams.html`
- Create: `app/templates/employment/_analysis.html`
- Create: `app/templates/employment/_reports.html`
- Create: `tests/test_employment_workspace.py`
- Modify: `tests/employment_factories.py`
- Modify: `app/schema.sql`
- Modify: `app/db.py`
- Modify: `app/repositories.py`
- Modify: `app/employment_repository.py`
- Modify: `app/routes/__init__.py`
- Modify: `app/routes/matching.py`
- Modify: `app/services/student_matching.py`
- Modify: `app/static/styles.css`
- Modify: `app/templates/intelligence/exam_form.html`
- Modify: `app/templates/intelligence/industries.html`

**Interfaces:**
- Produces: `employment_analysis.build_workspace(student_id) -> dict`.
- Produces: `employment_analysis.require_active_employment_goal(student_id) -> sqlite3.Row`; raises `InactiveGoalPath`.
- Produces: `employment_analysis.report_readiness(student_id) -> {"ready": bool, "blocking": list[str], "warnings": list[str]}`.
- Produces: endpoint `employment.workspace(student_id)` with allowlisted `?tab=` values.

- [ ] **Step 1: Write failing workspace tests**

Extend `tests/employment_factories.py`:

```python
from app.db import get_db
from app.services import student_goals


def goal_student(app, primary_goal, name):
    with app.app_context():
        return student_goals.create_student_with_goal(
            {
                "name": name, "gender": "女", "enrollment_year": 2024,
                "current_term": "大二下", "school": "示例大学", "college": "商学院",
                "major": "经济学", "city": "上海", "responsible_teacher": "测试老师",
            },
            {"primary_goal": primary_goal, "alternate_goal": "升学" if primary_goal == "就业" else "就业",
             "decision_reason": "功能测试目标分流"},
            actor_id=None,
        )


def employment_student(app):
    return goal_student(app, "就业", "就业工作区学生")


def advancement_student(app):
    return goal_student(app, "升学", "升学工作区学生")


def configured_employment_student(app):
    with app.app_context():
        actor_id = create_user(username="workspace-admin")
        source_id = create_source(actor_id)
        job_id, published_skill_id = create_published_job_and_skill("测试经营分析师", "已审核技能")
        draft_skill_id = repositories.create_knowledge_skill({"name": "草稿技能", "skill_type": "工具技能"})
        repositories.update_knowledge_status("skill", draft_skill_id, "已发布")
        student_id = student_goals.create_student_with_goal(
            {
                "name": "完整就业工作区学生", "gender": "女", "enrollment_year": 2024,
                "current_term": "大二下", "school": "示例大学", "major": "经济学",
            },
            {"primary_goal": "就业", "alternate_goal": "升学", "decision_reason": "准备就业"},
            actor_id,
        )
        repositories.upsert_student_job_target(student_id, {"job_id": job_id, "priority": 1}, actor_id)
        common = {
            "job_id": job_id, "source_id": source_id, "evidence_note": "测试关系证据",
            "confidence_level": "中", "sample_size": 120,
            "last_verified_at": "2026-07-15", "next_check_at": "2026-10-15",
            "owner_user_id": actor_id, "reviewer_user_id": actor_id,
            "limitation_note": "测试数据，不代表真实市场",
        }
        repositories.create_job_skill_link({**common, "skill_id": published_skill_id}, actor_id)
        repositories.create_job_skill_link({**common, "skill_id": draft_skill_id}, actor_id)
        rows = get_db().execute(
            "SELECT id, skill_id FROM job_skill_links WHERE job_id = ?", (job_id,)
        ).fetchall()
        link_ids = {row["skill_id"]: row["id"] for row in rows}
        repositories.submit_job_skill_link(link_ids[published_skill_id])
        repositories.review_job_skill_link(link_ids[published_skill_id], "已发布")
        return student_id, link_ids[published_skill_id], link_ids[draft_skill_id]


def make_auth_app(tmp_path, name="employment-auth"):
    return create_app({
        "TESTING": True, "AUTH_DISABLED": False, "SECRET_KEY": "employment-test",
        "DATABASE": tmp_path / f"{name}.sqlite3",
        "UPLOAD_DIR": tmp_path / f"{name}-uploads",
        "GENERATED_DIR": tmp_path / f"{name}-generated",
        "BACKUP_DIR": tmp_path / f"{name}-backups",
    })


def create_login_user(role, username):
    return repositories.create_user({
        "username": username, "display_name": username,
        "password_hash": generate_password_hash("password123", method="pbkdf2:sha256:600000"),
        "role": role,
    })


def login(client, username):
    return client.post("/login", data={"username": username, "password": "password123"})
```

Create `tests/test_employment_workspace.py` with authenticated and auth-disabled cases:

```python
from app import employment_repository, repositories
from app.services import employment_analysis
from tests.employment_factories import (
    advancement_student, configured_employment_student, create_login_user,
    create_published_job_and_skill, employment_student, login, make_auth_app,
)


def test_employment_workspace_has_six_deep_linkable_tabs(client, app):
    student_id = employment_student(app)
    page = client.get(f"/students/{student_id}/employment?tab=market")
    text = page.get_data(as_text=True)
    assert page.status_code == 200
    for label in ("目标岗位", "技能差距", "市场情报", "证书与考试", "老师结论", "报告版本"):
        assert label in text
    assert 'aria-current="page"' in text


def test_advancement_student_cannot_write_employment_data(tmp_path):
    auth_app = make_auth_app(tmp_path)
    client = auth_app.test_client()
    with auth_app.app_context():
        create_login_user("admin", "admin")
    student_id = advancement_student(auth_app)
    login(client, "admin")
    response = client.post(
        f"/students/{student_id}/employment/analysis",
        data={"suitability_summary": "文本", "risk_summary": "文本", "action_recommendations": "文本", "limitation_note": "文本"},
    )
    assert response.status_code == 409


def test_skill_gap_uses_only_governed_requirements(client, app):
    student_id, published_link_id, draft_link_id = configured_employment_student(app)
    with app.app_context():
        workspace = employment_analysis.build_workspace(student_id)
    skill_names = [skill["name"] for job in workspace["jobs"] for skill in job["skills"]]
    assert "已审核技能" in skill_names
    assert "草稿技能" not in skill_names


def test_analysis_draft_persists_and_unknown_tab_is_404(tmp_path):
    auth_app = make_auth_app(tmp_path, "analysis-auth")
    client = auth_app.test_client()
    with auth_app.app_context():
        create_login_user("admin", "admin")
    student_id = employment_student(auth_app)
    login(client, "admin")
    saved = client.post(
        f"/students/{student_id}/employment/analysis",
        data={"suitability_summary": "适合原因", "risk_summary": "主要风险",
              "action_recommendations": "行动建议", "limitation_note": "测试数据限制"},
    )
    assert saved.status_code == 302
    with auth_app.app_context():
        assert employment_repository.get_analysis_draft(student_id)["risk_summary"] == "主要风险"
    assert client.get(f"/students/{student_id}/employment?tab=unknown").status_code == 404


def test_collaborator_cannot_write_employment_workspace(tmp_path):
    auth_app = make_auth_app(tmp_path, "collaborator-auth")
    client = auth_app.test_client()
    with auth_app.app_context():
        collaborator_id = create_login_user("collaborator", "collab")
    student_id = employment_student(auth_app)
    with auth_app.app_context():
        repositories.assign_student_access(student_id, collaborator_id, "编辑")
    login(client, "collab")
    response = client.post(
        f"/students/{student_id}/employment/analysis",
        data={"suitability_summary": "越权", "risk_summary": "越权",
              "action_recommendations": "越权", "limitation_note": "越权"},
    )
    assert response.status_code == 403
```

Add this validation/reuse test:

```python
def test_target_validation_and_existing_exam_plan_reuse(tmp_path):
    auth_app = make_auth_app(tmp_path, "target-exam-auth")
    client = auth_app.test_client()
    with auth_app.app_context():
        admin_id = create_login_user("admin", "admin")
        job_id, _ = create_published_job_and_skill("测试目标岗位", "测试目标技能")
        exam_id = repositories.create_exam_information(
            {"exam_name": "测试资格考试", "official_url": "https://example.test/exam",
             "reviewer_user_id": admin_id, "next_check_at": "2026-10-15"},
            admin_id,
        )
    student_id = employment_student(auth_app)
    login(client, "admin")
    assert client.post(
        f"/students/{student_id}/employment/targets",
        data={"job_id": job_id, "priority": 4},
    ).status_code == 400
    assert client.post(
        f"/students/{student_id}/employment/exams",
        data={"exam_id": exam_id, "priority": 1},
    ).status_code == 400
    with auth_app.app_context():
        repositories.update_exam_status(exam_id, "已发布")
    saved = client.post(
        f"/students/{student_id}/employment/exams",
        data={"exam_id": exam_id, "priority": 1, "purpose": "就业资格",
              "preparation_status": "准备中", "personal_deadline": "2026-09-01",
              "next_action": "完成报名", "owner_user_id": admin_id},
    )
    assert saved.status_code == 302
    assert "tab=exams" in saved.headers["Location"]
    assert "测试资格考试" in client.get(saved.headers["Location"]).get_data(as_text=True)
```

- [ ] **Step 2: Run tests and observe missing blueprint/service failures**

```bash
.venv/bin/python -m pytest tests/test_employment_workspace.py -q
```

Expected: import or endpoint failures.

- [ ] **Step 3: Add the current analysis draft table and repository functions**

Add to `app/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS student_employment_analysis_drafts (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    suitability_summary TEXT NOT NULL DEFAULT '',
    risk_summary TEXT NOT NULL DEFAULT '',
    action_recommendations TEXT NOT NULL DEFAULT '',
    limitation_note TEXT NOT NULL DEFAULT '',
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Add `get_analysis_draft(student_id)` and `upsert_analysis_draft(student_id, data, actor_id)` to `employment_repository.py`. Use one `INSERT ... ON CONFLICT(student_id) DO UPDATE` statement and update `updated_at`.

- [ ] **Step 4: Implement goal guard, workspace aggregation, and chart data**

Create `app/services/employment_analysis.py`:

```python
from app import employment_repository, repositories
from app.services import student_goals
from app.services.student_matching import build_student_intelligence_report


class InactiveGoalPath(RuntimeError):
    pass


def require_active_employment_goal(student_id):
    profile = student_goals.get_goal_profile(student_id)
    if profile is None or profile["primary_goal"] != "就业":
        raise InactiveGoalPath("该学生当前不在就业路径")
    return profile


def _breakdown_groups(snapshot):
    groups = {key: [] for key in ("学历", "经验", "热门技能", "地区")}
    for row in employment_repository.list_market_breakdowns(snapshot["id"]):
        groups[row["dimension_type"]].append(dict(row))
    for rows in groups.values():
        maximum = max((row["value"] for row in rows), default=0)
        for row in rows:
            row["bar_percent"] = round(row["value"] / maximum * 100) if maximum else 0
    return groups


def build_workspace(student_id):
    profile = require_active_employment_goal(student_id)
    student = repositories.get_student(student_id)
    matching = build_student_intelligence_report(student)
    targets = repositories.list_student_job_targets(student_id)
    target_ids = {row["job_id"] for row in targets}
    target_jobs = [row for row in matching["jobs"] if row["job"]["id"] in target_ids]
    snapshots = []
    for job_result in target_jobs:
        for snapshot in employment_repository.list_current_market_snapshots(job_result["job"]["id"]):
            snapshots.append({"record": snapshot, "breakdowns": _breakdown_groups(snapshot)})
    all_exam_plans = repositories.list_student_exam_plans(student_id)
    current_exam_plans = [
        row for row in all_exam_plans
        if row["exam_status"] == "已发布"
        and row["next_check_at"] >= date.today().isoformat()
        and row["official_url"] and row["reviewer_user_id"] and row["limitation_note"]
    ]
    return {
        "student": student,
        "goal_profile": profile,
        "targets": targets,
        "jobs": target_jobs,
        "trends": matching["trends"],
        "market_snapshots": snapshots,
        "exam_plans": current_exam_plans,
        "excluded_exam_plans": [row for row in all_exam_plans if row not in current_exam_plans],
        "analysis_draft": employment_repository.get_analysis_draft(student_id),
        "readiness": report_readiness(student_id),
    }


def report_readiness(student_id):
    require_active_employment_goal(student_id)
    blocking = []
    warnings = []
    targets = repositories.list_student_job_targets(student_id)
    primary = next((row for row in targets if row["priority"] == 1), None)
    if primary is None:
        blocking.append("请设置第一目标岗位")
    else:
        requirements = repositories.list_job_skill_requirements(primary["job_id"])
        if not requirements:
            blocking.append("第一目标缺少已审核且未过期的岗位技能关系")
        assessments = {row["skill_id"]: row for row in repositories.list_student_skill_assessments(student_id)}
        missing_core = [row["skill_name"] for row in requirements
                        if row["importance_level"] == "核心" and row["skill_id"] not in assessments]
        if missing_core:
            blocking.append("核心技能尚未评估：" + "、".join(missing_core))
        zero_without_note = [row["skill_name"] for row in requirements
                             if row["importance_level"] == "核心"
                             and row["skill_id"] in assessments
                             and assessments[row["skill_id"]]["current_level"] == 0
                             and not assessments[row["skill_id"]]["evidence_note"].strip()]
        if zero_without_note:
            blocking.append("零级核心技能必须明确记录无证据：" + "、".join(zero_without_note))
        if not employment_repository.list_current_market_snapshots(primary["job_id"]):
            blocking.append("第一目标缺少已审核且未过期的市场快照")
    draft = employment_repository.get_analysis_draft(student_id)
    for field, label in (
        ("suitability_summary", "适合原因"), ("risk_summary", "主要风险"),
        ("action_recommendations", "行动建议"), ("limitation_note", "限制说明"),
    ):
        if draft is None or not draft[field].strip():
            blocking.append(f"老师结论缺少{label}")
    for plan in repositories.list_student_exam_plans(student_id):
        if (plan["exam_status"] != "已发布"
                or plan["next_check_at"] < date.today().isoformat()
                or not plan["official_url"] or not plan["reviewer_user_id"]
                or not plan["limitation_note"]):
            warnings.append(f"考试信息不可引用：{plan['exam_name']}")
    for target in targets:
        if target["priority"] == 1:
            continue
        if not repositories.list_job_skill_requirements(target["job_id"]):
            warnings.append(f"第{target['priority']}目标缺少已审核技能关系")
        if not employment_repository.list_current_market_snapshots(target["job_id"]):
            warnings.append(f"第{target['priority']}目标缺少市场快照")
    return {"ready": not blocking, "blocking": blocking, "warnings": warnings}
```

Import `date` from `datetime`. Add `limitation_note TEXT NOT NULL DEFAULT ''` to both `exam_information` and `industry_trends` in `schema.sql`, use `_add_column_if_missing` for both existing tables, and include the field in their existing create/update repository field lists and forms.

Extend `repositories.list_student_exam_plans` to select `e.next_check_at`, `e.source_name`, `e.limitation_note`, and the collector/reviewer/execution-owner IDs. Change the trend query to this filter and update existing test fixtures with a limitation:

```sql
WHERE t.status = '已发布' AND i.status = '已发布'
  AND t.next_check_at >= date('now')
  AND t.evidence_summary != '' AND t.limitation_note != ''
  AND t.reviewer_user_id IS NOT NULL
  AND (t.source_id IS NOT NULL OR t.source_url != '')
```

In `report_readiness`, treat a selected exam with empty source, reviewer, future check date, or limitation as a warning and exclude it from `workspace["exam_plans"]`; only current governed exams and trends enter the frozen payload.

- [ ] **Step 5: Implement routes and split templates**

Register `employment_bp` and implement:

```text
GET  /students/<id>/employment?tab=targets|skills|market|exams|analysis|reports
POST /students/<id>/employment/targets
POST /students/<id>/employment/skills
POST /students/<id>/employment/exams
POST /students/<id>/employment/analysis
```

Every POST route must call `require_active_employment_goal` first, convert `InactiveGoalPath` to HTTP 409, use `@role_required('admin', 'teacher')`, and write an audit log. Reuse current target, assessment, and exam repository functions instead of duplicating SQL.

Use this route structure in `app/routes/employment.py`:

```python
TABS = {
    "targets": "employment/_targets.html", "skills": "employment/_skills.html",
    "market": "employment/_market.html", "exams": "employment/_exams.html",
    "analysis": "employment/_analysis.html", "reports": "employment/_reports.html",
}


def _guard(student_id):
    try:
        employment_analysis.require_active_employment_goal(student_id)
    except employment_analysis.InactiveGoalPath as exc:
        abort(409, description=str(exc))


@employment_bp.get("")
def workspace(student_id):
    _guard(student_id)
    tab = request.args.get("tab", "targets")
    if tab not in TABS:
        abort(404)
    return render_template(
        "employment/workspace.html", workspace=employment_analysis.build_workspace(student_id),
        active_tab=tab, active_partial=TABS[tab],
        available_jobs=repositories.list_published_jobs(),
        available_skills=repositories.list_published_skills(),
        available_exams=repositories.list_published_exams(), users=repositories.list_users(),
    )


@employment_bp.post("/targets")
@role_required("admin", "teacher")
def save_target(student_id):
    _guard(student_id)
    job_id = int(request.form.get("job_id", ""))
    priority = int(request.form.get("priority", ""))
    if priority not in (1, 2, 3) or job_id not in {row["id"] for row in repositories.list_published_jobs()}:
        abort(400)
    repositories.upsert_student_job_target(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(g.current_user["id"], "set_student_job_target", "student", student_id)
    return redirect(url_for("employment.workspace", student_id=student_id, tab="targets"))


@employment_bp.post("/skills")
@role_required("admin", "teacher")
def save_skill(student_id):
    _guard(student_id)
    skill_id = int(request.form.get("skill_id", ""))
    level = int(request.form.get("current_level", ""))
    if level not in range(5) or skill_id not in {row["id"] for row in repositories.list_published_skills()}:
        abort(400)
    repositories.upsert_student_skill_assessment(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(g.current_user["id"], "assess_student_skill", "student", student_id)
    return redirect(url_for("employment.workspace", student_id=student_id, tab="skills"))


@employment_bp.post("/exams")
@role_required("admin", "teacher")
def save_exam(student_id):
    _guard(student_id)
    exam_id = int(request.form.get("exam_id", ""))
    priority = int(request.form.get("priority", ""))
    if priority not in (1, 2, 3) or exam_id not in {row["id"] for row in repositories.list_published_exams()}:
        abort(400)
    repositories.upsert_student_exam_plan(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(g.current_user["id"], "set_student_exam_plan", "student", student_id)
    return redirect(url_for("employment.workspace", student_id=student_id, tab="exams"))


@employment_bp.post("/analysis")
@role_required("admin", "teacher")
def save_analysis(student_id):
    _guard(student_id)
    employment_repository.upsert_analysis_draft(student_id, request.form, g.current_user["id"])
    repositories.create_audit_log(g.current_user["id"], "update_employment_analysis", "student", student_id)
    return redirect(url_for("employment.workspace", student_id=student_id, tab="analysis"))
```

`workspace.html` must include exactly one partial based on an allowlisted `tab`; never construct a template path from unchecked user input. Each tab link uses `aria-current="page"` when active. The targets and exams forms move from `matching/report.html` into their partials. The skills tab includes the accessible gap bars and the underlying table. The reports partial initially renders readiness only; Task 6 adds version actions.

Replace the interim employment report body from Task 2. Point all rendered forms to `employment.*` endpoints. Preserve each legacy matching POST path for one release with a 307 redirect so the method and form body survive:

```python
return redirect(url_for("employment.save_target", student_id=student_id), code=307)
return redirect(url_for("employment.save_skill", student_id=student_id), code=307)
return redirect(url_for("employment.save_exam", student_id=student_id), code=307)
```

- [ ] **Step 6: Run workspace and regression tests**

```bash
.venv/bin/python -m pytest tests/test_employment_workspace.py tests/test_intelligence.py tests/test_student_goals.py tests/test_student_workflow.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 5**

```bash
git add app/schema.sql app/db.py app/repositories.py app/employment_repository.py app/routes/employment.py app/routes/__init__.py app/routes/matching.py app/services/employment_analysis.py app/services/student_matching.py app/templates/employment app/templates/intelligence/exam_form.html app/templates/intelligence/industries.html app/static/styles.css tests/employment_factories.py tests/test_employment_workspace.py tests/test_intelligence.py tests/test_student_goals.py tests/test_student_workflow.py
git commit -m "feat: add employment intelligence workspace"
```

---

### Task 6: Immutable Student Intelligence Report Versions

**Files:**
- Create: `app/services/intelligence_reports.py`
- Create: `app/templates/employment/report_detail.html`
- Create: `tests/test_intelligence_reports.py`
- Modify: `tests/employment_factories.py`
- Modify: `app/schema.sql`
- Modify: `app/employment_repository.py`
- Modify: `app/routes/employment.py`
- Modify: `app/templates/employment/_reports.html`
- Modify: `app/static/styles.css`
- Modify: `app/services/student_workflow.py`
- Modify: `tests/test_student_workflow.py`

**Interfaces:**
- Produces: `intelligence_reports.generate(student_id, actor_id) -> int`.
- Produces: `intelligence_reports.confirm(report_id, student_id, actor_id) -> None`.
- Produces: `intelligence_reports.void(report_id, student_id, reason, actor_id) -> None`.
- Produces: `employment_repository.get_intelligence_report(report_id)` and `list_intelligence_reports(student_id, goal_type)`.

- [ ] **Step 1: Write failing versioning and immutability tests**

Extend `tests/employment_factories.py`:

```python
from app import employment_repository


def complete_employment_student(app):
    student_id, published_link_id, _ = configured_employment_student(app)
    with app.app_context():
        actor = repositories.get_user_by_username("workspace-admin")
        link = repositories.get_job_skill_link(published_link_id)
        target = repositories.list_student_job_targets(student_id)[0]
        snapshot_id = employment_repository.create_market_snapshot(
            {
                "job_id": target["job_id"], "region": "上海",
                "period_start": "2026-06-01", "period_end": "2026-06-30",
                "observed_posting_count": 150, "sample_size": 120,
                "salary_min": 8000, "salary_median": 12000, "salary_max": 18000,
                "currency": "CNY", "salary_period": "月", "source_id": link["source_id"],
                "evidence_summary": "功能测试招聘摘要",
                "limitation_note": "测试数据，仅用于功能验证，不代表真实市场",
                "owner_user_id": actor["id"], "reviewer_user_id": actor["id"],
                "next_check_at": "2026-10-15", "data_classification": "测试数据",
            },
            [{"dimension_type": "热门技能", "label": "已审核技能", "value": 68,
              "unit": "%", "sample_size": 120, "sort_order": 1}],
            actor["id"],
        )
        employment_repository.submit_market_snapshot(snapshot_id)
        employment_repository.review_market_snapshot(snapshot_id, "已发布")
        repositories.upsert_student_skill_assessment(
            student_id,
            {"skill_id": link["skill_id"], "current_level": 2, "evidence_note": "课程项目证据"},
            actor["id"],
        )
        employment_repository.upsert_analysis_draft(
            student_id,
            {
                "suitability_summary": "专业基础与岗位相关",
                "risk_summary": "缺少真实项目经历",
                "action_recommendations": "优先完成 SQL 项目",
                "limitation_note": "全部市场数据为功能测试数据",
            },
            actor["id"],
        )
        return student_id, link["skill_id"]
```

Create `tests/test_intelligence_reports.py`:

```python
import json
import pytest

from app import employment_repository, repositories
from app.services import intelligence_reports
from tests.employment_factories import (
    complete_employment_student, create_login_user, employment_student,
    login, make_auth_app,
)


def test_report_generation_freezes_data_and_increments_versions(app):
    student_id, skill_id = complete_employment_student(app)
    with app.app_context():
        first_id = intelligence_reports.generate(student_id, actor_id=None)
        first_before = employment_repository.get_intelligence_report(first_id)["snapshot_json"]
        repositories.upsert_student_skill_assessment(
            student_id, {"skill_id": skill_id, "current_level": 4, "evidence_note": "更新后的证据"}
        )
        second_id = intelligence_reports.generate(student_id, actor_id=None)
        first_after = employment_repository.get_intelligence_report(first_id)["snapshot_json"]
        second = employment_repository.get_intelligence_report(second_id)
        assert first_before == first_after
        assert second["version"] == 2
        assert json.loads(first_before)["student"]["id"] == student_id


def test_generation_rolls_back_when_readiness_changes(app, monkeypatch):
    student_id, _ = complete_employment_student(app)
    monkeypatch.setattr(
        "app.services.intelligence_reports.employment_analysis.report_readiness",
        lambda student_id: {"ready": False, "blocking": ["第一目标缺少市场快照"], "warnings": []},
    )
    with app.app_context(), pytest.raises(intelligence_reports.ReportNotReady):
        intelligence_reports.generate(student_id, actor_id=None)
    with app.app_context():
        assert employment_repository.list_intelligence_reports(student_id, "就业") == []


def test_confirmation_and_voiding_change_status_without_changing_snapshot(app):
    student_id, _ = complete_employment_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=None)
        frozen = employment_repository.get_intelligence_report(report_id)["snapshot_json"]
        intelligence_reports.confirm(report_id, student_id, actor_id=None)
        assert employment_repository.get_intelligence_report(report_id)["status"] == "已确认"
        with pytest.raises(ValueError, match="作废原因不能为空"):
            intelligence_reports.void(report_id, student_id, "", actor_id=None)
        intelligence_reports.void(report_id, student_id, "依据需要重新审核", actor_id=None)
        report = employment_repository.get_intelligence_report(report_id)
        assert report["status"] == "已作废"
        assert report["snapshot_json"] == frozen


def test_report_detail_rejects_report_owned_by_another_student(client, app):
    student_id, _ = complete_employment_student(app)
    other_id = employment_student(app)
    with app.app_context():
        report_id = intelligence_reports.generate(student_id, actor_id=None)
    assert client.get(f"/students/{other_id}/employment/reports/{report_id}").status_code == 404


def test_collaborator_cannot_generate_report(tmp_path):
    auth_app = make_auth_app(tmp_path, "report-collaborator")
    client = auth_app.test_client()
    with auth_app.app_context():
        collaborator_id = create_login_user("collaborator", "collab")
    student_id, _ = complete_employment_student(auth_app)
    with auth_app.app_context():
        repositories.assign_student_access(student_id, collaborator_id, "编辑")
    login(client, "collab")
    assert client.post(f"/students/{student_id}/employment/reports").status_code == 403
```

- [ ] **Step 2: Run tests and observe missing report service**

```bash
.venv/bin/python -m pytest tests/test_intelligence_reports.py -q
```

Expected: import failure for `app.services.intelligence_reports`.

- [ ] **Step 3: Add the report table and repository queries**

Add to `app/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS student_intelligence_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    goal_type TEXT NOT NULL CHECK(goal_type IN ('升学', '就业')),
    version INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT '待确认' CHECK(status IN ('待确认', '已确认', '已作废')),
    data_classification TEXT NOT NULL CHECK(data_classification IN ('测试数据', '真实数据')),
    snapshot_json TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    confirmed_at TEXT,
    voided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    voided_at TEXT,
    void_reason TEXT NOT NULL DEFAULT '',
    UNIQUE(student_id, goal_type, version)
);

CREATE INDEX IF NOT EXISTS idx_student_intelligence_reports_student
ON student_intelligence_reports(student_id, goal_type, version DESC);
```

Add these repository functions; insertion intentionally does not commit because the service owns the `BEGIN IMMEDIATE` transaction:

```python
def next_report_version(student_id, goal_type):
    return get_db().execute(
        """SELECT COALESCE(MAX(version), 0) + 1
           FROM student_intelligence_reports WHERE student_id = ? AND goal_type = ?""",
        (student_id, goal_type),
    ).fetchone()[0]


def insert_intelligence_report(student_id, goal_type, version, classification, snapshot_json, actor_id):
    cursor = get_db().execute(
        """INSERT INTO student_intelligence_reports
           (student_id, goal_type, version, data_classification, snapshot_json, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (student_id, goal_type, version, classification, snapshot_json, actor_id),
    )
    return cursor.lastrowid


def set_report_confirmed(report_id, actor_id):
    db = get_db()
    db.execute(
        """UPDATE student_intelligence_reports
           SET status = '已确认', confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP
           WHERE id = ? AND status = '待确认'""",
        (actor_id, report_id),
    )
    db.commit()


def set_report_voided(report_id, reason, actor_id):
    db = get_db()
    db.execute(
        """UPDATE student_intelligence_reports
           SET status = '已作废', voided_by = ?, voided_at = CURRENT_TIMESTAMP, void_reason = ?
           WHERE id = ? AND status != '已作废'""",
        (actor_id, reason, report_id),
    )
    db.commit()
```

Do not expose any repository function that updates `snapshot_json`. List/get queries join creator, confirmer, and voider display names for the version UI.

- [ ] **Step 4: Implement deterministic snapshot generation**

Create `app/services/intelligence_reports.py` with:

```python
import json
from datetime import datetime, timezone
from dataclasses import asdict, is_dataclass

from app import employment_repository
from app.db import get_db
from app.services import employment_analysis


class ReportNotReady(ValueError):
    def __init__(self, blocking):
        self.blocking = blocking
        super().__init__("；".join(blocking))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def to_plain(value):
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if hasattr(value, "keys") and not isinstance(value, dict):
        return {key: to_plain(value[key]) for key in value.keys()}
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def _snapshot_payload(workspace, generated_at):
    return to_plain({
        "schema_version": 1,
        "calculation_version": "employment-match-v1",
        "generated_at": generated_at,
        "student": {"id": workspace["student"].id, "name": workspace["student"].name,
                    "school": workspace["student"].school, "major": workspace["student"].major},
        "goal_profile": dict(workspace["goal_profile"]),
        "targets": [dict(row) for row in workspace["targets"]],
        "jobs": workspace["jobs"],
        "market_snapshots": workspace["market_snapshots"],
        "trends": [dict(row) for row in workspace["trends"]],
        "exam_plans": [dict(row) for row in workspace["exam_plans"]],
        "teacher_analysis": dict(workspace["analysis_draft"]),
        "warnings": workspace["readiness"]["warnings"],
    })


def generate(student_id, actor_id):
    employment_analysis.require_active_employment_goal(student_id)
    readiness = employment_analysis.report_readiness(student_id)
    if not readiness["ready"]:
        raise ReportNotReady(readiness["blocking"])
    workspace = employment_analysis.build_workspace(student_id)
    payload = _snapshot_payload(workspace, utc_now())
    snapshot_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        version = employment_repository.next_report_version(student_id, "就业")
        report_id = employment_repository.insert_intelligence_report(
            student_id, "就业", version, "测试数据", snapshot_json, actor_id
        )
        db.commit()
        return report_id
    except Exception:
        db.rollback()
        raise


def confirm(report_id, student_id, actor_id):
    report = employment_repository.get_intelligence_report(report_id)
    if report is None or report["student_id"] != student_id:
        raise LookupError("报告不存在")
    if report["status"] != "待确认":
        raise ValueError("只有待确认报告可以确认")
    employment_repository.set_report_confirmed(report_id, actor_id)


def void(report_id, student_id, reason, actor_id):
    report = employment_repository.get_intelligence_report(report_id)
    reason = reason.strip()
    if report is None or report["student_id"] != student_id:
        raise LookupError("报告不存在")
    if report["status"] == "已作废" or not reason:
        raise ValueError("作废原因不能为空，且报告不能重复作废")
    employment_repository.set_report_voided(report_id, reason, actor_id)
```

Before serializing, convert every SQLite row and dataclass to plain dictionaries so JSON encoding never depends on Flask internals. In deterministic tests, monkeypatch `app.services.intelligence_reports.utc_now` to return `2026-07-15T00:00:00+00:00` rather than comparing wall-clock text.

Confirmation requires `status='待确认'`; voiding requires a nonempty reason and permits `待确认` or `已确认`. Both write audit logs in the route layer.

- [ ] **Step 5: Add report routes and immutable rendering**

Add:

```text
POST /students/<id>/employment/reports
GET  /students/<id>/employment/reports/<report_id>
POST /students/<id>/employment/reports/<report_id>/confirm
POST /students/<id>/employment/reports/<report_id>/void
```

Teacher/admin can generate and confirm. The detail GET remains readable after a goal switch, but POST confirmation/void requires the active employment goal. Render entirely from parsed `snapshot_json`; do not call live matching repositories to fill historical content.

Implement the route actions with explicit ownership checks:

```python
@employment_bp.post("/reports")
@role_required("admin", "teacher")
def generate_report(student_id):
    _guard(student_id)
    try:
        report_id = intelligence_reports.generate(student_id, g.current_user["id"])
    except intelligence_reports.ReportNotReady as exc:
        return redirect(url_for("employment.workspace", student_id=student_id, tab="reports", error=str(exc)))
    repositories.create_audit_log(g.current_user["id"], "generate_intelligence_report", "student", student_id, f"report={report_id}")
    return redirect(url_for("employment.report_detail", student_id=student_id, report_id=report_id))


@employment_bp.get("/reports/<int:report_id>")
def report_detail(student_id, report_id):
    report = employment_repository.get_intelligence_report(report_id)
    if report is None or report["student_id"] != student_id:
        abort(404)
    return render_template("employment/report_detail.html", report=report, snapshot=json.loads(report["snapshot_json"]))


@employment_bp.post("/reports/<int:report_id>/confirm")
@role_required("admin", "teacher")
def confirm_report(student_id, report_id):
    _guard(student_id)
    try:
        intelligence_reports.confirm(report_id, student_id, g.current_user["id"])
    except LookupError:
        abort(404)
    repositories.create_audit_log(g.current_user["id"], "confirm_intelligence_report", "student", student_id, f"report={report_id}")
    return redirect(url_for("employment.report_detail", student_id=student_id, report_id=report_id))


@employment_bp.post("/reports/<int:report_id>/void")
@role_required("admin", "teacher")
def void_report(student_id, report_id):
    _guard(student_id)
    try:
        intelligence_reports.void(report_id, student_id, request.form.get("void_reason", ""), g.current_user["id"])
    except LookupError:
        abort(404)
    except ValueError as exc:
        abort(400, description=str(exc))
    repositories.create_audit_log(g.current_user["id"], "void_intelligence_report", "student", student_id, f"report={report_id}")
    return redirect(url_for("employment.report_detail", student_id=student_id, report_id=report_id))
```

The reports tab displays readiness blocking items, warnings, version, status, classification, creator, and timestamps. The test-data banner must contain the exact text `测试数据，仅用于功能验证`.

Update `build_student_workflow` so an employment student's stage 2 is `completed` only when `list_confirmed_intelligence_reports(student_id, "就业")` returns at least one version. It is `in_progress` after the goal is confirmed but before report confirmation. Advancement remains `in_progress` in this increment because its specialized module is explicitly out of scope. Add to `tests/test_student_workflow.py`:

```python
from app.services import intelligence_reports
from tests.employment_factories import advancement_student, complete_employment_student


def test_employment_stage_two_completes_only_after_report_confirmation(app):
    student_id, _ = complete_employment_student(app)
    with app.test_request_context():
        assert build_student_workflow(student_id)["stages"][1]["status"] == "in_progress"
        report_id = intelligence_reports.generate(student_id, actor_id=None)
        intelligence_reports.confirm(report_id, student_id, actor_id=None)
        assert build_student_workflow(student_id)["stages"][1]["status"] == "completed"


def test_advancement_stage_two_stays_in_progress_until_specialized_module_exists(app):
    student_id = advancement_student(app)
    with app.test_request_context():
        assert build_student_workflow(student_id)["stages"][1]["status"] == "in_progress"
```

- [ ] **Step 6: Run report tests**

```bash
.venv/bin/python -m pytest tests/test_intelligence_reports.py tests/test_employment_workspace.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 6**

```bash
git add app/schema.sql app/employment_repository.py app/services/intelligence_reports.py app/services/student_workflow.py app/routes/employment.py app/templates/employment/_reports.html app/templates/employment/report_detail.html app/static/styles.css tests/employment_factories.py tests/test_intelligence_reports.py tests/test_employment_workspace.py tests/test_student_workflow.py
git commit -m "feat: freeze student intelligence report versions"
```

---

### Task 7: Planning Documents Reference Confirmed Intelligence Versions

**Files:**
- Create: `tests/test_planning_intelligence_reference.py`
- Modify: `tests/employment_factories.py`
- Modify: `app/schema.sql`
- Modify: `app/db.py`
- Modify: `app/repositories.py`
- Modify: `app/routes/planning.py`
- Modify: `app/services/planning_generator.py`
- Modify: `app/templates/planning/generate.html`
- Modify: `app/templates/planning/detail.html`
- Modify: `tests/test_planning_edit_export.py`
- Modify: `tests/test_planning_routes.py`

**Interfaces:**
- Changes: `repositories.create_planning_document(student_id, data)` accepts `intelligence_report_id`.
- Changes: `build_planning_context(student_id, intelligence_report_id=None)` includes parsed frozen intelligence under `employment_intelligence`.
- Produces: `employment_repository.list_confirmed_intelligence_reports(student_id, goal_type)`.

- [ ] **Step 1: Write failing reference and restriction tests**

Extend `tests/employment_factories.py`:

```python
from app.services import intelligence_reports


def confirmed_test_report(app):
    student_id, _ = complete_employment_student(app)
    with app.app_context():
        actor = repositories.get_user_by_username("workspace-admin")
        report_id = intelligence_reports.generate(student_id, actor["id"])
        intelligence_reports.confirm(report_id, student_id, actor["id"])
        return student_id, report_id


def create_and_confirm_second_report(student_id):
    actor = repositories.get_user_by_username("workspace-admin")
    report_id = intelligence_reports.generate(student_id, actor["id"])
    intelligence_reports.confirm(report_id, student_id, actor["id"])
    return report_id


def test_data_plan(app):
    student_id, report_id = confirmed_test_report(app)
    with app.app_context():
        document_id = repositories.create_planning_document(
            student_id,
            {"title": "测试就业规划", "content_markdown": "# 测试就业规划",
             "intelligence_report_id": report_id},
        )
        return student_id, report_id, document_id
```

Create `tests/test_planning_intelligence_reference.py`:

```python
from app import repositories
from tests.employment_factories import (
    confirmed_test_report, create_and_confirm_second_report, test_data_plan,
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
            {"title": "就业规划", "content_markdown": "# 就业规划", "intelligence_report_id": first_report_id},
        )
        create_and_confirm_second_report(student_id)
        assert repositories.get_planning_document(document_id)["intelligence_report_id"] == first_report_id


def test_test_data_plan_stays_internal_and_cannot_export(client, app):
    student_id, report_id, document_id = test_data_plan(app)
    visibility = client.post(
        f"/students/{student_id}/planning/documents/{document_id}/visibility",
        data={"visibility": "学生可见"},
    )
    export = client.post(f"/students/{student_id}/planning/documents/{document_id}/export/pdf")
    assert visibility.status_code == 409
    assert export.status_code == 409
```

- [ ] **Step 2: Run tests and observe missing reference column**

```bash
.venv/bin/python -m pytest tests/test_planning_intelligence_reference.py -q
```

Expected: failures for missing column and form behavior.

- [ ] **Step 3: Add the planning reference column and migration**

Add to `planning_documents` in `app/schema.sql`:

```sql
intelligence_report_id INTEGER REFERENCES student_intelligence_reports(id) ON DELETE RESTRICT,
```

Use `_add_column_if_missing` in `app/db.py`:

```python
_add_column_if_missing(
    db, "planning_documents", "intelligence_report_id",
    "INTEGER REFERENCES student_intelligence_reports(id) ON DELETE RESTRICT",
)
```

Do not backfill existing documents.

- [ ] **Step 4: Carry the selected frozen report through planning generation**

Update `create_planning_document` INSERT and values with `intelligence_report_id`. In `planning.generate`:

```python
goal_profile = student_goals.get_goal_profile(student_id)
confirmed_reports = employment_repository.list_confirmed_intelligence_reports(student_id, "就业")
selected_report_id = request.form.get("intelligence_report_id", "").strip()
if request.method == "POST" and goal_profile and goal_profile["primary_goal"] == "就业":
    allowed = {str(row["id"]): row for row in confirmed_reports}
    if selected_report_id not in allowed:
        return render_template(
            "planning/generate.html", student=student, completion=completion,
            documents=documents, confirmed_reports=confirmed_reports,
            error="请选择一个已确认的就业情报报告版本",
        ), 400
```

Pass the selected ID to both `build_planning_context` and `create_planning_document`. Parse the stored JSON and add an employment section to generated Markdown with target jobs, skill gaps, market evidence, teacher analysis, source limitations, report version, and the test-data warning. Never query live employment data while rendering this section.

Use this exact context boundary in `planning_generator.py`:

```python
import json
from app import employment_repository


def _frozen_employment_intelligence(student_id, report_id):
    if not report_id:
        return None
    report = employment_repository.get_intelligence_report(int(report_id))
    if report is None or report["student_id"] != student_id or report["status"] != "已确认":
        raise ValueError("就业情报报告无效或尚未确认")
    return {"report": dict(report), "snapshot": json.loads(report["snapshot_json"])}


def build_planning_context(student_id, intelligence_report_id=None):
    student = repositories.get_student(student_id)
    if student is None:
        raise ValueError("学生不存在")
    return {
        "student": student,
        "student_questionnaire": row_to_dict(repositories.get_student_questionnaire(student_id)),
        "parent_questionnaire": row_to_dict(repositories.get_parent_questionnaire(student_id)),
        "materials": [row_to_dict(row) for row in repositories.list_materials(student_id)],
        "disclaimers": [row_to_dict(row) for row in repositories.list_disclaimers(student_id)],
        "teacher_notes": row_to_dict(repositories.get_teacher_notes(student_id)),
        "employment_intelligence": _frozen_employment_intelligence(student_id, intelligence_report_id),
    }


def _employment_intelligence_section(value):
    if not value:
        return ""
    report = value["report"]
    snapshot = value["snapshot"]
    targets = "、".join(row["job_name"] for row in snapshot["targets"])
    analysis = snapshot["teacher_analysis"]
    lines = [
        "## 就业目标与职业情报依据",
        f"- 引用报告：V{report['version']}（{report['data_classification']}）",
        f"- 目标岗位：{targets or '未填写'}",
        f"- 适合原因：{analysis['suitability_summary']}",
        f"- 主要风险：{analysis['risk_summary']}",
        f"- 行动建议：{analysis['action_recommendations']}",
        f"- 数据局限：{analysis['limitation_note']}",
    ]
    if report["data_classification"] == "测试数据":
        lines.append("- 警告：测试数据，仅用于功能验证，不代表真实就业市场。")
    return "\n".join(lines)
```

Insert `_employment_intelligence_section(context["employment_intelligence"])` immediately after the information-basis section in `generate_initial_plan`, omitting the empty string for advancement or legacy plans.

Edits create a new planning version carrying the original `intelligence_report_id` unless the user returns to generation and explicitly selects another confirmed report.

- [ ] **Step 5: Enforce teacher-internal visibility and export restrictions**

Add a helper in `planning.py`:

```python
def _uses_test_intelligence(document):
    report_id = document["intelligence_report_id"]
    if not report_id:
        return False
    report = employment_repository.get_intelligence_report(report_id)
    return report is not None and report["data_classification"] == "测试数据"
```

Return HTTP 409 from visibility updates to any non-`老师内部` value and from DOCX/PDF export when this helper is true. Show the reason on planning detail with `测试数据不能对外可见或导出`.

- [ ] **Step 6: Run planning and export tests**

```bash
.venv/bin/python -m pytest tests/test_planning_intelligence_reference.py tests/test_planning_routes.py tests/test_planning_edit_export.py tests/test_planning_visibility.py -q
```

Expected: all tests pass; existing documents without an intelligence reference retain existing export behavior.

- [ ] **Step 7: Commit Task 7**

```bash
git add app/schema.sql app/db.py app/repositories.py app/routes/planning.py app/services/planning_generator.py app/templates/planning/generate.html app/templates/planning/detail.html tests/employment_factories.py tests/test_planning_intelligence_reference.py tests/test_planning_routes.py tests/test_planning_edit_export.py tests/test_planning_visibility.py
git commit -m "feat: bind plans to confirmed intelligence versions"
```

---

### Task 8: Visual QA, Local Test Data, and Full Regression

**Files:**
- Modify: `app/static/styles.css`
- Modify: `app/templates/employment/workspace.html`
- Modify: `app/templates/employment/_skills.html`
- Modify: `app/templates/employment/_market.html`
- Modify: `app/templates/employment/report_detail.html`
- Modify: `tests/test_employment_workspace.py`
- Modify: `tests/test_intelligence_reports.py`

**Interfaces:**
- Consumes: all earlier tasks.
- Produces: a browser-verified employment flow for local student ID 7 using clearly labeled test data.

- [ ] **Step 1: Add markup-level accessibility and print tests**

Append assertions that verify:

```python
assert 'aria-label="就业情报工作区"' in text
assert 'role="img"' in text
assert 'aria-label="当前水平' in text
assert '<table' in text  # every chart has a tabular fallback
assert '测试数据，仅用于功能验证' in report_text
assert '数据局限' in report_text
```

Also assert every source link rendered with `target="_blank"` includes `rel="noopener"`.

- [ ] **Step 2: Run focused tests and observe missing markup**

```bash
.venv/bin/python -m pytest tests/test_employment_workspace.py tests/test_intelligence_reports.py -q
```

Expected: failures identify missing accessible labels or fallback tables.

- [ ] **Step 3: Finish CSS/SVG, print, and narrow-screen behavior**

Use these class boundaries in `styles.css` and templates:

```css
.employment-tabs { display:flex; overflow-x:auto; border-bottom:1px solid #e2e8f0; }
.employment-tabs a[aria-current="page"] { color:#2563eb; border-bottom:2px solid #2563eb; }
.evidence-meta { background:#f8fafc; border-left:3px solid #2563eb; padding:12px; }
.skill-gap-bar { background:#e2e8f0; border-radius:999px; overflow:hidden; }
.skill-gap-bar > i { display:block; min-height:10px; background:#2563eb; }
.test-data-banner { background:#fff7ed; border:1px solid #fdba74; color:#9a3412; }
@media (max-width: 760px) {
  .employment-summary-grid, .employment-two-column { grid-template-columns:1fr; }
}
@media print {
  .employment-tabs, .employment-actions, .no-print { display:none !important; }
  .employment-chart-table { display:table !important; }
}
```

Charts must show exact numeric values next to bars and must not depend on color alone. Keep editable forms in `no-print` containers. The immutable report detail is the printable narrative view.

- [ ] **Step 4: Run all automated tests**

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass; total count is greater than 85.

- [ ] **Step 5: Back up the local database before browser fixtures**

Run in the implementation worktree configured against the real local instance only after confirming its database path:

```bash
.venv/bin/flask --app run.py backup-data
```

Expected: a new verified archive is created under `backups/`. Do not restore or alter existing backups.

- [ ] **Step 6: Enter student ID 7 test data through governed UI**

Start Flask locally and use the browser to:

1. Confirm student 7 primary goal `就业`, alternate goal `升学`, reason `功能测试：验证就业路径分流`.
2. Edit the existing test job-skill relationships with the source, owner, reviewer, dates, confidence, sample size, and limitation `测试数据，仅用于功能验证，不代表真实就业市场`, then submit and publish them.
3. Create and publish one Shanghai test market snapshot for the primary test job with a positive sample size and breakdowns for education, experience, and hot skills.
4. Complete the core skill assessments, teacher analysis, and any relevant test exam plan.
5. Verify the readiness checklist has no blocking items, generate V1, and confirm it.
6. Change the teacher analysis, generate V2, and verify V1 remains byte-for-byte unchanged in its rendered facts.
7. Generate a teacher-internal plan from V1 and verify V2 is not silently substituted.
8. Verify student/parent visibility and PDF/DOCX export are blocked for the test-data plan.

- [ ] **Step 7: Browser visual verification**

Verify these URLs with an authenticated teacher/admin session:

```text
/students/7
/students/7/stage-two
/students/7/employment?tab=targets
/students/7/employment?tab=skills
/students/7/employment?tab=market
/students/7/employment?tab=exams
/students/7/employment?tab=analysis
/students/7/employment?tab=reports
/students/7/planning/generate
```

At desktop and narrow widths, confirm no horizontal page overflow, tabs remain usable, source/limitation text is readable, charts match their tables, and print preview excludes forms.

- [ ] **Step 8: Re-run full verification after local QA**

```bash
.venv/bin/python -m pytest -q
git status --short
git diff --check
```

Expected: the full suite passes, no whitespace errors exist, and only intended implementation files plus local runtime/test-data artifacts are changed.

- [ ] **Step 9: Commit Task 8 code only**

```bash
git add app/static/styles.css app/templates/employment/workspace.html app/templates/employment/_skills.html app/templates/employment/_market.html app/templates/employment/report_detail.html tests/test_employment_workspace.py tests/test_intelligence_reports.py
git commit -m "test: verify employment intelligence workflow"
```

Do not add `instance/`, `uploads/`, `generated/`, `backups/`, `tmp/`, or `.superpowers/` to the commit.

---

## Final Verification Checklist

- [ ] `.venv/bin/python -m pytest -q` passes with more than 85 tests.
- [ ] Existing student, questionnaire, file, planning, export, backup, and permission tests still pass.
- [ ] Existing students without a goal are not guessed; they see a goal-confirmation step.
- [ ] Employment and advancement students reach different stage-two workspaces.
- [ ] Goal changes require a confirmed replanning record and preserve history.
- [ ] Only governed, published, unexpired evidence enters live employment analysis.
- [ ] Every generated report is immutable and versioned.
- [ ] Planning documents retain the explicitly selected confirmed report ID.
- [ ] Test-data reports and plans remain internal and cannot be exported as real reports.
- [ ] Student ID 7 shows obvious test-data labels and no claim of real market evidence.
- [ ] Browser, print, and narrow-screen checks pass.
- [ ] No runtime data or unrelated dirty-worktree files are staged.
