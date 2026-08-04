"""主窗口 - Flet 实现（四栏布局 + 深浅双主题）

布局：Rail 导航栏(72) | 文件夹侧栏(260) | 邮件列表(380) | 邮件详情(自适应)
风格：简洁清新，文字为主，圆角化，无图标。
保持 main.py 调用的公共接口兼容。
"""

import flet as ft
from datetime import datetime

from src.core.logger import get_logger
from src.gui.theme import (
    Color, DarkColor, Radius, Font, LIGHT_THEME, DARK_THEME,
)
from src.gui.mail_list import MailListView
from src.gui.mail_detail import MailDetailView
from src.gui.folder_sidebar import FolderSidebar

logger = get_logger("gui.main")


class MailApp:
    """邮件助手应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._is_dark = False
        self._fetching = False
        self._fetch_worker = None
        self._on_fetch = None

        self._init_page()
        self._apply_theme()
        self._build_ui()

    # ---- 初始化 ----
    def _init_page(self):
        self.page.title = "邮件助手"
        self.page.padding = 0
        self.page.window.width = 1280
        self.page.window.height = 800
        self.page.window.min_width = 1000
        self.page.window.min_height = 640
        self.page.bgcolor = Color.BG_MAIN

    def _apply_theme(self):
        """应用当前主题"""
        c = DarkColor if self._is_dark else Color
        self.page.theme = LIGHT_THEME if not self._is_dark else DARK_THEME
        self.page.dark_theme = DARK_THEME
        self.page.theme_mode = ft.ThemeMode.DARK if self._is_dark else ft.ThemeMode.LIGHT
        self.page.bgcolor = c.BG_MAIN

    @property
    def _c(self):
        return DarkColor if self._is_dark else Color

    # ---- UI 构建 ----
    def _build_ui(self):
        c = self._c

        # 顶部应用栏（文字按钮，无图标）
        self.page.appbar = ft.AppBar(
            leading=ft.Container(
                content=ft.Text(
                    "邮件助手",
                    size=Font.PANEL_TITLE,
                    weight=ft.FontWeight.W_600,
                    color=c.TEXT_PRIMARY,
                ),
                padding=ft.Padding(left=16, top=0, right=8, bottom=0),
                alignment="center_left",
            ),
            leading_width=120,
            title=ft.Container(),
            center_title=False,
            bgcolor=c.BG_CARD,
            actions=[
                self._build_fetch_btn(),
                self._build_text_action("写邮件", self._on_compose_clicked),
                ft.VerticalDivider(width=1, color=c.BORDER),
                self._build_theme_toggle(),
                self._build_text_action("设置", self._on_settings_clicked, secondary=True),
            ],
        )

        # 四栏内容区
        rail = self._build_rail()
        folder_sidebar = self._build_folder_sidebar()
        list_panel = self._build_list_panel()
        detail_panel = self._build_detail_panel()

        content_row = ft.Row(
            [
                rail,
                ft.Container(width=1, bgcolor=c.BORDER),
                folder_sidebar,
                ft.Container(width=1, bgcolor=c.BORDER),
                list_panel,
                ft.Container(width=1, bgcolor=c.BORDER),
                detail_panel,
            ],
            spacing=0,
            expand=True,
        )

        # 底部状态栏（无 emoji）
        status_bar = self._build_status_bar()

        self.page.add(
            ft.Column(
                [content_row, status_bar],
                spacing=0,
                expand=True,
            )
        )

    def _build_text_action(self, text: str, on_click, secondary: bool = False) -> ft.Container:
        """顶部文字按钮（圆角）"""
        c = self._c
        color = c.TEXT_SECONDARY if secondary else c.PRIMARY
        return ft.Container(
            content=ft.Text(
                text,
                size=Font.BODY,
                color=color,
                weight=ft.FontWeight.W_500,
            ),
            on_click=on_click,
            padding=ft.Padding(left=14, top=7, right=14, bottom=7),
            border_radius=Radius.BUTTON,
            ink=True,
        )

    def _build_fetch_btn(self) -> ft.Container:
        """拉取邮件按钮"""
        c = self._c
        self._fetch_btn = ft.Container(
            content=ft.Text(
                "拉取邮件",
                size=Font.BODY,
                color=c.PRIMARY,
                weight=ft.FontWeight.W_500,
            ),
            on_click=self._on_fetch_clicked,
            padding=ft.Padding(left=14, top=7, right=14, bottom=7),
            border_radius=Radius.BUTTON,
            bgcolor=c.PRIMARY_CONTAINER,
            ink=True,
        )
        return self._fetch_btn

    def _build_theme_toggle(self) -> ft.Container:
        """主题切换按钮"""
        c = self._c
        self._theme_btn = ft.Container(
            content=ft.Text(
                "深色" if not self._is_dark else "浅色",
                size=Font.BODY,
                color=c.TEXT_SECONDARY,
                weight=ft.FontWeight.W_500,
            ),
            on_click=self._on_theme_toggle,
            padding=ft.Padding(left=14, top=7, right=14, bottom=7),
            border_radius=Radius.BUTTON,
            ink=True,
        )
        return self._theme_btn

    def _build_rail(self) -> ft.NavigationRail:
        """第一栏：导航 Rail（72px，文字标签，无图标）"""
        c = self._c
        self._sidebar = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=72,
            min_extended_width=72,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.INBOX_OUTLINED,
                    selected_icon=ft.Icons.INBOX,
                    label="收件箱",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SEND_OUTLINED,
                    selected_icon=ft.Icons.SEND,
                    label="已发送",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.WARNING_AMBER_OUTLINED,
                    selected_icon=ft.Icons.WARNING,
                    label="告警",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.APPROVAL_OUTLINED,
                    selected_icon=ft.Icons.APPROVAL,
                    label="审批",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.ARTICLE_OUTLINED,
                    selected_icon=ft.Icons.ARTICLE,
                    label="资讯",
                ),
            ],
            on_change=self._on_category_changed,
            bgcolor=c.BG_RAIL,
        )
        return self._sidebar

    def _build_folder_sidebar(self) -> ft.Container:
        """第二栏：文件夹侧栏（260px）"""
        c = self._c
        self._folder_sidebar = FolderSidebar(
            on_select=self._on_folder_selected,
            is_dark=self._is_dark,
        )
        return ft.Container(
            content=self._folder_sidebar,
            width=260,
            bgcolor=c.BG_SIDEBAR,
            expand=False,
        )

    def _build_list_panel(self) -> ft.Container:
        """第三栏：邮件列表（380px）"""
        c = self._c
        self._mail_list = MailListView(
            on_select=self._on_mail_selected,
            is_dark=self._is_dark,
        )

        # 列表标题 + 计数
        self._list_title = ft.Text(
            "收件箱",
            size=Font.PANEL_TITLE,
            weight=ft.FontWeight.W_600,
            color=c.TEXT_PRIMARY,
        )
        self._list_count = ft.Text(
            "(0)",
            size=Font.AUX,
            color=c.TEXT_SECONDARY,
        )

        header = ft.Container(
            content=ft.Row(
                [
                    self._list_title,
                    self._list_count,
                    ft.Container(expand=True),
                ],
                spacing=8,
            ),
            padding=ft.Padding(left=16, top=14, right=16, bottom=12),
            border=ft.Border.only(bottom=ft.border.BorderSide(1, c.BORDER)),
            bgcolor=c.BG_CARD,
        )

        return ft.Container(
            content=ft.Column(
                [header, self._mail_list],
                spacing=0,
            ),
            width=380,
            bgcolor=c.BG_MAIN,
            expand=False,
        )

    def _build_detail_panel(self) -> ft.Container:
        """第四栏：邮件详情（自适应）"""
        c = self._c
        self._mail_detail = MailDetailView(is_dark=self._is_dark)
        return ft.Container(
            content=self._mail_detail,
            expand=True,
            bgcolor=c.BG_CARD,
        )

    def _build_status_bar(self) -> ft.Container:
        """底部状态栏（无 emoji，用文字 + 色点）"""
        c = self._c
        self._status_dot = ft.Container(
            width=8,
            height=8,
            border_radius=4,
            bgcolor=c.TEXT_SECONDARY,
        )
        self._status_connection = ft.Text("未连接", size=Font.AUX, color=c.TEXT_SECONDARY)
        self._status_last_fetch = ft.Text("上次拉取: --", size=Font.AUX, color=c.TEXT_SECONDARY)
        self._status_pending = ft.Text("待处理: 0", size=Font.AUX, color=c.TEXT_SECONDARY)
        self._status_next = ft.Text("下次: --", size=Font.AUX, color=c.TEXT_SECONDARY)

        sep = ft.Text("|", size=Font.AUX, color=c.BORDER)

        return ft.Container(
            content=ft.Row(
                [
                    self._status_dot,
                    self._status_connection,
                    sep,
                    self._status_last_fetch,
                    sep,
                    self._status_pending,
                    sep,
                    self._status_next,
                ],
                spacing=12,
            ),
            padding=ft.Padding(left=16, top=7, right=16, bottom=7),
            bgcolor=c.BG_MAIN,
            border=ft.Border.only(top=ft.border.BorderSide(1, c.BORDER)),
        )

    # ---- 事件处理 ----
    def _on_category_changed(self, e):
        categories = ["收件箱", "已发送", "告警", "审批", "资讯"]
        idx = e.control.selected_index
        if 0 <= idx < len(categories):
            self._list_title.value = categories[idx]
            logger.info(f"切换到分类: {categories[idx]}")
            self.page.update()

    def _on_folder_selected(self, folder_key: str):
        """文件夹/分类切换"""
        name_map = {
            "inbox": "收件箱",
            "starred": "星标邮件",
            "sent": "已发送",
            "drafts": "草稿",
            "archive": "归档",
            "trash": "已删除",
            "work": "工作",
            "approval": "审批",
            "alert": "告警",
            "info": "资讯",
        }
        self._list_title.value = name_map.get(folder_key, folder_key)
        self.page.update()

    def _on_mail_selected(self, message_id: str):
        logger.info(f"选中邮件: {message_id}")
        if self._on_fetch:
            self._on_fetch("select", message_id)

    def _on_fetch_clicked(self, e):
        if self._fetching:
            return
        self._fetching = True
        c = self._c
        self._fetch_btn.content.value = "拉取中..."
        self._fetch_btn.bgcolor = c.BG_HOVER
        self.page.update()
        logger.info("点击拉取邮件")
        if self._on_fetch:
            self._on_fetch("fetch", None)

    def _on_compose_clicked(self, e):
        """写邮件"""
        sb = ft.SnackBar(content=ft.Text("写邮件功能将在后续版本实现"), open=True)
        self.page.overlay.append(sb)
        self.page.update()

    def _on_settings_clicked(self, e):
        if self._on_fetch:
            self._on_fetch("settings", None)

    def _on_theme_toggle(self, e):
        """切换深浅主题"""
        self._is_dark = not self._is_dark
        self._apply_theme()
        # 刷新按钮文字
        self._theme_btn.content.value = "浅色" if self._is_dark else "深色"
        # 通知子组件刷新配色
        self._mail_list.update_theme(self._is_dark)
        self._mail_detail.update_theme(self._is_dark)
        self._folder_sidebar.update_theme(self._is_dark)
        # 重建整体 UI 以应用配色
        self.page.clean()
        self._build_ui()
        self.page.update()
        logger.info(f"切换主题: {'深色' if self._is_dark else '浅色'}")

    # ---- 公共方法（保持 main.py 兼容） ----
    def update_connection_status(self, connected: bool):
        c = self._c
        if connected:
            self._status_connection.value = "已连接"
            self._status_dot.bgcolor = c.SUCCESS
        else:
            self._status_connection.value = "未连接"
            self._status_dot.bgcolor = c.ERROR
        self.page.update()

    def update_last_fetch_time(self, time_str: str):
        self._status_last_fetch.value = f"上次拉取: {time_str}"
        self.page.update()

    def update_pending_count(self, count: int):
        self._status_pending.value = f"待处理: {count}"
        # 同步更新收件箱未读数
        self._folder_sidebar.set_unread_count("inbox", count)
        self.page.update()

    def update_next_fetch_time(self, time_str: str):
        self._status_next.value = f"下次: {time_str}"
        self.page.update()

    def set_fetch_button_enabled(self, enabled: bool):
        self._fetching = not enabled
        c = self._c
        if enabled:
            self._fetch_btn.content.value = "拉取邮件"
            self._fetch_btn.bgcolor = c.PRIMARY_CONTAINER
        else:
            self._fetch_btn.content.value = "拉取中..."
            self._fetch_btn.bgcolor = c.BG_HOVER
        self.page.update()

    def set_mails(self, mails: list):
        self._mail_list.set_mails(mails)
        self._list_count.value = f"({len(mails)})"
        self.page.update()

    def show_mail_detail(self, mail):
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
        return None
