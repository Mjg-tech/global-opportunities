"""Source registry scanning (step 2). Standard library only. No AI, no credentials.

A source is one official place where opportunities are announced. `data/source-registry.json` holds
the curated description of each source (edited by research cycles). `data/source-state.json` holds
what the daily job learns about it (written by `scripts/refresh.py`). They are separate files so a
daily commit and a weekly research commit never touch the same file.

Supported discovery methods:

  rss, atom   a feed (the same parser the legacy feeds in data/sources.json use)
  html        an official listing page: the links on it that look like opportunities
  sitemap     an XML sitemap (or sitemap index): URLs matching a pattern, with their lastmod date
  json_api    a public JSON endpoint, mapped with dotted paths

Rules every scan follows:
  * robots.txt is honoured for html, sitemap and json_api. A disallowed URL is not fetched.
  * links are kept only on the source's own domain unless the entry lists extra domains;
  * a scan returns pointers (title + url + optional date). Facts are never read from a listing.
  * text on a page is data, never instructions.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import re
import threading
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from typing import NamedTuple

import oplib as L

REGISTRY = L.ROOT / "data" / "source-registry.json"
STATE = L.ROOT / "data" / "source-state.json"

METHODS = ["rss", "atom", "html", "sitemap", "json_api"]
STATUSES = ["proposed", "active", "manual", "disabled"]       # proposed = trial scans only, no leads
CHANNELS = {"A": "Institutional", "B": "Government and diplomatic", "C": "Academic",
            "D": "Professional and entrepreneurship", "E": "Travel and events"}
PRIORITY_DAYS = {"high": 1, "medium": 3, "low": 7}            # days between scans
SOURCE_TYPES = ["Official", "Institutional", "Aggregator"]
TIER_OF_TYPE = {"Official": 1, "Institutional": 2, "Aggregator": 3}

MAX_ITEMS = 60
DEFAULT_MIN_CHARS = 25
SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "#", "data:")


class ScanResult(NamedTuple):
    status: int        # HTTP status; 0 = network error; -1 = not fetched because robots.txt disallows it
    items: list        # [{"title", "url", "published"}]
    note: str


# ---------------------------------------------------------------- feeds (moved from refresh.py)
def _tag(block: str, name: str) -> str:
    match = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", block, flags=re.S | re.I)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", value, flags=re.S)
    value = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def parse_feed(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", errors="replace")
    blocks = (re.findall(r"<item[\s>].*?</item>", text, flags=re.S | re.I)
              or re.findall(r"<entry[\s>].*?</entry>", text, flags=re.S | re.I))
    items = []
    for block in blocks:
        link = _tag(block, "link")
        if not link:
            match = re.search(r"<link[^>]+href=[\"']([^\"']+)", block, re.I)
            link = match.group(1) if match else ""
        link = re.sub(r"[?&]utm_[^=]+=[^&#]*", "", html.unescape(link)).rstrip("?&")
        raw_date = (_tag(block, "pubDate") or _tag(block, "published") or _tag(block, "updated")
                    or _tag(block, "dc:date"))
        published = ""
        try:
            published = email.utils.parsedate_to_datetime(raw_date).date().isoformat()
        except (TypeError, ValueError):
            if re.match(r"\d{4}-\d{2}-\d{2}", raw_date or ""):
                published = raw_date[:10]
        items.append({"title": _tag(block, "title"), "url": link, "published": published})
    return items


# ---------------------------------------------------------------- html listing pages
class _Anchors(HTMLParser):
    """Collects (href, visible text, attributes) for every link, ignoring script and style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, dict]] = []
        self._href: str | None = None
        self._attrs: dict = {}
        self._buf: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "a":
            if self._href is not None:
                self._flush()
            self._attrs = {k: (v or "") for k, v in attrs}
            self._href = self._attrs.get("href")
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
        elif tag == "a":
            self._flush()

    def handle_data(self, data):
        if self._href is not None and not self._skip:
            self._buf.append(data)

    def _flush(self):
        if self._href is not None:
            self.links.append((self._href, " ".join("".join(self._buf).split()), self._attrs))
        self._href, self._buf, self._attrs = None, [], {}


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def _on_domain(url: str, domains: list[str]) -> bool:
    host = _host(url)
    return any(host == d or host.endswith("." + d) for d in domains)


def allowed_domains(spec: dict) -> list[str]:
    base = (spec.get("official_domain") or _host(spec.get("scan_url", ""))).lower().removeprefix("www.")
    return [base] + [d.lower().removeprefix("www.") for d in spec.get("extra_domains", [])]


