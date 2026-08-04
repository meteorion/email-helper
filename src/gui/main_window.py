"""主窗口 - Flet 实现（四栏布局 + 深浅双主题）

严格对齐 email_desktop_ui_design.html 设计稿：
  - 第一栏：导航 Rail（72px，深蓝背景，Logo + 垂直文字导航 + 用户头像）
  - 第二栏：文件夹侧栏（260px，浅灰背景，撰写按钮 + 文件夹 + 标签 + 存储）
  - 第三栏：邮件列表（380px，搜索框 + 筛选Tab + 邮件项）
  - 第四栏：邮件详情（自适应，工具栏 + 大标题 + 发件人 + 正文 + 附件 + 回复区）

保持 main.py 调用的公共接口兼容。
"""

import flet as ft

from src.core.logger import get_logger
from src.gui.theme import (
    Color, DarkColor, Radius, Font,
    LIGHT_THEME, DARK_THEME,
)
from src.gui.mail_list import MailListView
from src.gui.mail_detail import MailDetailView
from src.gui.folder_sidebar import FolderSidebar

logger = get_logger("gui.main")


# Rail 导航项：(key, 标签, 图标)
RAIL_ITEMS = [
    ("inbox", "邮件", ft.Icons.INBOX),
    ("sent", "已发", ft.Icons.SEND_OUTLINED),
    ("alert", "告警", ft.Icons.WARNING_AMBER_OUTLINED),
    ("approval", "审批", ft.Icons.APPROVAL_OUTLINED),
    ("info", "资讯", ft.Icons.ARTICLE_OUTLINED),
]


