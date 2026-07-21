#!/usr/bin/env python3
"""Seed draft-only career knowledge for the shipbuilding and computing families."""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing


GLOBAL_DISCLAIMER = "典型路径，不承诺固定年限、薪资或必然晋升。"
SEED_SOURCE_NAME = "职业族受控种子知识（待审核）"

MAJORS = (
    {
        "name": "船舶与海洋工程",
        "discipline_category": "工学",
        "description": "面向船舶设计、建造、动力与质量等岗位的受控种子知识。",
    },
    {
        "name": "计算机科学与技术",
        "discipline_category": "工学",
        "description": "面向软件开发、数据与算法等岗位的受控种子知识。",
    },
)

JOBS = (
    ("船舶设计工程师", "船舶与海洋工程", "船舶与海洋工程", "造船", "参与船舶总体与专业设计的工程岗位。", "助理设计工程师 -> 设计工程师 -> 高级设计工程师 -> 专业负责人/项目总师/技术管理", ("船舶原理", "结构设计", "CAD", "三维船舶设计", "CAE", "PLM")),
    ("船舶结构工程师", "船舶与海洋工程", "船舶与海洋工程", "造船", "负责船体结构、强度与有限元分析的工程岗位。", "助理结构工程师 -> 结构工程师 -> 高级结构工程师 -> 专业负责人", ("船体结构", "有限元分析", "强度分析", "CAD", "CAE")),
    ("船舶工艺工程师", "船舶与海洋工程", "船舶与海洋工程", "造船", "负责船舶建造工艺与生产协同的工程岗位。", "助理工艺工程师 -> 工艺工程师 -> 高级工艺工程师 -> 工艺主管/制造管理", ("建造工艺", "焊接", "精益制造", "CAM", "生产计划")),
    ("船舶电气工程师", "船舶与海洋工程", "船舶与海洋工程", "造船", "负责船舶电气、自动化与控制系统的工程岗位。", "助理电气工程师 -> 电气工程师 -> 高级电气工程师 -> 电气专业负责人", ("船舶电气", "自动化", "控制", "PLC", "电气设计")),
    ("轮机工程师", "船舶与海洋工程", "船舶与海洋工程", "造船", "负责船舶动力、机械与管系系统的工程岗位。", "助理轮机工程师 -> 轮机工程师 -> 高级轮机工程师 -> 动力专业负责人", ("船舶动力", "机械", "管系", "调试", "设备维护")),
    ("船舶检验/质量工程师", "船舶与海洋工程", "船舶与海洋工程", "造船", "负责船舶检验、质量体系与问题分析的工程岗位。", "检验员/助理工程师 -> 质量工程师 -> 高级质量工程师 -> 质量主管/认证方向", ("质量体系", "无损检测", "规范标准", "检验", "问题分析")),
    ("后端开发工程师", "计算机科学与技术", "软件与信息技术服务", "计算机", "负责服务端应用、数据存储与系统集成的开发岗位。", "初级开发工程师 -> 中级开发工程师 -> 高级开发工程师 -> 技术负责人/架构师/工程经理", ("Python", "Java", "Go", "SQL", "MySQL", "Redis", "Docker", "Git", "Linux", "微服务")),
    ("前端开发工程师", "计算机科学与技术", "软件与信息技术服务", "计算机", "负责 Web 与应用界面实现的开发岗位。", "初级前端工程师 -> 中级前端工程师 -> 高级前端工程师 -> 前端负责人/全栈/工程管理", ("JavaScript", "TypeScript", "Vue", "React", "Node.js", "Git")),
    ("测试开发工程师", "计算机科学与技术", "软件与信息技术服务", "计算机", "负责测试设计、自动化与质量工程的开发岗位。", "测试工程师 -> 测试开发工程师 -> 高级测试开发工程师 -> 测试负责人/质量管理", ("测试设计", "Python", "Java", "接口测试", "自动化测试", "CI/CD", "Git")),
    ("数据分析师", "计算机科学与技术", "软件与信息技术服务", "计算机", "负责数据处理、分析与业务洞察的岗位。", "初级分析师 -> 数据分析师 -> 高级分析师 -> 数据产品/数据科学/分析管理", ("SQL", "Python", "Excel", "Pandas", "统计学", "BI工具")),
    ("算法工程师", "计算机科学与技术", "软件与信息技术服务", "计算机", "负责机器学习模型研发、评估与应用的岗位。", "算法工程师 -> 高级算法工程师 -> 算法专家/技术负责人", ("Python", "机器学习", "深度学习", "数据结构", "模型评估", "Linux")),
    ("嵌入式软件工程师", "计算机科学与技术", "软件与信息技术服务", "计算机", "负责嵌入式系统、驱动与通信软件的开发岗位。", "初级嵌入式工程师 -> 嵌入式软件工程师 -> 高级嵌入式工程师 -> 技术负责人/系统架构", ("C/C++", "Linux", "RTOS", "驱动", "通信协议", "Git")),
)


