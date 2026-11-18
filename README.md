# Global Opportunity Intelligence

A personal, self-updating database of scholarships, fellowships, funded programmes, conferences
and travel opportunities, published as a static website on GitHub Pages.

Live site: https://mjg-tech.github.io/global-opportunities/

The site answers one question: which legitimate opportunities can this applicant apply for right
now, what do they require, what do they pay for, where do they take place, when is the deadline
and where is the application?

Every record is checked against the organiser's own page and assessed against one anonymous
applicant profile (`data/profile.json`). Ten well-verified records are worth more here than a
hundred copied from aggregators.

## System architecture

```
Research cycle (AI agent or person)             Daily refresh (GitHub Action, no AI)
  search, read the official page,                 recompute statuses, archive closed cycles,
  write a record, scripts/upsert.py               re-check official pages, harvest feeds
                 |                                              |
                 v                                              v
        data/opportunities.json                    data/leads.json  data/meta.json
        data/changelog.json                        data/watch-state.json  reports/latest.md
                 \                                              /
                  +----------------- git push -----------------+
                                        |
                       .github/workflows/refresh.yml
                                        |
                 static site: index.html, opportunities.html, leads.html
                                        |
                                  GitHub Pages
```

Two loops feed the same files:

| Loop | Runs | May change | May never change |
|---|---|---|---|
| Daily refresh (`scripts/refresh.py`) | every day at 05:17 UTC on GitHub, no secrets | statuses, archive, link and change flags, the list of unverified leads (scored, archived, never deleted) | any fact: deadline, funding, eligibility, URL |
| Research cycle (`AGENTS.md`) | weekly, by an AI agent or by hand | records, through `scripts/upsert.py` | the applicant profile, unless its owner asks |

The site reads the JSON files at load time, so a push to `main` is all it takes to publish.

## Repository layout

```
index.html              dashboard: key numbers, action queue, deadline monitor, charts
opportunities.html      explorer: search, filters, sorting, cards, detail view
leads.html              unverified leads found by the daily refresh: score, flags, paging, feed health
assets/css/style.css    one stylesheet, light and dark
assets/js/app.js        shared: data loading, status rules, badges, cards, detail dialog
assets/js/views.js      the eleven preset views (shared by the dashboard and the explorer)
assets/js/*.js          one script per page
data/opportunities.json the database (live records)
data/profile.json       anonymous applicant profile used for the eligibility labels
data/sources.json       aggregator feeds read daily, feeds rejected, research watchlist
data/source-registry.json  official sources (curated): where each is, how to read it, whether it is active
data/source-state.json  what the daily job learned about each source: last scan, failures, yield (machine-written)
data/scout-queries.json search phrases (en, fr, pt, es) per channel, rotated weekly by the planner
data/leads.json         active unverified leads, each with a status, score and flags (written by the daily refresh)
data/lead-rules.json    retention and scoring numbers for leads (cap, expiry, weights)
data/lead-audit.json    every title the lead filters set aside, with the reason (90 days)
data/meta.json          counts, deadline buckets, feed health, flags (written by the refresh)
data/changelog.json     every change to a tracked field (and to evidence), newest first
data/evidence/<id>.json per-criterion eligibility, funding detail and application cycles of one record
data/watch-state.json   HTTP status and date-line fingerprint of each official page
archive/archive.json    closed cycles and retired records (never deleted)
archive/leads-archive.json  leads that expired, were published, were closed by research, or fell below the cap
research/YYYY-MM-DD/    one research cycle: scouts/ (plan and one file per channel), judge/ (verdicts and report), accepted.json
tests/                  unit tests and the discovery benchmark (python -m unittest discover -s tests)
reports/                latest.md (generated daily), one report per research cycle, one audit per month
scripts/                oplib.py, leadfilter.py, sourcelib.py, sources.py, scouts.py, judge.py, audit.py, evidence.py,
                        cycles.py, upsert.py,
                        validate.py, refresh.py, integrity.py, measure.py (standard library only)
AGENTS.md               runbook for the research cycle
```

## Data structure

`data/opportunities.json` is `{schema_version, updated, opportunities: [...]}`. Each record:

