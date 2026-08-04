"""邮件元数据仓储"""

import json
from datetime import datetime
from typing import Optional

from src.core.logger import get_logger
from src.core.models import MailData
from src.core.storage.database import Database

logger = get_logger("storage.mail_repo")


class MailRepository:
    """邮件元数据 SQLite 仓储"""

    def __init__(self, db: Database):
        self.db = db

    def upsert_mail(self, mail: MailData, account_id: str = "default") -> None:
        """插入或更新邮件元数据"""
        tags_json = json.dumps(mail.tags, ensure_ascii=False)
        self.db.execute(
            """INSERT OR REPLACE INTO mails
            (message_id, account_id, sender, sender_domain, recipient, subject,
             send_time, receive_time, body_text, body_html, body_file_path,
             category, priority, confidence, need_reply, tags, classify_source,
             content_fingerprint, thread_id, in_reply_to, references_hdr,
             status, is_read, is_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mail.message_id, account_id, mail.sender, mail.sender_domain,
             mail.recipient, mail.subject,
             mail.send_time.isoformat() if isinstance(mail.send_time, datetime) else str(mail.send_time),
             mail.receive_time.isoformat() if isinstance(mail.receive_time, datetime) else str(mail.receive_time),
             mail.body_text, mail.body_html, mail.local_file_path,
             mail.category, mail.priority, mail.confidence,
             int(mail.need_reply), tags_json, mail.classify_source,
             mail.content_fingerprint, mail.thread_id,
             mail.in_reply_to, mail.references,
             mail.status, int(mail.is_read), int(mail.is_sent)),
        )

    def get_mail(self, message_id: str) -> dict | None:
        """查询邮件元数据"""
        return self.db.query_one(
            "SELECT * FROM mails WHERE message_id = ?", (message_id,))

    def list_mails(self, category: str | None = None,
                   status: str | None = None,
                   search_query: str | None = None,
                   limit: int = 100, offset: int = 0) -> list[dict]:
        """按分类/状态/关键词筛选邮件"""
        sql = "SELECT * FROM mails WHERE 1=1"
        params: list = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if search_query:
            sql += " AND (subject LIKE ? OR sender LIKE ? OR body_text LIKE ?)"
            param = f"%{search_query}%"
            params.extend([param, param, param])
        sql += " ORDER BY send_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return self.db.query_all(sql, tuple(params))

    def search_mails(self, query: str, limit: int = 100) -> list[dict]:
        """全文搜索邮件"""
        param = f"%{query}%"
        return self.db.query_all(
            """SELECT * FROM mails
            WHERE subject LIKE ? OR sender LIKE ? OR body_text LIKE ?
            ORDER BY send_time DESC LIMIT ?""",
            (param, param, param, limit))

    def update_status(self, message_id: str, status: str) -> None:
        """更新邮件状态"""
        self.db.execute(
            "UPDATE mails SET status = ? WHERE message_id = ?",
            (status, message_id))

    def update_category(self, message_id: str, category: str,
                        priority: str, confidence: float,
                        need_reply: bool, source: str,
                        reason: str = "", tags: list[str] | None = None) -> None:
        """更新 AI 分类结果"""
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        self.db.execute(
            """UPDATE mails SET category = ?, priority = ?, confidence = ?,
            need_reply = ?, classify_source = ?, tags = ? WHERE message_id = ?""",
            (category, priority, confidence, int(need_reply), source,
             tags_json, message_id))

    def update_tags(self, message_id: str, tags: list[str]) -> None:
        """单独更新标签"""
        tags_json = json.dumps(tags, ensure_ascii=False)
        self.db.execute(
            "UPDATE mails SET tags = ? WHERE message_id = ?",
            (tags_json, message_id))

    def count_by_category(self) -> dict[str, int]:
        """按分类统计"""
        rows = self.db.query_all(
            "SELECT category, COUNT(*) as cnt FROM mails GROUP BY category")
        return {row["category"] or "未分类": row["cnt"] for row in rows}

    def count_unread(self) -> int:
        """统计未读"""
        row = self.db.query_one(
            "SELECT COUNT(*) as cnt FROM mails WHERE is_read = 0")
        return row["cnt"] if row else 0

    def count_by_status(self) -> dict[str, int]:
        """按状态统计"""
        rows = self.db.query_all(
            "SELECT status, COUNT(*) as cnt FROM mails GROUP BY status")
        return {row["status"]: row["cnt"] for row in rows}

    def get_mails_by_thread(self, thread_id: str) -> list[dict]:
        """获取同一线程的邮件"""
        return self.db.query_all(
            "SELECT * FROM mails WHERE thread_id = ? ORDER BY send_time",
            (thread_id,))
