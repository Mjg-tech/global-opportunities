"""Daily maintenance run. No AI, no credentials: executed by .github/workflows/refresh.yml.

What it does, in order:
  1. Recomputes the deadline status of every record.
  2. Closes finished cycles: snapshots them into archive/archive.json, then either
     rolls a recurring programme forward ("next cycle not announced") or moves a
     one-off opportunity out of the live database.
  3. Re-fetches each official page, stores its HTTP status and a fingerprint of
     its date/deadline lines, and flags dead links and changed pages.
  4. Harvests the RSS feeds listed in data/sources.json into data/leads.json (scored, never
     deleted: see scripts/leadfilter.py and data/lead-rules.json).
     Leads are pointers only (title + link). They start as NEW and are never treated as verified.
  5. Writes data/meta.json and reports/latest.md.

What it never does: edit a factual field (deadline, funding, eligibility, URL).
Facts only change through a research cycle and scripts/upsert.py. See AGENTS.md.

    python scripts/refresh.py                 # full run
    python scripts/refresh.py --no-network    # statuses, lifecycle, meta, report only
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import leadfilter as LF
import cycles as CY
import evidence as EV
import oplib as L
import sourcelib as S

# Lead filtering, scoring and retention numbers live in leadfilter.py and data/lead-rules.json.
LEADS_ARCHIVE = L.ROOT / "archive" / "leads-archive.json"
LEAD_AUDIT = L.ROOT / "data" / "lead-audit.json"
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
parse_feed = S.parse_feed          # the feed parser lives in sourcelib; kept here for callers and tests


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


def lead_id_of(url: str) -> str:
    return hashlib.sha1(L.norm_url(url).encode("utf-8")).hexdigest()[:12]


def harvest(db: dict, archive: dict, today: dt.date) -> tuple[list[dict], list[dict], int, dict]:
    """Read the feeds and the due registry sources into data/leads.json. Nothing is deleted:

    * a title the filters reject is written to data/lead-audit.json with the reason;
    * a lead that expires, is published as a record, or no longer fits under the cap moves to
      archive/leads-archive.json;
    * words that suggest a restricted audience lower a lead's score, they never remove it.
    """
    stamp = today.isoformat()
    rules = LF.load_rules()
    ret = rules["retention"]
    sources = L.load(L.SOURCES, {"feeds": []})
    store = L.load(L.LEADS, {"schema_version": 1, "updated": "", "leads": []})
    lead_archive = L.load(LEADS_ARCHIVE, {"schema_version": 1, "updated": "", "leads": []})
    audit = L.load(LEAD_AUDIT, {"schema_version": 1, "updated": "", "entries": []})
    previous = {f["name"]: f for f in L.load(L.META, {}).get("feeds", [])}
    records = db["opportunities"] + archive["opportunities"]

    leads, retired = [], []
    for lead in store["leads"]:
        LF.migrate_lead(lead, today, rules)
        age = (today - (L.parse_date(lead.get("first_seen")) or today)).days
        if known_record(lead["title"], records):
            lead["status"] = "PUBLISHED"
            retired.append((lead, "now a record in the database"))
        elif lead["status"] in LF.TERMINAL_STATUSES:
            retired.append((lead, f"closed by research ({lead['status']})"))
        elif lead["status"] == "NEW" and age > ret["ttl_days"]:
            retired.append((lead, f"not reviewed within {ret['ttl_days']} days"))
        else:
            leads.append(lead)
    by_id = {lead["id"]: lead for lead in leads}
    gone = {x["id"] for x in lead_archive["leads"]} | {lead["id"] for lead, _ in retired}
    audited = {e["id"] for e in audit["entries"]}
    feeds = [f for f in sources.get("feeds", []) if f.get("enabled", True)]
    registry = S.load_registry()["sources"]
    src_state = S.load_state()
    state_map = src_state.setdefault("sources", {})
    for src in registry:                      # registry sources join the legacy feeds as scan units
        if S.is_due(src, state_map, today):
            spec = S.spec_of(src)
            feeds.append({"name": spec["name"], "url": spec["scan_url"], "tier": spec["tier"],
                          "lang": spec["lang"], "filter": spec["filter"], "_spec": spec, "_src": src,
                          "_trial": src["status"] == "proposed"})

    def run_unit(unit: dict) -> S.ScanResult:
        if "_spec" not in unit:
            status, _final, body = L.fetch(
                unit["url"], timeout=25, accept="application/rss+xml,application/atom+xml,application/xml,*/*")
            return S.ScanResult(status, parse_feed(body) if status == 200 else [], "")
        try:
            return S.scan(unit["_spec"])
        except Exception as exc:  # noqa: BLE001 - one broken source must not stop the others
            return S.ScanResult(0, [], f"scan error: {type(exc).__name__}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        scans = list(pool.map(run_unit, feeds))

    health, reseen, new_count = [], [], 0
    source_rows: list[dict] = []
    rejected_total: dict[str, int] = {}
    for feed, scan in zip(feeds, scans):
        status, items = scan.status, scan.items
        trial = feed.get("_trial", False)
        added, valid, would_add = 0, 0, 0
        skipped: dict[str, int] = {}
        for item in items:
            title, url = item["title"], item["url"]
            if not title or not url.startswith("http"):
                continue
            valid += 1
            result = LF.assess(title, item["published"], feed.get("tier", 3), feed.get("filter", ""), today, rules)
            if trial:                         # trial scan: measure what would become a lead, store nothing
                lid = lead_id_of(url)
                if (result.kind == "lead" and lid not in by_id and lid not in gone
                        and not known_record(title, records)):
                    would_add += 1
                continue
            if result.kind == "reject":
                skipped[result.reason] = skipped.get(result.reason, 0) + 1
                rejected_total[result.reason] = rejected_total.get(result.reason, 0) + 1
                lid = lead_id_of(url)
                if result.reason != "too_old" and lid not in audited:
                    audit["entries"].append({"id": lid, "date": stamp, "source": feed["name"], "title": title,
                                             "url": url, "reason": result.reason, "detail": result.detail})
                    audited.add(lid)
                continue
            match = known_record(title, records)
            if match:
                reseen.append({"id": match["id"], "title": title, "url": url, "source": feed["name"],
                               "seen": stamp})
                continue
            lead_id = lead_id_of(url)
            if lead_id in by_id:
                by_id[lead_id]["last_seen"] = stamp
                continue
            if lead_id in gone:
                continue
            twin = next((x for x in leads if same_lead(title, x["title"])), None)
            if twin:                              # same programme from another feed: corroboration
                if feed["name"] != twin["source"] and feed["name"] not in twin.setdefault("also_seen_in", []):
                    twin["also_seen_in"].append(feed["name"])
                twin["last_seen"] = stamp
                continue
            flags = list(result.flags)
            earlier = next((x for x in lead_archive["leads"] if same_lead(title, x["title"])), None)
            lead = {"id": lead_id, "title": title, "url": url, "source": feed["name"],
                    "source_tier": feed.get("tier", 3), "language": feed.get("lang", "en"),
                    "published": item["published"], "first_seen": stamp, "last_seen": stamp,
                    "status": "NEW", "score": result.score, "flags": flags}
            if earlier:                           # a programme seen in an earlier cycle: possible new edition
                lead["seen_before"] = earlier["id"]
                flags.append("recurring:seen-before")
            leads.append(lead)
            by_id[lead_id] = lead
            added += 1
        new_count += added
        if "_src" in feed:                    # registry source: its counters live in data/source-state.json
            entry = S.record_scan(state_map.setdefault(feed["_src"]["source_id"], {}), feed["_src"], scan, added, today)
            if trial:
                entry["trial_scans"] = entry.get("trial_scans", 0) + 1
                entry["trial_would_be_leads"] = entry.get("trial_would_be_leads", 0) + would_add
            source_rows.append({"id": feed["_src"]["source_id"], "name": feed["name"], "status": feed["_src"]["status"],
                                "http": status, "items": len(items), "new": added, "would_add": would_add,
                                "note": scan.note if status != 200 or not items else ""})
            continue
        prev = previous.get(feed["name"], {})
        empty = status != 200 or not items
        stale = status == 200 and valid > 0 and skipped.get("too_old", 0) == valid
        row = {"name": feed["name"], "url": feed["url"], "tier": feed.get("tier", 3), "status": status,
               "items": len(items), "new": added, "skipped": skipped,
               "empty_streak": prev.get("empty_streak", 0) + 1 if empty else 0,
               "stale_streak": prev.get("stale_streak", 0) + 1 if stale else 0}
        limit = ret["feed_alert_after_runs"]
        row["alert"] = (f"no items for {row['empty_streak']} runs" if row["empty_streak"] >= limit
                        else f"only stale items for {row['stale_streak']} runs" if row["stale_streak"] >= limit
                        else "")
        health.append(row)

    cap = ret["max_active_leads"]
    over = len(leads) - cap
    if over > 0:                                  # only untouched (NEW) leads can fall below the cap
        weakest = sorted((x for x in leads if x["status"] == "NEW"),
                         key=lambda x: (x["score"], x.get("first_seen", ""), x["id"]))[:over]
        dropped = {x["id"] for x in weakest}
        retired += [(x, f"below the cap of {cap} active leads") for x in weakest]
        leads = [x for x in leads if x["id"] not in dropped]
    leads.sort(key=lambda x: (x["score"], x.get("first_seen", ""), x["id"]), reverse=True)

    for lead, reason in retired:
        old = dict(lead)
        old.update({"archived_on": stamp, "archive_reason": reason})
        if old["status"] == "NEW":               # a research status (PUBLISHED, EXCLUDED, ...) is kept as it was
            old["status_before_archive"], old["status"] = "NEW", "ARCHIVED"
        lead_archive["leads"].append(old)
    audit["entries"] = LF.trim_audit(audit["entries"], today, ret["audit_days"])
    for doc in (store, lead_archive, audit):
        doc["updated"] = stamp
    store["leads"] = leads
    L.save(L.LEADS, store)
    L.save(LEADS_ARCHIVE, lead_archive)
    L.save(LEAD_AUDIT, audit)
    if source_rows:
        src_state["updated"] = stamp
        L.save(S.STATE, src_state)
    summary = {"active": len(leads), "archived_total": len(lead_archive["leads"]),
               "retired_this_run": len(retired), "rejected_this_run": rejected_total,
               "audit_entries": len(audit["entries"]),
               "sources": {"registered": len(registry), "scanned": len(source_rows),
                           "failed": [r["id"] for r in source_rows if r["http"] != 200 or not r["items"]],
                           "new_leads": sum(r["new"] for r in source_rows), "rows": source_rows}}
    return health, reseen[:40], new_count, summary


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
    stored = EV.load_all()
    # Derived, never written back to a record: confirmed openings, estimates and the programmes with no pattern yet.
    meta["upcoming"] = CY.watch_list(records, stored, archive["opportunities"], today)
    meta["evidence"] = {"files": len(stored), "ids": sorted(i for i, e in stored.items() if e.get("criteria") or e.get("funding") or e.get("cycles")),
                        "records_with_criteria": sum(1 for r in records if stored.get(r["id"], {}).get("criteria")),
                        "records_with_funding_detail": sum(1 for r in records if stored.get(r["id"], {}).get("funding")),
                        "live_records": len(records)}
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
    info = meta.get("leads")
    if info:
        rej = ", ".join(f"{k} {v}" for k, v in sorted(info["rejected_this_run"].items())) or "none"
        lines += ["", "## Leads", "",
                  f"- Active: {info['active']} | archived in total: {info['archived_total']} | "
                  f"retired this run: {info['retired_this_run']}",
                  f"- Titles rejected this run: {rej}. Reasons are logged in `data/lead-audit.json`."]
    src = (info or {}).get("sources")
    if src and src["scanned"]:
        lines += ["", "## Registry sources scanned this run", "",
                  f"- {src['scanned']} of {src['registered']} registered sources were due; "
                  f"{src['new_leads']} new leads; failed or empty: {', '.join(src['failed']) or 'none'}.", "",
                  "| Source | Mode | HTTP | Items | New leads | Trial yield | Note |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {r['name']} | {r['status']} | {r['http']} | {r['items']} | {r['new']} | "
                  f"{r['would_add'] if r['status'] == 'proposed' else ''} | {r['note']} |" for r in src["rows"]]
    lines += ["", "## Feed health", "", "| Feed | Tier | HTTP | Items | New leads | Alert |", "|---|---|---|---|---|---|"]
    lines += [f"| {f['name']} | {f['tier']} | {f['status']} | {f['items']} | {f['new']} | {f.get('alert') or ''} |"
              for f in meta.get("feeds", [])] or ["| (not run) | | | | | |"]
    upcoming = meta.get("upcoming", {})
    soon = [i for i in upcoming.get("items", []) if i.get("check_now")]
    lines += ["", "## Upcoming to watch", "",
              "Derived each day; estimates come from earlier cycles and are not announced dates.", "",
              f"- {len(upcoming.get('items', []))} programmes to watch, {len(upcoming.get('not_yet_announced', []))} "
              f"with no earlier cycle to compare, {upcoming.get('left_out_not_eligible', 0)} not eligible left out"]
    lines += [f"- check the official page now: {i['title']} ({i['phase'].lower()}: {i['window_text']})" for i in soon]
    ev = meta.get("evidence", {})
    lines += [f"- evidence files: {ev.get('files', 0)} ({ev.get('records_with_criteria', 0)} of {ev.get('live_records', 0)} "
              "live records have per-criterion eligibility)"]
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
            health, reseen, new_leads, leads_summary = harvest(db, archive, today)
            extra.update({"feeds": health, "reseen": reseen, "new_leads_last_run": new_leads,
                          "leads": leads_summary})
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