def _skill_type(name):
    return "软件/工具" if name.isascii() or name in {"CAD", "CAE", "PLM", "CAM", "PLC", "BI工具"} else "专业技能"


def _upsert_named_record(conn, table, name, values):
    existing = conn.execute(
        f"SELECT id, status FROM {table} WHERE name = ?", (name,)
    ).fetchone()
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    updates = ", ".join(
        f"{column} = excluded.{column}" for column in values if column != "name"
    )
    conn.execute(
        f"""
        INSERT INTO {table} ({columns}) VALUES ({placeholders})
        ON CONFLICT(name) DO UPDATE SET {updates}, updated_at = CURRENT_TIMESTAMP
        WHERE {table}.status = '草稿'
        """,
        tuple(values.values()),
    )
    row = conn.execute(f"SELECT id FROM {table} WHERE name = ?", (name,)).fetchone()
    return int(row["id"]), existing is None


def _is_draft(conn, table, record_id):
    row = conn.execute(
        f"SELECT status FROM {table} WHERE id = ?", (record_id,)
    ).fetchone()
    return row is not None and row["status"] == "草稿"


def _upsert_major_job_link(conn, major_id, job_id, owner_user_id):
    existing = conn.execute(
        "SELECT id FROM major_job_links WHERE major_id = ? AND job_id = ?", (major_id, job_id)
    ).fetchone()
    conn.execute(
        """
        INSERT INTO major_job_links (
            major_id, job_id, relevance_level, evidence_note, source_url, created_by
        ) VALUES (?, ?, '高度相关', '职业族受控种子关联，待人工审核。', '', ?)
        ON CONFLICT(major_id, job_id) DO UPDATE SET
            relevance_level = excluded.relevance_level,
            evidence_note = excluded.evidence_note,
            source_url = excluded.source_url,
            created_by = excluded.created_by
        WHERE (
            SELECT status FROM knowledge_majors WHERE id = major_job_links.major_id
        ) = '草稿' AND (
            SELECT status FROM knowledge_jobs WHERE id = major_job_links.job_id
        ) = '草稿'
        """,
        (major_id, job_id, owner_user_id),
    )
    return existing is None


