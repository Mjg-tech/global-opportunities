"""Lead-filter tests. Run all tests with:  python -m unittest discover -s tests -v

`leadfilter.assess` decides whether a feed title becomes a lead (with a score and flags) or is
rejected with a reason. Only three things reject a title: it is too old, it is not an opportunity
(job ad, tender, guide), or it has no opportunity word at all. Words that hint at a restricted
audience lower the score and add a flag; they never reject.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import leadfilter as LF  # noqa: E402
import oplib as L  # noqa: E402

TODAY = L.parse_date("2026-11-17")
RULES = LF.load_rules()
BENCH = json.loads((ROOT / "tests" / "benchmark.json").read_text(encoding="utf-8"))


def assess(title, published="", tier=3, feed_filter=""):
    return LF.assess(title, published, tier, feed_filter, TODAY, RULES)


class KeepsWhatItShould(unittest.TestCase):
    def test_plain_scholarship_call_is_a_lead(self):
        self.assertEqual(assess("Chevening Scholarships 2027 for future leaders").kind, "lead")

    def test_french_call_is_a_lead(self):
        self.assertEqual(assess("Appel à candidatures : bourses d'excellence 2027").kind, "lead")

    def test_funded_summit_is_a_lead(self):
        self.assertEqual(assess("Fully funded youth summit 2027 in Nairobi").kind, "lead")

    def test_named_programmes_without_a_generic_word_are_leads(self):
        for title in ("Knight-Hennessy Scholars (2027 cohort)", "Schwarzman Scholars (Class of 2028-2029)",
                      "Mundus MAPP: Erasmus Mundus Master's in Public Policy (2027-2029)",
                      "USTC International Winter Camp 2027", "ALX sponsored tech programmes",
                      "Volontaires unis pour la Francophonie (V-Francophonie)"):
            with self.subTest(title=title):
                self.assertEqual(assess(title).kind, "lead")


class RejectsNonOpportunities(unittest.TestCase):
    def test_every_negative_in_benchmark_is_rejected(self):
        leaked = [n["title"] for n in BENCH["negatives"] if assess(n["title"]).kind == "lead"]
        self.assertEqual(leaked, [], "job ads, news or guides became leads")

    def test_recruitment_ad_is_rejected_with_a_reason(self):
        result = assess("ACME recrute un comptable à Kinshasa, programme de formation inclus")
        self.assertEqual((result.kind, result.reason), ("reject", "not_opportunity"))

    def test_news_without_an_opportunity_word_is_rejected_with_a_reason(self):
        result = assess("Deux nouveaux Etats et gouvernements rejoignent la Francophonie")
        self.assertEqual((result.kind, result.reason), ("reject", "no_opportunity_word"))

    def test_old_items_are_rejected_by_age(self):
        result = assess("Mastercard Foundation Scholarship 2027", "2026-09-01")
        self.assertEqual((result.kind, result.reason), ("reject", "too_old"))

    def test_strict_feed_keeps_only_clear_calls(self):
        self.assertEqual(assess("Clôture du sommet de la Francophonie", feed_filter="strict").kind, "reject")
        self.assertEqual(assess("Appel à candidatures : prix 2027", feed_filter="strict").kind, "lead")

    def test_unfiltered_feed_skips_the_whitelist_but_not_the_job_filter(self):
        self.assertEqual(assess("Refugee-Led Research Hub East Africa", feed_filter="none").kind, "lead")
        self.assertEqual(assess("We are hiring a driver", feed_filter="none").kind, "reject")


class AudienceWordsNeverReject(unittest.TestCase):
    """A title alone does not establish ineligibility. These are real titles from the live feeds."""

    def test_place_name_is_not_an_audience(self):
        result = assess("Arab American Leadership Program 2027 in the USA (AALP)")
        self.assertEqual((result.kind, result.flags), ("lead", []))

    def test_list_that_includes_masters_is_not_phd_only(self):
        result = assess("The Bayer Foundation Scientific Fellowships 2027 for Master, PhD, and Medical Students")
        self.assertEqual((result.kind, result.flags), ("lead", []))

    def test_postgraduates_worldwide_is_not_undergraduate_only(self):
        result = assess("The UNIQLO Global Management Program 2027 for undergraduates and postgraduates worldwide")
        self.assertEqual((result.kind, result.flags), ("lead", []))

    def test_gender_word_is_flagged_but_not_penalised(self):
        # data/profile.json records no gender, so the title cannot rule anything out.
        plain = assess("The WIPO IP Fellowship 2027 for young professionals")
        women = assess("The WIPO IP and Women Fellowship 2027 for young professionals")
        self.assertEqual(women.kind, "lead")
        self.assertEqual(women.score, plain.score)
        self.assertTrue(any(f.startswith("check:gender-term") for f in women.flags))

    def test_institution_names_are_not_audiences(self):
        for title in ("American University in Cairo African Graduate Fellowship (Fall 2027)",
                      "European Forum Alpbach scholarship programme"):
            with self.subTest(title=title):
                self.assertEqual(assess(title).flags, [])

    def test_nationality_only_call_is_kept_but_ranked_last(self):
        nigerian = assess("The Egbin PowerUp Internship Programme 2027 for young Nigerian undergraduate students")
        plain = assess("The Egbin PowerUp Internship Programme 2027 for young graduates")
        self.assertEqual(nigerian.kind, "lead")
        self.assertTrue(any(f.startswith("audience:nationality") for f in nigerian.flags))
        self.assertLess(nigerian.score, plain.score - 30)

    def test_phd_only_call_is_kept_and_ranked_lower(self):
        phd = assess("Mauritius-Africa Scholarship Scheme 2027 (MPhil and PhD in Mauritius)")
        masters = assess("Mauritius-Africa Scholarship Scheme 2027 (Master's and PhD in Mauritius)")
        self.assertEqual(phd.kind, "lead")
        self.assertLess(phd.score, masters.score)

    def test_penalties_are_capped(self):
        worst = assess("Scholarship for Nigerian undergraduate students, application fee required, au Tchad")
        self.assertGreaterEqual(worst.score, RULES["score"]["base"] + RULES["score"]["weak_word"] - 45 - 1)


class Scoring(unittest.TestCase):
    def test_official_feed_outranks_aggregator_for_the_same_title(self):
        self.assertGreater(assess("Fellowship call 2027", tier=1).score, assess("Fellowship call 2027", tier=3).score)

    def test_official_feed_bonus_needs_a_call_in_the_title(self):
        # The strict filter already blocks news from official feeds; with no filter the bonus must not apply.
        plain = assess("Annual report 2027", tier=1, feed_filter="none")
        self.assertEqual(plain.score, RULES["score"]["base"])

    def test_recent_item_gets_a_small_boost(self):
        fresh = assess("Fellowship call 2027", published="2026-11-16")
        older = assess("Fellowship call 2027", published="2026-11-01")
        self.assertEqual(fresh.score - older.score, RULES["score"]["fresh_within_7_days"])

    def test_score_stays_between_0_and_100(self):
        for title in ("Fully funded scholarship Africa", "Scholarship for Nigerian PhD researchers au Tchad fee"):
            self.assertTrue(0 <= assess(title).score <= 100)


class Benchmark(unittest.TestCase):
    """Recall ratchet: the share of known real opportunities that survive the filters."""

    def test_recall_never_drops_below_the_floor(self):
        kept = sum(assess(p["title"]).kind == "lead" for p in BENCH["positives"])
        self.assertGreaterEqual(kept, BENCH["recall_floor"],
                                f"{kept}/{len(BENCH['positives'])} benchmark titles survive; floor {BENCH['recall_floor']}")

    def test_report_current_recall(self):
        total = len(BENCH["positives"])
        kept = sum(assess(p["title"]).kind == "lead" for p in BENCH["positives"])
        print(f"\n   benchmark recall: {kept}/{total} = {100 * kept / total:.1f}% (floor {BENCH['recall_floor']})")


class Migration(unittest.TestCase):
    def test_legacy_lead_gets_new_status_score_and_flags(self):
        old = {"id": "a1", "title": "Fellowship for Nigerian students 2027", "url": "https://example.org/a",
               "source": "X", "source_tier": 3, "first_seen": "2026-11-10", "status": "NEEDS VERIFICATION"}
        out = LF.migrate_lead(dict(old), TODAY, RULES)
        self.assertEqual(out["status"], "NEW")
        self.assertIn("score", out)
        self.assertTrue(out["flags"])
        self.assertEqual({k: out[k] for k in old if k != "status"}, {k: old[k] for k in old if k != "status"})

    def test_migration_is_idempotent_and_keeps_review_status(self):
        lead = {"id": "a2", "title": "Fellowship 2027", "first_seen": "2026-11-10", "status": "UNDER REVIEW",
                "score": 77, "flags": ["x"]}
        self.assertEqual(LF.migrate_lead(dict(lead), TODAY, RULES), dict(lead, last_seen="2026-11-10"))


if __name__ == "__main__":
    unittest.main()
