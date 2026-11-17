"""Data-integrity, deadline and privacy tests. Run with:  python -m unittest discover -s tests -v"""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import integrity  # noqa: E402
import leadfilter as LF  # noqa: E402
import oplib as L  # noqa: E402

DB = L.load_db()["opportunities"]
ARCHIVE = L.load_archive()["opportunities"]
LEADS = L.load(L.LEADS, {"leads": []})["leads"]
TODAY = dt.date(2026, 11, 17)


class Database(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [r["id"] for r in DB]
        self.assertEqual(len(ids), len(set(ids)))

    def test_archive_ids_are_unique(self):
        ids = [a.get("archive_id") for a in ARCHIVE]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_record_names_a_source_page(self):
        bare = [r["id"] for r in DB
                if not any(str(r.get(k, "")).startswith("http")
                           for k in ("official_information_url", "official_application_url", "source_url"))]
        self.assertEqual(bare, [], "records with no source URL at all")

    def test_fully_funded_needs_official_evidence(self):
        weak = []
        for r in DB:
            if r.get("funding_type") == "Fully Funded":
                official = [s for s in r.get("sources", []) if s.get("type") in ("Official", "Institutional")]
                if not official:
                    weak.append(r["id"])
        self.assertEqual(weak, [], "Fully Funded without an Official or Institutional source")

    def test_no_future_verification_dates(self):
        future = [r["id"] for r in DB if (L.parse_date(r.get("last_verified")) or TODAY) > dt.date.today() + dt.timedelta(days=1)]
        self.assertEqual(future, [])


class Deadlines(unittest.TestCase):
    def rec(self, **kw):
        return dict(kw)

    def test_past_deadline(self):
        self.assertEqual(L.compute_status(self.rec(application_deadline="2026-11-16"), TODAY), "DEADLINE PASSED")

    def test_deadline_today_is_closing_soon_not_passed(self):
        self.assertEqual(L.compute_status(self.rec(application_deadline="2026-11-17"), TODAY), "CLOSING SOON")

    def test_closing_soon_window_is_14_days(self):
        self.assertEqual(L.compute_status(self.rec(application_deadline="2026-12-01"), TODAY), "CLOSING SOON")
        self.assertEqual(L.compute_status(self.rec(application_deadline="2026-12-02"), TODAY), "OPEN")

    def test_not_yet_open_is_upcoming(self):
        rec = self.rec(application_deadline="2027-03-01", opens_on="2027-01-01")
        self.assertEqual(L.compute_status(rec, TODAY), "UPCOMING")

    def test_rolling_beats_everything(self):
        self.assertEqual(L.compute_status(self.rec(rolling=True, application_deadline="2020-01-01"), TODAY), "ROLLING")

    def test_prediction_alone_is_upcoming_never_open(self):
        rec = self.rec(expected_next_cycle="Usually opens each autumn")
        self.assertEqual(L.compute_status(rec, TODAY), "UPCOMING")

    def test_no_information_is_date_unknown(self):
        self.assertEqual(L.compute_status({}, TODAY), "DATE UNKNOWN")

    def test_days_remaining(self):
        self.assertEqual(L.days_remaining({"application_deadline": "2026-11-27"}, TODAY), 10)


class Leads(unittest.TestCase):
    def test_lead_ids_are_unique(self):
        ids = [x["id"] for x in LEADS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_lead_is_a_link_with_a_known_unverified_status(self):
        allowed = set(LF.LEAD_STATUSES) | {LF.LEGACY_STATUS}      # legacy value until the next daily run migrates it
        bad = [x["id"] for x in LEADS
               if not str(x.get("url", "")).startswith("http") or x.get("status") not in allowed
               or x.get("status") in ("VERIFIED", "PUBLISHED")]
        self.assertEqual(bad, [])


class Privacy(unittest.TestCase):
    """The repository is public. The profile must stay anonymous."""

    FORBIDDEN_KEYS = {"name", "full_name", "first_name", "last_name", "email", "phone", "address",
                      "passport_number", "date_of_birth", "birth_date", "cv", "linkedin"}

    def test_profile_has_no_identifying_fields(self):
        profile = L.load(ROOT / "data" / "profile.json", {})
        self.assertEqual(self.FORBIDDEN_KEYS & {k.lower() for k in profile}, set())

    def test_profile_age_is_a_band_not_a_date(self):
        profile = L.load(ROOT / "data" / "profile.json", {})
        self.assertNotRegex(json.dumps(profile.get("age_band", "")), r"\b(19|20)\d{2}-\d{2}-\d{2}\b")

    def test_no_personal_file_types_committed(self):
        stray = [p.name for p in ROOT.rglob("*") if p.suffix.lower() in {".docx", ".doc", ".pdf"}
                 and ".git" not in p.parts]
        self.assertEqual(stray, [], "documents (CVs, passports) must never enter the public repository")


class History(unittest.TestCase):
    """Nothing recorded in the baseline snapshot may disappear."""

    SNAPSHOT = ROOT / "data" / "snapshots" / "baseline-2026-11-17.json"

    @unittest.skipUnless(SNAPSHOT.exists(), "baseline snapshot not present")
    def test_no_record_lost_since_baseline(self):
        self.assertEqual(integrity.check(self.SNAPSHOT), 0)

    def test_fingerprint_ignores_derived_status(self):
        a = {"id": "x", "title": "T", "organization": "O", "status": "OPEN", "application_deadline": "2027-01-01"}
        b = dict(a, status="CLOSING SOON")
        self.assertEqual(integrity.fingerprint(a), integrity.fingerprint(b))

    def test_fingerprint_detects_a_changed_deadline(self):
        a = {"id": "x", "title": "T", "organization": "O", "application_deadline": "2027-01-01"}
        b = dict(a, application_deadline="2027-02-01")
        self.assertNotEqual(integrity.fingerprint(a), integrity.fingerprint(b))


if __name__ == "__main__":
    unittest.main()
