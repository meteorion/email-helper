"""数据模型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class Attachment:
    """邮件附件"""
    filename: str
    size: int
    mime_type: str
    content_id: Optional[str] = None  # 内联附件的 CID
    local_path: Optional[str] = None  # 本地存储路径
    blocked: bool = False  # 危险扩展名拦截标记

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "size": self.size,
            "mime_type": self.mime_type,
            "content_id": self.content_id,
            "local_path": self.local_path,
            "blocked": self.blocked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Attachment":
        return cls(
            filename=data["filename"],
            size=data["size"],
            mime_type=data["mime_type"],
            content_id=data.get("content_id"),
            local_path=data.get("local_path"),
            blocked=data.get("blocked", False),
        )


@dataclass
class MailData:
    """邮件数据"""
    message_id: str
    sender: str
    sender_domain: str
    recipient: str
    subject: str
    send_time: datetime
    receive_time: datetime
    body_text: str
    body_html: Optional[str]
    attachments: list[Attachment] = field(default_factory=list)
    is_read: bool = False
    is_sent: bool = False
    local_file_path: Optional[str] = None
    # Alpha 新增字段
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    content_fingerprint: Optional[str] = None
    thread_id: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    confidence: float = 0.0
    need_reply: bool = False
    tags: list[str] = field(default_factory=list)
    classify_source: Optional[str] = None  # rule/llm/cache/manual
    status: str = "new"  # new/pending_manual/processing/processed/archived

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "sender_domain": self.sender_domain,
            "recipient": self.recipient,
            "subject": self.subject,
            "send_time": self.send_time.isoformat(),
            "receive_time": self.receive_time.isoformat(),
            "body_text": self.body_text,
            "body_html": self.body_html,
            "attachments": [att.to_dict() for att in self.attachments],
            "is_read": self.is_read,
            "is_sent": self.is_sent,
            "local_file_path": self.local_file_path,
            "in_reply_to": self.in_reply_to,
            "references": self.references,
            "content_fingerprint": self.content_fingerprint,
            "thread_id": self.thread_id,
            "category": self.category,
            "priority": self.priority,
            "confidence": self.confidence,
            "need_reply": self.need_reply,
            "tags": self.tags,
            "classify_source": self.classify_source,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MailData":
        return cls(
            message_id=data["message_id"],
            sender=data["sender"],
            sender_domain=data["sender_domain"],
            recipient=data["recipient"],
            subject=data["subject"],
            send_time=datetime.fromisoformat(data["send_time"]),
            receive_time=datetime.fromisoformat(data["receive_time"]),
            body_text=data["body_text"],
            body_html=data.get("body_html"),
            attachments=[Attachment.from_dict(att) for att in data.get("attachments", [])],
            is_read=data.get("is_read", False),
            is_sent=data.get("is_sent", False),
            local_file_path=data.get("local_file_path"),
            in_reply_to=data.get("in_reply_to"),
            references=data.get("references"),
            content_fingerprint=data.get("content_fingerprint"),
            thread_id=data.get("thread_id"),
            category=data.get("category"),
            priority=data.get("priority"),
            confidence=data.get("confidence", 0.0),
            need_reply=data.get("need_reply", False),
            tags=data.get("tags", []),
            classify_source=data.get("classify_source"),
            status=data.get("status", "new"),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "MailData":
        return cls.from_dict(json.loads(json_str))
