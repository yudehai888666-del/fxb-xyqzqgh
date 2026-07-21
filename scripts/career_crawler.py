#!/usr/bin/env python3
"""
Recruitment platform crawler for the local academic planning SQLite database.

The script is intentionally independent of Flask app context. It reads existing
jobs from SQLite, crawls public recruitment pages, aggregates market signals,
and writes draft employment market snapshots for teacher review.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import random
import re
import sqlite3
import time
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover - exercised only when bs4 is absent.
    BeautifulSoup = None


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).with_name("crawler_config.json")
DEFAULT_DB_PATH = BASE_DIR / "instance" / "academic_planning.sqlite3"
SUPPORTED_CITIES = {
    "北京", "上海", "广州", "深圳", "杭州", "成都", "大连", "青岛", "南通", "舟山", "镇江", "全国"
}
EDUCATION_ORDER = ("博士", "硕士", "本科", "专科", "不限")
EXPERIENCE_ORDER = ("0-1年", "1-3年", "3-5年", "5-10年", "10年以上", "不限")
BREAKDOWN_TYPES = ("学历", "经验", "热门技能", "地区")
LIMITATION_NOTE = (
    "数据来源为公开招聘平台，样本为当前在招岗位，不代表全市场水平；"
    "薪资为挂牌价，实际到手受学历、经验、公司规模影响。"
)


def load_config(config_path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def setup_logger(db_path: str) -> logging.Logger:
    log_dir = Path(db_path).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"crawler_{date.today().strftime('%Y%m%d')}.log"
    logger = logging.getLogger("career_crawler")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename) == log_path
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _first_enabled_platform(config: dict[str, Any]) -> dict[str, Any]:
    for platform in config.get("platforms", []):
        if platform.get("enabled"):
            return platform
    raise ValueError("crawler_config.json 中没有启用的平台")


def _resolve_admin_user_id(conn: sqlite3.Connection, preferred_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'admin'",
        (preferred_id,),
    ).fetchone()
    if row:
        return int(row["id"])
    row = conn.execute(
        "SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
    ).fetchone()
    if row is None:
        raise ValueError("数据库中没有 admin 用户，无法写入负责人和审核人")
    return int(row["id"])


def _get_job(conn: sqlite3.Connection, job_name: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, name, job_family FROM knowledge_jobs WHERE name = ? AND status = '已发布'",
        (job_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"未找到已发布岗位：{job_name}")
    return row


def _existing_pending_snapshot(
    conn: sqlite3.Connection, job_id: int, region: str, period_start: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id FROM employment_market_snapshots
        WHERE job_id = ? AND region = ? AND period_start = ?
          AND status IN ('草稿', '待审核')
        ORDER BY id DESC LIMIT 1
        """,
        (job_id, region, period_start),
    ).fetchone()


def _build_headers(config: dict[str, Any]) -> dict[str, str]:
    user_agents = config.get("user_agents") or ["Mozilla/5.0"]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }


def _http_get(url: str, config: dict[str, Any], logger: logging.Logger) -> tuple[int, str]:
    try:
        import requests  # type: ignore
    except ImportError:  # pragma: no cover - exercised only when requests is absent.
        requests = None

    for attempt in range(1, 4):
        try:
            if requests is not None:
                response = requests.get(
                    url, headers=_build_headers(config), timeout=15
                )
                status_code = response.status_code
                text = response.text
            else:
                request = Request(url, headers=_build_headers(config))
                with urlopen(request, timeout=15) as response:
                    status_code = response.status
                    text = response.read().decode("utf-8", errors="ignore")
            if status_code in (429, 503):
                logger.warning("rate_limited url=%s status=%s attempt=%s", url, status_code, attempt)
                time.sleep(15)
                continue
            if "captcha" in text.lower() or "验证" in text:
                logger.warning("captcha_detected url=%s status=%s", url, status_code)
                return status_code, ""
            return status_code, text
        except Exception as exc:  # pragma: no cover - network behavior varies.
            logger.exception("request_failed url=%s attempt=%s error=%s", url, attempt, exc)
            if attempt < 3:
                time.sleep(15)
    return 0, ""


