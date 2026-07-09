# Academic Planning Milestone 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a teacher-facing workflow that generates a first-draft academic planning document with built-in information basis, disclaimer, risk boundaries, and local Markdown/HTML preview.

**Architecture:** Extend the existing Flask + SQLite app with a `planning_documents` table, a deterministic local draft generator, and teacher-facing planning routes. This milestone intentionally does not call a live AI API or produce Word/PDF; it creates a reliable local draft pipeline that later AI and export modules can replace or enhance.

**Tech Stack:** Python 3, Flask, SQLite, Jinja2, pytest, local Markdown file output.

---

## Scope

This plan implements the next useful slice after Milestone 1:

- Add planning document persistence.
- Add a deterministic first-draft generator from student record, student questionnaire, parent questionnaire, materials/disclaimers, and teacher notes.
- Add an integrated disclaimer and responsibility-boundary section inside every generated draft.
- Add teacher-facing pages to generate, preview, view, and save drafts.
- Add local `.md` file output under `generated/plans/student-<id>/`.
- Add tests for generation readiness, draft content, disclaimer content, persistence, file output, and route behavior.

Not included:

- Live AI API integration.
- Editable rich-text planning editor.
- Word export.
- PDF export.
- Billing/statistics module.
- Multi-user permissions.

## Existing Code Facts

Current Milestone 1 code has:

- Student records in `students`.
- Parent contacts in `parent_contacts`.
- Student questionnaires in `student_questionnaires`.
- Parent questionnaires in `parent_questionnaires`.
- Materials in `materials`.
- Disclaimers in `disclaimers`.
- Teacher notes in `teacher_notes`.
- Completion readiness in `app/services/completion.py`.
- Student detail page at `app/templates/students/detail.html`.

Current code does not have:

- Planning document database table.
- Planning-generation service.
- Planning routes.
- Planning templates.
- File output for generated plans.

## File Structure

Create or modify these files:

```text
app/
  config.py
  schema.sql
  repositories.py
  services/
    completion.py
    planning_generator.py
    planning_files.py
  routes/
    __init__.py
    planning.py
    students.py
  templates/
    planning/
      generate.html
      detail.html
    students/
      detail.html
tests/
  test_planning_repository.py
  test_planning_generator.py
  test_planning_routes.py
  test_planning_files.py
  test_planning_visibility.py
README.md
```

Responsibilities:

- `app/schema.sql`: adds `planning_documents`.
- `app/repositories.py`: adds persistence functions for planning drafts.
- `app/services/planning_generator.py`: turns existing student data into a deterministic Markdown draft.
- `app/services/planning_files.py`: writes generated Markdown to local project storage.
- `app/routes/planning.py`: exposes teacher-facing generate/view routes.
- `app/templates/planning/generate.html`: generation pre-check and confirmation page.
- `app/templates/planning/detail.html`: generated draft preview.
- `app/templates/students/detail.html`: entry point from student detail.

## Data Model

Add `planning_documents`:

```sql
CREATE TABLE IF NOT EXISTS planning_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '草稿',
    content_markdown TEXT NOT NULL,
    file_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Rules:

- Every generated document starts as `草稿`.
- Drafts are append-only for this milestone; generating again creates a new row.
- `file_path` stores the local Markdown path after file save.

## Task 1: Planning Document Schema And Repository

**Files:**
- Modify: `app/schema.sql`
- Modify: `app/repositories.py`
- Create: `tests/test_planning_repository.py`

- [ ] **Step 1: Add failing repository tests**

Create `tests/test_planning_repository.py`:

```python
from app import repositories


def create_student():
    return repositories.create_student(
        {
            "name": "规划同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "信息学院",
            "major": "计算机类",
        }
    )


def test_create_and_list_planning_documents(app):
    with app.app_context():
        student_id = create_student()
        document_id = repositories.create_planning_document(
            student_id,
            {
                "title": "规划同学大学四年初步规划",
                "content_markdown": "# 初步规划\n\n测试内容",
            },
        )
        documents = repositories.list_planning_documents(student_id)
        document = repositories.get_planning_document(document_id)

    assert document_id == 1
    assert len(documents) == 1
    assert documents[0]["title"] == "规划同学大学四年初步规划"
    assert document["status"] == "草稿"
    assert document["content_markdown"].startswith("# 初步规划")


