"""Data-integrity guard for upgrade work. Standard library only. Read-only except `snapshot`.

    python scripts/integrity.py snapshot data/snapshots/baseline-YYYY-MM-DD.json
    python scripts/integrity.py check    data/snapshots/baseline-YYYY-MM-DD.json

A snapshot stores, for every live record and every archived record, a SHA-256 of its factual
fields (TRACKED_FIELDS plus a few identity fields). `check` compares today's data with a snapshot:

  * a record or archive entry that has DISAPPEARED is an error (history must never shrink);
  * a record whose factual fields CHANGED is reported, not failed: research cycles legitimately
    change facts. The report lets a reviewer confirm that every change was intended;
  * new records are fine.

Derived fields (status, status_computed_on) are ignored on purpose: the daily refresh rewrites them.
Exit code 1 only when something disappeared.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import oplib as L

IDENTITY = ["id", "title", "organization", "official_application_url", "official_information_url"]
FACT_FIELDS = sorted(set(L.TRACKED_FIELDS) | set(IDENTITY) | {"last_verified"})


def fingerprint(rec: dict) -> str:
    payload = {k: rec.get(k) for k in FACT_FIELDS if k != "last_verified"}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def collect() -> dict:
    db, archive = L.load_db(), L.load_archive()
    return {
        "live": {r["id"]: {"fact_hash": fingerprint(r), "last_verified": r.get("last_verified", "")}
                 for r in db["opportunities"]},
        "archive": {a.get("archive_id") or a["id"]: {"fact_hash": fingerprint(a)}
                    for a in archive["opportunities"]},
    }


def snapshot(path: Path) -> int:
    data = collect()
    data["taken_on"] = L.today_utc().isoformat()
    data["counts"] = {"live": len(data["live"]), "archive": len(data["archive"])}
    L.save(path, data)
    print(f"snapshot written: {path} ({data['counts']['live']} live, {data['counts']['archive']} archived)")
    return 0


def check(path: Path) -> int:
    old, new = L.load(path, None), collect()
    if old is None:
        print(f"integrity: snapshot not found: {path}")
        return 1
    lost, changed = [], []
    for kind in ("live", "archive"):
        for key, entry in old[kind].items():
            now = new[kind].get(key)
            if now is None:
                # A live record may legitimately move to the archive when its one-off cycle closes.
                moved = kind == "live" and any(k.startswith(key + "@") for k in new["archive"])
                if not moved:
                    lost.append(f"{kind}:{key}")
            elif now["fact_hash"] != entry["fact_hash"]:
                changed.append(f"{kind}:{key}")
    added = [k for k in new["live"] if k not in old["live"]]
    print(f"integrity vs {old.get('taken_on', '?')}: {len(old['live'])} live / {len(old['archive'])} archive "
          f"before; {len(new['live'])} / {len(new['archive'])} now")
    print(f"  lost: {len(lost)}   fact-changed: {len(changed)}   added: {len(added)}")
    for item in lost:
        print("  LOST", item)
    for item in changed[:30]:
        print("  changed", item)
    return 1 if lost else 0


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in ("snapshot", "check"):
        print(__doc__)
        return 2
    path = Path(argv[2])
    return snapshot(path) if argv[1] == "snapshot" else check(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
