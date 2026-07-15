from app import repositories


LEVEL_LABELS = {0: "未评估", 1: "了解", 2: "掌握", 3: "熟练", 4: "精通"}
REQUIRED_LEVELS = {"了解": 1, "掌握": 2, "熟练": 3, "精通": 4}
IMPORTANCE_WEIGHTS = {"核心": 3, "重要": 2, "加分项": 1}


def _suggestion(skill_name, current_level, required_level):
    if current_level == 0:
        return f"先完成{skill_name}基础学习，并用课程、项目或证书形成首份证据"
    if required_level - current_level >= 2:
        return f"安排系统训练和实战项目，将{skill_name}提升到{LEVEL_LABELS[required_level]}"
    return f"通过项目、竞赛或实习把{skill_name}提升一级并补充成果证据"


def build_student_intelligence_report(student):
    assessments = repositories.list_student_skill_assessments(student.id)
    assessment_map = {row["skill_id"]: row for row in assessments}
    candidates = repositories.list_student_candidate_jobs(student.id, student.major)
    job_results = []

    for job in candidates:
        requirements = repositories.list_job_skill_requirements(job["id"])
        total_weight = 0
        achieved_weight = 0.0
        assessed_count = 0
        skill_rows = []
        for requirement in requirements:
            required_level = REQUIRED_LEVELS.get(requirement["proficiency_level"], 2)
            weight = IMPORTANCE_WEIGHTS.get(requirement["importance_level"], 1)
            assessment = assessment_map.get(requirement["skill_id"])
            current_level = assessment["current_level"] if assessment else 0
            if assessment:
                assessed_count += 1
            total_weight += weight
            achieved_weight += weight * min(current_level / required_level, 1)
            gap = max(required_level - current_level, 0)
            skill_rows.append(
                {
                    "skill_id": requirement["skill_id"],
                    "name": requirement["skill_name"],
                    "type": requirement["skill_type"],
                    "importance": requirement["importance_level"],
                    "current_level": current_level,
                    "current_label": LEVEL_LABELS[current_level],
                    "required_level": required_level,
                    "required_label": LEVEL_LABELS[required_level],
                    "gap": gap,
                    "evidence": assessment["evidence_note"] if assessment else "",
                    "suggestion": _suggestion(requirement["skill_name"], current_level, required_level) if gap else "能力已达到当前要求，继续用成果巩固",
                }
            )
        score = round(achieved_weight / total_weight * 100) if total_weight else None
        coverage = round(assessed_count / len(requirements) * 100) if requirements else 0
        job_results.append(
            {
                "job": job,
                "score": score,
                "coverage": coverage,
                "skills": skill_rows,
                "gaps": sorted((row for row in skill_rows if row["gap"]), key=lambda row: (-row["gap"], row["importance"])),
            }
        )

    published_trends = repositories.list_published_industry_trends()
    relevant_trends = []
    seen_trends = set()
    for trend in published_trends:
        for result in job_results:
            job = result["job"]
            if ((job["industry_name"] and job["industry_name"] == trend["industry_name"]) or
                    job["name"] in (trend["affected_jobs"] or "")):
                if trend["id"] not in seen_trends:
                    relevant_trends.append(trend)
                    seen_trends.add(trend["id"])
                break

    targets = repositories.list_student_job_targets(student.id)
    unpublished_targets = [row for row in targets if row["job_status"] != "已发布"]
    scores = [result["score"] for result in job_results if result["score"] is not None]
    return {
        "student": student,
        "targets": targets,
        "assessments": assessments,
        "jobs": job_results,
        "trends": relevant_trends,
        "unpublished_targets": unpublished_targets,
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "level_labels": LEVEL_LABELS,
        "data_ready": bool(job_results and any(result["skills"] for result in job_results)),
    }
