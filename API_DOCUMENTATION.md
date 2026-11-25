# API Documentation

Base URL: `http://localhost:8000` (Interactive OpenAPI docs available at `/docs`).

## Health & Settings
- `GET /health` & `GET /api/health` — Returns backend and MySQL database connectivity status.
- `GET /api/settings` — Returns system status, app metadata, and active Playwright automation settings.
- `PUT /api/settings` — Updates runtime automation settings (`headless`, `concurrency`, `per_website_timeout_sec`, `action_timeout_ms`, `post_submit_wait_ms`, `polite_delay_ms`, `max_retries`, `dry_run`).

## Websites
- `GET /api/websites` — Aggregate website counts (`total`, `visited`, `formstotal`, `captchatotal`, `deadsites`, `zerofieldsites`).
- `GET /api/websites/list` — Paginated, filterable website list (`skip`, `limit`, `search`, `scan_status`, `form_found`, `has_captcha`).
- `POST /api/websites` — Add a single validated URL (`{ "url": "..." }`).
- `POST /api/websites/bulk` — Bulk import URLs (`{ "urls": [...] }`).
- `POST /api/websites/import-csv` — Multipart CSV upload (`file`).
- `GET /api/websites/export-csv` — Download websites CSV.
- `GET /api/websites/{website_id}` — Detailed website info, `raw_fields`, and submission history.
- `POST /api/websites/{website_id}/scan` — Trigger Playwright discovery scan for a single website.
- `PATCH /api/websites/{website_id}/fields/{field_id}` — Override `cluster_key` on a discovered field.
- `DELETE /api/websites/{website_id}` — Delete a website and its related records.
- `GET /api/websites-with-fields`, `GET /api/dead-sites`, `GET /api/zero-field-sites` — Paginated legacy views.

## Campaigns
- `GET /api/campaigns` — List campaigns (`search`, `status`, `sort_by`).
- `POST /api/campaigns` — Create a draft campaign with target URLs and field strategies.
- `GET /api/campaigns/{campaign_id}` — Full campaign details, per-website statuses, strategies, and `lastRun`.
- `PUT /api/campaigns/{campaign_id}` — Update a non-running campaign.
- `DELETE /api/campaigns/{campaign_id}` — Delete a non-running campaign.
- `POST /api/campaigns/{campaign_id}/duplicate` — Clone an existing campaign as a draft.
- `GET /api/campaigns/{campaign_id}/status` — Live run progress, aggregate counts, and per-website statuses.
- `POST /api/campaigns/{campaign_id}/start` — Start campaign execution (returns `409` if already running).
- `POST /api/campaigns/{campaign_id}/pause` — Pause a running campaign.
- `POST /api/campaigns/{campaign_id}/resume` — Resume remaining `pending` targets in a paused campaign.
- `POST /api/campaigns/{campaign_id}/restart` — Reset all targets to `pending` and start a fresh run.
- `POST /api/campaigns/{campaign_id}/cancel` — Cancel an active campaign.
- `POST /api/fill-all-forms`, `GET /api/fill-status/{job_id}` — Legacy ad-hoc form filling endpoints.

## Submissions & Analytics
- `GET /api/form-submissions` — Paginated submissions (`skip`, `limit`, `status`, `campaign_id`, `search`).
- `GET /api/form-submissions/export-csv` — Export filtered submissions as CSV.
- `GET /api/analytics/overview` — Dashboard & analytics metrics (`days`, `campaign_id`).

## Field Mapping & Random Value Pool
- `GET /api/fill-form-template` — Canonical concepts grouped by prevalence.
- `GET /api/field-frequency`, `GET /api/field-mapping` — Aggregate field counts.
- `GET /api/field-mappings/details` — Paginated `field_concept_map` entries.
- `PUT /api/field-mappings` — Manually map a `normalized_label` to a `canonical_concept`.
- `GET /api/random-values`, `POST /api/random-values`, `DELETE /api/random-values/{id}` — Manage pool values.
- `POST /api/random-values/import-csv`, `GET /api/random-values/export-csv` — CSV import/export.

## Notifications
- `GET /api/notification-emails`, `POST /api/notification-emails`, `PATCH /api/notification-emails/{id}`, `DELETE /api/notification-emails/{id}`.
- `GET /api/email-config` (password masked), `POST /api/email-config`, `POST /api/test-email`.
