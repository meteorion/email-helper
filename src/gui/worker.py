"""后台工作线程 - Flet 版本，使用 threading"""

import threading
from datetime import datetime

from src.core.logger import get_logger
from src.core.models import MailData
from src.mail.imap_client import ImapClient
from src.mail.smtp_client import SmtpClient
from src.storage.mail_store import MailStore

logger = get_logger("gui.worker")


class MailFetchWorker:
    """邮件拉取工作线程"""

    def __init__(
        self,
        imap_client: ImapClient,
        mail_store: MailStore,
        on_finished=None,
        on_error=None,
        on_progress=None,
    ):
        self.imap_client = imap_client
        self.mail_store = mail_store
        self._on_finished = on_finished
        self._on_error = on_error
        self._on_progress = on_progress
        self._thread = None

    def start(self):
        """启动拉取"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """线程执行逻辑"""
        try:
            self._emit_progress("正在连接邮箱...")

            seen_ids = self.mail_store.get_seen_ids()

            self._emit_progress("正在拉取邮件...")

            new_mails = self.imap_client.fetch_unseen(seen_ids)

            if not new_mails:
                self._emit_progress("没有新邮件")
                if self._on_finished:
                    self._on_finished([])
                return

            self._emit_progress(f"正在保存 {len(new_mails)} 封邮件...")
            for mail in new_mails:
                self.mail_store.save(mail)
                seen_ids.add(mail.message_id)

            self.mail_store.save_seen_ids(seen_ids)

            logger.info(f"工作线程完成: 拉取 {len(new_mails)} 封新邮件")
            if self._on_finished:
                self._on_finished(new_mails)

        except Exception as e:
            error_msg = f"拉取邮件失败: {e}"
            logger.error(error_msg, exc_info=True)
            if self._on_error:
                self._on_error(error_msg)

    def _emit_progress(self, msg: str):
        """发送进度信息"""
        logger.info(f"[拉取进度] {msg}")
        if self._on_progress:
            self._on_progress(msg)


class MailSendWorker:
    """邮件发送工作线程"""

    def __init__(
        self,
        smtp_client: SmtpClient,
        to: str | list[str],
        subject: str,
        body: str,
        html: str | None = None,
        attachments: list[str] | None = None,
        cc: str | list[str] | None = None,
        on_finished=None,
        on_error=None,
        on_progress=None,
    ):
        self.smtp_client = smtp_client
        self.to = to
        self.subject = subject
        self.body = body
        self.html = html
        self.attachments = attachments
        self.cc = cc
        self._on_finished = on_finished
        self._on_error = on_error
        self._on_progress = on_progress
        self._thread = None

    def start(self):
        """启动发送"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """线程执行逻辑"""
        try:
            self._emit_progress("正在发送邮件...")

            success = self.smtp_client.send_mail(
                to=self.to,
                subject=self.subject,
                body=self.body,
                html=self.html,
                attachments=self.attachments,
                cc=self.cc,
            )

            if success:
                self._emit_progress("邮件发送成功")
                logger.info(f"工作线程完成: 发送邮件 '{self.subject}'")
            else:
                if self._on_error:
                    self._on_error("邮件发送失败")

            if self._on_finished:
                self._on_finished(success)

        except Exception as e:
            error_msg = f"发送邮件失败: {e}"
            logger.error(error_msg, exc_info=True)
            if self._on_error:
                self._on_error(error_msg)

    def _emit_progress(self, msg: str):
        """发送进度信息"""
        logger.info(f"[发送进度] {msg}")
        if self._on_progress:
            self._on_progress(msg)