"""Evidence files: per-criterion eligibility, funding detail and application cycles for one record.

    data/evidence/<record-id>.json

The record in data/opportunities.json stays the summary (one verdict, one coverage table). The evidence
file holds the detail behind it, each claim with the page and the sentence it came from:

    {
      "id": "...", "checked_on": "YYYY-MM-DD",
      "criteria": [{"criterion": "nationality", "requirement": "...", "applicant": "...",
                    "assessment": "MET|NOT MET|UNKNOWN|NOT STATED", "missing": "...",
                    "quote": "...", "page": "https://..."}],
      "funding":  [{"item": "airfare", "arrangement": "...", "amount": "...", "currency": "...",
                    "conditions": "...", "quote": "...", "page": "https://..."}],
      "out_of_pocket": "text, only from confirmed amounts",
      "cycles":   [{"cycle": "2026", "state": "HISTORICAL CYCLE", "opens_on": "", "deadline": "",
                    "basis": "...", "window_text": "...", "quote": "...", "page": "https://..."}]
    }

A scout delivers it as the key `evidence` inside a batch record. `scripts/upsert.py` moves it into the file;
the record itself never carries it. Nothing here is read from a page by code: the judge checks that every
quote is on the cited page before the record is accepted (scripts/judge.py).

Rules enforced by `check`:
  * a verdict of MET or NOT MET names the applicant fact it used; UNKNOWN names what is missing;
  * a verdict is never more favourable than its criteria (one NOT MET means NOT ELIGIBLE; LIKELY needs the
    nationality rule read and not NOT MET);
  * the funding table never claims more than the quote supports and never contradicts the record's coverage;
  * an amount always has a currency.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import oplib as L

EVIDENCE_DIR = L.ROOT / "data" / "evidence"

ASSESSMENTS = ["MET", "NOT MET", "UNKNOWN", "NOT STATED"]
CRITERIA = ["nationality", "residence", "age", "education", "discipline", "graduation", "enrolment", "experience",
            "language", "language_certificate", "passport", "employment", "business", "other"]
FUNDING_ITEMS = {"tuition": "tuition", "airfare": "flight", "accommodation": "accommodation", "meals": "meals",
                 "daily_allowance": "stipend", "visa_fees": "visa", "insurance": "insurance",
                 "local_transport": "local_transport", "airport_transfers": None, "participation_fee": None,
                 "training": None, "study_materials": None, "other_support": None}
ARRANGEMENTS = ["Paid directly by organiser", "Reimbursed after purchase", "Covered through an allowance",
                "Partially covered", "Not covered", "Unknown"]
CYCLE_STATES = ["CONFIRMED CURRENT CYCLE", "EXPECTED NEXT CYCLE", "HISTORICAL CYCLE", "NOT YET ANNOUNCED"]
CYCLE_BASES = ["organiser states", "pattern"]

ELIG_RANK = {"NOT ELIGIBLE": 0, "INSUFFICIENT INFORMATION": 1, "POSSIBLY ELIGIBLE": 2, "LIKELY ELIGIBLE": 3}
_COVERAGE_OF_ARRANGEMENT = {"Paid directly by organiser": "Covered", "Reimbursed after purchase": "Covered",
                            "Covered through an allowance": "Covered", "Partially covered": "Partially covered",
                            "Not covered": "Not covered", "Unknown": "Not specified"}
_COVERAGE_RANK = {"Covered": 3, "Partially covered": 2, "Not specified": 1, "Not covered": 0}
NATIONALITY_NAMES_DRC = re.compile(r"congo|\bdrc\b|\brdc\b|all nationalit|any nationalit|every nationalit|"
                                   r"toutes? nationalit|worldwide|all countries|any country|tous pays", re.I)
URL = re.compile(r"^https?://[^\s]+$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_QUOTE = 12


def path_of(rec_id: str) -> Path:
    return EVIDENCE_DIR / f"{rec_id}.json"


def load(rec_id: str) -> dict:
    return L.load(path_of(rec_id), {})


def load_all() -> dict[str, dict]:
    out = {}
    if EVIDENCE_DIR.is_dir():
        for p in sorted(EVIDENCE_DIR.glob("*.json")):
            out[p.stem] = L.load(p, {})
    return out


def finding(severity: str, rule: str, message: str) -> dict:
    return {"severity": severity, "rule": rule, "message": message}


def _quote_length(text: str) -> int:
    return len(re.sub(r"\s+", " ", text or "").strip())


# ---------------------------------------------------------------- eligibility
def derive_eligibility(criteria: list[dict]) -> str | None:
    """The most favourable verdict the criteria allow. The record may be lower, never higher."""
    marks = [c.get("assessment") for c in criteria or []]
    if not marks:
        return None
    if "NOT MET" in marks:
        return "NOT ELIGIBLE"
    met = marks.count("MET")
    if "UNKNOWN" in marks:
        return "POSSIBLY ELIGIBLE" if met else "INSUFFICIENT INFORMATION"
    nationality_read = any(c.get("criterion") == "nationality" and c.get("assessment") in ("MET", "NOT STATED")
                           for c in criteria)
    if met and nationality_read:
        return "LIKELY ELIGIBLE"
    return "POSSIBLY ELIGIBLE" if met else "INSUFFICIENT INFORMATION"


def counts(criteria: list[dict]) -> dict:
    marks = [c.get("assessment") for c in criteria or []]
    return {k: marks.count(k) for k in ASSESSMENTS} | {"total": len(marks)}


# ---------------------------------------------------------------- checks
def _check_criteria(criteria, out):
    for i, c in enumerate(criteria):
        tag = f"criteria[{i}] ({c.get('criterion', '?')})"
        if c.get("criterion") not in CRITERIA:
            out.append(finding("block", "evidence-criterion", f"{tag}: criterion must be one of {CRITERIA}"))
        if c.get("assessment") not in ASSESSMENTS:
            out.append(finding("block", "evidence-assessment", f"{tag}: assessment must be one of {ASSESSMENTS}"))
            continue
        if not (c.get("requirement") or "").strip():
            out.append(finding("block", "evidence-requirement", f"{tag}: the organiser's requirement is empty"))
        assessment = c["assessment"]
        if assessment in ("MET", "NOT MET") and not (c.get("applicant") or "").strip():
            out.append(finding("block", "evidence-applicant", f"{tag}: {assessment} must name the applicant fact it used"))
        if assessment == "UNKNOWN" and not (c.get("missing") or "").strip():
            out.append(finding("block", "evidence-missing", f"{tag}: UNKNOWN must name the missing fact"))
        if assessment != "NOT STATED":
            if _quote_length(c.get("quote", "")) < MIN_QUOTE:
                out.append(finding("block", "evidence-quote", f"{tag}: the organiser's sentence is missing or too short"))
            if not URL.match(c.get("page", "") or ""):
                out.append(finding("block", "evidence-page", f"{tag}: page must be the URL the sentence was read on"))
        if (c.get("criterion") == "nationality" and assessment == "MET"
                and not NATIONALITY_NAMES_DRC.search((c.get("quote", "") or "") + " " + (c.get("requirement", "") or ""))):
            out.append(finding("review", "evidence-nationality-not-drc",
                               f"{tag}: MET, but neither the requirement nor the quote names the DRC or says all nationalities "
                               "(an Africa-wide rule does not by itself include the DRC: read the country list)"))


def _check_funding(funding, rec, out):
    coverage = (rec or {}).get("coverage") or {}
    seen = set()
    for i, f in enumerate(funding):
        tag = f"funding[{i}] ({f.get('item', '?')})"
        item = f.get("item")
        if item not in FUNDING_ITEMS:
            out.append(finding("block", "evidence-funding-item", f"{tag}: item must be one of {list(FUNDING_ITEMS)}"))
            continue
        if item in seen:
            out.append(finding("block", "evidence-funding-duplicate", f"{tag}: listed twice"))
        seen.add(item)
        arrangement = f.get("arrangement")
        if arrangement not in ARRANGEMENTS:
            out.append(finding("block", "evidence-arrangement", f"{tag}: arrangement must be one of {ARRANGEMENTS}"))
            continue
        if arrangement != "Unknown":
            if _quote_length(f.get("quote", "")) < MIN_QUOTE:
                out.append(finding("block", "evidence-quote", f"{tag}: the organiser's sentence is missing or too short"))
            if not URL.match(f.get("page", "") or ""):
                out.append(finding("block", "evidence-page", f"{tag}: page must be the URL the sentence was read on"))
        if (f.get("amount") or "").strip() and not (f.get("currency") or "").strip():
            out.append(finding("block", "evidence-currency", f"{tag}: an amount needs its currency"))
        if (f.get("amount") or "").strip() and arrangement in ("Unknown", "Not covered"):
            out.append(finding("block", "evidence-amount-unsupported", f"{tag}: an amount contradicts the arrangement {arrangement!r}"))
        key = FUNDING_ITEMS[item]
        if key and key in coverage and coverage[key] not in ("Not applicable", None):
            stated = _COVERAGE_RANK.get(coverage[key], 1)
            proven = _COVERAGE_RANK[_COVERAGE_OF_ARRANGEMENT[arrangement]]
            if stated > proven:
                out.append(finding("block", "evidence-coverage-conflict",
                                   f"{tag}: the record's coverage.{key} says {coverage[key]!r} but the evidence supports only "
                                   f"{_COVERAGE_OF_ARRANGEMENT[arrangement]!r}"))
    if rec and rec.get("funding_type") == "Fully Funded" and funding:
        proven = {f["item"] for f in funding if f.get("arrangement") in
                  ("Paid directly by organiser", "Reimbursed after purchase", "Covered through an allowance")}
        if not proven:
            out.append(finding("review", "evidence-fully-funded-unproven",
                               "Fully Funded, but no funding line in the evidence is backed by a quote as paid"))


def _check_cycles(cycles, out):
    labels = set()
    for i, c in enumerate(cycles):
        tag = f"cycles[{i}] ({c.get('cycle', '?')})"
        if not (c.get("cycle") or "").strip():
            out.append(finding("block", "evidence-cycle-label", f"{tag}: cycle needs a label (a year or an edition)"))
        if c.get("cycle") in labels:
            out.append(finding("block", "evidence-cycle-duplicate", f"{tag}: listed twice"))
        labels.add(c.get("cycle"))
        state = c.get("state")
        if state not in CYCLE_STATES:
            out.append(finding("block", "evidence-cycle-state", f"{tag}: state must be one of {CYCLE_STATES}"))
            continue
        for field in ("opens_on", "deadline"):
            if c.get(field) and not ISO.match(c[field]):
                out.append(finding("block", "evidence-cycle-date", f"{tag}: {field} must be YYYY-MM-DD or empty"))
        if state in ("HISTORICAL CYCLE", "CONFIRMED CURRENT CYCLE"):
            if not URL.match(c.get("page", "") or "") or _quote_length(c.get("quote", "")) < MIN_QUOTE:
                out.append(finding("block", "evidence-cycle-unproven", f"{tag}: a {state.lower()} needs the page and the sentence that states it"))
        if state == "EXPECTED NEXT CYCLE":
            if c.get("basis") not in CYCLE_BASES:
                out.append(finding("block", "evidence-cycle-basis", f"{tag}: an expected cycle says basis: {CYCLE_BASES}"))
            if c.get("basis") == "organiser states" and (not URL.match(c.get("page", "") or "")
                                                          or _quote_length(c.get("quote", "")) < MIN_QUOTE):
                out.append(finding("block", "evidence-cycle-unproven", f"{tag}: 'organiser states' needs the page and the sentence"))
            if c.get("deadline"):
                out.append(finding("block", "evidence-cycle-predicted-date",
                                   f"{tag}: an expected cycle has no deadline; describe the period in window_text"))
        if state == "HISTORICAL CYCLE" and c.get("deadline") and L.parse_date(c["deadline"]) and \
                L.parse_date(c["deadline"]) > L.today_utc():
            out.append(finding("block", "evidence-cycle-historical-future", f"{tag}: a historical cycle cannot end in the future"))


def check(ev: dict, rec: dict | None = None) -> list[dict]:
    """Findings for one evidence block. `rec` is the record as it will be stored (for consistency checks)."""
    out: list[dict] = []
    if not isinstance(ev, dict):
        return [finding("block", "evidence-shape", "evidence must be an object")]
    for key, kind in (("criteria", list), ("funding", list), ("cycles", list)):
        if key in ev and not isinstance(ev[key], kind):
            out.append(finding("block", "evidence-shape", f"{key} must be a {kind.__name__}"))
    if out:
        return out
    criteria, funding, cycles = ev.get("criteria") or [], ev.get("funding") or [], ev.get("cycles") or []
    if not (criteria or funding or cycles):
        out.append(finding("block", "evidence-empty", "evidence has no criteria, funding or cycles"))
    _check_criteria(criteria, out)
    _check_funding(funding, rec, out)
    _check_cycles(cycles, out)
    if "out_of_pocket" in ev and not str(ev["out_of_pocket"] or "").strip():
        out.append(finding("block", "evidence-out-of-pocket", "out_of_pocket is present but empty (write Unknown if nothing is confirmed)"))
    if rec and criteria:
        derived = derive_eligibility(criteria)
        claimed = rec.get("eligibility_for_me")
        if derived and claimed in ELIG_RANK and ELIG_RANK[claimed] > ELIG_RANK[derived]:
            out.append(finding("block", "evidence-verdict-too-high",
                               f"the record says {claimed} but its own criteria allow at most {derived}"))
    return out


def stored_conflicts(rec: dict) -> list[dict]:
    """Findings that compare a record with the evidence file already stored for it."""
    ev = load(rec.get("id", ""))
    if not ev:
        return []
    out = []
    if ev.get("criteria"):
        derived = derive_eligibility(ev["criteria"])
        claimed = rec.get("eligibility_for_me")
        if derived and claimed in ELIG_RANK and ELIG_RANK[claimed] > ELIG_RANK[derived]:
            out.append(finding("block", "evidence-verdict-too-high",
                               f"the record says {claimed} but its stored criteria allow at most {derived}"))
    if ev.get("funding"):
        out += [f for f in _funding_findings(ev["funding"], rec) if f["rule"] == "evidence-coverage-conflict"]
    return out


def _funding_findings(funding, rec):
    out: list[dict] = []
    _check_funding(funding, rec, out)
    return out


# ---------------------------------------------------------------- quotes
def quote_items(ev: dict) -> list[tuple[str, str, str]]:
    """(where, page, quote) for every sentence the evidence relies on."""
    items = []
    for kind in ("criteria", "funding", "cycles"):
        for i, entry in enumerate(ev.get(kind) or []):
            if entry.get("quote") and entry.get("page"):
                items.append((f"{kind}[{i}]", entry["page"], entry["quote"]))
    return items


# ---------------------------------------------------------------- storing
def merge_cycles(old: list[dict], new: list[dict]) -> list[dict]:
    """History is kept: a cycle already stored is replaced only by a new entry with the same label."""
    merged = {c.get("cycle"): c for c in old or []}
    for c in new or []:
        merged[c.get("cycle")] = c
    return sorted(merged.values(), key=lambda c: (c.get("deadline") or c.get("opens_on") or "", c.get("cycle") or ""))


def store(rec_id: str, ev: dict, today: dt.date, changes: list[dict], title: str = "") -> dict:
    """Write data/evidence/<id>.json. A key left out of `ev` keeps its stored value; cycles accumulate."""
    old = load(rec_id)
    new = {"id": rec_id, "checked_on": today.isoformat()}
    for key in ("criteria", "funding", "out_of_pocket"):
        if key in ev:
            new[key] = ev[key]
        elif key in old:
            new[key] = old[key]
    cycles = merge_cycles(old.get("cycles"), ev.get("cycles")) if (ev.get("cycles") or old.get("cycles")) else []
    if cycles:
        new["cycles"] = cycles
    stamp = today.isoformat()

    def log(field, before, after):
        changes.append({"date": stamp, "id": rec_id, "title": title, "field": field, "old": before, "new": after})

    old_marks = {(c.get("criterion"), c.get("requirement")): c.get("assessment") for c in old.get("criteria") or []}
    for c in new.get("criteria") or []:
        key = (c.get("criterion"), c.get("requirement"))
        if old_marks.get(key) != c.get("assessment"):
            log(f"evidence:{c.get('criterion')}", old_marks.get(key), c.get("assessment"))
    old_pay = {f.get("item"): f.get("arrangement") for f in old.get("funding") or []}
    for f in new.get("funding") or []:
        if old_pay.get(f.get("item")) != f.get("arrangement"):
            log(f"evidence:funding:{f.get('item')}", old_pay.get(f.get("item")), f.get("arrangement"))
    old_cycles = {c.get("cycle"): c.get("state") for c in old.get("cycles") or []}
    for c in new.get("cycles") or []:
        if old_cycles.get(c.get("cycle")) != c.get("state"):
            log(f"evidence:cycle:{c.get('cycle')}", old_cycles.get(c.get("cycle")), c.get("state"))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    L.save(path_of(rec_id), new)
    return new