def _strip_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _find_first_text(blob: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = blob.get(key)
        if isinstance(value, str) and value.strip():
            return _strip_text(value)
    return ""


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _parse_json_posts(html: str) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    for script_text in re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.S | re.I):
        script_text = script_text.strip()
        json_candidates = []
        if script_text.startswith("{") or script_text.startswith("["):
            json_candidates.append(script_text)
        json_candidates.extend(
            match.group(1)
            for match in re.finditer(r"JSON\.parse\('(.+?)'\)", script_text, flags=re.S)
        )
        for candidate in json_candidates:
            try:
                data = json.loads(candidate)
            except Exception:
                continue
            for item in _walk_json(data):
                title = _find_first_text(item, ("title", "jobName", "positionName", "name"))
                salary = _find_first_text(item, ("salary", "salaryText", "salaryDesc", "compensation"))
                if not title or not salary:
                    continue
                posts.append(
                    {
                        "title": title,
                        "salary": salary,
                        "education": _find_first_text(item, ("education", "eduLevel", "degree")),
                        "experience": _find_first_text(item, ("experience", "workYear", "requireWorkYears")),
                        "city": _find_first_text(item, ("city", "dq", "workPlace", "address")),
                        "description": _find_first_text(item, ("description", "jobDesc", "labels", "skillLabels")),
                    }
                )
    return posts


