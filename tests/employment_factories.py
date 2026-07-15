from app import repositories


def create_user(username="evidence-admin", role="admin"):
    return repositories.create_user(
        {
            "username": username,
            "display_name": username,
            "password_hash": "test-only-hash",
            "role": role,
        }
    )


def create_source(actor_id):
    return repositories.create_intelligence_source(
        {
            "name": f"测试来源-{actor_id}",
            "url": f"https://example.test/source-{actor_id}",
        },
        actor_id,
    )


def create_published_job_and_skill(
    job_name="测试数据分析师", skill_name="测试SQL"
):
    job_id = repositories.create_knowledge_job(
        {"name": job_name, "industry_name": "测试产业"}
    )
    skill_id = repositories.create_knowledge_skill(
        {"name": skill_name, "skill_type": "工具技能"}
    )
    repositories.update_knowledge_status("job", job_id, "已发布")
    repositories.update_knowledge_status("skill", skill_id, "已发布")
    return job_id, skill_id
