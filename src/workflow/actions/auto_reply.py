"""自动回复 Action：调用 SmtpClient.send_mail 发送自动回复。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class AutoReplyAction(BaseAction):
    """自动回复邮件。"""

    action_name = "auto_reply"

    def execute(self) -> Any:
        smtp = self._require_dep("smtp_client")
        mail = self._mail()

        to = self.config.get("to") or getattr(mail, "sender", "")
        if not to:
            raise ValueError("auto_reply 缺少收件人 (to 或 mail.sender)")

        subject = self.config.get("subject") or f"Re: {getattr(mail, 'subject', '')}"
        body = self.config.get("body", "")
        if not body:
            body = self.config.get("template", "")
        html = self.config.get("html")
        cc = self.config.get("cc")
        attachments = self.config.get("attachments", []) or []

        ok = smtp.send_mail(
            to=to,
            subject=subject,
            body=body,
            html=html,
            attachments=attachments,
            cc=cc,
        )
        return {
            "status": "sent" if ok else "failed",
            "to": to,
            "subject": subject,
        }
