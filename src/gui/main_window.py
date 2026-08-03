"""主窗口 - Flet 实现"""

import flet as ft
from datetime import datetime
import threading

from src.core.logger import get_logger
from src.gui.mail_list import MailListView
from src.gui.mail_detail import MailDetailView
from src.gui.account_dialog import AccountDialog
from src.gui.worker import MailFetchWorker

logger = get_logger("gui.main")


class MailApp:
    """邮件助手应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._init_page()

        # 状态变量
        self._fetching = False
        self._fetch_worker = None

        # 构建 UI
        self._build_ui()

        # 初始化后回调（由 main.py 设置）
        self._on_fetch = None

    def _init_page(self):
        """初始化页面"""
        self.page.title = "邮件助手"
        self.page.padding = 0
        self.page.window.width = 1100
        self.page.window.height = 720
        self.page.window.min_width = 800
        self.page.window.min_height = 540

    def _build_ui(self):
        """构建 UI 布局"""
        # 顶部应用栏
        self.page.appbar = ft.AppBar(
            leading=ft.Icon(ft.Icons.EMAIL),
            leading_width=40,
            title=ft.Text("邮件助手", size=18, weight=ft.FontWeight.W_600),
            center_title=False,
            bgcolor=ft.Colors.WHITE,
            actions=[
                self._build_fetch_btn(),
                ft.VerticalDivider(width=1),
                ft.IconButton(
                    icon=ft.Icons.EDIT,
                    tooltip="写邮件",
                    on_click=self._on_compose_clicked,
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    tooltip="设置",
                    on_click=self._on_settings_clicked,
                ),
            ],
        )

        # 侧栏 + 内容区
        sidebar = self._build_sidebar()
        content = self._build_content()

        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.VerticalDivider(width=1),
                    content,
                ],
                expand=True,
                spacing=0,
            )
        )

        # 底部状态栏
        self._status_connection = ft.Text("🔴 未连接", size=12, color=ft.Colors.GREY_500)
        self._status_last_fetch = ft.Text("上次拉取: --", size=12, color=ft.Colors.GREY_500)
        self._status_pending = ft.Text("待处理: 0", size=12, color=ft.Colors.GREY_500)
        self._status_next = ft.Text("下次: --", size=12, color=ft.Colors.GREY_500)

        self.page.add(
            ft.Container(
                content=ft.Row(
                    [
                        self._status_connection,
                        ft.Text("|", size=12, color=ft.Colors.GREY_300),
                        self._status_last_fetch,
                        ft.Text("|", size=12, color=ft.Colors.GREY_300),
                        self._status_pending,
                        ft.Text("|", size=12, color=ft.Colors.GREY_300),
                        self._status_next,
                    ],
                    spacing=8,
                ),
                padding=ft.Padding(left=16, top=6, right=16, bottom=6),
                bgcolor=ft.Colors.GREY_50,
                border=ft.Border(top=ft.BorderSide(1, ft.Colors.GREY_200)),
            )
        )

    def _build_fetch_btn(self) -> ft.IconButton:
        """构建拉取按钮"""
        self._fetch_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="拉取邮件",
            on_click=self._on_fetch_clicked,
        )
        return self._fetch_btn

    def _build_sidebar(self) -> ft.NavigationRail:
        """构建侧栏导航"""
        self._sidebar = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=180,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.INBOX,
                    selected_icon=ft.Icons.INBOX,
                    label="收件箱",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SEND,
                    selected_icon=ft.Icons.SEND,
                    label="已发送",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.WARNING_AMBER,
                    selected_icon=ft.Icons.WARNING,
                    label="告警",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.APPROVAL,
                    selected_icon=ft.Icons.APPROVAL,
                    label="审批",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ARTICLE,
                    selected_icon=ft.Icons.ARTICLE,
                    label="资讯",
                ),
            ],
            on_change=self._on_category_changed,
            bgcolor=ft.Colors.WHITE,
        )
        return self._sidebar

    def _build_content(self) -> ft.Container:
        """构建内容区（邮件列表 + 详情）"""
        self._mail_list = MailListView(on_select=self._on_mail_selected)
        self._mail_detail = MailDetailView()

        # 列表标题
        self._list_title = ft.Text("收件箱", size=16, weight=ft.FontWeight.W_600)
        self._list_count = ft.Text("(0)", size=14, color=ft.Colors.GREY_500)

        list_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                self._list_title,
                                self._list_count,
                                ft.Container(expand=True),
                            ],
                            spacing=8,
                        ),
                        padding=ft.Padding(left=16, top=12, right=16, bottom=12),
                        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_200)),
                        bgcolor=ft.Colors.WHITE,
                    ),
                    self._mail_list,
                ],
                spacing=0,
            ),
            expand=3,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border(right=ft.BorderSide(1, ft.Colors.GREY_200)),
        )

        detail_panel = ft.Container(
            content=self._mail_detail,
            expand=7,
            bgcolor=ft.Colors.WHITE,
        )

        return ft.Container(
            content=ft.Row(
                [list_panel, detail_panel],
                spacing=0,
                expand=True,
            ),
            expand=True,
            bgcolor=ft.Colors.GREY_50,
        )

    # ---- 事件处理 ----

    def _on_category_changed(self, e):
        """分类切换"""
        categories = ["收件箱", "已发送", "告警", "审批", "资讯"]
        idx = e.control.selected_index
        if 0 <= idx < len(categories):
            self._list_title.value = categories[idx]
            logger.info(f"切换到分类: {categories[idx]}")
            self.page.update()

    def _on_mail_selected(self, message_id: str):
        """邮件选中"""
        logger.info(f"选中邮件: {message_id}")
        if self._on_fetch:
            self._on_fetch("select", message_id)

    def _on_fetch_clicked(self, e):
        """拉取邮件按钮"""
        if self._fetching:
            return
        self._fetching = True
        self._fetch_btn.icon = ft.Icons.HOURGLASS_EMPTY
        self._fetch_btn.disabled = True
        self.page.update()
        logger.info("点击拉取邮件")
        if self._on_fetch:
            self._on_fetch("fetch", None)

    def _on_compose_clicked(self, e):
        """写邮件"""
        sb = ft.SnackBar(content=ft.Text("写邮件功能将在后续版本实现"))
        sb.open = True
        self.page.snack_bar = sb
        self.page.update()

    def _on_settings_clicked(self, e):
        """设置按钮"""
        if self._on_fetch:
            self._on_fetch("settings", None)

    # ---- 公共方法 ----

    def update_connection_status(self, connected: bool):
        """更新连接状态"""
        if connected:
            self._status_connection.value = "🟢 已连接"
            self._status_connection.color = ft.Colors.GREEN_600
        else:
            self._status_connection.value = "🔴 未连接"
            self._status_connection.color = ft.Colors.GREY_500
        self.page.update()

    def update_last_fetch_time(self, time_str: str):
        """更新上次拉取时间"""
        self._status_last_fetch.value = f"上次拉取: {time_str}"
        self.page.update()

    def update_pending_count(self, count: int):
        """更新待处理邮件数"""
        self._status_pending.value = f"待处理: {count}"
        self.page.update()

    def update_next_fetch_time(self, time_str: str):
        """更新下次拉取时间"""
        self._status_next.value = f"下次: {time_str}"
        self.page.update()

    def set_fetch_button_enabled(self, enabled: bool):
        """设置拉取按钮状态"""
        self._fetching = not enabled
        self._fetch_btn.disabled = not enabled
        self._fetch_btn.icon = ft.Icons.REFRESH if enabled else ft.Icons.HOURGLASS_EMPTY
        self.page.update()

    def set_mails(self, mails: list):
        """设置邮件列表"""
        self._mail_list.set_mails(mails)
        self._list_count.value = f"({len(mails)})"
        self.page.update()

    def show_mail_detail(self, mail):
        """显示邮件详情"""
        self._mail_detail.show_mail(mail)
        self._mail_list.mark_as_read(mail.message_id)
        self.page.update()

    @property
    def mail_list(self):
        return self._mail_list

    @property
    def mail_detail(self):
        return self._mail_detail

    @property
    def account_label(self):
        """兼容旧接口"""
        return None