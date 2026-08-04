"""重复检测 Action：调用 execution_repo 查询 lookback 窗口内相同 key_fields 的执行记录。"""

from __future__ import annotations

import json
from typing import Any

from src.workflow.actions.base import BaseAction


class CheckDuplicateAction(BaseAction):
    """基于 key_fields 在历史执行记录中检测重复，返回布尔值。"""

    action_name = "check_duplicate"

    def execute(self) -> Any:
        repo = self._require_dep("execution_repo")
        key_fields = self.config.get("key_fields", []) or []
        lookback_hours = self.config.get("lookback_hours", 24)

        # 构造去重 key 字符串
        key_str = "|".join(self._stringify(f) for f in key_fields)
        if not key_str:
            # 无 key_fields 时直接判为非重复
            return False

        # 优先调用仓储的专用接口
        if hasattr(repo, "check_duplicate"):
            try:
                return bool(repo.check_duplicate(key_str, lookback_hours))
            except Exception as exc:
                self.logger.warning(f"execution_repo.check_duplicate 调用失败: {exc}")

        # 兜底：扫描近期执行记录的 context_snapshot
        lookback_days = max(1, lookback_hours // 24 + 1)
        list_recent = getattr(repo, "list_recent", None)
        if list_recent is None:
            return False
        try:
            recent_records = list_recent(days=lookback_days) or []
        except Exception as exc:
            self.logger.warning(f"execution_repo.list_recent 调用失败: {exc}")
            return False

        for record in recent_records:
            snapshot = record.get("context_snapshot") if isinstance(record, dict) else None
            if isinstance(snapshot, str):
                try:
                    snapshot = json.loads(snapshot)
                except json.JSONDecodeError:
                    snapshot = None
            if not isinstance(snapshot, dict):
                continue
            if self._snapshot_contains_key(snapshot, key_str):
                return True
        return False

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _snapshot_contains_key(snapshot: dict, key_str: str) -> bool:
        """在快照的 step_outputs 中查找匹配的 key 字符串。"""
        step_outputs = snapshot.get("step_outputs", {}) or {}
        for output in step_outputs.values():
            if isinstance(output, dict):
                joined = "|".join(str(v) for v in output.values())
                if joined == key_str:
                    return True
                # 也检查单值匹配
                for v in output.values():
                    if str(v) == key_str:
                        return True
            elif str(output) == key_str:
                return True
        return False
