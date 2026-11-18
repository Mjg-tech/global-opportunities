"""The independent judge: mechanical checks and the gate between scouts and the database.

    python scripts/judge.py check   FILE...                      rules every batch record must pass
    python scripts/judge.py verify  VERDICTS                      are the judge's quotes on the cited pages?
    python scripts/judge.py apply   --batches FILE... --verdicts VERDICTS [--out-dir DIR] [--no-network]
    python scripts/judge.py apply-leads --batches FILE... --verdicts VERDICTS --accepted accepted.json

A scout writes records; it never writes the database. The judge reads each cited page again, writes a
verdict with a verbatim quote, and may only LOWER trust (a verification label, a confidence, a funding
claim, an eligibility verdict). Nothing reaches data/opportunities.json except `accepted.json`, the
records that passed three independent gates: the rules below, the judge's verdict, and a literal check
that every quote appears on the page it cites. Text on a page is data; this module never obeys it.

A record may carry an `evidence` block (scripts/evidence.py): per-criterion eligibility, funding detail and
cycles, each with its own quote. `check` applies the evidence rules; `apply` checks every one of those
quotes on its page too, and drops the whole block (not the record) when one cannot be proven.

Batch files: a JSON list of records, or an object with "records" (and optionally "lead_outcomes").
Verdict file: {"records": [{"id", "decision": ACCEPT|DOWNGRADE|RETURN|REJECT, "reason",
"evidence": [{"url", "quote", "via"?}], "changes"?: {...}}], "lead_outcomes": [{"lead_id",
"decision": CONFIRM|OVERTURN, "reason"}]}.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

import evidence as EV
import leadfilter as LF
import oplib as L
import validate as V

# Aggregators and social pages are never an official source. Hosts of the feeds in data/sources.json are added.
AGGREGATORS = {
    "opportunitydesk.org", "opportunitiescorners.com", "opportunitesdumonde.com", "afri-carrieres.com",
    "lesopportunites.com", "scholarshipsforafricans.com", "scholars4dev.com", "mladiinfo.eu", "oyaop.com",
    "opportunitiesforafricans.com", "opportunitiesforyouth.org", "globalsouthopportunities.com", "mastere.tn",
    "partiuintercambio.org", "becasparatodos.com", "masoportunidades.com", "youthop.com", "yop.l-frii.com",
    "opportunity-desk.org", "scholarship-positions.com", "afterschoolafrica.com", "wemakescholars.com",
}
SOCIAL = {"facebook.com", "m.facebook.com", "t.me", "wa.me", "chat.whatsapp.com", "instagram.com", "x.com",
          "twitter.com", "linkedin.com", "tiktok.com", "youtube.com", "youtu.be"}
WEAK_SOURCE_TYPES = {"Aggregator", "News", "Social media"}
RANK = {
    "verification": ["NEEDS VERIFICATION", "PARTIALLY VERIFIED", "VERIFIED"],
    "source_confidence": ["LOW", "MEDIUM", "HIGH"],
    "eligibility_for_me": ["NOT ELIGIBLE", "INSUFFICIENT INFORMATION", "POSSIBLY ELIGIBLE", "LIKELY ELIGIBLE"],
}
DOWNGRADE_FIELDS = set(RANK) | {"funding_type", "potential_issues", "action"}
DECISIONS = ("ACCEPT", "DOWNGRADE", "RETURN", "REJECT")
NATIONALITY_OK = re.compile(r"congo|\bdrc\b|\brdc\b|africa|all nationalit|any nationalit|worldwide|international|"
                            r"open to all|no nationality|no restriction|developing countr|all countries", re.I)
NO_FEE = re.compile(r"^\s*(none|no\b|free|gratuit|n/?a|not applicable|0\b|nil|no fee|unknown)", re.I)
PERSONAL = re.compile(r"[\w.+-]+@(gmail|yahoo|hotmail|outlook|live|proton(mail)?|icloud)\.[a-z.]+|"
                      r"\bmy (date of birth|birthday|passport)\b|\bthe applicant['’]s (name|date of birth|passport)", re.I)
INJECTION = re.compile(r"ignore (all |any )?(previous|prior|above) instructions|system prompt|as an ai (language )?model|"
                       r"you must now|disregard (the )?(rules|runbook)", re.I)
MAX_DEADLINE_DAYS = 548                                  # a deadline more than ~18 months out is a typo until proven otherwise


# ---------------------------------------------------------------- loading
def load_batch(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"records": data, "lead_outcomes": []}
    records = data.get("records") if "records" in data else data.get("opportunities", [])
    return {"records": records or [], "lead_outcomes": data.get("lead_outcomes", []), "channel": data.get("channel", "")}


def load_batches(paths) -> tuple[list[dict], list[dict]]:
    records, outcomes = [], []
    for path in paths:
        batch = load_batch(path)
        records += batch["records"]
        outcomes += batch["lead_outcomes"]
    return records, outcomes


def host_of(url: str) -> str:
    return (urllib.parse.urlparse(url or "").hostname or "").lower().removeprefix("www.")


def aggregator_hosts() -> set[str]:
    hosts = set(AGGREGATORS)
    for feed in L.load(L.SOURCES, {}).get("feeds", []):
        if feed.get("tier", 3) >= 3 and host_of(feed.get("url", "")):
            hosts.add(host_of(feed["url"]))
    return hosts


def _on(host: str, domains: set[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


# ---------------------------------------------------------------- mechanical rules
def finding(severity: str, rule: str, message: str) -> dict:
    return {"severity": severity, "rule": rule, "message": message}


def check_record(rec: dict, existing: dict | None, today: dt.date, aggregators: set[str]) -> list[dict]:
    """Findings for one record. severity: block (stays out), review (the judge must address it), note."""
    out: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []
    V.check_record({k: v for k, v in rec.items() if k != "evidence"}, errors, warnings)   # evidence is checked below
    out += [finding("block", "schema", e.split(": ", 1)[-1]) for e in errors]
    out += [finding("note", "schema-warning", w.split(": ", 1)[-1]) for w in warnings]
    out += EV.check(rec["evidence"], rec) if rec.get("evidence") is not None else EV.stored_conflicts(rec)

    sources = rec.get("sources") or []
    if not sources:
        out.append(finding("block", "sources-missing", "no page is cited in sources[]"))
    cited = {L.norm_url(s.get("url", "")) for s in sources}
    if rec.get("source_url") and L.norm_url(rec["source_url"]) not in cited:
        out.append(finding("block", "source-url-not-cited", "source_url is not one of the pages listed in sources[]"))

    for field in ("official_application_url", "official_information_url"):
        host = host_of(rec.get(field, ""))
        if host and _on(host, aggregators | SOCIAL):
            out.append(finding("block", "official-url-is-aggregator", f"{field} points to {host}, which is not the organiser"))

    types = [s.get("type") for s in sources]
    official_hosts = {host_of(s.get("url", "")) for s in sources if s.get("type") == "Official"}
    if rec.get("verification") == "VERIFIED":
        info_host = host_of(rec.get("official_information_url", ""))
        if not any(h and (h == info_host or h.endswith("." + info_host) or info_host.endswith("." + h))
                   for h in official_hosts):
            out.append(finding("block", "verified-without-official-page",
                               "VERIFIED, but no Official page in sources[] is on the host of official_information_url"))
    if sources and all(t in WEAK_SOURCE_TYPES for t in types):
        if rec.get("verification") != "NEEDS VERIFICATION" or rec.get("source_confidence") == "HIGH":
            out.append(finding("block", "aggregator-only", "every cited page is an aggregator, news or social page: "
                               "the record can only be NEEDS VERIFICATION with LOW or MEDIUM confidence"))
    if rec.get("funding_type") == "Fully Funded":
        if not any(t in ("Official", "Institutional") for t in types):
            out.append(finding("block", "fully-funded-without-organiser", "Fully Funded needs the organiser's own page"))
        elif "Covered" not in (rec.get("coverage") or {}).values():
            out.append(finding("review", "fully-funded-unitemised", "Fully Funded but no coverage item is marked Covered"))

    deadline = L.parse_date(rec.get("application_deadline"))
    if rec.get("application_deadline") and not deadline:
        out.append(finding("block", "deadline-format", "application_deadline is not a date"))
    if deadline:
        if rec.get("deadline_text") in (None, "", L.UNKNOWN):
            out.append(finding("block", "deadline-without-wording", "a deadline needs the source's own wording in deadline_text"))
        if (deadline - today).days > MAX_DEADLINE_DAYS:
            out.append(finding("block", "deadline-too-far", f"{deadline} is more than {MAX_DEADLINE_DAYS} days away"))
        if deadline < today:
            out.append(finding("note", "deadline-passed", "the deadline has passed; the daily job will archive the record"))
    verified = L.parse_date(rec.get("last_verified"))
    if verified and verified > today:
        out.append(finding("block", "last-verified-future", "last_verified is in the future"))
    elif verified and verified < today:
        out.append(finding("review", "not-re-read-today", f"last_verified is {verified}: was this page read in this cycle?"))

    if rec.get("eligibility_for_me") == "LIKELY ELIGIBLE":
        if len((rec.get("eligibility_reason") or "").strip()) < 30:
            out.append(finding("block", "eligibility-unexplained", "LIKELY ELIGIBLE needs eligibility_reason naming the deciding criteria"))
        nat = rec.get("nationality_requirements")
        if nat in (None, "", L.UNKNOWN):
            out.append(finding("review", "nationality-unknown", "LIKELY ELIGIBLE but the nationality rule is not recorded"))
        elif not NATIONALITY_OK.search(str(nat)):
            out.append(finding("review", "nationality-may-exclude", f"nationality rule {str(nat)[:80]!r} does not name the DRC or Africa"))

    fee = rec.get("participation_fee")
    if fee and not NO_FEE.search(str(fee)) and (rec.get("verification") == "VERIFIED"
                                               or rec.get("upfront_cost_risk") in (None, "", "None", "Low")):
        out.append(finding("review", "fee-present", f"participation_fee {str(fee)[:60]!r}: check the scam rules and the cost risk"))

    blob = json.dumps(rec, ensure_ascii=False)
    if PERSONAL.search(blob):
        out.append(finding("block", "personal-data", "an email at a personal provider or a first-person identity phrase appears in the record"))
    if INJECTION.search(blob):
        out.append(finding("block", "injected-text", "the record contains text that reads like an instruction to an AI"))
    if not rec.get("match_keywords"):
        out.append(finding("note", "no-match-keywords", "match_keywords is empty: the feed matcher cannot recognise this record"))

    if existing:
        out += compare_with_existing(existing, rec)
    return out


def compare_with_existing(old: dict, new: dict) -> list[dict]:
    """What a batch record changes in a record that is already published."""
    out = []
    for field in L.TRACKED_FIELDS:
        if old.get(field) == new.get(field):
            continue
        if field in RANK:
            order = RANK[field]
            before, after = order.index(old[field]) if old.get(field) in order else -1, \
                order.index(new[field]) if new.get(field) in order else -1
            if after > before:
                out.append(finding("review", f"raised:{field}", f"{field}: {old.get(field)} -> {new.get(field)} needs a quoted page"))
            else:
                out.append(finding("note", f"lowered:{field}", f"{field}: {old.get(field)} -> {new.get(field)}"))
        elif field == "application_deadline" and old.get(field) and not new.get(field):
            out.append(finding("review", "deadline-removed", f"deadline {old[field]} was removed"))
        elif field in ("application_deadline", "funding_type", "nationality_requirements", "age_requirement"):
            out.append(finding("review", f"changed:{field}", f"{field}: {str(old.get(field))[:60]} -> {str(new.get(field))[:60]}"))
        elif old.get(field) and new.get(field) in (None, "", L.UNKNOWN):
            out.append(finding("note", f"emptied:{field}", f"{field} had a value and is now empty"))
    return out


def merge_like_upsert(rec: dict, db_records: list[dict], today: dt.date) -> tuple[dict, dict | None]:
    """The record as scripts/upsert.py would store it: a batch record may be a patch over a published one."""
    raw = dict(rec)
    raw.setdefault("id", L.slug(raw.get("title", "")))
    existing = L.find_duplicate(db_records, raw) if db_records else None
    if existing is None:
        raw.setdefault("date_discovered", today.isoformat())
        return L.normalize(raw, today), None
    merged = dict(existing)
    merged.update(raw)
    merged["id"] = existing["id"]
    merged["date_discovered"] = existing.get("date_discovered") or today.isoformat()
    return L.normalize(merged, today), existing


def check_batch(records: list[dict], db_records: list[dict], today: dt.date) -> dict:
    """Findings per record id, computed on the merged record. The same record twice in one batch is a block."""
    aggregators = aggregator_hosts()
    report: dict[str, list[dict]] = {}
    seen: dict[str, str] = {}
    for rec in records:
        merged, existing = merge_like_upsert(rec, db_records, today)
        rid = merged["id"] or "(no id)"
        findings = check_record(merged, existing, today, aggregators)
        key = L.dedupe_key(merged)
        if rid in report or key in seen:
            findings.append(finding("block", "duplicate-in-batch", f"appears twice in the batch (also as {seen.get(key, rid)})"))
        seen[key] = rid
        report.setdefault(rid, []).extend(findings)
    return report


def merged_by_id(records: list[dict], db_records: list[dict], today: dt.date) -> dict[str, dict]:
    out = {}
    for rec in records:
        merged, _ = merge_like_upsert(rec, db_records, today)
        out[merged["id"]] = merged
    return out


def blocked(report: dict) -> set[str]:
    return {rid for rid, fs in report.items() if any(f["severity"] == "block" for f in fs)}


# ---------------------------------------------------------------- quotes
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_status(url: str, quote: str, cache: dict, fetch=None) -> str:
    """found | not_found | unreachable. The page is fetched once per url."""
    fetch = fetch or L.fetch
    if url not in cache:
        status, _final, body = fetch(url, timeout=25)
        cache[url] = normalize_text(" ".join(L.visible_lines(body))) if status == 200 and body else None
    if cache[url] is None:
        return "unreachable"
    return "found" if normalize_text(quote) in cache[url] else "not_found"


def verify_quotes(verdicts: dict, fetch=None) -> dict[str, list[dict]]:
    """Per verdict id (record id or 'lead:<id>'): the status of each evidence quote."""
    cache: dict = {}
    out: dict[str, list[dict]] = {}
    for v in verdicts.get("records", []):
        out[v.get("id", "")] = [_evidence_status(e, cache, fetch) for e in v.get("evidence", [])]
    for v in verdicts.get("lead_outcomes", []):
        out["lead:" + v.get("lead_id", "")] = [_evidence_status(e, cache, fetch) for e in v.get("evidence", [])]
    return out


def _evidence_status(item: dict, cache: dict, fetch) -> dict:
    url, quote = item.get("url", ""), item.get("quote", "")
    if len(normalize_text(quote)) < 12:
        return {"url": url, "status": "too_short", "via": item.get("via", "")}
    return {"url": url, "status": quote_status(url, quote, cache, fetch), "via": item.get("via", "")}


def verify_evidence(records: list[dict], fetch=None) -> dict[str, list[dict]]:
    """Per record id: the status of every quote inside its `evidence` block, read on the page it cites."""
    cache: dict = {}
    out: dict[str, list[dict]] = {}
    for rec in records:
        ev = rec.get("evidence")
        if not ev:
            continue
        rid = rec.get("id") or L.slug(rec.get("title", ""))
        out[rid] = [{"where": where, "url": page, "status": quote_status(page, quote, cache, fetch)}
                    for where, page, quote in EV.quote_items(ev)]
    return out


def unproven_evidence(rid: str, results: list[dict] | None, cited: set[str], verdict: dict) -> str:
    """Why an evidence block cannot be trusted, or an empty string. A page nobody can read counts only when
    the judge declared (via) that another reader saw the quote, exactly as for the judge's own quotes."""
    if results is None:
        return "evidence quotes were not checked"
    declared = {L.norm_url(e.get("url", "")) for e in (verdict.get("evidence") or []) if e.get("via")}
    for r in results:
        norm = L.norm_url(r["url"])
        if norm not in cited:
            return f"{r['where']}: page {r['url']} is not cited in sources[]"
        if r["status"] == "not_found":
            return f"{r['where']}: the quote is not on {r['url']}"
        if r["status"] == "unreachable" and norm not in declared:
            return f"{r['where']}: {r['url']} could not be read and the judge declared no 'via'"
    return ""


