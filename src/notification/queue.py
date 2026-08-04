"""通知队列（优先级 + 聚合 + 冷却 + DND 延迟）"""

import heapq
import threading
import time
from typing import Any, Callable

from src.core.logger import get_logger

logger = get_logger("notification.queue")

# 优先级映射: 紧急=3, 普通=2, 低=1（heapq 用负数排序，紧急优先出队）
_PRIORITY_MAP: dict[str, int] = {
    "紧急": 3,
    "普通": 2,
    "低": 1,
    "低优先级": 1,
}

# 冷却参数（秒）
_SENDER_COOLDOWN = 300       # same_sender 5min
_SUBJECT_COOLDOWN = 600      # same_subject 10min
_GLOBAL_MAX_COUNT = 3        # 全局连续 3 条后暂停
_GLOBAL_PAUSE = 60           # 暂停 1 分钟

# 聚合窗口（秒）= 5 分钟
_AGGREGATION_WINDOW = 300


class NotificationQueue:
    """通知队列（优先级 + 聚合 + 冷却 + DND）

    使用 heapq 优先级队列（非单一 deque），紧急优先出队。
    所有操作加锁保证线程安全。

    队列 item 结构:
        {
            'notification': dict,
            'priority': '紧急'|'普通'|'低',
            'enqueued_at': float,           # Unix 时间戳
            'deferred_until': float | None,  # None=立即发送，非None=DND延迟
        }
    """

    def __init__(self, rate_limiter: Any, config: dict):
        self.rate_limiter = rate_limiter
        self.config = config
        # heapq 元素: (-priority, enqueued_at, item) 负数保证紧急优先
        self._heap: list[tuple[int, float, dict]] = []
        # 使用 RLock 保证 enqueue 内调用 _check_cooldown 时可重入
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._cooldown: dict[str, float] = {}
        self._global_count = 0
        self._global_reset_at = 0.0
        self._send_callback: Callable[[dict], dict] | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def set_sender(self, callback: Callable[[dict], dict]) -> None:
        """设置发送回调: callback(notification) -> {"success": bool, "error": str|None, ...}"""
        self._send_callback = callback

    def enqueue(self, notification: dict, priority: str = "普通") -> bool:
        """入队。检查冷却 → 加锁入 heapq 优先级队列

        全部在锁内操作。冷却未通过 → return False。
        """
        with self._lock:
            ok, reason = self._check_cooldown(notification)
            if not ok:
                logger.info(f"通知被冷却丢弃: {reason}")
                return False
            prio_val = _PRIORITY_MAP.get(priority, 2)
            now = time.time()
            item = {
                "notification": notification,
                "priority": priority,
                "enqueued_at": now,
                "deferred_until": notification.get("deferred_until"),
            }
            heapq.heappush(self._heap, (-prio_val, now, item))
            self._cv.notify()
            return True

    def _check_cooldown(self, notification: dict) -> tuple[bool, str]:
        """加锁检查冷却

        same_sender 5min / same_subject 10min / global 3 条后暂停 1min
        """
        with self._lock:
            now = time.time()
            sender = notification.get("sender", "")
            if sender and now - self._cooldown.get(f"sender:{sender}", 0) < _SENDER_COOLDOWN:
                return False, "same_sender 5min cooldown"
            subject = notification.get("subject", "")
            if subject and now - self._cooldown.get(f"subject:{subject}", 0) < _SUBJECT_COOLDOWN:
                return False, "same_subject 10min cooldown"
            # global 冷却窗口重置
            if now > self._global_reset_at:
                self._global_count = 0
                self._global_reset_at = now + _GLOBAL_PAUSE
            if self._global_count >= _GLOBAL_MAX_COUNT:
                return False, "global 3/min cooldown"
            return True, ""

    def _update_cooldown(self, notification: dict) -> None:
        """加锁更新冷却（发送成功后调用，必须在锁内以避免 TOCTOU 竞态）"""
        with self._lock:
            now = time.time()
            sender = notification.get("sender", "")
            subject = notification.get("subject", "")
            if sender:
                self._cooldown[f"sender:{sender}"] = now
            if subject:
                self._cooldown[f"subject:{subject}"] = now
            self._global_count += 1

    def start(self) -> None:
        """启动出队循环线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self.process_queue, daemon=True)
        self._thread.start()
        logger.info("通知队列处理线程已启动")

    def stop(self) -> None:
        """停止出队循环"""
        self._running = False
        with self._cv:
            self._cv.notify_all()

    def process_queue(self) -> None:
        """出队循环线程

        流程:
          1. 优先取紧急（heapq 负数排序）
          2. 检查 deferred_until → 未到时间的跳过
          3. 聚合同分类普通通知（5 分钟窗口）
          4. token_bucket.acquire → 获取令牌
          5. 发送 → 发送成功则 _update_cooldown
        """
        while self._running:
            item: dict | None = None
            with self._cv:
                while self._running and not self._heap:
                    self._cv.wait(timeout=1.0)
                if not self._running:
                    break
                # 查看堆顶
                _neg_prio, _enq, top = self._heap[0]
                now = time.time()
                deferred = top.get("deferred_until")
                if deferred and deferred > now:
                    wait = min(1.0, max(0.1, deferred - now))
                    self._cv.wait(timeout=wait)
                    continue
                heapq.heappop(self._heap)
                item = top

            if item is None:
                continue

            # 聚合同分类普通通知
            notification = self._aggregate(item)

            # 获取令牌
            if not self.rate_limiter.acquire(timeout=1.0):
                # 未获取令牌，重新入队稍后重试
                with self._lock:
                    prio_val = _PRIORITY_MAP.get(item["priority"], 2)
                    heapq.heappush(
                        self._heap, (-prio_val, item["enqueued_at"], item)
                    )
                continue

            # 发送
            if self._send_callback is None:
                logger.warning("未设置发送回调，丢弃通知")
                continue
            try:
                result = self._send_callback(notification)
            except Exception as e:
                logger.error(f"发送回调异常: {e}", exc_info=True)
                result = {"success": False, "error": str(e)}

            if result.get("success"):
                self._update_cooldown(notification)
            else:
                logger.warning(
                    f"通知发送失败: {result.get('error')} (已由回调持久化到失败队列)"
                )

    def _aggregate(self, item: dict) -> dict:
        """聚合同分类普通通知（5 分钟窗口内）

        相同分类的 N 条普通通知 → 合并为 "您有 N 封新{category}邮件待处理" 汇总消息
        """
        notification = dict(item["notification"])
        if item["priority"] != "普通":
            return notification

        category = notification.get("category", "")
        if not category:
            return notification

        now = time.time()
        aggregated = [notification]
        remaining: list[tuple[int, float, dict]] = []

        with self._lock:
            while self._heap:
                neg_prio, enq, other = heapq.heappop(self._heap)
                other_notif = other["notification"]
                deferred = other.get("deferred_until")
                ready = (not deferred) or deferred <= now
                same_cat = other_notif.get("category", "") == category
                in_window = (now - other.get("enqueued_at", now)) <= _AGGREGATION_WINDOW
                if (
                    other["priority"] == "普通"
                    and ready
                    and same_cat
                    and in_window
                ):
                    aggregated.append(other_notif)
                else:
                    remaining.append((neg_prio, enq, other))
            # 放回未参与聚合的项
            for entry in remaining:
                heapq.heappush(self._heap, entry)

        if len(aggregated) > 1:
            notification["content"] = (
                f"您有 {len(aggregated)} 封新{category}邮件待处理"
            )
            notification["_aggregated_count"] = len(aggregated)
            logger.info(f"聚合 {len(aggregated)} 封 {category} 通知为汇总消息")
        return notification