| Field | Meaning |
|---|---|
| `id` | lowercase slug, stable across cycles |
| `title`, `organization`, `overview` | plain-language identity |
| `category[]`, `subcategory[]`, `education_levels[]` | classification used by the filters |
| `country`, `city`, `region`, `continent` | where it takes place |
| `location_type` | International travel, Domestic travel, Remote, Hybrid |
| `delivery_mode` | In-person, Online, Hybrid |
| `program_dates` | when the programme itself runs |
| `application_deadline` | `YYYY-MM-DD`, or empty when no date is confirmed |
| `deadline_utc` | exact moment in UTC when the source gives a time |
| `deadline_text`, `deadline_timezone` | the source's own wording, always kept |
| `opens_on`, `open_now`, `rolling` | opening date; open with no single deadline; rolling admission |
| `recurring`, `expected_next_cycle`, `last_cycle_deadline` | cycle tracking |
| `status` | OPEN, CLOSING SOON, UPCOMING, DEADLINE PASSED, ROLLING, DATE UNKNOWN (derived) |
| `funding_type` | Fully, Substantially, Partially, Travel or Participation Funded, Self Funded, Funding Unclear |
| `coverage{}` | per expense: tuition, stipend, flight, accommodation, meals, visa, insurance, local_transport, each Covered, Partially covered, Not covered, Not specified or Not applicable |
| `funding_details[]`, `participation_fee`, `stipend` | the detail behind the label |
| `travel_funded`, `flight_funded`, `accommodation_funded`, `meals_funded`, `visa_funded`, `insurance_funded`, `local_transport_funded` | booleans derived from `coverage` |
| `eligibility[]`, `nationality_requirements[]`, `age_requirement`, `education_requirement`, `experience_requirement`, `language_requirement`, `other_requirements[]` | who can apply |
| `documents_required[]`, `application_process[]` | how to apply |
| `official_application_url`, `official_information_url`, `source_url` | never invented; empty when not confirmed |
| `source_type`, `source_confidence`, `verification`, `sources[]` | traceability |
| `eligibility_for_me`, `eligibility_reason` | LIKELY ELIGIBLE, POSSIBLY ELIGIBLE, NOT ELIGIBLE, INSUFFICIENT INFORMATION, with a factual reason |
| `relevance{}`, `relevance_reason` | academic, career, travel, networking, funding, accessibility, profile_fit, each Very High to Low |
| `potential_issues[]`, `benefits[]`, `visa{}`, `upfront_cost_risk` | risks and travel analysis |
| `action` | the next step for the applicant |
| `match_keywords[]` | phrases that identify this programme in feed titles (stops duplicates) |
| `last_verified`, `date_discovered`, `notes` | temporal tracking |

Anything that could not be confirmed is written as `Unknown / Not specified`. It is never guessed.

## Research workflow

Discover, collect, verify, classify, check eligibility, analyse funding, assess travel,
prioritise, publish, update. The full procedure is in `AGENTS.md`. In short:

1. Start from `reports/latest.md`: flags, deadlines inside 30 days, programmes seen again in feeds.
2. Re-verify those records on their official pages.
3. Pick promising items from `data/leads.json` and the watchlist in `data/sources.json`,
   find the organiser's own page, and read the deadline, eligibility and funding there.
4. Search beyond the usual scholarship sites, in English, French, Portuguese and Spanish.
5. Write the records to `research/YYYY-MM-DD/*.json` and merge them:
   `python scripts/upsert.py research/YYYY-MM-DD/*.json`
6. `python scripts/validate.py`, write `reports/YYYY-MM-DD-research.md`, commit and push.

## Verification process

| Label | Rule |
|---|---|
| VERIFIED | deadline, eligibility and funding read on the organiser's own page on `last_verified` |
| PARTIALLY VERIFIED | some facts from the official page; the rest from secondary sources, marked in the text |
| NEEDS VERIFICATION | the official page could not be read; everything is from secondary sources |

Rules enforced by `scripts/validate.py` (the publish step fails on an error):

- every record has a `source_url`; VERIFIED requires an official source and URL;
- "Fully Funded" cannot be claimed on a record that still needs verification;
- a LOW-confidence record must list its problems;
- dates are ISO dates, URLs are real URLs, enumerations are closed lists, ids are unique,
  and two records cannot share the same title and organiser.

Scam checks made during research: application or participation fees, organisers that cannot be
identified, unofficial domains, "fully funded" claims that appear only on aggregators, lapsed
domains that now redirect elsewhere. Suspect items are published only with LOW confidence and a
warning, or kept out of the database and noted in the research report.

