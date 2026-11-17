"""Tests of the source scanners and of the real source registry. No network.

`oplib.fetch` is replaced by canned pages. The registry tests read the real data/source-registry.json
(read-only): they guard its structure, not its content.
"""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import oplib as L  # noqa: E402
import sourcelib as S  # noqa: E402

TODAY = dt.date(2026, 11, 17)

PAGE = b"""<html><head><script>var a = '<a href="/trap">Trap link inside a script tag text</a>';</script></head><body>
<a href="/en/announcement/call-applications-ean-fellowship-programme">Call for Applications: Enterprise Africa Network Fellowship</a>
<a href="/en/announcements/20261105/call-papers-au-echo">Call for papers: AU Echo 2026 edition on water sustainability</a>
<a href="/en/pressreleases/20261117/chairperson-received-letters">AUC Chairperson received Letters of Credence of the WFP Representative</a>
<a href="/contact">Contact</a>
<a href="mailto:press@au.int">Write to the press office at the commission today</a>
<a href="https://other.example/scholarship-2027">Scholarship 2027 offered by another organisation entirely</a>
<a href="https://sub.au.int/en/announcement/youth-forum">Youth forum registration is open for young people</a>
<a href="/en/announcement/call-applications-ean-fellowship-programme#top">Call for Applications: Enterprise Africa Network Fellowship programme cohort</a>
<a href="/img" title="Apply now to the continental youth volunteer corps"><img src="x.png"></a>
</body></html>"""

SPEC = {"scan_url": "https://au.int/en/announcements", "discovery_method": "html", "official_domain": "au.int"}


class HtmlLinks(unittest.TestCase):
    def links(self, **spec):
        return S.parse_html_links(PAGE, "https://au.int/en/announcements", {**SPEC, **spec})

    def test_relative_links_are_resolved_and_other_domains_dropped(self):
        urls = [i["url"] for i in self.links()]
        self.assertIn("https://au.int/en/announcement/call-applications-ean-fellowship-programme", urls)
        self.assertFalse([u for u in urls if "other.example" in u])

    def test_subdomains_of_the_official_domain_are_allowed(self):
        self.assertTrue([i for i in self.links() if i["url"].startswith("https://sub.au.int/")])

    def test_extra_domains_are_opt_in(self):
        urls = [i["url"] for i in self.links(extra_domains=["other.example"])]
        self.assertTrue([u for u in urls if "other.example" in u])

    def test_scripts_mailto_and_short_navigation_text_are_ignored(self):
        titles = " ".join(i["title"] for i in self.links())
        self.assertNotIn("Trap link", titles)
        self.assertNotIn("press office", titles)
        self.assertNotIn("Contact", titles)

    def test_the_same_page_with_a_fragment_is_one_item_with_the_longest_title(self):
        items = [i for i in self.links() if "call-applications-ean" in i["url"]]
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["title"].endswith("cohort"))

    def test_title_attribute_is_used_when_the_text_is_empty(self):
        titles = [i["title"] for i in self.links()]
        self.assertIn("Apply now to the continental youth volunteer corps", titles)

    def test_include_and_exclude_filters(self):
        only = self.links(link_include="/announcements?/")
        self.assertTrue(only and all("/announcement" in i["url"] for i in only))
        none_press = self.links(link_exclude="pressreleases")
        self.assertFalse([i for i in none_press if "pressreleases" in i["url"]])

    def test_a_date_can_be_read_from_the_url(self):
        spec = {"url_date_regex": r"/(20\d{2})(\d{2})(\d{2})/"}
        dated = {i["url"]: i["published"] for i in self.links(**spec)}
        self.assertEqual(dated["https://au.int/en/announcements/20261105/call-papers-au-echo"], "2026-11-05")
        self.assertEqual(dated["https://au.int/en/announcement/call-applications-ean-fellowship-programme"], "")

    def test_an_impossible_date_in_the_url_is_ignored(self):
        self.assertEqual(S.date_from_url("https://x.org/20261399/a", {"url_date_regex": r"/(20\d{2})(\d{2})(\d{2})/"}), "")

    def test_max_items_caps_the_result(self):
        self.assertEqual(len(self.links(max_items=2)), 2)


