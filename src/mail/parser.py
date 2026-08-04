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

# chardet 可选依赖（用于字符集自动检测）
try:
    import chardet  # type: ignore
    _CHARDET_AVAILABLE: bool = True
except ImportError:  # pragma: no cover - chardet 是可选依赖
    chardet = None  # type: ignore
    _CHARDET_AVAILABLE = False

# chardet 检测置信度阈值
_CHARDET_CONFIDENCE_THRESHOLD: float = 0.8

# 危险附件扩展名（命中即标记 blocked=True，不下载）
DANGEROUS_EXTENSIONS: tuple[str, ...] = (
    ".exe", ".bat", ".cmd", ".ps1", ".vbs",
    ".js", ".jar", ".scr", ".com", ".pif",
)


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
    """解码邮件 part 的 payload

    字符集回退链：声明 charset → chardet 自动检测 → CHARSET_FALLBACK → utf-8 replace。
    chardet 不可用时跳过自动检测步骤。
    """
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""

    charset = part.get_content_charset()
    # 1. 优先尝试声明的 charset
    if charset:
        try:
            return payload.decode(charset)
        except (UnicodeDecodeError, LookupError):
            pass

    # 2. chardet 自动检测（如果可用）
    if _CHARDET_AVAILABLE and chardet is not None:
        try:
            detected = chardet.detect(payload)
            encoding = detected.get("encoding") if detected else None
            confidence = detected.get("confidence", 0.0) if detected else 0.0
            if encoding and confidence >= _CHARDET_CONFIDENCE_THRESHOLD:
                try:
                    return payload.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    pass
        except Exception as e:
            logger.debug(f"chardet 检测失败: {e}")

    # 3. CHARSET_FALLBACK 回退链
    if charset:
        charsets_to_try = [c for c in CHARSET_FALLBACK if c != charset]
    else:
        charsets_to_try = CHARSET_FALLBACK
    for enc in charsets_to_try:
        try:
            return payload.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # 4. 最终回退
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
    """提取邮件附件

    危险扩展名（DANGEROUS_EXTENSIONS）会被标记 ``blocked=True``，
    后续下载逻辑据此跳过下载。
    """
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

            # 危险扩展名拦截
            blocked = is_dangerous_attachment(filename)
            if blocked:
                logger.warning(f"拦截危险附件: {filename}")

            attachments.append(Attachment(
                filename=filename,
                size=size,
                mime_type=mime_type,
                content_id=content_id,
                blocked=blocked,
            ))

    return attachments


def is_dangerous_attachment(filename: str) -> bool:
    """判断附件是否属于危险扩展名。

    Args:
        filename: 附件文件名。

    Returns:
        命中危险扩展名返回 True，否则 False。
    """
    if not filename:
        return False
    # 取小写后缀比较，过滤空扩展名
    lower_name = filename.lower()
    return any(lower_name.endswith(ext) for ext in DANGEROUS_EXTENSIONS)


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


def compute_content_fingerprint(subject: str, body_text: str) -> str:
    """计算邮件内容指纹。

    指纹 = MD5(subject + body_text 前 500 字)，用于内容级去重。

    Args:
        subject: 邮件主题。
        body_text: 邮件纯文本正文。

    Returns:
        32 位十六进制 MD5 字符串。
    """
    raw = f"{subject}{body_text[:500]}"
    return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()


def extract_thread_id(
    in_reply_to: Optional[str],
    references: Optional[str],
) -> Optional[str]:
    """从 In-Reply-To / References 头提取线程 ID。

    优先取 In-Reply-To（去掉空白和尖括号），其次取 References 列表的第一个 ID。
    都没有则返回 None（由调用方决定是否回退到 message_id 作为新线程起点）。

    Args:
        in_reply_to: In-Reply-To 头值。
        references: References 头值（空格分隔的多个 message_id）。

    Returns:
        线程 ID 字符串，无法提取时返回 None。
    """
    if in_reply_to:
        candidate = in_reply_to.strip().strip("<>").strip()
        if candidate:
            return candidate
    if references:
        # References 头是空格分隔的多个 <message-id>
        for ref in references.split():
            candidate = ref.strip().strip("<>").strip()
            if candidate:
                return candidate
    return None


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

        # In-Reply-To / References 头提取
        in_reply_to_raw = msg.get("In-Reply-To", "")
        references_raw = msg.get("References", "")
        in_reply_to = in_reply_to_raw.strip() if in_reply_to_raw else None
        references = references_raw.strip() if references_raw else None

        # content_fingerprint 计算（subject + body_text 前 500 字 MD5）
        content_fingerprint = compute_content_fingerprint(subject, body_text)

        # thread_id 计算（从 in_reply_to 或 references 提取）
        thread_id = extract_thread_id(in_reply_to, references)

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
            in_reply_to=in_reply_to,
            references=references,
            content_fingerprint=content_fingerprint,
            thread_id=thread_id,
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
