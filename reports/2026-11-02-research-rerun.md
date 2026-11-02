# Research cycle rerun - 2026-11-02 (second, deeper pass)

Batch files: `research/2026-11-02-rerun/`. The first pass (`research/2026-11-02/`, `reports/2026-11-02-research.md`)
was left untouched. This file is extended at each checkpoint, so a report exists even if the session is cut off.

Run settings (diagnostic command output): `CLAUDE_EFFORT=max`, `--effort max`, `--model claude-sonnet-5-5`.

Method: every page below was opened again during this run with a plain `curl` (default headers, no tricks) and, where
that failed, with the WebFetch tool. Facts come from the page text, not from the first pass's summaries. Google Forms
and Microsoft Forms were not logged into.

## What the first pass (and earlier cycles) missed or got wrong

1. **Global Leadership Challenge** said LIKELY ELIGIBLE. Three stated criteria are not recorded in the profile:
   "young professional" status (the profile has internships, no full-time job), an exact age inside 21-30 (only an
   under-30 band is kept) and "already demonstrated commitment to responsible leadership". Lowered to POSSIBLY
   ELIGIBLE with the missing facts named (rule 5). The record also said "three winning teams"; the page says **four**.
2. **Jim Leech Mastercard Foundation Fellowship** was labelled Fully Funded. The organiser's page never says "fully
   funded". It describes a funnel (1000+ candidates take free online courses, 180+ finalists, **up to 60 Fellows** get
   a stipend) and states the stipend twice with different figures (CAD 500 under Financial Support, USD 350 in the
   Phase 3 text). Relabelled Participation Funded; eligibility lowered from LIKELY to POSSIBLY ELIGIBLE because
   "recent graduate" is not defined on the page and the 10 hours a week and written English are not in the profile.
3. **Wageningen Africa Scholarship Programme**: the recorded address now answers HTTP 308 and lands on a different
   page (`/en/education/master/study-expenses-masters/scholarships`). The URLs were updated; the ASP text is
   unchanged (African citizen, first-class honours or GPA of 80% or higher, deadline before 1 December 2026,
   lottery in the final stage, offer on 7 April 2027).
4. **AUC African Graduate Fellowship**: the graduate admissions page now calls 15 December 2026 "Regular admission"
   and 1 April 2027 "Late admission" (the record said early and regular). Spring 2027 admission closed on
   1 October 2026, so the "Fellowship Application Cycle for Spring 2027" (deadline 8 November) cannot be used by a new
   applicant.
5. **Raisina (PCNS places)**: the record still told the applicant to check whether PCNS limits the places to its
   youth community. The page read again today states no such condition. The action text was rewritten; the form is
   behind a Google sign-in (HTTP 401) and could not be read.
6. **Dalai Lama Fellows**: the action still told the applicant to join the 28 October information session, which has
   passed. Updated.

7. **DAAD Helmut-Schmidt-Programme** (earlier cycles: "call PDF not read"). Read now on static.daad.de: the 2027 call
   (Stipendienausschreibung 05/2026) ran **1 June to 31 July 2026** (now official, not secondary), pays EUR 992 a month
   plus health insurance, travel lump sums and tuition exemption, and asks for **above-average grades (upper third)**
   and **relevant practical experience (professional experience or internships)**, with minimums by course (3 months
   to 2 years). The record's old line "no experience required" was wrong, so its "very high" fit and LIKELY ELIGIBLE
   label went. Now VERIFIED, Substantially Funded, POSSIBLY ELIGIBLE. The Social Protection course (Bonn-Rhein-Sieg)
   names Business Administration degrees and asks for five months of related experience, so it is the one to watch
   for the next call.
8. **LIKELY ELIGIBLE labels that rest on unrecorded facts** (rule 5) lowered to POSSIBLY ELIGIBLE, each with the
   missing fact named: ICANN Fellowship (interest in ICANN's work), Mandela Washington Fellowship (exact age 25-35 and
   a record of accomplishment; the cycle is closed), Stipendium Hungaricum (the DRC authority's nomination, which
   the FAQ says is required), Nasser Fellowship (the criteria list decision-makers, programme alumni, activists and
   youth-council heads), plus the two found above (Global Leadership Challenge, Jim Leech). LIKELY ELIGIBLE records
   fell from 15 to 8.
9. **ICANN Fellowship**: the page lists the ICANN89 Policy Forum round (5 Nov to 5 Dec 2026) as open only to
   Fellowship alumni; the ICANN88 round (Lisbon, March 2027) is closed. The record already said so; recorded for completeness.

