from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for

from app import repositories
from app.services.uploads import save_upload

questionnaires_bp = Blueprint("questionnaires", __name__, url_prefix="/students/<int:student_id>")


def require_student(student_id):
    student = repositories.get_student(student_id)
    if student is None:
        abort(404)
    return student


@questionnaires_bp.route("/student-questionnaire", methods=("GET", "POST"))
def student_questionnaire(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        repositories.save_student_questionnaire(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))

    return render_template(
        "questionnaires/student.html",
        student=student,
        questionnaire=repositories.get_student_questionnaire(student_id),
    )


@questionnaires_bp.route("/parent-questionnaire", methods=("GET", "POST"))
def parent_questionnaire(student_id):
    student = require_student(student_id)
    if request.method == "POST":
        repositories.save_parent_questionnaire(student_id, request.form)
        return redirect(url_for("students.detail", student_id=student_id))

    questionnaire = repositories.get_parent_questionnaire(student_id)
    parent_contact = None
    if questionnaire is None:
        parent_contact = repositories.get_primary_parent_contact(student_id)

    return render_template(
        "questionnaires/parent.html",
        student=student,
        questionnaire=questionnaire,
        parent_contact=parent_contact,
    )


@questionnaires_bp.get("/disclaimer-template")
def disclaimer_template(student_id):
    student = require_student(student_id)
    from datetime import date
    today = date.today()
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>学业规划服务免责协议 — {student.name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "SimSun", "宋体", serif;
    font-size: 14px;
    line-height: 2;
    color: #000;
    padding: 40px 60px;
    max-width: 800px;
    margin: 0 auto;
  }}
  h1 {{ text-align: center; font-size: 20px; letter-spacing: 4px; margin-bottom: 8px; }}
  .subtitle {{ text-align: center; font-size: 13px; color: #555; margin-bottom: 32px; }}
  h2 {{ font-size: 15px; margin: 24px 0 8px; }}
  p {{ text-indent: 2em; margin-bottom: 8px; }}
  .blank {{ display: inline-block; border-bottom: 1px solid #000; min-width: 120px; }}
  .sign-section {{
    margin-top: 48px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 32px;
  }}
  .sign-block {{ line-height: 2.5; }}
  .sign-line {{ border-bottom: 1px solid #000; display: inline-block; width: 160px; }}
  @media print {{
    body {{ padding: 20px 40px; }}
    @page {{ size: A4; margin: 20mm 15mm; }}
  }}
</style>
</head>
<body>
<h1>学业规划服务免责协议</h1>
<p class="subtitle">本协议由学生及家长与规划老师共同确认后签署</p>

<h2>一、协议各方</h2>
<p>学生姓名：<span class="blank">{student.name}</span>&emsp;
   就读学校：<span class="blank">{student.school or ''}</span>&emsp;
   当前学期：<span class="blank">{student.current_term or ''}</span></p>
<p>家长/监护人姓名：<span class="blank" style="min-width:150px;">&nbsp;</span>&emsp;
   与学生关系：<span class="blank">&nbsp;</span></p>
<p>规划老师姓名：<span class="blank">&nbsp;</span></p>

<h2>二、服务内容说明</h2>
<p>规划老师将根据学生已提供的问卷信息、学业材料及沟通记录，为学生提供学业方向规划建议，包括但不限于目标设定、路径分析、时间规划及备选方案。</p>

<h2>三、免责声明</h2>
<p>1. 本规划方案基于学生和家长提供的信息生成，规划老师将尽力提供专业建议，但不对最终升学、就业等具体结果作出承诺或担保。</p>
<p>2. 学生和家长应如实提供相关信息。因信息不实、不完整或后续执行不到位导致的规划效果偏差，规划老师不承担责任。</p>
<p>3. 学业规划受学生个人能力、学校政策、招生变化等外部因素影响，规划老师不对上述不可控因素承担责任。</p>
<p>4. 在材料尚未完整提交的情况下，经家长/学生书面确认后，规划老师可先行生成初步规划草稿，该草稿具有参考价值，不构成最终结果承诺。</p>
<p>5. 双方均同意在规划过程中保持积极沟通，如有异议应及时提出，通过协商解决。</p>

<h2>四、协议生效</h2>
<p>本协议自家长/学生签字之日起生效。本协议一式两份，双方各执一份，或以扫描件/照片上传系统备档。</p>
<p>签署日期：&nbsp;&nbsp;{today.year}&nbsp; 年 &nbsp;<span class="blank" style="min-width:40px;">&nbsp;</span>&nbsp; 月 &nbsp;<span class="blank" style="min-width:40px;">&nbsp;</span>&nbsp; 日</p>

<div class="sign-section">
  <div class="sign-block">
    <p><strong>家长/监护人签字</strong></p>
    <p>签名：<span class="sign-line">&nbsp;</span></p>
    <p>日期：<span class="sign-line">&nbsp;</span></p>
  </div>
  <div class="sign-block">
    <p><strong>规划老师签字</strong></p>
    <p>签名：<span class="sign-line">&nbsp;</span></p>
    <p>日期：<span class="sign-line">&nbsp;</span></p>
  </div>
</div>

<p style="margin-top:40px; font-size:12px; color:#666; text-indent:0;">
  打印本协议后请双方签字，签字版扫描为 PDF 后上传至系统备档。
</p>
</body>
</html>"""
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@questionnaires_bp.route("/materials", methods=("GET", "POST"))

def materials(student_id):
    student = require_student(student_id)
    error = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            material = request.files.get("material")
            if material and material.filename:
                try:
                    stored_filename = save_upload(student_id, material)
                except ValueError as exc:
                    error = str(exc)
                else:
                    repositories.create_material(
                        student_id,
                        {
                            "uploader_type": request.form.get("uploader_type", ""),
                            "category": request.form.get("category", "其他材料"),
                            "original_filename": material.filename,
                            "stored_filename": stored_filename,
                        },
                    )
                    return redirect(
                        url_for("questionnaires.materials", student_id=student_id)
                    )
        elif action == "disclaimer":
            disclaimer_data = {
                "signer_type": request.form.get("signer_type", "").strip(),
                "signer_name": request.form.get("signer_name", "").strip(),
                "reason": request.form.get("reason", "").strip(),
            }
            if not all(disclaimer_data.values()):
                error = "免责确认信息不能为空，请填写确认人类型、确认人姓名和确认原因。"
                return (
                    render_template(
                        "questionnaires/materials.html",
                        student=student,
                        materials=repositories.list_materials(student_id),
                        disclaimers=repositories.list_disclaimers(student_id),
                        error=error,
                    ),
                    400,
                )

            repositories.confirm_disclaimer(student_id, disclaimer_data)
            return redirect(url_for("questionnaires.materials", student_id=student_id))

    return render_template(
        "questionnaires/materials.html",
        student=student,
        materials=repositories.list_materials(student_id),
        disclaimers=repositories.list_disclaimers(student_id),
        error=error,
    )
