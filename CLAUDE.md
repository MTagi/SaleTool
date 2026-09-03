# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SaleTool / "ABIM Sales Assistant": from a search-criteria file, find matching companies
(via Apollo.io — **never** by scraping linkedin.com), pull their senior contacts, enrich them
from their own websites, rank them against your service catalog, and draft outreach messages.

Python backend (FastAPI + Click CLI) + React SPA in `frontend/`.

## Language convention

**Code comments, docstrings and commit messages are in Vietnamese. Everything user-facing is
in English** — API error `detail` strings, job error messages, and the whole React UI. Follow
this split when adding code; don't translate existing Vietnamese comments to English.

Comments here explain *why*, often at length, and frequently record a decision that was
reversed or a trap hit in production. Read them before changing the code they sit on.

## Commands

```bash
# Backend deps (requirements-dev.txt pulls in runtime + mongo + test deps)
pip install -r requirements-dev.txt

pytest                              # backend tests
pytest tests/test_apollo_provider.py::test_more_than_one_page_is_fetched   # single test
ruff check .                        # lint (config in pyproject.toml)
ruff check . --fix

# Run the API (see "Required env vars" below — the server is broken in subtle
# ways without them)
python -m saletool.cli web create-user --username demo
python -m saletool.cli web serve --host 127.0.0.1 --port 8000

# CLI pipeline, no web UI
python -m saletool.cli search --config examples/search_criteria.example.yaml --output output.csv
python -m saletool.cli search --config ... --no-reveal-emails   # survey without burning Apollo credits

cd frontend && npm install && npm run dev     # http://127.0.0.1:5173, proxies /api/* to :8000
cd frontend && npm run lint                   # oxlint
cd frontend && npm run build                  # also serves as the frontend "test"

# Docker (see docs/docker.md). Needs SALETOOL_SECRET_KEY in .env or compose
# aborts by design; nginx serves the SPA and proxies /api/* to the backend.
docker compose up -d --build                  # http://localhost:8080
docker compose run --rm backend python -m saletool.cli web create-user --username demo
docker compose --profile mongo up -d          # also set SALETOOL_DB_BACKEND=mongo
docker compose --profile searxng up -d        # Settings -> instance URL http://searxng:8080
```

## Required env vars

The project does **not** load `.env` — export variables in the shell that runs the command.

- **`SALETOOL_SECRET_KEY`** — must be stable across restarts. Unset, the server mints a
  throwaway key each boot: all JWTs are invalidated *and* every API key saved in Settings
  becomes undecryptable, because the Fernet key is derived from this value via HKDF
  (`saletool/crypto.py`). Changing it = users must re-enter their API keys.
- **`PYTHONIOENCODING=utf-8`** on Windows — cp1252 console can't encode the Vietnamese CLI
  output. `create-user` succeeds and *then* raises `UnicodeEncodeError` while printing.
- `APOLLO_API_KEY` for the CLI only. The web UI reads the Apollo key from Settings, where it
  is stored encrypted; `/api/search` no longer accepts it as a form field.
- `SALETOOL_DB_BACKEND` (`sqlite` default | `mongo`), `SALETOOL_DB_PATH`, `SALETOOL_MONGO_URI`.

## Architecture

### The five-step chain

Each step consumes the previous one's output; this ordering is the core design, mirrored by
the 5-step bar in the UI:

```
1 Search    saletool/pipeline.py + providers/apollo.py  -> SearchRun in DB
2 Enrich    saletool/enrichment/                        -> CompanyEnrichment
3 Catalog   saletool/api/routes/catalog.py              -> Service[] (your own offerings)
4 Match     saletool/matching/                          -> ranked CompanyMatch[]
5 Message   saletool/messaging/                         -> GeneratedMessage[]
```

Steps 4 and 5 *degrade* rather than fail when an earlier step was skipped — matching without
enrichment scores on search data only (and the prompt tells the model to cap its confidence),
messaging without matching loses the "why I'm reaching out" opener. `saletool/api/jobs.py`
wires this together: `_collect_enrichments()` re-reads recent enrich jobs to build the index
both matching and messaging consume.

### Cost/reliability layering (the recurring design principle)

Two pipelines are built as cheap-and-exact-first ladders where **earlier layers are never
overwritten by later ones**:

- **Enrichment** (`enrichment/pipeline.py`): (0) JSON-LD/meta/mailto/regex → (1) sitemap +
  shallow crawl → (2) web search, optional → (3) LLM, only for fields still empty. HTML goes
  through `trafilatura` before any LLM call (~40× token reduction). Every value carries
  provenance (`EnrichmentSource`).
- **Apollo** (`providers/apollo.py`): search tells you only *whether* a person has an email;
  revealing it is a separate, **credit-charging** call, batched 10 people at a time and made
  only for people already flagged as having one. `--no-reveal-emails` / the UI checkbox skips it.

### LLM calls: never trust the model's output

