"""配置文件变更监听，自动热重载

通过轮询文件 mtime 检测配置文件变化，变化时触发对应回调实现热重载。
不依赖 watchdog/inotify，避免额外依赖。

用法：
    watcher = ConfigWatcher(
        watch_paths=[Path("config/ai.json"), Path("rules/custom_rules.yaml")],
        callbacks={
            "config/ai.json": on_ai_config_changed,
            "rules/custom_rules.yaml": on_rules_changed,
        },
    )
    watcher.start()
"""

import threading
from pathlib import Path
from typing import Callable, Optional

from src.core.logger import get_logger

logger = get_logger("core.config_watcher")

# 轮询间隔（秒）
_POLL_INTERVAL = 5.0


class ConfigWatcher:
    """配置文件变更监听，自动热重载"""

    def __init__(
        self,
        watch_paths: list[Path],
        callbacks: dict[str, Callable],
    ):
        """
        初始化配置监听器

        Args:
            watch_paths: 需监听的文件路径列表（可为相对或绝对路径）
            callbacks: 路径字符串 -> 回调函数 的映射，key 会被解析为绝对路径
                后与 watch_paths 匹配，因此相对路径写法需与当前工作目录一致。
                例：{"config/ai.json": on_ai_config_changed}
        """
        self._watchers: dict[Path, tuple[Callable, Optional[float]]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 标准化 callbacks：用解析后的绝对路径字符串作 key，
        # 兼容相对路径 / 绝对路径 / 不同分隔符写法
        normalized_callbacks: dict[str, Callable] = {}
        for key, cb in callbacks.items():
            normalized_callbacks[self._abs_key(key)] = cb

        for path in watch_paths:
            p = Path(path)
            cb = normalized_callbacks.get(self._abs_key(p))
            if cb is not None:
                self._register_internal(p, cb)
            else:
                logger.warning(
                    f"watch_paths 中的路径未在 callbacks 中找到对应回调，忽略: {p}"
                )

    def start(self) -> None:
        """启动监听线程（daemon=True）

        每 5 秒检查文件 mtime，变化则触发回调。
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("配置监听器已在运行")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="config-watcher",
        )
        self._thread.start()
        logger.info(
            f"配置监听器已启动，监听 {len(self._watchers)} 个文件，"
            f"轮询间隔 {int(_POLL_INTERVAL)} 秒"
        )

    def stop(self) -> None:
        """停止监听线程"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("配置监听器已停止")

    def _watch_loop(self) -> None:
        """检查 mtime → 触发回调

        循环直到 _stop_event 被设置。每轮快照一份监听列表后逐个检查，
        避免在回调中长时间持锁。
        """
        while not self._stop_event.wait(_POLL_INTERVAL):
            with self._lock:
                items = list(self._watchers.items())

            for path, (callback, last_mtime) in items:
                try:
                    if not path.exists():
                        # 文件被删除，记录当前状态不触发回调
                        if last_mtime is not None:
                            with self._lock:
                                self._watchers[path] = (callback, None)
                        continue

                    current_mtime = path.stat().st_mtime

                    # 首次发现文件存在：仅记录 mtime，不触发回调
                    if last_mtime is None:
                        with self._lock:
                            self._watchers[path] = (callback, current_mtime)
                        continue

                    if current_mtime != last_mtime:
                        logger.info(f"配置文件已变更: {path}")
                        try:
                            callback()
                        except Exception as e:
                            logger.error(f"重载配置失败: {path}: {e}", exc_info=True)
                        with self._lock:
                            self._watchers[path] = (callback, current_mtime)
                except Exception as e:
                    logger.error(f"检查配置文件失败: {path}: {e}")

    def register(self, path: Path, callback: Callable) -> None:
        """注册新的文件监听

        Args:
            path: 监听的文件路径
            callback: 文件变化时触发的回调
        """
        with self._lock:
            self._register_internal(Path(path), callback)

    def _register_internal(self, path: Path, callback: Callable) -> None:
        """注册监听项（内部实现，调用方需自行加锁）

        若文件存在，记录当前 mtime 作为基线；不存在则记录 None，
        待文件出现后再建立基线，避免首次注册即误触发。
        """
        try:
            mtime = path.stat().st_mtime if path.exists() else None
        except OSError as e:
            logger.warning(f"读取文件 mtime 失败: {path}: {e}")
            mtime = None
        self._watchers[path] = (callback, mtime)
        logger.debug(f"已注册配置监听: {path}")

    @staticmethod
    def _abs_key(p: Path | str) -> str:
        """将路径标准化为解析后的绝对路径字符串，用于匹配

        不要求文件存在（resolve 默认非严格模式）。
        """
        try:
            return str(Path(p).resolve())
        except Exception:
            return str(Path(p))
