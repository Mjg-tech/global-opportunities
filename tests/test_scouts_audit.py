"""Tests of the weekly planner (scripts/scouts.py) and the monthly audit (scripts/audit.py). No network."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit as A  # noqa: E402
import scouts as SC  # noqa: E402

TODAY = dt.date(2026, 11, 17)


def source(sid, channel, status="active", org="Org"):
    return {"source_id": sid, "organization": f"{org} {sid}", "label": "listing", "channel": channel,
            "official_domain": "example.org", "official_opportunities_url": f"https://example.org/{sid}",
            "discovery_method": "html", "status": status, "priority": "high", "source_type": "Official",
            "languages": ["en"], "verification_note": "HTTP 200"}


def lead(lid, title, score=50, status="NEW", source_name="Some aggregator"):
    return {"id": lid, "title": title, "url": f"https://x.example/{lid}", "score": score, "status": status,
            "source": source_name, "flags": [], "first_seen": "2026-11-10", "published": "2026-11-10"}


class Channels(unittest.TestCase):
    def test_keyword_guess_divides_aggregator_leads(self):
        cases = {"Global Youth Summit 2027 fully funded": "E", "Startup accelerator for young founders": "D",
                 "Chevening scholarships 2027": "B", "Master's scholarship at a European university": "C",
                 "Young Africa programme call": "A"}
        for title, channel in cases.items():
            self.assertEqual(SC.guess_channel(title), channel, title)

    def test_a_registry_source_decides_the_channel_before_keywords(self):
        reg = {"sources": [source("s1", "B", org="Embassy")]}
        names = {SC.S.spec_of(s)["name"]: s["channel"] for s in reg["sources"]}
        item = lead("a", "Summit for young leaders", source_name=SC.S.spec_of(reg["sources"][0])["name"])
        self.assertEqual(SC.lead_channel(item, names), "B")
        self.assertEqual(SC.lead_channel(lead("b", "Summit for young leaders"), names), "E")

    def test_intake_year_rolls_over_in_the_second_half_of_the_year(self):
        self.assertEqual(SC.intake_year(dt.date(2026, 3, 1)), 2026)
        self.assertEqual(SC.intake_year(dt.date(2026, 7, 1)), 2027)


class Queries(unittest.TestCase):
    BANK = json.loads((ROOT / "data" / "scout-queries.json").read_text(encoding="utf-8"))

    def test_the_real_bank_covers_every_channel_and_language(self):
        for channel in SC.CHANNEL_INFO:
            for lang in self.BANK["languages"]:
                self.assertTrue(self.BANK["channels"][channel][lang], (channel, lang))

    def test_picks_are_deterministic_per_week_and_rotate_between_weeks(self):
        week1 = SC.pick_queries(self.BANK, "E", TODAY)
        self.assertEqual(week1, SC.pick_queries(self.BANK, "E", TODAY))
        self.assertNotEqual(week1, SC.pick_queries(self.BANK, "E", TODAY + dt.timedelta(days=7)))

    def test_every_language_is_represented_and_the_year_is_filled_in(self):
        picks = SC.pick_queries(self.BANK, "C", TODAY)
        self.assertEqual({p["lang"] for p in picks}, {"en", "fr", "pt", "es"})
        self.assertTrue(all("{year" not in p["q"] for p in picks))
        self.assertTrue(any("2027" in p["q"] for p in picks))

    def test_no_phrase_carries_personal_data(self):
        text = json.dumps(self.BANK).lower()
        for banned in ("@", "mukubwa", "gmail", "passport"):
            self.assertNotIn(banned, text)


class Plan(unittest.TestCase):
    def build(self, leads, sources=None, records=None, meta=None, per=2):
        registry = {"sources": sources or []}
        return SC.build_plan(TODAY, registry, {"sources": {}}, leads, [], records or [], meta or {}, Queries.BANK, per)

    def test_each_channel_gets_at_most_its_share_of_the_best_leads(self):
        leads = [lead(f"e{i}", f"Youth summit {i}", score=40 + i) for i in range(5)]
        plan = self.build(leads, per=2)
        got = [x["id"] for x in plan["channels"]["E"]["leads"]]
        self.assertEqual(got, ["e4", "e3"])

    def test_under_review_leads_come_first_and_finished_ones_are_left_out(self):
        leads = [lead("hi", "Youth summit A", score=90), lead("held", "Youth summit B", score=10, status="UNDER REVIEW"),
                 lead("done", "Youth summit C", score=95, status="PUBLISHED"),
                 lead("no", "Youth summit D", score=95, status="EXCLUDED - CONFIRMED INELIGIBLE")]
        got = [x["id"] for x in self.build(leads, per=5)["channels"]["E"]["leads"]]
        self.assertEqual(got, ["held", "hi"])

    def test_a_lead_written_before_step_one_is_planned_as_new(self):
        legacy = {"id": "old", "title": "Summit fellowship 2027", "url": "https://x.example/old",
                  "source": "Feed", "source_tier": 3, "published": "2026-11-12", "first_seen": "2026-11-12",
                  "status": "NEEDS VERIFICATION"}
        plan = self.build([legacy])
        planned = [x for ch in plan["channels"].values() for x in ch["leads"]]
        self.assertEqual([x["id"] for x in planned], ["old"])
        self.assertEqual(planned[0]["status"], "NEW")

    def test_a_lead_is_planned_once(self):
        leads = [lead(f"l{i}", t) for i, t in enumerate(["Summit 2027", "Scholarship 2027", "Startup grant 2027", "Embassy award 2027"])]
        planned = [x["id"] for ch in self.build(leads, per=9)["channels"].values() for x in ch["leads"]]
        self.assertEqual(sorted(planned), sorted(x["id"] for x in leads))

    def test_manual_sources_are_listed_to_open_in_a_browser(self):
        plan = self.build([], sources=[source("a1", "A"), source("a2", "A", status="manual")])
        self.assertEqual(plan["channels"]["A"]["open_in_browser"], ["https://example.org/a2"])
        self.assertEqual(len(plan["channels"]["A"]["sources"]), 2)

    def test_the_orchestrator_gets_flagged_and_closing_records(self):
        closing = {"id": "soon", "application_deadline": "2026-12-01"}
        far = {"id": "far", "application_deadline": "2027-09-01"}
        plan = self.build([], records=[closing, far], meta={"flags": [{"id": "dead"}], "reseen": [{"id": "again"}]})
        orch = plan["orchestrator"]
        self.assertEqual((orch["reverify_flagged"], orch["reverify_closing_30_days"], orch["seen_again"]),
                         (["dead"], ["soon"], ["again"]))


class AuditSample(unittest.TestCase):
    AUDIT = {"entries": [
        {"id": f"r{i}", "date": "2026-11-10", "reason": "no_opportunity_word", "title": f"Title {i}", "url": f"https://x/{i}"}
        for i in range(10)] + [
        {"id": "n1", "date": "2026-11-11", "reason": "not_opportunity", "title": "Job ad", "url": "https://x/n1"},
        {"id": "old", "date": "2026-08-01", "reason": "not_opportunity", "title": "Too old", "url": "https://x/old"}]}
    ARCHIVE = {"leads": [
        {"id": "a1", "title": "Aged", "url": "https://x/a1", "archived_on": "2026-11-12", "status_before_archive": "NEW",
         "archive_reason": "not reviewed within 45 days", "score": 60},
        {"id": "a2", "title": "Published", "url": "https://x/a2", "archived_on": "2026-11-12", "status": "PUBLISHED",
         "archive_reason": "now a record in the database"},
        {"id": "a3", "title": "Capped", "url": "https://x/a3", "archived_on": "2026-11-12", "status_before_archive": "NEW",
         "archive_reason": "below the cap of 1500 active leads"}]}

    def test_population_covers_unreviewed_losses_only_inside_the_window(self):
        strata = A.population(self.AUDIT, self.ARCHIVE, TODAY)
        self.assertEqual({k: len(v) for k, v in strata.items()},
                         {"rejected:no_opportunity_word": 10, "rejected:not_opportunity": 1, "aged-out": 2})

    def test_the_sample_is_reproducible_stratified_and_capped(self):
        strata = A.population(self.AUDIT, self.ARCHIVE, TODAY)
        first = A.draw(strata, "2026-11", 6)
        self.assertEqual(first, A.draw(strata, "2026-11", 6))
        self.assertLessEqual(len(first), 6)
        self.assertEqual({i["stratum"] for i in first}, set(strata))
        self.assertNotEqual([i["id"] for i in first], [i["id"] for i in A.draw(strata, "2026-12", 6)])

    def test_an_empty_population_gives_an_empty_sample(self):
        self.assertEqual(A.draw({}, "2026-11", 10), [])


class AuditSummary(unittest.TestCase):
    SAMPLE = {"population": {"rejected:no_opportunity_word": 100, "aged-out": 40},
              "items": [{"id": f"r{i}", "title": f"T{i}", "url": f"https://x/{i}", "stratum": "rejected:no_opportunity_word"} for i in range(4)]
                       + [{"id": f"a{i}", "title": f"A{i}", "url": f"https://x/a{i}", "stratum": "aged-out"} for i in range(2)]}

    def test_rates_and_estimates_per_stratum(self):
        verdicts = {"items": [{"id": "r0", "verdict": "FALSE_EXCLUSION", "note": "real fellowship"},
                              {"id": "r1", "verdict": "CORRECT"}, {"id": "r2", "verdict": "CORRECT"},
                              {"id": "r3", "verdict": "UNCLEAR"}, {"id": "a0", "verdict": "CORRECT"}]}
        result = A.summarize(self.SAMPLE, verdicts)
        row = result["strata"]["rejected:no_opportunity_word"]
        self.assertEqual((row["judged"], row["false"], row["unclear"]), (4, 1, 1))
        self.assertEqual(row["rate"], 0.333)                    # unclear items are left out of the rate
        self.assertEqual(row["estimated_missed"], 33)
        self.assertEqual(result["alert"], ["rejected:no_opportunity_word"])
        self.assertEqual([m["id"] for m in result["false_exclusions"]], ["r0"])
        self.assertEqual(result["unjudged"], ["a1"])

    def test_a_stratum_with_no_verdict_has_no_rate(self):
        row = A.summarize(self.SAMPLE, {"items": []})["strata"]["aged-out"]
        self.assertIsNone(row["rate"])

    def test_a_verdict_outside_the_vocabulary_is_ignored(self):
        result = A.summarize(self.SAMPLE, {"items": [{"id": "r0", "verdict": "MAYBE"}]})
        self.assertEqual(result["strata"]["rejected:no_opportunity_word"]["judged"], 0)


class SourceReview(unittest.TestCase):
    def notes(self, src, st):
        return A.source_review({"sources": [src]}, {"sources": {src["source_id"]: st}})

    def test_failing_and_silent_active_sources_are_reported(self):
        self.assertIn("3 failed scans", self.notes(source("a", "A"), {"fail_streak": 3, "last_http": 503})[0])
        self.assertIn("no lead ever", self.notes(source("a", "A"), {"total_runs": 6, "leads_total": 0})[0])
        self.assertEqual(self.notes(source("a", "A"), {"total_runs": 6, "leads_total": 4}), [])

    def test_a_proposed_source_gets_a_promotion_hint_after_four_trials(self):
        ready = self.notes(source("p", "A", status="proposed"), {"trial_scans": 4, "trial_would_be_leads": 8})
        thin = self.notes(source("p", "A", status="proposed"), {"trial_scans": 4, "trial_would_be_leads": 1})
        self.assertIn("ready to activate", ready[0])
        self.assertIn("too thin", thin[0])
        self.assertEqual(self.notes(source("p", "A", status="proposed"), {"trial_scans": 2, "trial_would_be_leads": 9}), [])


if __name__ == "__main__":
    unittest.main()
