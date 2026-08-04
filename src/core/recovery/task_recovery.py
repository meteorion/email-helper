"""任务恢复管理器（容错恢复）。

启动时调用 ``TaskRecovery.recover_on_startup``，将崩溃未完成的任务
（running 状态）标记为 failed，并将可重试的任务重新加入对应引擎的处理队列；
同时清理超期未处理的 pending 任务。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from src.core.logger import get_logger
from src.core.storage.task_repository import (
    STATUS_ABORTED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    TYPE_AI_CLASSIFY,
    TYPE_MAIL_FETCH,
    TYPE_NOTIFICATION_SEND,
    TYPE_WORKFLOW_EXECUTE,
    TaskRepository,
)

logger = get_logger("recovery.task_recovery")


# 默认 pending 任务清理阈值（天）
DEFAULT_PENDING_CLEANUP_DAYS: int = 7


class TaskRecovery:
    """任务恢复管理器。

    在程序启动时调用 ``recover_on_startup``，处理上次崩溃残留的任务：
    1. running → failed（崩溃未完成）
    2. failed 且可重试 → 通过回调重新加入对应引擎队列
    3. pending 超过 7 天 → aborted
    """

    def __init__(
        self,
        task_repo: TaskRepository,
        mail_repo: Any = None,
        execution_repo: Any = None,
    ) -> None:
        """初始化任务恢复管理器。

        Args:
            task_repo: TaskRepository 实例。
            mail_repo: MailRepository 实例（可选，用于查邮件元数据）。
            execution_repo: ExecutionRepository 实例（可选，用于清理 running 流程记录）。
        """
        self.task_repo: TaskRepository = task_repo
        self.mail_repo: Any = mail_repo
        self.execution_repo: Any = execution_repo
        # 引擎恢复回调：按任务类型注册，签名为 (task_dict) -> None
        self._recovery_callbacks: dict[str, Callable[[dict], None]] = {}

    # ── 回调注册 ─────────────────────────────────────

    def register_recovery_callback(
        self,
        task_type: str,
        callback: Callable[[dict], None],
    ) -> None:
        """注册任务恢复回调。

        Args:
            task_type: 任务类型（mail_fetch / ai_classify / workflow_execute / notification_send）。
            callback: 接收任务字典的回调函数。
        """
        self._recovery_callbacks[task_type] = callback
        logger.info(f"已注册任务恢复回调: type={task_type}")

    # ── 启动恢复主流程 ───────────────────────────────

    def recover_on_startup(
        self,
        classifier: Any = None,
        workflow_engine: Any = None,
        notification_engine: Any = None,
    ) -> list[dict]:
        """启动恢复流程。

        步骤：
        1. 所有 running 的 tasks → 标记为 failed（崩溃未完成）。
        2. 所有 failed 可重试的 tasks → 通过回调重新加入对应 Worker 队列。
        3. execution_records 中 running 的记录 → 标记为 failed。
        4. pending 超过 7 天的 tasks → aborted。

        Args:
            classifier: AI 分类器（可选，兼容旧签名）。
            workflow_engine: 流程引擎（可选，兼容旧签名）。
            notification_engine: 通知引擎（可选，兼容旧签名）。

        Returns:
            恢复报告列表，每项形如 ``{task_id, type, action, result}``。
        """
        logger.info("开始执行启动恢复流程")
        report: list[dict] = []

        # 1. running → failed
        crashed_count = self.mark_crashed_tasks()
        logger.info(f"标记崩溃任务 (running → failed): {crashed_count} 个")
        for _ in range(crashed_count):
            report.append({
                "task_id": "",
                "type": "",
                "action": "mark_failed",
                "result": "crashed_running_marked_failed",
            })

        # 2. failed 可重试 → 重新入队
        retryable = self.task_repo.get_retryable_tasks()
        logger.info(f"可重试任务: {len(retryable)} 个")
        for task in retryable:
            entry = self._retry_task(task)
            report.append(entry)

        # 3. 清理 execution_records running
        exec_cleaned = self._mark_crashed_execution_records()
        if exec_cleaned:
            logger.info(f"清理崩溃流程记录 (running → failed): {exec_cleaned} 个")
            report.append({
                "task_id": "",
                "type": "execution_record",
                "action": "mark_failed",
                "result": f"crashed_execution_records_marked_failed:{exec_cleaned}",
            })

        # 4. pending 超期 → aborted
        stale = self.task_repo.get_stale_pending_tasks(
            days=DEFAULT_PENDING_CLEANUP_DAYS
        )
        logger.info(f"超期 pending 任务: {len(stale)} 个")
        for task in stale:
            self.task_repo.abort_task(
                task["id"], reason="pending 超过 7 天未处理，自动中止"
            )
            report.append({
                "task_id": task.get("id", ""),
                "type": task.get("type", ""),
                "action": "abort_stale",
                "result": "pending_expired_aborted",
            })

        # 5. failed 已超最大重试次数 → aborted
        exceeded = self.task_repo.get_failed_exceeded_retries()
        for task in exceeded:
            self.task_repo.abort_task(
                task["id"], reason="超过最大重试次数，自动中止"
            )
            report.append({
                "task_id": task.get("id", ""),
                "type": task.get("type", ""),
                "action": "abort_exceeded_retries",
                "result": "max_retries_exceeded_aborted",
            })

        logger.info(
            f"启动恢复流程完毕，共处理 {len(report)} 项"
        )
        return report

    def mark_crashed_tasks(self) -> int:
        """将所有 running 状态的任务标记为 failed。

        Returns:
            标记的任务数量。
        """
        running = self.task_repo.get_running_tasks()
        for task in running:
            self.task_repo.update_status(
                task["id"],
                STATUS_FAILED,
                error="程序异常退出中断",
            )
        return len(running)

    # ── 内部辅助 ─────────────────────────────────────

    def _retry_task(self, task: dict) -> dict:
        """对单个可重试任务触发恢复回调。

        Args:
            task: 任务字典。

        Returns:
            恢复报告条目 ``{task_id, type, action, result}``。
        """
        task_id = task.get("id", "")
        task_type = task.get("type", "")
        result: str

        # 重试次数 +1
        self.task_repo.increment_attempt(task_id)

        callback = self._recovery_callbacks.get(task_type)
        if callback is None:
            # 没有注册回调，根据类型走默认处理
            result = self._default_retry(task)
        else:
            try:
                callback(task)
                # 回到 pending，等待引擎拉起
                self.task_repo.update_status(task_id, STATUS_PENDING)
                result = "requeued_via_callback"
            except Exception as e:
                logger.error(
                    f"恢复回调执行失败 task_id={task_id} type={task_type}: {e}",
                    exc_info=True,
                )
                self.task_repo.update_status(
                    task_id, STATUS_FAILED, error=f"恢复回调失败: {e}"
                )
                result = f"callback_failed:{e}"

        return {
            "task_id": task_id,
            "type": task_type,
            "action": "retry",
            "result": result,
        }

    def _default_retry(self, task: dict) -> str:
        """未注册回调时的默认重试策略。

        - mail_fetch: 不特殊处理，下次调度周期会覆盖。
        - ai_classify / workflow_execute / notification_send: 标记为 pending，等待引擎拉起。

        Args:
            task: 任务字典。

        Returns:
            处理结果描述。
        """
        task_id = task.get("id", "")
        task_type = task.get("type", "")
        if task_type == TYPE_MAIL_FETCH:
            # 邮件拉取由调度器自动覆盖，无需重复入队
            self.task_repo.update_status(
                task_id, STATUS_ABORTED, error="mail_fetch 由调度器自动覆盖，无需恢复"
            )
            return "skipped_mail_fetch"
        # 其他类型：标记为 pending 等待引擎拉起
        self.task_repo.update_status(task_id, STATUS_PENDING)
        return "marked_pending_default"

    def _mark_crashed_execution_records(self) -> int:
        """将 execution_records 中 running 的记录标记为 failed。

        Returns:
            标记的记录数量。
        """
        if self.execution_repo is None:
            return 0
        try:
            running = self.execution_repo.get_running_records()
            for record in running:
                self.execution_repo.update_status(
                    record["id"], STATUS_FAILED,
                    error_message="程序异常退出中断",
                )
            return len(running)
        except Exception as e:
            logger.warning(f"清理 execution_records 失败: {e}")
            return 0


__all__ = ["TaskRecovery", "DEFAULT_PENDING_CLEANUP_DAYS"]
