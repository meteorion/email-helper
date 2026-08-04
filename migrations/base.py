"""数据迁移基类与管理器。

提供 ``Migration`` 抽象基类和 ``MigrationManager`` 编排器：
- ``Migration``: 单个版本迁移的实现骨架（migrate / validate / rollback）。
- ``MigrationManager``: 按顺序执行迁移，负责版本读取、备份、回滚和版本写入。

迁移脚本不自建 Database / SecretManager，由 main.py 注入已初始化的实例。
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core.logger import get_logger

logger = get_logger("migrations.base")


class Migration:
    """单个版本迁移的抽象基类。

    子类必须设置 ``from_version`` / ``to_version`` 并实现
    ``migrate`` / ``validate`` / ``rollback`` 三个方法。
    """

    from_version: str = ""
    to_version: str = ""

    def migrate(
        self,
        data_dir: Path,
        config_dir: Path,
        db: Any,
        secret_mgr: Any,
    ) -> None:
        """执行迁移逻辑。

        Args:
            data_dir: 数据目录（data/）。
            config_dir: 配置目录（config/）。
            db: 已初始化的 Database 实例。
            secret_mgr: 已初始化的 SecretManager 实例。
        """
        raise NotImplementedError

    def validate(self, data_dir: Path, config_dir: Path, db: Any) -> bool:
        """迁移后校验，返回 True 表示通过。

        Args:
            data_dir: 数据目录。
            config_dir: 配置目录。
            db: Database 实例。

        Returns:
            校验是否通过。
        """
        raise NotImplementedError

    def rollback(
        self,
        data_dir: Path,
        config_dir: Path,
        backup_dir: Path,
    ) -> None:
        """迁移失败回滚：用 backup 目录内容覆盖回原位。

        Args:
            data_dir: 数据目录。
            config_dir: 配置目录。
            backup_dir: 备份目录（包含 data/ 和 config/ 子目录）。
        """
        raise NotImplementedError


class MigrationManager:
    """迁移编排器：负责版本读取、备份、按序执行迁移、回滚和版本写入。

    迁移脚本顺序由 ``_discover_migrations`` 返回的列表决定，
    每次执行 ``run_migrations`` 会：
    1. 备份 data/ 和 config/ 到 ``backup/时间戳/`` 目录
    2. 按顺序执行所有满足 ``from_version == 当前版本`` 的迁移
    3. 每个迁移完成后立即 ``validate``，失败则 ``_restore`` 并停止
    4. 全部成功后写入新的 schema_version
    """

    # 当前应用目标版本（最新版本）
    LATEST_VERSION: str = "0.2.0"

    def __init__(
        self,
        data_dir: Path,
        config_dir: Path,
        db: Any,
        secret_mgr: Any,
    ) -> None:
        """初始化迁移管理器。

        Args:
            data_dir: 数据目录路径。
            config_dir: 配置目录路径。
            db: 已初始化的 Database 实例。
            secret_mgr: 已初始化的 SecretManager 实例。
        """
        self.data_dir: Path = Path(data_dir)
        self.config_dir: Path = Path(config_dir)
        self.db: Any = db
        self.secret_mgr: Any = secret_mgr
        # schema_version.json 位于 data 目录下
        self.version_file: Path = self.data_dir / "schema_version.json"
        # 备份根目录
        self.backup_root: Path = self.data_dir.parent / "backup"

    # ── 版本读写 ───────────────────────────────────

    def get_current_version(self) -> str:
        """读取当前 schema 版本。

        schema_version.json 不存在时，认为是初始 MVP 版本 ``0.1.0``。

        Returns:
            当前版本字符串。
        """
        if not self.version_file.exists():
            logger.info("schema_version.json 不存在，判定为初始版本 0.1.0")
            return "0.1.0"
        try:
            with open(self.version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            version = data.get("version", "0.1.0")
            return version
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取 schema_version.json 失败: {e}，回退为 0.1.0")
            return "0.1.0"

    def set_version(self, version: str) -> None:
        """写入 schema 版本。

        Args:
            version: 目标版本字符串。
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": version,
            "migrated_at": datetime.now().isoformat(),
        }
        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"schema 版本已更新: {version}")

    def needs_migration(self) -> bool:
        """判断是否需要迁移。

        Returns:
            当前版本低于 ``LATEST_VERSION`` 时返回 True。
        """
        return self._compare_version(self.get_current_version(), self.LATEST_VERSION) < 0

    # ── 迁移编排 ───────────────────────────────────

    def run_migrations(self) -> None:
        """执行所有待执行的迁移。

        流程：备份 → 按序执行迁移 → 验证 → 更新版本号。
        任一步骤失败则回滚到备份并停止。
        """
        if not self.needs_migration():
            logger.info(
                f"当前版本 {self.get_current_version()} 已是最新，无需迁移"
            )
            return

        # 备份
        backup_dir = self._backup()
        logger.info(f"已创建迁移前备份: {backup_dir}")

        current = self.get_current_version()
        migrations = self._discover_migrations()

        try:
            for migration in migrations:
                if migration.from_version != current:
                    continue
                logger.info(
                    f"执行迁移: {migration.from_version} → {migration.to_version}"
                )
                migration.migrate(
                    self.data_dir, self.config_dir, self.db, self.secret_mgr
                )
                if not migration.validate(self.data_dir, self.config_dir, self.db):
                    raise RuntimeError(
                        f"迁移校验失败: {migration.from_version} → {migration.to_version}"
                    )
                current = migration.to_version
                self.set_version(current)
                logger.info(
                    f"迁移完成并校验通过: {migration.from_version} → {migration.to_version}"
                )

            # 全部成功，确保版本号已是最新
            if current != self.LATEST_VERSION:
                self.set_version(self.LATEST_VERSION)

            logger.info("所有迁移执行完毕")
        except Exception as e:
            logger.error(f"迁移过程出错，开始回滚: {e}", exc_info=True)
            self._restore(backup_dir)
            raise

    # ── 备份 / 回滚 ─────────────────────────────────

    def _backup(self) -> Path:
        """备份 data/ 和 config/ 到 backup/时间戳/ 目录。

        Returns:
            备份目录路径。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_root / f"{timestamp}_v{self.LATEST_VERSION}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 备份 data 目录（排除 backup 自身，避免递归）
        if self.data_dir.exists():
            dest_data = backup_dir / "data"
            shutil.copytree(
                self.data_dir,
                dest_data,
                ignore=shutil.ignore_patterns("backup"),
            )
        # 备份 config 目录
        if self.config_dir.exists():
            dest_config = backup_dir / "config"
            shutil.copytree(self.config_dir, dest_config)

        return backup_dir

    def _restore(self, backup_dir: Path) -> None:
        """回滚：把 backup 目录内容覆盖回 data/ 和 config/。

        Args:
            backup_dir: 备份目录路径（包含 data/ 和 config/ 子目录）。
        """
        backup_dir = Path(backup_dir)
        if not backup_dir.exists():
            logger.error(f"备份目录不存在，无法回滚: {backup_dir}")
            return

        # 恢复 data 目录
        src_data = backup_dir / "data"
        if src_data.exists():
            if self.data_dir.exists():
                # 移除当前 data 目录（仅清理内容，保留目录本身）
                for child in self.data_dir.iterdir():
                    if child.name == "backup":
                        continue
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            else:
                self.data_dir.mkdir(parents=True, exist_ok=True)
            # 把备份数据拷回
            for child in src_data.iterdir():
                dest = self.data_dir / child.name
                if child.is_dir():
                    shutil.copytree(child, dest)
                else:
                    shutil.copy2(child, dest)

        # 恢复 config 目录
        src_config = backup_dir / "config"
        if src_config.exists():
            if self.config_dir.exists():
                for child in self.config_dir.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            else:
                self.config_dir.mkdir(parents=True, exist_ok=True)
            for child in src_config.iterdir():
                dest = self.config_dir / child.name
                if child.is_dir():
                    shutil.copytree(child, dest)
                else:
                    shutil.copy2(child, dest)

        logger.info(f"已从备份恢复: {backup_dir}")

    # ── 迁移脚本发现 ─────────────────────────────────

    def _discover_migrations(self) -> list[Migration]:
        """发现所有可用的迁移脚本。

        目前硬编码注册 ``v0_1_0_to_v0_2_0``，后续可扩展为动态扫描。

        Returns:
            迁移实例列表（按 from_version 升序）。
        """
        migrations: list[Migration] = []
        try:
            from migrations.v0_1_0_to_v0_2_0 import MigrationV01ToV02
            migrations.append(MigrationV01ToV02())
        except Exception as e:
            logger.warning(f"加载迁移脚本失败: {e}")
        return migrations

    # ── 工具方法 ─────────────────────────────────────

    @staticmethod
    def _compare_version(v1: str, v2: str) -> int:
        """比较两个语义版本号。

        Args:
            v1: 版本号 1，如 "0.1.0"。
            v2: 版本号 2，如 "0.2.0"。

        Returns:
            v1 < v2 返回 -1，相等返回 0，v1 > v2 返回 1。
        """
        def _parse(v: str) -> list[int]:
            parts: list[int] = []
            for seg in v.split("."):
                try:
                    parts.append(int(seg))
                except ValueError:
                    parts.append(0)
            return parts

        a = _parse(v1)
        b = _parse(v2)
        # 补齐长度
        length = max(len(a), len(b))
        a += [0] * (length - len(a))
        b += [0] * (length - len(b))
        for x, y in zip(a, b):
            if x < y:
                return -1
            if x > y:
                return 1
        return 0


# 模块导出便捷符号
__all__ = ["Migration", "MigrationManager"]
