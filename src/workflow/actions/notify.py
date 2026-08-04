"""通知 Action：调用 NotificationEngine.send_async 发送企微群通知。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class NotifyAction(BaseAction):
    """发送通知（企微群机器人等）。"""

    action_name = "notify"

    def execute(self) -> Any:
        engine = self._require_dep("notification_engine")
        notification = {
            "category": self.config.get("category", ""),
            "priority": self.config.get("priority", "普通"),
            "template_name": self.config.get("template", ""),
            "channel": self.config.get("channel", ""),
            "webhook": self.config.get("webhook", ""),
            "content": self.config.get("content", ""),
            "context": self.config.get("context", {}),
            "mention_override": self.config.get("mention"),
            "title": self.config.get("title", ""),
        }
        # 去掉空值，避免覆盖引擎默认值
        notification = {k: v for k, v in notification.items() if v}

        if hasattr(engine, "send_async"):
            engine.send_async(notification)
        elif hasattr(engine, "send"):
            engine.send(notification)
        else:
            raise RuntimeError("NotificationEngine 缺少 send_async/send 方法")

        self.logger.info(
            f"通知已入队: channel={notification.get('channel')} "
            f"template={notification.get('template_name')}"
        )
        return {"status": "queued", "notification": notification}