class Sitemaps(unittest.TestCase):
    SITEMAP = b"""<urlset>
<url><loc>https://x.org/calls/young-researchers-fellowship-2027</loc><lastmod>2026-11-10T08:00:00Z</lastmod></url>
<url><loc>https://x.org/calls/12345</loc><lastmod>2026-11-12</lastmod></url>
<url><loc>https://x.org/about/our-history-and-mission</loc><lastmod>2026-01-01</lastmod></url>
<url><loc>https://x.org/calls/summer-school-application</loc></url>
</urlset>"""

    def test_titles_come_from_slugs_and_numeric_slugs_are_dropped(self):
        items, children = S.parse_sitemap(self.SITEMAP, {"url_include": "/calls/"})
        self.assertEqual(children, [])
        self.assertEqual([i["title"] for i in items], ["Young researchers fellowship 2027", "Summer school application"])

    def test_newest_first_and_lastmod_is_a_date(self):
        items, _ = S.parse_sitemap(self.SITEMAP, {"url_include": "/calls/"})
        self.assertEqual(items[0]["published"], "2026-11-10")

    def test_an_index_returns_its_children(self):
        index = b"<sitemapindex><sitemap><loc>https://x.org/s1.xml</loc></sitemap><sitemap><loc>https://x.org/s2.xml</loc></sitemap></sitemapindex>"
        items, children = S.parse_sitemap(index, {})
        self.assertEqual((items, children), ([], ["https://x.org/s1.xml", "https://x.org/s2.xml"]))


class JsonApi(unittest.TestCase):
    DATA = json.dumps({"data": {"rows": [
        {"name": "Open call for fellows 2027", "link": "/calls/1", "posted": "2026-11-09T10:00:00Z"},
        {"name": "No link here"}, {"name": 5, "link": "/x"}]}}).encode()

    def test_dotted_paths_map_the_fields(self):
        spec = {"items_path": "data.rows", "title_key": "name", "url_key": "link", "date_key": "posted",
                "url_prefix": "https://x.org/"}
        self.assertEqual(S.parse_json(self.DATA, spec), [
            {"title": "Open call for fellows 2027", "url": "https://x.org/calls/1", "published": "2026-11-09"}])

    def test_bad_json_or_wrong_path_gives_nothing(self):
        self.assertEqual(S.parse_json(b"<html>", {}), [])
        self.assertEqual(S.parse_json(self.DATA, {"items_path": "data.missing"}), [])


class Robots(unittest.TestCase):
    def setUp(self):
        S._ROBOTS.clear()
        self.addCleanup(S._ROBOTS.clear)
        self.calls = []

    def serve(self, robots_status, robots_body=b"", page=b"<a href='/a/long-opportunity-title-2027'>A long opportunity title 2027</a>"):
        def fetch(url, timeout=25, accept=None):
            self.calls.append(url)
            if url.endswith("/robots.txt"):
                return robots_status, url, robots_body
            return 200, url, page
        patcher = mock.patch.object(L, "fetch", fetch)
        patcher.start()
        self.addCleanup(patcher.stop)

    def scan(self):
        return S.scan({"scan_url": "https://x.org/a", "discovery_method": "html", "official_domain": "x.org"})

    def test_disallowed_path_is_not_fetched(self):
        self.serve(200, b"User-agent: *\nDisallow: /a\n")
        result = self.scan()
        self.assertEqual((result.status, result.items), (-1, []))
        self.assertNotIn("https://x.org/a", self.calls)

    def test_other_paths_stay_allowed(self):
        self.serve(200, b"User-agent: *\nDisallow: /private\n")
        self.assertEqual(self.scan().status, 200)

    def test_missing_robots_file_means_no_restriction(self):
        self.serve(404)
        self.assertEqual(self.scan().status, 200)

    def test_unreachable_robots_file_means_do_not_crawl_this_run(self):
        self.serve(503)
        result = self.scan()
        self.assertEqual(result.status, -1)
        self.assertIn("unreachable", result.note)

    def test_robots_is_fetched_once_per_host(self):
        self.serve(404)
        self.scan()
        self.scan()
        self.assertEqual(sum(c.endswith("/robots.txt") for c in self.calls), 1)

    def test_feeds_do_not_need_robots(self):
        self.serve(200, b"User-agent: *\nDisallow: /\n", page=b"<rss><channel><item><title>T</title><link>https://x.org/1</link></item></channel></rss>")
        result = S.scan({"scan_url": "https://x.org/feed", "discovery_method": "rss"})
        self.assertEqual((result.status, len(result.items)), (200, 1))

    def test_unknown_method_is_reported_not_raised(self):
        self.assertEqual(S.scan({"scan_url": "https://x.org/", "discovery_method": "telepathy"}).status, 0)


