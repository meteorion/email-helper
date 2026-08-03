"""定时调度器 - 定时触发邮件拉取任务"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional, Callable

from src.core.logger import get_logger
from src.mail.imap_client import ImapClient
from src.storage.mail_store import MailStore

logger = get_logger("mail.scheduler")


class MailScheduler:
    """邮件定时调度器"""

    def __init__(
        self,
        imap_client: ImapClient,
        mail_store: MailStore,
        interval_minutes: int = 5,
        on_new_mails: Optional[Callable[[list], None]] = None,
    ):
        """
        初始化调度器

        Args:
            imap_client: IMAP 客户端
            mail_store: 邮件存储
            interval_minutes: 拉取间隔（分钟）
            on_new_mails: 新邮件回调函数 (可选)
        """
        self.imap_client = imap_client
        self.mail_store = mail_store
        self.interval_minutes = interval_minutes
        self.on_new_mails = on_new_mails

        self._scheduler: Optional[BackgroundScheduler] = None
        self._running = False

    def start(self):
        """启动调度"""
        if self._running:
            logger.warning("调度器已在运行中")
            return

        try:
            self._scheduler = BackgroundScheduler()

            # 添加定时任务
            self._scheduler.add_job(
                self.fetch_mails,
                trigger=IntervalTrigger(minutes=self.interval_minutes),
                id="mail_fetch",
                name="定时拉取邮件",
                replace_existing=True,
            )

            self._scheduler.start()
            self._running = True
            logger.info(f"邮件调度器已启动，间隔: {self.interval_minutes} 分钟")

        except Exception as e:
            logger.error(f"启动调度器失败: {e}", exc_info=True)
            raise

    def stop(self):
        """停止调度"""
        if self._scheduler and self._running:
            try:
                self._scheduler.shutdown(wait=False)
                self._running = False
                logger.info("邮件调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")

    def fetch_now(self) -> list:
        """
        手动触发一次拉取

        Returns:
            新拉取的邮件列表
        """
        logger.info("手动触发邮件拉取")
        return self.fetch_mails()

    def fetch_mails(self) -> list:
        """
        执行邮件拉取任务

        Returns:
            新拉取的邮件列表
        """
        try:
            logger.info("开始拉取邮件...")

            # 获取已处理的邮件 ID
            seen_ids = self.mail_store.get_seen_ids()

            # 拉取未读邮件
            new_mails = self.imap_client.fetch_unseen(seen_ids)

            if not new_mails:
                logger.info("没有新邮件")
                return []

            # 保存新邮件
            for mail in new_mails:
                self.mail_store.save(mail)
                seen_ids.add(mail.message_id)

            # 更新 seen_ids
            self.mail_store.save_seen_ids(seen_ids)

            logger.info(f"成功拉取并保存 {len(new_mails)} 封新邮件")

            # 触发回调
            if self.on_new_mails:
                try:
                    self.on_new_mails(new_mails)
                except Exception as e:
                    logger.error(f"新邮件回调执行失败: {e}")

            return new_mails

        except Exception as e:
            logger.error(f"拉取邮件失败: {e}", exc_info=True)
            return []

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    def set_interval(self, interval_minutes: int):
        """
        设置拉取间隔

        Args:
            interval_minutes: 新的间隔（分钟）
        """
        self.interval_minutes = interval_minutes

        if self._running and self._scheduler:
            # 重新调度
            self._scheduler.reschedule_job(
                "mail_fetch",
                trigger=IntervalTrigger(minutes=interval_minutes),
            )
            logger.info(f"拉取间隔已更新: {interval_minutes} 分钟")
