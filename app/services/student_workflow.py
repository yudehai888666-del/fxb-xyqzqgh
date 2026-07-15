from app import repositories
from app.services.completion import get_student_completion


def build_student_workflow(student_id):
    completion = get_student_completion(student_id)
    notes_done = completion["teacher_notes"] == "已填写"
    targets = repositories.list_student_job_targets(student_id)
    skills = repositories.list_student_skill_assessments(student_id)
    exams = repositories.list_student_exam_plans(student_id)
    documents = repositories.list_planning_documents(student_id)
    confirmed_documents = [row for row in documents if row["status"] == "已确认"]
    replanning_cases = repositories.list_replanning_cases(student_id)

    stage1 = "completed" if completion["ready_for_ai"] else "in_progress"
    intelligence_started = bool(targets or skills or exams)
    stage2 = (
        "completed" if targets and (skills or exams)
        else "in_progress" if intelligence_started or stage1 == "completed"
        else "pending"
    )
    stage3 = (
        "completed" if notes_done
        else "in_progress" if stage2 == "completed"
        else "pending"
    )
    stage4 = (
        "completed" if confirmed_documents
        else "in_progress" if documents or stage3 == "completed"
        else "pending"
    )
    stage5 = "in_progress" if confirmed_documents else "pending"
    stage6 = "in_progress" if replanning_cases else "pending"
    stages = [
        {"number": 1, "title": "信息采集", "status": stage1,
         "summary": "学生、家长、材料与免责"},
        {"number": 2, "title": "目标与情报", "status": stage2,
         "summary": f"{len(targets)}个岗位目标 · {len(skills)}项技能 · {len(exams)}项考试"},
        {"number": 3, "title": "诊断访谈", "status": stage3,
         "summary": "老师判断、风险与家庭共识"},
        {"number": 4, "title": "形成规划", "status": stage4,
         "summary": f"{len(documents)}个版本 · {len(confirmed_documents)}个已确认"},
        {"number": 5, "title": "执行复盘", "status": stage5,
         "summary": "任务、进度、风险与阶段复盘"},
        {"number": 6, "title": "变更重规划", "status": stage6,
         "summary": f"{len(replanning_cases)}条变更记录"},
    ]
    current = next((stage["number"] for stage in stages[:5] if stage["status"] != "completed"), 5)
    completed = sum(stage["status"] == "completed" for stage in stages[:5])
    return {
        "stages": stages,
        "current": current,
        "progress": round(completed / 5 * 100),
        "completion": completion,
        "next_stage": stages[current - 1],
    }
