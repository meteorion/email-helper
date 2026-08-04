"""定时调度器 - 定时触发邮件拉取任务"""

from datetime import datetime
from typing import Any, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
        trigger_type: str = "interval",
        cron_expression: Optional[str] = None,
        work_hours_only: bool = False,
        work_hours: Optional[dict] = None,
        work_days: Optional[list[int]] = None,
        mail_repository: Optional[Any] = None,
        classifier: Optional[Any] = None,
        workflow_engine: Optional[Any] = None,
        cache_repository: Optional[Any] = None,
    ):
        """
        初始化调度器

        Args:
            imap_client: IMAP 客户端
            mail_store: 邮件存储
            interval_minutes: 拉取间隔（分钟）
            on_new_mails: 新邮件回调函数 (可选)
            trigger_type: 触发类型，"interval" 或 "cron"
            cron_expression: Cron 表达式（trigger_type="cron" 时使用），
                如 "0 */2 * * 1-5" 表示工作日每 2 小时整点
            work_hours_only: 是否仅在工作时间拉取
            work_hours: 工作时间，如 {"start": "08:30", "end": "18:30"}
            work_days: 工作日列表（1=周一 ... 7=周日），如 [1,2,3,4,5]
            mail_repository: 邮件元数据 SQLite 仓储（Alpha，可选）
            classifier: AI 分类器（Alpha，可选）
            workflow_engine: 流程执行引擎（Alpha，可选）
            cache_repository: 去重缓存仓储（Alpha，可选）
        """
        self.imap_client = imap_client
        self.mail_store = mail_store
        self.interval_minutes = interval_minutes
        self.on_new_mails = on_new_mails

        # 触发器配置
        self.trigger_type: str = trigger_type
        self.cron_expression: Optional[str] = cron_expression

        # 工作时间过滤
        self.work_hours_only: bool = work_hours_only
        self.work_hours: dict = work_hours or {"start": "08:30", "end": "18:30"}
        self.work_days: list[int] = work_days if work_days is not None else [1, 2, 3, 4, 5]

        # Alpha 集成组件
        self.mail_repository = mail_repository
        self.classifier = classifier
        self.workflow_engine = workflow_engine
        self.cache_repository = cache_repository

        self._scheduler: Optional[BackgroundScheduler] = None
        self._running = False

    def start(self):
        """启动调度"""
        if self._running:
            logger.warning("调度器已在运行中")
            return

        try:
            self._scheduler = BackgroundScheduler()

            # 根据触发类型选择 trigger
            trigger = self._build_trigger()

            # 添加定时任务
            self._scheduler.add_job(
                self.fetch_mails,
                trigger=trigger,
                id="mail_fetch",
                name="定时拉取邮件",
                replace_existing=True,
            )

            self._scheduler.start()
            self._running = True
            if self.trigger_type == "cron" and self.cron_expression:
                logger.info(f"邮件调度器已启动，Cron: {self.cron_expression}")
            else:
                logger.info(f"邮件调度器已启动，间隔: {self.interval_minutes} 分钟")

        except Exception as e:
            logger.error(f"启动调度器失败: {e}", exc_info=True)
            raise

    def _build_trigger(self):
        """根据 trigger_type 构建调度触发器

        - cron 模式：用 CronTrigger.from_crontab 解析标准 5 段 Cron 表达式
        - interval 模式（默认）：固定分钟间隔

        工作时间过滤在 fetch_mails 内部执行，不叠加到 trigger 上，
        以保证 Cron 表达式语义与用户输入一致。
        """
        if self.trigger_type == "cron" and self.cron_expression:
            return CronTrigger.from_crontab(self.cron_expression)
        return IntervalTrigger(minutes=self.interval_minutes)

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

        工作时间过滤：work_hours_only=True 时，若当前不在工作日/工作时间段，
        直接跳过本次拉取并返回空列表。

        去重逻辑：
        - 若注入了 cache_repository，使用其 is_seen() / mark_seen() / get_all_seen_ids()
          替代旧的 mail_store.get_seen_ids() / save_seen_ids()
        - 否则回退到旧逻辑（mail_store 维护 seen_ids.json），保持向后兼容

        持久化：保存邮件正文 JSON 后，若注入了 mail_repository 则调用 upsert_mail()
        写入 SQLite 元数据。

        分类集成：若注入了 classifier，新邮件通过 on_new_mails 回调加入分类队列。

        Returns:
            新拉取的邮件列表
        """
        try:
            logger.info("开始拉取邮件...")

            # 工作时间过滤：不在工作时间则跳过
            if self.work_hours_only and not self._is_within_work_hours():
                logger.debug("当前不在工作时间内，跳过本次拉取")
                return []

            # 获取已处理邮件 ID
            if self.cache_repository is not None:
                seen_ids = self.cache_repository.get_all_seen_ids()
            else:
                seen_ids = self.mail_store.get_seen_ids()

            # 拉取未读邮件
            new_mails = self.imap_client.fetch_unseen(seen_ids)

            if not new_mails:
                logger.info("没有新邮件")
                return []

            # 过滤 + 保存
            truly_new: list = []
            for mail in new_mails:
                # 用 cache_repository.is_seen() 做权威去重检查（防御 IMAP 重复推送）
                if self.cache_repository is not None and self.cache_repository.is_seen(mail.message_id):
                    continue

                # 保存邮件正文 JSON
                self.mail_store.save(mail)

                # 保存邮件元数据到 SQLite（Alpha）
                if self.mail_repository is not None:
                    try:
                        self.mail_repository.upsert_mail(mail)
                    except Exception as e:
                        logger.error(f"upsert_mail 失败 ({mail.message_id}): {e}")

                # 标记已处理
                if self.cache_repository is not None:
                    self.cache_repository.mark_seen(mail.message_id)
                else:
                    seen_ids.add(mail.message_id)

                truly_new.append(mail)

            # 向后兼容：旧逻辑持久化 seen_ids
            if self.cache_repository is None:
                self.mail_store.save_seen_ids(seen_ids)

            logger.info(f"成功拉取并保存 {len(truly_new)} 封新邮件")

            # 触发回调 / 分类队列
            if truly_new:
                self._dispatch_new_mails(truly_new)

            return truly_new

        except Exception as e:
            logger.error(f"拉取邮件失败: {e}", exc_info=True)
            return []

    def _is_within_work_hours(self) -> bool:
        """检查当前时间是否在工作时间内

        - 工作日按 ISO 周序号判断（1=周一 ... 7=周日），需在 self.work_days 中
        - 工作时间按 HH:MM 转分钟数比较，含两端
        - work_hours 格式异常时视为不限制（返回 True），避免误锁死调度
        """
        now = datetime.now()

        # 工作日检查
        today_weekday = now.isoweekday()  # 1=Mon ... 7=Sun
        if self.work_days and today_weekday not in self.work_days:
            return False

        # 工作时间检查
        if not self.work_hours:
            return True

        start_str = self.work_hours.get("start", "00:00")
        end_str = self.work_hours.get("end", "23:59")
        try:
            start_h, start_m = (int(x) for x in str(start_str).split(":"))
            end_h, end_m = (int(x) for x in str(end_str).split(":"))
        except (ValueError, AttributeError):
            logger.warning(f"工作时间格式错误: {self.work_hours}，跳过时间过滤")
            return True

        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        now_minutes = now.hour * 60 + now.minute
        return start_minutes <= now_minutes <= end_minutes

    def _dispatch_new_mails(self, new_mails: list) -> None:
        """分发新邮件到回调 / 分类队列

        - 若注入了 classifier（Alpha 管线就绪），通过 on_new_mails 回调将新邮件
          ID 加入分类队列；无回调时记录日志
        - 否则按旧逻辑触发 on_new_mails 回调
        """
        if self.classifier is not None:
            if self.on_new_mails is not None:
                try:
                    self.on_new_mails(new_mails)
                except Exception as e:
                    logger.error(f"新邮件回调（分类队列）执行失败: {e}")
            else:
                logger.debug(f"已拉取 {len(new_mails)} 封新邮件，但未注册分类回调")
            return

        if self.on_new_mails is not None:
            try:
                self.on_new_mails(new_mails)
            except Exception as e:
                logger.error(f"新邮件回调执行失败: {e}")

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