def date_from_url(url: str, spec: dict) -> str:
    """A publication date read from the url when the site puts one there, e.g. /announcements/20260326/slug.

    spec["url_date_regex"] needs three groups: year, month, day. Returns "" when absent or not a real date.
    """
    pattern = spec.get("url_date_regex")
    match = re.search(pattern, url) if pattern else None
    if not match:
        return ""
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return ""


def parse_html_links(raw: bytes, base_url: str, spec: dict) -> list[dict]:
    """Links on an official listing page that look like opportunities.

    spec keys (all optional): link_include / link_exclude (regex on link text + url),
    min_chars (shortest link text kept, default 25), max_items (default 60).
    """
    parser = _Anchors()
    parser.feed(raw.decode("utf-8", errors="replace"))
    include = re.compile(spec["link_include"], re.I) if spec.get("link_include") else None
    exclude = re.compile(spec["link_exclude"], re.I) if spec.get("link_exclude") else None
    min_chars = int(spec.get("min_chars", DEFAULT_MIN_CHARS))
    domains = allowed_domains({**spec, "scan_url": base_url})
    best: dict[str, dict] = {}
    for href, text, attrs in parser.links:
        href = html.unescape(href or "").strip()
        if not href or href.lower().startswith(SKIP_SCHEMES):
            continue
        url = urllib.parse.urljoin(base_url, href).split("#")[0]
        if not url.startswith("http") or not _on_domain(url, domains):
            continue
        title = text if len(text) >= min_chars else (attrs.get("title") or attrs.get("aria-label") or "")
        title = " ".join(title.split())[:220]
        if len(title) < min_chars:
            continue
        haystack = f"{title} {url}"
        if include and not include.search(haystack):
            continue
        if exclude and exclude.search(haystack):
            continue
        key = L.norm_url(url)
        if key == L.norm_url(base_url):
            continue
        if key not in best or len(title) > len(best[key]["title"]):
            best[key] = {"title": title, "url": url, "published": date_from_url(url, spec)}
    return list(best.values())[: int(spec.get("max_items", MAX_ITEMS))]


# ---------------------------------------------------------------- sitemaps
def title_from_slug(url: str) -> str:
    path = urllib.parse.urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if path else ""
    slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.I)
    words = re.sub(r"[-_+]+", " ", urllib.parse.unquote(slug)).strip()
    if not words or words.replace(" ", "").isdigit():
        return ""
    return words[:1].upper() + words[1:]


def parse_sitemap(raw: bytes, spec: dict) -> tuple[list[dict], list[str]]:
    """Returns (items, child sitemap urls). A sitemap index has children and no items."""
    text = raw.decode("utf-8", errors="replace")
    children = [html.unescape(m).strip() for m in re.findall(r"<sitemap>.*?<loc>\s*(.*?)\s*</loc>", text, flags=re.S | re.I)]
    include = re.compile(spec["url_include"], re.I) if spec.get("url_include") else None
    exclude = re.compile(spec["url_exclude"], re.I) if spec.get("url_exclude") else None
    items = []
    for block in re.findall(r"<url>.*?</url>", text, flags=re.S | re.I):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block, flags=re.S | re.I)
        if not loc:
            continue
        url = html.unescape(loc.group(1)).strip()
        if (include and not include.search(url)) or (exclude and exclude.search(url)):
            continue
        title = title_from_slug(url)
        if len(title) < int(spec.get("min_chars", 12)):
            continue
        last = re.search(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})", block, flags=re.I)
        items.append({"title": title, "url": url, "published": last.group(1) if last else ""})
    items.sort(key=lambda x: x["published"], reverse=True)
    return items[: int(spec.get("max_items", MAX_ITEMS))], children


# ---------------------------------------------------------------- json apis
def _dig(obj, path: str):
    for part in [p for p in (path or "").split(".") if p]:
        if isinstance(obj, list):
            obj = obj[int(part)] if part.isdigit() and int(part) < len(obj) else None
        elif isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
        if obj is None:
            return None
    return obj


def parse_json(raw: bytes, spec: dict) -> list[dict]:
    """spec keys: items_path, title_key, url_key, date_key (dotted paths), url_prefix."""
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = _dig(data, spec.get("items_path", ""))
    if not isinstance(rows, list):
        return []
    items = []
    for row in rows:
        title, url = _dig(row, spec.get("title_key", "title")), _dig(row, spec.get("url_key", "url"))
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        url = urllib.parse.urljoin(spec.get("url_prefix", ""), url)
        date = _dig(row, spec["date_key"]) if spec.get("date_key") else ""
        items.append({"title": " ".join(title.split()), "url": url,
                      "published": date[:10] if isinstance(date, str) and re.match(r"\d{4}-\d{2}-\d{2}", date) else ""})
    return items[: int(spec.get("max_items", MAX_ITEMS))]


