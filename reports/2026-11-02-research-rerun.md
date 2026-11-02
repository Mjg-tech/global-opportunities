# Research cycle rerun - 2026-11-02 (second, deeper pass)

Batch files: `research/2026-11-02-rerun/` (merged with `python scripts/upsert.py research/2026-11-02-rerun/*.json`).
The first pass (`research/2026-11-02/`, `reports/2026-11-02-research.md`) and `data/profile.json` were not touched
(`git diff 70bc51f..HEAD` is empty for them). Pushed in five checkpoints and a final commit with the plain message.

Run settings (output of the diagnostic command): `CLAUDE_EFFORT=max`, `--effort max`, `--model claude-sonnet-5-5`.

Method: every page cited below was opened again in this run, with a plain `curl` (default headers, no tricks) and,
where that failed, once with the WebFetch tool. Facts come from the page text, not from the first pass's summaries.
Google Forms and Microsoft Forms were not logged into. Nothing was applied for, paid, registered or sent.

Result: **4 new records** (one is a LOW-confidence warning), **21 records with changed content**, 5 records re-read
with only a new `last_verified` date; 77 live records (73 before); `validate.py` ends with 0 errors and the one existing
warning (Chevening: "Fully Funded", components not itemised on the pages). LIKELY ELIGIBLE labels fell from 15 to 8.

## What the first pass (and earlier cycles) missed or got wrong

1. **Global Leadership Challenge** said LIKELY ELIGIBLE. Three stated criteria are not in the profile: "young professional"
   status (it has internships, no full-time job), an exact age inside 21-30 (only an under-30 band is kept) and "already
   demonstrated commitment to responsible leadership". Now POSSIBLY ELIGIBLE with the missing facts named (rule 5). The
   record also said "three winning teams"; the page says **four**.
2. **Jim Leech Mastercard Foundation Fellowship** was labelled Fully Funded. The page never says "fully funded": 1000+
   candidates take free online courses, 180+ finalists continue, **up to 60 Fellows** get a stipend, and the amount is stated
   twice with different figures (CAD 500, USD 350). Now Participation Funded; LIKELY became POSSIBLY ELIGIBLE because
   "recent graduate" is undefined and 10 hours a week and written English are not in the profile.
3. **DAAD Helmut-Schmidt-Programme** (earlier cycles: "call PDF not read"). The call PDF (Stipendienausschreibung 05/2026,
   studies from September/October 2027) was read on static.daad.de: application period **1 June to 31 July 2026** (now
   official), EUR 992 a month plus health insurance, travel lump sums and tuition exemption, and the call asks for
   **above-average grades (upper third)** and **relevant practical experience (professional experience or internships)**, with
   minimums by course (3 months to 2 years). The record's "no experience required" and "very high fit" were wrong. Now
   VERIFIED, Substantially Funded, POSSIBLY ELIGIBLE. The Social Protection course (Bonn-Rhein-Sieg) names Business
   Administration degrees and asks for five months of related experience: the one to watch for the next call.
4. **LIKELY ELIGIBLE labels resting on facts the profile does not record** (rule 5), lowered to POSSIBLY ELIGIBLE with the
   missing fact named: ICANN Fellowship (interest in ICANN's work), Mandela Washington Fellowship (exact age 25-35 and a
   record of accomplishment; cycle closed), Stipendium Hungaricum (the FAQ says "only the nominated applicants can proceed",
   so the DRC authority's nomination decides), Nasser Fellowship (the criteria list decision-makers, programme alumni,
   activists and youth-council heads), plus items 1-3.