class State(unittest.TestCase):
    SRC = {"source_id": "s", "priority": "medium"}

    def ok(self, items=3):
        return S.ScanResult(200, [{}] * items, "")

    def test_success_schedules_by_priority(self):
        for priority, days in (("high", 1), ("medium", 3), ("low", 7)):
            entry = S.record_scan({}, {"priority": priority}, self.ok(), 2, TODAY)
            self.assertEqual(entry["next_check"], (TODAY + dt.timedelta(days=days)).isoformat())
            self.assertEqual((entry["fail_streak"], entry["leads_total"]), (0, 2))

    def test_failure_is_retried_tomorrow_and_counted(self):
        entry = S.record_scan({}, {"priority": "low"}, S.ScanResult(503, [], ""), 0, TODAY)
        self.assertEqual((entry["fail_streak"], entry["next_check"]), (1, "2026-11-18"))
        entry = S.record_scan(entry, {"priority": "low"}, S.ScanResult(200, [], ""), 0, TODAY)   # 200 with no items fails too
        self.assertEqual(entry["fail_streak"], 2)
        entry = S.record_scan(entry, {"priority": "low"}, self.ok(), 0, TODAY)
        self.assertEqual(entry["fail_streak"], 0)

    def test_reliability_needs_five_runs_and_uses_the_success_ratio(self):
        entry = {}
        for _ in range(4):
            S.record_scan(entry, self.SRC, self.ok(), 0, TODAY)
        self.assertEqual(entry["reliability"], "UNRATED")
        S.record_scan(entry, self.SRC, self.ok(), 0, TODAY)
        self.assertEqual(entry["reliability"], "HIGH")
        for _ in range(3):                      # 5 of 8 runs worked = 62%
            S.record_scan(entry, self.SRC, S.ScanResult(0, [], ""), 0, TODAY)
        self.assertEqual(entry["reliability"], "MEDIUM")
        for _ in range(4):                      # 5 of 12 = 42%
            S.record_scan(entry, self.SRC, S.ScanResult(0, [], ""), 0, TODAY)
        self.assertEqual(entry["reliability"], "LOW")

    def test_counters_are_a_rolling_window(self):
        entry = {}
        for _ in range(61):
            S.record_scan(entry, self.SRC, self.ok(), 0, TODAY)
        self.assertLessEqual(entry["total_runs"], 60)
        self.assertEqual(entry["ok_runs"], entry["total_runs"])      # all runs were successes, so the ratio survives halving

    def test_is_due(self):
        src = {"source_id": "s", "status": "active"}
        self.assertTrue(S.is_due(src, {}, TODAY))
        self.assertTrue(S.is_due(src, {"s": {"next_check": "2026-11-17"}}, TODAY))
        self.assertFalse(S.is_due(src, {"s": {"next_check": "2026-11-18"}}, TODAY))
        for status in ("manual", "disabled"):
            self.assertFalse(S.is_due({**src, "status": status}, {}, TODAY))


class RegistryFile(unittest.TestCase):
    """Guards on the real registry. They check structure and honesty, not which sources are listed."""

    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "data" / "source-registry.json").read_text(encoding="utf-8"))
        cls.sources = cls.registry["sources"]

    def test_the_registry_is_structurally_valid(self):
        self.assertEqual(S.validate_registry(self.registry, dt.date.today()), [])

    def test_there_are_enough_sources_and_every_channel_is_covered(self):
        self.assertGreaterEqual(len(self.sources), 20)
        self.assertEqual({s["channel"] for s in self.sources}, set(S.CHANNELS))

    def test_active_sources_were_verified_and_blocked_ones_are_never_scanned(self):
        for src in self.sources:
            if src["status"] in ("active", "proposed"):
                self.assertTrue(src["verification_note"].startswith("HTTP 200"), src["source_id"])
            if src["status"] == "manual":
                self.assertFalse(S.is_due(src, {}, TODAY), src["source_id"])

    def test_every_entry_has_a_plain_https_url_without_credentials(self):
        for src in self.sources:
            url = src["official_opportunities_url"]
            self.assertTrue(url.startswith("https://") and "@" not in url, src["source_id"])

    def test_the_validator_catches_the_mistakes_it_exists_for(self):
        good = self.sources[0]
        cases = {
            "duplicate": [good, dict(good)],
            "not on official_domain": [{**good, "official_opportunities_url": "https://evil.example/x"}],
            "must be https": [{**good, "official_opportunities_url": "http://" + good["official_domain"] + "/x"}],
            "not one of": [{**good, "status": "maybe"}],
            "aggregators belong": [{**good, "source_type": "Aggregator"}],
            "valid regex": [{**good, "harvest": {"link_include": "([unclosed"}}],
            "unknown harvest option": [{**good, "harvest": {"magic": 1}}],
            "missing verification_note": [{k: v for k, v in good.items() if k != "verification_note"}],
        }
        for needle, sources in cases.items():
            errors = S.validate_registry({"sources": sources})
            self.assertTrue(any(needle in e for e in errors), (needle, errors))

    def test_a_rejected_domain_cannot_be_registered(self):
        rejected = [{"domain": "x.org", "rejected_on": "2026-11-17", "reason": "compromised"}]
        src = {**self.sources[0], "official_domain": "x.org", "official_opportunities_url": "https://x.org/a"}
        errors = S.validate_registry({"sources": [src], "rejected": rejected})
        self.assertTrue(any("rejected list" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