## Website architecture

Static HTML, one stylesheet, plain JavaScript, no build step and no external requests.
`assets/js/app.js` loads the JSON files, recomputes the deadline status in the browser (so
"days left" is right even between refreshes) and renders cards and the detail dialog with
`textContent` only. Filter state lives in the query string, so any view can be bookmarked.
A detail view can be linked directly: `opportunities.html#o=<id>`.

Run it locally with `python -m http.server` from the repository root.

## How to update the database

```bash
git pull --rebase                      # the daily refresh commits to main
python scripts/upsert.py batch.json    # add or update records (no duplicates, changes logged)
python scripts/validate.py             # must report 0 errors
python scripts/refresh.py --no-network # optional: recompute statuses and reports/latest.md
git add -A && git commit -m "Research cycle YYYY-MM-DD" && git push
```

To retire a record by hand, move it from `data/opportunities.json` to `archive/archive.json`
with an `archive_id` and an `archived_on` date. Do not delete it.

## How to deploy GitHub Pages

The intended setup: the repository's Pages source is "GitHub Actions", and
`.github/workflows/refresh.yml` publishes on every push to `main`, every day at 05:17 UTC and
on demand (Actions tab, "Refresh and publish", "Run workflow").

If `.github/workflows/refresh.yml` is not in the repository yet, Pages serves the `main` branch
directly and nothing refreshes by itself. The workflow file can only be pushed with a token
that has the `workflow` scope. To finish the setup:

```bash
gh auth refresh -h github.com -s workflow
git push
gh api -X PUT repos/<owner>/<name>/pages -f build_type=workflow
gh workflow run refresh.yml
```

To recreate it on a new repository:

```bash
gh repo create <name> --public --source . --push
gh api -X POST repos/<owner>/<name>/pages -f build_type=workflow
gh workflow run refresh.yml
```

Pushing workflow files needs a token with the `workflow` scope.

## Leads

A lead is a title and a link from a feed. It is a pointer, never a fact. `scripts/leadfilter.py`
decides what happens to each feed title:

| Outcome | When | What is kept |
|---|---|---|
| Rejected, counted only | the item is older than `max_item_age_days` (30) | nothing: it is simply old |
| Rejected, logged | the title is a job ad, tender, guide or how-to (`not_opportunity`) | a line in `data/lead-audit.json` |
| Rejected, logged | the title has no opportunity word at all, such as news or a report (`no_opportunity_word`) | a line in `data/lead-audit.json` |
| Lead | everything else | a record in `data/leads.json` with a `score` and `flags` |

**A title alone never rules an opportunity out.** Words such as a nationality, "PhD", "undergraduates"
or "women" lower the score and add a flag (`audience:nationality`, `audience:level-only`,
`audience:country`, `check:gender-term`, `risk:fee-in-title`). A flag is a reason to read the
organiser's page. It can name the venue ("Arab American Leadership Program ... in the USA"), list
several levels ("Master, PhD and medical students"), or describe a group the profile does not record
(the profile stores no gender). A lead is set aside as ineligible only when the organiser's own page
states a requirement the profile cannot meet.

The score (0 to 100) only orders the list. It rises for strong words (scholarship, fellowship,
fully funded), an official feed, an Africa or DRC signal and a recent date, and falls for flags. Its
weights are in `data/lead-rules.json`. `scripts/leadfilter.py` holds the keyword patterns.

**Nothing is deleted.** Lead statuses are `NEW`, `UNDER REVIEW`, `OFFICIAL SOURCE FOUND`,
`VERIFICATION REQUIRED`, `VERIFIED`, `PUBLISHED`, `NOT CURRENTLY OPEN`, `RECURRING PROGRAMME`,
`EXCLUDED - CONFIRMED INELIGIBLE`, `REJECTED - NOT A LEGITIMATE OPPORTUNITY` and `ARCHIVED`. The daily
job moves a lead to `archive/leads-archive.json` when it:

- stays `NEW` for more than `ttl_days` (45);
- becomes a record in the database (status `PUBLISHED`);
- is closed by a research cycle (`PUBLISHED`, `EXCLUDED - CONFIRMED INELIGIBLE`, `REJECTED - NOT A
  LEGITIMATE OPPORTUNITY`), which keeps its status and reason;
