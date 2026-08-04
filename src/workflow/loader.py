"""YAML 流程加载器 WorkflowLoader

目录结构（每个流程一个子目录）：
    workflows/{name}/
        current/workflow.yaml       当前生效版本的 YAML
        versions/{version}/workflow.yaml  历史版本归档
        versions.json               版本元信息

versions.json 结构：
    {
      "workflow_name": "审批邮件处理流程",
      "current_version": "1.1",
      "versions": [
        {"version": "1.0", "created_at": "...", "description": "...", "status": "archived"},
        {"version": "1.1", "created_at": "...", "description": "...", "status": "active"}
      ]
    }
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from src.core.logger import get_logger

logger = get_logger("workflow.loader")


class WorkflowLoader:
    """流程 YAML 加载器，负责流程列表、加载、版本保存与回滚。"""

    def __init__(self, workflows_dir: Path | str):
        """初始化加载器。

        Args:
            workflows_dir: workflows 目录路径。
        """
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 列表
    # ------------------------------------------------------------------
    def list_workflows(self) -> list[dict]:
        """列出所有流程及其当前版本基本信息。"""
        result: list[dict] = []
        if not self.workflows_dir.exists():
            return result
        for entry in sorted(self.workflows_dir.iterdir()):
            if not entry.is_dir():
                continue
            current_yaml = entry / "current" / "workflow.yaml"
            if not current_yaml.exists():
                continue
            try:
                wf_def = self._read_yaml(current_yaml)
            except Exception as exc:
                logger.error(f"加载流程 {entry.name} 失败: {exc}")
                continue
            meta = self._load_versions_meta(entry)
            result.append(
                {
                    "name": entry.name,
                    "display_name": wf_def.get("name", entry.name),
                    "current_version": meta.get("current_version"),
                    "enabled": wf_def.get("enabled", True),
                    "description": wf_def.get("description", ""),
                    "version": str(wf_def.get("version", "1.0")),
                    "priority": wf_def.get("trigger", {}).get("priority", 0),
                }
            )
        return result

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def load_workflow(self, name: str, version: str | None = None) -> dict:
        """加载流程定义。

        Args:
            name: 流程目录名。
            version: 指定版本号；None 表示加载 current 版本。

        Returns:
            流程 YAML 解析后的字典。

        Raises:
            FileNotFoundError: 流程或版本不存在。
        """
        wf_dir = self.workflows_dir / name
        if not wf_dir.exists():
            raise FileNotFoundError(f"流程不存在: {name}")

        if version is None:
            yaml_path = wf_dir / "current" / "workflow.yaml"
        else:
            yaml_path = wf_dir / "versions" / version / "workflow.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"流程版本不存在: {name}@{version}")
        return self._read_yaml(yaml_path)

    # ------------------------------------------------------------------
    # 保存新版本
    # ------------------------------------------------------------------
    def save_new_version(self, name: str, yaml_content: str, description: str) -> str:
        """保存新版本流程定义，并切换 current 到该版本。

        Args:
            name: 流程目录名。
            yaml_content: YAML 文本内容。
            description: 版本描述。

        Returns:
            新版本号字符串。
        """
        try:
            wf_def = yaml.safe_load(yaml_content)
        except yaml.YAMLError as exc:
            raise ValueError(f"YAML 语法错误: {exc}") from exc
        if not isinstance(wf_def, dict):
            raise ValueError("流程定义必须是 YAML 字典")

        version = str(wf_def.get("version", "1.0"))
        wf_dir = self.workflows_dir / name
        wf_dir.mkdir(parents=True, exist_ok=True)

        # 1. 归档到 versions/{version}/
        version_dir = wf_dir / "versions" / version
        version_dir.mkdir(parents=True, exist_ok=True)
        self._write_text(version_dir / "workflow.yaml", yaml_content)

        # 2. 同步到 current/
        current_dir = wf_dir / "current"
        current_dir.mkdir(parents=True, exist_ok=True)
        self._write_text(current_dir / "workflow.yaml", yaml_content)

        # 3. 更新 versions.json
        meta = self._load_versions_meta(wf_dir)
        # 旧 active 版本归档
        for v in meta.get("versions", []):
            if v.get("status") == "active":
                v["status"] = "archived"
        # 移除同版本旧记录后追加新记录
        meta["versions"] = [
            v for v in meta.get("versions", []) if v.get("version") != version
        ]
        meta["versions"].append(
            {
                "version": version,
                "created_at": datetime.now().isoformat(),
                "description": description,
                "status": "active",
            }
        )
        meta["current_version"] = version
        meta.setdefault("workflow_name", wf_def.get("name", name))
        self._save_versions_meta(wf_dir, meta)

        logger.info(f"流程 {name} 保存新版本 {version}: {description}")
        return version

    # ------------------------------------------------------------------
    # 回滚
    # ------------------------------------------------------------------
    def rollback(self, name: str, to_version: str) -> None:
        """把 current 切回指定历史版本。"""
        wf_dir = self.workflows_dir / name
        if not wf_dir.exists():
            raise FileNotFoundError(f"流程不存在: {name}")
        version_yaml = wf_dir / "versions" / to_version / "workflow.yaml"
        if not version_yaml.exists():
            raise FileNotFoundError(f"版本不存在: {to_version}")

        content = self._read_text(version_yaml)
        current_dir = wf_dir / "current"
        current_dir.mkdir(parents=True, exist_ok=True)
        self._write_text(current_dir / "workflow.yaml", content)

        meta = self._load_versions_meta(wf_dir)
        for v in meta.get("versions", []):
            v["status"] = (
                "active" if v.get("version") == to_version else "archived"
            )
        meta["current_version"] = to_version
        self._save_versions_meta(wf_dir, meta)
        logger.info(f"流程 {name} 已回滚到版本 {to_version}")

    # ------------------------------------------------------------------
    # 当前版本查询
    # ------------------------------------------------------------------
    def get_current_version(self, name: str) -> str | None:
        """返回流程当前版本号，不存在时返回 None。"""
        wf_dir = self.workflows_dir / name
        if not wf_dir.exists():
            return None
        meta = self._load_versions_meta(wf_dir)
        return meta.get("current_version")

    def list_versions(self, name: str) -> list[dict]:
        """返回流程的全部版本元信息列表。"""
        wf_dir = self.workflows_dir / name
        if not wf_dir.exists():
            return []
        return self._load_versions_meta(wf_dir).get("versions", [])

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _read_yaml(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}

    @staticmethod
    def _read_text(path: Path) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _load_versions_meta(wf_dir: Path) -> dict:
        """读取 versions.json，缺失或损坏时返回空骨架。"""
        meta_path = wf_dir / "versions.json"
        if not meta_path.exists():
            return {
                "workflow_name": wf_dir.name,
                "current_version": None,
                "versions": [],
            }
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if not isinstance(meta, dict):
                raise ValueError("versions.json 顶层不是对象")
            meta.setdefault("workflow_name", wf_dir.name)
            meta.setdefault("current_version", None)
            meta.setdefault("versions", [])
            return meta
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning(f"读取 versions.json 失败 ({wf_dir.name}): {exc}")
            return {
                "workflow_name": wf_dir.name,
                "current_version": None,
                "versions": [],
            }

    @staticmethod
    def _save_versions_meta(wf_dir: Path, meta: dict) -> None:
        meta_path = wf_dir / "versions.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
