"""保存处理记录 Action：把流程处理结果写入 data/records/YYYY-MM-DD/ 目录。"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import Any

from src.workflow.actions.base import BaseAction


class SaveRecordAction(BaseAction):
    """保存处理记录到本地文件，支持 json/csv/txt 格式。"""

    action_name = "save_record"

    def execute(self) -> Any:
        fmt = self.config.get("format", "json").lower()
        base_path = self.config.get("path", "./data/records/")
        data = self.config.get("data", {})

        today = datetime.now().strftime("%Y-%m-%d")
        day_dir = os.path.join(base_path, today)
        os.makedirs(day_dir, exist_ok=True)

        ts = datetime.now().strftime("%H%M%S%f")
        filename = f"record_{ts}.{fmt}"
        file_path = os.path.join(day_dir, filename)

        if fmt == "json":
            self._write_json(file_path, data)
        elif fmt == "csv":
            self._write_csv(file_path, data)
        else:
            self._write_text(file_path, data)

        self.logger.info(f"处理记录已保存: {file_path}")
        return {"path": file_path, "format": fmt}

    @staticmethod
    def _write_json(path: str, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _write_csv(path: str, data: Any) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if isinstance(data, dict):
                writer.writerow(list(data.keys()))
                writer.writerow([str(v) for v in data.values()])
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                writer.writerow(headers)
                for row in data:
                    writer.writerow([str(row.get(h, "")) for h in headers])
            else:
                writer.writerow(["value"])
                writer.writerow([str(data)])

    @staticmethod
    def _write_text(path: str, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(data, (dict, list)):
                f.write(json.dumps(data, ensure_ascii=False, indent=2, default=str))
            else:
                f.write(str(data))
