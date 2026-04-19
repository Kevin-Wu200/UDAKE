import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.example.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER", "noreply@example.com")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_user)
        self.email_from_name = os.getenv("EMAIL_FROM_NAME", "UDAKE Team")
        
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "email")
        self.template_env = Environment(loader=FileSystemLoader(template_dir))

    def send_email(self, to: str, subject: str, html_body: str, text_body: Optional[str] = None):
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.email_from_name} <{self.email_from}>"
        msg["To"] = to
        msg["Subject"] = subject
        
        msg.attach(MIMEText(text_body or "请查看HTML版本的邮件", "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(f"Email sent to {to} successfully.")
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            raise e

    def send_ticket_notification(self, ticket: any, notification_type: str, extra_data: dict = None):
        template_map = {
            "submitted": "ticket_submitted.html",
            "approved": "ticket_approved.html",
            "rejected": "ticket_rejected.html",
        }
        
        template_name = template_map.get(notification_type)
        if not template_name:
            logger.error(f"Unknown notification type: {notification_type}")
            return
            
        template = self.template_env.get_template(template_name)
        data = {
            "ticket_id": ticket.id,
            "ticket_type": ticket.ticket_type,
            "created_at": ticket.created_at,
            **(extra_data or {})
        }
        html_body = template.render(**data)
        
        subject_map = {
            "submitted": "工单申请成功 - UDAKE",
            "approved": "工单申请已批准 - UDAKE",
            "rejected": "工单申请已拒绝 - UDAKE",
        }
        
        self.send_email(ticket.email, subject_map.get(notification_type, "工单更新"), html_body)
