# Database Documentation (`form_insights`)

## Connection Management
- Configured via `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, and `MYSQL_POOL_SIZE`.
- Managed by `backend/app/database/connection.py` using `mysql.connector.pooling.MySQLConnectionPool` and context-managed transactions (`db_session()`).

## Active Tables

| Table | Purpose |
|---|---|
| `websites` | Target URLs, scan `timestamp`, `form_found`, `has_captcha`, `is_dead` flags |
| `raw_fields` | Extracted HTML form inputs (`tag_name`, `field_id`, `field_name`, `field_type`, `placeholder`, `cluster_key`, `cluster_score`) |
| `field_concept_map` | Maps `normalized_label` to `canonical_concept` with `is_manual` override flag |
| `random_value_pool` | Approved random values keyed by `field_concept` |
| `campaigns` | Campaign metadata, sender info, message content, `status`, and summary counters |
| `campaign_websites` | Per-campaign target URLs with `status`, `submission_id`, `error`, and `processed_at` |
| `campaign_field_strategy` | Per-campaign concept strategy (`constant`, `random`, `custom`) and `constant_value` |
| `campaign_runs` | Execution run history, `progress`, `total`, JSON `results`, and timestamps |
| `form_submissions` | Submission audit log (`website_id`, `url`, `normalized_url`, `status`, `filled_fields`, `error`, `campaignid`) |
| `form_submissions_details` | Captured HTTP `request_url`, `payload_json`, `response_json`, and `status_code` |
| `email_config` | Single-row SMTP configuration (`id = 1`) |
| `notification_emails` | Active/inactive email recipients |

## Non-Destructive Migrations
`backend/app/database/migrations.py` runs idempotently on FastAPI startup:
- Expands `campaigns.status` to `VARCHAR(30)` to support `draft`, `queued`, `running`, `paused`, `completed`, `failed`, `cancelled`.
- Adds `status`, `submission_id`, `error`, `processed_at` to `campaign_websites` if missing.
- Adds performance indexes `idx_websites_flags` and `idx_fs_status_created`.
- Preserves all existing records without dropping tables or resetting data.
