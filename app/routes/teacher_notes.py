from flask import Blueprint, abort, redirect, render_template, request, url_for

from app import repositories

teacher_notes_bp = Blueprint(
    "teacher_notes", __name__, url_prefix="/students/<int:student_id>/teacher-notes"
)

NOTE_FIELDS = [
    ("source_channel", "来源渠道"),
    ("consultation_stage", "咨询阶段"),
    ("core_request", "核心诉求"),
    ("family_student_conflict", "家庭与学生冲突"),
    ("resource_match_level", "资源匹配程度"),
    ("goal_feasibility", "目标可行性"),
    ("execution_risk", "执行风险"),
    ("academic_risk", "学业风险"),
    ("transfer_feasibility", "转专业可行性"),
    ("service_suggestions", "服务建议"),
    ("ai_generation_focus", "AI 生成关注点"),
]

NOTE_PLACEHOLDER = """建议记录时覆盖以下内容，可直接口述或按条填写：

来源渠道：例如家长首次咨询、学生主动咨询、转介绍等
咨询阶段：例如初诊、方案沟通、复盘、签约前确认等
核心诉求：家庭和学生最想解决的问题是什么
家庭与学生冲突：目标、预算、执行方式、专业选择是否存在分歧
资源匹配程度：家庭时间、预算、行业资源、陪伴能力是否支持目标
目标可行性：保研、考研、留学、就业、转专业等目标的初步判断
执行风险：自律性、拖延、情绪、时间管理、配合度等
学业风险：挂科风险、薄弱科目、绩点压力、关键课程风险等
转专业可行性：目标专业、窗口期、课程门槛、替代路径等
服务建议：基础规划、学科辅导、转专业、竞赛科研、就业等建议
AI 生成关注点：希望生成规划时重点强调什么"""


@teacher_notes_bp.route("", methods=("GET", "POST"))
def edit(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)

    if request.method == "POST":
        structured_fields = [field for field, _label in NOTE_FIELDS]
        has_split_fields = any(
            field in request.form for field in structured_fields
        )
        if has_split_fields:
            # 旧式分字段提交：直接从 form 中读取各字段
            data = {field: request.form.get(field, "") for field in structured_fields}
            data["combined_notes"] = request.form.get("combined_notes", "")
        else:
            # 新式综合纪要提交：解析 combined_notes 文本
            data = parse_combined_notes(request.form.get("combined_notes", ""))
        repositories.save_teacher_notes(student_id, data)
        return redirect(url_for("students.detail", student_id=student_id))

    notes = repositories.get_teacher_notes(student_id)
    return render_template(
        "teacher_notes/edit.html",
        student=student,
        combined_notes=format_combined_notes(notes),
        note_placeholder=NOTE_PLACEHOLDER,
    )


def format_combined_notes(notes):
    if not notes:
        return ""
    if "combined_notes" in notes.keys() and notes["combined_notes"]:
        return notes["combined_notes"]
    lines = []
    for field, label in NOTE_FIELDS:
        value = notes[field].strip() if notes[field] else ""
        if value:
            lines.append(f"{label}：{value}")
    return "\n".join(lines)


def parse_combined_notes(text):
    content = (text or "").strip()
    parsed = {field: "" for field, _label in NOTE_FIELDS}
    parsed["combined_notes"] = content
    if not content:
        return parsed

    label_to_field = {label: field for field, label in NOTE_FIELDS}
    current_field = None
    fallback_lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matched_field = None
        matched_value = ""
        for label, field in label_to_field.items():
            if line.startswith(f"{label}：") or line.startswith(f"{label}:"):
                matched_field = field
                matched_value = (
                    line.split("：", 1)[1]
                    if "：" in line
                    else line.split(":", 1)[1]
                )
                break
        if matched_field:
            current_field = matched_field
            parsed[current_field] = _append_line(
                parsed[current_field], matched_value.strip()
            )
        elif current_field:
            parsed[current_field] = _append_line(parsed[current_field], line)
        else:
            fallback_lines.append(line)

    fallback_text = "\n".join(fallback_lines).strip()
    has_structured_values = any(parsed[field] for field, _label in NOTE_FIELDS)
    if fallback_text and not has_structured_values:
        parsed["core_request"] = fallback_text
        parsed["ai_generation_focus"] = fallback_text
    elif fallback_text:
        parsed["core_request"] = _append_line(parsed["core_request"], fallback_text)
    return parsed


def _append_line(existing, line):
    if not line:
        return existing
    if not existing:
        return line
    return f"{existing}\n{line}"