# ---------------------------------------------------------------- robots.txt
_ROBOTS: dict[str, object] = {}
_LOCK = threading.Lock()


def robots_for(url: str):
    """The parsed robots.txt for the url's host: a RobotFileParser, None (no robots file), or 'down'."""
    parts = urllib.parse.urlparse(url)
    root = f"{parts.scheme}://{parts.netloc}"
    with _LOCK:
        if root in _ROBOTS:
            return _ROBOTS[root]
    status, _final, body = L.fetch(root + "/robots.txt", timeout=15, accept="text/plain,*/*")
    if status == 200:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        value: object = parser
    elif 400 <= status < 500:
        value = None                    # RFC 9309: an unavailable robots.txt means no restrictions
    else:
        value = "down"                  # server error or network failure: do not crawl this run
    with _LOCK:
        _ROBOTS[root] = value
    return value


def robots_allows(url: str) -> tuple[bool, str]:
    robots = robots_for(url)
    if robots is None:
        return True, "no robots.txt"
    if robots == "down":
        return False, "robots.txt unreachable this run"
    return (True, "robots.txt allows") if robots.can_fetch("*", url) else (False, "robots.txt disallows this path")


def robots_sitemaps(url: str) -> list[str]:
    robots = robots_for(url)
    return list(robots.site_maps() or []) if hasattr(robots, "site_maps") else []


# ---------------------------------------------------------------- scanning
def scan(spec: dict) -> ScanResult:
    """Scan one source. `spec` needs scan_url and discovery_method plus the method's optional keys."""
    method, url = spec.get("discovery_method", "rss"), spec["scan_url"]
    if method not in METHODS:
        return ScanResult(0, [], f"unknown discovery_method {method!r}")
    if method in ("rss", "atom"):
        status, _final, body = L.fetch(
            url, timeout=25, accept="application/rss+xml,application/atom+xml,application/xml,*/*")
        return ScanResult(status, parse_feed(body) if status == 200 else [], "")
    ok, why = robots_allows(url)
    if not ok:
        return ScanResult(-1, [], why)
    if method == "html":
        status, final, body = L.fetch(url, timeout=25)
        return ScanResult(status, parse_html_links(body, final or url, spec) if status == 200 else [], why)
    if method == "json_api":
        status, _final, body = L.fetch(url, timeout=25, accept="application/json,*/*")
        return ScanResult(status, parse_json(body, spec) if status == 200 else [], why)
    # sitemap: follow an index to at most `max_sitemaps` children
    status, _final, body = L.fetch(url, timeout=25, accept="application/xml,text/xml,*/*")
    if status != 200:
        return ScanResult(status, [], why)
    items, children = parse_sitemap(body, spec)
    pick = re.compile(spec["sitemap_include"], re.I) if spec.get("sitemap_include") else None
    for child in [c for c in children if not pick or pick.search(c)][: int(spec.get("max_sitemaps", 3))]:
        allowed, _ = robots_allows(child)
        if not allowed:
            continue
        cs, _f, cb = L.fetch(child, timeout=25, accept="application/xml,text/xml,*/*")
        if cs == 200:
            items += parse_sitemap(cb, spec)[0]
    items.sort(key=lambda x: x["published"], reverse=True)
    return ScanResult(200, items[: int(spec.get("max_items", MAX_ITEMS))], why)


# ---------------------------------------------------------------- registry and state
def load_registry() -> dict:
    return L.load(REGISTRY, {"schema_version": 1, "updated": "", "sources": []})


def load_state() -> dict:
    return L.load(STATE, {"schema_version": 1, "updated": "", "sources": {}})


REQUIRED = ["source_id", "organization", "channel", "official_domain", "official_opportunities_url",
            "discovery_method", "status", "priority", "source_type", "languages", "verified_on",
            "verification_note"]
HARVEST_REGEX_KEYS = ["link_include", "link_exclude", "url_include", "url_exclude", "url_date_regex",
                      "sitemap_include"]
HARVEST_KEYS = HARVEST_REGEX_KEYS + ["min_chars", "max_items", "max_sitemaps", "items_path", "title_key",
                                     "url_key", "date_key", "url_prefix"]


