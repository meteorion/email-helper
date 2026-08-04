"""账户配置对话框 - Flet 实现"""

import json
import base64
from pathlib import Path

import flet as ft

from src.core.logger import get_logger

logger = get_logger("gui.account")


class AccountDialog:
    """账户配置对话框"""

    def __init__(self, page: ft.Page, config_path: str = "config/account.json"):
        self.page = page
        self.config_path = Path(config_path)
        self._account_data = {}

        # 表单字段（无图标，圆角统一 6px）
        self.email_input = ft.TextField(
            label="邮箱地址",
            hint_text="your@email.com",
            border_radius=6,
        )
        self.password_input = ft.TextField(
            label="密码",
            hint_text="邮箱密码或授权码",
            password=True,
            can_reveal_password=True,
            border_radius=6,
        )

        self.imap_host = ft.TextField(
            label="IMAP 服务器",
            value="imap.exmail.qq.com",
            border_radius=6,
        )
        self.imap_port = ft.TextField(
            label="IMAP 端口",
            value="993",
            width=100,
            border_radius=6,
        )
        self.imap_ssl = ft.Checkbox(label="使用 SSL 加密", value=True)

        self.smtp_host = ft.TextField(
            label="SMTP 服务器",
            value="smtp.exmail.qq.com",
            border_radius=6,
        )
        self.smtp_port = ft.TextField(
            label="SMTP 端口",
            value="465",
            width=100,
            border_radius=6,
        )
        self.smtp_ssl = ft.Checkbox(label="使用 SSL 加密", value=True)

        self._status_text = ft.Text(size=12, color=ft.Colors.GREY_500)
        self._test_btn = ft.OutlinedButton(
            "测试连接",
            on_click=self._on_test_connection,
        )

        self._dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("邮箱账户配置", weight=ft.FontWeight.W_600),
            content=ft.Column(
                [
                    self._status_text,
                    ft.Divider(height=1),
                    ft.Text("基本信息", weight=ft.FontWeight.W_600, size=14),
                    self.email_input,
                    self.password_input,
                    ft.Divider(height=1),
                    ft.Text("IMAP 配置（收邮件）", weight=ft.FontWeight.W_600, size=14),
                    ft.Row([self.imap_host, self.imap_port], spacing=12),
                    self.imap_ssl,
                    ft.Divider(height=1),
                    ft.Text("SMTP 配置（发邮件）", weight=ft.FontWeight.W_600, size=14),
                    ft.Row([self.smtp_host, self.smtp_port], spacing=12),
                    self.smtp_ssl,
                ],
                spacing=8,
                height=480,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                self._test_btn,
                ft.Container(expand=True),
                ft.TextButton("取消", on_click=self._on_cancel),
                ft.FilledButton("保存配置", on_click=self._on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self._load_config()

    def show(self):
        """显示对话框"""
        if self._dialog not in self.page.overlay:
            self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    def _load_config(self):
        """加载配置"""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.email_input.value = data.get("email", "")

            pwd_b64 = data.get("password", "")
            if pwd_b64:
                try:
                    pwd = base64.b64decode(pwd_b64).decode("utf-8")
                    self.password_input.value = pwd
                except Exception:
                    pass

            imap = data.get("imap", {})
            self.imap_host.value = imap.get("host", "imap.exmail.qq.com")
            self.imap_port.value = str(imap.get("port", 993))
            self.imap_ssl.value = imap.get("ssl", True)

            smtp = data.get("smtp", {})
            self.smtp_host.value = smtp.get("host", "smtp.exmail.qq.com")
            self.smtp_port.value = str(smtp.get("port", 465))
            self.smtp_ssl.value = smtp.get("ssl", True)

            self._account_data = data
            self.page.update()

            logger.info("账户配置已加载")
        except Exception as e:
            logger.error(f"加载账户配置失败: {e}")

    def _on_save(self, e):
        """保存配置"""
        email = self.email_input.value.strip()
        password = self.password_input.value.strip()

        if not email:
            self._status_text.value = "请输入邮箱地址"
            self._status_text.color = ft.Colors.RED_500
            self.page.update()
            return

        if not password:
            self._status_text.value = "请输入密码"
            self._status_text.color = ft.Colors.RED_500
            self.page.update()
            return

        config = {
            "email": email,
            "password": base64.b64encode(password.encode("utf-8")).decode("utf-8"),
            "password_decoded": password,
            "imap": {
                "host": self.imap_host.value.strip(),
                "port": int(self.imap_port.value.strip() or "993"),
                "ssl": self.imap_ssl.value,
            },
            "smtp": {
                "host": self.smtp_host.value.strip(),
                "port": int(self.smtp_port.value.strip() or "465"),
                "ssl": self.smtp_ssl.value,
            },
        }

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            self._account_data = config
            logger.info("账户配置已保存")
            self._status_text.value = "配置已保存"
            self._status_text.color = ft.Colors.GREEN_600
            self.page.update()
            self._dialog.open = False
            self.page.update()

        except Exception as ex:
            logger.error(f"保存账户配置失败: {ex}")
            self._status_text.value = f"保存失败: {ex}"
            self._status_text.color = ft.Colors.RED_500
            self.page.update()

    def _on_cancel(self, e):
        """取消"""
        self._dialog.open = False
        self.page.update()

    def _on_test_connection(self, e):
        """测试连接"""
        email = self.email_input.value.strip()
        password = self.password_input.value.strip()

        if not email or not password:
            self._status_text.value = "请先填写邮箱和密码"
            self._status_text.color = ft.Colors.RED_500
            self.page.update()
            return

        self._test_btn.disabled = True
        self._test_btn.text = "测试中..."
        self._status_text.value = "正在测试连接..."
        self._status_text.color = ft.Colors.GREY_500
        self.page.update()

        import threading

        def _do_test():
            try:
                from src.mail.imap_client import ImapClient
                from src.mail.smtp_client import SmtpClient

                imap_client = ImapClient(
                    host=self.imap_host.value.strip(),
                    port=int(self.imap_port.value.strip() or "993"),
                    username=email,
                    password=password,
                    use_ssl=self.imap_ssl.value,
                )
                imap_client.connect()
                imap_client.disconnect()

                smtp_client = SmtpClient(
                    host=self.smtp_host.value.strip(),
                    port=int(self.smtp_port.value.strip() or "465"),
                    username=email,
                    password=password,
                    use_ssl=self.smtp_ssl.value,
                )
                smtp_client.connect()
                smtp_client.disconnect()

                self._status_text.value = "IMAP 和 SMTP 连接测试成功!"
                self._status_text.color = ft.Colors.GREEN_600
                logger.info("账户连接测试成功")
            except Exception as ex:
                self._status_text.value = f"连接测试失败: {ex}"
                self._status_text.color = ft.Colors.RED_500
                logger.error(f"连接测试失败: {ex}")
            finally:
                self._test_btn.disabled = False
                self._test_btn.text = "测试连接"
                self.page.update()

        threading.Thread(target=_do_test, daemon=True).start()

    def get_account_data(self) -> dict:
        """获取账户数据"""
        return self._account_data