# ---------------------------------------------------------------- apply
def lower_only(rec: dict, changes: dict) -> tuple[dict, list[str]]:
    """Apply the judge's changes. Anything that would raise trust, or touch another field, is refused."""
    refused, applied = [], dict(rec)
    for field, value in (changes or {}).items():
        if field not in DOWNGRADE_FIELDS:
            refused.append(f"{field}: the judge may not edit this field (RETURN the record to its scout)")
        elif field in RANK:
            order = RANK[field]
            if value not in order or rec.get(field) not in order or order.index(value) > order.index(rec[field]):
                refused.append(f"{field}: {rec.get(field)} -> {value} would not lower trust")
            else:
                applied[field] = value
        elif field == "funding_type":
            if value == "Funding Unclear":
                applied[field] = value
            else:
                refused.append("funding_type: only 'Funding Unclear' is allowed as a downgrade")
        elif field == "potential_issues":
            applied[field] = list(rec.get(field) or []) + [x for x in (value if isinstance(value, list) else [value]) if x]
        elif field == "action":
            applied[field] = str(value)
    return applied, refused


def apply(records: list[dict], verdicts: dict, report: dict, quotes: dict, merged: dict | None = None,
          evidence_quotes: dict | None = None) -> dict:
    """Decide each record. Returns {"accepted": [records], "log": {...}}; see the module docstring."""
    by_id = {v.get("id"): v for v in verdicts.get("records", [])}
    accepted, log = [], {"accepted": [], "downgraded": [], "returned": [], "rejected": [], "unreviewed": [],
                         "blocked": [], "quote_failed": [], "refused_changes": [], "evidence_dropped": []}
    block_ids = blocked(report)
    merged = merged or {}
    for rec in records:
        rid = rec.get("id") or L.slug(rec.get("title", ""))
        base = merged.get(rid, rec)
        verdict = by_id.get(rid)
        if rid in block_ids:
            log["blocked"].append({"id": rid, "rules": [f["rule"] for f in report[rid] if f["severity"] == "block"]})
            continue
        if not verdict:
            log["unreviewed"].append(rid)
            continue
        decision = verdict.get("decision")
        if decision not in DECISIONS:
            log["unreviewed"].append(rid)
            continue
        if decision == "RETURN":
            log["returned"].append({"id": rid, "reason": verdict.get("reason", "")})
            continue
        if decision == "REJECT":
            log["rejected"].append({"id": rid, "reason": verdict.get("reason", "")})
            continue
        warning_only = base.get("verification") == "NEEDS VERIFICATION" and base.get("source_confidence") == "LOW"
        results = quotes.get(rid, [])
        cited = {L.norm_url(s.get("url", "")) for s in base.get("sources") or []}
        if not warning_only and not results:
            log["quote_failed"].append({"id": rid, "why": "no evidence quote from the judge"})
            continue
        # A quote counts when the checker found it on the page, or when the judge declares (via) that another
        # reader saw it. A page nobody can read leaves the quote unproven: the record is held back, not trusted.
        bad = [r for r in results if r["status"] in ("not_found", "too_short")
               or (r["status"] == "unreachable" and not r["via"]) or L.norm_url(r["url"]) not in cited]
        if bad:
            why = ("page unreadable by the checker and no 'via' declared" if bad[0]["status"] == "unreachable"
                   else f"{bad[0]['status']} / not cited")
            log["quote_failed"].append({"id": rid, "why": f"{why}: {bad[0]['url']}"})
            continue
        final, issues = dict(rec), []
        if decision == "DOWNGRADE":
            lowered, refused = lower_only(base, verdict.get("changes") or {})
            if refused:
                log["refused_changes"].append({"id": rid, "refused": refused})
                continue
            final.update({k: lowered[k] for k in verdict.get("changes") or {}})
        if final.get("evidence"):
            why = unproven_evidence(rid, (evidence_quotes or {}).get(rid) if evidence_quotes is not None else None,
                                    cited, verdict)
            if why:
                final.pop("evidence")
                log["evidence_dropped"].append({"id": rid, "why": why})
        accepted.append(final)
        log["downgraded" if decision == "DOWNGRADE" else "accepted"].append(rid)
    return {"accepted": accepted, "log": log}


