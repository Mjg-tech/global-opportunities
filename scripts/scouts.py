"""Weekly research plan: one work packet per channel scout, plus the orchestrator's own list.

    python scripts/scouts.py plan [--today YYYY-MM-DD] [--leads-per-scout N] [--out FILE]

Read-only except for the plan file. It splits the week's work so five scouts (or one agent doing five
passes) do not overlap: each channel gets its registry sources, the best open leads that belong to it,
a slice of the research watchlist and a rotating set of search phrases. The channel of an aggregator
lead is a keyword guess used only to divide the work; a scout may pick up any lead.

The orchestrator list is what AGENTS.md steps 2-3 need: records to re-verify and programmes seen again.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import evidence as EV
import leadfilter as LF
import oplib as L
import sourcelib as S

QUERIES = L.ROOT / "data" / "scout-queries.json"

CHANNEL_INFO = {
    "A": ("Institutional",
          "UN agencies, the AU and regional bodies, the EU, development banks, foundations. Calls for "
          "applications, fellowships, youth programmes, young-professional schemes."),
    "B": ("Government and diplomatic",
          "Government scholarships, embassy programmes, ministry exchanges, bilateral cooperation "
          "(including programmes run through embassies in Kinshasa)."),
    "C": ("Academic",
          "Universities and scholarship bodies: master's, doctoral and research scholarships, Erasmus "
          "Mundus, summer schools, research fellowships."),
    "D": ("Professional and entrepreneurship",
          "Entrepreneurship programmes, accelerators, business competitions, professional and "
          "leadership fellowships, innovation prizes."),
    "E": ("Travel and events",
          "Funded summits, forums, delegations, study tours, youth assemblies, volunteering abroad, "
          "travel grants. Check who pays for travel and accommodation."),
}

# Keyword guess used only to divide aggregator leads and watchlist items between scouts. Checked in order.
_GUESS = [
    ("E", re.compile(r"summit|forum|conference|congress|delegat|study tour|assembly|parliament|festival|expo\b|"
                     r"volunteer|volontariat|hackathon|workshop|\bcamp\b|exchange visit|sommet|conf[ée]rence|"
                     r"colloque|cumbre|c[úu]pula", re.I)),
    ("D", re.compile(r"entrepreneur|start-?up|incubat|accelerat|innovation|pitch|seed|business|prize|\bprix\b|"
                     r"challenge|competition|concours|award|young professional|emprend", re.I)),
    ("B", re.compile(r"embass|ambassad|government|gouvernement|ministr|foreign affairs|state department|diplomat|"
                     r"bilateral|chevening|fulbright|daad|campus ?france|stipendium|\bcsc\b|mext|\bknb\b|\bitec\b|"
                     r"\biccr\b|gobierno|governo", re.I)),
    ("C", re.compile(r"scholar|bourse|master|\bmsc\b|\bphd\b|doctor|universit|studentship|erasmus|degree|"
                     r"undergraduate|postgraduate|summer school|research fellow|beca|bolsa|[ée]cole d", re.I)),
]
OPEN_STATUSES = {"NEW", "UNDER REVIEW", "OFFICIAL SOURCE FOUND", "VERIFICATION REQUIRED"}
QUERIES_PER_LANGUAGE = {"en": 4, "fr": 2, "pt": 1, "es": 1}
EVIDENCE_PER_SCOUT = 3           # records per channel per week that get their per-criterion evidence written


def guess_channel(text: str) -> str:
    for channel, pattern in _GUESS:
        if pattern.search(text or ""):
            return channel
    return "A"


def lead_channel(lead: dict, source_channels: dict[str, str]) -> str:
    """A lead from a registry source belongs to that source's channel; any other is a keyword guess."""
    return source_channels.get(lead.get("source", "")) or guess_channel(lead.get("title", ""))


def intake_year(today: dt.date) -> int:
    return today.year + 1 if today.month >= 7 else today.year


def pick_queries(bank: dict, channel: str, today: dt.date) -> list[dict]:
    """A few phrases per language, rotated by ISO week so consecutive weeks differ."""
    week = today.isocalendar()[1]
    chosen = []
    for lang, want in QUERIES_PER_LANGUAGE.items():
        pool = (bank.get("channels", {}).get(channel, {}) or {}).get(lang, [])
        if not pool:
            continue
        start = (week * want) % len(pool)
        for i in range(min(want, len(pool))):
            phrase = pool[(start + i) % len(pool)]
            chosen.append({"lang": lang, "q": phrase.replace("{year}", str(intake_year(today)))
                                                   .replace("{year_now}", str(today.year))})
    return chosen


def evidence_backlog(records: list[dict], stored: dict, today: dt.date) -> list[dict]:
    """Live records with no per-criterion evidence yet, most useful first: open and soonest-closing, then
    upcoming, never the ones already ruled out."""
    todo = [r for r in records if not (stored.get(r["id"]) or {}).get("criteria")
            and r.get("eligibility_for_me") != "NOT ELIGIBLE"]
    order = {"CLOSING SOON": 0, "OPEN": 1, "ROLLING": 2, "UPCOMING": 3, "DATE UNKNOWN": 4, "DEADLINE PASSED": 5}
    todo.sort(key=lambda r: (order.get(L.compute_status(r, today), 9), r.get("application_deadline") or "9999", r["id"]))
    return [{"id": r["id"], "title": r.get("title", ""), "status": L.compute_status(r, today),
             "official_page": r.get("official_information_url") or r.get("source_url", ""),
             "has_funding_detail": bool((stored.get(r["id"]) or {}).get("funding"))} for r in todo]


