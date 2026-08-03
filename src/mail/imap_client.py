"""IMAP 客户端 - 连接企微邮箱，拉取未读邮件"""

import imaplib
import socket
from typing import Optional
from datetime import datetime, timezone

from src.core.logger import get_logger
from src.mail.parser import parse_email

logger = get_logger("mail.imap")


class ImapClient:
    """IMAP 客户端，负责连接和邮件拉取"""

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

        self._conn: Optional[imaplib.IMAP4_SSL | imaplib.IMAP4] = None
        self._connected = False

    def connect(self) -> bool:
        """建立 IMAP SSL 连接"""
        try:
            logger.info(f"连接 IMAP 服务器: {self.host}:{self.port}")

            if self.use_ssl:
                self._conn = imaplib.IMAP4_SSL(
                    self.host, self.port, timeout=self.timeout
                )
            else:
                self._conn = imaplib.IMAP4(
                    self.host, self.port, timeout=self.timeout
                )

            # 登录
            self._conn.login(self.username, self.password)
            self._connected = True
            logger.info(f"IMAP 登录成功: {self.username}")
            return True

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP 认证失败: {e}")
            raise ConnectionError(f"IMAP 认证失败: {e}") from e
        except socket.timeout:
            logger.error(f"IMAP 连接超时: {self.host}:{self.port}")
            raise ConnectionError(f"IMAP 连接超时") from None
        except Exception as e:
            logger.error(f"IMAP 连接失败: {e}")
            raise ConnectionError(f"IMAP 连接失败: {e}") from e

    def disconnect(self):
        """关闭连接"""
        if self._conn:
            try:
                if self._connected:
                    self._conn.logout()
            except Exception as e:
                logger.warning(f"IMAP 断开连接时出错: {e}")
            finally:
                self._conn = None
                self._connected = False
                logger.info("IMAP 连接已关闭")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self._conn is not None

    def fetch_unseen(self, seen_ids: set[str], folder: str = "INBOX") -> list:
        """
        拉取未见邮件

        Args:
            seen_ids: 已处理邮件 ID 集合
            folder: 邮件文件夹，默认 INBOX

        Returns:
            MailData 列表
        """
        if not self.is_connected():
            raise ConnectionError("IMAP 未连接")

        from src.core.models import MailData
        mails: list[MailData] = []

        try:
            # 选择文件夹
            status, _ = self._conn.select(folder, readonly=True)
            if status != "OK":
                logger.error(f"选择文件夹失败: {folder}")
                return mails

            # 搜索未读邮件
            status, data = self._conn.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("搜索未读邮件失败")
                return mails

            mail_ids = data[0].split()
            if not mail_ids:
                logger.info("没有未读邮件")
                return mails

            logger.info(f"发现 {len(mail_ids)} 封未读邮件")

            # 逐封拉取
            for mail_id in mail_ids:
                try:
                    mail = self._fetch_single_mail(mail_id, seen_ids)
                    if mail:
                        mails.append(mail)
                except Exception as e:
                    logger.error(f"拉取邮件 {mail_id} 失败: {e}")
                    continue

            logger.info(f"成功拉取 {len(mails)} 封新邮件")
            return mails

        except Exception as e:
            logger.error(f"拉取邮件失败: {e}", exc_info=True)
            return mails

    def _fetch_single_mail(self, mail_id: bytes, seen_ids: set[str]):
        """拉取单封邮件"""
        from src.core.models import MailData

        try:
            # 获取邮件内容
            status, data = self._conn.fetch(mail_id, "(RFC822)")
            if status != "OK":
                logger.warning(f"获取邮件 {mail_id} 失败")
                return None

            raw_email = data[0][1]
            if not raw_email:
                return None

            # 解析邮件
            mail = parse_email(raw_email)

            # 检查是否已处理
            if mail.message_id in seen_ids:
                logger.debug(f"邮件已处理，跳过: {mail.message_id}")
                return None

            return mail

        except Exception as e:
            logger.error(f"解析邮件 {mail_id} 失败: {e}")
            return None

    def mark_as_read(self, message_id: str, folder: str = "INBOX") -> bool:
        """
        标记邮件为已读

        Args:
            message_id: 邮件 Message-ID
            folder: 文件夹

        Returns:
            是否成功
        """
        if not self.is_connected():
            raise ConnectionError("IMAP 未连接")

        try:
            # 选择文件夹
            status, _ = self._conn.select(folder, readonly=False)
            if status != "OK":
                return False

            # 搜索指定 Message-ID 的邮件
            status, data = self._conn.search(
                None, f'HEADER Message-ID "{message_id}"'
            )
            if status != "OK" or not data[0]:
                logger.warning(f"未找到邮件: {message_id}")
                return False

            mail_ids = data[0].split()
            for mail_id in mail_ids:
                # 标记为已读
                self._conn.store(mail_id, "+FLAGS", "\\Seen")

            logger.info(f"标记邮件已读: {message_id}")
            return True

        except Exception as e:
            logger.error(f"标记已读失败: {e}")
            return False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
