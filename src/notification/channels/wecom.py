"""企微群机器人 Webhook 通知渠道"""

import requests

from src.core.logger import get_logger

logger = get_logger("notification.wecom")


class WecomWebhookChannel:
    """企微群机器人 Webhook 渠道

    支持 markdown / text 消息类型，超时 10 秒。
    """

    def __init__(self, webhook_url: str, timeout: int = 10):
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(
        self,
        content: str,
        msg_type: str = "markdown",
        mentioned: list[str] | None = None,
    ) -> dict:
        """发送企微群机器人消息

        Args:
            content: 消息内容
            msg_type: 消息类型 (markdown/text)
            mentioned: @人列表 (仅 text 类型生效)

        Returns:
            {"success": bool, "error": str|None, "status_code": int}
            企微频率限制错误码 45009 → error 包含 "rate_limit:45009" 标记，
            供 RetryHandler.is_rate_limit_error 识别后固定等待 60 秒。
        """
        if msg_type == "markdown":
            payload = {"msgtype": "markdown", "markdown": {"content": content}}
        elif msg_type == "text":
            payload = {
                "msgtype": "text",
                "text": {
                    "content": content,
                    "mentioned_list": mentioned or [],
                },
            }
        else:
            return {
                "success": False,
                "error": f"invalid_param:不支持的消息类型 {msg_type}",
                "status_code": 0,
            }

        try:
            resp = requests.post(
                self.webhook_url, json=payload, timeout=self.timeout
            )
        except requests.Timeout as e:
            logger.warning(f"企微请求超时: {e}")
            return {"success": False, "error": f"timeout:{e}", "status_code": 0}
        except requests.ConnectionError as e:
            logger.warning(f"企微连接失败: {e}")
            return {"success": False, "error": f"network:{e}", "status_code": 0}
        except requests.RequestException as e:
            logger.warning(f"企微请求异常: {e}")
            return {"success": False, "error": f"network:{e}", "status_code": 0}

        status_code = resp.status_code
        try:
            data = resp.json()
        except Exception as e:
            return {
                "success": False,
                "error": f"invalid_param:响应解析失败 {e}",
                "status_code": status_code,
            }

        errcode = data.get("errcode", -1)
        errmsg = data.get("errmsg", "")

        if errcode == 0:
            return {"success": True, "error": None, "status_code": status_code}
        if errcode == 45009:
            logger.warning("企微频率限制 45009")
            return {
                "success": False,
                "error": "rate_limit:45009 api frequency limit exceeded",
                "status_code": status_code,
            }
        if errcode in (40014, 41001):
            return {
                "success": False,
                "error": f"auth_failed:errcode={errcode} {errmsg}",
                "status_code": status_code,
            }
        return {
            "success": False,
            "error": f"invalid_param:errcode={errcode} {errmsg}",
            "status_code": status_code,
        }
