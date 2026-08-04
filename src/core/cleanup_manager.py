"""定时数据清理管理器

按保留期限清理过期数据，避免磁盘膨胀。覆盖：
- 邮件元数据（SQLite mails 表）+ 邮件正文 JSON 文件
- 附件文件
- 流程执行记录（SQLite execution_records 表）+ records_dir 文件
- 日志文件（轮转日志）
- 去重缓存（seen_message_ids）+ 过期分类缓存（classify_cache）

定时清理使用 threading.Timer 周期触发，不依赖额外调度器。
"""

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.core.logger import get_logger
from src.core.storage.database import Database

logger = get_logger("core.cleanup")


class CleanupManager:
    """定时数据清理"""

    def __init__(
        self,
        db: Database,
        mail_store: Optional[object] = None,
        attachments_dir: Optional[str | Path] = None,
        records_dir: Optional[str | Path] = None,
        log_dir: Optional[str | Path] = None,
    ):
        """
        初始化清理管理器

        Args:
            db: SQLite 数据库管理器
            mail_store: 邮件存储对象（用于回退获取 attachments_dir / mails_dir）
            attachments_dir: 附件目录（未提供时尝试从 mail_store 取）
            records_dir: 处理记录文件目录
            log_dir: 日志文件目录
        """
        self.db = db
        self.mail_store = mail_store
        self.attachments_dir: Optional[Path] = Path(attachments_dir) if attachments_dir else None
        self.records_dir: Optional[Path] = Path(records_dir) if records_dir else None
        self.log_dir: Optional[Path] = Path(log_dir) if log_dir else None

        # 定时清理状态
        self._cleanup_running: bool = False
        self._cleanup_interval_sec: float = 24 * 3600
        self._cleanup_timer: Optional[threading.Timer] = None

    def cleanup_all(self) -> dict:
        """执行全部清理，使用各类型的默认保留期限

        Returns:
            {mails_deleted, attachments_deleted, records_deleted,
             logs_deleted, cache_deleted}
        """
        logger.info("开始执行全量数据清理...")
        before = self._disk_usage()

        result = {
            "mails_deleted": self.cleanup_old_mails(),
            "attachments_deleted": self.cleanup_attachments(),
            "records_deleted": self.cleanup_records(),
            "logs_deleted": self.cleanup_old_logs(),
            "cache_deleted": self.cleanup_seen_ids(),
        }

        after = self._disk_usage()
        freed = before - after
        logger.info(
            f"清理完成：邮件 {result['mails_deleted']} 封，"
            f"附件 {result['attachments_deleted']} 个，"
            f"记录 {result['records_deleted']} 条，"
            f"日志 {result['logs_deleted']} 个，"
            f"缓存 {result['cache_deleted']} 条，"
            f"释放空间约 {freed} 字节"
        )
        return result

    def cleanup_old_mails(self, days: int = 30) -> int:
        """删除超过 days 天的邮件元数据

        同时删除该邮件对应的正文 JSON 文件（body_file_path）。

        Args:
            days: 保留期限（天）

        Returns:
            删除的邮件元数据条数
        """
        cutoff = self._cutoff_str(days)

        # 先查询待清理邮件的正文文件路径，删除文件
        rows = self.db.query_all(
            "SELECT body_file_path FROM mails WHERE created_at < ?",
            (cutoff,),
        )
        deleted_files = 0
        for row in rows:
            fp = row.get("body_file_path")
            if not fp:
                continue
            try:
                p = Path(fp)
                if p.exists():
                    p.unlink()
                    deleted_files += 1
            except Exception as e:
                logger.warning(f"删除邮件正文文件失败 {fp}: {e}")

        # 删除 SQLite 元数据
        cursor = self.db.execute(
            "DELETE FROM mails WHERE created_at < ?", (cutoff,)
        )
        count = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        logger.info(f"清理旧邮件: 元数据 {count} 条, 正文文件 {deleted_files} 个")
        return count

    def cleanup_attachments(self, days: int = 7) -> int:
        """删除超过 days 天的附件文件

        保留元信息，仅删除磁盘文件。按文件 mtime 判断。

        Args:
            days: 保留期限（天）

        Returns:
            删除的附件文件数
        """
        attachments_dir = self.attachments_dir
        if attachments_dir is None and self.mail_store is not None:
            attachments_dir = getattr(self.mail_store, "attachments_dir", None)
        if attachments_dir is None:
            logger.debug("未配置 attachments_dir，跳过附件清理")
            return 0

        attachments_dir = Path(attachments_dir)
        if not attachments_dir.exists():
            return 0

        cutoff_ts = time.time() - days * 86400
        count = 0
        for f in attachments_dir.rglob("*"):
            if not f.is_file():
                continue
            try:
                if f.stat().st_mtime < cutoff_ts:
                    f.unlink()
                    count += 1
            except Exception as e:
                logger.warning(f"删除附件失败 {f}: {e}")

        logger.info(f"清理旧附件: {count} 个（保留 {days} 天）")
        return count

    def cleanup_records(self, days: int = 90) -> int:
        """删除超过 days 天的执行记录

        清理 SQLite execution_records 表中 started_at 早于 cutoff 的记录，
        并删除 records_dir 中的旧记录文件。

        Args:
            days: 保留期限（天）

        Returns:
            删除的执行记录条数
        """
        cutoff = self._cutoff_str(days)

        cursor = self.db.execute(
            "DELETE FROM execution_records WHERE started_at < ?", (cutoff,)
        )
        count = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

        # 删除 records_dir 中的旧记录文件
        file_count = 0
        if self.records_dir is not None:
            records_dir = Path(self.records_dir)
            cutoff_ts = time.time() - days * 86400
            if records_dir.exists():
                for f in records_dir.rglob("*"):
                    if not f.is_file():
                        continue
                    try:
                        if f.stat().st_mtime < cutoff_ts:
                            f.unlink()
                            file_count += 1
                    except Exception as e:
                        logger.warning(f"删除记录文件失败 {f}: {e}")

        logger.info(
            f"清理旧执行记录: DB {count} 条, 文件 {file_count} 个（保留 {days} 天）"
        )
        return count

    def cleanup_old_logs(self, days: int = 30) -> int:
        """清理旧日志文件（保留最近的）

        删除 log_dir 下 mtime 早于 cutoff 的 *.log / *.log.* 轮转文件。

        Args:
            days: 保留期限（天）

        Returns:
            删除的日志文件数
        """
        if self.log_dir is None:
            logger.debug("未配置 log_dir，跳过日志清理")
            return 0

        log_dir = Path(self.log_dir)
        if not log_dir.exists():
            return 0

        cutoff_ts = time.time() - days * 86400
        count = 0
        for f in log_dir.glob("*.log*"):
            if not f.is_file():
                continue
            try:
                if f.stat().st_mtime < cutoff_ts:
                    f.unlink()
                    count += 1
            except Exception as e:
                logger.warning(f"删除日志文件失败 {f}: {e}")

        logger.info(f"清理旧日志: {count} 个（保留 {days} 天）")
        return count

    def cleanup_seen_ids(self, days: int = 30) -> int:
        """清理旧的去重记录

        删除 seen_message_ids 表中 last_seen_at 早于 cutoff 的记录，
        顺带清理已过期的分类缓存（classify_cache）。

        Args:
            days: 保留期限（天）

        Returns:
            删除的去重记录条数
        """
        cutoff = self._cutoff_str(days)

        cursor = self.db.execute(
            "DELETE FROM seen_message_ids WHERE last_seen_at < ?", (cutoff,)
        )
        count = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

        # 顺带清理过期分类缓存
        try:
            self.db.execute(
                "DELETE FROM classify_cache WHERE expires_at < CURRENT_TIMESTAMP"
            )
        except Exception as e:
            logger.warning(f"清理分类缓存失败: {e}")

        logger.info(f"清理旧去重记录: {count} 条（保留 {days} 天）")
        return count

    def start_scheduled_cleanup(self, interval_hours: int = 24) -> None:
        """启动定时清理（threading.Timer 周期触发）

        Args:
            interval_hours: 清理间隔（小时），默认 24
        """
        if self._cleanup_running:
            logger.warning("定时清理已在运行")
            return
        self._cleanup_running = True
        self._cleanup_interval_sec = interval_hours * 3600
        logger.info(f"启动定时清理，间隔 {interval_hours} 小时")
        self._schedule_next_cleanup()

    def stop(self) -> None:
        """停止定时清理"""
        self._cleanup_running = False
        if self._cleanup_timer is not None:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None
        logger.info("定时清理已停止")

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _schedule_next_cleanup(self) -> None:
        """调度下一次清理任务（threading.Timer）"""
        if not self._cleanup_running:
            return
        self._cleanup_timer = threading.Timer(
            self._cleanup_interval_sec, self._run_scheduled_cleanup
        )
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _run_scheduled_cleanup(self) -> None:
        """定时清理线程入口：执行清理后调度下一次"""
        try:
            self.cleanup_all()
        except Exception as e:
            logger.error(f"定时清理失败: {e}", exc_info=True)
        finally:
            self._schedule_next_cleanup()

    @staticmethod
    def _cutoff_str(days: int) -> str:
        """生成 cutoff 时间字符串（SQLite DATETIME 兼容格式）"""
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    def _disk_usage(self) -> int:
        """估算各清理目录的总占用字节数（用于报告释放空间）"""
        total = 0
        for d in (self.attachments_dir, self.records_dir, self.log_dir):
            if d is None:
                continue
            d = Path(d)
            if not d.exists():
                continue
            for f in d.rglob("*"):
                try:
                    if f.is_file():
                        total += f.stat().st_size
                except Exception:
                    continue
        return total
