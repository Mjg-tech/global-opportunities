"""Tests of step 4: evidence files (scripts/evidence.py), cycles (scripts/cycles.py) and how the judge,
upsert, validate and the weekly planner use them. No network: pages are canned."""
import copy
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import cycles as CY  # noqa: E402
import evidence as EV  # noqa: E402
import judge as J  # noqa: E402
import oplib as L  # noqa: E402
import scouts as SC  # noqa: E402
import upsert as U  # noqa: E402
import validate as V  # noqa: E402

TODAY = dt.date(2026, 11, 18)
PAGE = "https://org.example/criteria"
PAGE2 = "https://org.example/benefits"


def crit(criterion="nationality", assessment="MET", **over):
    c = {"criterion": criterion, "requirement": "Citizens of all countries may apply.", "applicant": "Citizen of the DRC.",
         "assessment": assessment, "quote": "Citizens of all countries may apply.", "page": PAGE}
    if assessment == "UNKNOWN":
        c["missing"] = "The exact age."
    c.update(over)
    return c


def pay(item="tuition", arrangement="Paid directly by organiser", **over):
    f = {"item": item, "arrangement": arrangement, "quote": "Tuition is covered by the programme.", "page": PAGE2}
    f.update(over)
    return f


def cycle(label="2026", state="HISTORICAL CYCLE", **over):
    c = {"cycle": label, "state": state, "opens_on": "2026-01-10", "deadline": "2026-02-20",
         "quote": "Applications are open 10 January to 20 February 2026.", "page": PAGE}
    c.update(over)
    return c


def rec(**over):
    r = {"id": "example-2027", "title": "Example 2027", "organization": "Example Org", "eligibility_for_me": "POSSIBLY ELIGIBLE",
         "coverage": {"tuition": "Covered", "flight": "Not specified"}, "funding_type": "Substantially Funded",
         "recurring": True, "application_deadline": "", "last_cycle_deadline": "2026-02-20"}
    r.update(over)
    return r


def rules(findings, severity=None):
    return {f["rule"] for f in findings if severity in (None, f["severity"])}