def test_update_planning_document_file_path(app):
    with app.app_context():
        student_id = create_student()
        document_id = repositories.create_planning_document(
            student_id,
            {
                "title": "文件路径测试",
                "content_markdown": "# 文件路径测试",
            },
        )
        repositories.update_planning_document_file_path(
            document_id,
            "generated/plans/student-1/plan-1.md",
        )
        document = repositories.get_planning_document(document_id)

    assert document["file_path"] == "generated/plans/student-1/plan-1.md"
```

- [ ] **Step 2: Run repository tests and confirm failure**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_repository.py -v
```

Expected: FAIL because `create_planning_document` is not defined or table is missing.

- [ ] **Step 3: Add schema**

Append to `app/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS planning_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '草稿',
    content_markdown TEXT NOT NULL,
    file_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 4: Add repository functions**

Append to `app/repositories.py`:

```python
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
            data["title"].strip(),
            data.get("status", "草稿").strip() or "草稿",
            data["content_markdown"],
            data.get("file_path", "").strip(),
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_planning_document(document_id):
    return get_db().execute(
        """
        SELECT *
        FROM planning_documents
        WHERE id = ?
        """,
        (document_id,),
    ).fetchone()


def list_planning_documents(student_id):
    return get_db().execute(
        """
        SELECT *
        FROM planning_documents
        WHERE student_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (student_id,),
    ).fetchall()


def update_planning_document_file_path(document_id, file_path):
    db = get_db()
    db.execute(
        """
        UPDATE planning_documents
        SET file_path = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (file_path, document_id),
    )
    db.commit()
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_repository.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/schema.sql app/repositories.py tests/test_planning_repository.py
git commit -m "feat: add planning document persistence"
```

## Task 2: Planning Context And Draft Generator

**Files:**
- Create: `app/services/planning_generator.py`
- Create: `tests/test_planning_generator.py`

- [ ] **Step 1: Add failing generator tests**

Create `tests/test_planning_generator.py`:

```python
from app import repositories
from app.services.planning_generator import build_planning_context, generate_initial_plan


def seed_ready_student():
    student_id = repositories.create_student(
        {
            "name": "陈同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "信息学院",
            "major": "计算机类",
        }
    )
    repositories.save_student_questionnaire(
        student_id,
        {
            "academic_status": "高数基础一般，英语较好",
            "weak_subjects": "高等数学",
            "tutoring_needs": "期末前需要学科辅导",
            "future_intentions": "保研优先，考研备选",
            "motivation_status": "需要老师定期提醒",
        },
    )
    repositories.save_parent_questionnaire(
        student_id,
        {
            "parent_name": "陈女士",
            "relationship": "母亲",
            "family_resources": "家庭支持科研和语言培训",
            "target_priorities": "保研第一，考研第二，就业第三",
            "parent_observations": "孩子自律一般但目标感较强",
            "current_concerns": "担心高数和绩点",
            "investment_willingness": "接受基础规划和必要专项服务",
        },
    )
    repositories.save_teacher_notes(
        student_id,
        {
            "goal_feasibility": "保研需要观察大一绩点和英语成绩",
            "academic_risk": "高数存在短期风险",
            "service_suggestions": "建议先做学科辅导和四年规划",
            "ai_generation_focus": "保研第一，考研第二，就业第三",
        },
    )
    repositories.confirm_disclaimer(
        student_id,
        {
            "signer_type": "家长",
            "signer_name": "陈女士",
            "reason": "当前材料暂缺，确认基于已填写信息生成初步规划。",
        },
    )
    return student_id


