"""Verify and inspect sources. Read-only: nothing here writes a data file.

    python scripts/sources.py probe URL [--method html|rss|atom|sitemap|json_api]
                                        [--include REGEX] [--exclude REGEX] [--min-chars N] [--domain D]
    python scripts/sources.py list

`probe` is the check a source must pass before it enters data/source-registry.json: does the page
answer an automated reader, does robots.txt allow it, does it offer a feed or sitemap, and does the
scanner find items that the lead filters would keep. It prints a draft registry entry; a person or a
research cycle decides whether to add it (as `proposed` first).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse

import leadfilter as LF
import oplib as L
import sourcelib as S


def detect_method(body: bytes) -> str:
    head = body[:4000].decode("utf-8", errors="replace").lstrip().lower()
    if "<urlset" in head or "<sitemapindex" in head:
        return "sitemap"
    if "<rss" in head or "<feed" in head or ("<?xml" in head and "<channel" in head):
        return "rss"
    if head.startswith("{") or head.startswith("["):
        return "json_api"
    return "html"


def discover_links(body: bytes, base: str) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    found = []
    for tag in re.findall(r"<link\b[^>]*>", text, flags=re.I):
        if re.search(r"rel=[\"']alternate[\"']", tag, re.I) and re.search(r"type=[\"']application/(rss|atom)\+xml", tag, re.I):
            href = re.search(r"href=[\"']([^\"']+)", tag, re.I)
            if href:
                found.append(urllib.parse.urljoin(base, href.group(1)))
    return found


def probe(args: argparse.Namespace) -> int:
    url = args.url
    host = urllib.parse.urlparse(url).hostname or ""
    domain = (args.domain or host).lower().removeprefix("www.")
    print(f"URL      {url}")
    allowed, why = S.robots_allows(url)
    print(f"robots   {why}")
    sitemaps = S.robots_sitemaps(url)
    if sitemaps:
        print("sitemaps declared in robots.txt:", *sitemaps[:5], sep="\n   ")
    status, final, body = L.fetch(url, timeout=25)
    print(f"fetch    HTTP {status}, {len(body)} bytes" + (f", redirected to {final}" if final and final != url else ""))
    if status != 200:
        print("RESULT   not readable by an automated reader: register as `manual`, never as `active`.")
        return 1
    feeds = discover_links(body, final or url)
    if feeds:
        print("feeds advertised on the page:", *feeds[:5], sep="\n   ")
    method = args.method or detect_method(body)
    print(f"method   {method}" + ("" if args.method else " (auto-detected)"))
    if not allowed:
        print("RESULT   robots.txt does not allow this path: do not scan it.")
        return 1
    harvest = {k: v for k, v in (("link_include", args.include), ("link_exclude", args.exclude),
                                 ("min_chars", args.min_chars)) if v}
    spec = {"scan_url": url, "discovery_method": method, "official_domain": domain, **harvest}
    result = S.scan(spec)
    print(f"scan     HTTP {result.status}, {len(result.items)} items")
    kept = 0
    for item in result.items:
        verdict = LF.assess(item["title"], item["published"], 1, "", L.today_utc())
        kept += verdict.kind == "lead"
        mark = f"lead {verdict.score:>3}" if verdict.kind == "lead" else f"skip ({verdict.reason})"
        print(f"   {mark:<26} {item['title'][:84]}")
    print(f"yield    {kept} of {len(result.items)} items would become leads")
    entry = {"source_id": re.sub(r"[^a-z0-9]+", "-", domain).strip("-"), "organization": "FILL IN",
             "official_domain": domain, "official_opportunities_url": url, "discovery_method": method,
             "status": "proposed", "channel": "FILL IN (A-E)", "priority": "medium", "source_type": "Official",
             "languages": ["en"], "harvest": harvest}
    print("draft entry (fill in the blanks, keep it `proposed` until trial scans look right):")
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return 0 if kept else 2


def listing(_args: argparse.Namespace) -> int:
    registry, state = S.load_registry()["sources"], S.load_state()["sources"]
    print(f"{len(registry)} sources")
    for src in registry:
        st = state.get(src["source_id"], {})
        print(f"  {src['status']:<9} {src.get('channel', '?')} {src['source_id']:<34} {src['discovery_method']:<8} "
              f"last ok {st.get('last_successful_scan', '-'):<10} items {st.get('items_last_scan', '-')!s:<4} "
              f"leads {st.get('leads_total', 0):<4} {st.get('reliability', 'UNRATED')}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("url")
    p.add_argument("--method", choices=S.METHODS)
    p.add_argument("--include", help="regex a link's text or url must match")
    p.add_argument("--exclude", help="regex that drops a link")
    p.add_argument("--min-chars", type=int, dest="min_chars")
    p.add_argument("--domain", help="official domain if different from the url's host")
    p.set_defaults(func=probe)
    sub.add_parser("list").set_defaults(func=listing)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
