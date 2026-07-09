import pytest

from app import repositories
from app.services.planning_generator import (
    build_planning_context,
    generate_information_basis,
    generate_initial_plan,
)


def seed_ready_student(include_materials=False):
    student_id = repositories.create_student(
        {
            "name": "陈同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "经济管理学院",
            "major": "工商管理",
            "city": "上海",
            "phone": "13800000000",
            "service_stage": "初步规划",
            "responsible_teacher": "王老师",
        }
    )
    repositories.save_student_questionnaire(
        student_id,
        {
            "adaptation_status": "刚入学，对大学节奏仍在适应。",
            "academic_status": "英语基础较好，高等数学压力较大。",
            "weak_subjects": "高等数学",
            "tutoring_needs": "需要每周学科辅导和学习计划检查。",
            "interests_strengths": "沟通表达较好，愿意参加商赛。",
            "future_intentions": "希望优先保研，同时关注转入金融专业。",
            "motivation_status": "目标感较强，但执行稳定性一般。",
        },
    )
    repositories.save_parent_questionnaire(
        student_id,
        {
            "parent_name": "陈女士",
            "relationship": "母亲",
            "parent_phone": "13900000000",
            "communication_method": "微信",
            "family_resources": "家庭可提供竞赛、科研、语言考试和升学咨询资源。",
            "target_priorities": "保研第一，考研第二，就业第三",
            "parent_observations": "孩子自律性需要外部督促。",
            "current_concerns": "担心高数影响绩点，也担心转专业窗口错过。",
            "investment_willingness": "愿意投入必要辅导费用，但需明确费用边界。",
        },
    )
    repositories.save_teacher_notes(
        student_id,
        {
            "source_channel": "线下面谈",
            "consultation_stage": "初次规划",
            "core_request": "围绕保研、转专业和学业补弱建立四年路径。",
            "family_student_conflict": "家长目标较高，学生更担心短期课程压力。",
            "resource_match_level": "资源较充足，但需要聚焦使用。",
            "goal_feasibility": "保研目标可作为第一目标，但需持续观察绩点排名。",
            "execution_risk": "执行风险中等，需要月度复盘。",
            "academic_risk": "高等数学是当前主要学业风险。",
            "transfer_feasibility": "可关注金融专业转入要求和时间节点。",
            "service_suggestions": "先稳绩点，再补竞赛和科研。",
            "ai_generation_focus": "突出家庭资源、目标排序、转专业和风险边界。",
        },
    )
    repositories.confirm_disclaimer(
        student_id,
        {
            "signer_type": "家长",
            "signer_name": "陈女士",
            "reason": "知悉规划不承诺结果",
        },
    )
    if include_materials:
        repositories.create_material(
            student_id,
            {
                "uploader_type": "student",
                "original_filename": "陈同学-成绩单.pdf",
                "stored_filename": "student-1-transcript.pdf",
                "category": "成绩单",
            },
        )
    return student_id


def test_generate_initial_plan_contains_core_sections(app):
    with app.app_context():
        student_id = seed_ready_student()
        context = build_planning_context(student_id)
        draft = generate_initial_plan(context)

    assert "陈同学大学四年初步规划" in draft["title"]
    content_markdown = draft["content_markdown"]
    assert "# 陈同学大学四年初步规划" in content_markdown
    assert "## 二、信息依据与免责声明" in content_markdown
    assert "不构成保研、录取、转专业、就业或考试结果承诺" in content_markdown
    assert "## 三、家庭资源与升学目标分析" in content_markdown
    assert "保研第一，考研第二，就业第三" in content_markdown
    assert "## 四、学业基础与学科辅导建议" in content_markdown
    assert "高等数学" in content_markdown
    assert "## 五、专业适应与转专业目标建议" in content_markdown
    assert "## 八、目标风险、备选路径与责任边界" in content_markdown
    assert "第二路径" in content_markdown
    assert "费用边界" in content_markdown


def test_build_planning_context_rejects_missing_student(app):
    with app.app_context(), pytest.raises(ValueError, match="学生不存在"):
        build_planning_context(999)


def test_information_basis_lists_uploaded_materials(app):
    with app.app_context():
        student_id = seed_ready_student(include_materials=True)
        context = build_planning_context(student_id)
        information_basis = generate_information_basis(context)

    assert "当前已上传材料" in information_basis
    assert "陈同学-成绩单.pdf" in information_basis
    assert "已确认免责。" in information_basis


def test_information_basis_notes_missing_materials_with_confirmed_disclaimer(app):
    with app.app_context():
        student_id = seed_ready_student()
        context = build_planning_context(student_id)
        information_basis = generate_information_basis(context)

    assert "当前未上传关键材料。" in information_basis
    assert "已确认免责。" in information_basis