5. **Funding labels the organiser's own wording does not support** (rule 4), found by auditing every Fully Funded record:
   - **Mundus MAPP**: the official financial-aid page says "a limited number" of EMJM scholarships go to the highest-ranked
     applicants, EUR 1,400 a month (maximum EUR 33,600, which must also cover travel, visa and installation), a full tuition
     waiver, and that the scholarship "does NOT cover" the Study Visit and Winter School (EUR 600-1000 each) or travel and visa
     costs to the consortium countries; applicants should seek external funding too. Now **Substantially Funded** (it was Fully
     Funded and VERIFIED on 29 October).
   - **GLOCAL Erasmus Mundus**: tuition, insurance, an "optional contribution" to travel and a monthly allowance (EUR 1,400, or
     EUR 1,275 after three EUR 1,000 advances); never "fully funded". Now Substantially Funded. The scholarship, how-to-apply
     and entry-requirements pages now all give 14 January 2027, 13:00 UK time. The Glasgow country-grade page has no entry for
     the DRC, so the grade rule for a Congolese Licence is unpublished (stays PARTIALLY VERIFIED).
   - **DAAD In-Country/In-Region**: the official page says the scholarship "usually includes" tuition, a monthly rate, allowances
     and, for In-Region scholars only, travel and insurance. Now Substantially Funded.
   - **Tony Elumelu Entrepreneurship Programme**: the page describes training, mentoring and a "$5,000 non-refundable seed capital" paid
     into the business account after a document review, never "fully funded". Now Partially Funded (the stipend coverage mark was also wrong).
   - **McKinsey.org Forward**: a free online learning programme ("There are no fees to apply, register, or partake"), so Participation Funded,
     not Fully Funded. Its action still said "Apply today" although the FAQ now reads "Applications are not open at the moment"; fixed. The
     FAQ answers sit in the page's embedded data, collapsed in the visible text; the DRC is on the Africa list. Now VERIFIED.
   - **Türkiye Bursları**: upgraded in the other direction. The organiser's own words on its "Why Türkiye Scholarships?" page are "a fully
     funded ... education" (tuition, one-year Turkish course, accommodation, a once-off flight ticket, health insurance, a monthly stipend of
     9,500 TL at master's level). The criteria page, read directly (earlier cycles had only search snippets): master's applicants under 30,
     at least 75% for graduate candidates, citizens of all countries except Turkey. The calendar still gives 10 January to 20 February with no
     year. Now VERIFIED (it was PARTIALLY VERIFIED).
   - Left as Fully Funded because the pages carry comprehensive wording or itemise it: Gates Cambridge, Mastercard Foundation
     Scholars (Cambridge, Edinburgh, Sciences Po, McGill), Knight-Hennessy, Mandela Rhodes, Schwarzman, VLIR-UOS, Yenching,
     Kectil, Chevening (its page says "fully-funded", no itemised components). **For a person to review:** the Swedish Institute
     (not eligible anyway; its page says insurance is not included).
6. **ARES international training scholarships** (earlier: "pages return empty content", INSUFFICIENT INFORMATION). The ARES page
   now reads with a plain request: deadline 18 September 2026 and "Prochain appel : Aout 2027" (both official), the DRC ("RD Congo")
   is among the 32 countries, the scholarship covers international travel, a subsistence allowance, registration fees, visa costs
   and insurance, and applicants need **two years of relevant professional occupation after the last diploma**. The profile has
   under one year, so the label is now **NOT ELIGIBLE** (today) and the record VERIFIED, Substantially Funded.
7. **Wageningen Africa Scholarship Programme**: the recorded address now answers HTTP 308 and lands on
   `/en/education/master/study-expenses-masters/scholarships`; URLs updated, ASP text unchanged (African citizen, first-class
   honours or GPA 80% or higher, before 1 December 2026, lottery in the final stage, offer on 7 April 2027).
8. **AUC African Graduate Fellowship**: the graduate admissions page now calls 15 December 2026 "Regular admission" and 1 April
   2027 "Late admission" (the record said early and regular). Spring 2027 admission closed on 1 October 2026, so the "Fellowship
   Application Cycle for Spring 2027" (deadline 8 November) cannot be used by a new applicant.
9. **Raisina (PCNS places)**: the action text still told the applicant to check whether PCNS limits the places to its youth
   community; the page read today states no such condition. The form is behind a Google sign-in (HTTP 401) and was not read.
   **Dalai Lama Fellows**: the action still pointed to the 28 October information session, which has passed.
