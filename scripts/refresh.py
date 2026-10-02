"""Daily maintenance run. No AI, no credentials: executed by .github/workflows/refresh.yml.

What it does, in order:
  1. Recomputes the deadline status of every record.
  2. Closes finished cycles: snapshots them into archive/archive.json, then either
     rolls a recurring programme forward ("next cycle not announced") or moves a
     one-off opportunity out of the live database.
  3. Re-fetches each official page, stores its HTTP status and a fingerprint of
     its date/deadline lines, and flags dead links and changed pages.
  4. Harvests the RSS feeds listed in data/sources.json into data/leads.json.
     Leads are pointers only (title + link), always labelled NEEDS VERIFICATION.
  5. Writes data/meta.json and reports/latest.md.

What it never does: edit a factual field (deadline, funding, eligibility, URL).
Facts only change through a research cycle and scripts/upsert.py. See AGENTS.md.

    python scripts/refresh.py                 # full run
    python scripts/refresh.py --no-network    # statuses, lifecycle, meta, report only
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import oplib as L

LEAD_TTL_DAYS = 45
LEAD_MAX_AGE_DAYS = 30
MAX_LEADS = 250

INCLUDE = re.compile(
    r"scholarship|fellowship|fully[- ]funded|\bfunded\b|\bgrants?\b|bourses?\b|\bbecas?\b|\bbolsas?\b|"
    r"exchange|summit|conference|forum|\bprogram(me)?\b|\bawards?\b|\bprize\b|\bprix\b|competition|"
    r"concours|challenge|internship|\bstage\b|training|formation|volunt|bootcamp|accelerator|incubat|"
    r"residenc|summer school|winter school|appel [àa] candidatures|call for applications|"
    r"convocatoria|leadership|academy|delegat", re.I)
STRICT = re.compile(
    r"scholarship|fellowship|bourses?\b|call for applications|appel [àa] candidatures|volunt|"
    r"internship|\bstage\b|\bprix\b|award|concours|competition", re.I)
EXCLUDE = re.compile(
    r"\bjobs?\b|recrut|recruit|vacanc|appel d.offres|avis d.appel|consultan|prestataire|\btender\b|"
    r"lecturer|professor|post-?doc|\bhiring\b|\bRFP\b|\bRFAs?\b|how to\b|\bguide\b|comment postuler|"
    r"\btips\b|\bg[ée]n[ée]rateur\b|assurance|\bCV\b|recherche une?\b|\brecherche \d", re.I)
PROFILE = L.ROOT / "data" / "profile.json"
STOP = {"scholarship", "scholarships", "program", "programme", "fellowship", "fellowships", "fully",
        "funded", "international", "students", "student", "young", "youth", "applications", "apply",
        "africa", "african", "africans", "global", "world", "from", "with", "master", "masters",
        "bourse", "bourses", "pour", "des", "the", "and", "for", "call", "open", "university"}


# ---------------------------------------------------------------- lifecycle
def lifecycle(db: dict, archive: dict, today: dt.date, changes: list[dict]) -> None:
    stamp = today.isoformat()
    keep = []
    archived_ids = {a.get("archive_id") for a in archive["opportunities"]}
    for rec in db["opportunities"]:
        deadline = L.parse_date(rec.get("application_deadline"))
        if not deadline or (today - deadline).days <= L.ARCHIVE_GRACE_DAYS:
            keep.append(rec)
            continue
        archive_id = f"{rec['id']}@{rec['application_deadline']}"
        if archive_id not in archived_ids:
            snapshot = dict(rec)
            snapshot.update({"archive_id": archive_id, "archived_on": stamp, "status": "DEADLINE PASSED"})
            archive["opportunities"].append(snapshot)
        if rec.get("recurring"):
            closed = rec["application_deadline"]
            rec["last_cycle_deadline"] = closed
            rec["deadline_text"] = f"Last cycle closed on {closed}. Next cycle not announced yet."
            rec["application_deadline"] = rec["deadline_utc"] = rec["opens_on"] = ""
            if not rec.get("expected_next_cycle"):
                rec["expected_next_cycle"] = f"Recurring programme; previous cycle closed on {closed}."
            if rec.get("verification") == "VERIFIED":
                rec["verification"] = "PARTIALLY VERIFIED"
            note = (f"[auto {stamp}] Cycle closed. The details below describe the previous cycle "
                    f"and must be re-verified when the next call opens.")
            rec["notes"] = (rec.get("notes", "") + " " + note).strip()
            changes.append({"date": stamp, "id": rec["id"], "title": rec["title"],
                            "field": "(cycle closed)", "old": closed, "new": "rolled to next cycle"})
            keep.append(rec)
        else:
            changes.append({"date": stamp, "id": rec["id"], "title": rec["title"],
                            "field": "(archived)", "old": rec["application_deadline"], "new": "archive"})
    db["opportunities"] = keep


# ---------------------------------------------------------------- official-page watch
def watch(db: dict, today: dt.date) -> tuple[dict, list[dict]]:
    stamp = today.isoformat()
    state = L.load(L.WATCH, {})
    targets = [(r["id"], r["official_information_url"]) for r in db["opportunities"]
               if r.get("official_information_url")]

    def probe(target):
        rid, url = target
        status, _final, body = L.fetch(url, timeout=20)
        return rid, url, status, (L.date_lines_hash(body) if status == 200 and body else "")

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe, targets))

    summary = {"checked": len(results), "ok": 0, "blocked_or_unreachable": 0, "dead": 0}
    for rid, url, status, fingerprint in results:
        prev = state.get(rid, {})
        if prev.get("url") != url:
            prev = {}
        entry = {"url": url, "status": status, "checked": stamp,
                 "fingerprint": fingerprint or prev.get("fingerprint", ""),
                 "changed_on": prev.get("changed_on", ""),
                 "fail_streak": 0}
        if status == 200:
            summary["ok"] += 1
            if fingerprint and prev.get("fingerprint") and fingerprint != prev["fingerprint"]:
                entry["changed_on"] = stamp
        elif status in (404, 410):
            entry["fail_streak"] = prev.get("fail_streak", 0) + 1
            summary["dead"] += 1
        else:
            summary["blocked_or_unreachable"] += 1
        state[rid] = entry
    for rid in list(state):                    # forget records that left the database
        if rid not in {t[0] for t in targets}:
            del state[rid]
    L.save(L.WATCH, state)

    flags = []
    by_id = {r["id"]: r for r in db["opportunities"]}
    for rid, entry in state.items():
        rec = by_id.get(rid)
        if not rec:
            continue
        if entry["fail_streak"] >= 2:
            flags.append({"id": rid, "type": "dead_link", "since": entry["checked"],
                          "detail": f"Official page returned HTTP {entry['status']} on two runs."})
        if entry["changed_on"] and entry["changed_on"] > (rec.get("last_verified") or ""):
            flags.append({"id": rid, "type": "source_changed", "since": entry["changed_on"],
                          "detail": "Date or deadline wording on the official page changed after the "
                                    "last verification. Re-verify."})
    return summary, flags


# ---------------------------------------------------------------- feed harvest
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


def title_tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", title.lower()) if w not in STOP and not w.isdigit()}


def same_lead(a: str, b: str) -> bool:
    """Two feed titles that describe the same programme (aggregators reword each other)."""
    ta, tb = title_tokens(a), title_tokens(b)
    common = ta & tb
    return len(common) >= 2 and len(common) / max(1, min(len(ta), len(tb))) >= 0.7


def known_record(title: str, records: list[dict]) -> dict | None:
    low = title.lower()
    lead_tokens = title_tokens(title)
    for rec in records:
        for phrase in rec.get("match_keywords") or []:
            if phrase.lower() in low:
                return rec
        tokens = title_tokens(rec.get("title", ""))
        if len(tokens) >= 2 and len(tokens & lead_tokens) / len(tokens) >= 0.75:
            return rec
    return None


def audience_filter() -> re.Pattern | None:
    """Titles aimed at an audience the profile is not part of (set in data/profile.json)."""
    patterns = L.load(PROFILE, {}).get("lead_filters", {}).get("exclude_title_patterns", [])
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I) if patterns else None


def harvest(db: dict, archive: dict, today: dt.date) -> tuple[list[dict], list[dict], int]:
    stamp = today.isoformat()
    other_audience = audience_filter()
    sources = L.load(L.SOURCES, {"feeds": []})
    store = L.load(L.LEADS, {"schema_version": 1, "updated": "", "leads": []})
    records = db["opportunities"] + archive["opportunities"]
    # Keep a lead until it expires, or until a research cycle turns it into a record.
    leads = [lead for lead in store["leads"]
             if (today - (L.parse_date(lead.get("first_seen")) or today)).days <= LEAD_TTL_DAYS
             and not known_record(lead["title"], records)]
    have = {lead["id"] for lead in leads}
    feeds = [f for f in sources.get("feeds", []) if f.get("enabled", True)]

    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(lambda f: L.fetch(
            f["url"], timeout=25, accept="application/rss+xml,application/atom+xml,application/xml,*/*"),
            feeds))

    health, reseen, new_count = [], [], 0
    for feed, (status, _final, body) in zip(feeds, fetched):
        items = parse_feed(body) if status == 200 else []
        added = 0
        pattern = STRICT if feed.get("filter") == "strict" else INCLUDE
        for item in items:
            title, url = item["title"], item["url"]
            if not title or not url.startswith("http"):
                continue
            published = L.parse_date(item["published"])
            if published and (today - published).days > LEAD_MAX_AGE_DAYS:
                continue
            if not pattern.search(title) or EXCLUDE.search(title):
                continue
            if other_audience and other_audience.search(title):
                continue
            match = known_record(title, records)
            if match:
                reseen.append({"id": match["id"], "title": title, "url": url, "source": feed["name"],
                               "seen": stamp})
                continue
            lead_id = hashlib.sha1(L.norm_url(url).encode("utf-8")).hexdigest()[:12]
            if lead_id in have:
                continue
            twin = next((x for x in leads if same_lead(title, x["title"])), None)
            if twin:                              # same programme from another feed: corroboration
                if feed["name"] != twin["source"] and feed["name"] not in twin.setdefault("also_seen_in", []):
                    twin["also_seen_in"].append(feed["name"])
                continue
            have.add(lead_id)
            leads.append({"id": lead_id, "title": title, "url": url, "source": feed["name"],
                          "source_tier": feed.get("tier", 3), "language": feed.get("lang", "en"),
                          "published": item["published"], "first_seen": stamp,
                          "status": "NEEDS VERIFICATION"})
            added += 1
        new_count += added
        health.append({"name": feed["name"], "url": feed["url"], "tier": feed.get("tier", 3),
                       "status": status, "items": len(items), "new": added})

    leads.sort(key=lambda lead: (lead.get("first_seen", ""), lead.get("published", "")), reverse=True)
    store["leads"] = leads[:MAX_LEADS]
    store["updated"] = stamp
    L.save(L.LEADS, store)
    return health, reseen[:40], new_count


# ---------------------------------------------------------------- meta + report
def build_meta(db: dict, archive: dict, today: dt.date, extra: dict) -> dict:
    records = db["opportunities"]
    counts = {
        "total": len(records),
        "archived": len(archive["opportunities"]),
        "by_status": {s: sum(r["status"] == s for r in records) for s in L.STATUSES},
        "by_funding": {f: sum(r["funding_type"] == f for r in records) for f in L.FUNDING_TYPES},
        "by_eligibility": {e: sum(r["eligibility_for_me"] == e for r in records) for e in L.ELIGIBILITY},
        "by_verification": {v: sum(r["verification"] == v for r in records) for v in L.VERIFICATION},
        "travel_funded": sum(bool(r["travel_funded"]) for r in records),
    }
    buckets = {str(n): [] for n in L.DEADLINE_BUCKETS}
    for rec in records:
        left = L.days_remaining(rec, today)
        if left is None or left < 0:
            continue
        for limit in sorted(L.DEADLINE_BUCKETS):
            if left <= limit:
                buckets[str(limit)].append(rec["id"])
                break
    meta = L.load(L.META, {})
    meta.update({"schema_version": 1,
                 "last_refresh": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "counts": counts, "deadline_buckets": buckets})
    meta.update(extra)
    return meta


def write_report(db: dict, meta: dict, today: dt.date) -> None:
    records = db["opportunities"]
    by_id = {r["id"]: r for r in records}
    order = {"LIKELY ELIGIBLE": 0, "POSSIBLY ELIGIBLE": 1, "INSUFFICIENT INFORMATION": 2, "NOT ELIGIBLE": 3}
    live = [r for r in records if r["status"] in ("OPEN", "CLOSING SOON")
            and r["eligibility_for_me"] != "NOT ELIGIBLE" and r["source_confidence"] != "LOW"]
    live.sort(key=lambda r: (r["application_deadline"] or "9999", order[r["eligibility_for_me"]]))
    lines = [f"# Status report - {today.isoformat()}", "",
             "Generated by `scripts/refresh.py`. Facts come from `data/opportunities.json`; "
             "this file only re-arranges them.", "",
             f"- Live records: {meta['counts']['total']} (archived: {meta['counts']['archived']})",
             "- By status: " + ", ".join(f"{k} {v}" for k, v in meta["counts"]["by_status"].items() if v),
             "- By eligibility: " + ", ".join(f"{k} {v}" for k, v in meta["counts"]["by_eligibility"].items() if v),
             "", "## Action queue (open now, not ruled out)", ""]
    for i, rec in enumerate(live, 1):
        left = L.days_remaining(rec, today)
        lines += [f"{i}. **{rec['title']}** ({rec['organization']})",
                  f"   - Deadline: {rec['application_deadline']} ({left} days left) - {rec['deadline_text']}",
                  f"   - Status: {rec['status']} | Funding: {rec['funding_type']} | "
                  f"Eligibility: {rec['eligibility_for_me']} | Verification: {rec['verification']}",
                  f"   - Action: {rec.get('action') or 'Review the official page.'}",
                  f"   - Apply: {rec.get('official_application_url') or rec.get('official_information_url') or 'no verified link'}", ""]
    if not live:
        lines += ["Nothing open right now.", ""]
    risky = [r for r in records if r["source_confidence"] == "LOW"]
    if risky:
        lines += ["## Low-confidence listings (warnings, not recommendations)", ""]
        lines += [f"- **{r['title']}**: {'; '.join(r.get('potential_issues') or [])}" for r in risky] + [""]
    lines += ["## Deadline monitor", ""]
    for limit in sorted(L.DEADLINE_BUCKETS):
        ids = meta["deadline_buckets"].get(str(limit), [])
        label = "24 hours" if limit == 1 else f"{limit} days"
        names = "; ".join(f"{by_id[i]['title']} ({by_id[i]['application_deadline']})" for i in ids if i in by_id)
        lines.append(f"- Within {label}: {names or 'none'}")
    lines += ["", "## Flags raised by the automatic checks", ""]
    flags = meta.get("flags", [])
    lines += [f"- `{f['id']}` {f['type']} since {f['since']}: {f['detail']}" for f in flags] or ["- none"]
    lines += ["", "## Programmes seen again in the feeds (possible new cycle)", ""]
    reseen = meta.get("reseen", [])
    lines += [f"- `{r['id']}` <- {r['title']} ({r['source']}) {r['url']}" for r in reseen] or ["- none"]
    lines += ["", "## Feed health", "", "| Feed | Tier | HTTP | Items | New leads |", "|---|---|---|---|---|"]
    lines += [f"| {f['name']} | {f['tier']} | {f['status']} | {f['items']} | {f['new']} |"
              for f in meta.get("feeds", [])] or ["| (not run) | | | | |"]
    path = L.ROOT / "reports" / "latest.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--no-network", action="store_true", help="skip page checks and feeds")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    args = parser.parse_args()
    today = L.parse_date(args.today) or L.today_utc()
    stamp = today.isoformat()

    db, archive = L.load_db(), L.load_archive()
    changes: list[dict] = []
    lifecycle(db, archive, today, changes)
    db["opportunities"] = [L.normalize(r, today) for r in db["opportunities"]]
    db["opportunities"].sort(key=lambda r: r["id"])
    db["status_computed_on"] = stamp
    archive["updated"] = stamp

    extra: dict = {}
    if not args.no_network:
        try:
            summary, flags = watch(db, today)
            extra.update({"watch": summary, "flags": flags})
        except Exception as exc:  # noqa: BLE001 - never let a network hiccup block publishing
            print("watch failed:", exc)
        try:
            health, reseen, new_leads = harvest(db, archive, today)
            extra.update({"feeds": health, "reseen": reseen, "new_leads_last_run": new_leads})
        except Exception as exc:  # noqa: BLE001
            print("harvest failed:", exc)

    L.save(L.DB, db)
    L.save(L.ARCHIVE, archive)
    L.log_changes(changes)
    meta = build_meta(db, archive, today, extra)
    L.save(L.META, meta)
    write_report(db, meta, today)
    print(f"refresh: {meta['counts']['total']} live, {meta['counts']['archived']} archived, "
          f"{len(changes)} lifecycle changes, {extra.get('new_leads_last_run', 0)} new leads, "
          f"{len(meta.get('flags', []))} flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
