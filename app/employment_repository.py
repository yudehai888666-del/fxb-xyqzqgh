from datetime import date

from app.db import get_db


BREAKDOWN_TYPES = ("学历", "经验", "热门技能", "地区")
SNAPSHOT_COLUMNS = """
    ms.*, j.name AS job_name, s.name AS source_name, s.url AS source_url,
    owner.display_name AS owner_name, reviewer.display_name AS reviewer_name
"""


def _require_canonical_date(value, message):
    text = (value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(message) from exc
    if parsed.isoformat() != text:
        raise ValueError(message)
    return text


def _optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def _market_values(data):
    if data.get("data_classification", "测试数据") != "测试数据":
        raise ValueError("本阶段只能录入测试数据")
    period_start = _require_canonical_date(data.get("period_start"), "统计周期无效")
    period_end = _require_canonical_date(data.get("period_end"), "统计周期无效")
    if period_start > period_end:
        raise ValueError("统计周期无效")
    salaries = [
        int(data[key])
        for key in ("salary_min", "salary_median", "salary_max")
        if data.get(key) not in (None, "")
    ]
    if salaries and salaries != sorted(salaries):
        raise ValueError("薪资最低值、中位值和最高值顺序无效")
    return (
        int(data["job_id"]),
        data["region"].strip(),
        period_start,
        period_end,
        int(data.get("observed_posting_count", 0)),
        int(data.get("sample_size", 0)),
        _optional_int(data.get("salary_min")),
        _optional_int(data.get("salary_median")),
        _optional_int(data.get("salary_max")),
        data.get("currency", "CNY").strip() or "CNY",
        data.get("salary_period", "月").strip() or "月",
        int(data["source_id"]),
        int(data["source_snapshot_id"]) if data.get("source_snapshot_id") else None,
        data.get("evidence_summary", "").strip(),
        data.get("limitation_note", "").strip(),
        "测试数据",
        int(data["owner_user_id"]),
        int(data["reviewer_user_id"]),
        _require_canonical_date(data.get("next_check_at"), "复核日期无效"),
    )


def _insert_breakdowns(db, snapshot_id, breakdowns):
    for row in breakdowns:
        if row["dimension_type"] not in BREAKDOWN_TYPES or not row["label"].strip():
            raise ValueError("市场分布维度无效")
        db.execute(
            """INSERT INTO employment_market_breakdowns
               (snapshot_id, dimension_type, label, value, unit, sample_size, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                row["dimension_type"],
                row["label"].strip(),
                float(row["value"]),
                row.get("unit", "%") or "%",
                int(row.get("sample_size", 0)),
                int(row.get("sort_order", 0)),
            ),
        )


def create_market_snapshot(data, breakdowns, actor_id):
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO employment_market_snapshots
               (job_id, region, period_start, period_end, observed_posting_count,
                sample_size, salary_min, salary_median, salary_max, currency,
                salary_period, source_id, source_snapshot_id, evidence_summary,
                limitation_note, data_classification, owner_user_id,
                reviewer_user_id, next_check_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*_market_values(data), actor_id),
        )
        snapshot_id = cursor.lastrowid
        _insert_breakdowns(db, snapshot_id, breakdowns)
        db.commit()
        return snapshot_id
    except Exception:
        db.rollback()
        raise


def get_market_snapshot(snapshot_id):
    return get_db().execute(
        f"""SELECT {SNAPSHOT_COLUMNS}
            FROM employment_market_snapshots ms
            JOIN knowledge_jobs j ON j.id = ms.job_id
            JOIN intelligence_sources s ON s.id = ms.source_id
            JOIN users owner ON owner.id = ms.owner_user_id
            JOIN users reviewer ON reviewer.id = ms.reviewer_user_id
            WHERE ms.id = ?""",
        (snapshot_id,),
    ).fetchone()


def list_market_snapshots(job_id=None):
    params = []
    where = ""
    if job_id is not None:
        where = "WHERE ms.job_id = ?"
        params.append(job_id)
    return get_db().execute(
        f"""SELECT {SNAPSHOT_COLUMNS}
            FROM employment_market_snapshots ms
            JOIN knowledge_jobs j ON j.id = ms.job_id
            JOIN intelligence_sources s ON s.id = ms.source_id
            JOIN users owner ON owner.id = ms.owner_user_id
            JOIN users reviewer ON reviewer.id = ms.reviewer_user_id
            {where}
            ORDER BY ms.period_end DESC, ms.id DESC""",
        params,
    ).fetchall()


def list_market_breakdowns(snapshot_id):
    return get_db().execute(
        """SELECT *
           FROM employment_market_breakdowns
           WHERE snapshot_id = ?
           ORDER BY sort_order, id""",
        (snapshot_id,),
    ).fetchall()


def update_market_snapshot(snapshot_id, data, breakdowns, actor_id):
    existing = get_market_snapshot(snapshot_id)
    if existing is None:
        raise ValueError("市场快照不存在")
    if existing["status"] not in ("草稿", "已退回"):
        raise ValueError("已发布市场快照不可修改")
    db = get_db()
    try:
        db.execute(
            """UPDATE employment_market_snapshots
               SET job_id = ?, region = ?, period_start = ?, period_end = ?,
                   observed_posting_count = ?, sample_size = ?, salary_min = ?,
                   salary_median = ?, salary_max = ?, currency = ?, salary_period = ?,
                   source_id = ?, source_snapshot_id = ?, evidence_summary = ?,
                   limitation_note = ?, data_classification = ?, owner_user_id = ?,
                   reviewer_user_id = ?, next_check_at = ?, status = '草稿',
                   created_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (*_market_values(data), actor_id, snapshot_id),
        )
        db.execute(
            "DELETE FROM employment_market_breakdowns WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        _insert_breakdowns(db, snapshot_id, breakdowns)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _validate_ready_for_submission(row):
    if row is None:
        raise ValueError("市场快照不存在")
    if row["sample_size"] <= 0:
        raise ValueError("提交前请补齐正样本量、来源、证据、责任人、复核日期和限制说明")
    required = (
        row["source_id"],
        row["evidence_summary"],
        row["limitation_note"],
        row["owner_user_id"],
        row["reviewer_user_id"],
        row["next_check_at"],
    )
    if not all(required):
        raise ValueError("提交前请补齐正样本量、来源、证据、责任人、复核日期和限制说明")
    _require_canonical_date(row["period_start"], "统计周期无效")
    _require_canonical_date(row["period_end"], "统计周期无效")
    _require_canonical_date(row["next_check_at"], "复核日期无效")


def submit_market_snapshot(snapshot_id):
    row = get_market_snapshot(snapshot_id)
    _validate_ready_for_submission(row)
    if row["status"] not in ("草稿", "已退回"):
        raise ValueError("只有草稿或已退回市场快照可以提交审核")
    get_db().execute(
        """UPDATE employment_market_snapshots
           SET status = '待审核', updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (snapshot_id,),
    )
    get_db().commit()


def review_market_snapshot(snapshot_id, status):
    if status not in ("已发布", "已退回", "已过期"):
        raise ValueError("invalid market snapshot status")
    row = get_market_snapshot(snapshot_id)
    if row is None:
        raise ValueError("市场快照不存在")
    if status == "已发布":
        _validate_ready_for_submission(row)
        if row["status"] != "待审核":
            raise ValueError("市场快照需先提交审核")
    get_db().execute(
        """UPDATE employment_market_snapshots
           SET status = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (status, snapshot_id),
    )
    get_db().commit()


def list_current_market_snapshots(job_id):
    return get_db().execute(
        f"""SELECT {SNAPSHOT_COLUMNS}
            FROM employment_market_snapshots ms
            JOIN knowledge_jobs j ON j.id = ms.job_id
            JOIN intelligence_sources s ON s.id = ms.source_id
            JOIN users owner ON owner.id = ms.owner_user_id
            JOIN users reviewer ON reviewer.id = ms.reviewer_user_id
            WHERE ms.job_id = ? AND ms.status = '已发布'
              AND ms.data_classification = '测试数据'
              AND ms.sample_size > 0
              AND date(ms.next_check_at) = ms.next_check_at
              AND substr(ms.next_check_at, 1, 4) BETWEEN '0001' AND '9999'
              AND date(ms.next_check_at) >= date('now')
            ORDER BY ms.period_end DESC, ms.id DESC""",
        (job_id,),
    ).fetchall()


def get_analysis_draft(student_id):
    return get_db().execute(
        "SELECT * FROM student_employment_analysis_drafts WHERE student_id = ?",
        (student_id,),
    ).fetchone()


def upsert_analysis_draft(student_id, data, actor_id):
    db = get_db()
    db.execute(
        """
        INSERT INTO student_employment_analysis_drafts (
            student_id, suitability_summary, risk_summary,
            action_recommendations, limitation_note, updated_by
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            suitability_summary = excluded.suitability_summary,
            risk_summary = excluded.risk_summary,
            action_recommendations = excluded.action_recommendations,
            limitation_note = excluded.limitation_note,
            updated_by = excluded.updated_by,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            student_id,
            data.get("suitability_summary", "").strip(),
            data.get("risk_summary", "").strip(),
            data.get("action_recommendations", "").strip(),
            data.get("limitation_note", "").strip(),
            actor_id,
        ),
    )
    db.commit()
