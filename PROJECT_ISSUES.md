# Contact Form Filler — Identified Issues & Remediation Plan

## 1. Critical Bugs

| ID | Issue | Location | Impact | Proposed Solution |
|---|---|---|---|---|
| **CRIT-01** | Duplicate `run_campaign_pipeline` definition | `backend/fastapi_backend.py` (lines 837 & 1026) | The second definition silently shadows the first, ignores `max_websites`, skips `cluster_websites`, and omits `campaign_field_strategy` handling. | Consolidate into a single well-structured `CampaignService.run_pipeline()` method. |
| **CRIT-02** | Broken `MySQLDB` import in `/api/test-email` | `backend/fastapi_backend.py` line 1357 | `from dbmysql import MySQLDB` raises `ImportError` because `MySQLDB` lives in `form_filler.py`, crashing test emails with HTTP 500. | Refactor DB access into `database/connection.py` and update `EmailNotifier` to use standard DB sessions/connections. |
| **CRIT-03** | Wrong dictionary key in `/api/fill-form-template` | `backend/fastapi_backend.py` line 626 | Reads `c.get("fieldprevalence")` instead of `c.get("field_prevalence")` returned by `auto_concept_mapper.get_concept_details()`, forcing all concepts into `commonFields`. | Fix key lookup to `field_prevalence` and return standardized Pydantic schemas. |
| **CRIT-04** | Campaign sender/strategy values ignored during filling | `backend/form_filler.py` (`process_website_inner`, `normalize_websites_input`) | `fastapi_backend.py` passes `sender_name`, `sender_email`, `subject_line`, `message_body`, and `campaignid`, but `form_filler.py` discards them and always pulls from `RandomValuePool` or hardcoded fallbacks. | Pass `campaign_id` and resolved field strategies/values into `run_batch()` / `process_website_inner()` so constant/custom/random strategies work as configured. |
| **CRIT-05** | False-positive `"success"` on unknown POST response | `backend/form_filler.py` lines 1786–1788 | Reports `status = "success"` with `"Unknown response (best-effort success)"` even when response content is ambiguous. | Mark ambiguous responses without clear confirmation (`success: true` or `SUCCESS_TEXT_RE`) as `unconfirmed` / `manual_review` instead of `success`. |
| **CRIT-06** | Missing `/health` endpoint | `backend/fastapi_backend.py` | `run_server.py` advertises `http://localhost:8000/health`, but no route exists (returns 404). | Implement `GET /health` and `GET /api/health` checking API and MySQL connectivity. |

---

## 2. Backend Issues
- **BACK-01 — No duplicate-run guard**: `POST /api/campaigns/{id}/start` unconditionally creates a new `campaign_runs` row and launches a background task even if the campaign is already `running`. *Solution*: Enforce state transitions and reject concurrent starts on the same campaign with HTTP 409.
- **BACK-02 — Broken Pause/Resume/Restart semantics**: `pause` sets `campaigns.status = 'paused'`, while `restart` and `continue` both call `start_campaign()` which starts from index 0 in a new run. *Solution*: Track per-website campaign execution status (`campaign_websites.status`) so `resume` continues only remaining/pending websites, `restart` resets and reruns, and `cancel` cleanly aborts.
- **BACK-03 — Missing `mysql-connector-python` and `python-dotenv` in `requirements.txt`**: Fresh environments fail to start. *Solution*: Add all required dependencies with pinned compatible versions.
- **BACK-04 — Unstructured `print()` debugging & monolithic file**: `fastapi_backend.py` is 1,389 lines mixing SQL, routes, and async orchestration. *Solution*: Refactor into `app/api/routes/`, `app/services/`, `app/database/`, `app/schemas/`, `app/core/`.
- **BACK-05 — Missing CRUD endpoints for Websites, Field Mappings, and Settings**: No endpoints exist to list/search/add/delete individual websites, view/edit website raw fields, cancel campaigns, delete campaigns, or inspect backend/automation settings. *Solution*: Implement full REST endpoints for all required UI workflows.

---

## 3. Frontend Issues
- **FE-01 — Monolithic legacy HTML**: `frontend/analytics.html` is 2,675 lines of inline HTML/CSS/JS; `frontend/index.html` calls non-existent `/api/stats` and `/api/urls` endpoints. *Solution*: Replace with a modular React + TypeScript + Vite + Tailwind + shadcn/ui application.
- **FE-02 — Hardcoded `APIBASE`**: `http://127.0.0.1:8000/api` is hardcoded in `analytics.html` and `campaign_details.html`. *Solution*: Centralize API client using `VITE_API_URL`.
- **FE-03 — Aggressive polling & full re-renders**: `index.html` and `campaign_details.html` poll every 1.2–2s regardless of campaign state. *Solution*: Use React Query with smart polling (only when a campaign is active).

---

