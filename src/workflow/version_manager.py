"""流程版本管理器 VersionManager

对 WorkflowLoader 的版本相关操作做一层语义化封装，便于上层（GUI / API）
调用，不直接操作文件系统。
"""

from __future__ import annotations

from typing import Any

from src.core.logger import get_logger
from src.workflow.loader import WorkflowLoader

logger = get_logger("workflow.version_manager")


class VersionManager:
    """流程版本管理器，封装 WorkflowLoader 的版本管理能力。"""

    def __init__(self, loader: WorkflowLoader):
        self.loader = loader

    def list_versions(self, name: str) -> list[dict]:
        """返回指定流程的全部版本元信息。"""
        return self.loader.list_versions(name)

    def get_current_version(self, name: str) -> str | None:
        """返回当前版本号。"""
        return self.loader.get_current_version(name)

    def load_version(self, name: str, version: str) -> dict:
        """加载指定版本的流程定义。"""
        return self.loader.load_workflow(name, version)

    def load_current(self, name: str) -> dict:
        """加载 current 版本的流程定义。"""
        return self.loader.load_workflow(name)

    def save_new_version(
        self, name: str, yaml_content: str, description: str = ""
    ) -> str:
        """保存新版本并切换 current，返回新版本号。"""
        return self.loader.save_new_version(name, yaml_content, description)

    def rollback(self, name: str, to_version: str) -> None:
        """回滚 current 到指定历史版本。"""
        self.loader.rollback(name, to_version)

    def get_version_info(self, name: str, version: str) -> dict | None:
        """查询单个版本元信息，不存在返回 None。"""
        for v in self.list_versions(name):
            if v.get("version") == version:
                return v
        return None

    def compare_versions(
        self, name: str, version_a: str, version_b: str
    ) -> dict[str, Any]:
        """粗粒度对比两个版本（返回各自定义的关键字段差异）。

        Alpha 阶段不做细粒度 diff，仅返回两边的关键字段供上层展示。
        """
        def_a = self.load_version(name, version_a)
        def_b = self.load_version(name, version_b)
        return {
            "version_a": version_a,
            "version_b": version_b,
            "a_summary": _summarize(def_a),
            "b_summary": _summarize(def_b),
            "a_steps": len(def_a.get("steps", []) or []),
            "b_steps": len(def_b.get("steps", []) or []),
        }


def _summarize(wf_def: dict) -> dict:
    """提取流程定义的关键摘要字段。"""
    return {
        "name": wf_def.get("name", ""),
        "version": wf_def.get("version", ""),
        "enabled": wf_def.get("enabled", True),
        "description": wf_def.get("description", ""),
        "trigger_mail_type": wf_def.get("trigger", {}).get("mail_type"),
        "trigger_priority": wf_def.get("trigger", {}).get("priority", 0),
    }
