"""Lead filtering and scoring. Standard library only, no network, no side effects.

A feed title goes through four steps. Only the first three can reject it:

  1. too old                     -> rejected, counted, not logged (it is just an old item)
  2. not an opportunity          -> rejected and LOGGED (job ads, tenders, guides, how-tos)
  3. no opportunity word at all  -> rejected and LOGGED (news, speeches, reports)
  4. everything else             -> kept as a lead, with a score and flags

Words that suggest a restricted audience (a nationality, "PhD", "undergraduates", "women") never
reject a title. They lower its score and add a flag, because a title alone does not establish
that the applicant is ineligible: it can name the venue ("Arab American Leadership Program ... in the
USA"), list several levels ("Master, PhD and medical students") or describe a group the profile does
not record (the profile stores no gender). Ineligibility is decided later, on the organiser's own page.

Rejections are written to data/lead-audit.json by the caller so false exclusions can be audited.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import NamedTuple

import oplib as L

RULES_PATH = L.ROOT / "data" / "lead-rules.json"

LEAD_STATUSES = [
    "NEW", "UNDER REVIEW", "OFFICIAL SOURCE FOUND", "VERIFICATION REQUIRED", "VERIFIED", "PUBLISHED",
    "NOT CURRENTLY OPEN", "RECURRING PROGRAMME", "EXCLUDED - CONFIRMED INELIGIBLE",
    "REJECTED - NOT A LEGITIMATE OPPORTUNITY", "ARCHIVED",
]
LEGACY_STATUS = "NEEDS VERIFICATION"          # what leads carried before step 1
# Statuses a research cycle sets while it works on a lead. The daily job never archives these on its own
# (neither by age nor under the cap).
TERMINAL_STATUSES = {"PUBLISHED", "EXCLUDED - CONFIRMED INELIGIBLE",
                     "REJECTED - NOT A LEGITIMATE OPPORTUNITY", "ARCHIVED"}
# A lead in a terminal status is finished: the daily job moves it to archive/leads-archive.json unchanged.
HELD_STATUSES = set(LEAD_STATUSES) - {"NEW"} - TERMINAL_STATUSES

DEFAULT_RULES = {
    "retention": {"max_active_leads": 1500, "ttl_days": 45, "max_item_age_days": 30,
                  "audit_days": 90, "feed_alert_after_runs": 7},
    "score": {"base": 40, "tier1": 25, "tier2": 15, "strong_word": 15, "weak_word": 8,
              "region_signal": 5, "fresh_within_7_days": 5, "nationality_for": -35, "level_only": -25,
              "country_specific": -15, "fee_risk": -10, "max_total_penalty": -45},
}

# ---------------------------------------------------------------- patterns
INCLUDE = re.compile(
    r"scholar(?:ship)?s?\b|fellowship|fully[- ]funded|\bfunded\b|\bgrants?\b|bourses?\b|\bbecas?\b|\bbolsas?\b|"
    r"exchange|summit|conference|forum|\bprogram(?:me)?s?\b|\bprogramas?\b|\bawards?\b|\bprize\b|\bprix\b|"
    r"competition|concours|challenge|internship|\bstage\b|training|formation|volunt|volont|bootcamp|"
    r"boot camp|accelerator|incubat|residenc|summer school|winter school|\b(?:summer|winter) camp\b|"
    r"\bcamp\b|appel [àa] candidatures|call for (?:applications|proposals|nominations|participants)|"
    r"convocatoria|leadership|academy|delegat|joint master|erasmus|mundus|cohort|class of|traineeship|"
    r"apprentic|mentor|stipend|bursar|sponsored|study tour|observer|mobility|hackathon|symposium|"
    r"workshop|seminar|s[ée]minaire|festival|congress|congr[eè]s|dialogue|olympiad|\bcourses?\b|\bmooc\b|"
    r"e-learning|young leaders?|jeunes leaders?", re.I)
# Mixed feeds (official news streams) keep only titles that clearly name a call.
STRICT = re.compile(
    r"scholar(?:ship)?s?\b|fellowship|bourses?\b|call for applications|appel [àa] candidatures|volunt|volont|"
    r"internship|\bstage\b|\bprix\b|award|concours|competition", re.I)
NOT_OPPORTUNITY = re.compile(
    r"\bjobs?\b|recrut|recruit|vacanc|appel d.offres|avis d.appel|consultan|prestataire|\btender\b|"
    r"lecturer|professor|post-?doc|\bhiring\b|\bRFP\b|\bRFAs?\b|how to\b|\bguide\b|comment postuler|"
    r"\btips\b|\bg[ée]n[ée]rateur\b|assurance|\bCV\b|recherche une?\b|\brecherche \d", re.I)

_DEMONYM = (r"(?:nigerian|kenyan|ghanaian|ugandan|rwandan|tanzanian|zambian|zimbabwean|malawian|ethiopian|"
            r"cameroonian|south african|egyptian|moroccan|tunisian|indian|pakistani|bangladeshi|filipino|"
            r"indonesian|american|british|canadian|australian|european|asian)s?")
_GROUP = (r"(?:students?|undergraduates?|graduates?|youths?|young people|nationals?|citizens?|women|men|"
          r"professionals?|entrepreneurs?|residents?|researchers?|scholars?|applicants?|candidates?|"
          r"teachers?|farmers?|talents?)")
# "for (young) Nigerian ...", "pour les Camerounais", or "<nationality> <group>". A bare place or
# organisation name ("American University in Cairo", "Arab American Leadership Program") is not a match.
NATIONALITY_FOR = re.compile(
    rf"\b(?:for|to|open to|reserved for|restricted to|pour|aux)\s+(?:the |all |les |young |jeunes )*(?:\w+ )?{_DEMONYM}\b"
    rf"|\b{_DEMONYM}\s+{_GROUP}\b", re.I)
COUNTRY_SPECIFIC = re.compile(
    r"\b(?:au|du|en|de)\s+(?:tchad|s[ée]n[ée]gal|mali|niger|togo|b[ée]nin|cameroun|burkina|gabon|guin[ée]e)\b", re.I)
LEVEL_ONLY_PHD = re.compile(
    r"\bphd\b|\bph\.d\b|doctoral|doctorat|doctorales?|postdoctoral|\bresearchers?\b|chercheurs?|economist program", re.I)
LEVEL_ONLY_UNDERGRAD = re.compile(r"\bundergraduates?\b|high school|secondary school|lyc[ée]ens?", re.I)
# Words that show the title covers more than one level. They cancel the level-only penalty.
MIXED_LEVELS = re.compile(
    r"\bmaster|\b(?:post-?)?graduates?\b|\bbachelor|\blicen[cs]e|all levels|worldwide|international students|"
    r"young professionals|any level|open to all", re.I)
GENDER_TERM = re.compile(r"\b(?:women|woman|female|femmes?|girls?)\b", re.I)
FEE_RISK = re.compile(r"\b(?:application|registration|participation)\s+fee\b|\bpaid\s+(?:conference|summit|programme|program)\b", re.I)
STRONG = re.compile(
    r"scholar(?:ship)?s?\b|fellowship|bourses?\b|\bbecas?\b|\bbolsas?\b|fully[- ]funded|fully sponsored|"
    r"enti[eè]rement financ", re.I)
WEAK = re.compile(
    r"\bfunded\b|stipend|sponsored|\bgrants?\b|bursar|summit|conference|forum|exchange|internship|\bstage\b|"
    r"volunt|volont|delegat|study tour|traineeship|\bprogram(?:me)?s?\b", re.I)
REGION = re.compile(
    r"\b(?:africa|african|africain\w*|rdc|congo|drc|kinshasa|global south|developing countries|"
    r"pays en d[ée]veloppement)\b", re.I)


class Assessment(NamedTuple):
    kind: str          # "lead" or "reject"
    reason: str        # reject: too_old | not_opportunity | no_opportunity_word ; lead: ""
    detail: str        # the matched text, for the audit log
    score: int         # 0-100, meaningful for leads
    flags: list        # e.g. ["audience:nationality:Nigerian"]


def load_rules() -> dict:
    """data/lead-rules.json merged over the built-in defaults, so a missing key never crashes the run."""
    disk = L.load(RULES_PATH, {})
    merged = {"retention": dict(DEFAULT_RULES["retention"]), "score": dict(DEFAULT_RULES["score"])}
    for section in merged:
        merged[section].update({k: v for k, v in (disk.get(section) or {}).items() if isinstance(v, (int, float))})
    return merged


def score_title(title: str, tier: int, published: str, today: dt.date, rules: dict) -> tuple[int, list]:
    w = rules["score"]
    score, flags = w["base"], []
    strong, weak = bool(STRONG.search(title)), bool(WEAK.search(title))
    if strong:
        score += w["strong_word"]
    elif weak:
        score += w["weak_word"]
    if strong or weak:                       # an official source only counts when the title names a call
        score += w["tier1"] if tier == 1 else w["tier2"] if tier == 2 else 0
    if REGION.search(title):
        score += w["region_signal"]
    when = L.parse_date(published)
    if when and 0 <= (today - when).days <= 7:
        score += w["fresh_within_7_days"]

    penalty = 0
    nat = NATIONALITY_FOR.search(title)
    if nat:
        penalty += w["nationality_for"]
        flags.append("audience:nationality:" + nat.group(0).strip())
    country = COUNTRY_SPECIFIC.search(title)
    if country:
        penalty += w["country_specific"]
        flags.append("audience:country:" + country.group(0).strip())
    if not MIXED_LEVELS.search(title):
        for label, pattern in (("phd", LEVEL_ONLY_PHD), ("undergraduate", LEVEL_ONLY_UNDERGRAD)):
            hit = pattern.search(title)
            if hit:
                penalty += w["level_only"]
                flags.append(f"audience:level-only:{hit.group(0).strip()}")
                break
    if FEE_RISK.search(title):
        penalty += w["fee_risk"]
        flags.append("risk:fee-in-title")
    gender = GENDER_TERM.search(title)
    if gender:                               # no penalty: the profile records no gender, so this is a check to make
        flags.append("check:gender-term:" + gender.group(0).strip())
    score += max(penalty, w["max_total_penalty"])
    return max(0, min(100, score)), flags


def assess(title: str, published: str = "", tier: int = 3, feed_filter: str = "", today: dt.date | None = None,
           rules: dict | None = None) -> Assessment:
    rules = rules or load_rules()
    today = today or L.today_utc()
    when = L.parse_date(published)
    if when and (today - when).days > rules["retention"]["max_item_age_days"]:
        return Assessment("reject", "too_old", f"{(today - when).days} days old", 0, [])
    bad = NOT_OPPORTUNITY.search(title)
    if bad:
        return Assessment("reject", "not_opportunity", bad.group(0), 0, [])
    if feed_filter != "none":
        pattern = STRICT if feed_filter == "strict" else INCLUDE
        if not pattern.search(title):
            return Assessment("reject", "no_opportunity_word", "", 0, [])
    score, flags = score_title(title, tier, published, today, rules)
    return Assessment("lead", "", "", score, flags)


def migrate_lead(lead: dict, today: dt.date, rules: dict) -> dict:
    """Bring a lead written before step 1 up to the new shape. Idempotent. Never drops a field."""
    if lead.get("status") in (None, "", LEGACY_STATUS):
        lead["status"] = "NEW"
    if "score" not in lead:
        lead["score"], lead["flags"] = score_title(
            lead.get("title", ""), lead.get("source_tier", 3), lead.get("published", ""), today, rules)
    lead.setdefault("flags", [])
    lead.setdefault("last_seen", lead.get("first_seen", ""))
    return lead


def trim_audit(entries: list[dict], today: dt.date, audit_days: int) -> list[dict]:
    keep = []
    for entry in entries:
        when = L.parse_date(entry.get("date"))
        if when is None or (today - when).days <= audit_days:
            keep.append(entry)
    return keep


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