def test_generate_initial_plan_contains_core_sections(app):
    with app.app_context():
        student_id = seed_ready_student()
        context = build_planning_context(student_id)
        draft = generate_initial_plan(context)

    assert "# 陈同学大学四年初步规划" in draft["title"]
    assert "## 信息依据与免责声明" in draft["content_markdown"]
    assert "不构成保研、录取、转专业、就业或考试结果承诺" in draft["content_markdown"]
    assert "## 家庭资源与升学目标分析" in draft["content_markdown"]
    assert "保研第一，考研第二，就业第三" in draft["content_markdown"]
    assert "## 学业基础与学科辅导建议" in draft["content_markdown"]
    assert "高等数学" in draft["content_markdown"]
    assert "## 目标风险、备选路径与责任边界" in draft["content_markdown"]
    assert "第二路径" in draft["content_markdown"]


def test_build_planning_context_rejects_missing_student(app):
    with app.app_context():
        try:
            build_planning_context(999)
        except ValueError as exc:
            message = str(exc)
        else:
            message = ""

    assert message == "学生不存在"
```

- [ ] **Step 2: Run generator tests and confirm failure**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_generator.py -v
```

Expected: FAIL because `app.services.planning_generator` does not exist.

- [ ] **Step 3: Implement generator**

Create `app/services/planning_generator.py`:

```python
from app import repositories


def row_to_dict(row):
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def value(data, key, fallback="未填写"):
    text = str(data.get(key, "") or "").strip()
    return text if text else fallback


def build_planning_context(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        raise ValueError("学生不存在")

    return {
        "student": student,
        "student_questionnaire": row_to_dict(
            repositories.get_student_questionnaire(student_id)
        ),
        "parent_questionnaire": row_to_dict(
            repositories.get_parent_questionnaire(student_id)
        ),
        "materials": [row_to_dict(row) for row in repositories.list_materials(student_id)],
        "disclaimers": [
            row_to_dict(row) for row in repositories.list_disclaimers(student_id)
        ],
        "teacher_notes": row_to_dict(repositories.get_teacher_notes(student_id)),
    }


def generate_information_basis(context):
    materials = context["materials"]
    disclaimers = context["disclaimers"]
    material_line = "已上传材料：" + "、".join(
        item["original_filename"] for item in materials
    ) if materials else "当前未上传关键材料。"
    disclaimer_line = "已确认免责。" if disclaimers else "当前尚未完成免责确认。"
    return (
        "本初步规划基于学生主档案、学生问卷、主要家长问卷、老师访谈记录"
        "以及当前已上传材料生成。"
        f"\n\n- {material_line}"
        f"\n- {disclaimer_line}"
        "\n- 规划内容用于阶段性路径建议与沟通参考，不构成保研、录取、转专业、就业或考试结果承诺。"
        "\n- 若后续成绩、政策、材料真实性、学生执行情况发生变化，应重新评估并更新规划。"
    )


def generate_initial_plan(context):
    student = context["student"]
    sq = context["student_questionnaire"]
    pq = context["parent_questionnaire"]
    notes = context["teacher_notes"]

    title = f"# {student.name}大学四年初步规划"
    body = f"""
{title}

## 一、学生基础画像

- 学校：{student.school}
- 学院/专业：{student.college or "未填写"} / {student.major}
- 入学年份：{student.enrollment_year}
- 当前学期：{student.current_term}
- 当前学业情况：{value(sq, "academic_status")}
- 学生未来意向：{value(sq, "future_intentions")}

## 二、信息依据与免责声明

{generate_information_basis(context)}

## 三、家庭资源与升学目标分析

- 家庭资源：{value(pq, "family_resources")}
- 目标优先级：{value(pq, "target_priorities")}
- 家长对孩子的观察：{value(pq, "parent_observations")}
- 当前担忧：{value(pq, "current_concerns")}
- 投入意愿：{value(pq, "investment_willingness")}

## 四、学业基础与学科辅导建议

- 薄弱科目：{value(sq, "weak_subjects")}
- 学科辅导需求：{value(sq, "tutoring_needs")}
- 老师判断的学业风险：{value(notes, "academic_risk")}
- 初步建议：优先稳住大一基础课程和绩点，期末前对薄弱课程做短周期复盘与辅导。

## 五、专业适应与转专业目标建议

- 学生适应状态：{value(sq, "adaptation_status")}
- 兴趣与能力：{value(sq, "interests_strengths")}
- 转专业可行性：{value(notes, "transfer_feasibility")}
- 初步建议：如学生对当前专业不适应，应尽早确认学校转专业政策、成绩要求、申请窗口和面试材料。

## 六、四年总体发展目标

- 第一目标：{value(notes, "ai_generation_focus", value(sq, "future_intentions"))}
- 目标可行性：{value(notes, "goal_feasibility")}
- 执行风险：{value(notes, "execution_risk")}
- 服务建议：{value(notes, "service_suggestions")}

## 七、大一到大四年度规划

### 大一：适应大学节奏，稳住成绩底盘

重点关注课程适应、学习方法、期末风险、英语基础和是否存在转专业可能。

### 大二：积累证书、竞赛、项目和科研入口

重点推进英语、计算机等级、竞赛、大创、科研或项目经历，形成简历素材。

### 大三：确定主路径和备选路径

围绕保研、考研、留学、就业等方向形成目标清单、材料清单和阶段任务。

### 大四：集中冲刺并完成最终衔接

根据主路径完成推免、考研、留学申请、就业投递或其他结果落地。

## 八、目标风险、备选路径与责任边界

- 第一目标：优先依据家长目标、学生意向和老师记录综合判断。
- 风险触发：挂科、绩点下滑、英语未达标、材料不真实、学生长期不配合、错过学校政策窗口等。
- 第二路径：当第一目标不可行时，建议切换到考研、就业或留学等备选路径。
- 第三路径：结合家庭资源和学生执行情况保留就业、升学或其他专项服务方案。
- 费用边界：基础规划包含路径评估和初步切换建议；考研课程、复试辅导、留学申请、就业训练、科研竞赛等属于后续专项服务，应另行确认报价。

## 九、后续跟进建议

建议每学期至少复盘一次成绩、证书、项目、竞赛、科研、实习和目标路径变化，并根据真实执行情况更新规划。
""".strip()

    return {
        "title": f"{student.name}大学四年初步规划",
        "content_markdown": body,
    }
```

