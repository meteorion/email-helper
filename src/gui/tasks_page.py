"""任务页面 - Flet 实现

功能：
  - 左栏：筛选Tab + 任务列表（复选框+优先级色条+标签）
  - 右栏：任务详情（标题+描述+信息卡片+操作按钮）
"""

from datetime import datetime, timedelta

import flet as ft

from src.gui.theme import Color, DarkColor, Radius, Font, TAG_COLOR_MAP


# 筛选 Tab 定义
_FILTER_TABS = [
    ("all", "全部"),
    ("active", "进行中"),
    ("done", "已完成"),
]

# 优先级定义：(key, 名称, 颜色属性)
_PRIORITY_DEFS = [
    ("high", "高", "ERROR"),
    ("medium", "中", "WARNING"),
    ("low", "低", "SUCCESS"),
]


def _get_tag_colors(tag: str, colors):
    """根据标签名获取颜色 (bg, text)"""
    attr = "TAG_" + TAG_COLOR_MAP.get(tag, "PROJECT")
    return getattr(colors, attr)


def _get_priority_color(key: str, colors) -> str:
    """根据优先级 key 获取颜色"""
    for k, _name, attr in _PRIORITY_DEFS:
        if k == key:
            return getattr(colors, attr)
    return colors.TEXT_PLACEHOLDER


def _get_priority_name(key: str) -> str:
    for k, name, _attr in _PRIORITY_DEFS:
        if k == key:
            return name
    return ""


# 示例任务数据
_SAMPLE_TASKS = [
    {
        "id": "t1",
        "title": "回复客户合同条款确认邮件",
        "description": (
            "客户对合同第 3 条付款节点提出修改意见，需法务审核后回复。"
            "包含附件两份：合同修订稿、付款计划表。"
        ),
        "priority": "high",
        "due_date": "2026-08-06",
        "tags": ["工作", "项目 Alpha"],
        "related_mail": "客户合同条款修订建议",
        "assignee": "张明",
        "status": "进行中",
        "completed": False,
    },
    {
        "id": "t2",
        "title": "准备周三项目评审会议材料",
        "description": (
            "整理 Q3 进度报告，准备演示 PPT，确认会议室预订情况，"
            "提前发送议程给参会人。"
        ),
        "priority": "high",
        "due_date": "2026-08-06",
        "tags": ["会议", "项目"],
        "related_mail": "项目评审会议通知",
        "assignee": "李华",
        "status": "进行中",
        "completed": False,
    },
    {
        "id": "t3",
        "title": "核对本月部门报销单据",
        "description": "汇总本部门 7 月报销单据，核对发票与申请金额一致性，提交财务复审。",
        "priority": "medium",
        "due_date": "2026-08-08",
        "tags": ["财务"],
        "related_mail": "7 月报销单据汇总提醒",
        "assignee": "王芳",
        "status": "进行中",
        "completed": False,
    },
    {
        "id": "t4",
        "title": "更新项目文档版本至 v1.2",
        "description": "同步最新接口变更到项目文档，更新版本号与变更日志，通知测试团队。",
        "priority": "medium",
        "due_date": "2026-08-10",
        "tags": ["项目 Alpha"],
        "related_mail": "接口变更同步通知",
        "assignee": "陈晨",
        "status": "进行中",
        "completed": False,
    },
    {
        "id": "t5",
        "title": "确认团队建设活动场地",
        "description": "联系三家候选场地，对比价格与设施，提交方案给行政主管审批。",
        "priority": "low",
        "due_date": "2026-08-12",
        "tags": ["个人"],
        "related_mail": "团建活动方案征集",
        "assignee": "赵琳",
        "status": "进行中",
        "completed": False,
    },
    {
        "id": "t6",
        "title": "提交上周工作周报",
        "description": "已完成并提交，主管已阅。",
        "priority": "medium",
        "due_date": "2026-08-04",
        "tags": ["工作"],
        "related_mail": "周报提交提醒",
        "assignee": "张明",
        "status": "已完成",
        "completed": True,
    },
    {
        "id": "t7",
        "title": "归档上月项目交付物",
        "description": "已完成项目交付物归档，文件已上传至共享盘。",
        "priority": "low",
        "due_date": "2026-08-03",
        "tags": ["项目"],
        "related_mail": "项目交付物归档通知",
        "assignee": "李华",
        "status": "已完成",
        "completed": True,
    },
]


