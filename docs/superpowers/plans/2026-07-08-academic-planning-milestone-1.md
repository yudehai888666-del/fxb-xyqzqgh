# Academic Planning Milestone 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working local web app milestone for student records, guided student/parent questionnaires, optional material upload, disclaimer confirmation, and teacher internal notes.

**Architecture:** Use a small Flask application with SQLite for local persistence and Jinja templates for server-rendered pages. Keep domain logic in focused repository and service modules so later milestones can add AI generation, document export, and billing without rewriting the data model.

**Tech Stack:** Python 3, Flask, SQLite, pytest, Werkzeug file uploads, Jinja2 templates, vanilla CSS.

---

## Scope

This plan implements only Milestone 1 from the approved design: business data and questionnaire workflow.

Included:

- Local Flask app scaffold.
- SQLite schema and repository layer.
- Student master records.
- Parent contacts and one primary parent questionnaire.
- Student guided questionnaire.
- Optional material upload.
- Material-missing disclaimer confirmation.
- Teacher consultation and internal diagnosis notes.
- Dashboard, student list, student detail, form pages.
- Basic automated tests for schema, repositories, routes, and upload/disclaimer behavior.

Not included in this plan:

- AI generation.
- Planning document editor.
- Word/PDF export.
- Billing and specialty service statistics.
- Multi-user login and permissions.

Those should each receive their own implementation plan after this milestone passes.

## File Structure

Create this structure under `/Users/yu/Desktop/学业规划`:

```text
app/
  __init__.py
  config.py
  db.py
  models.py
  repositories.py
  services/
    __init__.py
    completion.py
    uploads.py
  routes/
    __init__.py
    dashboard.py
    students.py
    questionnaires.py
    teacher_notes.py
  templates/
    base.html
    dashboard.html
    students/
      list.html
      new.html
      detail.html
    questionnaires/
      student.html
      parent.html
    teacher_notes/
      edit.html
  static/
    styles.css
  schema.sql
tests/
  conftest.py
  test_db.py
  test_repositories.py
  test_routes_students.py
  test_questionnaires.py
  test_uploads_and_disclaimer.py
run.py
requirements.txt
.gitignore
README.md
```

Responsibilities:

- `app/__init__.py`: Flask app factory and blueprint registration.
- `app/config.py`: environment-based local paths and app config.
- `app/db.py`: SQLite connection, schema initialization, test database support.
- `app/models.py`: dataclasses for domain records.
- `app/repositories.py`: all SQL read/write operations.
- `app/services/completion.py`: questionnaire/material completion calculations.
- `app/services/uploads.py`: safe upload path generation and file persistence.
- `app/routes/*.py`: route handlers grouped by workflow.
- `app/templates/*`: server-rendered UI.
- `app/static/styles.css`: local app styling.
- `tests/*`: pytest coverage for the milestone.

## Task 1: Project Scaffold And App Factory

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `run.py`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/routes/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write dependency files**

Create `requirements.txt`:

```text
Flask==3.0.3
pytest==8.2.2
```

Create `.gitignore`:

```text
.venv/
__pycache__/
.pytest_cache/
*.pyc
instance/
uploads/
*.sqlite3
*.db
.DS_Store
```

- [ ] **Step 2: Create the app factory**

Create `app/config.py`:

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = PROJECT_ROOT / "instance"
UPLOAD_DIR = PROJECT_ROOT / "uploads"


class Config:
    SECRET_KEY = "local-dev-academic-planning"
    DATABASE = INSTANCE_DIR / "academic_planning.sqlite3"
    UPLOAD_DIR = UPLOAD_DIR
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
```

Create `app/routes/__init__.py`:

```python
from .dashboard import bp as dashboard_bp
from .students import bp as students_bp
from .questionnaires import bp as questionnaires_bp
from .teacher_notes import bp as teacher_notes_bp


def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(teacher_notes_bp)
```

Create `app/__init__.py`:

```python
from flask import Flask

from .config import Config
from .db import close_db
from .routes import register_blueprints


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.config["DATABASE"].parent.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)

    register_blueprints(app)
    app.teardown_appcontext(close_db)
    return app
```

Create `run.py`:

```python
from app import create_app
from app.db import init_db


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5050, debug=True)
```

- [ ] **Step 3: Add temporary route modules so imports resolve**

Create `app/routes/dashboard.py`:

```python
from flask import Blueprint

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    return "Academic Planning"
```

Create `app/routes/students.py`:

```python
from flask import Blueprint

bp = Blueprint("students", __name__, url_prefix="/students")
```

Create `app/routes/questionnaires.py`:

```python
from flask import Blueprint

bp = Blueprint("questionnaires", __name__, url_prefix="/students/<int:student_id>")
```

Create `app/routes/teacher_notes.py`:

```python
from flask import Blueprint

bp = Blueprint("teacher_notes", __name__, url_prefix="/students/<int:student_id>/teacher-notes")
```

- [ ] **Step 4: Write the first failing test**

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    test_app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
        }
    )
    return test_app


@pytest.fixture()
def client(app):
    return app.test_client()
```

Create `tests/test_db.py`:

```python
def test_homepage_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Academic Planning" in response.data
```

- [ ] **Step 5: Run the scaffold test**

Run:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest tests/test_db.py -v
```

Expected: PASS for `test_homepage_loads`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt run.py app tests
git commit -m "feat: scaffold local Flask app"
```

## Task 2: SQLite Schema And Repository Layer

