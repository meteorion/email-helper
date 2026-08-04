"""账户配置对话框 - Flet 实现

按 email_desktop_ui_design.html 设计稿风格重写：
  - 640px 宽、圆角 12px、居中弹窗 + 半透明遮罩
  - header 灰底 (#f8fafc) + 标题 + 关闭按钮 (hover 红)
  - 表单分组：基本信息 / IMAP 配置 / SMTP 配置
  - 圆角输入框 (浅灰底 #f9fafb，focus 蓝边 + 光晕)
  - 底部胶囊按钮：存草稿(次要) / 取消(次要) / 保存配置(主按钮渐变)
  - 深浅双主题适配
保持 main.py 调用的公共接口兼容。
"""

import json
import base64
import threading
from pathlib import Path

import flet as ft

from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font

logger = get_logger("gui.account")


def _field(colors, *, password=False, label=None, hint=None, value=None,
           width=None, on_change=None, reveal=False):
    """统一构建设计稿风格输入框"""
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        password=password,
        can_reveal_password=reveal,
        text_size=Font.BODY_SM,
        border_radius=Radius.CARD,
        border_color=colors.BORDER,
        bgcolor=colors.BG_HOVER,
        focused_border_color=colors.PRIMARY_500,
        focused_bgcolor=colors.BG_MAIN,
        content_padding=ft.Padding(14, 8, 14, 8),
        width=width,
        on_change=on_change,
    )


