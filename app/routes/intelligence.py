import sqlite3

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from app import repositories
from app.auth import role_required
from app.services.intelligence_collection import (
    CollectionError,
    collect_source,
    validate_public_url,
)


intelligence_bp = Blueprint("intelligence", __name__)


def _actor_id():
    return g.current_user["id"] if g.current_user is not None else None


def _audit(action, target_type, target_id=None, details=""):
    repositories.create_audit_log(
        _actor_id(), action, target_type, target_id, details, request.remote_addr or ""
    )


@intelligence_bp.get("/knowledge")
def knowledge_index():
    can_edit = g.current_user and g.current_user["role"] in ("admin", "teacher")
    return render_template(
        "intelligence/knowledge.html",
        majors=repositories.list_knowledge_majors(),
        jobs=repositories.list_knowledge_jobs(),
        skills=repositories.list_knowledge_skills(),
        graph_links=repositories.list_knowledge_graph_links(),
        job_skill_links=repositories.list_job_skill_links(),
        sources=repositories.list_intelligence_sources() if can_edit else [],
        users=repositories.list_users() if can_edit else [],
        message=request.args.get("message", ""),
    )


@intelligence_bp.post("/knowledge/majors")
@role_required("admin", "teacher")
def create_major():
    if not request.form.get("name", "").strip():
        return redirect(url_for("intelligence.knowledge_index", message="专业名称不能为空"))
    try:
        record_id = repositories.create_knowledge_major(request.form, _actor_id())
    except sqlite3.IntegrityError:
        return redirect(url_for("intelligence.knowledge_index", message="该专业已经存在"))
    _audit("create_knowledge_major", "knowledge_major", record_id)
    return redirect(url_for("intelligence.knowledge_index", message="专业条目已保存为草稿"))


@intelligence_bp.post("/knowledge/jobs")
@role_required("admin", "teacher")
def create_job():
    if not request.form.get("name", "").strip():
        return redirect(url_for("intelligence.knowledge_index", message="岗位名称不能为空"))
    try:
        record_id = repositories.create_knowledge_job(request.form, _actor_id())
    except sqlite3.IntegrityError:
        return redirect(url_for("intelligence.knowledge_index", message="该岗位已经存在"))
    _audit("create_knowledge_job", "knowledge_job", record_id)
    return redirect(url_for("intelligence.knowledge_index", message="岗位条目已保存为草稿"))


@intelligence_bp.post("/knowledge/skills")
@role_required("admin", "teacher")
def create_skill():
    if not request.form.get("name", "").strip():
        return redirect(url_for("intelligence.knowledge_index", message="技能名称不能为空"))
    try:
        record_id = repositories.create_knowledge_skill(request.form, _actor_id())
    except sqlite3.IntegrityError:
        return redirect(url_for("intelligence.knowledge_index", message="该技能已经存在"))
    _audit("create_knowledge_skill", "knowledge_skill", record_id)
    return redirect(url_for("intelligence.knowledge_index", message="技能条目已保存为草稿"))


@intelligence_bp.post("/knowledge/major-job-links")
@role_required("admin", "teacher")
def create_major_job_link():
    if not request.form.get("major_id") or not request.form.get("job_id"):
        return redirect(url_for("intelligence.knowledge_index", message="请选择专业和岗位"))
    record_id = repositories.create_major_job_link(request.form, _actor_id())
    _audit("link_major_job", "major_job_link", record_id)
    return redirect(url_for("intelligence.knowledge_index", message="专业与岗位关系已保存"))


@intelligence_bp.post("/knowledge/job-skill-links")
@role_required("admin", "teacher")
def create_job_skill_link():
    if not request.form.get("job_id") or not request.form.get("skill_id"):
        return redirect(url_for("intelligence.knowledge_index", message="请选择岗位和技能"))
    try:
        record_id = repositories.create_job_skill_link(request.form, _actor_id())
    except ValueError as exc:
        return redirect(url_for("intelligence.knowledge_index", message=str(exc)))
    _audit("link_job_skill", "job_skill_link", record_id)
    return redirect(url_for("intelligence.knowledge_index", message="岗位与技能关系已保存为草稿"))


@intelligence_bp.post("/knowledge/job-skill-links/<int:link_id>/submit")
@role_required("admin", "teacher")
def submit_job_skill_link(link_id):
    try:
        repositories.submit_job_skill_link(link_id)
    except ValueError as exc:
        return redirect(url_for("intelligence.knowledge_index", message=str(exc)))
    _audit("submit_job_skill_link", "job_skill_link", link_id)
    return redirect(url_for("intelligence.knowledge_index", message="岗位技能证据已提交审核"))