## Re-verified independently (pages opened in this run)

Text matched the records, except where listed above.

| Record | Pages read |
|---|---|
| Raisina PCNS (closes today 17:00 Casablanca) | policycenter.ma call page |
| Global Leadership Challenge (5 Nov) | leadership-challenge.org/applynow |
| Fortis Fellowship (8 Nov) | fortissociety.org/fellowship (the `/faq` address is a 404; the FAQ is on the same page) |
| USTC Winter Camp (8 Nov, UTC+8, 3000 CNY) | ic.ustc.edu.cn winter camp page |
| Dalai Lama Fellows (11 Nov 22:00 UTC) | dalailamafellows.com/apply |
| Kectil (15 Nov, ages 17-26, "provided free") | kectil.com home and who-can-apply |
| AFS Sir Cyril Taylor (19 Nov 23:59 UTC) | youthassembly.org programme page |
| Telemachus (23 Nov) | globalthinkersmentors.org home and mentees page |
| Sciences Po Mastercard (23 Nov / 14 Dec), Boutmy (29 Nov) | three sciencespo.fr pages |
| WFF Youth Policy Board (30 Nov, aggregator date) | call page, form page, Terms of Reference PDF |
| Yenching (30 Nov 09:00 Beijing) | yenchingacademy.pku.edu.cn admissions |
| Jim Leech (1 Dec), Mundus MAPP (1 Dec 23:59 CET), Wageningen (1 Dec) | official pages |
| GLOCAL (14 Jan), Weidenfeld-Hoffmann process page, Obama Leaders ("applications live on November 9", ages 24-45), Türkiye Burslari calendar (general round 10 January - 20 February), AUC fellowship pages, DAAD in-country overview PDF (09/2026; no deadlines in it) | official pages |
| DAAD Helmut-Schmidt call, course and country PDFs; ICANN Fellowship page (ICANN88 closed, ICANN89 alumni only); Nasser criteria; Stipendium Hungaricum Apply page (nomination required, no 2027/2028 call); McKinsey.org Forward FAQ (raw page: "Applications are not open at the moment"; DRC on the Africa list); RLC East Africa (ages 18-35, DRC listed, no dates) | official pages |
| One Young World (31 Oct, passed), Pan African University (au-pau.org: "Applications closed on 15/12/2025"; au.int announcements show no 2027-2028 call) | official pages |

## Could not read

- **Google Forms** for Raisina and AFS: HTTP 401 (sign-in required).
- **Microsoft Form** embedded in the WFF Youth Policy Board call page (JavaScript form; no text).
- **sbs.ox.ac.uk** (AfOx Oxford MBA), **rdc.emb-japan.go.jp** (MEXT, Embassy of Japan in the DRC) and
  **coe.int** (World Forum for Democracy youth delegation): HTTP 403 to both readers. Not retried. The three records
  stay NEEDS VERIFICATION.
- **iucea.org**: connection reset by peer (curl error 35). **UNHCR Rwanda** copy of the EACSP detailed call: HTTP 403.
- **nm-aist.ac.tz** EACSP call PDF: 404 at the address a search result gave.

## New records

