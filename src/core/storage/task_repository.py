"""任务状态仓储（容错恢复）。

封装 SQLite ``tasks`` 表的读写，提供任务生命周期管理：
创建、状态/步骤更新、重试计数、按状态查询等。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from src.core.logger import get_logger

logger = get_logger("storage.task_repository")


# 任务状态常量
STATUS_PENDING: str = "pending"
STATUS_RUNNING: str = "running"
STATUS_SUCCESS: str = "success"
STATUS_FAILED: str = "failed"
STATUS_ABORTED: str = "aborted"

# 任务类型常量
TYPE_MAIL_FETCH: str = "mail_fetch"
TYPE_AI_CLASSIFY: str = "ai_classify"
TYPE_WORKFLOW_EXECUTE: str = "workflow_execute"
TYPE_NOTIFICATION_SEND: str = "notification_send"

# 默认重试间隔（分钟）
DEFAULT_RETRY_INTERVAL_MINUTES: int = 5

# pending 任务清理阈值（天）
PENDING_CLEANUP_DAYS: int = 7


class TaskRepository:
    """任务状态仓储，封装 ``tasks`` 表的所有读写操作。"""

    def __init__(self, db: Any) -> None:
        """初始化任务仓储。

        Args:
            db: Database 实例。
        """
        self.db: Any = db

    def create_task(
        self,
        type: str,
        mail_id: Optional[str],
        workflow_name: Optional[str],
        notification_data: Optional[dict],
        max_retries: int = 3,
    ) -> str:
        """创建新任务，返回 task_id。

        Args:
            type: 任务类型（mail_fetch / ai_classify / workflow_execute / notification_send）。
            mail_id: 关联邮件 message_id，无关联时为 None。
            workflow_name: 关联流程名，无关联时为 None。
            notification_data: 通知任务的数据载荷，无关联时为 None。
            max_retries: 最大重试次数，默认 3。

        Returns:
            新建任务的 task_id（UUID 字符串）。
        """
        task_id = str(uuid.uuid4())
        notif_json = (
            json.dumps(notification_data, ensure_ascii=False)
            if notification_data
            else None
        )
        self.db.execute(
            """INSERT INTO tasks
            (id, type, mail_id, workflow_name, notification_data,
             status, max_retries, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (
                task_id,
                type,
                mail_id,
                workflow_name,
                notif_json,
                STATUS_PENDING,
                max_retries,
            ),
        )
        logger.info(f"创建任务: id={task_id}, type={type}, mail_id={mail_id}")
        return task_id

    def update_status(
        self,
        task_id: str,
        status: str,
        error: str = "",
    ) -> None:
        """更新任务状态。

        - 进入 running 时记录 started_at。
        - 进入 success / failed / aborted 时记录 completed_at 和错误信息。
        - failed 状态会基于当前 attempt_count 计算 next_retry_at。

        Args:
            task_id: 任务 ID。
            status: 新状态。
            error: 错误信息（失败时使用）。
        """
        if status == STATUS_RUNNING:
            self.db.execute(
                """UPDATE tasks
                SET status = ?, started_at = CURRENT_TIMESTAMP,
                    error_message = NULL
                WHERE id = ?""",
                (status, task_id),
            )
        elif status in (STATUS_SUCCESS, STATUS_ABORTED):
            self.db.execute(
                """UPDATE tasks
                SET status = ?, completed_at = CURRENT_TIMESTAMP,
                    error_message = ?
                WHERE id = ?""",
                (status, error, task_id),
            )
        elif status == STATUS_FAILED:
            # 计算下一次重试时间
            next_retry = (
                datetime.now() + timedelta(minutes=DEFAULT_RETRY_INTERVAL_MINUTES)
            ).isoformat()
            self.db.execute(
                """UPDATE tasks
                SET status = ?, completed_at = CURRENT_TIMESTAMP,
                    error_message = ?, next_retry_at = ?
                WHERE id = ?""",
                (status, error, next_retry, task_id),
            )
        else:
            self.db.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
        logger.info(f"任务状态更新: id={task_id}, status={status}")

    def update_step(
        self,
        task_id: str,
        current_step: str,
        context_data: Optional[dict] = None,
    ) -> None:
        """更新任务当前步骤和上下文快照。

        Args:
            task_id: 任务 ID。
            current_step: 当前步骤标识。
            context_data: 上下文快照字典，None 表示不更新。
        """
        ctx_json = (
            json.dumps(context_data, ensure_ascii=False)
            if context_data is not None
            else None
        )
        self.db.execute(
            """UPDATE tasks
            SET current_step = ?, context_data = ?
            WHERE id = ?""",
            (current_step, ctx_json, task_id),
        )
        logger.debug(
            f"任务步骤更新: id={task_id}, step={current_step}"
        )

    def increment_attempt(self, task_id: str) -> int:
        """任务重试次数 +1，返回更新后的 attempt_count。

        Args:
            task_id: 任务 ID。

        Returns:
            更新后的 attempt_count；任务不存在时返回 0。
        """
        row = self.db.query_one(
            "SELECT attempt_count FROM tasks WHERE id = ?",
            (task_id,),
        )
        if not row:
            return 0
        new_count = int(row["attempt_count"]) + 1
        self.db.execute(
            "UPDATE tasks SET attempt_count = ?, next_retry_at = NULL WHERE id = ?",
            (new_count, task_id),
        )
        logger.info(f"任务重试次数 +1: id={task_id}, attempt_count={new_count}")
        return new_count

    def get_task(self, task_id: str) -> Optional[dict]:
        """查询任务详情。

        Args:
            task_id: 任务 ID。

        Returns:
            任务字典（含解析后的 notification_data / context_data），不存在返回 None。
        """
        row = self.db.query_one(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        )
        return self._normalize_row(row) if row else None

    def get_running_tasks(self) -> list[dict]:
        """查询所有 running 状态的任务。

        Returns:
            任务字典列表。
        """
        rows = self.db.query_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY started_at ASC",
            (STATUS_RUNNING,),
        )
        return [self._normalize_row(r) for r in rows]

    def get_pending_tasks(self) -> list[dict]:
        """查询所有 pending 状态的任务。

        Returns:
            任务字典列表。
        """
        rows = self.db.query_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at ASC",
            (STATUS_PENDING,),
        )
        return [self._normalize_row(r) for r in rows]

    def get_retryable_tasks(self) -> list[dict]:
        """查询所有 failed 且达到重试时间的任务。

        条件：status='failed' AND next_retry_at <= now() AND attempt_count < max_retries。

        Returns:
            可重试任务字典列表。
        """
        now_iso = datetime.now().isoformat()
        rows = self.db.query_all(
            """SELECT * FROM tasks
            WHERE status = ?
              AND next_retry_at IS NOT NULL
              AND next_retry_at <= ?
              AND attempt_count < max_retries
            ORDER BY next_retry_at ASC""",
            (STATUS_FAILED, now_iso),
        )
        return [self._normalize_row(r) for r in rows]

    def get_failed_exceeded_retries(self) -> list[dict]:
        """查询 failed 且超出最大重试次数的任务（用于标记 aborted）。

        Returns:
            超出重试上限的任务字典列表。
        """
        rows = self.db.query_all(
            """SELECT * FROM tasks
            WHERE status = ? AND attempt_count >= max_retries""",
            (STATUS_FAILED,),
        )
        return [self._normalize_row(r) for r in rows]

    def get_stale_pending_tasks(self, days: int = PENDING_CLEANUP_DAYS) -> list[dict]:
        """查询 pending 超过指定天数的任务（用于清理）。

        Args:
            days: 阈值天数，默认 7 天。

        Returns:
            超期 pending 任务字典列表。
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.query_all(
            """SELECT * FROM tasks
            WHERE status = ? AND created_at < ?
            ORDER BY created_at ASC""",
            (STATUS_PENDING, cutoff),
        )
        return [self._normalize_row(r) for r in rows]

    def abort_task(self, task_id: str, reason: str = "") -> None:
        """将任务标记为 aborted。

        Args:
            task_id: 任务 ID。
            reason: 中止原因。
        """
        self.update_status(task_id, STATUS_ABORTED, error=reason)

    # ── 工具方法 ─────────────────────────────────────

    @staticmethod
    def _normalize_row(row: Optional[dict]) -> Optional[dict]:
        """把数据库行中的 JSON 字段解析为 Python 对象。

        Args:
            row: 数据库行字典。

        Returns:
            解析后的字典；输入为 None 时返回 None。
        """
        if not row:
            return None
        result = dict(row)
        for key in ("notification_data", "context_data"):
            value = result.get(key)
            if isinstance(value, str) and value:
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # 保留原始字符串
                    pass
        return result


__all__ = [
    "TaskRepository",
    "STATUS_PENDING",
    "STATUS_RUNNING",
    "STATUS_SUCCESS",
    "STATUS_FAILED",
    "STATUS_ABORTED",
    "TYPE_MAIL_FETCH",
    "TYPE_AI_CLASSIFY",
    "TYPE_WORKFLOW_EXECUTE",
    "TYPE_NOTIFICATION_SEND",
]
