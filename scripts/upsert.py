"""Merge researched records into data/opportunities.json.

Usage:
    python scripts/upsert.py batch.json [more.json ...]

A batch file is a JSON array of records (schema: README, "Data structure").
For each record the script:
  * finds the existing record for the same opportunity (same id, same official
    page, or same title + organiser) so that no duplicate is created;
  * merges the new facts over the old ones;
  * logs every changed tracked field (deadline, funding, eligibility, URLs ...)
    to data/changelog.json;
  * recomputes the derived fields (status, *_funded booleans);
  * moves an `evidence` block (per-criterion eligibility, funding detail, cycles) out of the record into
    data/evidence/<id>.json, where earlier cycles are kept and changes are logged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import evidence as EV
import oplib as L


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    db = L.load_db()
    records = db["opportunities"]
    today = L.today_utc()
    stamp = today.isoformat()
    changes: list[dict] = []
    added = updated = stored = 0

    for path in paths:
        batch = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(batch, dict):
            if "opportunities" not in batch and not batch.get("title"):
                print(f"upsert: {path} is not a batch of records (no 'opportunities' list and no title); skipped")
                continue
            batch = batch.get("opportunities", [batch])
        for raw in batch:
            raw.setdefault("id", L.slug(raw.get("title", "")))
            evidence = raw.pop("evidence", None)
            existing = L.find_duplicate(records, raw)
            if existing is None:
                raw.setdefault("date_discovered", stamp)
                records.append(L.normalize(raw, today))
                added += 1
                changes.append({"date": stamp, "id": raw["id"], "title": raw.get("title", ""),
                                "field": "(new record)", "old": None, "new": "added"})
                if evidence:
                    EV.store(raw["id"], evidence, today, changes, raw.get("title", ""))
                    stored += 1
                continue
            merged = dict(existing)
            merged.update(raw)
            merged["id"] = existing["id"]
            merged["date_discovered"] = existing.get("date_discovered") or stamp
            merged = L.normalize(merged, today)
            for change in L.diff_tracked(existing, merged):
                changes.append({"date": stamp, "id": merged["id"], "title": merged["title"], **change})
            records[records.index(existing)] = merged
            updated += 1
            if evidence:
                EV.store(merged["id"], evidence, today, changes, merged["title"])
                stored += 1

    records.sort(key=lambda r: r["id"])
    db["updated"] = stamp
    L.save(L.DB, db)
    L.log_changes(changes)
    print(f"upsert: {added} added, {updated} updated, {len(records)} records in database, "
          f"{len(changes)} change-log entries, {stored} evidence files written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