# ---------------------------------------------------------------- leads
OUTCOMES = {"PROMOTED", "UNDER REVIEW", "OFFICIAL SOURCE FOUND", "VERIFICATION REQUIRED", "NOT CURRENTLY OPEN",
            "RECURRING PROGRAMME", "EXCLUDED - CONFIRMED INELIGIBLE", "REJECTED - NOT A LEGITIMATE OPPORTUNITY"}
EXCLUSIONS = {"EXCLUDED - CONFIRMED INELIGIBLE", "REJECTED - NOT A LEGITIMATE OPPORTUNITY"}


def apply_leads(leads: list[dict], outcomes: list[dict], verdicts: dict, accepted_ids: set[str],
                quotes: dict, stamp: str) -> dict:
    """Set lead statuses from scout outcomes. A lead is never deleted and an exclusion needs the judge's CONFIRM."""
    by_id = {x["id"]: x for x in leads}
    confirmed = {v["lead_id"] for v in verdicts.get("lead_outcomes", []) if v.get("decision") == "CONFIRM"}
    log = {"applied": [], "held_for_review": [], "unknown_lead": [], "invalid": []}
    for out in outcomes:
        lead = by_id.get(out.get("lead_id"))
        kind = out.get("outcome")
        if lead is None:
            log["unknown_lead"].append(out.get("lead_id"))
            continue
        if kind not in OUTCOMES:
            log["invalid"].append({"lead_id": lead["id"], "why": f"unknown outcome {kind!r}"})
            continue
        if kind == "PROMOTED":
            if out.get("record_id") in accepted_ids:
                lead.update({"status": "PUBLISHED", "record_id": out["record_id"], "reviewed_on": stamp})
                log["applied"].append(lead["id"])
            else:
                lead.update({"status": "UNDER REVIEW", "review_note": "promotion was not accepted by the judge"})
                log["held_for_review"].append(lead["id"])
            continue
        if kind in EXCLUSIONS:
            statuses = quotes.get("lead:" + lead["id"], [])
            ok = lead["id"] in confirmed and out.get("reason") and out.get("page") and \
                all(r["status"] == "found" or r["via"] for r in statuses) and bool(statuses)
            if not ok:
                lead.update({"status": "UNDER REVIEW", "review_note": f"{kind.lower()} proposed but not confirmed by the judge"})
                log["held_for_review"].append(lead["id"])
                continue
            lead.update({"status": kind, "exclusion_reason": out["reason"], "exclusion_page": out["page"],
                         "reviewed_on": stamp})
            log["applied"].append(lead["id"])
            continue
        if kind in ("OFFICIAL SOURCE FOUND", "NOT CURRENTLY OPEN") and not out.get("page"):
            log["invalid"].append({"lead_id": lead["id"], "why": f"{kind} needs the page that shows it"})
            continue
        lead.update({"status": kind, "reviewed_on": stamp})
        if out.get("page"):
            lead["official_page"] = out["page"]
        log["applied"].append(lead["id"])
    return log