`saletool/llm_api.py` is the shared OpenAI-compatible client. It sends
`provider.require_parameters=true` (structured-output support on OpenRouter varies by
*endpoint*, not by model — the same model can work then fail), falls back from `json_schema`
to plain `json_object` on 400/404, and strips ```json fences. Callers **always re-validate
with Pydantic**.

Beyond that, `messaging/pipeline.py::validate_message()` re-checks everything measurable in
code after the model answers — per-channel length limits from `MESSAGE_CHANNELS`
(`models.py`), leftover `[placeholders]`, "as an AI" leakage, recipient name missing. It
surfaces problems next to the text and **never auto-edits**; truncating a sentence is worse
than letting the user fix it. LinkedIn's 300-char cap is a hard platform reject, not a style
preference.

Scoring in `matching/pipeline.py` is deliberately split: the LLM scores each (company,
service) pair, but **totalling and ranking is plain Python** so the order is explainable and
stable between runs. Errored companies sort last, distinct from genuinely low scores.

### Storage abstraction

`saletool/db/base.py` defines the interfaces; `sqlite_repo.py` and `mongo_repo.py` each
implement all of them; `factory.py` picks via `SALETOOL_DB_BACKEND` and imports the
implementation module lazily so `pymongo` stays optional. **Routes and auth never touch a DB
driver directly — always go through `saletool/db/factory.py`.**

The three background job types (enrich, match, message) share one generic
`JobRepository[TSummary, TDetail]`; the named subclasses exist only to give each a distinct
dependency-injection type. Adding a fourth job type means adding models + a subclass, not a
new storage design.

Settings and the service catalog are **system-wide singletons, not per-user**. Search runs
and jobs *are* per-user, and every repo read takes `username` and returns `None` for another
user's row — that scoping is the access control, so keep it when adding queries.

### Background jobs

`api/jobs.py` runs jobs as bare `asyncio` tasks (no Celery/Redis — deliberate for a small
internal tool), capped at 2 concurrent by a semaphore, writing progress to the DB after every
company so the UI can poll a partially-filled table. Known trade-off: **in-flight jobs die on
server restart**. Message jobs additionally keep their request params in the in-memory
`_message_requests` dict, so a restart loses them and the job reports that explicitly.

Frontend polls via `hooks/useJob.js` (2 s interval); all three job types share the same
status/progress shape, which is why one hook covers them.

### Prevalidation over late errors

`GET /api/status` reports what's configured (LLM key, sender profile, catalog size). Matching
and Messages pages read it via `StatusContext`, show what's missing with a link to the fix,
and disable submit — instead of letting the user fill a form and collect a 400. Keep new
prerequisites flowing through `routes/status.py` + `components/Prerequisites.jsx` rather than
adding a new frontend-side check.

Similarly, `GET /api/search/options` serves the seniority list from `models.py::SENIORITY_LEVELS`
so the frontend keeps no second copy. Don't hardcode enum lists in JS.

### Adding a data provider

Implement `CompanyContactProvider` (`providers/base.py`: `search_companies`,
`search_contacts`) and register it in `providers/__init__.py::get_provider`. Routes and
`pipeline.py` need no changes. `mock` and `csv_import` providers existed and were removed —
`git show 4617a41` if you need them back.

## Constraints that are not negotiable

- **No browser automation against linkedin.com**, and no automation on a logged-in Sales
  Navigator session. This is the project's founding decision (ToS + the Proxycurl/hiQ
  outcomes); see `docs/tong-ket.md` Part II. Data comes from Apollo's API.
- Enrichment crawling stays polite by default: honour `robots.txt`, 1 s between requests to
  the same domain, truthful User-Agent. Don't turn these off or add settings that do.

## Environment notes (verified 2026-09-01, this checkout)

- **Do not re-add a `-> None` return annotation to a 204 route.** Combined with
  `from __future__ import annotations`, FastAPI resolves it to `NoneType` (truthy), treats it
  as a response model, and asserts `Status code 204 must not have a response body` — at import
  time, so the whole app fails to start, not just the tests. This bit
  `saletool/api/routes/catalog.py::delete_service` on FastAPI 0.115.5 / Python 3.12; the
  annotation is now dropped with a comment saying why.
- 211 tests pass here; the rest fail only because the active interpreter lacks
  `pytest-httpx`, `mongomock` and `trafilatura` (all listed in the requirements files).
- **Never mint an ordering timestamp with `datetime.now()` — use `saletool/clock.py::now_iso()`.**
  Measured on this machine: 2000 consecutive `datetime.now()` calls yield **2 distinct values**,
  one of them repeated 1333 times. The system clock ticks every ~15.6ms, so any two rows saved
  in the same tick share a `created_at`, and `ORDER BY created_at` then returns them in whatever
  order the engine likes. That used to make `test_get_latest_run` and `::test_list_runs_most_recent_first`
  fail about half the time, and it silently mis-ordered the History list and made `/api/download`
  without a `run_id` hand back the wrong run. `clock.py` issues strictly increasing stamps
  (bumping by 1µs when the clock has not moved); SQLite reads additionally tie-break on `rowid`
  so rows written *before* that fix still come back in insertion order. Mongo has no such
  fallback — its `_id` is a random UUID — so pre-existing Mongo rows with duplicate timestamps
  stay ambiguous.

## Docs

- `README.md` — the fullest description of every feature, and the reasoning behind the Apollo
  filter/credit behaviour. Read it before changing search criteria handling.
- `docs/chay-local.md` — running backend + frontend + self-hosted SearXNG on Windows,
  including the SearXNG patches needed there.
- `docs/tong-ket.md` — a prior session's worklog plus the LinkedIn data-sourcing survey.
  Parts are stale (it references `frontend/src/constants.js`, which no longer exists, and
  the `csv_import` provider, since removed).