- is a `NEW` lead with one of the lowest scores while more than `max_active_leads` (1500) are active.

A lead that a research cycle is working on (`UNDER REVIEW` and the other in-progress statuses) is never
archived by the daily job. A new feed item that resembles an archived lead is flagged
`recurring:seen-before`, which is how a new edition of a known programme is noticed.

A feed in `data/sources.json` may set `"filter": "strict"` (official news streams: keep only titles that
name a call) or `"filter": "none"` (skip the opportunity-word check for a feed that only publishes
opportunities; job ads are still rejected). `data/meta.json` counts, per feed, consecutive runs with no
items or only stale items, and `reports/latest.md` shows an alert after `feed_alert_after_runs` (7).

`lead_filters.exclude_title_patterns` in `data/profile.json` is no longer read. Its owner may remove it.

## Source registry

`data/sources.json` holds aggregator feeds, which find a lot and verify nothing. `data/source-registry.json`
holds **official places**: an institution's call-for-applications page, a youth portal, an embassy feed.
The daily job scans them next to the feeds, and their items go through the same lead filters. An item
from a registry source starts with the `Official` tier, so it ranks above the same title from an aggregator.

Each entry says where the source is (`official_opportunities_url`, `official_domain`), how to read it
(`discovery_method`: `rss`, `atom`, `html`, `sitemap` or `json_api`, with options under `harvest`), which
channel it serves (A institutional, B government and diplomatic, C academic, D professional and
entrepreneurship, E travel and events), how often to look (`priority`: high daily, medium every 3 days,
low weekly), and what was seen when it was verified (`verified_on`, `verification_note`).

| `status` | What the daily job does |
|---|---|
| `active` | scans it; new items become leads |
| `proposed` | scans it as a trial: counts what *would* become leads, stores none (`trial_would_be_leads` in the state file) |
| `manual` | never fetches it. The site refuses automated readers (403, connection reset, time-outs) or lists nothing a scanner can read. A research cycle opens it in a browser |
| `disabled` | ignored |

Rules the scanner follows: `robots.txt` is read first and a disallowed page is not fetched (an
unreachable `robots.txt` means skip the source that day); links must stay on the source's own domain;
nothing is read from a listing except a title, a link and, when the URL carries one, a date; a page that
blocks automated readers is recorded as `manual`, never worked around.

The registry (edited by research cycles) and the state (written by the daily job) are separate files so
a daily commit and a research commit never touch the same file. The state holds, per source: last
check, last HTTP status, items seen, leads created, consecutive failures and a reliability grade
(`HIGH`/`MEDIUM`/`LOW` from the success ratio over the last 60 scans, `UNRATED` before 5). A failed scan is
retried the next day. `scripts/validate.py` checks the registry's structure and warns when an active
source has failed 7 times in a row or has not been re-verified for 180 days.

**Adding a source.** Probe it first: `python scripts/sources.py probe URL` reports robots, HTTP status,
the method it detects, the feeds it advertises, and which items the lead filters would keep, then prints a
draft entry. Add it as `proposed`, let it run a week or two, and set it `active` once its trial yield is
real. `python scripts/sources.py list` shows every source with its latest state. A domain that is
compromised or not what it claims goes in the registry's `rejected` list, which `validate.py` enforces.

## Scouts, judge and audit

The weekly cycle is split by channel so that no one reader has to cover everything, and so that the
reader who writes a record is never the one who approves it.

```
scripts/scouts.py plan   ->  research/DATE/scouts/plan.json     one packet per channel (A-E) + the orchestrator's list
five scouts              ->  research/DATE/scouts/<channel>.json records, lead outcomes, blocked pages, proposed sources
scripts/judge.py check   ->  rules every record must pass       (no network)
the judge                ->  research/DATE/judge/verdicts.json   a decision and a verbatim quote per record
scripts/judge.py apply   ->  research/DATE/accepted.json         only this file goes to upsert.py
scripts/judge.py apply-leads  sets lead statuses from the scouts' outcomes
```

