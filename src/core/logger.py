"""日志初始化模块"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 模块级 logger 名称
LOG_APP = "app"
LOG_MAIL = "mail"
LOG_GUI = "gui"
LOG_STORAGE = "storage"


def setup_logging(log_dir: str | Path = "./logs", log_level: str = "INFO"):
    """
    初始化日志系统。

    - 输出到 logs/app.log (RotatingFileHandler, 10MB x 5)
    - DEBUG 级别时同时输出到控制台
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 文件 handler: 10MB 轮转, 保留 5 个
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # 根 logger
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)

    # 控制台 handler (仅 DEBUG 模式)
    if level <= logging.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger"""
    return logging.getLogger(name)
