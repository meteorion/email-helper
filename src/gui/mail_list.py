"""邮件列表组件 - Flet 实现"""

import flet as ft
from src.core.models import MailData
from src.core.logger import get_logger

logger = get_logger("gui.mail_list")


class MailListView(ft.ListView):
    """邮件列表视图"""

    def __init__(self, on_select=None):
        super().__init__()
        self.spacing = 0
        self.padding = ft.Padding(top=8)
        self.expand = True
        self._mails: dict[str, MailData] = {}
        self._on_select = on_select

    def set_mails(self, mails: list[MailData]):
        """设置邮件列表"""
        self.controls.clear()
        self._mails.clear()

        for mail in mails:
            self._mails[mail.message_id] = mail
            self.controls.append(_build_mail_item(mail, self._on_item_click))

        logger.info(f"邮件列表已更新: {len(mails)} 封")

    def _on_item_click(self, e: ft.ControlEvent):
        """列表项点击"""
        message_id = e.control.data
        if message_id and self._on_select:
            logger.info(f"选中邮件: {message_id}")
            self._on_select(message_id)

    def mark_as_read(self, message_id: str):
        """标记为已读并刷新"""
        if message_id in self._mails:
            self._mails[message_id].is_read = True
            self.set_mails(list(self._mails.values()))


def _build_mail_item(mail: MailData, on_click) -> ft.Container:
    """构建单个邮件列表项"""
    unread = not mail.is_read

    # 发件人样式
    sender = ft.Text(
        mail.sender if not mail.sender.startswith("<") else mail.sender.split("<")[0].strip(),
        size=14,
        weight=ft.FontWeight.W_600 if unread else ft.FontWeight.W_400,
        color=ft.Colors.GREY_900 if unread else ft.Colors.GREY_700,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # 时间
    time_str = mail.send_time.strftime("%m-%d %H:%M")
    time_text = ft.Text(
        time_str,
        size=12,
        color=ft.Colors.GREY_500,
    )

    # 主题
    subject = ft.Text(
        mail.subject,
        size=13,
        weight=ft.FontWeight.W_600 if unread else ft.FontWeight.W_400,
        color=ft.Colors.GREY_900 if unread else ft.Colors.GREY_700,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # 预览
    preview_controls = [subject]
    if mail.body_text:
        preview = mail.body_text[:80].replace("\n", " ")
        if len(mail.body_text) > 80:
            preview += "..."
        preview_controls.append(
            ft.Text(
                preview,
                size=12,
                color=ft.Colors.GREY_500,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )

    # 附件标记
    if mail.attachments:
        preview_controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.ATTACH_FILE, size=12, color=ft.Colors.GREY_500),
                    ft.Text(
                        f"{len(mail.attachments)} 个附件",
                        size=11,
                        color=ft.Colors.GREY_500,
                    ),
                ],
                spacing=4,
            )
        )

    content = ft.Column(
        [
            ft.Row(
                [
                    ft.Container(
                        ft.Icon(ft.Icons.CIRCLE, size=8, color=ft.Colors.BLUE_500),
                        visible=unread,
                        margin=ft.Margin(right=6),
                    ),
                    sender,
                    ft.Container(expand=True),
                    time_text,
                ],
                spacing=4,
            ),
            ft.Column(preview_controls, spacing=4),
        ],
        spacing=6,
    )

    return ft.Container(
        content=content,
        data=mail.message_id,
        on_click=on_click,
        padding=ft.Padding(left=16, top=12, right=16, bottom=12),
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_100)),
        bgcolor=ft.Colors.WHITE if not unread else None,
        ink=True,
        border_radius=0,
    )