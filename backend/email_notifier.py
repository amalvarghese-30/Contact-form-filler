"""
Email notification system for form submissions
Sends filled form data to configured recipients after successful submission
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any
import html
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Handles sending email notifications for form submissions"""
    
    def __init__(self, db):
        self.db = db
    
    def get_config(self) -> Dict[str, Any]:
        """Get SMTP configuration from database"""
        cur = self.db.conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM email_config WHERE id = 1")
        config = cur.fetchone()
        cur.close()
        return config or {}
    
    def get_active_recipients(self) -> List[str]:
        """Get list of active notification email addresses"""
        cur = self.db.conn.cursor()
        cur.execute("SELECT email FROM notification_emails WHERE is_active = TRUE")
        recipients = [row[0] for row in cur.fetchall()]
        cur.close()
        return recipients
    
    def send_notification(
        self, 
        website_url: str,
        contact_url: str,
        filled_values: Dict[str, str],
        submission_id: int,
        campaign_id: int = None,
        status_code: int = 200
    ) -> bool:
        """
        Send email notification with filled form data
        
        Args:
            website_url: Main website URL
            contact_url: Contact page URL
            filled_values: Dictionary of field names to values
            submission_id: Database submission ID
            campaign_id: Campaign ID (if part of campaign)
            status_code: HTTP response status code
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Get configuration
            config = self.get_config()
            if not config or not config.get('is_enabled'):
                logger.debug("[EMAIL] Email notifications disabled")
                return False
            
            recipients = self.get_active_recipients()
            if not recipients:
                logger.debug("[EMAIL] No active recipients configured")
                return False
            
            # Validate SMTP config
            if not all([config.get('smtp_host'), config.get('smtp_user'), config.get('smtp_password')]):
                logger.warning("[EMAIL] SMTP configuration incomplete")
                return False
            
            # Build email content
            subject = f"✅ New Form Submission - {website_url}"
            html_body = self._build_email_html(
                website_url, contact_url, filled_values, 
                submission_id, campaign_id, status_code
            )
            
            # Send email
            self._send_smtp_email(
                config=config,
                recipients=recipients,
                subject=subject,
                html_body=html_body
            )
            
            logger.info(f"[EMAIL] Sent notification to {len(recipients)} recipient(s)")
            return True
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send notification: {e}")
            return False
    
    def _build_email_html(
        self,
        website_url: str,
        contact_url: str,
        filled_values: Dict[str, str],
        submission_id: int,
        campaign_id: int,
        status_code: int
    ) -> str:
        """Build HTML email body"""
        
        # Format timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Build fields table
        fields_html = ""
        for field_name, value in filled_values.items():
            # Capitalize field name nicely and escape HTML
            display_name = html.escape(field_name.replace('_', ' ').title())
            display_value = html.escape(str(value)[:200])
            fields_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600; color: #555;">
                    {display_name}:
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; color: #333;">
                    {display_value}
                </td>
            </tr>
            """
        
        # Campaign info
        campaign_html = ""
        if campaign_id:
            campaign_html = f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600; color: #555;">
                    Campaign ID:
                </td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; color: #333;">
                    {campaign_id}
                </td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">📝 New Form Submission</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;">{timestamp}</p>
            </div>
            
            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                
                <!-- Website Info -->
                <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #667eea;">
                    <h3 style="margin: 0 0 15px 0; color: #667eea; font-size: 16px;">🌐 Website Information</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600; color: #555;">
                                Website:
                            </td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                                <a href="{website_url}" style="color: #667eea; text-decoration: none;">{website_url}</a>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600; color: #555;">
                                Contact Page:
                            </td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                                <a href="{contact_url}" style="color: #667eea; text-decoration: none;">{contact_url}</a>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600; color: #555;">
                                Status:
                            </td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                                <span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                                    ✓ Success ({status_code})
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
                
                <!-- Filled Form Data -->
                <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #764ba2;">
                    <h3 style="margin: 0 0 15px 0; color: #764ba2; font-size: 16px;">📋 Filled Form Data</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        {fields_html}
                    </table>
                </div>
                
                <!-- Submission Details -->
                <div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                    <h3 style="margin: 0 0 15px 0; color: #f59e0b; font-size: 16px;">📊 Submission Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: 600; color: #555;">
                                Submission ID:
                            </td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; color: #333;">
                                {submission_id}
                            </td>
                        </tr>
                        {campaign_html}
                    </table>
                </div>
                
                <!-- Footer -->
                <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #eee; text-align: center; color: #999; font-size: 12px;">
                    <p style="margin: 0;">This is an automated notification from <strong>Contact Form Filler</strong></p>
                    <p style="margin: 5px 0 0 0;">🤖 Automated Form Submission System</p>
                </div>
                
            </div>
            
        </body>
        </html>
        """
        
        return html
    
    def _send_smtp_email(
        self,
        config: Dict[str, Any],
        recipients: List[str],
        subject: str,
        html_body: str
    ):
        """Send email via SMTP"""
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config.get('from_name', 'Contact Form Filler')} <{config['smtp_user']}>"
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        # Attach HTML body
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Send via SMTP
        with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)
            
        logger.debug(f"[EMAIL] Sent to: {', '.join(recipients)}")
