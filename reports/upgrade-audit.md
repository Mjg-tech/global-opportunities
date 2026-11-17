# Upgrade audit (step 0)

Measured on 2026-11-17 against the live repository state (80 live records, 12 archived, 250 leads).
Nothing in `data/opportunities.json`, `archive/archive.json` or `data/profile.json` was changed to
produce this report. Reproduce every number with:

```
python scripts/measure.py --out reports/baseline-2026-11-17.json
python scripts/integrity.py check data/snapshots/baseline-2026-11-17.json
python -m unittest discover -s tests -v
```

## 1. Summary

Discovery loses opportunities at three places, and a fourth limit sits behind them.

| # | Where | Evidence | Effect |
|---|---|---|---|
| 1 | Title filters | 17 of 81 known real programmes (21%) would be rejected if they appeared in a feed under their database title: 13 by the include whitelist, 4 by the audience patterns. | Real programmes never become leads. |
| 2 | Lead cap | `MAX_LEADS = 250` and `leads.json` holds exactly 250. Oldest lead is 28 days old, not the nominal 45; median 15 days. | Leads are silently pushed out by newer ones before anyone reviews them. |
| 3 | Source mix | 247 of 250 leads (98.8%) come from tier-3 aggregators; 3 from one official feed. 4 of 15 feeds returned nothing on 2026-11-17 (HTTP 403, 520, 522, and an empty feed). 3 more returned only items older than 30 days. | Only 5 of 15 feeds produced a new candidate on that day. Official announcements are barely sampled. |
| 4 | Promotion throughput | 41 records were created on 2 Oct; since then 4 to 8 per week. 16 leads were promoted in about 6 weeks. | Even a perfect lead list will not multiply the record count until verification scales (step 3). |

Consequence for the plan: step 1 (lead retention and filters) improves recall and removes silent loss, but
the number of verified records grows mainly through steps 2 (more official sources) and 3 (parallel
researchers plus a judge).

## 2. Findings in detail

### 2.1 Include whitelist (`refresh.py` `INCLUDE`)
The whitelist is a list of English, French, Spanish and Portuguese keywords matched against the title only.
13 known programmes fail it, for example `Knight-Hennessy Scholars`, `Schwarzman Scholars`, and every
`Erasmus Mundus Joint Master ...` title. `scholarship` does not match `scholars`; named programmes whose
titles contain no generic word are invisible to it.
Caveat: the database titles are normalised by the researcher. A feed headline for the same programme
often adds "Scholarship" or "Fully Funded". The 21% is therefore an upper bound for the whitelist and a
proxy, not a measured loss rate.

### 2.2 Audience patterns (`data/profile.json` `lead_filters.exclude_title_patterns`)
Ran against live feeds, 9 titles were rejected on 2026-11-17. Most were right (Nigerian-only calls).
Four were not safe to reject from the title alone:

| Title | Pattern | Problem |
|---|---|---|
| Arab American Leadership Program 2027 in the USA | `american` | The word names the venue, not the applicants. |
| UNIQLO Global Management Program ... undergraduates and postgraduates worldwide (fully funded to Tokyo) | `undergraduates` | The title also names postgraduates. |
| Bayer Foundation Scientific Fellowships ... Master, PhD, and Medical Students | `phd` | The title also names Master students. |
| WIPO IP and Women Fellowship ... young professionals | `women` | `profile.json` records no gender, so excluding on this word infers a fact that is not recorded. |

