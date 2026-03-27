"""Email template management with multilingual support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


@dataclass(frozen=True)
class EmailTemplate:
    subject: str
    html: str


class EmailTemplateManager:
    """Render email templates with Chinese/English variants."""

    def __init__(self) -> None:
        self._templates: Dict[Tuple[str, str], EmailTemplate] = {
            ("register_code", "zh-CN"): EmailTemplate(
                subject="欢迎加入 UDAKE，邮箱验证码",
                html=(
                    "<h2>欢迎，{{ username }}</h2>"
                    "<p>你的邮箱验证码是：<b>{{ code }}</b></p>"
                    "<p>验证码 {{ valid_time }} 内有效，请勿泄露给他人。</p>"
                ),
            ),
            ("register_code", "en-US"): EmailTemplate(
                subject="Welcome to UDAKE - Email Verification Code",
                html=(
                    "<h2>Welcome, {{ username }}</h2>"
                    "<p>Your verification code is: <b>{{ code }}</b></p>"
                    "<p>This code is valid for {{ valid_time }}.</p>"
                ),
            ),
            ("reset_password_code", "zh-CN"): EmailTemplate(
                subject="UDAKE 密码重置验证码",
                html=(
                    "<h2>你好，{{ username }}</h2>"
                    "<p>你正在重置密码，验证码为：<b>{{ code }}</b></p>"
                    "<p>验证码 {{ valid_time }} 内有效，若非本人操作请忽略本邮件。</p>"
                ),
            ),
            ("reset_password_code", "en-US"): EmailTemplate(
                subject="UDAKE Password Reset Code",
                html=(
                    "<h2>Hello, {{ username }}</h2>"
                    "<p>You requested a password reset. Code: <b>{{ code }}</b></p>"
                    "<p>Valid for {{ valid_time }}. Ignore this email if it was not you.</p>"
                ),
            ),
            ("change_email_code", "zh-CN"): EmailTemplate(
                subject="UDAKE 修改邮箱验证码",
                html=(
                    "<h2>你好，{{ username }}</h2>"
                    "<p>你正在将邮箱修改为新地址，验证码：<b>{{ code }}</b></p>"
                    "<p>验证码 {{ valid_time }} 内有效。</p>"
                ),
            ),
            ("change_email_code", "en-US"): EmailTemplate(
                subject="UDAKE Change Email Verification Code",
                html=(
                    "<h2>Hello, {{ username }}</h2>"
                    "<p>You are changing your email address. Code: <b>{{ code }}</b></p>"
                    "<p>This code is valid for {{ valid_time }}.</p>"
                ),
            ),
            ("change_email_notice", "zh-CN"): EmailTemplate(
                subject="UDAKE 邮箱已变更通知",
                html=(
                    "<h2>你好，{{ username }}</h2>"
                    "<p>你的账号邮箱已从 <b>{{ old_email }}</b> 修改为 <b>{{ new_email }}</b>。</p>"
                    "<p>如果这不是你的操作，请立即联系管理员。</p>"
                ),
            ),
            ("change_email_notice", "en-US"): EmailTemplate(
                subject="UDAKE Email Changed Notification",
                html=(
                    "<h2>Hello, {{ username }}</h2>"
                    "<p>Your account email has changed from <b>{{ old_email }}</b> to <b>{{ new_email }}</b>.</p>"
                    "<p>If this wasn't you, contact support immediately.</p>"
                ),
            ),
        }

    def _render_string(self, content: str, variables: Mapping[str, object]) -> str:
        try:
            from jinja2 import Template  # type: ignore

            return Template(content).render(**variables)
        except Exception:
            rendered = content
            for key, value in variables.items():
                rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))
            return rendered

    def render(
        self,
        template_key: str,
        *,
        language: str = "zh-CN",
        variables: Mapping[str, object] | None = None,
    ) -> EmailTemplate:
        normalized_lang = "en-US" if language.lower().startswith("en") else "zh-CN"
        template = self._templates.get((template_key, normalized_lang))
        if template is None:
            template = self._templates[(template_key, "zh-CN")]
        context = dict(variables or {})
        subject = self._render_string(template.subject, context)
        html = self._render_string(template.html, context)
        return EmailTemplate(subject=subject, html=html)