**Files:**
- Create: `app/schema.sql`
- Create: `app/db.py`
- Create: `app/models.py`
- Create: `app/repositories.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_db.py`
- Create: `tests/test_repositories.py`

- [ ] **Step 1: Define the schema**

Create `app/schema.sql`:

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    enrollment_year INTEGER NOT NULL,
    current_term TEXT NOT NULL,
    school TEXT NOT NULL,
    college TEXT NOT NULL DEFAULT '',
    major TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    service_stage TEXT NOT NULL DEFAULT '信息收集',
    responsible_teacher TEXT NOT NULL DEFAULT '本人',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parent_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    communication_method TEXT NOT NULL DEFAULT '',
    is_primary_decision_maker INTEGER NOT NULL DEFAULT 1,
    questionnaire_status TEXT NOT NULL DEFAULT '未填写',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_questionnaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    adaptation_status TEXT NOT NULL DEFAULT '',
    academic_status TEXT NOT NULL DEFAULT '',
    weak_subjects TEXT NOT NULL DEFAULT '',
    tutoring_needs TEXT NOT NULL DEFAULT '',
    interests_strengths TEXT NOT NULL DEFAULT '',
    future_intentions TEXT NOT NULL DEFAULT '',
    motivation_status TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parent_questionnaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_contact_id INTEGER NOT NULL UNIQUE REFERENCES parent_contacts(id) ON DELETE CASCADE,
    family_resources TEXT NOT NULL DEFAULT '',
    target_priorities TEXT NOT NULL DEFAULT '',
    parent_observations TEXT NOT NULL DEFAULT '',
    current_concerns TEXT NOT NULL DEFAULT '',
    investment_willingness TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    uploader_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '其他材料',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS disclaimers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    signer_type TEXT NOT NULL,
    signer_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teacher_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    source_channel TEXT NOT NULL DEFAULT '',
    consultation_stage TEXT NOT NULL DEFAULT '',
    core_request TEXT NOT NULL DEFAULT '',
    family_student_conflict TEXT NOT NULL DEFAULT '',
    resource_match_level TEXT NOT NULL DEFAULT '',
    goal_feasibility TEXT NOT NULL DEFAULT '',
    execution_risk TEXT NOT NULL DEFAULT '',
    academic_risk TEXT NOT NULL DEFAULT '',
    transfer_feasibility TEXT NOT NULL DEFAULT '',
    service_suggestions TEXT NOT NULL DEFAULT '',
    ai_generation_focus TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 2: Implement database helpers**

Create `app/db.py`:

```python
import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    schema_path = Path(__file__).with_name("schema.sql")
    db = get_db()
    db.executescript(schema_path.read_text(encoding="utf-8"))
    db.commit()
```

Create `app/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Student:
    id: int
    name: str
    gender: str
    enrollment_year: int
    current_term: str
    school: str
    college: str
    major: str
    city: str
    phone: str
    service_stage: str
    responsible_teacher: str


@dataclass(frozen=True)
class ParentContact:
    id: int
    student_id: int
    name: str
    relationship: str
    phone: str
    communication_method: str
    is_primary_decision_maker: bool
    questionnaire_status: str
```

- [ ] **Step 3: Implement repository functions**

Create `app/repositories.py`:

```python
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
```

- [ ] **Step 4: Initialize database in tests**

Modify `tests/conftest.py` to initialize schema:

```python
import pytest

from app import create_app
from app.db import init_db


@pytest.fixture()
def app(tmp_path):
    test_app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "test.sqlite3",
            "UPLOAD_DIR": tmp_path / "uploads",
        }
    )
    with test_app.app_context():
        init_db()
    return test_app


@pytest.fixture()
def client(app):
    return app.test_client()
```

Update `tests/test_db.py`:

```python
from app.db import get_db


def test_homepage_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Academic Planning" in response.data


def test_schema_creates_students_table(app):
    with app.app_context():
        row = get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'students'"
        ).fetchone()

    assert row["name"] == "students"
```

Create `tests/test_repositories.py`:

```python
from app import repositories


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
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_db.py tests/test_repositories.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/schema.sql app/db.py app/models.py app/repositories.py tests
git commit -m "feat: add local data model"
```

## Task 3: Dashboard, Student List, Student Creation, And Student Detail

**Files:**
- Modify: `app/routes/dashboard.py`
- Modify: `app/routes/students.py`
- Create: `app/templates/base.html`
- Create: `app/templates/dashboard.html`
- Create: `app/templates/students/list.html`
- Create: `app/templates/students/new.html`
- Create: `app/templates/students/detail.html`
- Create: `app/static/styles.css`
- Create: `tests/test_routes_students.py`

- [ ] **Step 1: Write route tests**

Create `tests/test_routes_students.py`:

```python
def test_student_list_loads(client):
    response = client.get("/students")

    assert response.status_code == 200
    assert "学生档案".encode("utf-8") in response.data


def test_create_student_redirects_to_detail(client):
    response = client.post(
        "/students/new",
        data={
            "name": "王同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "管理学院",
            "major": "工商管理",
            "city": "杭州",
            "phone": "13700000000",
            "responsible_teacher": "于老师",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "王同学".encode("utf-8") in response.data
    assert "家长联系人".encode("utf-8") in response.data
```

- [ ] **Step 2: Implement dashboard and student routes**

Replace `app/routes/dashboard.py`:

```python
from flask import Blueprint, render_template

from app import repositories

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    students = repositories.list_students()
    return render_template("dashboard.html", students=students[:5], total_students=len(students))
```

Replace `app/routes/students.py`:

```python
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

bp = Blueprint("students", __name__, url_prefix="/students")


@bp.get("")
def list_view():
    students = repositories.list_students()
    return render_template("students/list.html", students=students)


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        student_id = repositories.create_student(request.form)
        return redirect(url_for("students.detail", student_id=student_id))
    return render_template("students/new.html")


@bp.get("/<int:student_id>")
def detail(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    parents = repositories.list_parent_contacts(student_id)
    return render_template("students/detail.html", student=student, parents=parents)
```

- [ ] **Step 3: Create templates and CSS**

Create `app/templates/base.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}学业规划工作台{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
  </head>
  <body>
    <header class="topbar">
      <a class="brand" href="{{ url_for('dashboard.index') }}">学业规划工作台</a>
      <nav>
        <a href="{{ url_for('students.list_view') }}">学生档案</a>
        <a href="{{ url_for('students.new') }}">新增学生</a>
      </nav>
    </header>
    <main class="page">
      {% block content %}{% endblock %}
    </main>
  </body>
</html>
```

Create `app/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}首页工作台{% endblock %}
{% block content %}
<section class="page-header">
  <h1>首页工作台</h1>
  <p>当前学生档案：{{ total_students }} 个</p>
</section>
<section class="panel">
  <h2>最近学生</h2>
  <div class="table">
    {% for student in students %}
      <a class="row" href="{{ url_for('students.detail', student_id=student.id) }}">
        <span>{{ student.name }}</span>
        <span>{{ student.school }}</span>
        <span>{{ student.major }}</span>
        <span>{{ student.service_stage }}</span>
      </a>
    {% else %}
      <p class="empty">还没有学生档案。</p>
    {% endfor %}
  </div>
</section>
{% endblock %}
```

Create `app/templates/students/list.html`:

```html
{% extends "base.html" %}
{% block title %}学生档案{% endblock %}
{% block content %}
<section class="page-header split">
  <div>
    <h1>学生档案</h1>
    <p>管理学生主档案、问卷状态、材料与老师诊断。</p>
  </div>
  <a class="button primary" href="{{ url_for('students.new') }}">新增学生</a>
</section>
<section class="panel">
  <div class="table">
    {% for student in students %}
      <a class="row" href="{{ url_for('students.detail', student_id=student.id) }}">
        <span>{{ student.name }}</span>
        <span>{{ student.current_term }}</span>
        <span>{{ student.school }}</span>
        <span>{{ student.major }}</span>
        <span>{{ student.responsible_teacher }}</span>
      </a>
    {% else %}
      <p class="empty">还没有学生档案。</p>
    {% endfor %}
  </div>
</section>
{% endblock %}
```

Create `app/templates/students/new.html`:

```html
{% extends "base.html" %}
{% block title %}新增学生{% endblock %}
{% block content %}
<section class="page-header">
  <h1>新增学生主档案</h1>
  <p>学生基础信息只在主档案中保存，家长问卷不重复采集。</p>
</section>
<form class="form panel" method="post">
  <label>学生姓名 <input name="name" required></label>
  <label>性别 <input name="gender" required></label>
  <label>入学年份 <input name="enrollment_year" type="number" value="2026" required></label>
  <label>当前年级/学期 <input name="current_term" value="大一上" required></label>
  <label>学校 <input name="school" required></label>
  <label>学院 <input name="college"></label>
  <label>专业 <input name="major" required></label>
  <label>所在城市 <input name="city"></label>
  <label>学生联系方式 <input name="phone"></label>
  <label>负责老师 <input name="responsible_teacher" value="本人"></label>
  <button class="button primary" type="submit">保存档案</button>
</form>
{% endblock %}
```

Create `app/templates/students/detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ student.name }}{% endblock %}
{% block content %}
<section class="page-header">
  <h1>{{ student.name }}</h1>
  <p>{{ student.school }} · {{ student.major }} · {{ student.current_term }}</p>
</section>
<section class="grid">
  <div class="panel">
    <h2>学生主档案</h2>
    <p>性别：{{ student.gender }}</p>
    <p>入学年份：{{ student.enrollment_year }}</p>
    <p>城市：{{ student.city or "未填写" }}</p>
    <p>服务阶段：{{ student.service_stage }}</p>
  </div>
  <div class="panel">
    <h2>家长联系人</h2>
    {% for parent in parents %}
      <p>{{ parent.name }} · {{ parent.relationship }} · {{ parent.questionnaire_status }}</p>
    {% else %}
      <p class="empty">还没有家长联系人。</p>
    {% endfor %}
    <a class="button" href="{{ url_for('questionnaires.parent_questionnaire', student_id=student.id) }}">填写家长问卷</a>
  </div>
  <div class="panel">
    <h2>问卷与诊断</h2>
    <a class="button" href="{{ url_for('questionnaires.student_questionnaire', student_id=student.id) }}">填写学生问卷</a>
    <a class="button" href="{{ url_for('teacher_notes.edit', student_id=student.id) }}">老师访谈记录</a>
  </div>
</section>
{% endblock %}
```

Create `app/static/styles.css`:

```css
body {
  margin: 0;
  color: #1f2933;
  background: #f6f7f9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

a { color: inherit; text-decoration: none; }

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 28px;
  background: #ffffff;
  border-bottom: 1px solid #d9dee7;
}

.brand { font-weight: 700; }
.topbar nav { display: flex; gap: 18px; color: #506070; }
.page { max-width: 1120px; margin: 0 auto; padding: 28px; }
.page-header { margin-bottom: 22px; }
.page-header h1 { margin: 0 0 8px; font-size: 28px; }
.page-header p { margin: 0; color: #627386; }
.split { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.panel {
  background: #ffffff;
  border: 1px solid #d9dee7;
  border-radius: 8px;
  padding: 20px;
}
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
.table { display: grid; gap: 8px; }
.row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  padding: 12px;
  border: 1px solid #e4e8ef;
  border-radius: 6px;
  background: #fbfcfd;
}
.form { display: grid; gap: 14px; max-width: 720px; }
.form label { display: grid; gap: 6px; font-weight: 600; }
input, textarea, select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #cfd6e0;
  border-radius: 6px;
  padding: 10px 12px;
  font: inherit;
  background: #ffffff;
}
textarea { min-height: 120px; resize: vertical; }
.button {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: fit-content;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid #b9c3d1;
  border-radius: 6px;
  background: #ffffff;
  color: #233244;
  cursor: pointer;
}
.button.primary { background: #22577a; color: #ffffff; border-color: #22577a; }
.empty { color: #7b8794; }
```

