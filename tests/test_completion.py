from app import repositories
from app.services.completion import get_student_completion


def create_sample_student():
    return repositories.create_student(
        {
            "name": "赵同学",
            "gender": "女",
            "enrollment_year": "2026",
            "current_term": "大一上",
            "school": "示例大学",
            "college": "法学院",
            "major": "法学",
            "city": "上海",
            "phone": "13800000008",
            "service_stage": "信息收集",
            "responsible_teacher": "王老师",
        }
    )


def test_student_completion_ready_after_required_inputs(app):
    with app.app_context():
        student_id = create_sample_student()

        completion = get_student_completion(student_id)

        assert completion["ready_for_ai"] is False

        repositories.save_student_questionnaire(
            student_id,
            {
                "adaptation_status": "适应良好",
                "academic_status": "成绩稳定",
                "weak_subjects": "数学",
                "tutoring_needs": "学习复盘",
                "interests_strengths": "表达能力强",
                "future_intentions": "保研优先",
                "motivation_status": "目标明确",
            },
        )
        repositories.save_parent_questionnaire(
            student_id,
            {
                "parent_name": "赵女士",
                "relationship": "母亲",
                "parent_phone": "13900000008",
                "communication_method": "微信",
                "family_resources": "家庭支持稳定",
                "target_priorities": "保研第一",
                "parent_observations": "孩子自驱力较强",
                "current_concerns": "科研经历不足",
                "investment_willingness": "愿意投入",
            },
        )
        repositories.save_teacher_notes(
            student_id,
            {
                "source_channel": "家长咨询",
                "consultation_stage": "初诊",
                "core_request": "明确保研路径",
                "family_student_conflict": "目标基本一致",
                "resource_match_level": "支持较强",
                "goal_feasibility": "需要保持绩点",
                "execution_risk": "需要阶段复盘",
                "academic_risk": "数学基础需观察",
                "transfer_feasibility": "暂不转专业",
                "service_suggestions": "先做学业节奏管理",
                "ai_generation_focus": "保研路径",
            },
        )
        repositories.confirm_disclaimer(
            student_id,
            {
                "signer_type": "家长",
                "signer_name": "赵女士",
                "reason": "当前材料暂缺，先基于已填写信息生成规划。",
            },
        )

        completion = get_student_completion(student_id)

        assert completion["ready_for_ai"] is True
