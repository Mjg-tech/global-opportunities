"""Offline tests of the daily lead harvest. No network: `oplib.fetch` is replaced by a canned feed and
every data path points into a temporary directory, so the real data files are never touched.

The guarantee under test: nothing disappears. Every lead is active, archived, or recorded in the audit log.
"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import leadfilter as LF  # noqa: E402
import oplib as L  # noqa: E402
import refresh as R  # noqa: E402
import sourcelib as S  # noqa: E402

TODAY = dt.date(2026, 11, 17)


def rss(*items):
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><pubDate>{d}</pubDate></item>" for t, u, d in items)
    return f"<rss><channel>{body}</channel></rss>".encode("utf-8")


RECENT = "Mon, 16 Nov 2026 08:00:00 +0000"
OLD = "Mon, 01 Sep 2026 08:00:00 +0000"


class HarvestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.paths = {"LEADS": base / "leads.json", "SOURCES": base / "sources.json", "META": base / "meta.json"}
        self.addCleanup(self.tmp.cleanup)
        for name, path in self.paths.items():
            patcher = mock.patch.object(L, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, path in (("LEADS_ARCHIVE", base / "leads-archive.json"), ("LEAD_AUDIT", base / "lead-audit.json")):
            patcher = mock.patch.object(R, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        # the real registry and state files must never be read or written by a test
        self.registry_path, self.state_path = base / "source-registry.json", base / "source-state.json"
        for name, path in (("REGISTRY", self.registry_path), ("STATE", self.state_path)):
            patcher = mock.patch.object(S, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.feed_body = rss()
        self.feed_status = 200
        patcher = mock.patch.object(L, "fetch", lambda *a, **k: (self.feed_status, "", self.feed_body))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.rules = LF.load_rules()
        patcher = mock.patch.object(LF, "load_rules", lambda: self.rules)
        patcher.start()
        self.addCleanup(patcher.stop)
        L.save(L.SOURCES, {"feeds": [{"name": "Test feed", "url": "https://feed.example/rss", "tier": 3,
                                      "lang": "en", "enabled": True}]})
        self.db, self.archive = {"opportunities": []}, {"opportunities": []}

    def put_leads(self, *leads):
        L.save(L.LEADS, {"schema_version": 1, "updated": "", "leads": list(leads)})

    def lead(self, lid, title, first_seen="2026-11-10", **extra):
        base = {"id": lid, "title": title, "url": f"https://example.org/{lid}", "source": "Old feed",
                "source_tier": 3, "language": "en", "published": first_seen, "first_seen": first_seen,
                "status": "NEEDS VERIFICATION"}
        base.update(extra)
        return base

    def run_harvest(self):
        return R.harvest(self.db, self.archive, TODAY)

    def leads(self):
        return L.load(L.LEADS, {})["leads"]

    def archived(self):
        return L.load(R.LEADS_ARCHIVE, {"leads": []})["leads"]

    def audit(self):
        return L.load(R.LEAD_AUDIT, {"entries": []})["entries"]


class Rejections(HarvestCase):
    def test_rejected_titles_are_logged_with_a_reason_and_too_old_is_not(self):
        self.feed_body = rss(
            ("Fellowship call for young professionals 2027", "https://a.example/1", RECENT),
            ("ACME recrute un comptable", "https://a.example/2", RECENT),
            ("Rapport annuel de la Secrétaire générale", "https://a.example/3", RECENT),
            ("Old scholarship 2026", "https://a.example/4", OLD))
        _health, _reseen, new, summary = self.run_harvest()
        self.assertEqual(new, 1)
        reasons = sorted(e["reason"] for e in self.audit())
        self.assertEqual(reasons, ["no_opportunity_word", "not_opportunity"])
        self.assertEqual(summary["rejected_this_run"], {"not_opportunity": 1, "no_opportunity_word": 1, "too_old": 1})

    def test_the_same_rejected_title_is_logged_once(self):
        self.feed_body = rss(("ACME recrute un comptable", "https://a.example/2", RECENT))
        self.run_harvest()
        self.run_harvest()
        self.assertEqual(len(self.audit()), 1)

    def test_nationality_only_title_becomes_a_low_ranked_lead_not_a_rejection(self):
        self.feed_body = rss(("Internship 2027 for young Nigerian undergraduate students", "https://a.example/5", RECENT))
        self.run_harvest()
        lead, = self.leads()
        self.assertEqual(lead["status"], "NEW")
        self.assertTrue(any(f.startswith("audience:") for f in lead["flags"]))
        self.assertEqual(self.audit(), [])


class Retention(HarvestCase):
    def test_nothing_disappears_when_leads_expire(self):
        self.put_leads(self.lead("old1", "Fellowship A 2027", first_seen="2026-08-01"),
                       self.lead("new1", "Fellowship B 2027", first_seen="2026-11-10"))
        before = {x["id"] for x in self.leads()}
        self.run_harvest()
        after = {x["id"] for x in self.leads()} | {x["id"] for x in self.archived()}
        self.assertEqual(before, after)
        gone, = self.archived()
        self.assertEqual((gone["id"], gone["status"]), ("old1", "ARCHIVED"))
        self.assertIn("not reviewed within", gone["archive_reason"])

    def test_leads_under_review_are_never_expired_by_the_daily_job(self):
        self.put_leads(self.lead("held", "Fellowship C 2027", first_seen="2026-06-01", status="UNDER REVIEW", score=50, flags=[]))
        self.run_harvest()
        self.assertEqual([x["id"] for x in self.leads()], ["held"])
        self.assertEqual(self.archived(), [])

    def test_cap_archives_the_lowest_scores_and_keeps_them(self):
        self.rules = {"retention": dict(self.rules["retention"], max_active_leads=2), "score": self.rules["score"]}
        self.put_leads(self.lead("a", "Fully funded fellowship Africa 2027", score=90, flags=[], status="NEW"),
                       self.lead("b", "Scholarship call 2027", score=70, flags=[], status="NEW"),
                       self.lead("c", "Internship for young Nigerian students", score=8, flags=["x"], status="NEW"))
        self.run_harvest()
        self.assertEqual(sorted(x["id"] for x in self.leads()), ["a", "b"])
        low, = self.archived()
        self.assertEqual(low["id"], "c")
        self.assertIn("below the cap", low["archive_reason"])

    def test_leads_under_review_survive_the_cap(self):
        self.rules = {"retention": dict(self.rules["retention"], max_active_leads=1), "score": self.rules["score"]}
        self.put_leads(self.lead("rev", "Review me 2027", score=5, flags=[], status="UNDER REVIEW"),
                       self.lead("n1", "Fellowship N1 2027", score=60, flags=[], status="NEW"),
                       self.lead("n2", "Fellowship N2 2027", score=50, flags=[], status="NEW"))
        self.run_harvest()
        ids = sorted(x["id"] for x in self.leads())
        self.assertEqual(ids, ["rev"])
        self.assertEqual(sorted(x["id"] for x in self.archived()), ["n1", "n2"])

    def test_finished_research_statuses_move_to_the_archive_unchanged(self):
        self.put_leads(self.lead("x1", "Fellowship for Kenyan citizens only 2027", status="EXCLUDED - CONFIRMED INELIGIBLE",
                                 exclusion_reason="Official page lists nationalities without the DRC", score=10, flags=[]),
                       self.lead("x2", "Scholarship with fee 2027", status="REJECTED - NOT A LEGITIMATE OPPORTUNITY", score=30, flags=[]),
                       self.lead("keep", "Fellowship 2027 keep", score=60, flags=[], status="NEW"))
        self.run_harvest()
        self.assertEqual([x["id"] for x in self.leads()], ["keep"])
        archived = {x["id"]: x for x in self.archived()}
        self.assertEqual(archived["x1"]["status"], "EXCLUDED - CONFIRMED INELIGIBLE")
        self.assertEqual(archived["x1"]["exclusion_reason"], "Official page lists nationalities without the DRC")
        self.assertEqual(archived["x2"]["status"], "REJECTED - NOT A LEGITIMATE OPPORTUNITY")

    def test_lead_that_became_a_record_is_archived_as_published(self):
        self.db["opportunities"] = [{"id": "chev", "title": "Chevening Scholarships", "match_keywords": ["chevening"]}]
        self.put_leads(self.lead("l1", "Chevening Scholarships 2027 open"))
        self.run_harvest()
        self.assertEqual(self.leads(), [])
        gone, = self.archived()
        self.assertEqual(gone["status"], "PUBLISHED")

    def test_archived_programme_returning_is_flagged_as_seen_before(self):
        L.save(R.LEADS_ARCHIVE, {"schema_version": 1, "updated": "", "leads": [
            self.lead("prev", "Obama Foundation Leaders Africa programme 2026", status="ARCHIVED")]})
        self.feed_body = rss(("Obama Foundation Leaders Africa programme 2027", "https://a.example/o27", RECENT))
        self.run_harvest()
        lead, = self.leads()
        self.assertEqual(lead.get("seen_before"), "prev")
        self.assertIn("recurring:seen-before", lead["flags"])

    def test_legacy_leads_are_migrated_in_place(self):
        self.put_leads(self.lead("legacy", "Fellowship for Kenyan students 2027"))
        self.run_harvest()
        lead, = self.leads()
        self.assertEqual(lead["status"], "NEW")
        self.assertIn("score", lead)


class FeedHealth(HarvestCase):
    def test_empty_feed_raises_an_alert_after_the_configured_number_of_runs(self):
        L.save(L.META, {"feeds": [{"name": "Test feed", "empty_streak": 6, "stale_streak": 0}]})
        self.feed_status, self.feed_body = 520, b""
        health, *_ = self.run_harvest()
        self.assertEqual(health[0]["empty_streak"], 7)
        self.assertIn("no items for 7 runs", health[0]["alert"])

    def test_healthy_feed_resets_the_streaks(self):
        L.save(L.META, {"feeds": [{"name": "Test feed", "empty_streak": 5, "stale_streak": 3}]})
        self.feed_body = rss(("Fellowship call 2027", "https://a.example/9", RECENT))
        health, *_ = self.run_harvest()
        self.assertEqual((health[0]["empty_streak"], health[0]["stale_streak"], health[0]["alert"]), (0, 0, ""))

    def test_feed_of_only_old_items_counts_as_stale(self):
        self.feed_body = rss(("Old fellowship", "https://a.example/10", OLD), ("Old award", "https://a.example/11", OLD))
        health, *_ = self.run_harvest()
        self.assertEqual(health[0]["stale_streak"], 1)


LISTING = b"""<html><body>
<a href="/opportunities/young-leaders-fellowship-2027">Call for applications: Young Leaders Fellowship 2027</a>
<a href="/about">About the organisation and its long history of work</a>
<a href="https://elsewhere.example/scholarship-2027">Scholarship 2027 on another domain entirely here</a>
</body></html>"""


class RegistrySources(HarvestCase):
    """Sources from data/source-registry.json run through the same lead pipeline as the legacy feeds."""

    def setUp(self):
        super().setUp()
        self.pages, self.calls = {}, []
        S._ROBOTS.clear()                      # robots.txt answers are cached per process; tests must not share them
        self.addCleanup(S._ROBOTS.clear)
        patcher = mock.patch.object(L, "fetch", self.route)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.feed_body = rss()                 # the legacy feed stays empty so only registry sources matter

    def route(self, url, timeout=25, accept=None):
        self.calls.append(url)
        if url in self.pages:
            status, body = self.pages[url]
            return status, url, body
        if url.endswith("/robots.txt"):
            return 404, url, b""
        if url == "https://feed.example/rss":
            return self.feed_status, url, self.feed_body
        return 404, url, b""

    def source(self, sid="src-one", status="active", **extra):
        base = {"source_id": sid, "organization": "Example Org", "label": "Listing", "channel": "A",
                "official_domain": "example.org", "official_opportunities_url": "https://example.org/listing",
                "discovery_method": "html", "status": status, "priority": "high", "source_type": "Official",
                "languages": ["en"], "verified_on": "2026-11-17", "verification_note": "test", "harvest": {}}
        base.update(extra)
        return base

    def put_registry(self, *sources):
        L.save(S.REGISTRY, {"schema_version": 1, "updated": "", "sources": list(sources)})

    def state(self):
        return L.load(S.STATE, {"sources": {}})["sources"]

    def test_an_active_source_makes_leads_from_its_own_domain_only(self):
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source())
        _h, _r, new, summary = self.run_harvest()
        lead, = self.leads()
        self.assertEqual(new, 1)
        self.assertEqual(lead["url"], "https://example.org/opportunities/young-leaders-fellowship-2027")
        self.assertEqual(lead["source_tier"], 1)
        self.assertTrue(lead["source"].startswith("Example Org"))
        self.assertEqual(summary["sources"]["scanned"], 1)
        self.assertEqual(summary["sources"]["new_leads"], 1)

    def test_a_proposed_source_is_measured_but_stores_no_lead(self):
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source(status="proposed"))
        self.run_harvest()
        self.assertEqual(self.leads(), [])
        entry = self.state()["src-one"]
        self.assertEqual((entry["trial_scans"], entry["trial_would_be_leads"]), (1, 1))
        self.assertEqual(self.audit(), [])

    def test_manual_and_disabled_sources_are_never_fetched(self):
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source("m", status="manual"), self.source("d", status="disabled"))
        _h, _r, _n, summary = self.run_harvest()
        self.assertEqual(summary["sources"]["scanned"], 0)
        self.assertFalse([c for c in self.calls if "example.org" in c])
        self.assertFalse(self.state_path.exists())

    def test_a_source_is_scanned_again_only_when_due(self):
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source(priority="medium"))
        self.run_harvest()
        self.assertEqual(self.state()["src-one"]["next_check"], "2026-11-20")
        _h, _r, _n, again = self.run_harvest()
        self.assertEqual(again["sources"]["scanned"], 0)

    def test_a_failing_source_is_retried_the_next_day_and_reported(self):
        self.pages["https://example.org/listing"] = (503, b"")
        self.put_registry(self.source(priority="low"))
        _h, _r, _n, summary = self.run_harvest()
        entry = self.state()["src-one"]
        self.assertEqual((entry["fail_streak"], entry["next_check"]), (1, "2026-11-18"))
        self.assertEqual(summary["sources"]["failed"], ["src-one"])

    def test_robots_disallow_means_the_page_is_not_fetched(self):
        self.pages["https://example.org/robots.txt"] = (200, b"User-agent: *\nDisallow: /listing\n")
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source())
        _h, _r, new, summary = self.run_harvest()
        self.assertEqual(new, 0)
        row, = summary["sources"]["rows"]
        self.assertEqual(row["http"], -1)
        self.assertIn("robots", row["note"])

    def test_one_broken_source_does_not_stop_the_others(self):
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source("bad", official_opportunities_url="https://example.org/missing"),
                          self.source("good"))
        _h, _r, new, _s = self.run_harvest()
        self.assertEqual(new, 1)

    def test_state_is_not_written_into_the_registry(self):
        self.pages["https://example.org/listing"] = (200, LISTING)
        self.put_registry(self.source())
        before = self.registry_path.read_text(encoding="utf-8")
        self.run_harvest()
        self.assertEqual(self.registry_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
