# Changelog

## v2.0.0 — Full-Stack Stabilization & Modern Web Redesign
### Backend
- Refactored monolithic `fastapi_backend.py` into `app/` (`api/routes`, `core`, `services`, `automation`, `database`, `schemas`).
- Removed duplicate `run_campaign_pipeline` definition and implemented `CampaignService` with duplicate-run prevention, true Pause/Resume/Restart/Cancel, and per-website status tracking.
- Fixed `/api/test-email` `MySQLDB` import error and `/api/fill-form-template` `field_prevalence` key mismatch.
- Fixed `form_filler.py` to honor campaign field strategies (`constant`, `custom`, `random`), record `campaignid` in `form_submissions`, update `websites`/`raw_fields` on scan, and avoid false-positive `"success"` on unconfirmed POST responses.
- Added MySQL connection pooling, non-destructive startup migrations, SSRF URL validation, HTML escaping in notification emails, `/health` endpoints, and `pytest` suite.

### Frontend
- Replaced legacy HTML files (`analytics.html`, `campaign_details.html`, `index.html`) with a modern React 18 + TypeScript + Vite + Tailwind CSS + Recharts SaaS application.
- Built all 11 required pages: Dashboard, Websites, Website Details, Campaigns, 4-Step Campaign Wizard, Live Campaign Monitor, Submissions, Analytics, Field Mapping & Value Pools, Notifications, and Settings.
