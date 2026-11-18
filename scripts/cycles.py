"""Application cycles: which cycle of a recurring programme a record is in, and what to watch next.

A record in data/opportunities.json describes a programme and its current cycle. Closed cycles are kept in
archive/archive.json (one snapshot per cycle) and, when a scout supplies them, in data/evidence/<id>.json.
This module reads both and never writes a record:

  CONFIRMED CURRENT CYCLE  a page states a deadline in the future, or the programme is open or rolling
  EXPECTED NEXT CYCLE      no confirmed date. Either the organiser states a period (evidence cycle with
                           basis "organiser states") or the earlier cycles suggest a month (basis "pattern")
  HISTORICAL CYCLE         a closed cycle (archive snapshots, evidence cycles)
  NOT YET ANNOUNCED        recurring, no confirmed date and no earlier cycle on record to compare with

A pattern is an estimate for planning. It is stored only in data/meta.json under `upcoming`, never in
`application_deadline`, and the site labels it as an estimate every time it appears.

    python scripts/cycles.py          # prints the current watch list
"""
from __future__ import annotations

import calendar
import datetime as dt
import sys

import evidence as EV
import oplib as L

HORIZON_DAYS = 365           # an expected deadline further away than this is not worth a place on the list
CHECK_NOW_DAYS = 90          # inside this distance the call may already be open: read the official page
STATE_CURRENT, STATE_EXPECTED, STATE_HISTORICAL, STATE_NONE = EV.CYCLE_STATES


def month_label(day: dt.date) -> str:
    return f"{calendar.month_name[day.month]} {day.year}"


def add_years(day: dt.date, years: int) -> dt.date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:                      # 29 February
        return day.replace(year=day.year + years, day=28)


def closed_deadlines(rec: dict, ev: dict, archive_records: list[dict], today: dt.date) -> list[dt.date]:
    """Deadlines of this programme's earlier cycles, oldest first. Only dates a page stated."""
    found = set()
    value = L.parse_date(rec.get("last_cycle_deadline"))
    if value and value < today:
        found.add(value)
    for old in archive_records:
        if old.get("id") == rec.get("id"):
            day = L.parse_date(old.get("application_deadline"))
            if day and day < today:
                found.add(day)
    for cycle in ev.get("cycles") or []:
        if cycle.get("state") == STATE_HISTORICAL:
            day = L.parse_date(cycle.get("deadline"))
            if day and day < today:
                found.add(day)
    return sorted(found)


def month_spread(dates: list[dt.date]) -> int:
    """Largest gap in months between the deadlines' months of the year, going the short way round."""
    if len(dates) < 2:
        return 0
    months = [d.month for d in dates]
    return max(min(abs(a - b), 12 - abs(a - b)) for a in months for b in months)


def next_occurrence(last: dt.date, today: dt.date) -> dt.date:
    years = 1
    while add_years(last, years) <= today:
        years += 1
    return add_years(last, years)


def classify(rec: dict, ev: dict, archive_records: list[dict], today: dt.date) -> dict:
    """The cycle state of one live record, with the facts behind it."""
    status = L.compute_status(rec, today)
    history = closed_deadlines(rec, ev, archive_records, today)
    base = {"id": rec["id"], "history": [d.isoformat() for d in history]}
    opens = L.parse_date(rec.get("opens_on"))
    deadline = L.parse_date(rec.get("application_deadline"))
    if status in ("OPEN", "CLOSING SOON", "ROLLING") or (deadline and deadline >= today):
        phase = "announced opening" if opens and opens > today else "open now"
        return {**base, "state": STATE_CURRENT, "phase": phase, "basis": "page states it"}
    if opens and opens > today:
        return {**base, "state": STATE_CURRENT, "phase": "announced opening", "basis": "page states it"}
    stated = [c for c in ev.get("cycles") or []
              if c.get("state") == STATE_EXPECTED and c.get("basis") == "organiser states"]
    if stated:
        return {**base, "state": STATE_EXPECTED, "basis": "organiser states", "window_text": stated[-1].get("window_text", "")}
    if rec.get("recurring") and history:
        expected = next_occurrence(history[-1], today)
        spread = month_spread(history)
        confidence = ("one earlier cycle" if len(history) == 1 else
                      f"{len(history)} earlier cycles, same time of year" if spread <= 1 else
                      f"{len(history)} earlier cycles, months vary by {spread}")
        return {**base, "state": STATE_EXPECTED, "basis": "pattern", "expected_deadline_month": expected.strftime("%Y-%m"),
                "window_text": f"around {month_label(expected)} (closing)", "pattern": confidence,
                "days_until": (expected - today).days}
    return {**base, "state": STATE_NONE, "basis": "no earlier cycle to compare"}


def watch_list(records: list[dict], evidence: dict[str, dict], archive_records: list[dict], today: dt.date) -> dict:
    items, none_yet, left_out = [], [], 0
    for rec in records:
        if rec.get("eligibility_for_me") == "NOT ELIGIBLE":
            left_out += 1
            continue
        info = classify(rec, evidence.get(rec["id"], {}), archive_records, today)
        entry = {"id": rec["id"], "title": rec["title"], "organization": rec.get("organization", ""),
                 "state": info["state"], "basis": info["basis"], "history": info["history"],
                 "eligibility_for_me": rec.get("eligibility_for_me", ""), "funding_type": rec.get("funding_type", ""),
                 "organiser_text": (rec.get("expected_next_cycle") or "")[:400],
                 "url": rec.get("official_information_url") or rec.get("source_url", "")}
        if info["state"] == STATE_CURRENT:
            opens = L.parse_date(rec.get("opens_on"))
            if info.get("phase") == "announced opening" and opens:
                days = (opens - today).days
                items.append({**entry, "phase": "Opening announced", "window_text": f"opens {opens.isoformat()}",
                              "days_until": days, "check_now": days <= 14})
            continue
        if info["state"] == STATE_NONE:
            none_yet.append({"id": rec["id"], "title": rec["title"], "organiser_text": entry["organiser_text"]})
            continue
        days = info.get("days_until")
        if info["basis"] == "pattern":
            if days is None or days > HORIZON_DAYS:
                continue
            items.append({**entry, "phase": "Expected again (estimate)", "window_text": info["window_text"],
                          "expected_deadline_month": info["expected_deadline_month"], "pattern": info["pattern"],
                          "days_until": days, "check_now": days <= CHECK_NOW_DAYS})
        else:
            items.append({**entry, "phase": "Expected again (organiser states a period)",
                          "window_text": info.get("window_text", ""), "days_until": None, "check_now": False})
    items.sort(key=lambda x: (x["days_until"] is None, x["days_until"] if x["days_until"] is not None else 0, x["title"]))
    return {"generated": today.isoformat(), "items": items, "not_yet_announced": none_yet,
            "left_out_not_eligible": left_out}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    today = L.today_utc()
    result = watch_list(L.load_db()["opportunities"], EV.load_all(), L.load_archive()["opportunities"], today)
    for item in result["items"]:
        when = f"{item['days_until']:>4} d" if item["days_until"] is not None else "   - "
        print(f"{when}  {item['phase']:<44} {item['id'][:44]:<44} {item['window_text']}"
              + ("  <- check now" if item["check_now"] else ""))
    print(f"{len(result['items'])} to watch, {len(result['not_yet_announced'])} not yet announced, "
          f"{result['left_out_not_eligible']} not eligible left out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