def _upsert_job_skill_link(conn, job_id, skill_id, owner_user_id, reviewer_user_id):
    existing = conn.execute(
        "SELECT id, status FROM job_skill_links WHERE job_id = ? AND skill_id = ?",
        (job_id, skill_id),
    ).fetchone()
    if existing is not None and existing["status"] != "草稿":
        return False
    conn.execute(
        """
        INSERT INTO job_skill_links (
            job_id, skill_id, importance_level, proficiency_level, evidence_note,
            source_url, confidence_level, sample_size, last_verified_at, next_check_at,
            owner_user_id, reviewer_user_id, status, limitation_note, created_by
        ) VALUES (?, ?, '核心', '掌握', '职业族受控种子技能，待人工审核。', '',
                  '', 0, '', '', ?, ?, '草稿',
                  '种子词典用于候选匹配，不等同于岗位硬性要求。', ?)
        ON CONFLICT(job_id, skill_id) DO UPDATE SET
            importance_level = excluded.importance_level,
            proficiency_level = excluded.proficiency_level,
            evidence_note = excluded.evidence_note,
            source_url = excluded.source_url,
            confidence_level = excluded.confidence_level,
            sample_size = excluded.sample_size,
            last_verified_at = excluded.last_verified_at,
            next_check_at = excluded.next_check_at,
            owner_user_id = excluded.owner_user_id,
            reviewer_user_id = excluded.reviewer_user_id,
            limitation_note = excluded.limitation_note,
            created_by = excluded.created_by
        WHERE job_skill_links.status = '草稿'
        """,
        (job_id, skill_id, owner_user_id, reviewer_user_id, owner_user_id),
    )
    return existing is None


def seed_career_knowledge(db_path: str, owner_user_id: int, reviewer_user_id: int) -> dict[str, int]:
    """Create or refresh draft seed records without overwriting governed knowledge."""
    counts = {"majors": 0, "jobs": 0, "skills": 0, "major_job_links": 0, "job_skill_links": 0}
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("BEGIN")
            major_ids = {}
            for major in MAJORS:
                major_id, created = _upsert_named_record(
                    conn, "knowledge_majors", major["name"], {
                        **major, "degree_level": "本科", "source_url": "",
                        "source_name": SEED_SOURCE_NAME, "created_by": owner_user_id,
                    }
                )
                major_ids[major["name"]] = major_id
                counts["majors"] += int(created)

            skill_ids = {}
            skill_names = {skill for *_, skills in JOBS for skill in skills}
            for skill_name in sorted(skill_names):
                skill_id, created = _upsert_named_record(
                    conn, "knowledge_skills", skill_name, {
                        "name": skill_name, "skill_type": _skill_type(skill_name),
                        "description": "职业族受控种子技能词典，待人工审核。",
                        "source_url": "", "source_name": SEED_SOURCE_NAME,
                        "created_by": owner_user_id,
                    }
                )
                skill_ids[skill_name] = skill_id
                counts["skills"] += int(created)

            job_ids = {}
            for name, major_name, industry, family, description, path, skills in JOBS:
                job_id, created = _upsert_named_record(
                    conn, "knowledge_jobs", name, {
                        "name": name, "industry_name": industry, "job_family": family,
                        "description": description,
                        "development_direction": f"{path}。{GLOBAL_DISCLAIMER}",
                        "source_url": "", "source_name": SEED_SOURCE_NAME,
                        "created_by": owner_user_id,
                    }
                )
                job_ids[name] = job_id
                counts["jobs"] += int(created)

            for name, major_name, _industry, _family, _description, _path, skills in JOBS:
                job_id = job_ids[name]
                major_id = major_ids[major_name]
                if not (
                    _is_draft(conn, "knowledge_majors", major_id)
                    and _is_draft(conn, "knowledge_jobs", job_id)
                ):
                    continue
                if _upsert_major_job_link(conn, major_id, job_id, owner_user_id):
                    counts["major_job_links"] += 1
                for skill_name in skills:
                    if not _is_draft(conn, "knowledge_skills", skill_ids[skill_name]):
                        continue
                    if _upsert_job_skill_link(conn, job_id, skill_ids[skill_name], owner_user_id, reviewer_user_id):
                        counts["job_skill_links"] += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return counts


def main():
    parser = argparse.ArgumentParser(description="写入造船与计算机职业族草稿知识")
    parser.add_argument("--db", default="instance/academic_planning.sqlite3")
    parser.add_argument("--owner-user-id", type=int, required=True)
    parser.add_argument("--reviewer-user-id", type=int, required=True)
    args = parser.parse_args()
    print(seed_career_knowledge(args.db, args.owner_user_id, args.reviewer_user_id))


if __name__ == "__main__":
    main()