class AccountDialog:
    """账户配置对话框（设计稿风格）"""

    def __init__(self, page: ft.Page, config_path: str = "config/account.json",
                 is_dark: bool = False):
        self.page = page
        self.config_path = Path(config_path)
        self._is_dark = is_dark
        self._account_data = {}

        # 表单字段
        c = self._colors
        self.email_input = _field(c, label="邮箱地址", hint="your@email.com")
        self.password_input = _field(c, label="密码", hint="邮箱密码或授权码",
                                     password=True, reveal=True)
        self.imap_host = _field(c, label="IMAP 服务器", value="imap.exmail.qq.com")
        self.imap_port = _field(c, label="端口", value="993", width=120)
        self.imap_ssl = ft.Checkbox(
            label="使用 SSL 加密", value=True,
            label_style=ft.TextStyle(size=Font.BODY_SM, color=c.TEXT_PRIMARY),
        )
        self.smtp_host = _field(c, label="SMTP 服务器", value="smtp.exmail.qq.com")
        self.smtp_port = _field(c, label="端口", value="465", width=120)
        self.smtp_ssl = ft.Checkbox(
            label="使用 SSL 加密", value=True,
            label_style=ft.TextStyle(size=Font.BODY_SM, color=c.TEXT_PRIMARY),
        )

        # 状态文字
        self._status_text = ft.Text(size=Font.AUX, color=c.TEXT_SECONDARY)

        # 测试按钮
        self._test_btn = ft.Container(
            content=ft.Text("测试连接", size=Font.AUX, color=c.TEXT_SECONDARY),
            padding=ft.Padding(10, 5, 10, 5),
            border=ft.Border.all(1, c.BORDER),
            border_radius=Radius.PILL,
            bgcolor=c.BG_MAIN,
            on_click=self._on_test_connection,
            ink=True,
        )

        # 构建 dialog 内容
        self._dialog = ft.AlertDialog(
            modal=True,
            content=self._build_content(),
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            actions=self._build_actions(),
        )

        self._load_config()

    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    # ---- 构建 UI ----
    def _build_content(self) -> ft.Container:
        """构建弹窗内容（header + body）"""
        c = self._colors

        # Header
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        "邮箱账户配置",
                        size=Font.WINDOW_TITLE,
                        weight=ft.FontWeight.W_600,
                        color=c.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    self._build_close_btn(),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(20, 16, 20, 16),
            bgcolor=c.BG_SIDEBAR,
            border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER)),
        )

        # Body
        body = ft.Container(
            content=ft.Column(
                [
                    # 状态提示
                    self._status_text,
                    # 基本信息
                    self._build_section("基本信息", [
                        self.email_input,
                        self.password_input,
                    ]),
                    # IMAP
                    self._build_section("IMAP 配置（收邮件）", [
                        ft.Row([self.imap_host, self.imap_port], spacing=12),
                        self.imap_ssl,
                    ]),
                    # SMTP
                    self._build_section("SMTP 配置（发邮件）", [
                        ft.Row([self.smtp_host, self.smtp_port], spacing=12),
                        self.smtp_ssl,
                    ]),
                ],
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.Padding(20, 20, 20, 20),
            width=600,
            height=440,
        )

        return ft.Container(
            content=ft.Column([header, body], spacing=0),
            width=640,
            border_radius=Radius.DIALOG,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=c.BG_MAIN,
        )

    def _build_close_btn(self) -> ft.Container:
        """关闭按钮（圆形，hover 红）"""
        c = self._colors
        return ft.Container(
            content=ft.Icon(ft.Icons.CLOSE, size=16, color=c.TEXT_SECONDARY),
            width=26,
            height=26,
            border_radius=50,
            alignment=ft.Alignment(0, 0),
            on_click=self._on_cancel,
            ink=True,
        )

    def _build_section(self, title: str, controls: list) -> ft.Column:
        """表单分组（小标题 + 字段）"""
        c = self._colors
        return ft.Column(
            [
                ft.Text(
                    title,
                    size=Font.BODY_SM,
                    weight=ft.FontWeight.W_600,
                    color=c.TEXT_PRIMARY,
                ),
                *controls,
            ],
            spacing=10,
        )

    def _build_actions(self) -> list:
        """底部按钮区"""
        c = self._colors

        # 左侧：测试连接
        left = ft.Row([self._test_btn], spacing=8)

        # 右侧：取消 + 保存
        cancel_btn = ft.Container(
            content=ft.Text("取消", size=Font.AUX, color=c.TEXT_SECONDARY),
            padding=ft.Padding(14, 6, 14, 6),
            border=ft.Border.all(1, c.BORDER),
            border_radius=Radius.PILL,
            bgcolor=c.BG_MAIN,
            on_click=self._on_cancel,
            ink=True,
        )

        save_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SAVE_OUTLINED, size=14, color=c.TEXT_ON_PRIMARY),
                    ft.Text(
                        "保存配置",
                        size=Font.AUX,
                        color=c.TEXT_ON_PRIMARY,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding(16, 6, 16, 6),
            border_radius=Radius.PILL,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0),
                end=ft.Alignment(1, 0),
                colors=c.COMPOSE_GRADIENT,
            ),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=6,
                color="rgba(59,130,246,0.25)",
                offset=ft.Offset(0, 2),
            ),
            on_click=self._on_save,
            ink=True,
        )

        right = ft.Row([cancel_btn, save_btn], spacing=8)
        return [left, right]

    # ---- 显示/隐藏 ----
    def show(self):
        """显示对话框"""
        if self._dialog not in self.page.overlay:
            self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    def _close(self):
        self._dialog.open = False
        self.page.update()

    # ---- 配置加载/保存 ----
    def _load_config(self):
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.email_input.value = data.get("email", "")

            pwd_b64 = data.get("password", "")
            if pwd_b64:
                try:
                    self.password_input.value = base64.b64decode(pwd_b64).decode("utf-8")
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
            logger.info("账户配置已加载")
        except Exception as e:
            logger.error(f"加载账户配置失败: {e}")

    def _on_save(self, e):
        c = self._colors
        email = (self.email_input.value or "").strip()
        password = (self.password_input.value or "").strip()

        if not email:
            self._status_text.value = "请输入邮箱地址"
            self._status_text.color = c.ERROR
            self.page.update()
            return

        if not password:
            self._status_text.value = "请输入密码"
            self._status_text.color = c.ERROR
            self.page.update()
            return

        config = {
            "email": email,
            "password": base64.b64encode(password.encode("utf-8")).decode("utf-8"),
            "password_decoded": password,
            "imap": {
                "host": (self.imap_host.value or "").strip(),
                "port": int((self.imap_port.value or "993").strip() or "993"),
                "ssl": self.imap_ssl.value,
            },
            "smtp": {
                "host": (self.smtp_host.value or "").strip(),
                "port": int((self.smtp_port.value or "465").strip() or "465"),
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
            self._status_text.color = c.SUCCESS
            self.page.update()
            self._close()
        except Exception as ex:
            logger.error(f"保存账户配置失败: {ex}")
            self._status_text.value = f"保存失败: {ex}"
            self._status_text.color = c.ERROR
            self.page.update()

    def _on_cancel(self, e):
        self._close()

    def _on_test_connection(self, e):
        c = self._colors
        email = (self.email_input.value or "").strip()
        password = (self.password_input.value or "").strip()

        if not email or not password:
            self._status_text.value = "请先填写邮箱和密码"
            self._status_text.color = c.ERROR
            self.page.update()
            return

        self._test_btn.content.value = "测试中..."
        self._status_text.value = "正在测试连接..."
        self._status_text.color = c.TEXT_SECONDARY
        self.page.update()

        def _do_test():
            try:
                from src.mail.imap_client import ImapClient
                from src.mail.smtp_client import SmtpClient

                imap_client = ImapClient(
                    host=(self.imap_host.value or "").strip(),
                    port=int((self.imap_port.value or "993").strip() or "993"),
                    username=email,
                    password=password,
                    use_ssl=self.imap_ssl.value,
                )
                imap_client.connect()
                imap_client.disconnect()

                smtp_client = SmtpClient(
                    host=(self.smtp_host.value or "").strip(),
                    port=int((self.smtp_port.value or "465").strip() or "465"),
                    username=email,
                    password=password,
                    use_ssl=self.smtp_ssl.value,
                )
                smtp_client.connect()
                smtp_client.disconnect()

                self._status_text.value = "IMAP 和 SMTP 连接测试成功!"
                self._status_text.color = c.SUCCESS
                logger.info("账户连接测试成功")
            except Exception as ex:
                self._status_text.value = f"连接测试失败: {ex}"
                self._status_text.color = c.ERROR
                logger.error(f"连接测试失败: {ex}")
            finally:
                self._test_btn.content.value = "测试连接"
                self.page.update()

        threading.Thread(target=_do_test, daemon=True).start()

    # ---- 公共方法 ----
    def get_account_data(self) -> dict:
        return self._account_data

    def update_theme(self, is_dark: bool):
        """切换主题时刷新配色"""
        self._is_dark = is_dark
        # 重建以应用新配色
        c = self._colors
        self.email_input.border_color = c.BORDER
        self.email_input.bgcolor = c.BG_HOVER
        self.email_input.focused_border_color = c.PRIMARY_500
        self.email_input.focused_bgcolor = c.BG_MAIN
        self.page.update()
