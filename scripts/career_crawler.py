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
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover - exercised only when bs4 is absent.
    BeautifulSoup = None


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(__file__).with_name("crawler_config.json")
DEFAULT_DB_PATH = BASE_DIR / "instance" / "academic_planning.sqlite3"
CITY_LABELS = (
    "北京", "上海", "广州", "深圳", "杭州", "成都", "大连", "青岛", "南通", "舟山", "镇江"
)
SUPPORTED_CITIES = {*CITY_LABELS, "全国"}
EDUCATION_ORDER = ("博士", "硕士", "本科", "专科", "不限")
EXPERIENCE_ORDER = ("0-1年", "1-3年", "3-5年", "5-10年", "10年以上", "不限")
BREAKDOWN_TYPES = ("学历", "经验", "热门技能", "地区")
LIMITATION_NOTE = (
    "数据来源为公开招聘平台，样本为当前在招岗位，不代表全市场水平；"
    "薪资为挂牌价，实际到手受学历、经验、公司规模影响。"
)
APPROVED_PLATFORM_FIELDS = (
    "enabled",
    "url",
    "source_kind",
    "collection_mode",
    "allowed_public_pages",
    "search_url_template",
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


def _http_get(
    url: str, config: dict[str, Any], logger: logging.Logger
) -> tuple[int, str, str]:
    try:
        import requests  # type: ignore
    except ImportError:  # pragma: no cover - exercised only when requests is absent.
        requests = None

    try:
        if requests is not None:
            response = requests.get(url, headers=_build_headers(config), timeout=15)
            return response.status_code, response.text, ""
        request = Request(url, headers=_build_headers(config))
        with urlopen(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8", errors="ignore"), ""
    except Exception as exc:  # pragma: no cover - network behavior varies.
        logger.exception("request_failed url=%s error=%s", url, exc)
        return 0, "", f"请求失败：{_strip_text(exc)}"


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
                        "company": _find_first_text(item, ("company", "companyName", "brandName", "compName")),
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
        company_node = card.select_one(
            ".company-name, .company-name a, .company-info a, [data-company]"
        )
        salary_match = re.search(
            r"(\d+(?:\.\d+)?\s*[kK千万][^\s，,;；]*)|(面议|薪资保密|保密)",
            text,
        )
        posts.append(
            {
                "company": _strip_text(company_node.get_text(" ")) if company_node else "",
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


def _validate_platform(platform: dict[str, Any]) -> None:
    missing = [field for field in APPROVED_PLATFORM_FIELDS if field not in platform]
    if missing:
        raise ValueError(f"招聘平台配置缺少字段：{'、'.join(missing)}")
    if not isinstance(platform["enabled"], bool):
        raise ValueError("招聘平台配置 enabled 必须为布尔值")
    if not all(_strip_text(platform[field]) for field in ("url", "source_kind", "collection_mode", "search_url_template")):
        raise ValueError("招聘平台配置包含空字段")
    allowed_pages = platform["allowed_public_pages"]
    if not isinstance(allowed_pages, list) or not allowed_pages or not all(
        isinstance(page, str) and page.startswith("/") for page in allowed_pages
    ):
        raise ValueError("招聘平台配置 allowed_public_pages 无效")


def _approved_platforms(
    conn: sqlite3.Connection, config: dict[str, Any]
) -> list[dict[str, Any]]:
    approved: list[dict[str, Any]] = []
    for platform in config.get("platforms", []):
        _validate_platform(platform)
        if not platform["enabled"]:
            continue
        source = conn.execute(
            """
            SELECT id FROM intelligence_sources
            WHERE url = ? AND source_kind = ? AND collection_mode = ?
              AND is_active = 1 AND TRIM(compliance_note) <> ''
            """,
            (
                platform["url"],
                platform["source_kind"],
                platform["collection_mode"],
            ),
        ).fetchone()
        if source is None:
            raise ValueError(
                f"平台{platform.get('name', platform['url'])}缺少已启用且具备合规说明的数据源"
            )
        approved.append({**platform, "source_id": int(source["id"])})
    if not approved:
        raise ValueError("crawler_config.json 中没有启用的平台")
    return approved


def _is_allowed_public_page(platform: dict[str, Any], url: str) -> bool:
    configured = urlsplit(platform["url"])
    candidate = urlsplit(url)
    return (
        configured.scheme == candidate.scheme
        and configured.netloc == candidate.netloc
        and any(candidate.path.startswith(path) for path in platform["allowed_public_pages"])
    )


def _page_title(html: str) -> str:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        if soup.title:
            return _strip_text(soup.title.get_text(" "))[:200]
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    return _strip_text(match.group(1))[:200] if match else ""


def _capture_payload(
    source_id: int,
    status_code: int,
    html: str,
    page_posts: list[dict[str, str]],
    error_message: str = "",
) -> dict[str, Any]:
    raw = html.encode("utf-8")
    excerpt = (
        f"公开岗位列表解析到 {len(page_posts)} 条样本；仅保存聚合采集元数据，不保存职位描述。"
        if not error_message
        else f"公开页面采集失败：{error_message[:300]}"
    )
    return {
        "source_id": source_id,
        "http_status": status_code or None,
        "content_hash": hashlib.sha256(raw).hexdigest(),
        "page_title": _page_title(html),
        "content_excerpt": excerpt,
        "content_bytes": len(raw),
        "error_message": error_message[:500],
    }


def _page_stop_reason(status_code: int, html: str, request_error: str) -> str:
    if request_error:
        return request_error
    if status_code in (429, 503):
        return f"HTTP {status_code}，停止当前页面采集"
    lowered = html.lower()
    if "captcha" in lowered or "验证" in html:
        return "检测到验证码页面，停止当前页面采集"
    if "login" in lowered or "登录" in html:
        return "检测到登录页面，停止当前页面采集"
    if status_code >= 400:
        return f"HTTP {status_code}，停止当前页面采集"
    return ""


def fetch_approved_posts(
    job_name: str,
    city: str,
    max_pages: int,
    config: dict[str, Any],
    logger: logging.Logger,
    approved_platforms: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    posts: list[dict[str, str]] = []
    source_snapshots: list[dict[str, Any]] = []
    city_codes = config.get("city_codes", {})
    for platform in approved_platforms:
        for page in range(max_pages):
            url = platform["search_url_template"].format(
                keyword=quote(job_name),
                city=quote(city),
                city_code=city_codes.get(city, city),
                page=page,
            )
            if not _is_allowed_public_page(platform, url):
                source_snapshots.append(
                    _capture_payload(
                        platform["source_id"], 0, "", [],
                        "配置生成了未获批准的公开页面",
                    )
                )
                break
            status_code, html, request_error = _http_get(url, config, logger)
            page_posts: list[dict[str, str]] = []
            stop_reason = _page_stop_reason(status_code, html, request_error)
            if not stop_reason:
                try:
                    page_posts = _parse_posts(html)
                except Exception as exc:
                    stop_reason = f"页面解析失败：{_strip_text(exc)}"
            source_snapshots.append(
                _capture_payload(
                    platform["source_id"], status_code, html, page_posts, stop_reason
                )
            )
            if stop_reason:
                logger.warning("page_stopped url=%s reason=%s", url, stop_reason)
                break
            for post in page_posts:
                post.setdefault("platform", platform["name"])
            posts.extend(page_posts)
            logger.info("page_fetched url=%s status=%s valid_items=%s", url, status_code, len(page_posts))
            time.sleep(random.uniform(1.5, 3.5))
    return posts, source_snapshots


def parse_salary_to_monthly(salary_text: str) -> tuple[int, int] | None:
    text = _strip_text(salary_text).lower()
    if not text or any(
        token in text for token in ("13薪", "年终", "股权", "期权", "面议", "保密")
    ):
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
    for city in CITY_LABELS:
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
        "company": _strip_text(post.get("company")),
        "title": _strip_text(post.get("title")),
        "salary_text": _strip_text(post.get("salary")),
        "salary": parse_salary_to_monthly(_strip_text(post.get("salary"))),
        "education": _extract_education(education, config.get("education_map", {})),
        "experience": _extract_experience(experience, config.get("experience_map", {})),
        "city": _extract_city(city),
        "description": text,
    }


def deduplicate_posts(
    posts: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    for post in posts:
        normalized = _normalize_post(post, config)
        fingerprint = hashlib.sha256(
            "\x1f".join(
                normalized[field].casefold()
                for field in ("company", "title", "city", "salary_text", "description")
            ).encode("utf-8")
        ).hexdigest()
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            unique.append(post)
    return unique


def confidence_for(
    source_count: int, sample_size: int, period_end: str | date, today: date
) -> str:
    try:
        end_date = period_end if isinstance(period_end, date) else date.fromisoformat(period_end)
    except ValueError:
        return "低"
    age_days = (today - end_date).days
    if age_days < 0 or age_days > 31 or source_count < 1 or sample_size < 1:
        return "低"
    if source_count >= 2 and sample_size >= 20:
        return "高"
    return "中"


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


def _record_source_snapshot(
    conn: sqlite3.Connection,
    data: dict[str, Any],
    created_by: int,
) -> int:
    row = conn.execute(
        "SELECT last_content_hash FROM intelligence_sources WHERE id = ?",
        (data["source_id"],),
    ).fetchone()
    if row is None:
        raise ValueError("source snapshot references an unknown source")
    content_hash = _strip_text(data.get("content_hash"))
    error_message = _strip_text(data.get("error_message"))[:500]
    if error_message:
        change_status = "采集失败"
    elif not row["last_content_hash"]:
        change_status = "首次采集"
    elif content_hash != row["last_content_hash"]:
        change_status = "有变化"
    else:
        change_status = "无变化"
    cursor = conn.execute(
        """
        INSERT INTO intelligence_source_snapshots (
            source_id, http_status, content_hash, page_title, content_excerpt,
            content_bytes, is_changed, error_message, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(data["source_id"]),
            data.get("http_status"),
            content_hash,
            _strip_text(data.get("page_title"))[:200],
            _strip_text(data.get("content_excerpt"))[:500],
            int(data.get("content_bytes") or 0),
            int(bool(content_hash and row["last_content_hash"] and content_hash != row["last_content_hash"])),
            error_message,
            created_by,
        ),
    )
    if error_message:
        conn.execute(
            """
            UPDATE intelligence_sources SET last_fetch_at = CURRENT_TIMESTAMP,
                last_change_status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (change_status, error_message, data["source_id"]),
        )
    else:
        conn.execute(
            """
            UPDATE intelligence_sources SET last_fetch_at = CURRENT_TIMESTAMP,
                last_content_hash = ?, last_change_status = ?, last_error = '',
                updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """,
            (content_hash, change_status, data["source_id"]),
        )
    return int(cursor.lastrowid)


def _insert_snapshot(
    conn: sqlite3.Connection,
    job_id: int,
    job_name: str,
    city: str,
    source_id: int,
    source_snapshot_id: int,
    owner_user_id: int,
    reviewer_user_id: int,
    period_start: str,
    period_end: str,
    next_check_at: str,
    aggregate: dict[str, Any],
    source_name: str,
) -> int:
    evidence_summary = (
        f"通过{source_name}采集公开招聘列表，关键词\"{job_name}\"，城市\"{city}\"，"
        f"共采集{aggregate['sample_size']}条有效薪资数据，"
        f"统计周期{period_start}至{period_end}。"
    )
    cursor = conn.execute(
        """
        INSERT INTO employment_market_snapshots (
            job_id, region, period_start, period_end, observed_posting_count,
            sample_size, salary_min, salary_median, salary_max, currency,
            salary_period, source_id, source_snapshot_id, evidence_summary, limitation_note,
            data_classification, owner_user_id, reviewer_user_id, next_check_at,
            status, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CNY', '月', ?, ?, ?, ?, '真实数据', ?, ?, ?, '草稿', ?)
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
            source_snapshot_id,
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
        approved_platforms = _approved_platforms(conn, config)
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

    posts, source_payloads = fetch_approved_posts(
        job_name, city, max_pages, config, logger, approved_platforms
    )
    posts = deduplicate_posts(posts, config)
    aggregate = aggregate_posts(posts, str(job["job_family"] or ""), config)
    approved_source_ids = {platform["source_id"] for platform in approved_platforms}

    with closing(_connect(db_path)) as conn:
        try:
            conn.execute("BEGIN")
            persisted_sources = []
            for payload in source_payloads:
                if payload.get("source_id") not in approved_source_ids:
                    raise ValueError("采集结果关联了未批准的数据源")
                snapshot_id = _record_source_snapshot(conn, payload, owner_id)
                persisted_sources.append((snapshot_id, payload))
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
            successful_sources = {
                payload["source_id"]
                for _, payload in persisted_sources
                if payload.get("http_status") == 200 and not payload.get("error_message")
            }
            confidence_level = confidence_for(
                len(successful_sources), aggregate["sample_size"], period_end, today
            )
            if confidence_level == "低":
                conn.commit()
                logger.info(
                    "task_insufficient_confidence job_name=%s city=%s source_count=%s sample_size=%s",
                    job_name,
                    city,
                    len(successful_sources),
                    aggregate["sample_size"],
                )
                return {
                    "status": "insufficient_confidence",
                    "confidence_level": confidence_level,
                }
            primary_snapshot_id, primary_payload = next(
                (
                    (snapshot_id, payload)
                    for snapshot_id, payload in persisted_sources
                    if payload.get("http_status") == 200 and not payload.get("error_message")
                ),
                (None, None),
            )
            if primary_snapshot_id is None or primary_payload is None:
                raise ValueError("中高置信度市场快照缺少成功来源快照")
            snapshot_id = _insert_snapshot(
                conn,
                int(job["id"]),
                job_name,
                city,
                int(primary_payload["source_id"]),
                primary_snapshot_id,
                owner_id,
                reviewer_id,
                period_start,
                period_end,
                next_check_at,
                aggregate,
                next(
                    platform["name"]
                    for platform in approved_platforms
                    if platform["source_id"] == primary_payload["source_id"]
                ),
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
        "confidence_level": confidence_level,
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
