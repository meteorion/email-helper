"""失败通知持久化队列"""

import json
import time
import uuid
from typing import Any

from src.core.logger import get_logger

logger = get_logger("notification.failure_queue")

# 默认重试间隔（秒）= 30 分钟
_DEFAULT_RETRY_INTERVAL = 1800


class FailureQueue:
    """失败通知持久化队列

    表结构（假设已创建）:
        CREATE TABLE failed_notifications (
            id TEXT PRIMARY KEY, channel TEXT, recipient TEXT, content TEXT,
            error TEXT, retry_count INTEGER DEFAULT 0,
            first_failed_at REAL, last_failed_at REAL, next_retry_at REAL,
            status TEXT DEFAULT 'pending'
        );

    时间字段统一使用 Unix 时间戳 REAL 类型，避免 TEXT/REAL 混用导致
    get_retryable() 失效。
    """

    def __init__(self, db: Any):
        """db 需提供 execute / fetchall 方法"""
        self.db = db

    def add_failure(
        self, channel: str, recipient: str, content: dict, error: str
    ) -> str:
        """写入 failed_notifications 表，时间用 Unix 时间戳 REAL

        Returns:
            failure_id
        """
        failure_id = str(uuid.uuid4())
        now = time.time()
        try:
            self.db.execute(
                "INSERT INTO failed_notifications "
                "(id, channel, recipient, content, error, retry_count, "
                "first_failed_at, last_failed_at, next_retry_at, status) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'pending')",
                (
                    failure_id,
                    channel,
                    recipient,
                    json.dumps(content, ensure_ascii=False),
                    error,
                    now,
                    now,
                    now + _DEFAULT_RETRY_INTERVAL,
                ),
            )
            logger.info(f"已记录失败通知: {failure_id} channel={channel}")
        except Exception as e:
            logger.error(f"写入失败队列异常: {e}", exc_info=True)
        return failure_id

    def get_retryable(self) -> list[dict]:
        """获取可重试的失败通知

        SELECT * WHERE next_retry_at <= ? AND status != 'given_up'
        （next_retry_at 为 Unix 时间戳 REAL）
        """
        now = time.time()
        try:
            rows = self.db.fetchall(
                "SELECT id, channel, recipient, content, error, retry_count, "
                "first_failed_at, last_failed_at, next_retry_at, status "
                "FROM failed_notifications "
                "WHERE next_retry_at <= ? AND status != 'given_up'",
                (now,),
            )
        except Exception as e:
            logger.error(f"查询可重试通知异常: {e}", exc_info=True)
            return []

        result: list[dict] = []
        for row in rows:
            result.append(
                {
                    "id": row[0],
                    "channel": row[1],
                    "recipient": row[2],
                    "content": row[3],
                    "error": row[4],
                    "retry_count": row[5],
                    "first_failed_at": row[6],
                    "last_failed_at": row[7],
                    "next_retry_at": row[8],
                    "status": row[9],
                }
            )
        return result

    def mark_retrying(self, failure_id: str) -> None:
        """标记为重试中"""
        try:
            self.db.execute(
                "UPDATE failed_notifications SET status = 'retrying' WHERE id = ?",
                (failure_id,),
            )
        except Exception as e:
            logger.error(f"标记重试中异常: {e}", exc_info=True)

    def mark_given_up(self, failure_id: str) -> None:
        """标记为放弃"""
        try:
            self.db.execute(
                "UPDATE failed_notifications SET status = 'given_up' WHERE id = ?",
                (failure_id,),
            )
            logger.warning(f"失败通知已放弃: {failure_id}")
        except Exception as e:
            logger.error(f"标记放弃异常: {e}", exc_info=True)

    def update_retry(
        self, failure_id: str, next_retry: float, error: str
    ) -> None:
        """更新重试信息"""
        now = time.time()
        try:
            self.db.execute(
                "UPDATE failed_notifications "
                "SET retry_count = retry_count + 1, last_failed_at = ?, "
                "next_retry_at = ?, error = ?, status = 'pending' "
                "WHERE id = ?",
                (now, next_retry, error, failure_id),
            )
        except Exception as e:
            logger.error(f"更新重试信息异常: {e}", exc_info=True)

    def remove(self, failure_id: str) -> None:
        """重试成功后删除记录"""
        try:
            self.db.execute(
                "DELETE FROM failed_notifications WHERE id = ?",
                (failure_id,),
            )
            logger.info(f"失败通知已清除: {failure_id}")
        except Exception as e:
            logger.error(f"删除失败记录异常: {e}", exc_info=True)