class TempEvidence(unittest.TestCase):
    """Every test that writes evidence files does so in a throwaway folder."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(EV, "EVIDENCE_DIR", Path(self.tmp.name) / "evidence")
        patcher.start()
        self.addCleanup(patcher.stop)


class Criteria(unittest.TestCase):
    def test_complete_evidence_has_no_block(self):
        ev = {"criteria": [crit(), crit("age", "UNKNOWN", quote="Applicants must be under 30.")]}
        self.assertEqual(rules(EV.check(ev, rec()), "block"), set())

    def test_a_verdict_needs_the_applicant_fact_and_a_missing_fact_needs_a_name(self):
        self.assertIn("evidence-applicant", rules(EV.check({"criteria": [crit(applicant="")]}), "block"))
        self.assertIn("evidence-missing", rules(EV.check({"criteria": [crit("age", "UNKNOWN", missing="")]}), "block"))

    def test_a_requirement_needs_its_sentence_and_page_unless_the_organiser_is_silent(self):
        for bad in (crit(quote=""), crit(quote="too short"), crit(page=""), crit(page="not a url")):
            self.assertTrue({"evidence-quote", "evidence-page"} & rules(EV.check({"criteria": [bad]}), "block"), bad)
        silent = {"criterion": "experience", "requirement": "The call states no experience requirement.", "assessment": "NOT STATED"}
        self.assertEqual(rules(EV.check({"criteria": [silent]}), "block"), set())

    def test_unknown_vocabulary_is_refused(self):
        self.assertIn("evidence-assessment", rules(EV.check({"criteria": [crit(assessment="PROBABLY")]}), "block"))
        self.assertIn("evidence-criterion", rules(EV.check({"criteria": [crit("favourite_colour")]}), "block"))

    def test_an_africa_wide_sentence_does_not_prove_the_drc(self):
        africa = crit(requirement="Applicants from African countries.", quote="Applicants from African countries and the Diaspora.")
        self.assertIn("evidence-nationality-not-drc", rules(EV.check({"criteria": [africa]}), "review"))
        self.assertNotIn("evidence-nationality-not-drc", rules(EV.check({"criteria": [crit()]})))
        named = crit(quote="Nationals of the Democratic Republic of the Congo are eligible.")
        self.assertNotIn("evidence-nationality-not-drc", rules(EV.check({"criteria": [named]})))

    def test_the_shape_and_emptiness_are_checked(self):
        self.assertIn("evidence-empty", rules(EV.check({}), "block"))
        self.assertIn("evidence-shape", rules(EV.check({"criteria": "yes"}), "block"))
        self.assertIn("evidence-shape", rules(EV.check([]), "block"))


class Verdict(unittest.TestCase):
    CASES = [
        (["NOT MET", "MET"], "NOT ELIGIBLE"),
        (["MET", "UNKNOWN"], "POSSIBLY ELIGIBLE"),
        (["UNKNOWN", "UNKNOWN"], "INSUFFICIENT INFORMATION"),
        (["MET", "MET"], "LIKELY ELIGIBLE"),
        (["NOT STATED"], "INSUFFICIENT INFORMATION"),
    ]

    def test_the_ceiling_follows_the_criteria(self):
        for marks, expected in self.CASES:
            rows = [crit("nationality" if i == 0 else "education", m) for i, m in enumerate(marks)]
            self.assertEqual(EV.derive_eligibility(rows), expected, marks)

    def test_likely_needs_the_nationality_rule_read(self):
        no_nationality = [crit("education", "MET"), crit("age", "MET")]
        self.assertEqual(EV.derive_eligibility(no_nationality), "POSSIBLY ELIGIBLE")
        open_to_all = [{"criterion": "nationality", "requirement": "No nationality restriction.", "assessment": "NOT STATED"}, crit("education", "MET")]
        self.assertEqual(EV.derive_eligibility(open_to_all), "LIKELY ELIGIBLE")

    def test_a_record_may_be_lower_than_its_criteria_but_never_higher(self):
        unknown_age = {"criteria": [crit(), crit("age", "UNKNOWN")]}
        self.assertIn("evidence-verdict-too-high", rules(EV.check(unknown_age, rec(eligibility_for_me="LIKELY ELIGIBLE")), "block"))
        self.assertNotIn("evidence-verdict-too-high", rules(EV.check(unknown_age, rec(eligibility_for_me="POSSIBLY ELIGIBLE"))))
        met = {"criteria": [crit(), crit("education", "MET")]}
        self.assertNotIn("evidence-verdict-too-high", rules(EV.check(met, rec(eligibility_for_me="POSSIBLY ELIGIBLE"))))

    def test_one_failed_criterion_forbids_anything_but_not_eligible(self):
        failed = {"criteria": [crit("age", "NOT MET", applicant="Over the limit.")]}
        for verdict in ("LIKELY ELIGIBLE", "POSSIBLY ELIGIBLE", "INSUFFICIENT INFORMATION"):
            self.assertIn("evidence-verdict-too-high", rules(EV.check(failed, rec(eligibility_for_me=verdict)), "block"), verdict)
        self.assertEqual(rules(EV.check(failed, rec(eligibility_for_me="NOT ELIGIBLE")), "block"), set())


class Funding(unittest.TestCase):
    def test_an_amount_needs_a_currency_and_a_payer(self):
        self.assertIn("evidence-currency", rules(EV.check({"funding": [pay("daily_allowance", amount="9500")]}), "block"))
        ok = pay("daily_allowance", "Covered through an allowance", amount="9500", currency="TL")
        self.assertEqual(rules(EV.check({"funding": [ok]}, rec(coverage={"stipend": "Covered"})), "block"), set())
        unsupported = {"item": "meals", "arrangement": "Unknown", "amount": "10", "currency": "USD"}
        self.assertIn("evidence-amount-unsupported", rules(EV.check({"funding": [unsupported]}), "block"))

    def test_the_record_may_not_claim_more_than_the_evidence_supports(self):
        unknown_flight = {"item": "airfare", "arrangement": "Unknown"}
        self.assertIn("evidence-coverage-conflict", rules(EV.check({"funding": [unknown_flight]}, rec(coverage={"flight": "Covered"})), "block"))
        self.assertIn("evidence-coverage-conflict",
                      rules(EV.check({"funding": [pay("airfare", "Partially covered")]}, rec(coverage={"flight": "Covered"})), "block"))
        not_paid = pay("airfare", "Not covered")
        self.assertIn("evidence-coverage-conflict", rules(EV.check({"funding": [not_paid]}, rec(coverage={"flight": "Partially covered"})), "block"))

    def test_the_record_may_say_less_than_the_evidence(self):
        paid = pay("airfare")
        self.assertNotIn("evidence-coverage-conflict", rules(EV.check({"funding": [paid]}, rec(coverage={"flight": "Not specified"}))))

    def test_online_programmes_keep_their_not_applicable(self):
        self.assertNotIn("evidence-coverage-conflict",
                         rules(EV.check({"funding": [{"item": "airfare", "arrangement": "Unknown"}]}, rec(coverage={"flight": "Not applicable"}))))

    def test_fully_funded_needs_one_paid_line_with_a_quote(self):
        nothing_paid = {"funding": [{"item": "meals", "arrangement": "Unknown"}]}
        self.assertIn("evidence-fully-funded-unproven", rules(EV.check(nothing_paid, rec(funding_type="Fully Funded")), "review"))
        self.assertNotIn("evidence-fully-funded-unproven", rules(EV.check({"funding": [pay()]}, rec(funding_type="Fully Funded"))))

    def test_an_item_is_listed_once_and_from_the_vocabulary(self):
        self.assertIn("evidence-funding-duplicate", rules(EV.check({"funding": [pay(), pay()]}), "block"))
        self.assertIn("evidence-funding-item", rules(EV.check({"funding": [pay("yacht")]}), "block"))
        self.assertIn("evidence-arrangement", rules(EV.check({"funding": [pay(arrangement="Maybe")]}), "block"))

    def test_out_of_pocket_may_not_be_blank(self):
        self.assertIn("evidence-out-of-pocket", rules(EV.check({"funding": [pay()], "out_of_pocket": " "}), "block"))
        self.assertEqual(rules(EV.check({"funding": [pay()], "out_of_pocket": "Unknown"}), "block"), set())


class Cycles(unittest.TestCase):
    def test_a_history_needs_a_page_and_a_sentence(self):
        self.assertIn("evidence-cycle-unproven", rules(EV.check({"cycles": [cycle(quote="")]}), "block"))
        self.assertEqual(rules(EV.check({"cycles": [cycle()]}), "block"), set())

    def test_a_prediction_never_carries_a_date_the_organiser_did_not_state(self):
        expected = {"cycle": "2027", "state": "EXPECTED NEXT CYCLE", "basis": "pattern", "window_text": "around February"}
        self.assertEqual(rules(EV.check({"cycles": [expected]}), "block"), set())
        self.assertIn("evidence-cycle-predicted-date", rules(EV.check({"cycles": [dict(expected, deadline="2027-02-20")]}), "block"))
        self.assertIn("evidence-cycle-basis", rules(EV.check({"cycles": [dict(expected, basis="hunch")]}), "block"))
        self.assertIn("evidence-cycle-unproven", rules(EV.check({"cycles": [dict(expected, basis="organiser states")]}), "block"))

    def test_a_past_cycle_cannot_end_in_the_future_and_labels_are_unique(self):
        self.assertIn("evidence-cycle-historical-future", rules(EV.check({"cycles": [cycle(deadline="2999-01-01")]}), "block"))
        self.assertIn("evidence-cycle-duplicate", rules(EV.check({"cycles": [cycle(), cycle()]}), "block"))
        self.assertIn("evidence-cycle-date", rules(EV.check({"cycles": [cycle(deadline="20/02/2026")]}), "block"))


class Storing(TempEvidence):
    def test_the_file_is_written_and_changes_are_logged(self):
        changes = []
        EV.store("example-2027", {"criteria": [crit()], "funding": [pay()], "cycles": [cycle()]}, TODAY, changes, "Example")
        stored = EV.load("example-2027")
        self.assertEqual((stored["id"], stored["checked_on"]), ("example-2027", "2026-11-18"))
        self.assertEqual({c["field"] for c in changes},
                         {"evidence:nationality", "evidence:funding:tuition", "evidence:cycle:2026"})

    def test_a_later_patch_keeps_what_it_does_not_mention_and_accumulates_cycles(self):
        EV.store("example-2027", {"criteria": [crit()], "cycles": [cycle("2026")]}, TODAY, [])
        later = dt.date(2027, 11, 20)
        EV.store("example-2027", {"cycles": [cycle("2027", opens_on="2027-01-10", deadline="2027-02-19")]}, later, [])
        stored = EV.load("example-2027")
        self.assertEqual([c["cycle"] for c in stored["cycles"]], ["2026", "2027"])
        self.assertEqual(len(stored["criteria"]), 1)
        self.assertEqual(stored["checked_on"], "2027-11-20")

    def test_a_changed_assessment_is_logged_with_old_and_new(self):
        EV.store("example-2027", {"criteria": [crit("age", "UNKNOWN")]}, TODAY, [])
        changes = []
        EV.store("example-2027", {"criteria": [crit("age", "NOT MET", applicant="Over the limit.")]}, TODAY, changes)
        self.assertEqual([(c["field"], c["old"], c["new"]) for c in changes], [("evidence:age", "UNKNOWN", "NOT MET")])

    def test_unchanged_evidence_logs_nothing(self):
        EV.store("example-2027", {"criteria": [crit()]}, TODAY, [])
        changes = []
        EV.store("example-2027", {"criteria": [crit()]}, TODAY, changes)
        self.assertEqual(changes, [])


class UpsertMovesEvidence(TempEvidence):
    def test_the_record_never_carries_its_evidence(self):
        db, log = Path(self.tmp.name) / "db.json", Path(self.tmp.name) / "changelog.json"
        batch = Path(self.tmp.name) / "batch.json"
        record = {"id": "example-2027", "title": "Example 2027", "organization": "Example Org",
                  "evidence": {"criteria": [crit()], "cycles": [cycle()]}}
        batch.write_text(json.dumps([record]), encoding="utf-8")
        with mock.patch.object(L, "DB", db), mock.patch.object(L, "CHANGELOG", log):
            U.main([str(batch)])
            U.main([str(batch)])                                  # twice: still one record, still one file
        stored = json.loads(db.read_text(encoding="utf-8"))["opportunities"]
        self.assertEqual(len(stored), 1)
        self.assertNotIn("evidence", stored[0])
        self.assertEqual(EV.load("example-2027")["criteria"][0]["assessment"], "MET")
        self.assertEqual(len(json.loads(log.read_text(encoding="utf-8"))["entries"]), 3)   # new record + 2 evidence lines, once

    def test_validate_refuses_an_evidence_key_inside_a_record(self):
        errors, warnings = [], []
        full = L.normalize({"id": "example-2027", "title": "T", "organization": "O", "overview": "x", "eligibility_reason": "y",
                            "last_verified": "2026-11-18", "date_discovered": "2026-11-18", "source_url": PAGE,
                            "category": ["Scholarship"], "evidence": {"criteria": [crit()]}}, TODAY)
        V.check_record(full, errors, warnings)
        self.assertTrue(any("evidence" in e for e in errors), errors)


class JudgeGate(TempEvidence):
    SOURCES = [{"label": "Criteria", "url": PAGE, "type": "Official"}, {"label": "Benefits", "url": PAGE2, "type": "Official"}]

    def base(self, **over):
        r = {"id": "example-2027", "title": "Example 2027", "organization": "Example Org", "overview": "A funded programme.",
             "category": ["Fellowship"], "funding_type": "Partially Funded", "coverage": {"tuition": "Covered"},
             "application_deadline": "2027-01-31", "deadline_text": "Closes 31 January 2027.",
             "official_information_url": PAGE, "source_url": PAGE, "sources": self.SOURCES, "source_type": "Official",
             "source_confidence": "HIGH", "verification": "VERIFIED", "eligibility_for_me": "POSSIBLY ELIGIBLE",
             "eligibility_reason": "Open to all nationalities; the age limit is not recorded.",
             "nationality_requirements": "Citizens of all countries", "last_verified": "2026-11-18",
             "date_discovered": "2026-11-18", "match_keywords": ["example"], "action": "Read the page."}
        r.update(over)
        return r

    def check(self, record, existing=None):
        merged, _ = J.merge_like_upsert(record, [existing] if existing else [], TODAY)
        return J.check_record(merged, existing, TODAY, J.aggregator_hosts())

    def test_a_record_with_good_evidence_passes_the_rules(self):
        record = self.base(evidence={"criteria": [crit(), crit("age", "UNKNOWN")], "funding": [pay()]})
        self.assertEqual(rules(self.check(record), "block"), set())

    def test_a_verdict_above_the_criteria_is_blocked(self):
        record = self.base(eligibility_for_me="LIKELY ELIGIBLE", evidence={"criteria": [crit(), crit("age", "UNKNOWN")]})
        self.assertIn("evidence-verdict-too-high", rules(self.check(record), "block"))

    def test_stored_criteria_cap_a_later_patch_that_carries_no_evidence(self):
        EV.store("example-2027", {"criteria": [crit(), crit("age", "NOT MET", applicant="Over the limit.")]}, TODAY, [])
        existing = self.base(eligibility_for_me="NOT ELIGIBLE")
        patch = {"id": "example-2027", "eligibility_for_me": "LIKELY ELIGIBLE"}
        self.assertIn("evidence-verdict-too-high", rules(self.check(patch, existing), "block"))

    def test_stored_funding_evidence_blocks_a_stronger_coverage_claim(self):
        EV.store("example-2027", {"funding": [{"item": "airfare", "arrangement": "Not covered"}]}, TODAY, [])
        existing = self.base(coverage={"flight": "Not covered"})
        patch = {"id": "example-2027", "coverage": {"flight": "Covered"}}
        self.assertIn("evidence-coverage-conflict", rules(self.check(patch, existing), "block"))

    def evidence_for(self, results, via=False):
        record = self.base(evidence={"criteria": [crit()]})
        verdict = {"records": [{"id": "example-2027", "decision": "ACCEPT", "reason": "ok",
                                "evidence": [{"url": PAGE, "quote": "Citizens of all countries may apply.", **({"via": "webfetch"} if via else {})}]}]}
        quotes = {"example-2027": [{"url": PAGE, "status": "found", "via": "webfetch" if via else ""}]}
        merged = {"example-2027": J.merge_like_upsert(record, [], TODAY)[0]}
        return J.apply([record], verdict, {}, quotes, merged, {"example-2027": results})

    def test_evidence_survives_when_every_quote_is_on_its_page(self):
        out = self.evidence_for([{"where": "criteria[0]", "url": PAGE, "status": "found"}])
        self.assertIn("evidence", out["accepted"][0])
        self.assertEqual(out["log"]["evidence_dropped"], [])

    def test_evidence_is_dropped_but_the_record_is_kept_when_a_quote_is_not_on_the_page(self):
        out = self.evidence_for([{"where": "criteria[0]", "url": PAGE, "status": "found"},
                                 {"where": "funding[0]", "url": PAGE2, "status": "not_found"}])
        self.assertEqual(len(out["accepted"]), 1)
        self.assertNotIn("evidence", out["accepted"][0])
        self.assertIn("not on", out["log"]["evidence_dropped"][0]["why"])

    def test_an_unreadable_page_counts_only_when_the_judge_declared_a_reader(self):
        unreadable = [{"where": "criteria[0]", "url": PAGE, "status": "unreachable"}]
        self.assertNotIn("evidence", self.evidence_for(unreadable)["accepted"][0])
        self.assertIn("evidence", self.evidence_for(unreadable, via=True)["accepted"][0])

    def test_a_page_the_record_does_not_cite_is_dropped(self):
        out = self.evidence_for([{"where": "criteria[0]", "url": "https://other.example/page", "status": "found"}])
        self.assertNotIn("evidence", out["accepted"][0])
        self.assertIn("not cited", out["log"]["evidence_dropped"][0]["why"])

    def test_evidence_that_was_never_checked_is_dropped(self):
        record = self.base(evidence={"criteria": [crit()]})
        verdict = {"records": [{"id": "example-2027", "decision": "ACCEPT", "reason": "ok",
                                "evidence": [{"url": PAGE, "quote": "Citizens of all countries may apply."}]}]}
        quotes = {"example-2027": [{"url": PAGE, "status": "found", "via": ""}]}
        out = J.apply([record], verdict, {}, quotes, {"example-2027": J.merge_like_upsert(record, [], TODAY)[0]})
        self.assertNotIn("evidence", out["accepted"][0])
        self.assertIn("not checked", out["log"]["evidence_dropped"][0]["why"])

    def test_verify_evidence_reads_each_page_once_and_finds_the_quote(self):
        calls = []

        def fetch(url, timeout=25):
            calls.append(url)
            return 200, url, b"<html><body><p>Citizens   of all countries may apply.</p><p>Tuition is covered by the programme.</p></body></html>"
        record = self.base(evidence={"criteria": [crit(), crit("education", "MET")], "funding": [pay(page=PAGE)]})
        results = J.verify_evidence([record], fetch)["example-2027"]
        self.assertEqual({r["status"] for r in results}, {"found"})
        self.assertEqual(calls, [PAGE])
        invented = self.base(evidence={"criteria": [crit(quote="Every applicant receives a pony.")]})
        self.assertEqual(J.verify_evidence([invented], fetch)["example-2027"][0]["status"], "not_found")


class CycleStates(unittest.TestCase):
    def classify(self, record, ev=None, archive=None):
        return CY.classify(record, ev or {}, archive or [], TODAY)

    def test_an_open_programme_is_a_confirmed_current_cycle(self):
        info = self.classify(rec(application_deadline="2027-01-31", last_cycle_deadline=""))
        self.assertEqual((info["state"], info["basis"]), ("CONFIRMED CURRENT CYCLE", "page states it"))

    def test_an_announced_opening_is_confirmed_not_predicted(self):
        info = self.classify(rec(opens_on="2027-03-01", last_cycle_deadline=""))
        self.assertEqual((info["state"], info["phase"]), ("CONFIRMED CURRENT CYCLE", "announced opening"))

    def test_a_recurring_programme_without_a_date_is_expected_by_pattern(self):
        info = self.classify(rec())
        self.assertEqual((info["state"], info["basis"], info["expected_deadline_month"]), ("EXPECTED NEXT CYCLE", "pattern", "2027-02"))
        self.assertEqual(info["pattern"], "one earlier cycle")

    def test_no_earlier_cycle_means_not_yet_announced(self):
        self.assertEqual(self.classify(rec(last_cycle_deadline=""))["state"], "NOT YET ANNOUNCED")
        self.assertEqual(self.classify(rec(recurring=False))["state"], "NOT YET ANNOUNCED")

    def test_archived_cycles_add_to_the_history(self):
        archive = [{"id": "example-2027", "application_deadline": "2025-02-18"}, {"id": "other", "application_deadline": "2024-01-01"}]
        info = self.classify(rec(), archive=archive)
        self.assertEqual(info["history"], ["2025-02-18", "2026-02-20"])
        self.assertEqual(info["pattern"], "2 earlier cycles, same time of year")

    def test_cycles_that_drift_say_so(self):
        archive = [{"id": "example-2027", "application_deadline": "2025-08-18"}]
        self.assertIn("vary", self.classify(rec(), archive=archive)["pattern"])

    def test_an_organiser_stated_period_beats_a_pattern(self):
        ev = {"cycles": [{"cycle": "2027", "state": "EXPECTED NEXT CYCLE", "basis": "organiser states",
                          "window_text": "applications open in March", "page": PAGE, "quote": "Applications open in March 2027."}]}
        info = self.classify(rec(), ev)
        self.assertEqual((info["basis"], info["window_text"]), ("organiser states", "applications open in March"))

    def test_evidence_cycles_count_as_history(self):
        ev = {"cycles": [cycle("2024", deadline="2024-02-22"), cycle("2025", deadline="2025-02-20")]}
        self.assertEqual(self.classify(rec(), ev)["history"], ["2024-02-22", "2025-02-20", "2026-02-20"])

    def test_the_next_occurrence_skips_whole_years_and_survives_29_february(self):
        self.assertEqual(CY.next_occurrence(dt.date(2023, 3, 1), TODAY), dt.date(2027, 3, 1))
        self.assertEqual(CY.next_occurrence(dt.date(2024, 2, 29), dt.date(2026, 11, 18)), dt.date(2027, 2, 28))


class WatchList(unittest.TestCase):
    def test_the_list_is_sorted_and_labels_estimates_as_such(self):
        records = [rec(id="b", title="B", last_cycle_deadline="2026-09-01"), rec(id="a", title="A", last_cycle_deadline="2026-03-01")]
        out = CY.watch_list(records, {}, [], TODAY)
        self.assertEqual([i["id"] for i in out["items"]], ["a", "b"])
        self.assertTrue(all(i["phase"].startswith("Expected again (estimate)") and i["basis"] == "pattern" for i in out["items"]))

    def test_ruled_out_programmes_are_left_out_and_counted(self):
        out = CY.watch_list([rec(eligibility_for_me="NOT ELIGIBLE")], {}, [], TODAY)
        self.assertEqual((out["items"], out["left_out_not_eligible"]), ([], 1))

    def test_far_estimates_and_programmes_without_history_stay_off_the_list(self):
        records = [rec(id="far", last_cycle_deadline="2026-11-17"), rec(id="none", last_cycle_deadline="")]
        out = CY.watch_list(records, {}, [], TODAY)
        self.assertEqual([i["id"] for i in out["items"]], ["far"])                   # a yearly estimate is at most a year away
        self.assertEqual([i["id"] for i in out["not_yet_announced"]], ["none"])
        with mock.patch.object(CY, "HORIZON_DAYS", 100):
            self.assertEqual(CY.watch_list(records, {}, [], TODAY)["items"], [])

    def test_the_call_may_already_be_open_inside_ninety_days(self):
        soon = CY.watch_list([rec(last_cycle_deadline="2026-01-15")], {}, [], TODAY)["items"][0]
        later = CY.watch_list([rec(last_cycle_deadline="2026-06-15")], {}, [], TODAY)["items"][0]
        self.assertTrue(soon["check_now"])
        self.assertFalse(later["check_now"])

    def test_an_announced_opening_is_listed_as_announced(self):
        item = CY.watch_list([rec(opens_on="2027-01-04", last_cycle_deadline="")], {}, [], TODAY)["items"][0]
        self.assertEqual((item["phase"], item["window_text"], item["days_until"]), ("Opening announced", "opens 2027-01-04", 47))

    def test_nothing_the_list_derives_is_written_to_a_record(self):
        records = [rec(), rec(id="b", title="B", opens_on="2027-01-04")]
        before = copy.deepcopy(records)
        CY.watch_list(records, {}, [], TODAY)
        self.assertEqual(records, before)
        self.assertEqual({r["application_deadline"] for r in records}, {""})


class Backlog(unittest.TestCase):
    def test_open_records_come_first_and_finished_or_ruled_out_ones_are_left_out(self):
        records = [rec(id="later", title="Later", application_deadline="2027-06-01"),
                   rec(id="soon", title="Soon", application_deadline="2026-12-01"),
                   rec(id="done", title="Done", application_deadline="2026-12-05"),
                   rec(id="out", title="Out", application_deadline="2026-12-02", eligibility_for_me="NOT ELIGIBLE"),
                   rec(id="wait", title="Wait", application_deadline="", last_cycle_deadline="2026-02-01")]
        stored = {"done": {"criteria": [crit()]}}
        got = [i["id"] for i in SC.evidence_backlog(records, stored, TODAY)]
        self.assertEqual(got, ["soon", "later", "wait"])

    def test_each_channel_gets_a_small_share(self):
        records = [rec(id=f"r{i}", title=f"Scholarship {i}", application_deadline="2027-01-31", category=["Scholarship"]) for i in range(9)]
        bank = {"channels": {}, "languages": []}
        plan = SC.build_plan(TODAY, {"sources": []}, {"sources": {}}, [], [], records, {}, bank, 5, {})
        self.assertEqual(len(plan["channels"]["C"]["evidence_backlog"]), SC.EVIDENCE_PER_SCOUT)
        self.assertTrue(all(len(c["evidence_backlog"]) <= SC.EVIDENCE_PER_SCOUT for c in plan["channels"].values()))


class RealEvidenceFiles(unittest.TestCase):
    """The files committed in data/evidence obey the same rules the judge enforces."""
    def setUp(self):
        self.live = {r["id"]: r for r in L.load_db()["opportunities"]}
        self.archived = {r["id"] for r in L.load_archive()["opportunities"]}
        self.files = EV.load_all()

    def test_every_file_belongs_to_a_record_and_has_no_block_finding(self):
        for rid, ev in self.files.items():
            self.assertEqual(ev.get("id"), rid)
            self.assertTrue(rid in self.live or rid in self.archived, rid)
            self.assertEqual([f for f in EV.check(ev, self.live.get(rid)) if f["severity"] == "block"], [], rid)

    def test_every_quoted_page_is_one_the_record_cites(self):
        for rid, ev in self.files.items():
            if rid not in self.live:
                continue
            cited = {L.norm_url(s["url"]) for s in self.live[rid].get("sources", [])}
            for where, page, _quote in EV.quote_items(ev):
                self.assertIn(L.norm_url(page), cited, f"{rid} {where}")

    def test_no_live_record_carries_an_evidence_key(self):
        self.assertFalse([rid for rid, r in self.live.items() if "evidence" in r])

    def test_no_personal_data_in_the_files(self):
        text = json.dumps(self.files).lower()
        for banned in ("@gmail", "@yahoo", "@hotmail", "mukubwa", "passport number", "date of birth"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
