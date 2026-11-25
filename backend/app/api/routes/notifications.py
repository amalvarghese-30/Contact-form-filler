"""Email notification recipients, SMTP configuration, and test email routes."""

from fastapi import APIRouter, Form, HTTPException, Request
import mysql.connector

from app.database.connection import db_session
from app.schemas.settings import EmailConfigRequest
from email_notifier import EmailNotifier
from form_filler import MySQLDB

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notification-emails")
def list_notification_emails():
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT id, email, is_active, created_at FROM notification_emails ORDER BY id DESC")
        rows = cur.fetchall() or []
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])
        r["is_active"] = bool(r.get("is_active"))
    return {"items": rows}


@router.post("/notification-emails")
async def add_notification_email(request: Request, email: str | None = Form(default=None)):
    """Accept either form-data (legacy) or JSON body {email}."""
    resolved_email = email
    if not resolved_email:
        try:
            body = await request.json()
            resolved_email = body.get("email")
        except Exception:
            pass
    if not resolved_email or "@" not in str(resolved_email):
        raise HTTPException(status_code=400, detail="Valid email address is required")

    clean_email = str(resolved_email).strip()
    try:
        with db_session() as (_, cur):
            cur.execute("INSERT INTO notification_emails (email, is_active) VALUES (%s, TRUE)", (clean_email,))
            email_id = int(cur.lastrowid)
        return {"ok": True, "id": email_id, "email": clean_email}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")


@router.delete("/notification-emails/{email_id}")
def delete_notification_email(email_id: int):
    with db_session() as (_, cur):
        cur.execute("DELETE FROM notification_emails WHERE id=%s", (email_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")
    return {"ok": True}


@router.patch("/notification-emails/{email_id}")
def toggle_notification_email(email_id: int):
    with db_session() as (_, cur):
        cur.execute("UPDATE notification_emails SET is_active = NOT is_active WHERE id=%s", (email_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")
    return {"ok": True}


@router.get("/email-config")
def get_email_config():
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT id, smtp_host, smtp_port, smtp_user, smtp_password, from_name, is_enabled, updated_at FROM email_config WHERE id = 1")
        config = cur.fetchone()
    if not config:
        return {}
    if config.get("smtp_password"):
        config["smtp_password"] = "********"
    if config.get("updated_at"):
        config["updated_at"] = str(config["updated_at"])
    config["is_enabled"] = bool(config.get("is_enabled"))
    return config


@router.post("/email-config")
def update_email_config(config: EmailConfigRequest):
    with db_session() as (_, cur):
        if config.smtp_password == "********" or config.smtp_password is None:
            cur.execute(
                """
                UPDATE email_config
                SET smtp_host=%s, smtp_port=%s, smtp_user=%s, from_name=%s, is_enabled=%s
                WHERE id = 1
                """,
                (config.smtp_host, config.smtp_port, config.smtp_user, config.from_name, config.is_enabled),
            )
        else:
            cur.execute(
                """
                UPDATE email_config
                SET smtp_host=%s, smtp_port=%s, smtp_user=%s, smtp_password=%s, from_name=%s, is_enabled=%s
                WHERE id = 1
                """,
                (
                    config.smtp_host,
                    config.smtp_port,
                    config.smtp_user,
                    config.smtp_password,
                    config.from_name,
                    config.is_enabled,
                ),
            )
    return {"ok": True}


@router.post("/test-email")
async def send_test_email():
    db = MySQLDB()
    try:
        notifier = EmailNotifier(db)
        success = notifier.send_notification(
            website_url="https://example.com",
            contact_url="https://example.com/contact",
            filled_values={
                "fullname": "Test User",
                "email": "test@example.com",
                "phone": "+1 555 0100",
                "company": "Example Corp",
                "subject": "Test Notification",
                "message": "This is a test message from Contact Form Filler.",
            },
            submission_id=0,
            campaign_id=None,
            status_code=200,
        )
        if success:
            return {"ok": True, "message": "Test email sent successfully"}
        return {"ok": False, "message": "Failed to send test email. Verify SMTP settings and active recipients."}
    finally:
        db.close()
