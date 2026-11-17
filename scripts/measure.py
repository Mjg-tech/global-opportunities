"""Baseline measurement of the discovery filters. Read-only: writes nothing unless --out is given.

    python scripts/measure.py                       # prints the summary
    python scripts/measure.py --out reports/baseline-YYYY-MM-DD.json
    python scripts/measure.py --no-network          # skip the live feed funnel

It reuses the real filters from refresh.py (it does not copy them), so the numbers describe what
the daily run actually does. Three measurements:

  A. False exclusions on KNOWN opportunities: every live and archived record title is run through
     the lead filters. These are real programmes already in the database, so any title the filters
     would reject is a proven false negative.
  B. Live funnel: every item in every enabled feed is followed through the filters (too old, not an
     opportunity, no opportunity word) and then the known-record, already-a-lead and duplicate checks.
     Audience words no longer reject a title (see scripts/leadfilter.py).
  C. Lead retention: how long leads really survive against the nominal 45 days.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import sys
from pathlib import Path

import leadfilter as LF
import oplib as L
import refresh as R


def gate(title: str, today: dt.date, published: str = "", strict: bool = False) -> tuple[str, str]:
    """Return (stage, detail). stage is 'pass' or the reason the filters reject the title.

    Since step 1 the stages are too_old, not_opportunity and no_opportunity_word. Audience words no
    longer reject: they lower the score, and `detail` then carries the flags of a passing title.
    """
    result = LF.assess(title, published, 3, "strict" if strict else "", today)
    if result.kind == "lead":
        return "pass", ";".join(result.flags)
    return result.reason, result.detail


def known_titles() -> list[tuple[str, str]]:
    db, archive = L.load_db(), L.load_archive()
    seen, out = set(), []
    for rec in db["opportunities"] + archive["opportunities"]:
        if rec["id"] in seen:
            continue
        seen.add(rec["id"])
        out.append((rec["id"], rec["title"]))
    return out


def measure_known(today: dt.date) -> dict:
    rows = known_titles()
    rejected = []
    for rid, title in rows:
        stage, detail = gate(title, today)
        if stage != "pass":
            rejected.append({"id": rid, "title": title, "stage": stage, "detail": detail})
    return {"known_titles": len(rows), "rejected": len(rejected),
            "by_stage": dict(collections.Counter(r["stage"] for r in rejected)), "items": rejected}


def measure_funnel(db: dict, archive: dict, today: dt.date) -> dict:
    sources = L.load(L.SOURCES, {"feeds": []})
    feeds = [f for f in sources.get("feeds", []) if f.get("enabled", True)]
    records = db["opportunities"] + archive["opportunities"]
    result, samples = [], collections.defaultdict(list)
    accepted: list[str] = []
    stored = {lead["id"] for lead in L.load(L.LEADS, {"leads": []})["leads"]}
    for feed in feeds:
        status, _final, body = L.fetch(
            feed["url"], timeout=25, accept="application/rss+xml,application/atom+xml,application/xml,*/*")
        items = R.parse_feed(body) if status == 200 else []
        stages = collections.Counter()
        for item in items:
            title, url = item["title"], item["url"]
            if not title or not url.startswith("http"):
                stages["unusable"] += 1
                continue
            stage, detail = gate(title, today, item["published"], strict=feed.get("filter") == "strict")
            if stage == "pass":
                lead_id = hashlib.sha1(L.norm_url(url).encode("utf-8")).hexdigest()[:12]
                if R.known_record(title, records):
                    stage = "known_record"
                elif lead_id in stored:
                    stage = "already_lead"
                elif any(R.same_lead(title, t) for t in accepted):
                    stage = "duplicate"
                else:
                    accepted.append(title)
            stages[stage] += 1
            if stage == "pass" and detail and len(samples["demoted"]) < 400:
                samples["demoted"].append({"feed": feed["name"], "title": title, "detail": detail})
            if stage in ("no_opportunity_word", "not_opportunity") and len(samples[stage]) < 400:
                samples[stage].append({"feed": feed["name"], "title": title, "detail": detail})
        result.append({"feed": feed["name"], "tier": feed.get("tier", 3), "http": status,
                       "items": len(items), "stages": dict(stages)})
    totals = collections.Counter()
    for row in result:
        totals.update(row["stages"])
    return {"feeds": result, "totals": dict(totals), "new_candidates_this_run": len(accepted),
            "rejected_samples": {k: v for k, v in samples.items()}}


def measure_retention(today: dt.date) -> dict:
    leads = L.load(L.LEADS, {"leads": []})["leads"]
    ages = [(today - (L.parse_date(x.get("first_seen")) or today)).days for x in leads]
    by_source = collections.Counter(x.get("source") for x in leads)
    by_tier = collections.Counter(x.get("source_tier") for x in leads)
    ret = LF.load_rules()["retention"]
    return {"leads": len(leads), "cap": ret["max_active_leads"], "nominal_ttl_days": ret["ttl_days"],
            "oldest_days": max(ages, default=0), "newest_days": min(ages, default=0),
            "median_days": sorted(ages)[len(ages) // 2] if ages else 0,
            "by_source": dict(by_source.most_common()), "by_tier": {str(k): v for k, v in by_tier.items()}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--out", help="write the full result as JSON")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    today = L.parse_date(args.today) or L.today_utc()
    db, archive = L.load_db(), L.load_archive()

    report = {"measured_on": today.isoformat(), "known": measure_known(today),
              "retention": measure_retention(today)}
    if not args.no_network:
        report["funnel"] = measure_funnel(db, archive, today)

    known = report["known"]
    print(f"A. Known titles rejected by the lead filters: {known['rejected']} of {known['known_titles']} "
          f"{known['by_stage']}")
    for row in known["items"]:
        print(f"   [{row['stage']}:{row['detail']}] {row['title']}")
    ret = report["retention"]
    print(f"C. Leads kept: {ret['leads']} (cap {ret['cap']}); oldest {ret['oldest_days']} d, "
          f"median {ret['median_days']} d, newest {ret['newest_days']} d (nominal TTL {ret['nominal_ttl_days']} d)")
    print(f"   by tier: {ret['by_tier']}")
    if "funnel" in report:
        fun = report["funnel"]
        print(f"B. Live funnel, totals: {fun['totals']}; new candidates this run: {fun['new_candidates_this_run']}")
        for row in fun["feeds"]:
            print(f"   {row['feed'][:34]:34} http {row['http']:>3} items {row['items']:>3} {row['stages']}")
    if args.out:
        L.save(Path(args.out), report)
        print("written:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