def build_plan(today: dt.date, registry: dict, state: dict, leads: list[dict], watchlist: list[dict],
               records: list[dict], meta: dict, bank: dict, leads_per_scout: int = 12,
               stored_evidence: dict | None = None) -> dict:
    sources = registry.get("sources", [])
    source_channels = {S.spec_of(s)["name"]: s.get("channel", "") for s in sources}
    state = state.get("sources", {})
    channels: dict[str, dict] = {}
    for key, (name, focus) in CHANNEL_INFO.items():
        mine = [s for s in sources if s.get("channel") == key]
        channels[key] = {
            "name": name, "focus": focus,
            "sources": [{"id": s["source_id"], "organization": s["organization"],
                         "url": s["official_opportunities_url"], "status": s["status"],
                         "last_checked": state.get(s["source_id"], {}).get("last_checked", ""),
                         "fail_streak": state.get(s["source_id"], {}).get("fail_streak", 0),
                         "trial_would_be_leads": state.get(s["source_id"], {}).get("trial_would_be_leads"),
                         "note": s.get("verification_note", "")} for s in mine],
            "open_in_browser": [s["official_opportunities_url"] for s in mine if s["status"] == "manual"],
            "leads": [], "watchlist": [], "queries": pick_queries(bank, key, today), "evidence_backlog": []}

    rules = LF.load_rules()
    migrated = [LF.migrate_lead(dict(x), today, rules) for x in leads]    # copies: works before the daily job migrates
    candidates = [x for x in migrated if x.get("status") in OPEN_STATUSES]
    candidates.sort(key=lambda x: (x["status"] != "UNDER REVIEW", -x.get("score", 0), x.get("first_seen", ""), x["id"]))
    for lead in candidates:
        bucket = channels[lead_channel(lead, source_channels)]["leads"]
        if len(bucket) < leads_per_scout:
            bucket.append({"id": lead["id"], "title": lead["title"], "url": lead["url"], "score": lead.get("score", 0),
                           "status": lead["status"], "source": lead.get("source", ""), "flags": lead.get("flags", []),
                           "published": lead.get("published", "")})
    for item in watchlist:
        bucket = channels[guess_channel(f"{item.get('name', '')} {item.get('why', '')[:240]}")]["watchlist"]
        if len(bucket) < 6:
            bucket.append({"name": item.get("name", ""), "next_step": item.get("next_step", "")})

    by_id = {r["id"]: r for r in records}
    for item in evidence_backlog(records, stored_evidence or {}, today):
        rec = by_id[item["id"]]
        text = f"{rec.get('title', '')} {rec.get('organization', '')} {' '.join(rec.get('category') or [])}"
        bucket = channels[guess_channel(text)]["evidence_backlog"]
        if len(bucket) < EVIDENCE_PER_SCOUT:
            bucket.append(item)

    flagged = [f["id"] for f in meta.get("flags", [])]
    closing = [r["id"] for r in records if (L.days_remaining(r, today) is not None
                                            and 0 <= L.days_remaining(r, today) <= 30)]
    recurring = [r["id"] for r in records if r.get("recurring") and not r.get("application_deadline")]
    return {"date": today.isoformat(), "iso_week": today.isocalendar()[1], "intake_year": intake_year(today),
            "leads_per_scout": leads_per_scout, "channels": channels,
            "orchestrator": {"reverify_flagged": sorted(set(flagged)), "reverify_closing_30_days": sorted(closing),
                             "recurring_without_deadline": sorted(recurring),
                             "seen_again": [x["id"] for x in meta.get("reseen", [])]}}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--today")
    plan.add_argument("--leads-per-scout", type=int, default=12)
    plan.add_argument("--out", help="default: research/<today>/scouts/plan.json")
    args = parser.parse_args()
    today = L.parse_date(args.today) or L.today_utc()
    result = build_plan(
        today, S.load_registry(), S.load_state(), L.load(L.LEADS, {"leads": []})["leads"],
        L.load(L.SOURCES, {}).get("research_watchlist", []), L.load_db()["opportunities"], L.load(L.META, {}),
        L.load(QUERIES, {}), args.leads_per_scout, EV.load_all())
    out = Path(args.out) if args.out else L.ROOT / "research" / today.isoformat() / "scouts" / "plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"plan for {today} (ISO week {result['iso_week']}) written to {out}")
    for key, ch in result["channels"].items():
        print(f"  {key} {ch['name']:<34} sources {len(ch['sources']):>2} (browser {len(ch['open_in_browser'])}) "
              f"leads {len(ch['leads']):>2} watchlist {len(ch['watchlist'])} queries {len(ch['queries'])} "
              f"evidence {len(ch['evidence_backlog'])}")
    orch = result["orchestrator"]
    print(f"  orchestrator: reverify {len(orch['reverify_flagged'])} flagged + {len(orch['reverify_closing_30_days'])} "
          f"closing, {len(orch['seen_again'])} seen again, {len(orch['recurring_without_deadline'])} recurring without a date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
