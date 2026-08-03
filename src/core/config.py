"""应用配置管理模块"""

import json
from pathlib import Path
from typing import Any


# 默认配置
DEFAULT_CONFIG = {
    "app_name": "邮件助手",
    "version": "0.1.0",
    "data_dir": "./data",
    "log_dir": "./logs",
    "log_level": "INFO",
    "auto_start": True,
    "minimize_to_tray": True,
    "schedule": {
        "interval_minutes": 5,
        "work_hours_only": False,
        "work_hours": {"start": "08:30", "end": "18:30"},
        "work_days": [1, 2, 3, 4, 5],
    },
}


class AppConfig:
    """应用配置管理器，负责加载/保存 config/app.json"""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            config_path = Path("config/app.json")
        self._path = Path(config_path)
        self._data: dict = {}
        self.load()

    def load(self):
        """加载配置文件，不存在则创建默认配置"""
        if not self._path.exists():
            self._data = dict(DEFAULT_CONFIG)
            self._ensure_parent_dir()
            self.save()
        else:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def save(self):
        """保存当前配置到文件"""
        self._ensure_parent_dir()
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点号分隔的路径访问 (如 'schedule.interval_minutes')"""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """设置配置项，支持点号分隔的路径"""
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value
        self.save()

    @property
    def data(self) -> dict:
        return dict(self._data)

    def _ensure_parent_dir(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