## 4. Database Issues
- **DB-01 — Hardcoded credentials**: `DBCONFIG` in `fastapi_backend.py` and `dbmysql.py` hardcodes `user="root"`, `password=""`, `database="form_insights"`. *Solution*: Load via environment variables (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`).
- **DB-02 — No connection pooling**: Every request opens and closes a new raw `mysql.connector.connect()` connection. *Solution*: Use `mysql.connector.pooling.MySQLConnectionPool` with context-managed connection/cursor helpers.
- **DB-03 — `campaigns.status` ENUM mismatch**: `form_insights (2).sql` defines `status` as `enum('draft','running','completed','paused','error')`, lacking `queued`, `failed`, `cancelled`. *Solution*: Provide a safe non-destructive migration (`ALTER TABLE`) to support all required states (`draft`, `queued`, `running`, `paused`, `completed`, `failed`, `cancelled`).
- **DB-04 — Missing per-website campaign tracking**: `campaign_websites` lacks `status`, `error`, and `processed_at`, making per-website live monitoring and safe resume impossible. *Solution*: Add migration columns to `campaign_websites` (`status`, `submission_id`, `error`, `processed_at`).
- **DB-05 — Duplicate/legacy tables**: `formsubmissions` vs `form_submissions`, plus unused SQLite DBs in `data/` and `backend/`. *Solution*: Standardize on the active MySQL tables while preserving all existing records.

---

## 5. Automation Issues
- **AUTO-01 — No `campaign_id` saved in `form_submissions`**: `db.save_submission()` never writes `campaignid` even though the column exists in `form_submissions`. *Solution*: Pass and persist `campaign_id` in `form_submissions`.
- **AUTO-02 — `already_processed()` blocks campaign reruns when `ALLOW_RERUNS=False`**: `form_submissions` has a unique index on `normalized_url`, which prevents testing or running a second campaign against the same URL. *Solution*: Scope campaign deduplication per `(campaign_id, website_id)` and handle `INSERT` gracefully without losing audit history.
- **AUTO-03 — Browser lifecycle & crash recovery**: A browser crash inside `run_batch` aborts the entire campaign without updating per-website status. *Solution*: Wrap browser operations in a `PlaywrightManager` with proper cleanup, per-website error isolation, and configurable timeouts/retries.
- **AUTO-04 — `POST_SUBMIT_WAIT_MS` fixed sleep**: Always sleeps 8s after clicking submit even if a POST response arrives immediately. *Solution*: Keep configurable timeout while still capturing responses cleanly.

---

## 6. UI/UX Issues
- **UX-01**: Outdated gradient styling, inline alerts (`alert()` / `confirm()`), emoji-heavy navigation, and poor mobile responsiveness in `analytics.html` and `campaign_details.html`.
- **UX-02**: No multi-step Campaign Creation Wizard with explicit review & approval before launching.
- **UX-03**: No Website Details view to inspect/correct discovered field mappings, no dedicated Submissions detail drawer, and no Recharts-based Analytics page.
- *Solution*: Complete SaaS-grade UI redesign inspired by Linear, Stripe, and Vercel.

---

## 7. Security Issues
- **SEC-01 — Wildcard CORS with credentials**: `allow_origins=["*", ...]` combined with `allow_credentials=True`. *Solution*: Restrict `CORS_ORIGINS` via environment variable to approved frontend origins.
- **SEC-02 — No SSRF / URL validation**: Arbitrary URLs (including `localhost`, `127.0.0.1`, `169.254.x.x`, `10.x.x.x`, `file://`) can be submitted for Playwright scraping. *Solution*: Implement URL validation blocking private/loopback/link-local IPs unless explicitly enabled for controlled local testing (`ALLOW_LOCALHOST_TESTING=true` in dev).
- **SEC-03 — Plaintext SMTP password in `email_config` & unescaped HTML in email body**: `EmailNotifier._build_email_html()` interpolates `website_url` and `filled_values` directly into HTML without `html.escape()`. *Solution*: Escape all interpolated values in HTML emails and never return raw secrets in API responses.
- **SEC-04 — Missing `.gitignore` and `.env.example` gaps**: Risk of committing `.env`, logs, and SQLite/screenshot artifacts. *Solution*: Add comprehensive `.gitignore` and `.env.example`.

---

## 8. Performance Issues
- **PERF-01 — N+1 queries in `/api/websites-with-fields`**: Executes 1 query per website to fetch `raw_fields`. *Solution*: Fetch all fields for the paginated website IDs in a single `WHERE website_id IN (...)` query.
- **PERF-02 — Full-table scans on `raw_fields` and `websites`**: `/api/websites` runs 6 separate `COUNT(*)` queries per dashboard load. *Solution*: Combine into efficient aggregate queries and add pagination/filtering on list endpoints.
- **PERF-03 — Sequential single-URL Playwright launches**: `run_campaign_pipeline` calls `scrapeallforms` and `fillallforms` one URL at a time, launching and closing Chromium for *every single website*! *Solution*: Reuse a single browser/context per campaign run (or bounded concurrency semaphore) via `PlaywrightManager`.

---

## 9. Maintainability Issues
- **MAINT-01 — Cluttered `backend/` directory**: Over 50 ad-hoc debug/fix/backup scripts (`fastapi_backend_broken.py.bak`, `fix_*.py`, `check_*.py`, `*.txt`, `*.log`) mixed with production code. *Solution*: Archive obsolete diagnostic scripts into `archive/` once verified unused.
- **MAINT-02 — No automated test suite**: Test files in `backend/test_*.py` are ad-hoc scripts, not a `pytest` suite. *Solution*: Add `backend/tests/` with `pytest` unit and API integration tests.