def _parse_html_posts(html: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    selectors = (
        ".job-card-pc-container",
        ".job-card-left-box",
        ".sojob-item-main",
        ".job-card",
        "[data-nick]",
    )
    cards = []
    for selector in selectors:
        cards = soup.select(selector)
        if cards:
            break
    posts: list[dict[str, str]] = []
    for card in cards:
        text = _strip_text(card.get_text(" "))
        if not text:
            continue
        salary_match = re.search(
            r"(\d+(?:\.\d+)?\s*[kK千万][^\s，,;；]*)|(面议|薪资保密|保密)",
            text,
        )
        posts.append(
            {
                "title": _strip_text(
                    (card.select_one(".job-title-box a, .job-name, .position-name, a") or card).get_text(" ")
                ),
                "salary": salary_match.group(0) if salary_match else "",
                "education": _extract_education(text, {}),
                "experience": _extract_experience(text, {}),
                "city": _extract_city(text),
                "description": text,
            }
        )
    return posts


def _parse_posts(html: str) -> list[dict[str, str]]:
    posts = _parse_json_posts(html)
    if posts:
        return posts
    return _parse_html_posts(html)


def fetch_platform_posts(
    job_name: str,
    city: str,
    max_pages: int,
    config: dict[str, Any],
    logger: logging.Logger,
) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    city_codes = config.get("city_codes", {})
    for platform in config.get("platforms", []):
        if not platform.get("enabled"):
            continue
        for page in range(max_pages):
            url = platform["search_url_template"].format(
                keyword=quote(job_name),
                city=quote(city),
                city_code=city_codes.get(city, city),
                page=page,
            )
            status_code, html = _http_get(url, config, logger)
            page_posts = _parse_posts(html) if html else []
            for post in page_posts:
                post.setdefault("platform", platform["name"])
            posts.extend(page_posts)
            logger.info("page_fetched url=%s status=%s valid_items=%s", url, status_code, len(page_posts))
            time.sleep(random.uniform(1.5, 3.5))
        if posts:
            return posts
    return posts


def parse_salary_to_monthly(salary_text: str) -> tuple[int, int] | None:
    text = _strip_text(salary_text).lower()
    if not text or any(token in text for token in ("面议", "保密")):
        return None
    multiplier = 1000
    if "万" in text and "k" not in text:
        multiplier = 10000
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", text)]
    if not numbers:
        return None
    if len(numbers) == 1:
        low = high = numbers[0]
    else:
        low, high = numbers[0], numbers[1]
    if "年" in text:
        low /= 12
        high /= 12
    return int(round(low * multiplier)), int(round(high * multiplier))


def _trimmed_median(values: list[int]) -> int | None:
    if not values:
        return None
    sorted_values = sorted(values)
    trim = int(len(sorted_values) * 0.1)
    if trim and len(sorted_values) > trim * 2:
        sorted_values = sorted_values[trim:-trim]
    return int(round(median(sorted_values)))


def _extract_education(text: str, education_map: dict[str, str]) -> str:
    for key, label in education_map.items():
        if key in text:
            return label
    return "不限"


def _extract_experience(text: str, experience_map: dict[str, str]) -> str:
    normalized = text.replace("经验", "")
    for key in sorted(experience_map, key=len, reverse=True):
        if key in normalized:
            return experience_map[key]
    return "不限"


def _extract_city(text: str) -> str:
    for city in ("北京", "上海", "广州", "深圳", "杭州", "成都"):
        if city in text:
            return city
    return "全国"


def _normalize_post(post: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        _strip_text(post.get(key))
        for key in ("title", "salary", "education", "experience", "city", "description")
    )
    education = _strip_text(post.get("education")) or _extract_education(
        text, config.get("education_map", {})
    )
    experience = _strip_text(post.get("experience")) or _extract_experience(
        text, config.get("experience_map", {})
    )
    city = _strip_text(post.get("city")) or _extract_city(text)
    return {
        "salary_text": _strip_text(post.get("salary")),
        "salary": parse_salary_to_monthly(_strip_text(post.get("salary"))),
        "education": _extract_education(education, config.get("education_map", {})),
        "experience": _extract_experience(experience, config.get("experience_map", {})),
        "city": _extract_city(city),
        "description": text,
    }


def _job_keywords(job_family: str, config: dict[str, Any]) -> list[str]:
    keywords_by_family = config.get("skill_keywords_by_job_family", {})
    if job_family in keywords_by_family:
        return keywords_by_family[job_family]
    keywords: list[str] = []
    for values in keywords_by_family.values():
        for keyword in values:
            if keyword not in keywords:
                keywords.append(keyword)
    return keywords


def _count_skills(posts: list[dict[str, Any]], keywords: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for post in posts:
        description = post["description"].lower()
        for keyword in keywords:
            if keyword.lower() in description:
                counts[keyword] += 1
    return counts


def _percent_rows(
    dimension_type: str,
    counts: Counter[str],
    sample_size: int,
    order: tuple[str, ...] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not counts or sample_size <= 0:
        return []
    if order:
        labels = [label for label in order if counts.get(label)]
        labels.extend(
            label for label, _ in counts.most_common() if label not in labels
        )
    else:
        labels = [label for label, _ in counts.most_common(limit)]
    rows = []
    for sort_order, label in enumerate(labels[:limit], 1):
        rows.append(
            {
                "dimension_type": dimension_type,
                "label": label,
                "value": round(counts[label] / sample_size * 100, 2),
                "unit": "%",
                "sample_size": sample_size,
                "sort_order": sort_order,
            }
        )
    return rows


def aggregate_posts(
    posts: list[dict[str, Any]], job_family: str, config: dict[str, Any]
) -> dict[str, Any]:
    normalized_posts = [_normalize_post(post, config) for post in posts]
    valid_salary_posts = [post for post in normalized_posts if post["salary"]]
    lows = [post["salary"][0] for post in valid_salary_posts]
    highs = [post["salary"][1] for post in valid_salary_posts]
    medians = [
        int(round((post["salary"][0] + post["salary"][1]) / 2))
        for post in valid_salary_posts
    ]
    observed_count = len(normalized_posts)
    sample_size = len(valid_salary_posts)
    education_counts = Counter(post["education"] for post in normalized_posts)
    experience_counts = Counter(post["experience"] for post in normalized_posts)
    city_counts = Counter(post["city"] for post in normalized_posts)
    skill_counts = _count_skills(normalized_posts, _job_keywords(job_family, config))
    breakdowns = []
    breakdowns.extend(_percent_rows("学历", education_counts, observed_count, EDUCATION_ORDER))
    breakdowns.extend(_percent_rows("经验", experience_counts, observed_count, EXPERIENCE_ORDER))
    breakdowns.extend(_percent_rows("热门技能", skill_counts, observed_count))
    breakdowns.extend(_percent_rows("地区", city_counts, observed_count))
    return {
        "observed_posting_count": observed_count,
        "sample_size": sample_size,
        "salary_min": _trimmed_median(lows),
        "salary_median": _trimmed_median(medians),
        "salary_max": _trimmed_median(highs),
        "breakdowns": breakdowns,
    }


def _ensure_source(
    conn: sqlite3.Connection,
    platform: dict[str, Any],
    owner_user_id: int,
    reviewer_user_id: int,
) -> int:
    row = conn.execute(
        "SELECT id FROM intelligence_sources WHERE url = ?",
        (platform["url"],),
    ).fetchone()
    if row:
        source_id = int(row["id"])
        conn.execute(
            """
            UPDATE intelligence_sources
            SET name = ?, source_kind = ?, collection_mode = ?, update_frequency = ?,
                owner_user_id = ?, reviewer_user_id = ?, compliance_note = ?,
                is_active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                platform["name"],
                platform.get("source_kind", "招聘平台"),
                "公开网页",
                "每月",
                owner_user_id,
                reviewer_user_id,
                "仅采集公开招聘列表信息，用于内部测试数据草稿，发布前需人工审核。",
                source_id,
            ),
        )
        return source_id
    cursor = conn.execute(
        """
        INSERT INTO intelligence_sources (
            name, url, source_kind, collection_mode, update_frequency,
            owner_user_id, reviewer_user_id, compliance_note, is_active, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            platform["name"],
            platform["url"],
            platform.get("source_kind", "招聘平台"),
            "公开网页",
            "每月",
            owner_user_id,
            reviewer_user_id,
            "仅采集公开招聘列表信息，用于内部测试数据草稿，发布前需人工审核。",
            owner_user_id,
        ),
    )
    return int(cursor.lastrowid)


def _content_hash(payload: dict[str, Any]) -> str:
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _insert_snapshot(
    conn: sqlite3.Connection,
    job_id: int,
    job_name: str,
    city: str,
    source_id: int,
    owner_user_id: int,
    reviewer_user_id: int,
    period_start: str,
    period_end: str,
    next_check_at: str,
    aggregate: dict[str, Any],
    platform_name: str,
) -> int:
    evidence_summary = (
        f"通过{platform_name}爬取，关键词\"{job_name}\"，城市\"{city}\"，"
        f"共采集{aggregate['sample_size']}条有效薪资数据，"
        f"统计周期{period_start}至{period_end}。"
    )
    cursor = conn.execute(
        """
        INSERT INTO employment_market_snapshots (
            job_id, region, period_start, period_end, observed_posting_count,
            sample_size, salary_min, salary_median, salary_max, currency,
            salary_period, source_id, evidence_summary, limitation_note,
            data_classification, owner_user_id, reviewer_user_id, next_check_at,
            status, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CNY', '月', ?, ?, ?, '测试数据', ?, ?, ?, '草稿', ?)
        """,
        (
            job_id,
            city,
            period_start,
            period_end,
            aggregate["observed_posting_count"],
            aggregate["sample_size"],
            aggregate["salary_min"],
            aggregate["salary_median"],
            aggregate["salary_max"],
            source_id,
            evidence_summary,
            LIMITATION_NOTE,
            owner_user_id,
            reviewer_user_id,
            next_check_at,
            owner_user_id,
        ),
    )
    snapshot_id = int(cursor.lastrowid)
    for row in aggregate["breakdowns"]:
        if row["dimension_type"] not in BREAKDOWN_TYPES:
            continue
        conn.execute(
            """
            INSERT INTO employment_market_breakdowns (
                snapshot_id, dimension_type, label, value, unit, sample_size, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                row["dimension_type"],
                row["label"],
                row["value"],
                row["unit"],
                row["sample_size"],
                row["sort_order"],
            ),
        )
    return snapshot_id


def crawl_and_store(
    job_name: str,
    city: str = "全国",
    max_pages: int = 3,
    db_path: str = "instance/academic_planning.sqlite3",
    owner_user_id: int = 1,
    reviewer_user_id: int = 1,
) -> dict[str, Any]:
    """
    Crawl recruitment data for an exact published job name and write a draft
    market snapshot plus four groups of breakdown rows into the SQLite DB.
    """
    if city not in SUPPORTED_CITIES:
        raise ValueError("city 仅支持：北京/上海/广州/深圳/杭州/成都/大连/青岛/南通/舟山/镇江/全国")
    if max_pages < 1:
        raise ValueError("max_pages 必须大于等于 1")
    config = load_config()
    platform = _first_enabled_platform(config)
    logger = setup_logger(db_path)
    started_at = datetime.now().isoformat(timespec="seconds")
    logger.info("task_start job_name=%s city=%s started_at=%s", job_name, city, started_at)
    today = date.today()
    period_start = today.replace(day=1).isoformat()
    period_end = today.isoformat()
    next_check_at = (today + timedelta(days=90)).isoformat()

    with closing(_connect(db_path)) as conn:
        job = _get_job(conn, job_name)
        owner_id = _resolve_admin_user_id(conn, owner_user_id)
        reviewer_id = _resolve_admin_user_id(conn, reviewer_user_id)
        existing = _existing_pending_snapshot(conn, int(job["id"]), city, period_start)
        if existing:
            logger.info(
                "skip_existing_pending job_name=%s city=%s snapshot_id=%s",
                job_name,
                city,
                existing["id"],
            )
            return {
                "status": "skipped",
                "reason": "existing_pending_snapshot",
                "job_id": int(job["id"]),
                "snapshot_id": int(existing["id"]),
            }

    posts = fetch_platform_posts(job_name, city, max_pages, config, logger)
    aggregate = aggregate_posts(posts, str(job["job_family"] or ""), config)

    with closing(_connect(db_path)) as conn:
        try:
            conn.execute("BEGIN")
            source_id = _ensure_source(conn, platform, owner_id, reviewer_id)
            existing = _existing_pending_snapshot(conn, int(job["id"]), city, period_start)
            if existing:
                conn.rollback()
                logger.info(
                    "skip_existing_pending_after_crawl job_name=%s city=%s snapshot_id=%s",
                    job_name,
                    city,
                    existing["id"],
                )
                return {
                    "status": "skipped",
                    "reason": "existing_pending_snapshot",
                    "job_id": int(job["id"]),
                    "snapshot_id": int(existing["id"]),
                }
            snapshot_id = _insert_snapshot(
                conn,
                int(job["id"]),
                job_name,
                city,
                source_id,
                owner_id,
                reviewer_id,
                period_start,
                period_end,
                next_check_at,
                aggregate,
                platform["name"],
            )
            content_hash = _content_hash(
                {"job_name": job_name, "city": city, "period_start": period_start, **aggregate}
            )
            conn.execute(
                """
                UPDATE intelligence_sources
                SET last_fetch_at = CURRENT_TIMESTAMP,
                    last_content_hash = ?,
                    last_change_status = '已采集',
                    last_error = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (content_hash, source_id),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.exception("task_failed job_name=%s city=%s error=%s", job_name, city, exc)
            raise
    logger.info(
        "task_end job_name=%s city=%s total_items=%s salary_items=%s snapshot_id=%s",
        job_name,
        city,
        aggregate["observed_posting_count"],
        aggregate["sample_size"],
        snapshot_id,
    )
    return {
        "status": "inserted",
        "job_id": int(job["id"]),
        "snapshot_id": snapshot_id,
        "observed_posting_count": aggregate["observed_posting_count"],
        "sample_size": aggregate["sample_size"],
        "salary_min": aggregate["salary_min"],
        "salary_median": aggregate["salary_median"],
        "salary_max": aggregate["salary_max"],
        "breakdown_count": len(aggregate["breakdowns"]),
    }


def _published_jobs(db_path: str) -> list[str]:
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM knowledge_jobs WHERE status = '已发布' ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="采集招聘平台数据并写入就业市场草稿快照")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job", help="单个岗位名称，必须与 knowledge_jobs.name 完全一致")
    group.add_argument("--all", action="store_true", help="爬取所有已发布岗位")
    parser.add_argument("--city", default="全国", help="北京/上海/广州/深圳/杭州/成都/全国")
    parser.add_argument("--pages", type=int, default=3, help="每个关键词最多翻页数")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--owner-user-id", type=int, default=1, help="负责人用户 ID")
    parser.add_argument("--reviewer-user-id", type=int, default=1, help="审核人用户 ID")
    args = parser.parse_args()

    jobs = _published_jobs(args.db) if args.all else [args.job]
    results = []
    for job_name in jobs:
        results.append(
            crawl_and_store(
                job_name,
                city=args.city,
                max_pages=args.pages,
                db_path=args.db,
                owner_user_id=args.owner_user_id,
                reviewer_user_id=args.reviewer_user_id,
            )
        )
    print(json.dumps(results[0] if args.job else results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