@intelligence_bp.post("/knowledge/job-skill-links/<int:link_id>/review")
@role_required("admin")
def review_job_skill_link(link_id):
    if repositories.get_job_skill_link(link_id) is None:
        abort(404)
    status = request.form.get("status", "")
    try:
        repositories.review_job_skill_link(link_id, status)
    except ValueError:
        abort(400)
    _audit("review_job_skill_link", "job_skill_link", link_id, f"status={status}")
    return redirect(url_for("intelligence.knowledge_index", message=f"岗位技能证据状态已更新为{status}"))


@intelligence_bp.post("/knowledge/<kind>/<int:record_id>/status")
@role_required("admin")
def update_knowledge_status(kind, record_id):
    status = request.form.get("status", "")
    try:
        repositories.update_knowledge_status(kind, record_id, status)
    except ValueError:
        abort(400)
    _audit("review_knowledge", f"knowledge_{kind}", record_id, f"status={status}")
    return redirect(url_for("intelligence.knowledge_index", message=f"条目状态已更新为{status}"))


@intelligence_bp.get("/exams")
def exams_index():
    return render_template(
        "intelligence/exams.html",
        exams=repositories.list_exam_information(),
    )


@intelligence_bp.route("/exams/new", methods=("GET", "POST"))
@role_required("admin", "teacher")
def exam_new():
    if request.method == "POST":
        if not request.form.get("exam_name", "").strip():
            return render_template(
                "intelligence/exam_form.html", exam=None,
                users=repositories.list_users(), error="考试名称不能为空",
            )
        exam_id = repositories.create_exam_information(request.form, _actor_id())
        _audit("create_exam_information", "exam_information", exam_id)
        return redirect(url_for("intelligence.exam_detail", exam_id=exam_id))
    return render_template(
        "intelligence/exam_form.html", exam=None,
        users=repositories.list_users(), error="",
    )


@intelligence_bp.get("/exams/<int:exam_id>")
def exam_detail(exam_id):
    exam = repositories.get_exam_information(exam_id)
    if exam is None:
        abort(404)
    return render_template(
        "intelligence/exam_detail.html",
        exam=exam,
        revisions=repositories.list_exam_revisions(exam_id),
    )


@intelligence_bp.route("/exams/<int:exam_id>/edit", methods=("GET", "POST"))
@role_required("admin", "teacher")
def exam_edit(exam_id):
    exam = repositories.get_exam_information(exam_id)
    if exam is None:
        abort(404)
    if request.method == "POST":
        if not request.form.get("exam_name", "").strip():
            return render_template(
                "intelligence/exam_form.html", exam=exam,
                users=repositories.list_users(), error="考试名称不能为空",
            )
        repositories.update_exam_information(exam_id, request.form, _actor_id())
        _audit("update_exam_information", "exam_information", exam_id,
               request.form.get("change_summary", ""))
        return redirect(url_for("intelligence.exam_detail", exam_id=exam_id))
    return render_template(
        "intelligence/exam_form.html", exam=exam,
        users=repositories.list_users(), error="",
    )


@intelligence_bp.post("/exams/<int:exam_id>/submit")
@role_required("admin", "teacher")
def exam_submit(exam_id):
    exam = repositories.get_exam_information(exam_id)
    if exam is None:
        abort(404)
    if not exam["official_url"] or not exam["reviewer_user_id"] or not exam["next_check_at"]:
        return redirect(url_for("intelligence.exam_detail", exam_id=exam_id, error="提交前请填写官网、审核人和下次核查时间"))
    repositories.update_exam_status(exam_id, "待审核")
    _audit("submit_exam_review", "exam_information", exam_id)
    return redirect(url_for("intelligence.exam_detail", exam_id=exam_id))


@intelligence_bp.post("/exams/<int:exam_id>/review")
@role_required("admin")
def exam_review(exam_id):
    status = request.form.get("status", "")
    if status not in ("已发布", "已退回", "已过期"):
        abort(400)
    if repositories.get_exam_information(exam_id) is None:
        abort(404)
    repositories.update_exam_status(exam_id, status)
    _audit("review_exam_information", "exam_information", exam_id, f"status={status}")
    return redirect(url_for("intelligence.exam_detail", exam_id=exam_id))


@intelligence_bp.get("/industries")
def industries_index():
    return render_template(
        "intelligence/industries.html",
        industries=repositories.list_industries(),
        trends=repositories.list_industry_trends(),
        sources=repositories.list_intelligence_sources(),
        users=repositories.list_users() if g.current_user and g.current_user["role"] in ("admin", "teacher") else [],
        message=request.args.get("message", ""),
        error=request.args.get("error", ""),
    )