| id | Deadline | Funding | Eligibility | Verification |
|---|---|---|---|---|
| `eacsp-iucea-kfw-masters-scholarship-2026-cohort-4` | none open (cohort 4 closed 10 Sep 2026, 17:00 EAT) | Substantially Funded | POSSIBLY ELIGIBLE | PARTIALLY VERIFIED |
| `youth-global-forum-2027-paris-cgdl` | 18 Nov 2026 (the organiser's other page says 20 Nov) | Funding Unclear | POSSIBLY ELIGIBLE (to apply) | NEEDS VERIFICATION, source confidence LOW (warning) |
| `mastercard-foundation-scholars-mcgill-2027` | none open (Fall 2027 cohort closed; next cycle "Spring 2027") | Fully Funded | POSSIBLY ELIGIBLE | VERIFIED |
| `mastercard-foundation-associates-program` | rolling, no closing date | Funding Unclear (a stipend, amount not stated) | POSSIBLY ELIGIBLE | PARTIALLY VERIFIED |

- **EAC Scholarship Programme (EACSP), Phase II, cohort 4** (IUCEA, with the East African Community and Germany's KfW).
  A two-year, funded master's in an EAC country other than your own, open to nationals of the eight EAC states,
  **the DRC named explicitly**, age below 35, bachelor's with Second Class Upper Division or equivalent. Package: return
  economy ticket, full tuition, EUR 380 a month, EUR 200 on arrival, EUR 650 materials, EUR 1,500 research allowance,
  insurance, visa or entry fee. The programme table has business-related master's (MBA and HR management at KCA
  University, logistics and supply chain at Kibabii University, taxation at the University of Rwanda, innovation and
  entrepreneurship management at NM-AIST, economics at Daystar). The cohort 4 window ran 20 August to 10 September 2026,
  so nothing can be applied for today; the record is there to watch for the next cohort. The call was read on the
  University of Dar es Salaam copy of the PDF (the IUCEA site reset the connection and the UNHCR Rwanda copy gave 403),
  hence PARTIALLY VERIFIED, Institutional source. It does not say "fully funded", so the label is Substantially Funded.
- **Mastercard Foundation Scholars Program at McGill** (master's, Montreal). The DRC ("Congo (Democratic Republic)") is on the
  eligible list; 35 awards a year across 13 programmes; the FAQ says the scholarship "covers not only full tuition but all
  costs related to attending McGill" (tuition, on-campus housing, monthly stipend, immigration support). Only **Public Policy**
  is an evident fit (the others are agriculture, nutrition, engineering, public health, statistics). Criteria include never
  having registered for a master's, age 35 or under, a valid passport, a record of service and leadership, and financial need.
  The Fall 2027 cohort is closed (the 1 December 2026 date an aggregator quotes is only for candidates who already received a
  fee waiver); McGill says to watch for the next recruitment cycle in Spring 2027. Read in full on mcgill.ca, hence VERIFIED.
- **Mastercard Foundation Associates Program** (12-month paid work placements). The official page: open to alumni and
  "young people across Africa", apply for roles in your country of residence or remote roles, "a stipend is provided",
  roles posted on an ongoing basis, **Francophone Africa route "Closed for Applications"**. Age (18-35), experience (0-2 years)
  and the stipend amount come from aggregators only and the DRC is not named, so PARTIALLY VERIFIED, Funding Unclear.
  Worth a look because a paid year of experience would unblock the two-year work rules of ARES, Swedish Institute and others.
- **Youth Global Forum 2027, Paris** (CGDL, Toronto). Aggregators sell it as "Fully Funded". The organiser's own pages
  show 30 fully funded and 40 partially funded seats out of 250, a **USD 16.99 registration fee for the funded
  categories that is "mandatory, non-refundable, and cannot be disputed under any circumstances"**, airfare for fully funded
  delegates reimbursed only "after the event" (4 to 8 weeks), the visa "solely the delegate's responsibility", paid seats at
  USD 399 to USD 999.99 and two different funded deadlines (18 and 20 November). Published only as a warning (LOW).

10. **ARES international training scholarships** (earlier cycles: "ARES pages return empty content", PARTIALLY VERIFIED,
   INSUFFICIENT INFORMATION). The ARES page now reads with a plain request: deadline 18 September 2026 (official), "Prochain
   appel : Aout 2027", the DRC ("RD Congo") is on the list of 32 countries, the scholarship covers international travel, a
   subsistence allowance, registration fees, visa costs and insurance, and the applicant must show **two years of relevant
   professional occupation after the last diploma**. The profile records under one year, so the label is now NOT ELIGIBLE
   (today), the record VERIFIED and Substantially Funded. Trainings include a specialisation bachelor in Digital Integrated
   Supply Chain and masters in International and Development Economics and in Microfinance.

11. **Funding labels the organiser's own wording does not support** (rule 4), found by auditing every Fully Funded record:
    - **Mundus MAPP**: the official financial-aid page says only "a limited number" of EMJM scholarships go to the
      highest-ranked applicants, EUR 1,400 a month (maximum EUR 33,600) that must also cover travel, visa and
      installation, a full tuition waiver, and that the scholarship "does NOT cover" the Study Visit and Winter School
      (EUR 600-1000 each) or travel and visa costs to the consortium countries; applicants are told to seek external
      funding too. Relabelled **Substantially Funded** (it was Fully Funded, verified 29 October).
    - **GLOCAL Erasmus Mundus**: the scholarship page lists tuition, insurance, an "optional contribution" to travel and a
      monthly allowance (EUR 1,400, or EUR 1,275 after three EUR 1,000 advances) and never says fully funded: now
      Substantially Funded. All three official pages now agree on 14 January 2027, 13:00 UK time. The Glasgow
      country-grade page has no entry for the DRC, so the grade rule for a Congolese Licence is unpublished.
    - **DAAD In-Country/In-Region**: the official page says the scholarship "usually includes" tuition, a monthly rate,
      allowances and, for In-Region scholars only, travel and insurance: now Substantially Funded.
    Still labelled Fully Funded and left as they are because the pages give comprehensive wording or itemise it: Gates
    Cambridge, Mastercard Foundation Scholars (Cambridge, Edinburgh, Sciences Po, McGill), Knight-Hennessy, Mandela Rhodes,
    Schwarzman, VLIR-UOS, Yenching, Chevening (organiser wording "fully-funded", components not itemised), Kectil.
    **To review by hand** (label may be generous): Tony Elumelu (a USD 5,000 seed grant, no travel), Swedish Institute
    (not eligible anyway; its page says insurance is not included).
12. **Chevening**: the DRC page confirms the 2027-2028 round is closed and adds a cost the record did not carry: there is no UK visa
    processing centre in the DRC, so a scholar travels to another country for the visa and the TB test at their own cost,
    with only a discretionary reimbursement.

## Searches run (English, French, Portuguese, Spanish) and what they found

Twenty-eight standard searches in total (eight first, then twenty follow-ups) (youth summits, fellowships naming the DRC, 2027 master's scholarships,
funded internships, study tours, embassy and government programmes, Atlantic Dialogues, AMCI Morocco, EAPD Egypt,
Enabel, PEC-PG Brazil, AECID Spain). Results were mostly aggregator pages, so only items checked on an organiser's
page became records. Nothing new and open was found in Portuguese or Spanish.

- **Closed, so not recorded:** Mandela Washington Fellowship 2027 (13 Oct; already a closed-cycle record), Atlantic
  Dialogues Emerging Leaders 2026 (14 June; PCNS page marked CLOSED), WTO Young Professionals Programme 2027 (May 2026,
  also needs an advanced degree and age 32 or under), AfDB internship session 1 2027 (12 Oct; needs a master's),
  African Union Continental Capacity Building programme (27 Feb 2026), AECID Africa-Med Master (July 2026),
  AMCI Morocco 2026-2027 (14 July 2026, per a guide; nothing yet for 2027-2028).
- **Not eligible by nationality:** WACSI Next Generation Internship 2027 (fully funded, flights and stipend, closes 8 November, but
  its own page seeks interns from Benin, Mali, Cameroon, Chad, Ghana and Nigeria).
- **Not a fit:** AU Enterprise Africa Network Fellowship cohort 2 (au.int; for registered businesses with two years
  of operation and three full-time staff; the profile records no business), Mastercard Foundation Associates programme
  (DRC not named in any result), YouthConnekt Africa Summit 25-27 November in Kigali (no sponsorship wording found),
  Youth Ambassadors Africa (ages 15-18), Learn Africa / Fundación Mujeres por África (women only), KfW EAC is
  recorded above.
- **PEC-PG Brazil 2027:** no official edital found; guides disagree on dates. Not recorded.
- **Also searched without a result that fits:** GKS graduate 2027 (not yet published; a February to March window is only an
  aggregator guess), AUF mobility grants (no 2027 call; members' students only), Erasmus+ youth exchanges (no call naming the
  DRC), COP31 youth delegations (AYFICE closed 5 October; COY21 Antalya 5-7 November, travel not stated), ECOWAS and AfDB
  paid internships (closed; wrong region or need a master's), UNICEF internships (recent graduates under two years), CorpsAfrica
  (no DRC programme found), MIT-Zaragoza African Supply Chain scholarships (zlc.edu.es answers HTTP 403, so nothing can be
  recorded; an aggregator quotes 15 April), McCall MacBain (closed), UBC Mastercard (closed 6 September).

## Updated records

See "What the first pass missed". Records re-read with only a new `last_verified` date: Yenching, Sciences Po
Boutmy and Mastercard, WFF Youth Policy Board, GLOCAL, Obama Foundation Leaders.

## Action queue (unchanged except where noted above)

1. **Today 5:00 pm Casablanca (16:00 UTC): Raisina** - only if 28 to 35 with a leadership record.
2. **By 5 Nov: Global Leadership Challenge** - rolling review; now POSSIBLY ELIGIBLE.
3. By 8 Nov: Fortis; USTC only if the 3000 CNY fee is acceptable.
4. 9 Nov: Obama Foundation Leaders opens (page: "Applications live on November 9!"; no year on the page).
5. By 11 Nov 22:00 UTC: Dalai Lama Fellows. By 15 Nov: Kectil (ages 17-26).
