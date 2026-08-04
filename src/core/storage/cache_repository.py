"""去重缓存与分类缓存仓储"""

import json
import time
from datetime import datetime, timedelta

from src.core.logger import get_logger
from src.core.storage.database import Database

logger = get_logger("storage.cache_repo")


class CacheRepository:
    """去重缓存 + 分类缓存仓储"""

    def __init__(self, db: Database):
        self.db = db

    # ── seen_message_ids ──────────────────────────

    def is_seen(self, message_id: str, account_id: str = "default") -> bool:
        """是否已处理"""
        row = self.db.query_one(
            "SELECT 1 FROM seen_message_ids WHERE message_id = ? AND account_id = ?",
            (message_id, account_id))
        return row is not None

    def mark_seen(self, message_id: str, account_id: str = "default") -> None:
        """标记已处理"""
        self.db.execute(
            """INSERT OR REPLACE INTO seen_message_ids (message_id, account_id, first_seen_at, last_seen_at)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (message_id, account_id))

    def get_all_seen_ids(self, account_id: str = "default") -> set[str]:
        """获取所有已处理 ID（兼容旧接口）"""
        rows = self.db.query_all(
            "SELECT message_id FROM seen_message_ids WHERE account_id = ?",
            (account_id,))
        return {row["message_id"] for row in rows}

    def cleanup_old_seen_ids(self, days: int = 30) -> int:
        """清理旧的去重记录"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self.db.execute(
            "DELETE FROM seen_message_ids WHERE last_seen_at < ?", (cutoff,))
        return cursor.rowcount

    # ── classify_cache ────────────────────────────

    def get_classify_cache(self, mail_hash: str) -> dict | None:
        """获取分类缓存，返回完整 ClassifyResult dict"""
        row = self.db.query_one(
            """SELECT * FROM classify_cache
            WHERE mail_hash = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)""",
            (mail_hash,))
        if not row:
            return None
        # 优先从 result_json 恢复完整结果
        if row.get("result_json"):
            try:
                return json.loads(row["result_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        # 回退到逐字段构造
        return {
            "category": row["category"],
            "priority": row["priority"],
            "confidence": row["confidence"],
            "need_reply": bool(row["need_reply"]),
            "reason": row["reason"],
            "source": row["source"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
        }

    def set_classify_cache(self, mail_hash: str, result: dict,
                           ttl_hours: int = 24) -> None:
        """存入分类缓存（存完整 ClassifyResult）"""
        expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
        tags_json = json.dumps(result.get("tags", []), ensure_ascii=False)
        result_json = json.dumps(result, ensure_ascii=False)
        self.db.execute(
            """INSERT OR REPLACE INTO classify_cache
            (mail_hash, category, priority, confidence, need_reply, reason, source,
             tags, result_json, classified_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)""",
            (mail_hash, result.get("category"), result.get("priority"),
             result.get("confidence", 0.0), int(result.get("need_reply", False)),
             result.get("reason", ""), result.get("source", ""),
             tags_json, result_json, expires_at))

    def cleanup_expired_classify_cache(self) -> int:
        """清理过期分类缓存"""
        cursor = self.db.execute(
            "DELETE FROM classify_cache WHERE expires_at < CURRENT_TIMESTAMP")
        return cursor.rowcount

    # ── 多级去重 ──────────────────────────────────

    def is_duplicate_by_fingerprint(self, fp: str, lookback_days: int = 7) -> bool:
        """内容指纹去重"""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        row = self.db.query_one(
            """SELECT 1 FROM mails
            WHERE content_fingerprint = ? AND created_at > ? LIMIT 1""",
            (fp, cutoff))
        return row is not None

    def mark_fingerprint(self, fp: str) -> None:
        """标记指纹（实际上 mails 表 upsert 时已有，此方法为接口兼容）"""
        pass

    def get_thread_id(self, in_reply_to: str | None,
                      references: str | None) -> str | None:
        """从 In-Reply-To / References 提取线程 ID"""
        if in_reply_to:
            # 检查数据库中是否已有此 message_id 的 thread_id
            row = self.db.query_one(
                "SELECT thread_id FROM mails WHERE message_id = ?",
                (in_reply_to.strip(),))
            if row and row["thread_id"]:
                return row["thread_id"]
            return in_reply_to.strip()
        if references:
            refs = references.split()
            if refs:
                first_ref = refs[0].strip()
                row = self.db.query_one(
                    "SELECT thread_id FROM mails WHERE message_id = ?",
                    (first_ref,))
                if row and row["thread_id"]:
                    return row["thread_id"]
                return first_ref
        return None

    def is_thread_seen(self, thread_id: str) -> bool:
        """线程是否已存在"""
        row = self.db.query_one(
            "SELECT 1 FROM mails WHERE thread_id = ? LIMIT 1",
            (thread_id,))
        return row is not None

    def mark_thread_seen(self, thread_id: str) -> None:
        """标记线程（实际上 mails 表 upsert 时已有，此方法为接口兼容）"""
        pass