**The planner** gives each channel its registry sources (and the `manual` ones to open in a browser), the best
open leads that belong to it, a slice of the research watchlist and eight search phrases picked from
`data/scout-queries.json`, rotated by ISO week so consecutive weeks differ. The channel of a lead from a
registry source is that source's channel; for an aggregator lead it is a keyword guess used only to split the
work. The orchestrator's list names the records to re-verify (flagged, closing within 30 days) and the
programmes seen again in feeds. `scouts.py` works before and after the daily job has migrated old leads.

**One writer.** A scout never edits `data/` or uses git. Its file is a list of records (a full record or a
patch over a stored one), the outcome for each lead it handled, the pages that blocked it and the sources it
suggests. The orchestrator is the only role that merges and pushes. A weekly routine without the `Agent` tool
runs the same passes one after another in a single session; the mechanical gates below do not depend on it.

**The judge** has three layers and a limited power.

| Layer | What it does | Where it lives |
|---|---|---|
| Rules | checks each record as `upsert.py` would store it (a patch is merged first): cited pages, official URLs that are not aggregators or social pages, VERIFIED backed by an official page on the right host, Fully Funded backed by the organiser, deadline wording and plausibility, LIKELY ELIGIBLE explained, personal data, text that reads like an instruction to an AI, duplicates, and what a patch changes in a stored record. `block` keeps a record out; `review` must be answered by the judge | `judge.py check` |
| Verdict | an AI or a person re-reads each cited page itself and writes `ACCEPT`, `DOWNGRADE`, `RETURN` or `REJECT` with a quote copied from the page | `verdicts.json` |
| Quote check | the quote must literally appear (whitespace, case and typographic marks ignored) on a page the record cites. A page the checker cannot read counts only if the judge declares another reader (`via`) | `judge.py apply` |

The judge may only lower trust: a verification label, a confidence, an eligibility verdict, `funding_type`
to `Funding Unclear`, extra `potential_issues`. It cannot raise anything or edit a fact; a wrong fact is
`RETURN`ed to its scout for one more pass. A record with no verdict is not accepted. A lead set aside as
ineligible takes effect only when the judge confirms it with a quote, because a wrongly excluded
opportunity is the costliest error the pipeline can make. `via` is a declaration, not a proof: the monthly
audit and the report are how it is checked.

**Monthly audit.** On the first Monday of each month `scripts/audit.py sample` draws a reproducible sample
of what the pipeline turned away without a person deciding (titles the filters rejected, `NEW` leads that
aged out). Each page is opened and judged `FALSE_EXCLUSION`, `CORRECT` or `UNCLEAR`; `audit.py record` writes
`reports/audit-YYYY-MM.md` with the false-exclusion rate per stratum, an estimate of how many were missed,
the registry sources that fail or yield nothing, and the titles to add to `tests/benchmark.json`. A
stratum above 10% means a filter or retention rule must change, and the applicant approves changes that alter
what is thrown away.

## Evidence, cycles and views

**Evidence files** (`data/evidence/<record-id>.json`) hold the detail behind a record's one-line verdict.
The record stays the summary; the file adds, each with the page and the sentence it came from:

- *criteria*: one entry per requirement (nationality, age, education, grade, language certificate, enrolment...)
  with the organiser's requirement, the applicant fact used, and `MET`, `NOT MET`, `UNKNOWN` (naming the missing
  fact) or `NOT STATED`;
- *funding*: one entry per expense (tuition, airfare, accommodation, meals, allowance, visa fees, insurance,
  local transport, airport transfers, fees, training, materials) with who pays (`Paid directly by organiser`,
  `Reimbursed after purchase`, `Covered through an allowance`, `Partially covered`, `Not covered`, `Unknown`),
  the amount and currency when stated, the conditions, and `out_of_pocket`;
- *cycles*: earlier and expected editions (`HISTORICAL CYCLE`, `CONFIRMED CURRENT CYCLE`,
  `EXPECTED NEXT CYCLE`, `NOT YET ANNOUNCED`). Cycles accumulate: a new cycle never replaces an old one.

A scout supplies it as the key `evidence` inside a batch record; `scripts/upsert.py` moves it into the file, so
`opportunities.json` stays small and a record never carries it. Rules (`scripts/evidence.py`):

