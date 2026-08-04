"""HTTP 请求 Action：调用 requests 库发起外部 API 请求。"""

from __future__ import annotations

from typing import Any

from src.workflow.actions.base import BaseAction


class HttpRequestAction(BaseAction):
    """发起 HTTP 请求，返回状态码、响应文本与解析后的 JSON。"""

    action_name = "http_request"

    def execute(self) -> Any:
        import requests  # 延迟导入，避免未安装时影响包导入

        url = self.config.get("url")
        if not url:
            raise ValueError("http_request 缺少 url")

        method = str(self.config.get("method", "GET")).upper()
        headers = self.config.get("headers", {}) or {}
        params = self.config.get("params")
        body = self.config.get("body")
        timeout = self.config.get("timeout", 10)
        verify_ssl = self.config.get("verify_ssl", True)

        # 区分 JSON / 表单 / 纯文本
        json_body = None
        data_body = None
        if body is not None:
            if isinstance(body, (dict, list)):
                json_body = body
            elif isinstance(body, str):
                data_body = body

        self.logger.info(f"HTTP {method} {url}")
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            data=data_body,
            timeout=timeout,
            verify=verify_ssl,
        )

        try:
            json_resp = resp.json()
        except ValueError:
            json_resp = None

        return {
            "status_code": resp.status_code,
            "text": resp.text,
            "json": json_resp,
            "headers": dict(resp.headers),
        }