# ---------------------------------------------------------------- cli
def _print_report(report: dict) -> None:
    for rid, findings in report.items():
        marks = {"block": 0, "review": 0, "note": 0}
        for f in findings:
            marks[f["severity"]] += 1
        print(f"{'BLOCK ' if marks['block'] else 'review' if marks['review'] else 'ok    '} {rid}  "
              f"(block {marks['block']}, review {marks['review']}, note {marks['note']})")
        for f in findings:
            if f["severity"] != "note":
                print(f"    {f['severity']:<6} {f['rule']}: {f['message']}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    c.add_argument("--out")
    v = sub.add_parser("verify")
    v.add_argument("verdicts")
    a = sub.add_parser("apply")
    a.add_argument("--batches", nargs="+", required=True)
    a.add_argument("--verdicts", required=True)
    a.add_argument("--out-dir")
    a.add_argument("--no-network", action="store_true", help="skip the quote check (tests only: nothing counts as found)")
    al = sub.add_parser("apply-leads")
    al.add_argument("--batches", nargs="+", required=True)
    al.add_argument("--verdicts", required=True)
    al.add_argument("--accepted", required=True)
    args = parser.parse_args()
    today = L.today_utc()

    if args.cmd == "check":
        records, _ = load_batches(args.files)
        report = check_batch(records, L.load_db()["opportunities"], today)
        _print_report(report)
        if args.out:
            Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"judge check: {len(report)} records, {len(blocked(report))} blocked")
        return 1 if blocked(report) else 0

    verdicts = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    if args.cmd == "verify":
        for key, items in verify_quotes(verdicts).items():
            for item in items:
                print(f"{item['status']:<12} {key}  {item['url']}")
        return 0

    records, outcomes = load_batches(args.batches)
    if args.cmd == "apply":
        report = check_batch(records, L.load_db()["opportunities"], today)
        quotes = ({k: [{**e, "status": "unreachable"} for e in v] for k, v in verify_quotes(
            verdicts, fetch=lambda *a, **k: (0, "", b"")).items()} if args.no_network else verify_quotes(verdicts))
        fetch_none = (lambda *a, **k: (0, "", b"")) if args.no_network else None
        result = apply(records, verdicts, report, quotes, merged_by_id(records, L.load_db()["opportunities"], today),
                       verify_evidence(records, fetch_none))
        out_dir = Path(args.out_dir) if args.out_dir else Path(args.batches[0]).resolve().parent.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "accepted.json").write_text(json.dumps(result["accepted"], indent=2, ensure_ascii=False) + "\n",
                                               encoding="utf-8", newline="\n")
        (out_dir / "judge").mkdir(exist_ok=True)       # reports live in a subfolder: a stray research/DATE/*.json glob must not catch them
        (out_dir / "judge" / "judge-report.json").write_text(json.dumps({"date": today.isoformat(), **result["log"],
                                                               "findings": report}, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8", newline="\n")
        print("judge apply:", ", ".join(f"{k} {len(v)}" for k, v in result["log"].items()), f"-> {out_dir / 'accepted.json'}")
        return 0

    accepted_ids = {r["id"] for r in json.loads(Path(args.accepted).read_text(encoding="utf-8"))}
    store = L.load(L.LEADS, {"schema_version": 1, "updated": "", "leads": []})
    quotes = verify_quotes(verdicts)
    log = apply_leads(store["leads"], outcomes, verdicts, accepted_ids, quotes, today.isoformat())
    store["updated"] = today.isoformat()
    L.save(L.LEADS, store)
    print("judge apply-leads:", ", ".join(f"{k} {len(v)}" for k, v in log.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