- [ ] **Step 4: Run generator tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_generator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/planning_generator.py tests/test_planning_generator.py
git commit -m "feat: add initial planning generator"
```

## Task 3: Planning Markdown File Output

**Files:**
- Modify: `app/config.py`
- Create: `app/services/planning_files.py`
- Create: `tests/test_planning_files.py`

- [ ] **Step 1: Add failing file-output tests**

Create `tests/test_planning_files.py`:

```python
from pathlib import Path

from app.services.planning_files import save_planning_markdown


def test_save_planning_markdown_writes_student_file(app):
    content = "# 测试规划\n\n正文"
    with app.app_context():
        relative_path = save_planning_markdown(3, 9, "测试规划", content)

    expected = Path(app.config["GENERATED_DIR"]) / relative_path
    assert relative_path == "plans/student-3/plan-9.md"
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == content
```

- [ ] **Step 2: Run file tests and confirm failure**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_files.py -v
```

Expected: FAIL because `planning_files` does not exist.

- [ ] **Step 3: Add generated directory config**

Modify `app/config.py`:

```python
GENERATED_DIR = PROJECT_ROOT / "generated"
```

Inside `Config`:

```python
GENERATED_DIR = GENERATED_DIR
```

Modify `app/__init__.py` if needed so `create_app()` creates `app.config["GENERATED_DIR"]`.

- [ ] **Step 4: Implement file output**

Create `app/services/planning_files.py`:

```python
from pathlib import Path

from flask import current_app


def save_planning_markdown(student_id, document_id, title, content_markdown):
    relative_path = Path("plans") / f"student-{student_id}" / f"plan-{document_id}.md"
    destination = Path(current_app.config["GENERATED_DIR"]) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content_markdown, encoding="utf-8")
    return relative_path.as_posix()
```