In the database itself, `American University in Cairo African Graduate Fellowship`, `European Forum Alpbach
scholarship programme`, `Mauritius-Africa Scholarship Scheme 2027` and `Pan African University scholarships`
(a mixed master's and PhD call) are all valid records that the patterns would have deleted.
The rule in `AGENTS.md` and in the upgrade brief is the same: a title alone must not establish ineligibility.

### 2.3 Silent deletion and the cap
`harvest()` drops a lead when it is older than `LEAD_TTL_DAYS` (45), when a record now matches it, or when
it falls below the 250 cut after sorting by `first_seen`. Rejected titles (age, whitelist, exclude list,
audience) are not written anywhere. Nobody can later ask why a title was dropped, or audit whether the
filters are too strict.

### 2.4 Feed health on 2026-11-17

| Feed | HTTP | Items | Usable |
|---|---|---|---|
| African Union announcements | 200 | 10 | 0 (all older than 30 days) |
| Organisation internationale de la Francophonie | 200 | 10 | 0 (9 news items, 1 old) |
| Opportunity Desk | 200 | 10 | 7 new |
| Opportunities for Africans | 200 | 10 | 1 new |
| Global South Opportunities | 200 | 0 | 0 (empty feed) |
| Opportunities for Youth | 403 | 0 | 0 |
| Mladiinfo | 200 | 12 | 0 (all older than 30 days) |
| OYA Opportunities | 200 | 10 | 9 new |
| Opportunities Corners | 200 | 6 | 2 new |
| Opportunites du Monde | 200 | 10 | 2 new |
| Afri-Carrieres | 200 | 10 | 0 (guides and expat advice) |
| Mastere.tn | 520 | 0 | 0 |
| Partiu Intercambio | 200 | 10 | 0 (9 old) |
| Becas para todos | 200 | 10 | 0 (all old) |
| Mas Oportunidades | 522 | 0 | 0 |

One run yields 21 new candidates from 108 feed items. `data/meta.json` records HTTP status per feed
but nothing watches for a feed that stays stale or empty, so dead feeds sit in the list indefinitely.

### 2.5 What the database looks like

* 80 records; continents: Europe 31, Africa 22, Global 8, Asia 7, North America 7, South America 1,
  Oceania 1. No Middle East value exists in the data, and South America and Oceania are close to empty.
* Categories: Scholarship 43, Leadership 28, Travel 20, Fellowship 15, Training 12, Conference 9,
  Internship 5, Exchange 5, Volunteering 3, Entrepreneurship 3. The travel, event and entrepreneurship
  channels named in the brief are thin.
* 38 records are travel funded, 28 with the flight covered; 60 are international travel.
* `recurring` is true on 80 of 80 records, so it carries no information. The cycle model cannot yet tell a
  true annual programme from a one-off.
* 44 of 80 records have an empty deadline (cycle closed or not announced): over half are not actionable today.
* Every record has at least one Official or Institutional source, and every `Fully Funded` record has one.
  This is the main strength to protect.

### 2.6 Tests, validation and automation

* There was no test suite. `validate.py` checks record shape, duplicates and enums only.
* `.github/workflows/refresh.yml` runs `validate.py` but no tests. It is safe: no secrets, no AI.
* `validate.py` currently warns that two stored statuses (`mundus-mapp-2027`,
  `wageningen-africa-scholarship-programme-2027`) differ from the computed status. These are timing
  warnings that the next daily refresh clears; they are not errors.

## 3. What is preserved

Python standard library only; static GitHub Pages; JSON files; all 80 records and 12 archive entries
(snapshotted and checked by `scripts/integrity.py`); `changelog.json`; the anonymous profile; the
official-source rule; per-expense funding coverage; deadline buckets; no applications, payments or messages;
the rule that the daily job never edits a factual field.

## 4. What was added in step 0

| File | Purpose |
|---|---|
| `scripts/integrity.py` | Snapshot and check. Fails if any record or archive entry disappears. Derived fields are ignored. |
| `scripts/measure.py` | Read-only baseline: false exclusions on known titles, live funnel per feed, lead retention. Imports the real filters from `refresh.py`. |
| `data/snapshots/baseline-2026-11-17.json` | Fact fingerprints of 80 live and 12 archived records. |
| `reports/baseline-2026-11-17.json` | Raw measurements behind this report. |
| `tests/benchmark.json` | 85 positive titles (81 from the database, 4 live-feed titles) and 7 negatives. Recall floor 64/85 = 75.3%. |
| `tests/test_lead_filters.py` | Filter behaviour, the recall ratchet, and 6 `expectedFailure` tests for the defects in 2.1 and 2.2. |
| `tests/test_data_integrity.py` | Unique ids, source URLs, Fully Funded evidence, deadline logic, lead shape, privacy checks, no history lost. |

No data file, workflow, front-end file or existing script was modified.

## 5. Step 1: lead retention and filters (done locally, 2026-11-17)

What changed:

1. `scripts/leadfilter.py` holds the filters. `refresh.py` calls it. Numbers (cap, expiry, weights) are in
   `data/lead-rules.json`.
2. Audience words no longer reject. A nationality, "PhD", "undergraduates", a country or a gender word
   lowers the score and adds a flag; a title that lists several levels, or only names a venue, is not
   penalised. The profile records no gender, so a gender word is flagged for checking and costs no points.
3. Only three things reject a title: it is too old, it is a job ad, tender or guide, or it has no
   opportunity word. Each rejection except age is written to `data/lead-audit.json` with its reason.
4. Leads have statuses (`NEW`, `UNDER REVIEW`, ... `ARCHIVED`). The 250 existing leads migrate to `NEW`
   with a score on the next daily run.
5. Nothing is deleted. Expired, published and research-closed leads, and the weakest `NEW` leads above the
   cap of 1500, move to `archive/leads-archive.json`. Leads under review are never archived by the daily job.
   A new item that resembles an archived lead is flagged `recurring:seen-before`.
6. Whitelist widened for named programmes and events (`scholars`, `joint master`, `erasmus`, `cohort`,
   `class of`, `camp`, `courses`, `dialogue`, `programmes`, `volont...`). A feed may set `filter: "none"`.
7. Feed health: consecutive empty or stale runs are counted per feed and shown as an alert after 7 runs.
8. `leads.html` shows score, plain-language flag notes, status, sorting, an audience-flag filter, 100-per-page
   paging and feed alerts. It was checked in headless Chrome at 1280 px and 390 px with no console errors
   and no horizontal overflow.
9. `.github/workflows/refresh.yml` runs `python -m unittest discover -s tests` after validation and before
   anything is committed or published.

Measured before and after (same script, `scripts/measure.py`):

| Measure | Before (baseline) | After |
|---|---|---|
| Known programme titles the filters reject | 17 of 81 (13 whitelist, 4 audience) | 0 of 81 |
| Benchmark recall (85 titles) | 64 / 85 = 75.3% | 85 / 85 = 100% |
| Benchmark negatives (job ads, news, guides) that leak in | 0 of 7 | 0 of 7 |
| Titles set aside on live feeds, 2026-11-17 (excluding too old) | 35 | 26, every one a job ad, tender, guide, news item or report, each logged |
| Titles rejected on audience words | 9 | 0 (5 leads now carry an audience flag and 1 a gender check; the Nigerian-only calls rank last) |
| Lead cap | 250, saturated | 1500, with archive |
| Oldest active lead | 28 days (cap truncation) | no silent loss: everything is active, archived or logged |
| Tests | none | 61 |

Verification: `validate.py` 0 errors; `integrity.py` 0 records lost; 61 tests pass; a mutation test (archiving
disabled in a scratch copy) made 3 harvest tests fail, so the tests do detect lost leads; the full workflow order
(refresh, validate, tests) was rehearsed twice on a scratch copy with live feeds; the second run added 0 leads and
created no duplicates. Python 3.12 (the GitHub runner) is not installed locally; every script and test passes
a 3.12 syntax check, but the first run on GitHub is the real confirmation.

What step 1 does not do. On a typical day the old filters lost only a handful of live titles (35 set aside, of
which 9 were recoverable), so the daily lead count barely changes. The gains are recall on named programmes,
no silent loss, an audit trail, and a ranked list. A large increase in volume has to come from step 2 (more
official sources) and step 3 (parallel researchers and a judge), because the weekly promotion rate is the
bottleneck.

## 6. Risks and open points

* The benchmark measures recall against titles that the researchers chose, not against what feeds publish.
  A better benchmark will come from `reports/baseline-*.json` samples collected over several weeks.
* A permissive filter raises the lead volume. The weekly agent cannot read hundreds of leads. Ranking by
  score and by source tier (step 1) and parallel researchers (step 3) have to arrive together.
* Some official sites block automated readers (HTTP 403, 412, 429). They need the manual-verification
  task already described in `AGENTS.md`, not a workaround.
