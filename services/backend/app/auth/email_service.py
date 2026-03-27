"""SMTP email delivery service with provider failover."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import smtplib
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class InvalidEmailAddressError(ValueError):
    """Raised when recipient email is malformed."""


class EmailDeliveryError(RuntimeError):
    """Raised when SMTP delivery fails."""


@dataclass(frozen=True)
class SMTPAccount:
    host: str
    port: int
    user: str
    password: str
    use_tls: bool = True
    provider: str = "custom"


class SMTPEmailService:
    """SMTP sender with primary/backup failover and retries."""

    def __init__(
        self,
        *,
        accounts: Optional[List[SMTPAccount]] = None,
        retry_attempts: int = 3,
        retry_interval_seconds: int = 10,
        timeout_seconds: int = 20,
        max_workers: int = 4,
    ) -> None:
        self.accounts = [acc for acc in (accounts or []) if acc.host and acc.user]
        self.retry_attempts = max(1, retry_attempts)
        self.retry_interval_seconds = max(0, retry_interval_seconds)
        self.timeout_seconds = max(5, timeout_seconds)
        self._executor = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="auth-mail")
        self._lock = threading.Lock()
        self._delivery_logs: List[Dict[str, Any]] = []
        self._next_sender_idx = random.randint(0, 1024)

    @classmethod
    def from_env(cls) -> "SMTPEmailService":
        accounts: List[SMTPAccount] = []
        accounts_json = os.getenv("SMTP_ACCOUNTS")
        if accounts_json:
            try:
                parsed = json.loads(accounts_json)
                if isinstance(parsed, list):
                    for item in parsed:
                        if not isinstance(item, dict):
                            continue
                        accounts.append(
                            SMTPAccount(
                                host=str(item.get("host", "")).strip(),
                                port=int(item.get("port", 587)),
                                user=str(item.get("user", "")).strip(),
                                password=str(item.get("password", "")).strip(),
                                use_tls=bool(item.get("use_tls", True)),
                                provider=str(item.get("provider", "custom")).strip() or "custom",
                            )
                        )
            except Exception:
                logger.warning("SMTP_ACCOUNTS JSON 解析失败，将使用默认环境变量")

        if not accounts:
            host = os.getenv("SMTP_HOST", "smtp.qq.com").strip()
            user = os.getenv("SMTP_USER", "").strip()
            password = os.getenv("SMTP_PASSWORD", "").strip()
            port = int(os.getenv("SMTP_PORT", "587"))
            if user and password:
                accounts.append(
                    SMTPAccount(
                        host=host,
                        port=port,
                        user=user,
                        password=password,
                        use_tls=True,
                        provider="qq" if "qq.com" in host else "custom",
                    )
                )

            backup_host = os.getenv("SMTP_BACKUP_HOST", "smtp.gmail.com").strip()
            backup_user = os.getenv("SMTP_BACKUP_USER", "").strip()
            backup_password = os.getenv("SMTP_BACKUP_PASSWORD", "").strip()
            backup_port = int(os.getenv("SMTP_BACKUP_PORT", "587"))
            if backup_user and backup_password:
                accounts.append(
                    SMTPAccount(
                        host=backup_host,
                        port=backup_port,
                        user=backup_user,
                        password=backup_password,
                        use_tls=True,
                        provider="gmail" if "gmail.com" in backup_host else "custom",
                    )
                )

        return cls(
            accounts=accounts,
            retry_attempts=int(os.getenv("SMTP_RETRY_ATTEMPTS", "3")),
            retry_interval_seconds=int(os.getenv("SMTP_RETRY_INTERVAL", "10")),
            timeout_seconds=int(os.getenv("SMTP_TIMEOUT_SECONDS", "20")),
            max_workers=int(os.getenv("SMTP_ASYNC_WORKERS", "4")),
        )

    @property
    def delivery_logs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._delivery_logs)

    def _append_log(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._delivery_logs.append(payload)
            if len(self._delivery_logs) > 500:
                self._delivery_logs = self._delivery_logs[-500:]

    def _assert_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise InvalidEmailAddressError("邮箱地址格式无效")
        return normalized

    def _build_message(self, *, sender: str, recipient: str, subject: str, html: str, plain_text: Optional[str]) -> str:
        message = MIMEMultipart("alternative")
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        if plain_text:
            message.attach(MIMEText(plain_text, "plain", "utf-8"))
        message.attach(MIMEText(html, "html", "utf-8"))
        return message.as_string()

    def _send_via_account(self, account: SMTPAccount, *, recipient: str, subject: str, html: str, plain_text: Optional[str]) -> None:
        message = self._build_message(
            sender=account.user,
            recipient=recipient,
            subject=subject,
            html=html,
            plain_text=plain_text,
        )
        with smtplib.SMTP(account.host, account.port, timeout=self.timeout_seconds) as smtp:
            smtp.ehlo()
            if account.use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(account.user, account.password)
            smtp.sendmail(account.user, [recipient], message)

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
        plain_text: Optional[str] = None,
        async_send: bool = True,
    ) -> Future | Dict[str, Any]:
        recipient = self._assert_email(to_email)
        if async_send:
            return self._executor.submit(
                self._send_email_sync,
                recipient,
                subject,
                html_content,
                plain_text,
            )
        return self._send_email_sync(recipient, subject, html_content, plain_text)

    def _send_email_sync(self, recipient: str, subject: str, html_content: str, plain_text: Optional[str]) -> Dict[str, Any]:
        if not self.accounts:
            result = {
                "recipient": recipient,
                "subject": subject,
                "status": "skipped_no_account",
                "sent_at": int(time.time()),
            }
            self._append_log(result)
            logger.warning("未配置SMTP账号，跳过邮件发送: %s", recipient)
            return result

        total_accounts = len(self.accounts)
        with self._lock:
            start_idx = self._next_sender_idx % total_accounts
            self._next_sender_idx += 1

        last_error: Optional[str] = None
        for attempt in range(1, self.retry_attempts + 1):
            for offset in range(total_accounts):
                account = self.accounts[(start_idx + offset) % total_accounts]
                try:
                    self._send_via_account(
                        account,
                        recipient=recipient,
                        subject=subject,
                        html=html_content,
                        plain_text=plain_text,
                    )
                    result = {
                        "recipient": recipient,
                        "subject": subject,
                        "provider": account.provider,
                        "account": account.user,
                        "attempt": attempt,
                        "status": "sent",
                        "sent_at": int(time.time()),
                    }
                    self._append_log(result)
                    return result
                except InvalidEmailAddressError:
                    raise
                except Exception as exc:
                    last_error = str(exc)
                    self._append_log(
                        {
                            "recipient": recipient,
                            "subject": subject,
                            "provider": account.provider,
                            "account": account.user,
                            "attempt": attempt,
                            "status": "failed",
                            "error": str(exc),
                            "sent_at": int(time.time()),
                        }
                    )
                    logger.warning(
                        "邮件发送失败 attempt=%s provider=%s account=%s err=%s",
                        attempt,
                        account.provider,
                        account.user,
                        exc,
                    )
            if attempt < self.retry_attempts and self.retry_interval_seconds > 0:
                time.sleep(self.retry_interval_seconds)

        raise EmailDeliveryError(f"邮件发送失败，已重试{self.retry_attempts}次: {last_error or 'unknown error'}")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)