| Rule | What it prevents |
|---|---|
| The verdict can never be higher than the criteria allow | a record saying LIKELY ELIGIBLE with an unknown age, or anything but NOT ELIGIBLE beside a `NOT MET`. LIKELY also needs the nationality rule read |
| An Africa-wide sentence does not prove the DRC | `MET` on nationality needs a quote that names the DRC or says all nationalities, otherwise the judge must answer a `review` |
| The record's `coverage` may not claim more than the funding evidence supports | "flight covered" when the page says nothing about flights |
| An amount needs a currency and a payer | invented or unattached figures |
| A predicted cycle never carries a date | a guess becoming a deadline |
| Every quote must be on the page it cites | the judge's gate (`judge.py apply`) re-reads each page; one quote that cannot be proven drops the whole evidence block, never the record |

**Cycles and "Upcoming to watch".** `scripts/cycles.py` reads each live record, the archived snapshots of its
closed cycles and its evidence cycles, and the daily refresh writes the result to `data/meta.json` under
`upcoming`. It never writes a record. An opening the organiser announced is shown as *Announced*. A programme
with no date but with earlier cycles is shown as an *Estimate*: the next occurrence of the last deadline's
month, labelled with how many earlier cycles it rests on and flagged "read the official page now" inside 90 days.
Recurring programmes with no earlier cycle on record get no estimate. Not-eligible programmes are left out and
counted. The dashboard panel and `reports/latest.md` show the list.

**Views.** The explorer has eleven preset views (`assets/js/views.js`): Recommended, Fully funded, International
travel, Scholarships and fellowships, Conferences and events, Youth and leadership, Entrepreneurship and
innovation, International volunteering, Future opportunities, New discoveries, Needs verification. A view is a
saved question over the same records, opened as `opportunities.html?view=<id>`; it combines with every filter and
is shown with its definition. The dashboard shows each view's count.

**Weekly backlog.** The planner gives each scout up to three live records without criteria
(`evidence_backlog`: open and soonest-closing first, never the ruled-out ones), so the 80 records gain evidence
over a few weeks instead of in one expensive pass. The detail view shows the criteria, funding and cycle sections
only for records that have an evidence file.

## Tests

```
python -m unittest discover -s tests -v       # filters, harvest, deadlines, integrity, privacy
python scripts/integrity.py snapshot data/snapshots/baseline-YYYY-MM-DD.json
python scripts/integrity.py check    data/snapshots/baseline-YYYY-MM-DD.json   # fails if a record disappears
python scripts/measure.py                      # discovery funnel and false-exclusion measurement
```

`tests/benchmark.json` lists real programme titles the lead filters must keep and non-opportunities they
must reject. `recall_floor` is a ratchet: raise it when the filters improve, never lower it. The workflow
runs the tests before it publishes, so a regression stops the deployment.

## How automated research runs

- **Daily, on GitHub, free, no credentials.** `scripts/refresh.py` recomputes statuses, rolls or
  archives closed cycles, re-fetches each official page (HTTP status plus a fingerprint of its
  deadline lines), reads the feeds in `data/sources.json`, and stores new titles as leads
  (status NEW, never treated as verified). Titles that match a known record are reported as
  "seen again" instead of being stored twice. See "Leads" below.
- **Weekly research cycle.** An AI agent follows `AGENTS.md`: an orchestrator re-verifies flagged and
  closing records and hands five channel scouts their work, the scouts promote good leads to
  records after reading the official source and search for new and unusual opportunities, an
  independent judge re-reads every page the records cite, and only what passes reaches the database.
  See "Scouts, judge and audit". It never submits an application, pays a fee, or sends a message.
- **Deadline monitoring.** `data/meta.json` lists the records whose deadline falls within 30, 14,
  7, 3 and 1 days; the dashboard shows the same windows live.

## Privacy

The repository is public. It holds no name, contact details, CV or identity document. The
profile is a short anonymous description (nationality, age band, degree, experience, languages).
Pages carry `noindex` so search engines are asked not to list them.

## Limits

- Some official sites block automated readers. Those records say so and carry a lower
  verification label; a person should open the page in a browser.
- Leads are titles and links from aggregators. They are not checked by the daily refresh.
- Programme rules change. The `last_verified` date on each record says how old the check is.
- Per-criterion evidence exists only for records a scout has worked through (two pilots on 2026-11-18, then
  about fifteen a week). A record without it still shows its summary fields; the detail view says nothing more.
- A cycle estimate repeats last year's month. It cannot know that a programme changed its calendar, which is why
  it is labelled an estimate and always sits beside the organiser's own text.
