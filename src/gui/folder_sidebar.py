"""文件夹侧栏组件 - Flet 实现（第二栏 260px）

简洁清新风格，文字为主，无图标。
显示文件夹列表 + 分类筛选，支持未读计数徽章。
"""

import flet as ft

from src.gui.theme import Color, DarkColor, Radius, Font
from src.core.logger import get_logger

logger = get_logger("gui.folder_sidebar")


# 文件夹定义：(key, 名称, 默认未读数)
DEFAULT_FOLDERS = [
    ("inbox", "收件箱", 0),
    ("starred", "星标邮件", 0),
    ("sent", "已发送", 0),
    ("drafts", "草稿", 0),
    ("archive", "归档", 0),
    ("trash", "已删除", 0),
]

# 分类筛选分组
CATEGORY_GROUPS = [
    ("分类", [
        ("work", "工作"),
        ("approval", "审批"),
        ("alert", "告警"),
        ("info", "资讯"),
    ]),
]


@ft.control("Column", init=False)
class FolderSidebar(ft.Column):
    """文件夹侧栏视图"""

    def __init__(self, on_select=None, is_dark: bool = False):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._on_select = on_select
        self._is_dark = is_dark
        self._selected = "inbox"
        self._folder_items: dict[str, ft.Container] = {}
        self._count_badges: dict[str, ft.Text] = {}
        self._counts: dict[str, int] = {}

        self._build()

    # ---- 颜色辅助 ----
    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    # ---- 构建 UI ----
    def _build(self):
        c = self._colors
        self.controls = [
            # 顶部标题区
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text(
                            "邮件文件夹",
                            size=Font.PANEL_TITLE,
                            weight=ft.FontWeight.W_600,
                            color=c.TEXT_PRIMARY,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.Padding(left=16, top=14, right=16, bottom=10),
            ),
            # 文件夹列表
            self._build_folder_list(),
            # 分割线
            ft.Container(
                height=1,
                bgcolor=c.BORDER_LIGHT,
                margin=ft.Margin(left=16, top=8, right=16, bottom=8),
            ),
            # 分类筛选
            self._build_category_section(),
            # 弹性占位
            ft.Container(expand=True),
        ]

    def _build_folder_list(self) -> ft.Column:
        c = self._colors
        col = ft.Column(spacing=2, expand=False)

        for key, name, _ in DEFAULT_FOLDERS:
            badge = ft.Text(
                "",
                size=Font.SMALL,
                color=c.TEXT_ON_PRIMARY,
                visible=False,
            )
            self._count_badges[key] = badge

            item = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(
                            name,
                            size=Font.BODY,
                            color=c.TEXT_PRIMARY,
                        ),
                        ft.Container(expand=True),
                        ft.Container(
                            content=badge,
                            bgcolor=c.PRIMARY,
                            border_radius=Radius.PILL,
                            padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                            visible=False,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                data=key,
                on_click=self._on_folder_click,
                padding=ft.Padding(left=16, top=8, right=12, bottom=8),
                border_radius=Radius.LIST_ITEM,
                ink=True,
            )
            self._folder_items[key] = item
            col.controls.append(item)

        # 包一层带内边距的容器
        return ft.Container(
            content=col,
            padding=ft.Padding(left=8, top=4, right=8, bottom=4),
        )

    def _build_category_section(self) -> ft.Container:
        c = self._colors
        col = ft.Column(spacing=2)

        for group_title, items in CATEGORY_GROUPS:
            col.controls.append(
                ft.Container(
                    content=ft.Text(
                        group_title,
                        size=Font.AUX,
                        color=c.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600,
                    ),
                    padding=ft.Padding(left=16, top=4, right=16, bottom=6),
                )
            )
            for key, name in items:
                item = ft.Container(
                    content=ft.Text(
                        name,
                        size=Font.BODY,
                        color=c.TEXT_PRIMARY,
                    ),
                    data=key,
                    on_click=self._on_category_click,
                    padding=ft.Padding(left=24, top=7, right=16, bottom=7),
                    border_radius=Radius.LIST_ITEM,
                    ink=True,
                )
                col.controls.append(item)

        return ft.Container(content=col, padding=ft.Padding(left=0, top=0, right=8, bottom=4))

    # ---- 事件处理 ----
    def _on_folder_click(self, e: ft.ControlEvent):
        key = e.control.data
        if not key:
            return
        self._select(key)

    def _on_category_click(self, e: ft.ControlEvent):
        key = e.control.data
        if not key:
            return
        # 分类点击：高亮 + 回调
        self._clear_selection()
        self._selected = key
        if e.control:
            e.control.bgcolor = self._colors.BG_SELECTED
        self._refresh_styles()
        logger.info(f"选中分类: {key}")
        if self._on_select:
            self._on_select(key)
        self.update()

    def _select(self, key: str):
        self._clear_selection()
        self._selected = key
        self._refresh_styles()
        logger.info(f"选中文件夹: {key}")
        if self._on_select:
            self._on_select(key)
        self.update()

    def _clear_selection(self):
        for item in self._folder_items.values():
            item.bgcolor = None

    def _refresh_styles(self):
        c = self._colors
        for key, item in self._folder_items.items():
            if key == self._selected:
                item.bgcolor = c.BG_SELECTED
            else:
                item.bgcolor = None

    # ---- 公共方法 ----
    def select(self, key: str):
        """选中某个文件夹"""
        self._select(key)

    def update_theme(self, is_dark: bool):
        """切换主题时刷新配色"""
        self._is_dark = is_dark
        # 重建以应用新配色
        self._build()
        self._refresh_styles()
        # 更新徽章配色
        c = self._colors
        for key, badge in self._count_badges.items():
            badge.color = c.TEXT_ON_PRIMARY
        self.update()

    def set_unread_count(self, folder_key: str, count: int):
        """设置文件夹未读数"""
        self._counts[folder_key] = count
        if folder_key not in self._count_badges:
            return
        badge = self._count_badges[folder_key]
        if count > 0:
            badge.value = str(count)
            badge.visible = True
            badge.parent.visible = True if badge.parent else True
        else:
            badge.value = ""
            badge.visible = False
        self.update()
