# Progress of the 2026-11-19 research cycle

Run locally in an isolated clone (no remote, nothing pushed). Cycle date 2026-11-19; the merge steps run on
2026-11-21 because usage limits stopped the workers twice (19 Nov ~16:20 UTC and ~19:00 UTC).

## Stage 0 - scouting (stopped by usage limits, not finished) - 2026-11-21 11:05 UTC

| Batch | New records | Patches | Lead outcomes | State when stopped |
|---|---|---|---|---|
| A | 0 | 3 (evidence backlog) | 12 | watchlist in progress; search phrases not run |
| B | 1 | 1 | 12 | evidence backlog 1 of 3; EEAS page, watchlist, search phrases not run |
| C | 0 | 1 | 8 | evidence backlog 1 of 3; open_in_browser, watchlist, search phrases not run |
| D | 0 | 2 | 13 | watchlist in progress (UN YPP); search phrases not run |
| E | 0 | 3 (evidence backlog) | 8 | leads 8 of 12; open_in_browser, watchlist, search phrases not run |
| orchestrator (3 helpers) | - | 19 re-verification patches | - | helper 1: 5 of 10, helper 2: 9 of 10, helper 3: 5 of 10 |

Decision (coordinator's instruction of 2026-11-21): no further scouting; judge and merge what is on disk.

## Stage 1 - mechanical gate - done 2026-11-21 ~11:10 UTC

- The 19 re-verification patches were merged into `scouts/orchestrator.json`.
- `judge.py check` on A-E + orchestrator: 30 records (1 new, 29 patches), **0 blocked**, review findings listed for the
  judge (changed deadlines: ned-hurford 2026-11-30 -> 2026-12-07, aspire-leaders '' -> 2027-01-10,
  french-african-foundation '' -> 2026-12-16, mauritius '' -> 2027-01-31; rlc-east-africa funding raised to Fully Funded).
- Literal quote self-check: every evidence quote in every batch is found on its page by the repo reader.
- 37 lead set-asides (25 exclusions, 12 rejections) need a judge CONFIRM.

## Stage 2 - independent judge (3 workers) - started 2026-11-21 ~11:15 UTC

Part 1: A, B, C. Part 2: D, E. Part 3: orchestrator patches. Verdicts are merged into `judge/verdicts.json` as each
part finishes.

- 2026-11-21 ~11:25 UTC: `judge/verdicts.json` holds 21 record verdicts and 16 lead verdicts (parts 1 and 2 have
  judged all their records; part 3 has judged 10 of 19 patches). One RETURN so far (rlc-east-africa: the Fully Funded
  raise is not supported for the next cohort).

- 2026-11-21 ~11:30 UTC: judge parts 1 (A-C) and 2 (D-E) finished and merged. Records: 7 ACCEPT, 3 DOWNGRADE
  (fao-internship, tony-elumelu, afs-youth-assembly), 1 RETURN (rlc-east-africa). Leads: 35 CONFIRM, 2 OVERTURN
  (CEFOREP: text only in an aggregator JPG; FirstRand: page unreadable on 21 Nov). Part 3 still running.

- 2026-11-21 ~11:45 UTC: part 3 (19 orchestrator patches) finished: 17 ACCEPT, 2 DOWNGRADE (abe-initiative-jica,
  erasmus-mundus-joint-masters-2027).
- RETURN round for rlc-east-africa: the orchestrator applied the judge's correction in `scouts/B.json` (funding_type
  kept "Funding Unclear", coverage back to "Not specified", FAQ cost lines marked YALI-era with arrangement Unknown,
  English criterion UNKNOWN); `judge.py check` on B: 0 blocked; a fresh judge re-read the three pages: DOWNGRADE (one
  potential issue added). The round-2 verdict replaces the RETURN in `judge/verdicts.json`.

## Stage 3 - judge.py apply - done 2026-11-21 ~11:55 UTC

`judge/verdicts.json`: 30 record verdicts, 37 lead verdicts. `judge.py apply`: accepted 24, downgraded 6, returned 0,
rejected 0, unreviewed 0, blocked 0, quote_failed 0, refused_changes 0, evidence_dropped 0 -> `accepted.json`
(30 records, 11 with evidence blocks).

## Stage 4 - upsert.py - done 2026-11-21 (ran ONCE; do not re-run)

`upsert.py research/2026-11-19/accepted.json`: 1 added, 29 updated, 81 records in the database, 194 change-log
entries (all dated 2026-11-21 in `data/changelog.json`), 11 evidence files written (`data/evidence/`).

## Stage 5 - judge.py apply-leads - done 2026-11-21 (ran ONCE)

applied 51, held_for_review 2, unknown_lead 0, invalid 0. Lead statuses (306 leads): NEW 253, EXCLUDED 23,
REJECTED 12, NOT CURRENTLY OPEN 8, OFFICIAL SOURCE FOUND 3, PUBLISHED 3, UNDER REVIEW 2 (CEFOREP 86b033db176d,
FirstRand f22d8bda4926: judge OVERTURN), RECURRING PROGRAMME 1, VERIFICATION REQUIRED 1. The pladis exclusion
(101bf610f9ba) was applied because both judge quotes were `found` by the gate's live re-read (re-checked afterwards:
found).

## Stage 6 - validate.py - done 2026-11-21

`validate: 81 live records, 13 archived, 0 errors, 4 warnings, 13 evidence files`. Warnings: chevening (Fully Funded
without an itemised Covered component; record not touched this cycle), youth-global-forum-2027-paris-cgdl (stored
status CLOSING SOON vs computed DEADLINE PASSED; refresh recomputes it), evidence-nationality-not-drc on
fao-internship and internet-society (answered by judge part 1; see the report).

## Stage 7 - unit tests - done 2026-11-21

`python -m unittest discover -s tests` (Python 3.14.7): Ran 221 tests, OK. Integrity report in the test output:
lost 0, fact-changed 25, added 1. data/ hashes identical before and after the test run.

## Stage 8 - refresh.py --no-network - done 2026-11-21

`refresh: 81 live, 14 archived, 1 lifecycle changes, 0 new leads, 15 flags`. The lifecycle change: the closed cycle of
global-leadership-challenge-2026 (deadline 2026-11-05) was snapshotted to `archive/archive.json` and the live record
rolled forward to 'next cycle not announced'. Re-validation: 0 errors, 3 warnings. `reports/latest.md` and
`data/meta.json` regenerated.

## Stage 9 - report - done 2026-11-21

`reports/2026-11-19-research.md` written (the 7 sections of the final message plus the AGENTS.md step-9 contents).

## Cycle complete

Nothing committed, pushed or published; no remote. Not done (see the report's limits): unfinished scouting per channel,
11 re-verifications not written, search phrases not run. Do not re-run `upsert.py` or `apply-leads` on this date's files.
