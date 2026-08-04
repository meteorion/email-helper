"""邮件列表组件 - Flet 实现

简洁清新风格：圆角列表项、未读用左侧蓝色竖条 + 粗体、无图标。
附件用文字标记，配色遵循 theme.Color 规范。
"""

import flet as ft

from src.core.models import MailData
from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font

logger = get_logger("gui.mail_list")


@ft.control("ListView", init=False)
class MailListView(ft.ListView):
    """邮件列表视图"""

    def __init__(self, on_select=None, is_dark: bool = False):
        super().__init__()
        self.spacing = 4
        self.padding = ft.Padding(left=8, top=8, right=8, bottom=8)
        self.expand = True
        self.auto_scroll = True
        self._mails: dict[str, MailData] = {}
        self._on_select = on_select
        self._is_dark = is_dark
        self._selected_id: str | None = None

    # ---- 颜色辅助 ----
    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    def set_mails(self, mails: list[MailData]):
        """设置邮件列表"""
        self.controls.clear()
        self._mails.clear()

        for mail in mails:
            self._mails[mail.message_id] = mail
            self.controls.append(self._build_mail_item(mail))

        logger.info(f"邮件列表已更新: {len(mails)} 封")
        self.update()

    def _build_mail_item(self, mail: MailData) -> ft.Container:
        """构建单个邮件列表项"""
        c = self._colors
        unread = not mail.is_read
        selected = (self._selected_id == mail.message_id)

        # 选中 / 未读 背景与左边框
        if selected:
            bgcolor = c.BG_SELECTED
            bar_color = c.PRIMARY
            bar_visible = True
        elif unread:
            bgcolor = c.BG_CARD
            bar_color = c.PRIMARY
            bar_visible = True
        else:
            bgcolor = c.BG_CARD
            bar_color = None
            bar_visible = False

        # 发件人显示名
        sender_text = mail.sender
        if "<" in sender_text:
            sender_text = sender_text.split("<")[0].strip()

        # 发件人 + 时间
        top_row = ft.Row(
            [
                ft.Text(
                    sender_text,
                    size=Font.BODY,
                    weight=ft.FontWeight.W_600 if unread else ft.FontWeight.W_500,
                    color=c.TEXT_PRIMARY,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True,
                ),
                ft.Text(
                    mail.send_time.strftime("%m-%d %H:%M"),
                    size=Font.AUX,
                    color=c.PRIMARY if unread else c.TEXT_SECONDARY,
                ),
            ],
            spacing=8,
        )

        # 主题
        subject_row = ft.Text(
            mail.subject,
            size=Font.BODY,
            weight=ft.FontWeight.W_600 if unread else ft.FontWeight.W_400,
            color=c.TEXT_PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # 预览 + 附件标记
        bottom_controls = []
        if mail.body_text:
            preview = mail.body_text[:60].replace("\n", " ")
            if len(mail.body_text) > 60:
                preview += "..."
            bottom_controls.append(
                ft.Text(
                    preview,
                    size=Font.AUX,
                    color=c.TEXT_SECONDARY,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        # 附件用文字标记，避免图标
        if mail.attachments:
            bottom_controls.append(
                ft.Row(
                    [
                        ft.Text(
                            f"附件 {len(mail.attachments)} 个",
                            size=Font.SMALL,
                            color=c.TEXT_SECONDARY,
                        ),
                    ],
                    spacing=4,
                )
            )

        content = ft.Column(
            [
                top_row,
                subject_row,
                *bottom_controls,
            ],
            spacing=4,
        )

        # 左侧未读/选中竖条
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        width=3,
                        height=36,
                        bgcolor=bar_color,
                        border_radius=2,
                        visible=bar_visible,
                    ),
                    ft.Container(
                        content=content,
                        expand=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            data=mail.message_id,
            on_click=self._on_item_click,
            padding=ft.Padding(left=8, top=10, right=12, bottom=10),
            border_radius=Radius.CARD,
            bgcolor=bgcolor,
            ink=True,
            border=ft.Border.all(1, c.BORDER_LIGHT) if selected else None,
        )

    def _on_item_click(self, e: ft.ControlEvent):
        """列表项点击"""
        message_id = e.control.data
        if not message_id:
            return
        self._selected_id = message_id
        # 刷新选中态
        self.controls.clear()
        for mail in self._mails.values():
            self.controls.append(self._build_mail_item(mail))
        logger.info(f"选中邮件: {message_id}")
        if self._on_select:
            self._on_select(message_id)
        self.update()

    def mark_as_read(self, message_id: str):
        """标记为已读并刷新"""
        if message_id in self._mails:
            self._mails[message_id].is_read = True
            self.controls.clear()
            for mail in self._mails.values():
                self.controls.append(self._build_mail_item(mail))
            self.update()

    def update_theme(self, is_dark: bool):
        """切换主题时刷新配色"""
        self._is_dark = is_dark
        self.controls.clear()
        for mail in self._mails.values():
            self.controls.append(self._build_mail_item(mail))
        self.update()
