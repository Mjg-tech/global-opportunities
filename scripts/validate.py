"""Validate data/opportunities.json (and the archive) against the schema rules.

Exit code 1 if any error is found, so the GitHub Action refuses to publish a
broken or dishonest database. Run it after every edit:

    python scripts/validate.py
"""
from __future__ import annotations

import re
import sys

import oplib as L

URL = re.compile(r"^https?://[^\s]+$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_record(rec: dict, errors: list[str], warnings: list[str]) -> None:
    rid = rec.get("id") or "(no id)"

    def err(msg: str) -> None:
        errors.append(f"{rid}: {msg}")

    def warn(msg: str) -> None:
        warnings.append(f"{rid}: {msg}")

    for field in ("id", "title", "organization", "overview", "eligibility_reason", "last_verified",
                  "date_discovered"):
        if not rec.get(field):
            err(f"missing {field}")
    if rec.get("id") != L.slug(rec.get("id", "")):
        err("id must be a lowercase slug")
    for field in ("application_deadline", "opens_on", "last_verified", "date_discovered",
                  "last_cycle_deadline"):
        value = rec.get(field)
        if value and not ISO.match(value):
            err(f"{field} must be YYYY-MM-DD or empty, got {value!r}")
    for field in ("official_application_url", "official_information_url", "source_url"):
        value = rec.get(field)
        if value and not URL.match(value):
            err(f"{field} is not a URL: {value!r}")
    if not rec.get("source_url"):
        err("source_url is required: every record must be traceable")

    def enum(field: str, allowed: list[str], many: bool = False) -> None:
        value = rec.get(field)
        values = value if many else [value]
        for item in values or []:
            if item not in allowed:
                err(f"{field}: {item!r} not in {allowed}")

    enum("category", L.CATEGORIES, many=True)
    enum("education_levels", L.EDUCATION_LEVELS, many=True)
    enum("funding_type", L.FUNDING_TYPES)
    enum("verification", L.VERIFICATION)
    enum("eligibility_for_me", L.ELIGIBILITY)
    enum("source_confidence", L.CONFIDENCE)
    enum("source_type", L.SOURCE_TYPES)
    enum("location_type", L.LOCATION_TYPES)
    enum("delivery_mode", L.DELIVERY_MODES)
    enum("status", L.STATUSES)
    if not rec.get("category"):
        err("at least one category is required")
    for key, value in (rec.get("coverage") or {}).items():
        if key not in L.COVERAGE_KEYS:
            err(f"coverage: unknown key {key!r}")
        if value not in L.COVERAGE_VALUES:
            err(f"coverage.{key}: {value!r} not in {L.COVERAGE_VALUES}")
    for key, value in (rec.get("relevance") or {}).items():
        if key not in L.RELEVANCE_KEYS:
            err(f"relevance: unknown key {key!r}")
        if value not in L.RATINGS:
            err(f"relevance.{key}: {value!r} not in {L.RATINGS}")
    for src in rec.get("sources") or []:
        if not URL.match(src.get("url", "")):
            err(f"sources: bad url {src.get('url')!r}")
        if src.get("type") not in L.SOURCE_TYPES:
            err(f"sources: bad type {src.get('type')!r}")

    # Honesty rules (spec section 30).
    cov = rec.get("coverage") or {}
    if rec.get("verification") == "VERIFIED":
        if rec.get("source_type") != "Official":
            err("VERIFIED requires an Official source_type")
        if not rec.get("official_information_url"):
            err("VERIFIED requires official_information_url")
    if rec.get("funding_type") == "Fully Funded" and "Covered" not in cov.values():
        warn("Fully Funded but no coverage component is marked Covered (itemise it when the source allows)")
    if rec.get("funding_type") == "Fully Funded" and rec.get("verification") == "NEEDS VERIFICATION":
        err("Fully Funded may not be claimed on a record that still NEEDS VERIFICATION")
    if rec.get("status") != L.compute_status(rec):
        warn(f"stored status {rec.get('status')} differs from computed {L.compute_status(rec)}")
    if rec.get("application_deadline") and rec.get("deadline_text") in ("", L.UNKNOWN):
        warn("deadline date set but deadline_text (original wording) is empty")
    if rec.get("source_confidence") == "LOW" and not rec.get("potential_issues"):
        err("LOW confidence records must explain why in potential_issues")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    db = L.load_db()
    archive = L.load_archive()
    seen_ids: dict[str, str] = {}
    seen_keys: dict[str, str] = {}
    for rec in db["opportunities"]:
        check_record(rec, errors, warnings)
        rid, key = rec.get("id", ""), L.dedupe_key(rec)
        if rid in seen_ids:
            errors.append(f"{rid}: duplicate id")
        if key in seen_keys:
            errors.append(f"{rid}: duplicate of {seen_keys[key]} (same title and organiser)")
        seen_ids[rid] = rid
        seen_keys[key] = rid
    for rec in archive["opportunities"]:
        if not rec.get("archive_id"):
            errors.append(f"archive: {rec.get('id')} has no archive_id")

    for line in warnings:
        print("warning:", line)
    for line in errors:
        print("ERROR:", line)
    print(f"validate: {len(db['opportunities'])} live records, {len(archive['opportunities'])} archived, "
          f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