- [ ] **Step 5: Run file tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_files.py -v
```

Expected: PASS.

- [ ] **Step 6: Update `.gitignore`**

Add:

```text
generated/
```

- [ ] **Step 7: Commit**

```bash
git add .gitignore app/config.py app/__init__.py app/services/planning_files.py tests/test_planning_files.py
git commit -m "feat: add planning file output"
```

## Task 4: Planning Routes And Templates

**Files:**
- Create: `app/routes/planning.py`
- Modify: `app/routes/__init__.py`
- Modify: `app/templates/students/detail.html`
- Create: `app/templates/planning/generate.html`
- Create: `app/templates/planning/detail.html`
- Create: `tests/test_planning_routes.py`

- [ ] **Step 1: Add failing route tests**

Create `tests/test_planning_routes.py`:

```python
from app import repositories


def seed_ready_student():
    student_id = repositories.create_student(
        {
            "name": "路由同学",
            "gender": "男",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "管理学院",
            "major": "工商管理",
        }
    )
    repositories.save_student_questionnaire(
        student_id,
        {"future_intentions": "保研优先，考研备选", "academic_status": "绩点稳定"},
    )
    repositories.save_parent_questionnaire(
        student_id,
        {
            "parent_name": "路女士",
            "relationship": "母亲",
            "family_resources": "家庭支持升学规划",
            "target_priorities": "保研第一，考研第二，就业第三",
        },
    )
    repositories.save_teacher_notes(
        student_id,
        {
            "goal_feasibility": "目标需要结合大一绩点判断",
            "ai_generation_focus": "保研第一，考研第二，就业第三",
        },
    )
    repositories.confirm_disclaimer(
        student_id,
        {
            "signer_type": "家长",
            "signer_name": "路女士",
            "reason": "确认基于当前信息生成初步规划。",
        },
    )
    return student_id


def test_generate_page_requires_ready_student(client, app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "未完成同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "英语",
            }
        )

    response = client.get(f"/students/{student_id}/planning/generate")

    assert response.status_code == 200
    assert "信息仍需补充".encode("utf-8") in response.data
    assert "生成初步规划".encode("utf-8") in response.data


