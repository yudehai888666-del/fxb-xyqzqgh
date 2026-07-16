import hashlib
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib import error, parse, request, robotparser

from flask import current_app, has_app_context

from app import repositories


USER_AGENT = "AcademicPlanningResearchBot/1.0"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/json")


class CollectionError(ValueError):
    pass


SYNTHETIC_EGRESS_NETWORK = ipaddress.ip_network("198.18.0.0/15")


def validate_public_url(url, resolver=socket.getaddrinfo, allow_synthetic_egress=None):
    parsed = parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise CollectionError("仅支持公开的 HTTP 或 HTTPS 网页")
    if parsed.username or parsed.password:
        raise CollectionError("数据源链接不能包含账号或密码")
    try:
        port = parsed.port
    except ValueError as exc:
        raise CollectionError("数据源端口无效") from exc
    if port is not None and port not in (80, 443):
        raise CollectionError("仅允许标准网页端口 80 或 443")
    try:
        addresses = resolver(parsed.hostname, port or (443 if parsed.scheme == "https" else 80))
    except OSError as exc:
        raise CollectionError("无法解析数据源域名") from exc
    if not addresses:
        raise CollectionError("无法解析数据源域名")
    if allow_synthetic_egress is None:
        allow_synthetic_egress = bool(
            has_app_context() and current_app.config.get("ALLOW_SYNTHETIC_EGRESS")
        )
    try:
        hostname_is_literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        hostname_is_literal_ip = None
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        if (allow_synthetic_egress and hostname_is_literal_ip is None and
                ip in SYNTHETIC_EGRESS_NETWORK):
            continue
        if (not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise CollectionError("禁止采集本机、内网或保留网络地址")
    return parsed


class _SafeRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.text_parts = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._ignored_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text or self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)


def _open(opener, url, timeout):
    req = request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,text/plain,application/json;q=0.9",
        },
    )
    return opener.open(req, timeout=timeout)


def _robots_allows(opener, parsed, target_url, timeout):
    robots_url = parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        with _open(opener, robots_url, timeout) as response:
            raw = response.read(256 * 1024 + 1)
            if len(raw) > 256 * 1024:
                raise CollectionError("robots.txt 过大，已停止采集")
            charset = response.headers.get_content_charset() or "utf-8"
            rules = raw.decode(charset, errors="replace").splitlines()
    except error.HTTPError as exc:
        if exc.code == 404:
            return True
        raise CollectionError(f"无法确认 robots 规则（HTTP {exc.code}）") from exc
    except error.URLError as exc:
        raise CollectionError("无法读取 robots 规则，已停止采集") from exc
    parser = robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(rules)
    return parser.can_fetch(USER_AGENT, target_url)


def fetch_public_page(url, timeout=10, max_bytes=MAX_RESPONSE_BYTES):
    parsed = validate_public_url(url)
    opener = request.build_opener(_SafeRedirectHandler())
    if not _robots_allows(opener, parsed, url, timeout):
        raise CollectionError("robots.txt 不允许自动采集该页面")
    try:
        with _open(opener, url, timeout) as response:
            final_url = response.geturl()
            validate_public_url(final_url)
            content_type = response.headers.get_content_type().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise CollectionError(f"不支持采集该内容类型：{content_type}")
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise CollectionError("页面超过 2MB 采集上限")
            charset = response.headers.get_content_charset() or "utf-8"
            decoded = raw.decode(charset, errors="replace")
            status = getattr(response, "status", 200)
    except CollectionError:
        raise
    except error.HTTPError as exc:
        raise CollectionError(f"数据源返回 HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise CollectionError("无法连接数据源") from exc
    except TimeoutError as exc:
        raise CollectionError("连接数据源超时") from exc

    if content_type == "text/html":
        parser = _ReadableHTMLParser()
        parser.feed(decoded)
        title = " ".join(parser.title_parts)[:300]
        readable_text = " ".join(parser.text_parts)
    else:
        title = ""
        readable_text = decoded
    normalized_text = re.sub(r"\s+", " ", readable_text).strip()
    if not normalized_text:
        raise CollectionError("页面没有可用于比对的公开文本")
    return {
        "http_status": status,
        "content_hash": hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
        "page_title": title,
        "content_excerpt": normalized_text[:4000],
        "content_bytes": len(raw),
        "error_message": "",
    }


def collect_source(source_id, created_by=None):
    source = repositories.get_intelligence_source(source_id)
    if source is None or not source["is_active"]:
        raise CollectionError("数据源不存在或已停用")
    try:
        snapshot = fetch_public_page(source["url"])
    except CollectionError as exc:
        snapshot = {
            "http_status": None,
            "content_hash": "",
            "page_title": "",
            "content_excerpt": "",
            "content_bytes": 0,
            "error_message": str(exc)[:500],
        }
    snapshot_id, change_status = repositories.record_intelligence_snapshot(
        source_id, snapshot, created_by
    )
    return snapshot_id, change_status, snapshot.get("error_message", "")
