"""SMTP 客户端 - 发送邮件"""

import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional

from src.core.logger import get_logger

logger = get_logger("mail.smtp")


class SmtpClient:
    """SMTP 客户端，负责发送邮件"""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        timeout: int = 30,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.timeout = timeout

        self._conn: Optional[smtplib.SMTP_SSL | smtplib.SMTP] = None
        self._connected = False

    def connect(self) -> bool:
        """建立 SMTP SSL 连接"""
        try:
            logger.info(f"连接 SMTP 服务器: {self.host}:{self.port}")

            if self.use_ssl:
                self._conn = smtplib.SMTP_SSL(
                    self.host, self.port, timeout=self.timeout
                )
            else:
                self._conn = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                self._conn.starttls()

            # 登录
            self._conn.login(self.username, self.password)
            self._connected = True
            logger.info(f"SMTP 登录成功: {self.username}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP 认证失败: {e}")
            raise ConnectionError(f"SMTP 认证失败: {e}") from e
        except socket.timeout:
            logger.error(f"SMTP 连接超时: {self.host}:{self.port}")
            raise ConnectionError(f"SMTP 连接超时") from None
        except Exception as e:
            logger.error(f"SMTP 连接失败: {e}")
            raise ConnectionError(f"SMTP 连接失败: {e}") from e

    def disconnect(self):
        """关闭连接"""
        if self._conn:
            try:
                self._conn.quit()
            except Exception as e:
                logger.warning(f"SMTP 断开连接时出错: {e}")
            finally:
                self._conn = None
                self._connected = False
                logger.info("SMTP 连接已关闭")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self._conn is not None

    def send_mail(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: Optional[str] = None,
        attachments: Optional[list[str]] = None,
        cc: Optional[str | list[str]] = None,
    ) -> bool:
        """
        发送邮件

        Args:
            to: 收件人 (字符串或列表)
            subject: 邮件主题
            body: 纯文本正文
            html: HTML 正文 (可选)
            attachments: 附件文件路径列表 (可选)
            cc: 抄送 (字符串或列表，可选)

        Returns:
            是否发送成功
        """
        if not self.is_connected():
            raise ConnectionError("SMTP 未连接")

        # 标准化收件人和抄送
        if isinstance(to, str):
            to = [to]
        if isinstance(cc, str):
            cc = [cc]

        max_retries = 2
        retry_delay = 3

        for attempt in range(max_retries):
            try:
                # 构建邮件
                msg = self._build_message(to, subject, body, html, attachments, cc)

                # 发送
                all_recipients = to + (cc or [])
                self._conn.sendmail(self.username, all_recipients, msg.as_string())

                logger.info(f"邮件发送成功: {subject} -> {', '.join(to)}")
                return True

            except Exception as e:
                logger.error(f"邮件发送失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"{retry_delay} 秒后重试...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"邮件发送最终失败: {subject}")
                    return False

        return False

    def _build_message(
        self,
        to: list[str],
        subject: str,
        body: str,
        html: Optional[str],
        attachments: Optional[list[str]],
        cc: Optional[list[str]],
    ) -> MIMEMultipart:
        """构建 MIME 邮件"""
        msg = MIMEMultipart("mixed")
        msg["From"] = self.username
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = ", ".join(cc)

        # 正文
        if html:
            # 同时包含纯文本和 HTML
            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(body, "plain", "utf-8"))
            alt_part.attach(MIMEText(html, "html", "utf-8"))
            msg.attach(alt_part)
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        # 附件
        if attachments:
            for file_path in attachments:
                self._attach_file(msg, file_path)

        return msg

    def _attach_file(self, msg: MIMEMultipart, file_path: str):
        """添加附件"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"附件不存在: {file_path}")
                return

            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())

            encoders.encode_base64(part)

            # 设置附件头
            filename = path.name
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            )

            msg.attach(part)
            logger.debug(f"添加附件: {filename}")

        except Exception as e:
            logger.error(f"添加附件失败: {file_path}, 错误: {e}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