10. **Chevening**: the DRC page confirms the 2027-2028 round is closed and adds a cost the record did not carry: no UK visa
    processing centre in the DRC, so a scholar travels to another country for the visa and the TB test at their own cost, with only
    a discretionary reimbursement.
11. **Confirmed unchanged** (first pass was right): IREX CSP 2027 (DRC not on the Africa list, ages 27-39, five years of
    experience, "covers the cost of most expenses"), Fortis, USTC, Kectil, Telemachus, AFS Sir Cyril Taylor, Sciences Po
    Mastercard and Boutmy, Yenching, Wageningen, Maastricht (18 full scholarships, 10 December), the Cambridge fee waiver (DRC
    listed), One Young World (closed 31 October), Pan African University ("Applications closed on 15/12/2025"; au.int shows no
    2027-2028 call), EU Delegation DRC internship (no open call), ICANN (ICANN89 round for alumni only), McKinsey.org Forward
    ("Applications are not open at the moment"; DRC on the Africa list), Obama Leaders ("Applications live on November 9!", no year
    on the page; the record reads it as 2026 using the page's "November of the preceding year" rule).

## Re-verified independently (pages opened in this run)

| Record | Pages read |
|---|---|
| Raisina PCNS (closes today 17:00 Casablanca) | policycenter.ma call page |
| Global Leadership Challenge (5 Nov) | leadership-challenge.org/applynow |
| Fortis, USTC, Dalai Lama Fellows, Kectil, AFS Sir Cyril Taylor, Telemachus | the organisers' pages |
| Sciences Po Mastercard and Boutmy, Yenching, Jim Leech, Mundus MAPP (calendar, how to apply, financial aid), Wageningen, Maastricht | official pages |
| WFF Youth Policy Board (30 Nov, aggregator date) | call page, form page, Terms of Reference PDF |
| GLOCAL, Weidenfeld-Hoffmann process page, Obama Leaders, Türkiye Burslari calendar, AUC (fellowship, deadlines, how to apply), DAAD In-Country overview PDF and programme page | official pages |
| DAAD Helmut-Schmidt call, course and country PDFs; ICANN; Nasser; Stipendium Hungaricum; McKinsey.org; RLC East Africa; ARES; Aspire Leaders; AU-YVC; Chevening; EU Delegation DRC; IREX | official pages |
| One Young World, Pan African University (au-pau.org and au.int) | official pages |

## Could not read

- **Google Forms** for Raisina and AFS: HTTP 401 (sign-in required). **Microsoft Form** embedded in the WFF call page: "Loading..." (JavaScript).
- **sbs.ox.ac.uk** (AfOx Oxford MBA), **ox.ac.uk** (Weidenfeld-Hoffmann), **rdc.emb-japan.go.jp** (MEXT), **coe.int** (World Forum for
  Democracy), **zlc.edu.es** (MIT-Zaragoza), **afreximbank.com** internship page: HTTP 403 to the plain reader (the first three to WebFetch too).
  Not retried. AfOx, MEXT and World Forum for Democracy stay NEEDS VERIFICATION.
- **iucea.org**: connection reset (curl error 35); the UNHCR Rwanda copy of the EACSP detailed call: 403; an NM-AIST copy: 404.
- **jobs.fao.org** vacancy 2601980: the page returns empty fields (posting and closing date blank) to both readers; the 31 December
  closing date could not be re-read (noted on the record; `last_verified` not bumped).
- Re-read with nothing new (so `last_verified` was not bumped): ALX (no cohort dates on the page), JICA ABE, French-African Foundation, France Volontaires.

## New records

| id | Deadline | Funding | Eligibility | Verification |
|---|---|---|---|---|
| `eacsp-iucea-kfw-masters-scholarship-2026-cohort-4` | none open (cohort 4 closed 10 Sep 2026, 17:00 EAT) | Substantially Funded | POSSIBLY ELIGIBLE | PARTIALLY VERIFIED |
| `mastercard-foundation-scholars-mcgill-2027` | none open (Fall 2027 cohort closed; next cycle "Spring 2027") | Fully Funded | POSSIBLY ELIGIBLE | VERIFIED |
| `mastercard-foundation-associates-program` | rolling, no closing date | Funding Unclear (a stipend, amount not stated) | POSSIBLY ELIGIBLE | PARTIALLY VERIFIED |
| `youth-global-forum-2027-paris-cgdl` | 18 Nov 2026 (the organiser's other page says 20 Nov) | Funding Unclear | POSSIBLY ELIGIBLE (to apply) | NEEDS VERIFICATION, source confidence LOW (warning) |

- **EAC Scholarship Programme (EACSP), Phase II, cohort 4** (IUCEA, with the East African Community and Germany's KfW). A two-year,
  funded master's in an EAC country other than your own, for nationals of the eight EAC states, **the DRC named explicitly**, age
  below 35, bachelor's with Second Class Upper Division or equivalent. Package: return economy ticket, full tuition, EUR 380 a month,
  EUR 200 on arrival, EUR 650 materials, EUR 1,500 research allowance, insurance, visa or entry fee; up to 120 awards. The programme
  table has business-related master's (MBA and HR management at KCA University, logistics and supply chain at Kibabii University,
  taxation at INES-Ruhengeri in Rwanda, innovation and entrepreneurship management at NM-AIST, economics at Daystar). The cohort 4
  window ran 20 August to 10 September 2026 and results were due in December, so nothing can be applied for today; the record is there
  to watch for the next cohort ("three cohorts" in Phase II). Read on the University of Dar es Salaam copy of the call PDF, hence
  PARTIALLY VERIFIED and an Institutional source. It does not say "fully funded", so the label is Substantially Funded.
- **Mastercard Foundation Scholars Program at McGill** (master's, Montreal). The DRC ("Congo (Democratic Republic)") is on the eligible
  list; 35 awards a year across 13 programmes; the FAQ says the scholarship "covers not only full tuition but all costs related to
  attending McGill" (tuition, on-campus housing, monthly stipend, immigration support). Only **Public Policy** is an evident fit.
  Criteria include never having registered for a master's, age 35 or under, a valid passport, a record of service and leadership and
  financial need. The Fall 2027 cohort is closed (the 1 December 2026 date an aggregator quotes is only for candidates who already
  received a fee waiver); McGill says to watch for the next recruitment cycle in Spring 2027.
- **Mastercard Foundation Associates Program** (12-month paid work placements). The official page: open to alumni and "young people
  across Africa", apply for roles in your country of residence or remote roles, "a stipend is provided", roles posted on an ongoing
  basis, **Francophone Africa route "Closed for Applications"**. Age (18-35), experience (0-2 years) and the stipend amount come from
  aggregators only and the DRC is not named. Worth a look because a paid year of experience would unblock the two-year work rules
  of ARES, the Swedish Institute and others.
- **Youth Global Forum 2027, Paris** (CGDL, Toronto). Aggregators sell it as "Fully Funded". The organiser's pages show 30 fully funded
  and 40 partially funded seats out of 250, a **USD 16.99 registration fee for the funded categories that is "mandatory,
  non-refundable, and cannot be disputed under any circumstances"**, airfare for fully funded delegates reimbursed only "after the
  event" (4 to 8 weeks), the visa "solely the delegate's responsibility", paid seats at USD 399 to USD 999.99, an ages 16-46 range and two
  different funded deadlines. Published only as a warning (LOW).

## Updated records and what changed

Content changes: Global Leadership Challenge, Jim Leech, Tony Elumelu, Türkiye Bursları, McKinsey.org Forward, DAAD Helmut-Schmidt, ICANN, Mandela Washington, Stipendium Hungaricum, Nasser,
ARES, Mundus MAPP, GLOCAL, DAAD In-Country/In-Region, Wageningen, AUC, Dalai Lama Fellows, Raisina, AFS, Chevening, FAO RAF (note only).
Only a new `last_verified` date: Yenching, Sciences Po Boutmy and Mastercard, WFF Youth Policy Board, Obama Foundation Leaders.
`data/sources.json` watchlist: Chinese Government Scholarship (2027/2028 round open per the Chinese Embassy in Indonesia's notice, general
rules recorded, DRC route not found), Global Korea Scholarship (no official 2027 graduate call yet), and a new entry for the Czech
government scholarships (DRC not on the 2027/2028 country list) and NAWA Banach (no 2027/28 call).
The two `source_changed` flags in `latest.md` (One Young World, Pan African University) clear at the next networked daily refresh.

## Closing soon (next 14 days)

- **2 Nov, 17:00 Casablanca (16:00 UTC): Raisina Young Fellows (PCNS places)**, today; ages 28-35 and a leadership record (INSUFFICIENT INFORMATION).
- 5 Nov: Global Leadership Challenge (POSSIBLY ELIGIBLE now; online, travel only for the four winning teams; rolling review).
- 8 Nov: Fortis Fellowship; USTC Winter Camp (UTC+8, 3000 CNY fee).
- 9 Nov: Obama Foundation Leaders opens (not a closing date).
- 11 Nov, 22:00 UTC: Dalai Lama Fellows (online; needs a community project).
- 15 Nov: Kectil Program (ages 17-26).
- Just beyond: 18 Nov Youth Global Forum (warning), 19 Nov AFS Sir Cyril Taylor, 22 Nov Internet Society pre-fellowship training, 23 Nov Telemachus
  and Sciences Po Mastercard, 29 Nov Boutmy, 30 Nov WFF Youth Policy Board and Yenching, 1 Dec Jim Leech, Mundus MAPP and Wageningen.

## Newly found travel-funded opportunities

None that is open and recommendable. Found but closed: EACSP (return air ticket, cohort 4 closed 10 September) and McGill Mastercard
(immigration support and housing; flights not itemised; next cycle Spring 2027). Open but a warning: Youth Global Forum Paris (airfare
reimbursed after the event; non-refundable fee). The Associates programme pays a stipend, no travel.

## Strongest apparent eligibility

LIKELY ELIGIBLE (8): Internet Society Fellowship (training before 22 November, apply by 18 December), VLIR-UOS ICP Connect (per-programme
deadlines), Erasmus Mundus umbrella, Objectif 2030 free courses (session 30 November to 27 December), plus four records with no open call
(European Forum Alpbach, McKinsey.org Forward, RLC East Africa, Orange Digital Center). Strongest POSSIBLY ELIGIBLE on fit: Jim Leech (1 Dec),
Yenching (30 Nov, needs IELTS 7.0 or equivalent), Wageningen ASP (1 Dec, first-class or 80%), Mundus MAPP (1 Dec, 3.17 GPA, limited awards),
Maastricht NL-High Potential (10 Dec, 75%), Gates Cambridge and Mastercard Cambridge (8 Dec), then EPOG, GrEnFIn and Human Response (January).
Next-year watch: Türkiye Bursları (window 10 January to 20 February, age under 30, 75%), McGill (Spring 2027), EACSP (next cohort), DAAD Helmut-Schmidt (June-July 2027), ARES (August 2027; needs two years of work).

## Suspicious or unverified items

- **Youth Global Forum Paris** (above) and the earlier Baku SDG 17 warning: paid applications sold as "fully funded".
- **WFF Youth Policy Board**: official pages state ages 18-35, FAO-member nationality and C1 English but no deadline and no funding; 30 November
  is Opportunity Desk's date and the form cannot be read. **Telemachus**: format, fee and start date not stated.
- **AfOx Oxford MBA, MEXT (DRC embassy page), World Forum for Democracy**: official pages return 403; secondary details only.
- **Raisina and AFS**: the application forms need a Google sign-in, so their questions and documents are unread.
- **Mastercard Foundation Associates**: age, experience and stipend from aggregators; DRC access to remote roles unconfirmed.
- Skipped as not eligible or not a fit: WACSI Next Generation Internship (its page seeks interns from Benin, Mali, Cameroon, Chad, Ghana and Nigeria),
  AU Enterprise Africa Network Fellowship (registered businesses with two years of operation and three staff), Czech government scholarships (DRC
  not on the 2027/2028 country list), WTO Young Professionals (closed May 2026; advanced degree), AfDB and ECOWAS internships (closed or need a master's),
  Youth Ambassadors Africa (ages 15-18), Learn Africa (women only), CorpsAfrica (no DRC programme found).

## Expired items

Raisina closes today at 16:00 UTC. Already past: One Young World (31 Oct), UCT Mastercard (31 Oct), Ebuteli (30 Oct), Open Doors registration (1 Nov),
Edinburgh declaration form (26 Oct), RLRH (25 Oct), HSC youth ambassadors (19 Oct), Baku SDG 17 (24 Oct). Closed cycles now tracked for the next call:
EACSP (10 Sep), ARES (18 Sep), Helmut-Schmidt (31 Jul), McGill, Mandela Washington (13 Oct), Aspire Cohort 4 (16 Oct), Chevening (6 Oct), ICANN88.
The daily refresh archives passed cycles 14 days after the deadline.

## Searches run (English, French, Portuguese, Spanish)

34 standard searches: youth summits and delegations, fellowships naming the DRC, 2027 master's scholarships, funded internships, study tours, embassy and
government programmes, Atlantic Dialogues, AMCI Morocco, EAPD Egypt, Enabel, PEC-PG Brazil, AECID Spain, AUF mobility, Global Korea Scholarship, Erasmus+ youth
exchanges, COP31 youth delegations, supply chain and logistics scholarships, Mastercard Foundation partner universities, the Chinese Government Scholarship, Czech and
Polish government schemes. Results were mostly aggregator pages, so only items checked on an organiser's page became records. Portuguese and Spanish searches
found nothing new that is open to the DRC. Still searching without a fit: UN Volunteers, UNHCR internships and Fulbright (official pages blocked or closed).

## Action queue

1. **Today, 16:00 UTC: Raisina** - only if 28 to 35 with a leadership record in politics, diplomacy, business, media, civil society or academia.
2. **By 5 Nov: Global Leadership Challenge** - apply early (rolling review); keep 10-14 December free.
3. By 8 Nov: Fortis; USTC only if the 3000 CNY fee is acceptable. 9 Nov: open the Obama Leaders page. By 11 Nov 22:00 UTC: Dalai Lama Fellows. By 15 Nov: Kectil (ages 17-26).
4. By 19 Nov: AFS Sir Cyril Taylor (passport valid through August 2027). **By 22 Nov: Internet Society pre-fellowship training**, then apply by 18 December.
   By 23 Nov: Sciences Po Mastercard and, optionally, Telemachus.
5. **Book an English test now** (Yenching 30 Nov, Wageningen and Mundus MAPP 1 Dec, Cambridge 8 Dec, GLOCAL 14 Jan, EPOG 27 Jan).
6. Convert the Licence grade to a percentage and a 4.0 scale: Wageningen needs first-class or 80%, MAPP 3.17, Maastricht 75%, DAAD Helmut-Schmidt the upper third.
7. Write to eacsp@iucea.org to ask when the next EACSP cohort opens; watch mcgill.ca/mastercardfdn-scholars (Spring 2027), ares-ac.be (August 2027), daad.de (June-July 2027),
   the Stipendium Hungaricum site (mid-November), au.int and au-pau.org (PAU call), turkiyeburslari.gov.tr (10 January to 20 February round) and the Chinese Embassy in Kinshasa.
8. **Do not pay** the Youth Global Forum registration fee.
9. Open in a browser: the WFF Microsoft Form, the AfOx and Weidenfeld-Hoffmann Oxford pages, the MEXT page, the World Forum for Democracy call, FAO vacancy 2601980 and the
   Afreximbank internship page.
