"""Non-destructive database schema migrations that preserve all existing records."""

import logging

from app.database.connection import db_session

logger = logging.getLogger(__name__)


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    return bool(row and row[0] > 0)


def _index_exists(cur, table_name: str, index_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s
        """,
        (table_name, index_name),
    )
    row = cur.fetchone()
    return bool(row and row[0] > 0)


def run_migrations() -> None:
    """Apply safe, idempotent migrations to form_insights without dropping data."""
    try:
        with db_session() as (conn, cur):
            # 1. Core tables (only created if missing)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS websites (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  url VARCHAR(2048) NOT NULL,
                  timestamp DATETIME NULL,
                  form_found TINYINT(1) NOT NULL DEFAULT 0,
                  has_captcha TINYINT(1) NOT NULL DEFAULT 0,
                  is_dead TINYINT(1) NOT NULL DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  name VARCHAR(255) NOT NULL,
                  description TEXT NULL,
                  sender_name VARCHAR(255) NULL,
                  sender_email VARCHAR(255) NULL,
                  subject_line VARCHAR(255) NULL,
                  message_body TEXT NULL,
                  max_websites INT NOT NULL DEFAULT 50,
                  status VARCHAR(30) NOT NULL DEFAULT 'draft',
                  results_success INT DEFAULT 0,
                  results_failed INT DEFAULT 0,
                  results_captcha INT DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            # Expand campaigns.status to VARCHAR(30) so all states
            # (draft, queued, running, paused, completed, failed, cancelled) work cleanly.
            try:
                cur.execute(
                    "ALTER TABLE campaigns MODIFY COLUMN status VARCHAR(30) NOT NULL DEFAULT 'draft'"
                )
            except Exception as e:
                logger.debug(f"campaigns.status modify skipped: {e}")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_websites (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  campaign_id INT NOT NULL,
                  website_id INT NULL,
                  website_url VARCHAR(2048) NOT NULL,
                  status VARCHAR(30) NOT NULL DEFAULT 'pending',
                  submission_id INT UNSIGNED NULL,
                  error TEXT NULL,
                  processed_at TIMESTAMP NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_cw_campaign (campaign_id),
                  INDEX idx_cw_website (website_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            # Add per-website tracking columns to existing campaign_websites table if absent
            if not _column_exists(cur, "campaign_websites", "status"):
                cur.execute(
                    "ALTER TABLE campaign_websites ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'pending'"
                )
            if not _column_exists(cur, "campaign_websites", "submission_id"):
                cur.execute(
                    "ALTER TABLE campaign_websites ADD COLUMN submission_id INT UNSIGNED NULL"
                )
            if not _column_exists(cur, "campaign_websites", "error"):
                cur.execute("ALTER TABLE campaign_websites ADD COLUMN error TEXT NULL")
            if not _column_exists(cur, "campaign_websites", "processed_at"):
                cur.execute(
                    "ALTER TABLE campaign_websites ADD COLUMN processed_at TIMESTAMP NULL"
                )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_field_strategy (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  campaign_id INT NOT NULL,
                  field_concept VARCHAR(255) NOT NULL,
                  strategy VARCHAR(30) NOT NULL DEFAULT 'constant',
                  constant_value TEXT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_cfs_campaign (campaign_id),
                  INDEX idx_cfs_concept (field_concept)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            try:
                cur.execute(
                    "ALTER TABLE campaign_field_strategy MODIFY COLUMN strategy VARCHAR(30) NOT NULL DEFAULT 'constant'"
                )
            except Exception:
                pass

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_runs (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  campaign_id INT NOT NULL,
                  status VARCHAR(30) NOT NULL DEFAULT 'queued',
                  progress INT NOT NULL DEFAULT 0,
                  total INT NOT NULL DEFAULT 0,
                  results JSON NULL,
                  error TEXT NULL,
                  started_at TIMESTAMP NULL,
                  finished_at TIMESTAMP NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_campaign_id (campaign_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_emails (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  email VARCHAR(255) NOT NULL UNIQUE,
                  is_active BOOLEAN DEFAULT TRUE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS email_config (
                  id INT PRIMARY KEY DEFAULT 1,
                  smtp_host VARCHAR(255) DEFAULT 'smtp.gmail.com',
                  smtp_port INT DEFAULT 587,
                  smtp_user VARCHAR(255),
                  smtp_password VARCHAR(255),
                  from_name VARCHAR(255) DEFAULT 'Contact Form Filler',
                  is_enabled BOOLEAN DEFAULT FALSE,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                "INSERT INTO email_config (id, is_enabled) VALUES (1, FALSE) ON DUPLICATE KEY UPDATE id=id"
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS form_submissions_details (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  submission_id INT UNSIGNED NOT NULL,
                  request_url TEXT NULL,
                  payload_json LONGTEXT NULL,
                  response_json LONGTEXT NULL,
                  status_code INT NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_fsd_submission (submission_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            # Helpful indexes for analytics & filtering
            if not _column_exists(cur, "websites", "fields_count"):
                try:
                    cur.execute("ALTER TABLE websites ADD COLUMN fields_count INT NOT NULL DEFAULT 0")
                    cur.execute(
                        """
                        UPDATE websites w
                        SET fields_count = (SELECT COUNT(*) FROM raw_fields rf WHERE rf.website_id = w.id)
                        """
                    )
                except Exception as e:
                    logger.debug(f"websites.fields_count migration skipped: {e}")

            if not _index_exists(cur, "websites", "idx_websites_flags"):
                try:
                    cur.execute(
                        "CREATE INDEX idx_websites_flags ON websites (form_found, has_captcha, is_dead)"
                    )
                except Exception:
                    pass

            if not _index_exists(cur, "form_submissions", "idx_fs_status_created"):
                try:
                    cur.execute(
                        "CREATE INDEX idx_fs_status_created ON form_submissions (status, created_at)"
                    )
                except Exception:
                    pass

            conn.commit()
        logger.info("Database migrations verified successfully.")
    except Exception as e:
        logger.warning(f"Database migrations skipped or failed (DB may be offline): {e}")
