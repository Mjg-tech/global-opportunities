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
| Daily refresh (`scripts/refresh.py`) | every day at 05:17 UTC on GitHub, no secrets | statuses, archive, link and change flags, the list of unverified leads | any fact: deadline, funding, eligibility, URL |
| Research cycle (`AGENTS.md`) | weekly, by an AI agent or by hand | records, through `scripts/upsert.py` | the applicant profile, unless its owner asks |

The site reads the JSON files at load time, so a push to `main` is all it takes to publish.

## Repository layout

```
index.html              dashboard: key numbers, action queue, deadline monitor, charts
opportunities.html      explorer: search, filters, sorting, cards, detail view
leads.html              unverified leads found by the daily refresh, feed health
assets/css/style.css    one stylesheet, light and dark
assets/js/app.js        shared: data loading, status rules, badges, cards, detail dialog
assets/js/*.js          one script per page
data/opportunities.json the database (live records)
data/profile.json       anonymous applicant profile used for the eligibility labels
data/sources.json       feeds read daily, feeds rejected, research watchlist
data/leads.json         unverified leads (written by the daily refresh)
data/meta.json          counts, deadline buckets, feed health, flags (written by the refresh)
data/changelog.json     every change to a tracked field, newest first
data/watch-state.json   HTTP status and date-line fingerprint of each official page
archive/archive.json    closed cycles and retired records (never deleted)
research/YYYY-MM-DD/    the raw batch files of each research cycle
reports/                latest.md (generated daily) and one report per research cycle
scripts/                oplib.py, upsert.py, validate.py, refresh.py (standard library only)
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

Already set up. The repository's Pages source is "GitHub Actions", and
`.github/workflows/refresh.yml` publishes on every push to `main`, every day at 05:17 UTC and
on demand (Actions tab, "Refresh and publish", "Run workflow").

To recreate it on a new repository:

```bash
gh repo create <name> --public --source . --push
gh api -X POST repos/<owner>/<name>/pages -f build_type=workflow
gh workflow run refresh.yml
```

Pushing workflow files needs a token with the `workflow` scope.

## How automated research runs

- **Daily, on GitHub, free, no credentials.** `scripts/refresh.py` recomputes statuses, rolls or
  archives closed cycles, re-fetches each official page (HTTP status plus a fingerprint of its
  deadline lines), reads the feeds in `data/sources.json`, and stores new titles as leads
  labelled NEEDS VERIFICATION. Titles that match a known record are reported as "seen again"
  instead of being stored twice.
- **Weekly research cycle.** An AI agent follows `AGENTS.md`: it re-verifies flagged and
  closing records, promotes good leads to full records after reading the official source,
  searches for new and unusual opportunities, and pushes. It never submits an application, pays
  a fee, or sends a message.
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
