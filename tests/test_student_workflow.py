from app import repositories
from app.services import student_goals
from app.services.student_workflow import build_student_workflow


def test_student_workflow_orders_intelligence_before_diagnosis(app):
    with app.app_context():
        student_id = repositories.create_student(
            {
                "name": "流程测试员",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "测试大学",
                "college": "测试学院",
                "major": "测试专业",
                "city": "上海",
                "phone": "",
                "service_stage": "信息收集",
                "responsible_teacher": "测试老师",
            }
        )

        workflow = build_student_workflow(student_id)

        assert [stage["title"] for stage in workflow["stages"][:4]] == [
            "信息采集",
            "目标与情报",
            "诊断访谈",
            "形成规划",
        ]


def test_student_workflow_exposes_goal_aware_stage_two(app):
    with app.app_context():
        student_id = student_goals.create_student_with_goal(
            {
                "name": "就业流程测试员",
                "gender": "女",
                "enrollment_year": "2026",
                "current_term": "大一上",
                "school": "测试大学",
                "college": "测试学院",
                "major": "测试专业",
                "city": "上海",
                "phone": "",
                "service_stage": "信息收集",
                "responsible_teacher": "测试老师",
            },
            {
                "primary_goal": "就业",
                "alternate_goal": "升学",
                "decision_reason": "提前准备就业",
            },
            None,
        )

        workflow = build_student_workflow(student_id)

        assert workflow["stage2_url"] == f"/students/{student_id}/stage-two"
        assert workflow["goal_profile"]["primary_goal"] == "就业"
        assert workflow["stages"][1]["summary"] == "就业路径 · 0个岗位目标 · 0项技能"