def test_generate_initial_planning_document(client, app):
    with app.app_context():
        student_id = seed_ready_student()

    response = client.post(
        f"/students/{student_id}/planning/generate",
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "路由同学大学四年初步规划" in html
    assert "信息依据与免责声明" in html
    assert "目标风险、备选路径与责任边界" in html
    with app.app_context():
        documents = repositories.list_planning_documents(student_id)
    assert len(documents) == 1
    assert documents[0]["file_path"] == "plans/student-1/plan-1.md"
```

- [ ] **Step 2: Run route tests and confirm failure**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_routes.py -v
```

Expected: FAIL because planning route does not exist.

- [ ] **Step 3: Implement planning blueprint**

Create `app/routes/planning.py`:

```python
from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories
from app.services.completion import get_student_completion
from app.services.planning_files import save_planning_markdown
from app.services.planning_generator import build_planning_context, generate_initial_plan

planning_bp = Blueprint("planning", __name__, url_prefix="/students/<int:student_id>/planning")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@planning_bp.route("/generate", methods=("GET", "POST"))
def generate(student_id):
    student = require_student(student_id)
    completion = get_student_completion(student_id)

    if request.method == "POST":
        if not completion["ready_for_ai"]:
            return (
                render_template(
                    "planning/generate.html",
                    student=student,
                    completion=completion,
                    error="信息仍需补充，暂不能生成初步规划。",
                ),
                400,
            )

        draft = generate_initial_plan(build_planning_context(student_id))
        document_id = repositories.create_planning_document(student_id, draft)
        relative_path = save_planning_markdown(
            student_id,
            document_id,
            draft["title"],
            draft["content_markdown"],
        )
        repositories.update_planning_document_file_path(document_id, relative_path)
        return redirect(
            url_for(
                "planning.detail",
                student_id=student_id,
                document_id=document_id,
            )
        )

    return render_template(
        "planning/generate.html",
        student=student,
        completion=completion,
        error="",
    )


@planning_bp.get("/documents/<int:document_id>")
def detail(student_id, document_id):
    student = require_student(student_id)
    document = repositories.get_planning_document(document_id)
    if document is None or document["student_id"] != student_id:
        abort(404)
    return render_template("planning/detail.html", student=student, document=document)
```

- [ ] **Step 4: Register blueprint**

Modify `app/routes/__init__.py`:

```python
from .planning import planning_bp
```

Register:

```python
app.register_blueprint(planning_bp)
```

- [ ] **Step 5: Add planning templates**

Create `app/templates/planning/generate.html`:

```html
{% extends "base.html" %}

{% block title %}生成初步规划：{{ student.name }} - 学业规划工作台{% endblock %}

{% block content %}
  <section class="page-heading">
    <div>
      <p class="eyebrow">初步规划生成</p>
      <h1>生成初步规划：{{ student.name }}</h1>
      <p class="muted">系统将基于已填写信息生成 Markdown 初稿，并自动包含信息依据与免责声明。</p>
    </div>
    <a class="button secondary" href="{{ url_for('students.detail', student_id=student.id) }}">返回档案</a>
  </section>

  {% if error %}
    <p class="form-error" role="alert">{{ error }}</p>
  {% endif %}

  <section class="panel">
    <h2>生成前检查</h2>
    <dl class="info-list">
      <div><dt>学生问卷</dt><dd>{{ completion.student_questionnaire }}</dd></div>
      <div><dt>家长问卷</dt><dd>{{ completion.parent_questionnaire }}</dd></div>
      <div><dt>材料上传</dt><dd>{{ completion.materials }}</dd></div>
      <div><dt>免责确认</dt><dd>{{ completion.disclaimer }}</dd></div>
      <div><dt>教师沟通纪要</dt><dd>{{ completion.teacher_notes }}</dd></div>
    </dl>
    {% if completion.ready_for_ai %}
      <form method="post">
        <button class="button" type="submit">生成初步规划</button>
      </form>
    {% else %}
      <p class="empty">信息仍需补充，完成问卷、老师记录，并上传材料或确认免责后再生成。</p>
      <button class="button" disabled>生成初步规划</button>
    {% endif %}
  </section>
{% endblock %}
```

Create `app/templates/planning/detail.html`:

```html
{% extends "base.html" %}

{% block title %}{{ document["title"] }} - 学业规划工作台{% endblock %}

{% block content %}
  <section class="page-heading">
    <div>
      <p class="eyebrow">规划草稿</p>
      <h1>{{ document["title"] }}</h1>
      <p class="muted">状态：{{ document["status"] }}{% if document["file_path"] %} · 文件：{{ document["file_path"] }}{% endif %}</p>
    </div>
    <a class="button secondary" href="{{ url_for('students.detail', student_id=student.id) }}">返回档案</a>
  </section>

  <section class="panel">
    <pre class="markdown-preview">{{ document["content_markdown"] }}</pre>
  </section>
{% endblock %}
```

- [ ] **Step 6: Add student detail entry point**

Modify `app/templates/students/detail.html` inside the action list:

```html
<a class="button" href="{{ url_for('planning.generate', student_id=student.id) }}">生成初步规划</a>
```

If the current template uses icon buttons, match the existing button style and text.

- [ ] **Step 7: Add preview styles**

Modify `app/static/styles.css`:

```css
.markdown-preview {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font: 14px/1.7 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
```

- [ ] **Step 8: Run route tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_routes.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/routes/planning.py app/routes/__init__.py app/templates/planning app/templates/students/detail.html app/static/styles.css tests/test_planning_routes.py
git commit -m "feat: add planning generation workflow"
```

## Task 5: Dashboard And Student Detail Planning Document Visibility

**Files:**
- Modify: `app/routes/students.py`
- Modify: `app/templates/students/detail.html`
- Create: `tests/test_planning_visibility.py`

- [ ] **Step 1: Add failing visibility tests**

Create `tests/test_planning_visibility.py`:

```python
from app import repositories


def test_student_detail_shows_existing_planning_documents(client, app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "可见同学",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "示例大学",
                "major": "法学",
            }
        )
        repositories.create_planning_document(
            student_id,
            {
                "title": "可见同学大学四年初步规划",
                "content_markdown": "# 可见同学大学四年初步规划",
                "file_path": "plans/student-1/plan-1.md",
            },
        )

    response = client.get(f"/students/{student_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "已有规划草稿" in html
    assert "可见同学大学四年初步规划" in html
    assert "plans/student-1/plan-1.md" in html
```

- [ ] **Step 2: Run visibility test and confirm failure**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_visibility.py -v
```

Expected: FAIL because detail route does not pass planning documents.

- [ ] **Step 3: Pass documents to student detail**

Modify `app/routes/students.py` detail route:

```python
planning_documents=repositories.list_planning_documents(student_id),
```

- [ ] **Step 4: Render documents**

Modify `app/templates/students/detail.html`:

```html
<section class="panel">
  <div class="panel-header">
    <h2>已有规划草稿</h2>
    <a class="button secondary" href="{{ url_for('planning.generate', student_id=student.id) }}">生成初步规划</a>
  </div>
  {% if planning_documents %}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>状态</th>
            <th>文件</th>
          </tr>
        </thead>
        <tbody>
          {% for document in planning_documents %}
            <tr>
              <td><a href="{{ url_for('planning.detail', student_id=student.id, document_id=document['id']) }}">{{ document["title"] }}</a></td>
              <td>{{ document["status"] }}</td>
              <td>{{ document["file_path"] or "未保存" }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% else %}
    <p class="empty">暂无规划草稿。</p>
  {% endif %}
</section>
```

Place the section below the information-completion panel or near the action panel.

- [ ] **Step 5: Run visibility tests**

Run:

```bash
. .venv/bin/activate
python -m pytest tests/test_planning_visibility.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/students.py app/templates/students/detail.html tests/test_planning_visibility.py
git commit -m "feat: show planning drafts on student detail"
```

## Task 6: README And Smoke Test

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add to `README.md` under first-stage contents:

```markdown
第二阶段实现内容：

- 初步规划草稿生成
- 信息依据与免责声明自动写入规划草稿
- 目标风险、备选路径与责任边界章节
- 本地 Markdown 文件保存
- 学生详情页查看已有规划草稿
```

Add this generated-file note:

````markdown
生成的规划草稿默认保存到：

```text
generated/plans/student-<学生ID>/plan-<规划ID>.md
```
````

- [ ] **Step 2: Run full tests**

Run:

```bash
. .venv/bin/activate
python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Manual smoke test**

Run local server:

```bash
. .venv/bin/activate
python run.py
```

Open:

```text
http://127.0.0.1:5050
```

Verify:

- Student detail page has `生成初步规划`.
- Incomplete student sees generation blocked with `信息仍需补充`.
- Complete student can generate draft.
- Draft page shows `信息依据与免责声明`.
- Draft page shows `目标风险、备选路径与责任边界`.
- Local file exists under `generated/plans/student-<id>/plan-<id>.md`.

Stop the server after the smoke test.

- [ ] **Step 4: Commit and push**

```bash
git add README.md
git commit -m "docs: add planning generation runbook"
git push
```

## Final Verification

Before claiming Milestone 2 complete, run:

```bash
. .venv/bin/activate
python -m pytest -v
git status -sb
git log --oneline -12
```

Expected:

- All tests pass.
- Worktree contains no uncommitted changes except pre-existing user changes that were explicitly kept out of this milestone.
- Branch is pushed to `origin/codex/milestone-1` unless a new branch was created before execution.

## Self-Review

Spec coverage:

- Planning document persistence: Task 1.
- Initial draft generation: Task 2.
- Disclaimer and responsibility-boundary content inside draft: Task 2.
- Local Markdown output: Task 3.
- Teacher-facing generate and preview pages: Task 4.
- Student detail entry point and draft list: Task 4 and Task 5.
- README and smoke test: Task 6.

Scope check:

- Live AI integration is intentionally excluded.
- Word/PDF export is intentionally excluded.
- Rich text editing is intentionally excluded.
- Billing is intentionally excluded.

Type consistency:

- Planning routes use endpoint names `planning.generate` and `planning.detail`.
- Planning repository functions use `document_id` for planning document IDs.
- File output returns a relative path stored in `planning_documents.file_path`.