class MailApp:
    """邮件助手应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._is_dark = False
        self._fetching = False
        self._fetch_worker = None
        self._on_fetch = None
        self._rail_selected = "inbox"

        # 后续注入的服务引用（main.py 会赋值）
        self._scheduler = None
        self._imap_client = None
        self._smtp_client = None
        self._mail_store = None
        self._mail_repo = None
        self._classifier = None
        self._workflow_engine = None
        self._notification_engine = None

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
        c = self._c
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

        # 四栏内容区（无 AppBar，纯四栏布局对齐设计稿）
        rail = self._build_rail()
        folder_sidebar = self._build_folder_sidebar()
        list_panel = self._build_list_panel()
        detail_panel = self._build_detail_panel()

        content_row = ft.Row(
            [
                rail,
                folder_sidebar,
                list_panel,
                detail_panel,
            ],
            spacing=0,
            expand=True,
        )

        # 底部状态栏
        status_bar = self._build_status_bar()

        self.page.add(
            ft.Column(
                [content_row, status_bar],
                spacing=0,
                expand=True,
            )
        )

    # ===== 第一栏：导航 Rail（72px，深蓝） =====
    def _build_rail(self) -> ft.Container:
        """导航 Rail：Logo + 垂直文字导航 + 底部头像"""
        c = self._c

        # Logo 方块（蓝色渐变，文字 "E"）
        logo = ft.Container(
            content=ft.Text(
                "E",
                size=20,
                weight=ft.FontWeight.W_700,
                color=c.TEXT_ON_PRIMARY,
            ),
            width=40,
            height=40,
            border_radius=10,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=c.LOGO_GRADIENT,
            ),
        )

        # 导航项（垂直文字）
        nav_items = []
        for key, label, _icon in RAIL_ITEMS:
            nav_items.append(self._build_rail_item(key, label))

        # 底部头像（圆形渐变，文字 "W"）
        avatar = ft.Container(
            content=ft.Text(
                "W",
                size=14,
                weight=ft.FontWeight.W_600,
                color=c.TEXT_ON_PRIMARY,
            ),
            width=36,
            height=36,
            border_radius=50,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=c.AVATAR_GRADIENT_1,
            ),
            tooltip="王明",
        )

        # 设置项
        settings_item = self._build_rail_item("_settings", "设置")

        self._rail = ft.Column(
            [
                logo,
                ft.Container(height=16),
                *nav_items,
                ft.Container(expand=True),
                settings_item,
                ft.Container(height=8),
                avatar,
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        return ft.Container(
            content=self._rail,
            width=72,
            bgcolor=c.BG_RAIL,
            padding=ft.Padding(0, 16, 0, 16),
            expand=False,
        )

    def _build_rail_item(self, key: str, label: str) -> ft.Container:
        """单个 Rail 导航项（垂直文字 + 选中竖条）"""
        c = self._c
        is_selected = (key == self._rail_selected)
        text_color = c.TEXT_RAIL_SELECTED if is_selected else c.TEXT_RAIL
        bgcolor = c.BG_RAIL_SELECTED if is_selected else None

        # 垂直文字：每个字一行
        vertical_text = "\n".join(list(label))

        # 选中态左侧竖条
        indicator = ft.Container(
            width=3,
            height=24,
            bgcolor=c.PRIMARY_400,
            border_radius=ft.BorderRadius(top_left=0, top_right=3, bottom_left=0, bottom_right=3),
            visible=is_selected,
        )

        return ft.Container(
            content=ft.Stack(
                [
                    # 选中竖条（左侧偏外）
                    ft.Container(
                        content=indicator,
                        left=-16,
                        top=12,
                    ),
                    # 文字（居中）
                    ft.Container(
                        content=ft.Text(
                            vertical_text,
                            size=11,
                            color=text_color,
                            weight=ft.FontWeight.W_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        alignment=ft.Alignment(0, 0),
                        padding=ft.Padding(4, 0, 4, 0),
                    ),
                ],
            ),
            width=48,
            height=48,
            border_radius=12,
            bgcolor=bgcolor,
            data=key,
            on_click=self._on_rail_clicked,
            ink=True,
        )

    def _on_rail_clicked(self, e: ft.ControlEvent):
        key = e.control.data
        if not key:
            return
        if key == "_settings":
            if self._on_fetch:
                self._on_fetch("settings", None)
            return
        self._rail_selected = key
        # 触发分类切换
        self._on_category_changed(key)
        # 重建 Rail
        self.page.clean()
        self._build_ui()
        self.page.update()
        logger.info(f"Rail 切换到: {key}")

    def _on_category_changed(self, key: str):
        categories = {
            "inbox": "收件箱",
            "sent": "已发送",
            "alert": "告警",
            "approval": "审批",
            "info": "资讯",
        }
        name = categories.get(key, key)
        if hasattr(self, "_list_title"):
            self._list_title.value = name
        logger.info(f"切换到分类: {name}")

    # ===== 第二栏：文件夹侧栏 =====
    def _build_folder_sidebar(self) -> ft.Container:
        c = self._c
        self._folder_sidebar = FolderSidebar(
            on_select=self._on_folder_selected,
            on_compose=self._on_compose_clicked,
            is_dark=self._is_dark,
        )
        return ft.Container(
            content=self._folder_sidebar,
            width=260,
            bgcolor=c.BG_SIDEBAR,
            expand=False,
        )

    # ===== 第三栏：邮件列表 =====
    def _build_list_panel(self) -> ft.Container:
        c = self._c
        self._mail_list = MailListView(
            on_select=self._on_mail_selected,
            on_fetch=self._on_fetch_clicked,
            is_dark=self._is_dark,
        )
        return ft.Container(
            content=self._mail_list,
            width=380,
            bgcolor=c.BG_MAIN,
            expand=False,
        )

    # ===== 第四栏：邮件详情 =====
    def _build_detail_panel(self) -> ft.Container:
        c = self._c
        self._mail_detail = MailDetailView(is_dark=self._is_dark)
        return ft.Container(
            content=self._mail_detail,
            expand=True,
            bgcolor=c.BG_MAIN,
        )

    # ===== 底部状态栏 =====
    def _build_status_bar(self) -> ft.Container:
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

        # 主题切换按钮（右侧）
        self._theme_btn = ft.Container(
            content=ft.Text(
                "深色" if not self._is_dark else "浅色",
                size=Font.AUX,
                color=c.TEXT_SECONDARY,
            ),
            on_click=self._on_theme_toggle,
            padding=ft.Padding(10, 4, 10, 4),
            border_radius=Radius.BUTTON,
            ink=True,
        )

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
                    ft.Container(expand=True),
                    self._theme_btn,
                ],
                spacing=12,
            ),
            padding=ft.Padding(16, 7, 16, 7),
            bgcolor=c.BG_MAIN,
            border=ft.Border(top=ft.border.BorderSide(1, c.BORDER)),
        )

    # ---- 事件处理 ----
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
            "important": "重要",
            "attachments": "带附件",
            "spam": "垃圾箱",
        }
        if hasattr(self, "_mail_list"):
            self._mail_list.set_title(name_map.get(folder_key, folder_key))
        self.page.update()

    def _on_mail_selected(self, message_id: str):
        logger.info(f"选中邮件: {message_id}")
        if self._on_fetch:
            self._on_fetch("select", message_id)

    def _on_fetch_clicked(self, e=None):
        if self._fetching:
            return
        self._fetching = True
        if hasattr(self, "_mail_list"):
            self._mail_list.set_fetching(True)
        self.page.update()
        logger.info("点击拉取邮件")
        if self._on_fetch:
            self._on_fetch("fetch", None)

    def _on_compose_clicked(self, e=None):
        """写邮件"""
        sb = ft.SnackBar(content=ft.Text("写邮件功能将在后续版本实现"), open=True)
        self.page.overlay.append(sb)
        self.page.update()

    def _on_theme_toggle(self, e):
        """切换深浅主题"""
        self._is_dark = not self._is_dark
        self._apply_theme()
        # 重建整体 UI 以应用配色
        self.page.clean()
        self._build_ui()
        self.page.update()
        logger.info(f"切换主题: {'深色' if self._is_dark else '浅色'}")

    # ---- 公共方法（保持 main.py 兼容） ----
    def update_connection_status(self, connected: bool):
        c = self._c
        if not hasattr(self, "_status_dot"):
            return
        if connected:
            self._status_connection.value = "已连接"
            self._status_dot.bgcolor = c.SUCCESS
        else:
            self._status_connection.value = "未连接"
            self._status_dot.bgcolor = c.ERROR
        self.page.update()

    def update_last_fetch_time(self, time_str: str):
        if hasattr(self, "_status_last_fetch"):
            self._status_last_fetch.value = f"上次拉取: {time_str}"
            self.page.update()

    def update_pending_count(self, count: int):
        if hasattr(self, "_status_pending"):
            self._status_pending.value = f"待处理: {count}"
        # 同步更新收件箱未读数
        if hasattr(self, "_folder_sidebar"):
            self._folder_sidebar.set_unread_count("inbox", count)
        self.page.update()

    def update_next_fetch_time(self, time_str: str):
        if hasattr(self, "_status_next"):
            self._status_next.value = f"下次: {time_str}"
            self.page.update()

    def set_fetch_button_enabled(self, enabled: bool):
        self._fetching = not enabled
        if hasattr(self, "_mail_list"):
            self._mail_list.set_fetching(not enabled)
        self.page.update()

    def set_mails(self, mails: list):
        self._mail_list.set_mails(mails)
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
