"""邮件解析器 - 解析 IMAP 原始邮件为 MailData 对象"""

import email
from email import policy
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone
from typing import Optional
import hashlib
import re

from src.core.models import MailData, Attachment
from src.core.logger import get_logger

logger = get_logger("mail.parser")


# 字符集回退顺序
CHARSET_FALLBACK = ["utf-8", "gbk", "gb2312", "gb18030", "latin1"]


def decode_header_value(value: str) -> str:
    """
    解码邮件头 (主题/发件人等)
    支持 RFC 2047 编码字: =?charset?encoding?text?=
    """
    if not value:
        return ""

    decoded_parts = []
    try:
        parts = decode_header(value)
        for part, charset in parts:
            if isinstance(part, bytes):
                # 尝试声明的 charset，失败则依次尝试
                charsets_to_try = [charset] + [c for c in CHARSET_FALLBACK if c != charset]
                decoded = False
                for enc in charsets_to_try:
                    if not enc:
                        continue
                    try:
                        decoded_parts.append(part.decode(enc))
                        decoded = True
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                if not decoded:
                    # 最终回退：使用 replacement 字符
                    decoded_parts.append(part.decode("utf-8", errors="replace"))
            else:
                decoded_parts.append(part)
    except Exception as e:
        logger.warning(f"解码邮件头失败: {value}, 错误: {e}")
        return value

    return "".join(decoded_parts)


def extract_email_address(header_value: str) -> tuple[str, str]:
    """
    从邮件头提取邮箱地址和显示名称
    返回: (显示名称, 邮箱地址)
    """
    if not header_value:
        return "", ""

    # 先解码
    decoded = decode_header_value(header_value)
    # 解析
    name, addr = parseaddr(decoded)
    return name.strip(), addr.strip()


def get_sender_domain(email_addr: str) -> str:
    """从邮箱地址提取域名"""
    if "@" in email_addr:
        return email_addr.split("@")[-1].lower()
    return ""


def decode_payload(part: Message) -> str:
    """解码邮件 part 的 payload"""
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""

    charset = part.get_content_charset()
    if charset:
        charsets_to_try = [charset] + [c for c in CHARSET_FALLBACK if c != charset]
    else:
        charsets_to_try = CHARSET_FALLBACK

    for enc in charsets_to_try:
        try:
            return payload.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # 最终回退
    return payload.decode("utf-8", errors="replace")


def extract_body(msg: Message) -> tuple[str, Optional[str]]:
    """
    提取邮件正文
    返回: (纯文本, HTML)
    """
    text_body = ""
    html_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # 跳过附件
            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                text_body += decode_payload(part)
            elif content_type == "text/html":
                html_content = decode_payload(part)
                if html_body is None:
                    html_body = html_content
                else:
                    html_body += html_content
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            text_body = decode_payload(msg)
        elif content_type == "text/html":
            html_body = decode_payload(msg)

    # 如果只有 HTML 没有纯文本，从 HTML 提取纯文本
    if not text_body and html_body:
        text_body = html_to_text(html_body)

    return text_body.strip(), html_body


def html_to_text(html: str) -> str:
    """简单的 HTML 转纯文本"""
    # 移除 script 和 style 标签
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 移除标签
    text = re.sub(r"<[^>]+>", " ", html)
    # 清理空白
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_attachments(msg: Message) -> list[Attachment]:
    """提取邮件附件"""
    attachments = []

    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))

        # 检查是否是附件
        if "attachment" not in content_disposition and part.get_content_maintype() == "multipart":
            continue

        filename = part.get_filename()
        if filename:
            # 解码文件名
            filename = decode_header_value(filename)

            # 获取内容
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0

            # 获取 MIME 类型
            mime_type = part.get_content_type()

            # 获取 Content-ID (用于内联附件)
            content_id = part.get("Content-ID")
            if content_id:
                content_id = content_id.strip("<>")

            attachments.append(Attachment(
                filename=filename,
                size=size,
                mime_type=mime_type,
                content_id=content_id,
            ))

    return attachments


def parse_date(date_str: str) -> datetime:
    """解析邮件日期"""
    if not date_str:
        return datetime.now(timezone.utc)

    try:
        # 尝试使用 email.utils 解析
        dt = parsedate_to_datetime(date_str)
        # 转换为 UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"解析日期失败: {date_str}, 错误: {e}")
        return datetime.now(timezone.utc)


def parse_email(raw_bytes: bytes) -> MailData:
    """
    解析 IMAP 原始邮件为 MailData 对象

    Args:
        raw_bytes: IMAP FETCH 返回的原始邮件字节

    Returns:
        MailData 对象
    """
    try:
        # 解析邮件
        msg = email.message_from_bytes(raw_bytes, policy=policy.default)

        # 提取基本信息
        message_id = msg.get("Message-ID", "")
        if not message_id:
            # 生成一个基于内容的 ID
            content_hash = hashlib.md5(raw_bytes[:1000]).hexdigest()
            message_id = f"<generated-{content_hash}@local>"

        # 发件人
        sender_name, sender_addr = extract_email_address(msg.get("From", ""))
        sender_domain = get_sender_domain(sender_addr)
        sender = f"{sender_name} <{sender_addr}>" if sender_name else sender_addr

        # 收件人
        recipient_name, recipient_addr = extract_email_address(msg.get("To", ""))
        recipient = f"{recipient_name} <{recipient_addr}>" if recipient_name else recipient_addr

        # 主题
        subject = decode_header_value(msg.get("Subject", ""))

        # 日期
        send_time = parse_date(msg.get("Date", ""))
        receive_time = datetime.now(timezone.utc)  # IMAP 返回的接收时间

        # 正文
        body_text, body_html = extract_body(msg)

        # 附件
        attachments = extract_attachments(msg)

        return MailData(
            message_id=message_id,
            sender=sender,
            sender_domain=sender_domain,
            recipient=recipient,
            subject=subject,
            send_time=send_time,
            receive_time=receive_time,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    except Exception as e:
        logger.error(f"解析邮件失败: {e}", exc_info=True)
        # 返回一个最小的有效 MailData
        return MailData(
            message_id=f"<error-{hashlib.md5(raw_bytes[:100]).hexdigest()}@local>",
            sender="unknown",
            sender_domain="",
            recipient="unknown",
            subject="[解析失败]",
            send_time=datetime.now(timezone.utc),
            receive_time=datetime.now(timezone.utc),
            body_text=f"邮件解析失败: {e}",
            body_html=None,
            attachments=[],
        )
