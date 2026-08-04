"""通知分发主引擎"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.core.logger import get_logger

from .channels.wecom import WecomWebhookChannel
from .failure_queue import FailureQueue
from .queue import NotificationQueue
from .rate_limiter import TokenBucket
from .retry_handler import RetryHandler
from .template import TemplateEngine

logger = get_logger("notification.engine")

# 失败重试扫描间隔（秒）= 30 分钟
_RETRY_SCAN_INTERVAL = 1800
# 失败通知最大存活时间（秒）= 24 小时
_MAX_FAILURE_AGE = 24 * 3600
# 企微 45009 频率限制固定等待时间（秒）
_RATE_LIMIT_WAIT = 60.0


class NotificationEngine:
    """通知分发主引擎

    channels 配置从 notification_channels.yaml 加载:
        channels:
          wecom_alert:
            type: wecom
            webhook_ref: "secrets.webhooks.wecom_alert"
        routing:
          by_category:
            告警类: [wecom_alert]
            审批类: [wecom_alert]
          by_priority:
            紧急: [wecom_alert]
        dnd:
          enabled: true
          start: "22:00"
          end: "08:00"
          bypass_for_urgent: true
    """

    def __init__(
        self,
        channels_config_path: Path,
        templates_dir: Path,
        secret_mgr: Any,
        db: Any,
        rate_limit_config: dict,
        retry_config: dict,
    ):
        self.channels_config_path = Path(channels_config_path)
        self.templates_dir = Path(templates_dir)
        self.secret_mgr = secret_mgr
        self.db = db
        self.rate_limit_config = rate_limit_config
        self.retry_config = retry_config

        self.template_engine = TemplateEngine(self.templates_dir)
        self.failure_queue = FailureQueue(db)
        self.retry_handler = RetryHandler(
            max_retries=retry_config.get("max_retries", 3),
            base_delay=retry_config.get("base_delay", 5.0),
            backoff_multiplier=retry_config.get("backoff_multiplier", 3.0),
        )
        self.token_bucket = TokenBucket(
            capacity=rate_limit_config.get("capacity", 20),
            refill_interval_ms=rate_limit_config.get("refill_interval_ms", 3000),
        )
        self.queue = NotificationQueue(self.token_bucket, {})
        self.queue.set_sender(self._send_notification)

        self._channels: dict[str, WecomWebhookChannel] = {}
        self._routing: dict = {}
        self._dnd_config: dict = {}

        self._retry_thread: threading.Thread | None = None
        self._retry_running = False

        self.reload_config()

    def reload_config(self) -> None:
        """重新加载渠道配置"""
        try:
            with open(self.channels_config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"渠道配置文件不存在: {self.channels_config_path}")
            self._channels = {}
            self._routing = {}
            self._dnd_config = {}
            return
        except Exception as e:
            logger.error(f"加载渠道配置失败: {e}", exc_info=True)
            return

        channels = config.get("channels", {})
        self._channels = {}
        for name, ch_cfg in channels.items():
            if not ch_cfg.get("enabled", True):
                continue
            ch_type = ch_cfg.get("type", "")
            if ch_type in ("wecom", "wecom_webhook"):
                webhook_ref = ch_cfg.get("webhook_ref", "")
                webhook_url = self._resolve_webhook(webhook_ref)
                if not webhook_url:
                    logger.error(f"无法解析 webhook URL，跳过渠道 {name}")
                    continue
                self._channels[name] = WecomWebhookChannel(webhook_url)
            else:
                logger.warning(f"未知渠道类型: {ch_type} (channel={name})")

        self._routing = config.get("routing", {})
        self._dnd_config = config.get("dnd", {})
        logger.info(f"通知配置已重载: {len(self._channels)} 个渠道")

    def _resolve_webhook(self, ref: str) -> str:
        """解析 webhook 引用，兼容多种格式

        - "http(s)://..."               → 直接 URL
        - "${secrets.webhooks.xxx}"     → resolve_template
        - "secrets.webhooks.xxx"        → 去除 secrets. 前缀后 get_secret
        """
        if not ref:
            return ""
        if ref.startswith("http://") or ref.startswith("https://"):
            return ref
        if "${" in ref:
            try:
                return self.secret_mgr.resolve_template(ref)
            except Exception as e:
                logger.error(f"解析 webhook 模板失败 {ref}: {e}")
                return ""
        path = ref
        if path.startswith("secrets."):
            path = path[len("secrets."):]
        try:
            return self.secret_mgr.get_secret(path)
        except Exception as e:
            logger.error(f"获取 webhook 密钥失败 {path}: {e}")
            return ""

    def send_async(self, notification: dict) -> None:
        """异步发送通知

        notification = {
            category, priority, template_name, context, mention_override
        }

        流程:
          1. 根据 routing 选择 channels
          2. template.render → 渲染
          3. 检查 DND → 在 DND 内且非紧急 → 设置 deferred_until
          4. 入 NotificationQueue
        """
        category = notification.get("category", "")
        priority = notification.get("priority", "普通")
        template_name = notification.get("template_name", "")
        context = notification.get("context", {}) or {}
        mention_override = notification.get("mention_override")

        # 1. routing - 选择 channels
        channel_names = self._select_channels(category, priority)
        if not channel_names:
            logger.info(
                f"无匹配渠道，跳过通知: category={category} priority={priority}"
            )
            return

        # 2. 渲染模板
        try:
            rendered = self.template_engine.render(template_name, context)
        except Exception as e:
            logger.error(f"渲染模板失败 {template_name}: {e}", exc_info=True)
            return

        if mention_override is not None:
            rendered["mentioned"] = mention_override

        mail = context.get("mail", {}) if isinstance(context.get("mail"), dict) else {}
        payload = {
            "category": category,
            "priority": priority,
            "template_name": template_name,
            "content": rendered["content"],
            "msg_type": rendered["type"],
            "mentioned": rendered["mentioned"],
            "channels": channel_names,
            "sender": mail.get("sender", ""),
            "subject": mail.get("subject", ""),
        }

        # 3. 检查 DND
        if self._check_dnd() and priority != "紧急":
            deferred_until = self._next_dnd_end()
            payload["deferred_until"] = deferred_until
            logger.info(
                "免打扰时段，通知延迟至 "
                f"{datetime.fromtimestamp(deferred_until).strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # 4. 入队
        self.queue.enqueue(payload, priority)

    def _select_channels(self, category: str, priority: str) -> list[str]:
        """根据 routing 选择渠道

        优先级: by_priority > by_category > default
        """
        by_priority = self._routing.get("by_priority", {})
        by_category = self._routing.get("by_category", {})
        if priority in by_priority:
            return by_priority[priority] or []
        if category in by_category:
            return by_category[category] or []
        if "default" in by_category:
            return by_category["default"] or []
        return []

    def _check_dnd(self) -> bool:
        """检查当前是否在免打扰时段 22:00-08:00"""
        if not self._dnd_config.get("enabled", False):
            return False
        now = datetime.now()
        current = now.hour * 60 + now.minute
        start = self._parse_time(self._dnd_config.get("start", "22:00"))
        end = self._parse_time(self._dnd_config.get("end", "08:00"))
        if start <= end:
            return start <= current < end
        # 跨天逻辑: 22:00-08:00 → 当前时间 >= 22:00 或 < 08:00
        return current >= start or current < end

    def _next_dnd_end(self) -> float:
        """计算下一个 DND 结束时间（次日 08:00）的 Unix 时间戳"""
        now = datetime.now()
        end_str = self._dnd_config.get("end", "08:00")
        h, m = end_str.split(":")
        end_today = now.replace(
            hour=int(h), minute=int(m), second=0, microsecond=0
        )
        if now < end_today:
            return end_today.timestamp()
        return (end_today + timedelta(days=1)).timestamp()

    def _parse_time(self, t: str) -> int:
        """HH:MM → 当天分钟数"""
        parts = t.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    def _send_notification(self, notification: dict) -> dict:
        """发送通知到选定渠道（队列发送回调）"""
        channel_names = notification.get("channels", [])
        content = notification.get("content", "")
        msg_type = notification.get("msg_type", "markdown")
        mentioned = notification.get("mentioned", [])

        last_error = None
        for ch_name in channel_names:
            channel = self._channels.get(ch_name)
            if channel is None:
                logger.warning(f"渠道不存在: {ch_name}")
                continue
            try:
                result = channel.send(
                    content, msg_type=msg_type, mentioned=mentioned
                )
            except Exception as e:
                result = {"success": False, "error": f"network:{e}", "status_code": 0}
                logger.error(f"渠道 {ch_name} 发送异常: {e}", exc_info=True)

            if result.get("success"):
                logger.info(f"通知发送成功: channel={ch_name}")
                return result

            last_error = result.get("error") or "unknown"
            logger.warning(f"渠道 {ch_name} 发送失败: {last_error}")
            # 不可重试错误 → 持久化后返回
            if not self.retry_handler.should_retry(last_error):
                self.failure_queue.add_failure(
                    ch_name,
                    "",
                    {
                        "content": content,
                        "msg_type": msg_type,
                        "mentioned": mentioned,
                    },
                    last_error,
                )
                return result

        # 全部渠道失败 → 持久化到失败队列
        if last_error:
            self.failure_queue.add_failure(
                ",".join(channel_names),
                "",
                {
                    "content": content,
                    "msg_type": msg_type,
                    "mentioned": mentioned,
                },
                last_error,
            )
        return {"success": False, "error": last_error, "status_code": 0}

    def start(self) -> None:
        """启动队列处理线程 + 失败重试线程"""
        self.queue.start()
        self.start_retry_thread()

    def start_retry_thread(self) -> None:
        """后台线程每 30 分钟扫描 failure_queue.get_retryable()"""
        if self._retry_running:
            return
        self._retry_running = True
        self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._retry_thread.start()
        logger.info("通知失败重试线程已启动")

    def stop_retry_thread(self) -> None:
        """停止重试线程"""
        self._retry_running = False

    def _retry_loop(self) -> None:
        """重试扫描循环（每 30 分钟一次）"""
        while self._retry_running:
            try:
                retryable = self.failure_queue.get_retryable()
                for item in retryable:
                    self._retry_one(item)
            except Exception as e:
                logger.error(f"重试扫描异常: {e}", exc_info=True)
            time.sleep(_RETRY_SCAN_INTERVAL)

    def _retry_one(self, item: dict) -> None:
        """重试单条失败通知"""
        failure_id = item.get("id", "")
        first_failed = item.get("first_failed_at", 0) or 0

        # 超过 24h 放弃
        if time.time() - first_failed > _MAX_FAILURE_AGE:
            logger.error(f"失败通知超过 24h，放弃: {failure_id}")
            self.failure_queue.mark_given_up(failure_id)
            return

        error = item.get("error", "")
        if not self.retry_handler.should_retry(error):
            logger.warning(f"不可重试错误，放弃: {failure_id} error={error}")
            self.failure_queue.mark_given_up(failure_id)
            return

        self.failure_queue.mark_retrying(failure_id)

        channel_name = item.get("channel", "")
        first_channel = channel_name.split(",")[0] if channel_name else ""
        channel = self._channels.get(first_channel)
        if channel is None:
            self.failure_queue.update_retry(
                failure_id,
                time.time() + _RETRY_SCAN_INTERVAL,
                "channel not found",
            )
            return

        content_raw = item.get("content", "{}")
        try:
            content = (
                json.loads(content_raw)
                if isinstance(content_raw, str)
                else content_raw
            )
        except Exception:
            content = {}

        try:
            result = channel.send(
                content.get("content", ""),
                msg_type=content.get("msg_type", "markdown"),
                mentioned=content.get("mentioned", []),
            )
        except Exception as e:
            result = {"success": False, "error": f"network:{e}"}

        if result.get("success"):
            logger.info(f"重试发送成功: {failure_id}")
            self.failure_queue.remove(failure_id)
        else:
            new_error = result.get("error", "")
            if self.retry_handler.is_rate_limit_error(new_error):
                delay = _RATE_LIMIT_WAIT
            else:
                delay = self.retry_handler.get_delay(item.get("retry_count", 0))
            self.failure_queue.update_retry(
                failure_id, time.time() + delay, new_error
            )