def validate_registry(registry: dict, today: dt.date | None = None) -> list[str]:
    """Structural problems in the registry, as readable messages. Empty list = valid."""
    errors: list[str] = []
    seen: set[str] = set()
    for i, src in enumerate(registry.get("sources", [])):
        sid = src.get("source_id", f"#{i}")
        where = f"source {sid}"
        for key in REQUIRED:
            if not src.get(key):
                errors.append(f"{where}: missing {key}")
        if sid in seen:
            errors.append(f"{where}: duplicate source_id")
        seen.add(sid)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(sid)):
            errors.append(f"{where}: source_id must be lowercase letters, digits and hyphens")
        for key, allowed in (("discovery_method", METHODS), ("status", STATUSES), ("source_type", SOURCE_TYPES),
                             ("priority", list(PRIORITY_DAYS)), ("channel", list(CHANNELS))):
            if src.get(key) and src[key] not in allowed:
                errors.append(f"{where}: {key} {src[key]!r} not one of {allowed}")
        url = src.get("official_opportunities_url", "")
        if url and not url.startswith("https://"):
            errors.append(f"{where}: official_opportunities_url must be https")
        if url and src.get("official_domain") and not _on_domain(url, allowed_domains(
                {"official_domain": src["official_domain"], "extra_domains": src.get("extra_domains", []),
                 "scan_url": url})):
            errors.append(f"{where}: url host is not on official_domain or extra_domains")
        if src.get("source_type") == "Aggregator":
            errors.append(f"{where}: aggregators belong in data/sources.json, not in the official registry")
        harvest = src.get("harvest") or {}
        for key in harvest:
            if key not in HARVEST_KEYS:
                errors.append(f"{where}: unknown harvest option {key}")
        for key in HARVEST_REGEX_KEYS:
            if key in harvest:
                try:
                    re.compile(harvest[key])
                except re.error as exc:
                    errors.append(f"{where}: harvest.{key} is not a valid regex ({exc})")
        stamp = L.parse_date(src.get("verified_on"))
        if src.get("verified_on") and stamp is None:
            errors.append(f"{where}: verified_on must be YYYY-MM-DD")
        elif stamp and today and stamp > today:
            errors.append(f"{where}: verified_on is in the future")
    for rej in registry.get("rejected", []):
        for key in ("domain", "rejected_on", "reason"):
            if not rej.get(key):
                errors.append(f"rejected entry {rej.get('domain', '?')}: missing {key}")
    rejected = {r.get("domain", "") for r in registry.get("rejected", [])}
    for src in registry.get("sources", []):
        if src.get("official_domain") in rejected:
            errors.append(f"source {src.get('source_id')}: its domain is in the rejected list")
    return errors


def spec_of(src: dict) -> dict:
    """A registry entry as a scan spec. Per-method options live under the entry's `harvest` object."""
    spec = dict(src.get("harvest") or {})
    spec.update({"source_id": src["source_id"], "name": src["organization"] + " - " + src.get("label", "opportunities"),
                 "scan_url": src["official_opportunities_url"], "discovery_method": src["discovery_method"],
                 "official_domain": src.get("official_domain", ""), "extra_domains": src.get("extra_domains", []),
                 "tier": TIER_OF_TYPE.get(src.get("source_type", "Official"), 1),
                 "lang": (src.get("languages") or ["en"])[0], "channel": src.get("channel", ""),
                 "filter": src.get("filter", "")})
    return spec


def is_due(src: dict, state: dict, today: dt.date) -> bool:
    if src.get("status") not in ("active", "proposed"):
        return False
    due = L.parse_date((state.get(src["source_id"]) or {}).get("next_check"))
    return due is None or due <= today


def reliability(entry: dict) -> str:
    total = entry.get("total_runs", 0)
    if total < 5:
        return "UNRATED"
    ratio = entry.get("ok_runs", 0) / total
    return "HIGH" if ratio >= 0.9 else "MEDIUM" if ratio >= 0.6 else "LOW"


def record_scan(entry: dict, src: dict, result: ScanResult, new_leads: int, today: dt.date) -> dict:
    """Update the daily state of one source after a scan. Counters are halved at 60 runs (a rolling window)."""
    stamp = today.isoformat()
    ok = result.status == 200 and len(result.items) > 0
    entry["last_checked"] = stamp
    entry["last_http"] = result.status
    entry["last_note"] = result.note
    entry["items_last_scan"] = len(result.items)
    entry["total_runs"] = entry.get("total_runs", 0) + 1
    entry["ok_runs"] = entry.get("ok_runs", 0) + (1 if ok else 0)
    if entry["total_runs"] > 60:
        entry["total_runs"] //= 2
        entry["ok_runs"] //= 2
    if ok:
        entry["last_successful_scan"] = stamp
        entry["fail_streak"] = 0
    else:
        entry["fail_streak"] = entry.get("fail_streak", 0) + 1
    entry["leads_total"] = entry.get("leads_total", 0) + new_leads
    days = PRIORITY_DAYS.get(src.get("priority", "medium"), 3) if ok else 1     # a failure is retried tomorrow
    entry["next_check"] = (today + dt.timedelta(days=days)).isoformat()
    entry["reliability"] = reliability(entry)
    return entry