- [ ] **Step 4: Run route tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_routes_students.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes app/templates app/static tests/test_routes_students.py
git commit -m "feat: add student workspace pages"
```

## Task 4: Student And Parent Guided Questionnaires

**Files:**
- Modify: `app/repositories.py`
- Modify: `app/routes/questionnaires.py`
- Create: `app/templates/questionnaires/student.html`
- Create: `app/templates/questionnaires/parent.html`
- Create: `tests/test_questionnaires.py`

- [ ] **Step 1: Add questionnaire repository functions**

Append to `app/repositories.py`:

```python
def save_student_questionnaire(student_id, data):
    db = get_db()
    db.execute(
        """
        INSERT INTO student_questionnaires (
            student_id, adaptation_status, academic_status, weak_subjects,
            tutoring_needs, interests_strengths, future_intentions, motivation_status
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


def get_or_create_primary_parent(student_id, data):
    parents = list_parent_contacts(student_id)
    if parents:
        return parents[0].id
    return create_parent_contact(student_id, data)


def save_parent_questionnaire(student_id, data):
    parent_contact_id = get_or_create_primary_parent(
        student_id,
        {
            "name": data["parent_name"],
            "relationship": data["relationship"],
            "phone": data.get("parent_phone", ""),
            "communication_method": data.get("communication_method", ""),
            "is_primary_decision_maker": True,
        },
    )
    db = get_db()
    db.execute(
        """
        INSERT INTO parent_questionnaires (
            student_id, parent_contact_id, family_resources, target_priorities,
            parent_observations, current_concerns, investment_willingness
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(parent_contact_id) DO UPDATE SET
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
    db.execute(
        """
        UPDATE parent_contacts
        SET questionnaire_status = '已填写', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (parent_contact_id,),
    )
    db.commit()


def get_parent_questionnaire(student_id):
    return get_db().execute(
        """
        SELECT pq.*, pc.name AS parent_name, pc.relationship, pc.phone AS parent_phone,
               pc.communication_method
        FROM parent_questionnaires pq
        JOIN parent_contacts pc ON pc.id = pq.parent_contact_id
        WHERE pq.student_id = ?
        ORDER BY pq.submitted_at DESC
        LIMIT 1
        """,
        (student_id,),
    ).fetchone()
```

- [ ] **Step 2: Implement questionnaire routes**

Replace `app/routes/questionnaires.py`:

```python
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

bp = Blueprint("questionnaires", __name__, url_prefix="/students/<int:student_id>")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@bp.route("/student-questionnaire", methods=["GET", "POST"])
def student_questionnaire(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        repositories.save_student_questionnaire(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))
    questionnaire = repositories.get_student_questionnaire(student_id)
    return render_template(
        "questionnaires/student.html",
        student=student,
        questionnaire=questionnaire,
    )


@bp.route("/parent-questionnaire", methods=["GET", "POST"])
def parent_questionnaire(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        repositories.save_parent_questionnaire(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))
    questionnaire = repositories.get_parent_questionnaire(student_id)
    return render_template(
        "questionnaires/parent.html",
        student=student,
        questionnaire=questionnaire,
    )
```

- [ ] **Step 3: Create questionnaire templates**

Create `app/templates/questionnaires/student.html`:

```html
{% extends "base.html" %}
{% block title %}学生问卷{% endblock %}
{% block content %}
<section class="page-header">
  <h1>学生问卷：{{ student.name }}</h1>
  <p>分步骤采集学生本人状态、兴趣、目标和执行难点。</p>
</section>
<form class="form panel" method="post">
  <label>大学适应状态
    <textarea name="adaptation_status">{{ questionnaire["adaptation_status"] if questionnaire else "" }}</textarea>
  </label>
  <label>学业情况
    <textarea name="academic_status">{{ questionnaire["academic_status"] if questionnaire else "" }}</textarea>
  </label>
  <label>薄弱科目
    <textarea name="weak_subjects">{{ questionnaire["weak_subjects"] if questionnaire else "" }}</textarea>
  </label>
  <label>学科辅导需求
    <textarea name="tutoring_needs">{{ questionnaire["tutoring_needs"] if questionnaire else "" }}</textarea>
  </label>
  <label>兴趣与能力
    <textarea name="interests_strengths">{{ questionnaire["interests_strengths"] if questionnaire else "" }}</textarea>
  </label>
  <label>未来想法
    <textarea name="future_intentions">{{ questionnaire["future_intentions"] if questionnaire else "" }}</textarea>
  </label>
  <label>自我驱动力与执行难点
    <textarea name="motivation_status">{{ questionnaire["motivation_status"] if questionnaire else "" }}</textarea>
  </label>
  <button class="button primary" type="submit">保存学生问卷</button>
</form>
{% endblock %}
```

Create `app/templates/questionnaires/parent.html`:

```html
{% extends "base.html" %}
{% block title %}家长问卷{% endblock %}
{% block content %}
<section class="page-header">
  <h1>主要家长问卷：{{ student.name }}</h1>
  <p>家长问卷作为学生档案下的关联问卷，不重复采集学生基础信息。</p>
</section>
<form class="form panel" method="post">
  <label>家长姓名 <input name="parent_name" value="{{ questionnaire["parent_name"] if questionnaire else "" }}" required></label>
  <label>与学生关系 <input name="relationship" value="{{ questionnaire["relationship"] if questionnaire else "母亲" }}" required></label>
  <label>家长联系方式 <input name="parent_phone" value="{{ questionnaire["parent_phone"] if questionnaire else "" }}"></label>
  <label>常用沟通方式 <input name="communication_method" value="{{ questionnaire["communication_method"] if questionnaire else "微信" }}"></label>
  <label>家庭资源
    <textarea name="family_resources">{{ questionnaire["family_resources"] if questionnaire else "" }}</textarea>
  </label>
  <label>升学与发展目标排序
    <textarea name="target_priorities">{{ questionnaire["target_priorities"] if questionnaire else "" }}</textarea>
  </label>
  <label>家长对孩子的观察
    <textarea name="parent_observations">{{ questionnaire["parent_observations"] if questionnaire else "" }}</textarea>
  </label>
  <label>当前困惑
    <textarea name="current_concerns">{{ questionnaire["current_concerns"] if questionnaire else "" }}</textarea>
  </label>
  <label>投入意愿
    <textarea name="investment_willingness">{{ questionnaire["investment_willingness"] if questionnaire else "" }}</textarea>
  </label>
  <button class="button primary" type="submit">保存家长问卷</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Add questionnaire tests**

Create `tests/test_questionnaires.py`:

```python
from app import repositories


def create_sample_student(app):
    with app.app_context():
        return repositories.create_student(
            {
                "name": "赵同学",
                "gender": "男",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "电子信息类",
            }
        )


def test_student_questionnaire_save(client, app):
    student_id = create_sample_student(app)

    response = client.post(
        f"/students/{student_id}/student-questionnaire",
        data={
            "adaptation_status": "课程压力中等",
            "academic_status": "数学基础一般",
            "weak_subjects": "高数",
            "tutoring_needs": "期末前需要辅导",
            "interests_strengths": "喜欢编程",
            "future_intentions": "保研优先，考研备选",
            "motivation_status": "需要外部提醒",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        row = repositories.get_student_questionnaire(student_id)
    assert row["future_intentions"] == "保研优先，考研备选"


def test_parent_questionnaire_creates_primary_parent(client, app):
    student_id = create_sample_student(app)

    response = client.post(
        f"/students/{student_id}/parent-questionnaire",
        data={
            "parent_name": "赵女士",
            "relationship": "母亲",
            "parent_phone": "13600000000",
            "communication_method": "微信",
            "family_resources": "家庭支持考研和留学备选",
            "target_priorities": "保研第一，考研第二，就业第三",
            "parent_observations": "孩子执行力需要督促",
            "current_concerns": "担心第一学期成绩掉队",
            "investment_willingness": "接受基础规划和必要专项服务",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        parents = repositories.list_parent_contacts(student_id)
        questionnaire = repositories.get_parent_questionnaire(student_id)
    assert parents[0].questionnaire_status == "已填写"
    assert questionnaire["target_priorities"] == "保研第一，考研第二，就业第三"
```

- [ ] **Step 5: Run questionnaire tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_questionnaires.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/repositories.py app/routes/questionnaires.py app/templates/questionnaires tests/test_questionnaires.py
git commit -m "feat: add guided questionnaires"
```

## Task 5: Optional Material Upload And Disclaimer Confirmation

**Files:**
- Create: `app/services/uploads.py`
- Modify: `app/repositories.py`
- Modify: `app/routes/questionnaires.py`
- Modify: `app/templates/students/detail.html`
- Create: `app/templates/questionnaires/materials.html`
- Create: `tests/test_uploads_and_disclaimer.py`

- [ ] **Step 1: Add upload service**

Create `app/services/__init__.py`:

```python
```

Create `app/services/uploads.py`:

```python
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".txt",
}


def save_upload(student_id, file_storage):
    original_name = file_storage.filename or ""
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("不支持的文件类型")

    safe_original = secure_filename(original_name) or f"material{suffix}"
    stored_name = f"student-{student_id}-{uuid4().hex}-{safe_original}"
    destination = Path(current_app.config["UPLOAD_DIR"]) / stored_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination)
    return stored_name
```

- [ ] **Step 2: Add material and disclaimer repository functions**

Append to `app/repositories.py`:

```python
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
        "SELECT * FROM materials WHERE student_id = ? ORDER BY uploaded_at DESC",
        (student_id,),
    ).fetchall()


def confirm_disclaimer(student_id, data):
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO disclaimers (student_id, signer_type, signer_name, reason)
        VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            data["signer_type"],
            data["signer_name"],
            data["reason"],
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_disclaimers(student_id):
    return get_db().execute(
        "SELECT * FROM disclaimers WHERE student_id = ? ORDER BY confirmed_at DESC",
        (student_id,),
    ).fetchall()
```

- [ ] **Step 3: Add materials route**

Append to `app/routes/questionnaires.py`:

```python
from app.services.uploads import save_upload
```

Add this route below existing questionnaire routes:

```python
@bp.route("/materials", methods=["GET", "POST"])
def materials(student_id):
    student = require_student(student_id)
    error = ""
    if request.method == "POST":
        if request.form.get("action") == "upload":
            uploaded_file = request.files.get("material")
            if uploaded_file and uploaded_file.filename:
                try:
                    stored_filename = save_upload(student_id, uploaded_file)
                    repositories.create_material(
                        student_id,
                        {
                            "uploader_type": request.form.get("uploader_type", "老师"),
                            "original_filename": uploaded_file.filename,
                            "stored_filename": stored_filename,
                            "category": request.form.get("category", "其他材料"),
                        },
                    )
                except ValueError as exc:
                    error = str(exc)
            return redirect(url_for("questionnaires.materials", student_id=student_id))

        if request.form.get("action") == "disclaimer":
            repositories.confirm_disclaimer(
                student_id,
                {
                    "signer_type": request.form["signer_type"],
                    "signer_name": request.form["signer_name"],
                    "reason": request.form["reason"],
                },
            )
            return redirect(url_for("questionnaires.materials", student_id=student_id))

    return render_template(
        "questionnaires/materials.html",
        student=student,
        materials=repositories.list_materials(student_id),
        disclaimers=repositories.list_disclaimers(student_id),
        error=error,
    )
```

- [ ] **Step 4: Add materials page and detail link**

Create `app/templates/questionnaires/materials.html`:

```html
{% extends "base.html" %}
{% block title %}材料与免责{% endblock %}
{% block content %}
<section class="page-header">
  <h1>材料与免责：{{ student.name }}</h1>
  <p>材料上传不强制；未上传关键材料时，需要确认规划依据和责任边界。</p>
</section>
{% if error %}<p class="panel">{{ error }}</p>{% endif %}
<section class="grid">
  <form class="form panel" method="post" enctype="multipart/form-data">
    <h2>上传材料</h2>
    <input type="hidden" name="action" value="upload">
    <label>上传人
      <select name="uploader_type">
        <option>老师</option>
        <option>学生</option>
        <option>家长</option>
      </select>
    </label>
    <label>材料类型 <input name="category" value="成绩单"></label>
    <label>选择文件 <input name="material" type="file"></label>
    <button class="button primary" type="submit">上传</button>
  </form>
  <form class="form panel" method="post">
    <h2>免责确认</h2>
    <input type="hidden" name="action" value="disclaimer">
    <label>确认人类型
      <select name="signer_type">
        <option>家长</option>
        <option>学生</option>
        <option>老师代录</option>
      </select>
    </label>
    <label>确认人姓名 <input name="signer_name" required></label>
    <label>确认原因
      <textarea name="reason" required>当前未上传完整关键材料，规划基于已填写信息和已上传材料生成，不构成具体结果承诺。</textarea>
    </label>
    <button class="button primary" type="submit">确认免责</button>
  </form>
</section>
<section class="panel">
  <h2>已上传材料</h2>
  {% for material in materials %}
    <p>{{ material["category"] }} · {{ material["original_filename"] }} · {{ material["uploader_type"] }}</p>
  {% else %}
    <p class="empty">暂未上传材料。</p>
  {% endfor %}
  <h2>免责记录</h2>
  {% for disclaimer in disclaimers %}
    <p>{{ disclaimer["signer_type"] }} · {{ disclaimer["signer_name"] }} · {{ disclaimer["reason"] }}</p>
  {% else %}
    <p class="empty">暂未确认免责。</p>
  {% endfor %}
</section>
{% endblock %}
```

Modify the third panel in `app/templates/students/detail.html` to include:

```html
<a class="button" href="{{ url_for('questionnaires.materials', student_id=student.id) }}">材料与免责</a>
```

- [ ] **Step 5: Add upload and disclaimer tests**

Create `tests/test_uploads_and_disclaimer.py`:

```python
from io import BytesIO

from app import repositories


def create_student(app):
    with app.app_context():
        return repositories.create_student(
            {
                "name": "钱同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "法学",
            }
        )


def test_material_upload_records_file(client, app):
    student_id = create_student(app)

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "upload",
            "uploader_type": "家长",
            "category": "成绩单",
            "material": (BytesIO(b"score data"), "score.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        materials = repositories.list_materials(student_id)
    assert len(materials) == 1
    assert materials[0]["original_filename"] == "score.txt"


def test_disclaimer_confirmation_records_reason(client, app):
    student_id = create_student(app)

    response = client.post(
        f"/students/{student_id}/materials",
        data={
            "action": "disclaimer",
            "signer_type": "家长",
            "signer_name": "钱先生",
            "reason": "未上传培养方案，确认规划基于当前信息生成。",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        disclaimers = repositories.list_disclaimers(student_id)
    assert len(disclaimers) == 1
    assert disclaimers[0]["signer_name"] == "钱先生"
```

- [ ] **Step 6: Run upload and disclaimer tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_uploads_and_disclaimer.py -v
```

Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services app/repositories.py app/routes/questionnaires.py app/templates tests/test_uploads_and_disclaimer.py
git commit -m "feat: add materials and disclaimer workflow"
```

## Task 6: Teacher Consultation And Internal Diagnosis Notes

**Files:**
- Modify: `app/repositories.py`
- Modify: `app/routes/teacher_notes.py`
- Create: `app/templates/teacher_notes/edit.html`
- Create: `tests/test_teacher_notes.py`

- [ ] **Step 1: Add teacher note repository functions**

Append to `app/repositories.py`:

```python
def save_teacher_notes(student_id, data):
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
            data.get("source_channel", ""),
            data.get("consultation_stage", ""),
            data.get("core_request", ""),
            data.get("family_student_conflict", ""),
            data.get("resource_match_level", ""),
            data.get("goal_feasibility", ""),
            data.get("execution_risk", ""),
            data.get("academic_risk", ""),
            data.get("transfer_feasibility", ""),
            data.get("service_suggestions", ""),
            data.get("ai_generation_focus", ""),
        ),
    )
    db.commit()


def get_teacher_notes(student_id):
    return get_db().execute(
        "SELECT * FROM teacher_notes WHERE student_id = ?",
        (student_id,),
    ).fetchone()
```

- [ ] **Step 2: Implement teacher notes route**

Replace `app/routes/teacher_notes.py`:

```python
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

bp = Blueprint("teacher_notes", __name__, url_prefix="/students/<int:student_id>/teacher-notes")


@bp.route("", methods=["GET", "POST"])
def edit(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    if request.method == "POST":
        repositories.save_teacher_notes(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))
    notes = repositories.get_teacher_notes(student_id)
    return render_template("teacher_notes/edit.html", student=student, notes=notes)
```

- [ ] **Step 3: Create teacher notes template**

Create `app/templates/teacher_notes/edit.html`:

```html
{% extends "base.html" %}
{% block title %}老师访谈与诊断{% endblock %}
{% block content %}
<section class="page-header">
  <h1>老师访谈与内部诊断：{{ student.name }}</h1>
  <p>这些内容只服务老师后台，不直接展示给家长或学生。</p>
</section>
<form class="form panel" method="post">
  <label>学生来源 <input name="source_channel" value="{{ notes["source_channel"] if notes else "" }}"></label>
  <label>咨询阶段 <input name="consultation_stage" value="{{ notes["consultation_stage"] if notes else "" }}"></label>
  <label>核心诉求 <textarea name="core_request">{{ notes["core_request"] if notes else "" }}</textarea></label>
  <label>家长与学生主要矛盾点 <textarea name="family_student_conflict">{{ notes["family_student_conflict"] if notes else "" }}</textarea></label>
  <label>家庭资源匹配度 <textarea name="resource_match_level">{{ notes["resource_match_level"] if notes else "" }}</textarea></label>
  <label>目标可行性 <textarea name="goal_feasibility">{{ notes["goal_feasibility"] if notes else "" }}</textarea></label>
  <label>执行力风险 <textarea name="execution_risk">{{ notes["execution_risk"] if notes else "" }}</textarea></label>
  <label>学业风险 <textarea name="academic_risk">{{ notes["academic_risk"] if notes else "" }}</textarea></label>
  <label>转专业可行性 <textarea name="transfer_feasibility">{{ notes["transfer_feasibility"] if notes else "" }}</textarea></label>
  <label>服务建议 <textarea name="service_suggestions">{{ notes["service_suggestions"] if notes else "" }}</textarea></label>
  <label>AI 生成重点 <textarea name="ai_generation_focus">{{ notes["ai_generation_focus"] if notes else "" }}</textarea></label>
  <button class="button primary" type="submit">保存老师记录</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Add teacher note tests**

Create `tests/test_teacher_notes.py`:

```python
from app import repositories


def test_teacher_notes_save(client, app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "孙同学",
                "gender": "男",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "临床医学",
            }
        )

    response = client.post(
        f"/students/{student_id}/teacher-notes",
        data={
            "source_channel": "老客户转介绍",
            "consultation_stage": "初次咨询",
            "core_request": "希望保研优先，考研备选",
            "family_student_conflict": "家长希望留学，学生倾向保研",
            "resource_match_level": "家庭可支持语言和科研投入",
            "goal_feasibility": "保研需要观察大一绩点",
            "execution_risk": "学生主动性一般",
            "academic_risk": "高数和英语需要关注",
            "transfer_feasibility": "暂不建议转专业",
            "service_suggestions": "基础规划后推荐学科辅导",
            "ai_generation_focus": "保研第一，考研第二，就业第三",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        notes = repositories.get_teacher_notes(student_id)
    assert notes["goal_feasibility"] == "保研需要观察大一绩点"
    assert notes["ai_generation_focus"] == "保研第一，考研第二，就业第三"
```

- [ ] **Step 5: Run teacher note tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_teacher_notes.py -v
```

Expected: test PASS.

- [ ] **Step 6: Commit**

```bash
git add app/repositories.py app/routes/teacher_notes.py app/templates/teacher_notes tests/test_teacher_notes.py
git commit -m "feat: add teacher diagnosis notes"
```

## Task 7: Completion Summary On Student Detail

**Files:**
- Create: `app/services/completion.py`
- Modify: `app/routes/students.py`
- Modify: `app/templates/students/detail.html`
- Create: `tests/test_completion.py`

- [ ] **Step 1: Create completion service**

Create `app/services/completion.py`:

```python
from app import repositories


def get_student_completion(student_id):
    student_questionnaire = repositories.get_student_questionnaire(student_id)
    parent_questionnaire = repositories.get_parent_questionnaire(student_id)
    materials = repositories.list_materials(student_id)
    disclaimers = repositories.list_disclaimers(student_id)
    teacher_notes = repositories.get_teacher_notes(student_id)

    material_status = "已上传材料" if materials else "未上传材料"
    disclaimer_status = "已确认免责" if disclaimers else "未确认免责"

    return {
        "student_questionnaire": "已填写" if student_questionnaire else "未填写",
        "parent_questionnaire": "已填写" if parent_questionnaire else "未填写",
        "materials": material_status,
        "disclaimer": disclaimer_status,
        "teacher_notes": "已填写" if teacher_notes else "未填写",
        "ready_for_ai": bool(
            student_questionnaire
            and parent_questionnaire
            and teacher_notes
            and (materials or disclaimers)
        ),
    }
```

- [ ] **Step 2: Pass completion summary to detail template**

Modify `app/routes/students.py`:

```python
from app.services.completion import get_student_completion
```

Update the `detail` function:

```python
@bp.get("/<int:student_id>")
def detail(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    parents = repositories.list_parent_contacts(student_id)
    completion = get_student_completion(student_id)
    return render_template(
        "students/detail.html",
        student=student,
        parents=parents,
        completion=completion,
    )
```

- [ ] **Step 3: Render status summary**

Add this panel near the top of `app/templates/students/detail.html`:

```html
<section class="panel">
  <h2>信息完整度</h2>
  <p>学生问卷：{{ completion.student_questionnaire }}</p>
  <p>主要家长问卷：{{ completion.parent_questionnaire }}</p>
  <p>材料状态：{{ completion.materials }}</p>
  <p>免责状态：{{ completion.disclaimer }}</p>
  <p>老师记录：{{ completion.teacher_notes }}</p>
  <p>AI 生成准备：{{ "可以进入下一阶段" if completion.ready_for_ai else "信息仍需补充" }}</p>
</section>
```

- [ ] **Step 4: Add completion test**

Create `tests/test_completion.py`:

```python
from app import repositories
from app.services.completion import get_student_completion


def test_completion_requires_questionnaires_notes_and_material_or_disclaimer(app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "周同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "经济学",
            }
        )
        incomplete = get_student_completion(student_id)

        repositories.save_student_questionnaire(student_id, {"future_intentions": "保研"})
        repositories.save_parent_questionnaire(
            student_id,
            {
                "parent_name": "周女士",
                "relationship": "母亲",
                "target_priorities": "保研第一",
            },
        )
        repositories.save_teacher_notes(student_id, {"goal_feasibility": "需要看绩点"})
        repositories.confirm_disclaimer(
            student_id,
            {
                "signer_type": "家长",
                "signer_name": "周女士",
                "reason": "未上传完整材料，确认基于当前信息生成。",
            },
        )
        complete = get_student_completion(student_id)

    assert incomplete["ready_for_ai"] is False
    assert complete["ready_for_ai"] is True
```

- [ ] **Step 5: Run completion tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_completion.py -v
```

Expected: test PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/completion.py app/routes/students.py app/templates/students/detail.html tests/test_completion.py
git commit -m "feat: show student completion status"
```

## Task 8: README, Manual Smoke Test, And Push

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README**

Create `README.md`:

````markdown
# 学业规划本地网页系统

第一阶段实现内容：

- 学生主档案
- 主要家长问卷
- 学生问卷
- 可选材料上传
- 材料缺失免责确认
- 老师访谈与内部诊断
- 信息完整度状态

## 本地运行

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

打开：

```text
http://127.0.0.1:5050
```

## 测试

```bash
. .venv/bin/activate
python -m pytest -v
```
````

- [ ] **Step 2: Run all tests**

Run:

```bash
. .venv/bin/activate
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run the local server**

Run:

```bash
. .venv/bin/activate
python run.py
```

Expected:

```text
* Running on http://127.0.0.1:5050
```

- [ ] **Step 4: Manual smoke test in browser**

Open `http://127.0.0.1:5050` and verify:

- Homepage loads.
- New student can be created.
- Student detail page opens.
- Student questionnaire saves.
- Parent questionnaire saves and creates primary parent contact.
- Material upload accepts `.txt` file.
- Disclaimer confirmation saves.
- Teacher notes save.
- Student detail page shows readiness as `可以进入下一阶段` after questionnaires, notes, and material or disclaimer exist.

- [ ] **Step 5: Commit README**

```bash
git add README.md
git commit -m "docs: add milestone one runbook"
```

- [ ] **Step 6: Push**

```bash
git push
```

Expected:

```text
Everything up-to-date
```

or a normal GitHub push summary showing the new commits uploaded to `origin/main`.

## Final Verification

Before claiming Milestone 1 complete, run:

```bash
. .venv/bin/activate
python -m pytest -v
git status -sb
git log --oneline -8
```

Expected:

- Pytest reports all tests passed.
- `git status -sb` shows `## main...origin/main`.
- Recent commits include each milestone task commit.

## Self-Review

Spec coverage:

- Student master record: Task 2 and Task 3.
- Parent contact under student record: Task 2 and Task 4.
- One primary parent questionnaire with later reusable questionnaire-instance model: Task 4.
- Student guided questionnaire: Task 4.
- Optional material upload: Task 5.
- Disclaimer for missing materials: Task 5.
- Teacher consultation and internal diagnosis: Task 6.
- Information readiness for next AI phase: Task 7.
- Local run instructions and tests: Task 8.

Placeholder scan:

- The plan contains no unfinished markers or undefined future implementation steps inside this milestone.

Type consistency:

- `student_id` is the shared foreign key across questionnaires, materials, disclaimers, and teacher notes.
- Repository function names used by routes and tests match the definitions in earlier tasks.
- Template route names match blueprint endpoint names.