@intelligence_bp.post("/industries")
@role_required("admin", "teacher")
def create_industry():
    if not request.form.get("name", "").strip():
        return redirect(url_for("intelligence.industries_index", error="产业名称不能为空"))
    try:
        industry_id = repositories.create_industry(request.form, _actor_id())
    except sqlite3.IntegrityError:
        return redirect(url_for("intelligence.industries_index", error="该产业已经存在"))
    _audit("create_industry", "industry", industry_id)
    return redirect(url_for("intelligence.industries_index", message="产业条目已保存为草稿"))


@intelligence_bp.post("/industries/<int:industry_id>/status")
@role_required("admin")
def review_industry(industry_id):
    status = request.form.get("status", "")
    try:
        repositories.update_industry_status(industry_id, status)
    except ValueError:
        abort(400)
    _audit("review_industry", "industry", industry_id, f"status={status}")
    return redirect(url_for("intelligence.industries_index", message=f"产业状态已更新为{status}"))


@intelligence_bp.post("/intelligence-sources")
@role_required("admin")
def create_source():
    if not request.form.get("name", "").strip() or not request.form.get("url", "").strip():
        return redirect(url_for("intelligence.industries_index", error="数据源名称和链接不能为空"))
    try:
        validate_public_url(request.form["url"])
        source_id = repositories.create_intelligence_source(request.form, _actor_id())
    except CollectionError as exc:
        return redirect(url_for("intelligence.industries_index", error=str(exc)))
    except sqlite3.IntegrityError:
        return redirect(url_for("intelligence.industries_index", error="该数据源链接已经存在"))
    _audit("create_intelligence_source", "intelligence_source", source_id)
    return redirect(url_for("intelligence.source_detail", source_id=source_id))


@intelligence_bp.get("/intelligence-sources/<int:source_id>")
def source_detail(source_id):
    source = repositories.get_intelligence_source(source_id)
    if source is None:
        abort(404)
    return render_template(
        "intelligence/source_detail.html",
        source=source,
        snapshots=repositories.list_intelligence_snapshots(source_id),
        message=request.args.get("message", ""),
        error=request.args.get("error", ""),
    )


@intelligence_bp.post("/intelligence-sources/<int:source_id>/collect")
@role_required("admin", "teacher")
def collect_intelligence_source(source_id):
    if repositories.get_intelligence_source(source_id) is None:
        abort(404)
    snapshot_id, change_status, collection_error = collect_source(source_id, _actor_id())
    _audit("collect_intelligence_source", "intelligence_source", source_id,
           f"snapshot={snapshot_id},status={change_status}")
    if collection_error:
        return redirect(url_for("intelligence.source_detail", source_id=source_id,
                                error=collection_error))
    return redirect(url_for("intelligence.source_detail", source_id=source_id,
                            message=f"采集完成：{change_status}"))


@intelligence_bp.post("/industry-trends")
@role_required("admin", "teacher")
def create_industry_trend():
    if not request.form.get("industry_id") or not request.form.get("title", "").strip():
        return redirect(url_for("intelligence.industries_index", error="请选择产业并填写趋势标题"))
    trend_id = repositories.create_industry_trend(request.form, _actor_id())
    _audit("create_industry_trend", "industry_trend", trend_id)
    return redirect(url_for("intelligence.industries_index", message="产业趋势已保存为草稿"))


@intelligence_bp.post("/industry-trends/<int:trend_id>/submit")
@role_required("admin", "teacher")
def submit_industry_trend(trend_id):
    trend = repositories.get_industry_trend(trend_id)
    if trend is None:
        abort(404)
    if (not trend["reviewer_user_id"] or not trend["next_check_at"] or
            not trend["evidence_summary"] or
            not (trend["source_id"] or trend["source_url"])):
        return redirect(url_for("intelligence.industries_index",
                                error="提交前请补齐依据、来源、审核人和下次核查时间"))
    repositories.update_industry_trend_status(trend_id, "待审核")
    _audit("submit_industry_trend", "industry_trend", trend_id)
    return redirect(url_for("intelligence.industries_index", message="产业趋势已提交审核"))


@intelligence_bp.post("/industry-trends/<int:trend_id>/review")
@role_required("admin")
def review_industry_trend(trend_id):
    status = request.form.get("status", "")
    if status not in ("已发布", "已退回", "已过期"):
        abort(400)
    if repositories.get_industry_trend(trend_id) is None:
        abort(404)
    repositories.update_industry_trend_status(trend_id, status)
    _audit("review_industry_trend", "industry_trend", trend_id, f"status={status}")
    return redirect(url_for("intelligence.industries_index", message=f"趋势状态已更新为{status}"))
