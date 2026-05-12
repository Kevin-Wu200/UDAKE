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
        self._load_from_env()
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "email")
        self.template_env = Environment(loader=FileSystemLoader(template_dir))

    def _load_from_env(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.example.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER", "noreply@example.com")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.email_from = os.getenv("EMAIL_FROM", self.smtp_user)
        self.email_from_name = os.getenv("EMAIL_FROM_NAME", "UDAKE Team")
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
        self._enabled = bool(self.smtp_host.strip() and self.smtp_user.strip() and self.smtp_password.strip())

    def update_settings(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        use_tls: bool = None,
        use_ssl: bool = None,
        email_from: str = None,
        email_from_name: str = None,
    ):
        """从外部动态更新SMTP配置（供工作流邮件服务同步调用）。"""
        if host is not None:
            self.smtp_host = host
        if port is not None:
            self.smtp_port = int(port)
        if username is not None:
            self.smtp_user = username
        if password is not None and set(password) != {"*"}:
            self.smtp_password = password
        if use_tls is not None:
            self.use_tls = bool(use_tls)
        if use_ssl is not None:
            self.use_ssl = bool(use_ssl)
        if email_from is not None:
            self.email_from = email_from
        if email_from_name is not None:
            self.email_from_name = email_from_name
        self._enabled = bool(self.smtp_host.strip() and self.smtp_user.strip() and self.smtp_password.strip())
        logger.info("EmailService SMTP配置已更新: host=%s port=%s user=%s tls=%s ssl=%s",
                    self.smtp_host, self.smtp_port, self.smtp_user, self.use_tls, self.use_ssl)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send_email(self, to: str, subject: str, html_body: str, text_body: Optional[str] = None):
        if not self._enabled:
            logger.warning("SMTP未配置或未启用，跳过邮件发送: to=%s subject=%s", to, subject)
            return

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.email_from_name} <{self.email_from}>"
        msg["To"] = to
        msg["Subject"] = subject
        
        msg.attach(MIMEText(text_body or "请查看HTML版本的邮件", "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        try:
            if self.use_ssl:
                import ssl
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
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
        if not self._enabled:
            logger.info("SMTP未配置，跳过工单通知邮件: ticket_id=%s type=%s", ticket.id, notification_type)
            return

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


# 模块级单例，供其他模块共享
ticket_email_service = EmailService()
