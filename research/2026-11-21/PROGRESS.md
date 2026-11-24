# Progress of the 2026-11-21 discovery pass

Second pass on the 2026-11-19 cycle, run locally in the isolated clone (no remote, nothing committed or pushed).
`research/2026-11-19/` is already merged: never run `upsert.py` or `apply-leads` on it again.

Working files outside the repo (helpers, briefs, worker outputs before merge, "before" snapshots of data/):
`C:/Users/Moss/AppData/Local/Temp/claude/af9475e8d07f1710/3d2634a1-435a-4780-bdff-116dc66e5a59/scratchpad/work-2026-11-21/`
(`SCOUT-BRIEF.txt`, `REVERIFY-BRIEF.txt`, `quotecheck.py`, `showrec.py`, `lookup.py`, `prep.py`, `reverify-1.json`,
`reverify-2.json`, later `JUDGE-BRIEF.txt`, `judge-input/`, `verdicts-*.json`).

## Stage 0 - setup - done 2026-11-21 ~17:15 UTC

- `scouts/plan.json` copied unchanged from `research/2026-11-19/scouts/plan.json` (same search phrases, ISO week 47).
- Chrome: `list_connected_browsers` returned no browser, so no browser reads in this pass.
- Leftover leads (plan leads with no outcome in the 2026-11-19 scout files, all still NEW): C aebadcabc2d7,
  52fe64b7db30, cbcee7028ed3, 0ed1cb20bfd3; E 6c461f707486, d0c6f7686795, 292f584eb6ee, e030979e1ea8.
- Re-verifications assigned: helper 1 (`reverify-1.json`): UN YPP posting 285586 (new record or warning),
  wff-youth-policy-board-2027-2028, kectil-program-2027, mandela-washington-fellowship-2027, obama-foundation-leaders,
  si-scholarship-global-professionals, stipendium-hungaricum-2027. Helper 2 (`reverify-2.json`):
  weidenfeld-hoffmann-scholarships-oxford-2027, vlir-uos-icp-connect-2027, european-forum-alpbach-scholarships,
  african-union-youth-volunteer-corps, orange-digital-center-drc, mckinsey-forward-fall-2026,
  objectif-2030-ifdd-free-moocs (the last two plus alpbach, orange and vlir are the 5 LIKELY ELIGIBLE records).
- Workers: at most 3 at a time. Scouts A-E write `scouts/<X>.json` as they go; helpers write `work-2026-11-21/reverify-N.json`,
  merged into `scouts/orchestrator.json` by the orchestrator.

## Stage 1 - scouting and re-verification

- ~17:20 UTC: launched wave 1 (3 workers, lighter model as AGENTS.md allows for scouts): re-verification helper 1
  (UN YPP + 6 records), scout E (4 leftover leads + phrases), scout A (phrases). Queued: scouts C, D, B and helper 2,
  each started when a slot frees up.
- ~18:40 UTC: the account's 5-hour usage limit killed all three workers. Reset at 20:50 UTC; resumed 20:52 UTC.
  State on disk at the stop (all valid JSON, checked 20:55 UTC):
  - `scouts/A.json`: COMPLETE except the closing notes. 14 phrases run (8 plan + 6 own; en 6, fr 4, pt 2, es 2),
    4 new records (african-union-commission-internship-programme, unicef-internship-programme,
    sadc-secretariat-work-integrated-learning-programme, eac-youth-fellowship-ms-tcdc), `judge.py check` 0 blocked,
    every evidence quote `found`. One candidate left unwritten: UN Volunteers (unv.org blocked by an Incapsula bot check).
  - `scouts/E.json`: COMPLETE except the closing notes. 16 phrases (8 plan + 8 own/bank; every language), 0 records,
    5 lead outcomes (the 4 leftover leads + 068fdd54a49a Jeux de la Francophonie), 5 blocked pages.
  - `work-2026-11-21/reverify-1.json`: 6 of 7 items written (un-young-professionals-programme-2026 as a NEEDS
    VERIFICATION / LOW warning, wff, kectil, mandela-washington, obama, si-scholarship); `judge.py check` 0 blocked;
    every evidence quote `found`. stipendium-hungaricum-2027 was not reached: moved to helper 2.
  Decision: A, E and helper 1 are not resumed (nothing left but closing notes); their files are final.
- ~21:00 UTC: launched wave 2 (3 workers): scout C (4 leftover leads + phrases), helper 2 (8 records:
  stipendium-hungaricum-2027 + the 7 above), scout D (phrases). Queued: scout B.
