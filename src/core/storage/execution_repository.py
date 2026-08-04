"""流程执行记录仓储"""

import json
import uuid
from datetime import datetime

from src.core.logger import get_logger
from src.core.storage.database import Database

logger = get_logger("storage.exec_repo")


class ExecutionRepository:
    """流程执行记录 SQLite 仓储"""

    def __init__(self, db: Database):
        self.db = db

    def create_record(self, mail_id: str, workflow_name: str,
                      workflow_version: str) -> str:
        """创建执行记录，返回 execution_id"""
        exec_id = str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO execution_records
            (id, mail_id, workflow_name, workflow_version, status, started_at)
            VALUES (?, ?, ?, ?, 'running', CURRENT_TIMESTAMP)""",
            (exec_id, mail_id, workflow_name, workflow_version))
        return exec_id

    def update_status(self, exec_id: str, status: str,
                      error_message: str = "") -> None:
        """更新执行状态"""
        if status in ("success", "failed", "aborted"):
            self.db.execute(
                """UPDATE execution_records
                SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (status, error_message, exec_id))
        else:
            self.db.execute(
                "UPDATE execution_records SET status = ? WHERE id = ?",
                (status, exec_id))

    def update_step(self, exec_id: str, current_step: str,
                    context_snapshot: dict | None = None) -> None:
        """更新当前步骤和上下文快照"""
        snapshot_json = json.dumps(context_snapshot, ensure_ascii=False) if context_snapshot else None
        self.db.execute(
            """UPDATE execution_records
            SET current_step = ?, context_snapshot = ? WHERE id = ?""",
            (current_step, snapshot_json, exec_id))

    def get_record(self, exec_id: str) -> dict | None:
        """查询执行记录"""
        return self.db.query_one(
            "SELECT * FROM execution_records WHERE id = ?", (exec_id,))

    def list_by_mail(self, mail_id: str) -> list[dict]:
        """查询某邮件的所有执行记录"""
        return self.db.query_all(
            """SELECT * FROM execution_records WHERE mail_id = ?
            ORDER BY started_at DESC""",
            (mail_id,))

    def list_recent(self, limit: int = 50,
                    status: str | None = None) -> list[dict]:
        """查询最近的执行记录"""
        if status:
            return self.db.query_all(
                """SELECT * FROM execution_records WHERE status = ?
                ORDER BY started_at DESC LIMIT ?""",
                (status, limit))
        return self.db.query_all(
            "SELECT * FROM execution_records ORDER BY started_at DESC LIMIT ?",
            (limit,))

    def get_running_records(self) -> list[dict]:
        """获取所有 running 状态的记录（用于恢复）"""
        return self.db.query_all(
            "SELECT * FROM execution_records WHERE status = 'running'")

    def get_snapshot(self, exec_id: str) -> dict | None:
        """获取上下文快照"""
        row = self.db.query_one(
            "SELECT context_snapshot FROM execution_records WHERE id = ?",
            (exec_id,))
        if row and row["context_snapshot"]:
            try:
                return json.loads(row["context_snapshot"])
            except (json.JSONDecodeError, TypeError):
                return None
        return None
