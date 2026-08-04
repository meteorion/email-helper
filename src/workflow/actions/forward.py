"""转发邮件 Action：调用 SmtpClient.send_mail 转发邮件。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class ForwardAction(BaseAction):
    """转发邮件给指定收件人。"""

    action_name = "forward"

    def execute(self) -> Any:
        smtp = self._require_dep("smtp_client")
        mail = self._mail()

        to = self.config.get("to", [])
        if isinstance(to, str):
            to = [to]
        if not to:
            raise ValueError("forward 缺少收件人 (to)")

        cc = self.config.get("cc")
        subject = self.config.get("subject") or f"Fwd: {getattr(mail, 'subject', '')}"
        body = self.config.get("body") or self._build_forward_body(mail)
        html = self.config.get("html")
        attachments = list(self.config.get("attachments", []) or [])

        # 默认附带原邮件附件
        forward_attachments = self.config.get("forward_attachments", True)
        if forward_attachments:
            for att in getattr(mail, "attachments", []) or []:
                local_path = getattr(att, "local_path", None)
                if local_path:
                    attachments.append(local_path)

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

    @staticmethod
    def _build_forward_body(mail) -> str:
        """构造转发正文，附带原邮件信息。"""
        return (
            "----- 转发邮件 -----\n"
            f"发件人: {getattr(mail, 'sender', '')}\n"
            f"主题: {getattr(mail, 'subject', '')}\n"
            f"时间: {getattr(mail, 'send_time', '')}\n\n"
            f"{getattr(mail, 'body_text', '')}"
        )
