"""Monthly audit of false exclusions: did the pipeline turn away real opportunities?

    python scripts/audit.py sample [--month YYYY-MM] [--size 40] [--today YYYY-MM-DD]
    python scripts/audit.py record --month YYYY-MM
    python scripts/audit.py sources

`sample` draws a reproducible sample from two places where an opportunity can be lost without anyone
deciding it: titles the lead filters rejected (data/lead-audit.json) and NEW leads that aged out or fell
under the cap without ever being reviewed (archive/leads-archive.json). The auditor opens each page and
writes reports/audit-YYYY-MM-verdicts.json:

    {"items": [{"id": "...", "verdict": "FALSE_EXCLUSION" | "CORRECT" | "UNCLEAR", "note": "...", "page": "https://..."}]}

`record` turns the verdicts into reports/audit-YYYY-MM.md: the false-exclusion rate per stratum, the
estimated number missed, and the titles to add to tests/benchmark.json. Fix the filter, then add the
titles: the benchmark is a ratchet. `sources` reports which registry sources earn their place.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import oplib as L
import sourcelib as S

WINDOW_DAYS = 35
AUDIT = L.ROOT / "data" / "lead-audit.json"
LEADS_ARCHIVE = L.ROOT / "archive" / "leads-archive.json"
REPORTS = L.ROOT / "reports"
VERDICTS = ("FALSE_EXCLUSION", "CORRECT", "UNCLEAR")
FALSE_RATE_ALERT = 0.10                        # above this the filters or the retention rules need a change
UNREVIEWED = ("not reviewed within", "below the cap")


def month_of(today: dt.date) -> str:
    return today.strftime("%Y-%m")


def population(audit: dict, archive: dict, today: dt.date) -> dict[str, list[dict]]:
    """Items that left the pipeline in the last WINDOW_DAYS days without a person deciding, by stratum."""
    strata: dict[str, list[dict]] = {}
    for entry in audit.get("entries", []):
        when = L.parse_date(entry.get("date"))
        if when and (today - when).days <= WINDOW_DAYS:
            strata.setdefault(f"rejected:{entry['reason']}", []).append(
                {"id": entry["id"], "title": entry["title"], "url": entry["url"], "source": entry.get("source", ""),
                 "why": entry.get("detail") or entry["reason"]})
    for lead in archive.get("leads", []):
        when = L.parse_date(lead.get("archived_on"))
        if (when and (today - when).days <= WINDOW_DAYS and lead.get("status_before_archive") == "NEW"
                and str(lead.get("archive_reason", "")).startswith(UNREVIEWED)):
            strata.setdefault("aged-out", []).append(
                {"id": lead["id"], "title": lead["title"], "url": lead["url"], "source": lead.get("source", ""),
                 "why": lead.get("archive_reason", ""), "score": lead.get("score")})
    return strata


def draw(strata: dict[str, list[dict]], month: str, size: int) -> list[dict]:
    """Equal share per stratum (rounded up), in a fixed pseudo-random order that depends only on the month and the id."""
    if not strata:
        return []
    share = max(1, -(-size // len(strata)))
    items = []
    for name in sorted(strata):
        ranked = sorted(strata[name], key=lambda x: hashlib.sha1(f"{month}:{x['id']}".encode()).hexdigest())
        items += [{**x, "stratum": name} for x in ranked[:share]]
    return items[:size] if len(items) > size else items


def summarize(sample: dict, verdicts: dict) -> dict:
    by_id = {v["id"]: v for v in verdicts.get("items", []) if v.get("verdict") in VERDICTS}
    rows = {}
    for item in sample["items"]:
        row = rows.setdefault(item["stratum"], {"sampled": 0, "judged": 0, "false": 0, "unclear": 0,
                                                "population": sample["population"].get(item["stratum"], 0)})
        row["sampled"] += 1
        v = by_id.get(item["id"])
        if v:
            row["judged"] += 1
            row["false"] += v["verdict"] == "FALSE_EXCLUSION"
            row["unclear"] += v["verdict"] == "UNCLEAR"
    for row in rows.values():
        decided = row["judged"] - row["unclear"]
        row["rate"] = round(row["false"] / decided, 3) if decided else None
        row["estimated_missed"] = round(row["rate"] * row["population"]) if row["rate"] is not None else None
    missed = [{"id": i["id"], "title": i["title"], "url": i["url"], "stratum": i["stratum"],
               "note": by_id[i["id"]].get("note", ""), "page": by_id[i["id"]].get("page", "")}
              for i in sample["items"] if i["id"] in by_id and by_id[i["id"]]["verdict"] == "FALSE_EXCLUSION"]
    unjudged = [i["id"] for i in sample["items"] if i["id"] not in by_id]
    return {"strata": rows, "false_exclusions": missed, "unjudged": unjudged,
            "alert": [k for k, r in rows.items() if r["rate"] is not None and r["rate"] > FALSE_RATE_ALERT]}


def source_review(registry: dict, state: dict) -> list[str]:
    """Plain-language findings about registry sources, from the daily state."""
    notes = []
    for src in registry.get("sources", []):
        st, sid = state.get("sources", {}).get(src["source_id"], {}), src["source_id"]
        if src["status"] == "active":
            if st.get("fail_streak", 0) >= 3:
                notes.append(f"{sid}: {st['fail_streak']} failed scans in a row (last HTTP {st.get('last_http')}); "
                             "fix the entry or set it to manual")
            elif st.get("total_runs", 0) >= 5 and st.get("leads_total", 0) == 0:
                notes.append(f"{sid}: {st['total_runs']} scans and no lead ever: disable it or change its filters")
        elif src["status"] == "proposed" and st.get("trial_scans", 0) >= 4:
            per = st.get("trial_would_be_leads", 0) / st["trial_scans"]
            notes.append(f"{sid}: {st['trial_scans']} trial scans, {per:.1f} would-be leads per scan: "
                         + ("ready to activate" if per >= 1 else "still too thin, consider disabling"))
        elif src["status"] == "manual" and not L.parse_date(src.get("verified_on")):
            notes.append(f"{sid}: manual source without a verification date")
    return notes


def write_report(month: str, sample: dict, result: dict, notes: list[str]) -> Path:
    lines = [f"# False-exclusion audit - {month}", "",
             "Generated by `scripts/audit.py record`. Verdicts come from `reports/audit-" + month + "-verdicts.json`.", "",
             "| Stratum | Population | Sampled | Judged | False exclusions | Rate | Estimated missed |", "|---|---|---|---|---|---|---|"]
    for name, r in sorted(result["strata"].items()):
        rate = "-" if r["rate"] is None else f"{r['rate']:.0%}"
        lines.append(f"| {name} | {r['population']} | {r['sampled']} | {r['judged']} | {r['false']} | {rate} | "
                     f"{'-' if r['estimated_missed'] is None else r['estimated_missed']} |")
    lines += ["", f"Alert threshold: {FALSE_RATE_ALERT:.0%}. Strata above it: {', '.join(result['alert']) or 'none'}.", ""]
    lines += ["## False exclusions (add to `tests/benchmark.json` after the filter is fixed)", ""]
    lines += [f"- {m['title']} ({m['stratum']}) {m['page'] or m['url']} {m['note']}" for m in result["false_exclusions"]] or ["- none"]
    lines += ["", "## Items without a verdict", "", ", ".join(result["unjudged"]) or "none", "", "## Sources", ""]
    lines += [f"- {n}" for n in notes] or ["- nothing to change"]
    path = REPORTS / f"audit-{month}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--month")
    s.add_argument("--size", type=int, default=40)
    s.add_argument("--today")
    r = sub.add_parser("record")
    r.add_argument("--month", required=True)
    sub.add_parser("sources")
    args = parser.parse_args()
    registry, state = S.load_registry(), S.load_state()

    if args.cmd == "sources":
        print("\n".join(source_review(registry, state)) or "nothing to change")
        return 0
    if args.cmd == "sample":
        today = L.parse_date(args.today) or L.today_utc()
        month = args.month or month_of(today)
        strata = population(L.load(AUDIT, {"entries": []}), L.load(LEADS_ARCHIVE, {"leads": []}), today)
        sample = {"month": month, "size": args.size, "window_days": WINDOW_DAYS,
                  "population": {k: len(v) for k, v in strata.items()}, "items": draw(strata, month, args.size)}
        path = REPORTS / f"audit-{month}-sample.json"
        path.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"audit sample {month}: {len(sample['items'])} items from {sum(sample['population'].values())} "
              f"candidates in {len(strata)} strata -> {path}")
        return 0
    sample = json.loads((REPORTS / f"audit-{args.month}-sample.json").read_text(encoding="utf-8"))
    verdict_path = REPORTS / f"audit-{args.month}-verdicts.json"
    verdicts = json.loads(verdict_path.read_text(encoding="utf-8")) if verdict_path.exists() else {"items": []}
    result = summarize(sample, verdicts)
    path = write_report(args.month, sample, result, source_review(registry, state))
    print(f"audit record {args.month}: {len(result['false_exclusions'])} false exclusions, "
          f"{len(result['unjudged'])} without a verdict, alert on {result['alert'] or 'none'} -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