@ft.control("Column", init=False)
class TasksPage(ft.Column):
    """任务页面（左栏列表 + 右栏详情）"""

    def __init__(self, is_dark: bool = False):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._is_dark = is_dark
        self._tasks: list[dict] = [dict(t) for t in _SAMPLE_TASKS]
        self._selected_id: str | None = None
        self._current_filter = "all"

        # 左栏容器引用
        self._left_col: ft.Column | None = None
        self._filter_tabs_row: ft.Container | None = None
        self._task_items_col: ft.Column | None = None
        self._empty_view: ft.Container | None = None

        # 右栏持久控件（值替换更新，不重建整个组件）
        self._detail_empty: ft.Container | None = None
        self._detail_view: ft.Container | None = None
        self._detail_priority_tag: ft.Container | None = None
        self._detail_title: ft.Text | None = None
        self._detail_tags_row: ft.Row | None = None
        self._detail_desc: ft.Text | None = None
        self._info_due: ft.Text | None = None
        self._info_mail: ft.Text | None = None
        self._info_assignee: ft.Text | None = None
        self._info_status: ft.Text | None = None
        self._action_complete_btn: ft.Container | None = None
        self._action_complete_label: ft.Text | None = None

        self._build()

    @property
    def _colors(self):
        return DarkColor if self._is_dark else Color

    def _safe_update(self):
        """安全更新 UI，捕获控件未挂载到页面树时的异常。

        说明：page.clean() 会将控件从页面树移除，但 self.page 仍可能非 None，
        因此 `if self.page:` 判断无效。改用 try/except 兜底。
        """
        try:
            self.update()
        except Exception:
            pass

    # ===== 构建 UI =====
    def _build(self):
        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()
        self.controls = [
            ft.Row(
                [left_panel, right_panel],
                spacing=0,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        ]

    # ===== 左栏 =====
    def _build_left_panel(self) -> ft.Container:
        c = self._colors

        # 标题
        self._title = ft.Text(
            "我的任务",
            size=Font.PANEL_TITLE,
            weight=ft.FontWeight.W_600,
            color=c.TEXT_PRIMARY,
        )

        # 新建任务按钮（蓝色胶囊）
        self._new_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD, size=14, color=c.TEXT_ON_PRIMARY),
                    ft.Text(
                        "新建任务",
                        size=Font.AUX,
                        color=c.TEXT_ON_PRIMARY,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=4,
            ),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=c.COMPOSE_GRADIENT,
            ),
            padding=ft.Padding(12, 6, 12, 6),
            border_radius=Radius.PILL,
            on_click=self._on_new_task,
            ink=True,
        )

        # 筛选 Tab
        self._filter_tabs_row = self._build_filter_tabs()

        # 任务列表区（可滚动）
        self._task_items_col = ft.Column(
            spacing=0, expand=True, scroll=ft.ScrollMode.AUTO
        )

        # 空状态
        self._empty_view = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CHECKLIST, size=48, color=c.TEXT_PLACEHOLDER),
                    ft.Text("暂无任务", size=Font.BODY, color=c.TEXT_SECONDARY),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
            visible=False,
        )

        self._left_col = ft.Column(
            [
                # 标题区
                ft.Container(
                    content=ft.Row(
                        [self._title, ft.Container(expand=True), self._new_btn],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(20, 16, 20, 12),
                ),
                # 筛选 Tab
                self._filter_tabs_row,
                # 分割线
                ft.Container(height=1, bgcolor=c.BORDER_LIGHT),
                # 任务列表
                self._task_items_col,
                self._empty_view,
            ],
            spacing=0,
            expand=True,
        )

        return ft.Container(
            content=self._left_col,
            width=360,
            bgcolor=c.BG_CARD,
            border=ft.Border(right=ft.border.BorderSide(1, c.BORDER)),
        )

    def _build_filter_tabs(self) -> ft.Container:
        c = self._colors
        tabs = []
        for key, label in _FILTER_TABS:
            is_active = (key == self._current_filter)
            tab = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            label,
                            size=Font.BODY_SM,
                            color=c.PRIMARY_700 if is_active else c.TEXT_SECONDARY,
                            weight=(ft.FontWeight.W_600 if is_active
                                    else ft.FontWeight.W_400),
                        ),
                        ft.Container(
                            width=24,
                            height=2,
                            bgcolor=c.PRIMARY_700 if is_active else None,
                            border_radius=1,
                        ),
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                data=key,
                on_click=self._on_filter_click,
                padding=ft.Padding(0, 8, 20, 8),
            )
            tabs.append(tab)

        return ft.Container(
            content=ft.Row(tabs, spacing=0),
            padding=ft.Padding(20, 0, 0, 0),
            border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER_LIGHT)),
        )

    def _build_task_item(self, task: dict) -> ft.Container:
        c = self._colors
        is_completed = task.get("completed", False)
        is_selected = (task.get("id") == self._selected_id)
        priority_key = task.get("priority", "low")
        priority_color = _get_priority_color(priority_key, c)

        # 选中态：浅蓝背景
        bgcolor = c.BG_SELECTED if is_selected else None

        # 已完成任务半透明
        opacity = 0.5 if is_completed else 1.0

        # 复选框
        checkbox = ft.Checkbox(
            value=is_completed,
            fill_color=c.PRIMARY_500,
            check_color=c.TEXT_ON_PRIMARY,
            on_change=lambda e, tid=task["id"]: self._on_checkbox_change(e, tid),
        )

        # 任务标题（已完成：划线 + 半透明感）
        title_color = c.TEXT_SECONDARY if is_completed else c.TEXT_PRIMARY
        title_weight = ft.FontWeight.W_400 if is_completed else ft.FontWeight.W_500
        title_decor = (ft.TextDecoration.LINE_THROUGH if is_completed
                       else ft.TextDecoration.NONE)
        title_text = ft.Text(
            task.get("title", ""),
            size=Font.BODY,
            color=title_color,
            weight=title_weight,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
            text_align=ft.TextAlign.LEFT,
        )
        title_text.decoration = title_decor

        # 标签 chips
        tag_row = ft.Row(spacing=6)
        for tag in (task.get("tags") or [])[:2]:
            bg, txt = _get_tag_colors(tag, c)
            tag_row.controls.append(
                ft.Container(
                    content=ft.Text(
                        tag,
                        size=Font.TINY,
                        color=txt,
                        weight=ft.FontWeight.W_500,
                    ),
                    bgcolor=bg,
                    border_radius=Radius.TAB,
                    padding=ft.Padding(8, 2, 8, 2),
                )
            )

        # 截止日期
        due = task.get("due_date", "")
        due_color = self._get_due_color(due, is_completed)
        due_text = ft.Text(due, size=Font.AUX, color=due_color)

        # 顶部行：复选框 + 标题 + 截止日期
        top_row = ft.Row(
            [checkbox, title_text, due_text],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 标签行（左缩进 28px 对齐复选框）
        tags_container = ft.Container(
            content=tag_row,
            padding=ft.Padding(28, 4, 0, 0),
            visible=bool(task.get("tags")),
        )

        return ft.Container(
            content=ft.Column(
                [top_row, tags_container],
                spacing=2,
            ),
            data=task.get("id"),
            on_click=self._on_task_click,
            padding=ft.Padding(20, 12, 20, 12),
            border=ft.Border(
                left=ft.border.BorderSide(3, priority_color),
                bottom=ft.border.BorderSide(1, c.BORDER_LIGHT),
            ),
            bgcolor=bgcolor,
            opacity=opacity,
            ink=True,
        )

    def _get_due_color(self, due_str: str, is_completed: bool) -> str:
        """根据截止日期返回颜色（逾期红 / 临近黄 / 默认灰）"""
        c = self._colors
        if is_completed:
            return c.TEXT_PLACEHOLDER
        try:
            due = datetime.strptime(due_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            if due < today:
                return c.ERROR
            elif due <= today + timedelta(days=2):
                return c.WARNING
            return c.TEXT_PLACEHOLDER
        except Exception:
            return c.TEXT_PLACEHOLDER

    # ===== 右栏 =====
    def _build_right_panel(self) -> ft.Container:
        c = self._colors

        # 空状态：圆形背景图标 + 提示
        self._detail_empty = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.ASSIGNMENT_OUTLINED,
                            size=40,
                            color=c.PRIMARY_500,
                        ),
                        width=80,
                        height=80,
                        border_radius=50,
                        bgcolor=c.PRIMARY_50,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "选择任务查看详情",
                        size=Font.BODY,
                        color=c.TEXT_SECONDARY,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
            visible=True,
        )

        # ── 详情持久控件（值替换更新） ──
        self._detail_priority_tag = ft.Container(
            content=ft.Text("", size=Font.AUX),
            padding=ft.Padding(10, 3, 10, 3),
            border_radius=Radius.TAB,
        )

        self._detail_title = ft.Text(
            "",
            size=Font.DETAIL_SUBJECT,
            weight=ft.FontWeight.W_700,
            color=c.TEXT_PRIMARY,
        )

        self._detail_tags_row = ft.Row(spacing=6)

        self._detail_desc = ft.Text(
            "",
            size=Font.BODY,
            color=c.TEXT_SECONDARY,
        )

        # 信息卡片值文本
        self._info_due = ft.Text("", size=Font.BODY_SM, color=c.TEXT_PRIMARY)
        self._info_mail = ft.Text("", size=Font.BODY_SM, color=c.TEXT_PRIMARY)
        self._info_assignee = ft.Text("", size=Font.BODY_SM, color=c.TEXT_PRIMARY)
        self._info_status = ft.Text("", size=Font.BODY_SM, color=c.TEXT_PRIMARY)

        info_grid = ft.Column(
            [
                self._build_info_card("截止日期", ft.Icons.EVENT, self._info_due),
                ft.Container(height=10),
                self._build_info_card(
                    "关联邮件", ft.Icons.MAIL_OUTLINE, self._info_mail
                ),
                ft.Container(height=10),
                self._build_info_card(
                    "负责人", ft.Icons.PERSON_OUTLINE, self._info_assignee
                ),
                ft.Container(height=10),
                self._build_info_card(
                    "状态", ft.Icons.FLAG_OUTLINED, self._info_status
                ),
            ],
            spacing=0,
        )

        # 操作按钮
        self._action_complete_label = ft.Text(
            "标记完成",
            size=Font.BODY_SM,
            color=c.TEXT_ON_PRIMARY,
            weight=ft.FontWeight.W_500,
        )
        self._action_complete_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_OUTLINE,
                        size=14,
                        color=c.TEXT_ON_PRIMARY,
                    ),
                    self._action_complete_label,
                ],
                spacing=4,
            ),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=c.COMPOSE_GRADIENT,
            ),
            padding=ft.Padding(14, 7, 14, 7),
            border_radius=Radius.PILL,
            on_click=self._on_mark_complete,
            ink=True,
        )

        edit_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_OUTLINED, size=14, color=c.TEXT_SECONDARY),
                    ft.Text(
                        "编辑",
                        size=Font.BODY_SM,
                        color=c.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.Padding(14, 7, 14, 7),
            border_radius=Radius.PILL,
            border=ft.Border.all(1, c.BORDER),
            bgcolor=c.BG_MAIN,
            on_click=self._on_edit,
            ink=True,
        )

        delete_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.DELETE_OUTLINE, size=14, color=c.ERROR),
                    ft.Text(
                        "删除",
                        size=Font.BODY_SM,
                        color=c.ERROR,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.Padding(14, 7, 14, 7),
            border_radius=Radius.PILL,
            border=ft.Border.all(1, c.ERROR),
            bgcolor=c.BG_MAIN,
            on_click=self._on_delete,
            ink=True,
        )

        actions_row = ft.Row(
            [self._action_complete_btn, edit_btn, delete_btn], spacing=8
        )

        detail_content = ft.Container(
            content=ft.Column(
                [
                    self._detail_priority_tag,
                    ft.Container(height=8),
                    self._detail_title,
                    ft.Container(height=10),
                    self._detail_tags_row,
                    ft.Container(height=20),
                    self._detail_desc,
                    ft.Container(height=24),
                    info_grid,
                    ft.Container(height=24),
                    actions_row,
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding(32, 28, 32, 28),
        )

        self._detail_view = ft.Container(
            content=ft.Column(
                [detail_content],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            visible=False,
        )

        return ft.Container(
            content=ft.Column(
                [self._detail_empty, self._detail_view],
                spacing=0,
                expand=True,
            ),
            expand=True,
            bgcolor=c.BG_MAIN,
        )

    def _build_info_card(
        self, label: str, icon, value_text: ft.Text
    ) -> ft.Container:
        c = self._colors
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=18, color=c.TEXT_SECONDARY),
                    ft.Column(
                        [
                            ft.Text(label, size=Font.AUX, color=c.TEXT_SECONDARY),
                            value_text,
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=Radius.CARD,
            bgcolor=c.BG_CARD,
            border=ft.Border.all(1, c.BORDER),
        )

    # ===== 列表刷新 =====
    def _refresh_list(self):
        self._task_items_col.controls.clear()

        filtered = []
        for task in self._tasks:
            if self._current_filter == "active" and task.get("completed"):
                continue
            if self._current_filter == "done" and not task.get("completed"):
                continue
            filtered.append(task)

        for task in filtered:
            self._task_items_col.controls.append(self._build_task_item(task))

        self._empty_view.visible = (len(filtered) == 0)
        self._safe_update()

    # ===== 详情更新（值替换，不重建整个组件） =====
    def _show_detail(self, task: dict):
        c = self._colors

        self._detail_empty.visible = False
        self._detail_view.visible = True

        priority_key = task.get("priority", "low")
        priority_name = _get_priority_name(priority_key)
        priority_color = _get_priority_color(priority_key, c)

        # 优先级标签
        self._detail_priority_tag.content = ft.Text(
            f"{priority_name}优先级",
            size=Font.AUX,
            color=priority_color,
            weight=ft.FontWeight.W_600,
        )
        self._detail_priority_tag.bgcolor = self._priority_bg(priority_key)

        # 标题（已完成：划线 + 次要色）
        is_completed = task.get("completed", False)
        self._detail_title.value = task.get("title", "")
        self._detail_title.color = c.TEXT_SECONDARY if is_completed else c.TEXT_PRIMARY
        self._detail_title.weight = (ft.FontWeight.W_400 if is_completed
                                     else ft.FontWeight.W_700)
        self._detail_title.decoration = (ft.TextDecoration.LINE_THROUGH
                                         if is_completed
                                         else ft.TextDecoration.NONE)

        # 标签
        self._detail_tags_row.controls.clear()
        for tag in (task.get("tags") or []):
            bg, txt = _get_tag_colors(tag, c)
            self._detail_tags_row.controls.append(
                ft.Container(
                    content=ft.Text(
                        tag,
                        size=Font.AUX,
                        color=txt,
                        weight=ft.FontWeight.W_500,
                    ),
                    bgcolor=bg,
                    border_radius=Radius.TAB,
                    padding=ft.Padding(10, 3, 10, 3),
                )
            )

        # 描述
        self._detail_desc.value = task.get("description", "")

        # 信息卡片
        self._info_due.value = task.get("due_date", "—")
        self._info_mail.value = task.get("related_mail", "—")
        self._info_assignee.value = task.get("assignee", "—")
        self._info_status.value = task.get("status", "—")

        # 操作按钮文本
        self._action_complete_label.value = (
            "标记未完成" if is_completed else "标记完成"
        )

        self._safe_update()

    def _priority_bg(self, key: str) -> str:
        """优先级标签背景色（浅色）"""
        if key == "high":
            return "#FEE2E2" if not self._is_dark else "rgba(239,68,68,0.18)"
        elif key == "medium":
            return "#FEF3C7" if not self._is_dark else "rgba(245,158,11,0.18)"
        else:
            return "#DCFCE7" if not self._is_dark else "rgba(16,185,129,0.18)"

    # ===== 事件处理 =====
    def _on_filter_click(self, e: ft.ControlEvent):
        key = e.control.data
        if not key or key == self._current_filter:
            return
        self._current_filter = key
        # 重建筛选 Tab（下划线选中样式）
        idx = self._left_col.controls.index(self._filter_tabs_row)
        self._filter_tabs_row = self._build_filter_tabs()
        self._left_col.controls[idx] = self._filter_tabs_row
        self._refresh_list()

    def _on_task_click(self, e: ft.ControlEvent):
        task_id = e.control.data
        if not task_id:
            return
        self._selected_id = task_id
        self._refresh_list()
        task = next((t for t in self._tasks if t.get("id") == task_id), None)
        if task:
            self._show_detail(task)

    def _on_checkbox_change(self, e: ft.ControlEvent, task_id: str):
        """复选框点击切换完成状态后刷新列表样式"""
        new_val = bool(e.control.value)
        for task in self._tasks:
            if task.get("id") == task_id:
                task["completed"] = new_val
                task["status"] = "已完成" if new_val else "进行中"
                break
        self._refresh_list()
        # 若当前选中的是此任务，同步更新详情
        if self._selected_id == task_id:
            task = next(
                (t for t in self._tasks if t.get("id") == task_id), None
            )
            if task:
                self._show_detail(task)

    def _on_new_task(self, e=None):
        """新建任务（占位）"""
        pass

    def _on_mark_complete(self, e=None):
        if not self._selected_id:
            return
        task = next(
            (t for t in self._tasks if t.get("id") == self._selected_id), None
        )
        if not task:
            return
        task["completed"] = not task.get("completed", False)
        task["status"] = "已完成" if task["completed"] else "进行中"
        self._refresh_list()
        self._show_detail(task)

    def _on_edit(self, e=None):
        """编辑任务（占位）"""
        pass

    def _on_delete(self, e=None):
        if not self._selected_id:
            return
        self._tasks = [
            t for t in self._tasks if t.get("id") != self._selected_id
        ]
        self._selected_id = None
        self._refresh_list()
        # 清空详情
        self._detail_view.visible = False
        self._detail_empty.visible = True
        self._safe_update()

    # ===== 公共方法 =====
    def update_theme(self, is_dark: bool):
        """切换主题时刷新配色"""
        self._is_dark = is_dark
        self._build()
        self._refresh_list()
        if self._selected_id:
            task = next(
                (t for t in self._tasks if t.get("id") == self._selected_id),
                None,
            )
            if task:
                self._show_detail(task)
                return
        self._safe_update()
