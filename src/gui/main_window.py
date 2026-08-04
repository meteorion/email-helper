"""主窗口 - Flet 实现（四栏布局 + 深浅双主题）

严格对齐 email_desktop_ui_design.html 设计稿：
  - 第一栏：自定义导航侧栏（160px，深蓝背景，Logo + 横向文字导航 + 底部用户头像 + 设置）
  - 第二栏：文件夹侧栏（220px，浅灰背景，撰写按钮 + 文件夹 + 标签）
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
from src.gui.settings_page import SettingsPage
from src.gui.contacts_page import ContactsPage
from src.gui.tasks_page import TasksPage
from src.gui.demo_data import build_demo_mails, DEMO_FOLDER_COUNTS

logger = get_logger("gui.main")


# Rail 导航项：(key, 标签) — 4 个一级模块：邮件 / 联系人 / 任务 / 设置
RAIL_ITEMS = [
    ("mail", "邮件"),
    ("contacts", "联系人"),
    ("tasks", "任务"),
]


class MailApp:
    """邮件助手应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._is_dark = False
        self._fetching = False
        self._fetch_worker = None
        self._on_fetch = None
        self._rail_selected = "mail"
        self._in_settings = False
        self._settings_page = None
        self._contacts_page = None
        self._tasks_page = None

        # 后续注入的服务引用（main.py 会赋值）
        self._scheduler = None
        self._imap_client = None
        self._smtp_client = None
        self._mail_store = None
        self._mail_repo = None
        self._classifier = None
        self._workflow_engine = None
        self._notification_engine = None

        # 状态栏持久化（重建 UI 时恢复）
        self._connected = False
        self._last_fetch_str = "--"
        self._pending_count = 0
        self._next_fetch_str = "--"

        # 真实邮件数据加载标志（main.py 注入真实邮件后置 True，避免示例数据覆盖）
        self._real_mails_loaded = False
        self._current_mails: list = []   # 缓存最近一次 set_mails 的数据，供 UI 重建后恢复

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

        if self._real_mails_loaded:
            # UI 重建后用缓存的真实邮件恢复列表（返回设置页/主题切换等场景）
            if self._current_mails:
                self._mail_list.set_mails(self._current_mails)
        else:
            # 首次启动且尚未拉取真实邮件时，填充高保真原型示例数据
            self._load_demo_data()

    # ---- 高保真原型示例数据 ----
    def _load_demo_data(self):
        """加载与设计稿主界面一致的示例邮件、文件夹徽章，并默认选中首封展示详情。

        当 main.py 后续注入真实邮件时会通过 set_mails() 覆盖本数据。
        """
        mails = build_demo_mails()
        self._mail_list.set_mails(mails)

        # 文件夹未读徽章（对齐设计稿）
        for folder_key, count in DEMO_FOLDER_COUNTS.items():
            self._folder_sidebar.set_unread_count(folder_key, count)

        # 默认选中首封并展示详情
        first = mails[0]
        self._mail_list._selected_id = first.message_id
        self._mail_list._refresh_list()
        self._mail_detail.show_mail(first)

        try:
            self.page.update()
        except Exception as e:
            logger.warning(f"示例数据加载后 page.update 失败: {e}")

    # ===== 第一栏：自定义导航侧栏（160px，深蓝，图标+横向文字） =====
    # 图标使用 Flet 内置 Material Icons
    _RAIL_ICONS = {
        "mail": ft.Icons.MAIL_OUTLINE,
        "contacts": ft.Icons.CONTACTS_OUTLINED,
        "tasks": ft.Icons.CHECKLIST,
        "_settings": ft.Icons.SETTINGS_OUTLINED,
    }

    def _build_rail(self) -> ft.Container:
        """自定义宽侧栏：Logo + 图标+横向文字导航 + 底部设置（无头像）"""
        c = self._c

        # Logo 渐变背景条（居中「助手」文字，对齐 HTML .rail-logo）
        logo = ft.Container(
            content=ft.Text(
                "助手",
                size=14,
                weight=ft.FontWeight.W_700,
                color=c.TEXT_ON_PRIMARY,
            ),
            width=140,
            height=40,
            border_radius=10,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=c.LOGO_GRADIENT,
            ),
        )

        # 导航项（图标 + 横向文字）
        nav_items = []
        for key, label in RAIL_ITEMS:
            nav_items.append(self._build_rail_item(key, label))

        # 设置项
        settings_item = self._build_rail_item("_settings", "设置")

        self._rail = ft.Column(
            [
                logo,
                ft.Container(height=16),
                *nav_items,
                ft.Container(expand=True),
                settings_item,
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        )

        return ft.Container(
            content=self._rail,
            width=160,
            bgcolor=c.BG_RAIL,
            padding=ft.Padding(10, 16, 10, 16),
            expand=False,
        )

    def _build_rail_item(self, key: str, label: str) -> ft.Container:
        """单个导航项：图标 + 横向文字 + 选中竖条（左侧圆角指示器）"""
        c = self._c
        is_selected = (key == self._rail_selected)
        text_color = c.TEXT_RAIL_SELECTED if is_selected else c.TEXT_RAIL
        bgcolor = c.BG_RAIL_SELECTED if is_selected else None
        icon_color = c.TEXT_RAIL_SELECTED if is_selected else c.TEXT_RAIL

        # 选中态左侧竖条（高度 22px，对齐 HTML .rail-item.active::before）
        indicator = ft.Container(
            width=3,
            height=22,
            bgcolor=c.PRIMARY_400,
            border_radius=ft.BorderRadius(top_left=0, top_right=3, bottom_left=0, bottom_right=3),
            visible=is_selected,
        )

        icon_name = self._RAIL_ICONS.get(key, ft.Icons.CIRCLE)

        return ft.Container(
            content=ft.Stack(
                [
                    # 选中竖条（左侧）
                    ft.Container(
                        content=indicator,
                        left=0,
                        top=9,
                    ),
                    # 图标 + 文字（横向，左对齐）
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(icon_name, size=18, color=icon_color),
                                ft.Text(
                                    label,
                                    size=13,
                                    color=text_color,
                                    weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_500,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        left=12,
                        top=0,
                        height=40,
                        alignment=ft.Alignment(0, 0),
                    ),
                ],
            ),
            width=140,
            height=40,
            border_radius=10,
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
            self._show_settings()
            return
        # 如果当前在设置页面，先切回
        if self._in_settings:
            self._in_settings = False
        self._rail_selected = key
        # 根据模块切换页面
        if key == "contacts":
            self._show_contacts()
        elif key == "tasks":
            self._show_tasks()
        else:
            # mail / stats 走原有四栏布局
            self._on_category_changed(key)
            self.page.clean()
            self._build_ui()
            self.page.update()
        logger.info(f"Rail 切换到: {key}")

    def _show_settings(self):
        """切换到设置页面（保留已有实例状态）"""
        self._in_settings = True
        c = self._c

        # 首次创建，后续重建复用已有实例
        if not self._settings_page:
            self._settings_page = SettingsPage(
                page=self.page,
                is_dark=self._is_dark,
                on_back=self._back_to_mail,
                on_theme_change=self._on_settings_theme_change,
                on_open_account=self._goto_account_settings,
                on_rebuild=self._show_settings,
            )
        else:
            self._settings_page._is_dark = self._is_dark

        rail = self._build_rail()
        settings_view = self._settings_page.build()

        content_row = ft.Row(
            [rail, settings_view],
            spacing=0,
            expand=True,
        )
        status_bar = self._build_status_bar()

        self.page.clean()
        self.page.add(
            ft.Column(
                [content_row, status_bar],
                spacing=0,
                expand=True,
            )
        )
        self.page.update()
        logger.info(f"设置页面: tab={self._settings_page._selected_tab}")

    def _show_contacts(self):
        """切换到联系人页面"""
        if not self._contacts_page:
            self._contacts_page = ContactsPage(is_dark=self._is_dark)
        else:
            self._contacts_page.update_theme(self._is_dark)

        rail = self._build_rail()
        content_row = ft.Row(
            [rail, self._contacts_page],
            spacing=0,
            expand=True,
        )
        status_bar = self._build_status_bar()

        self.page.clean()
        self.page.add(
            ft.Column(
                [content_row, status_bar],
                spacing=0,
                expand=True,
            )
        )
        self.page.update()
        logger.info("切换到联系人页面")

    def _show_tasks(self):
        """切换到任务页面"""
        if not self._tasks_page:
            self._tasks_page = TasksPage(is_dark=self._is_dark)
        else:
            self._tasks_page.update_theme(self._is_dark)

        rail = self._build_rail()
        content_row = ft.Row(
            [rail, self._tasks_page],
            spacing=0,
            expand=True,
        )
        status_bar = self._build_status_bar()

        self.page.clean()
        self.page.add(
            ft.Column(
                [content_row, status_bar],
                spacing=0,
                expand=True,
            )
        )
        self.page.update()
        logger.info("切换到任务页面")

    def _back_to_mail(self):
        """从设置页面返回邮件视图"""
        self._in_settings = False
        self._settings_page = None
        self.page.clean()
        self._build_ui()
        self.page.update()
        logger.info("返回邮件视图")

    def _on_settings_theme_change(self, is_dark: bool):
        """设置页面中切换主题"""
        self._is_dark = is_dark
        self._apply_theme()
        # 重建设置页面
        if self._in_settings and self._settings_page:
            self._settings_page.update_theme(is_dark)
            self._show_settings()

    def _goto_account_settings(self):
        """进入设置页并定位到账户管理面板"""
        if self._settings_page:
            self._settings_page._selected_tab = "account"
        self._show_settings()
        logger.info("跳转到账户管理面板")

    def _on_category_changed(self, key: str):
        categories = {
            "mail": "邮件",
            "contacts": "联系人",
            "tasks": "任务",
        }
        name = categories.get(key, key)
        if hasattr(self, "_list_title"):
            self._list_title.value = name
        logger.info(f"切换到模块: {name}")

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
            width=220,
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
            bgcolor=c.SUCCESS if self._connected else c.TEXT_SECONDARY,
        )
        self._status_connection = ft.Text(
            "已连接" if self._connected else "未连接",
            size=Font.AUX,
            color=c.TEXT_PRIMARY if self._connected else c.TEXT_SECONDARY,
        )
        self._status_last_fetch = ft.Text(
            f"上次拉取: {self._last_fetch_str}", size=Font.AUX, color=c.TEXT_SECONDARY,
        )
        self._status_pending = ft.Text(
            f"待处理: {self._pending_count}", size=Font.AUX, color=c.TEXT_SECONDARY,
        )
        self._status_next = ft.Text(
            f"下次: {self._next_fetch_str}", size=Font.AUX, color=c.TEXT_SECONDARY,
        )

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
            "sent": "已发送",
            "drafts": "草稿",
            "archive": "归档",
            "work": "工作",
            "approval": "审批",
            "alert": "告警",
            "info": "资讯",
        }
        if hasattr(self, "_mail_list"):
            self._mail_list.set_title(name_map.get(folder_key, folder_key))
        self.page.update()

    def get_mail_by_id(self, message_id: str):
        """从当前列表查找 MailData，供外部回调使用"""
        if hasattr(self, "_mail_list"):
            for m in self._mail_list._mails:
                if m.message_id == message_id:
                    return m
        return None

    def _on_mail_selected(self, message_id: str):
        logger.info(f"选中邮件: {message_id}")
        mail = self.get_mail_by_id(message_id)
        if mail:
            was_unread = not mail.is_read
            self.show_mail_detail(mail)
            # 后台写 DB 已读标记（需要邮件服务就绪）
            if was_unread and self._on_fetch:
                self._on_fetch("mark_read", message_id)
        elif self._on_fetch:
            # 列表中找不到时降级走旧逻辑
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
        self._connected = connected
        if not hasattr(self, "_status_dot"):
            return
        if connected:
            self._status_connection.value = "已连接"
            self._status_connection.color = c.TEXT_PRIMARY
            self._status_dot.bgcolor = c.SUCCESS
        else:
            self._status_connection.value = "未连接"
            self._status_connection.color = c.TEXT_SECONDARY
            self._status_dot.bgcolor = c.ERROR
        self.page.update()

    def update_last_fetch_time(self, time_str: str):
        self._last_fetch_str = time_str
        if hasattr(self, "_status_last_fetch"):
            self._status_last_fetch.value = f"上次拉取: {time_str}"
            self.page.update()

    def update_pending_count(self, count: int):
        self._pending_count = count
        if hasattr(self, "_status_pending"):
            self._status_pending.value = f"待处理: {count}"
        if hasattr(self, "_folder_sidebar"):
            self._folder_sidebar.set_unread_count("inbox", count)
        self.page.update()

    def update_next_fetch_time(self, time_str: str):
        self._next_fetch_str = time_str
        if hasattr(self, "_status_next"):
            self._status_next.value = f"下次: {time_str}"
            self.page.update()

    def set_fetch_button_enabled(self, enabled: bool):
        self._fetching = not enabled
        if hasattr(self, "_mail_list"):
            self._mail_list.set_fetching(not enabled)
        self.page.update()

    def set_mails(self, mails: list):
        self._real_mails_loaded = True
        self._current_mails = list(mails)
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
