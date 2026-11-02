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
| One Young World (31 Oct, passed), Pan African University (au-pau.org: "Applications closed on 15/12/2025"; au.int announcements show no 2027-2028 call) | official pages |

## Could not read

- **Google Forms** for Raisina and AFS: HTTP 401 (sign-in required).
- **Microsoft Form** embedded in the WFF Youth Policy Board call page (JavaScript form; no text).
- **sbs.ox.ac.uk** (AfOx Oxford MBA), **rdc.emb-japan.go.jp** (MEXT, Embassy of Japan in the DRC) and
  **coe.int** (World Forum for Democracy youth delegation): HTTP 403 to both readers. Not retried. The three records
  stay NEEDS VERIFICATION.

## New records

None yet in this checkpoint (discovery continues).

## Updated records

See "What the first pass missed". Records re-read with only a new `last_verified` date: Yenching, Sciences Po
Boutmy and Mastercard, WFF Youth Policy Board, GLOCAL, Obama Foundation Leaders.

## Action queue (unchanged except where noted above)

1. **Today 5:00 pm Casablanca (16:00 UTC): Raisina** - only if 28 to 35 with a leadership record.
2. **By 5 Nov: Global Leadership Challenge** - rolling review; now POSSIBLY ELIGIBLE.
3. By 8 Nov: Fortis; USTC only if the 3000 CNY fee is acceptable.
4. 9 Nov: Obama Foundation Leaders opens (page: "Applications live on November 9!"; no year on the page).
5. By 11 Nov 22:00 UTC: Dalai Lama Fellows. By 15 Nov: Kectil (ages 17-26).
