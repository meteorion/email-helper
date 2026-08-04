"""联系人页面 - Flet 实现

功能：
  - 左栏：搜索 + 字母分组联系人列表
  - 右栏：联系人详情（头像 + 信息 + 操作按钮 + 最近往来）
"""

import flet as ft

from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font, TAG_COLOR_MAP

logger = get_logger("gui.contacts_page")


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

class RecentMail:
    """最近往来邮件条目"""

    def __init__(self, subject: str, time: str, direction: str = "收"):
        self.subject = subject
        self.time = time
        self.direction = direction  # "收" / "发"


class Contact:
    """联系人数据"""

    def __init__(self, name: str, email: str, phone: str = "",
                 department: str = "", position: str = "", tags=None,
                 notes: str = "", recent_mails=None):
        self.id = email
        self.name = name
        self.email = email
        self.phone = phone
        self.department = department
        self.position = position
        self.tags = list(tags) if tags else []
        self.notes = notes
        self.recent_mails = list(recent_mails) if recent_mails else []


# ---------------------------------------------------------------------------
# 示例数据（10 位联系人，覆盖 A-J 字母分组）
# ---------------------------------------------------------------------------

SAMPLE_CONTACTS = [
    Contact("Alice Wang", "alice.wang@example.com", phone="138-0013-8000",
            department="产品部", position="产品经理", tags=["工作", "项目"],
            notes="Q3 产品路线图负责人，每周三同步会。",
            recent_mails=[
                RecentMail("Re: Q3 产品路线图评审", "今天 10:32", "收"),
                RecentMail("本周产品同步会议程", "昨天 16:20", "发"),
                RecentMail("用户调研报告 V2", "08-01 09:15", "收"),
            ]),
    Contact("Bob Li", "bob.li@example.com", phone="139-0013-9001",
            department="工程部", position="前端架构师", tags=["项目"],
            notes="前端基建负责人，技术方案评审人。",
            recent_mails=[
                RecentMail("前端构建优化方案", "今天 14:08", "收"),
                RecentMail("Re: 组件库版本升级", "08-03 11:45", "发"),
                RecentMail("Code Review 反馈", "08-02 18:30", "收"),
            ]),
    Contact("Carol Zhang", "carol.zhang@example.com", phone="137-0013-7002",
            department="财务部", position="财务主管", tags=["财务"],
            notes="月度报销与合同审核对接人。",
            recent_mails=[
                RecentMail("7 月报销单审核结果", "08-04 09:50", "收"),
                RecentMail("合同付款申请", "08-01 15:12", "发"),
                RecentMail("季度税务申报提醒", "07-28 10:00", "收"),
            ]),
    Contact("David Chen", "david.chen@example.com", phone="136-0013-6003",
            department="销售部", position="销售总监", tags=["工作"],
            notes="华东区大客户对接，月度业绩复盘。",
            recent_mails=[
                RecentMail("华东区 Q3 业绩预测", "今天 17:25", "收"),
                RecentMail("客户拜访行程安排", "08-03 08:40", "发"),
                RecentMail("合同续约确认", "08-02 14:00", "收"),
            ]),
    Contact("Emma Liu", "emma.liu@example.com", phone="135-0013-5004",
            department="市场部", position="品牌经理", tags=["个人", "项目"],
            notes="品牌活动与内容合作对接人。",
            recent_mails=[
                RecentMail("品牌活动方案 V3", "08-04 16:10", "收"),
                RecentMail("公众号内容排期", "08-03 10:30", "发"),
                RecentMail("KOL 合作报价", "08-01 13:20", "收"),
            ]),
    Contact("Frank Zhao", "frank.zhao@example.com", phone="134-0013-4005",
            department="运营部", position="运营负责人", tags=["会议"],
            notes="双周运营复盘会主持人。",
            recent_mails=[
                RecentMail("双周运营复盘会议程", "今天 11:00", "收"),
                RecentMail("用户增长实验结论", "08-04 09:30", "发"),
                RecentMail("活动数据周报", "08-02 17:45", "收"),
            ]),
    Contact("Grace Sun", "grace.sun@example.com", phone="133-0013-3006",
            department="设计部", position="设计主管", tags=["项目"],
            notes="设计规范与视觉评审负责人。",
            recent_mails=[
                RecentMail("设计规范 2.0 终稿", "08-04 15:22", "收"),
                RecentMail("Re: 图标库交付", "08-03 14:00", "发"),
                RecentMail("视觉评审会议纪要", "08-01 16:50", "收"),
            ]),
    Contact("Henry Wu", "henry.wu@example.com", phone="132-0013-2007",
            department="工程部", position="后端架构师", tags=["工作", "会议"],
            notes="服务端架构与接口评审。",
            recent_mails=[
                RecentMail("接口性能优化报告", "今天 13:40", "收"),
                RecentMail("Re: 数据库迁移方案", "08-03 16:20", "发"),
                RecentMail("架构评审会议安排", "08-02 10:15", "收"),
            ]),
    Contact("Iris Zhou", "iris.zhou@example.com", phone="131-0013-1008",
            department="人事部", position="HRBP", tags=["个人"],
            notes="入职与团队建设对接人。",
            recent_mails=[
                RecentMail("新员工入职流程", "08-04 10:00", "收"),
                RecentMail("团队建设活动方案", "08-02 14:30", "发"),
                RecentMail("季度绩效反馈提醒", "07-30 09:00", "收"),
            ]),
    Contact("Jack Ma", "jack.ma@example.com", phone="130-0013-0009",
            department="商务部", position="商务经理", tags=["工作"],
            notes="合作伙伴与渠道对接。",
            recent_mails=[
                RecentMail("渠道合作意向回复", "今天 15:55", "收"),
                RecentMail("商务条款确认", "08-04 11:10", "发"),
                RecentMail("合作伙伴拜访纪要", "08-03 17:00", "收"),
            ]),
]


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_tag_colors(tag: str, colors):
    """根据标签名获取颜色 (bg, text)"""
    attr = "TAG_" + TAG_COLOR_MAP.get(tag, "PROJECT")
    return getattr(colors, attr)


def _avatar_gradient(index: int, colors):
    """根据索引轮换头像渐变（粉橙 / 靛紫 / 绿浅绿）"""
    grads = [colors.AVATAR_GRADIENT_1, colors.AVATAR_GRADIENT_2, colors.AVATAR_GRADIENT_3]
    return grads[index % len(grads)]


def _initial(name: str) -> str:
    """取首字母大写"""
    if not name:
        return "?"
    return name[0].upper()


def _group_key(name: str) -> str:
    """分组字母键（取首字母大写，非字母归入 #）"""
    if not name:
        return "#"
    ch = name[0].upper()
    return ch if ch.isalpha() else "#"


# ---------------------------------------------------------------------------
# 主组件
# ---------------------------------------------------------------------------

@ft.control("Column", init=False)
class ContactsPage(ft.Column):
    """联系人页面（左右两栏：列表 + 详情）"""

    def __init__(self, is_dark: bool = False, on_send_mail=None):
        super().__init__()
        self.spacing = 0
        self.expand = True
        self._is_dark = is_dark
        self._on_send_mail = on_send_mail
        self._contacts: list[Contact] = list(SAMPLE_CONTACTS)
        self._contact_index = {c.id: i for i, c in enumerate(self._contacts)}
        self._filtered: list[Contact] = []
        self._selected_id: str | None = None
        self._search_keyword = ""

        self._build()
        self._populate_list()

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

    # ---- 构建 UI ----
    def _build(self):
        c = self._colors
        self._left_panel = self._build_left_panel()
        self._empty_view = self._build_empty_view()
        self._detail_view = self._build_detail_view()
        self._detail_view.visible = False

        self._right_panel = ft.Container(
            content=ft.Column(
                [self._empty_view, self._detail_view],
                spacing=0,
                expand=True,
            ),
            expand=True,
            bgcolor=c.BG_MAIN,
        )

        self.controls = [
            ft.Row(
                [
                    self._left_panel,
                    ft.Container(width=1, bgcolor=c.BORDER),
                    self._right_panel,
                ],
                spacing=0,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        ]

    def _build_left_panel(self) -> ft.Container:
        """左栏：标题 + 搜索 + 字母分组列表"""
        c = self._colors
        self._search_input = ft.TextField(
            hint_text="搜索联系人...",
            text_size=Font.AUX,
            border_radius=18,
            border_color=c.BORDER,
            bgcolor=c.BG_HOVER,
            focused_border_color=c.PRIMARY_500,
            focused_bgcolor=c.BG_MAIN,
            height=36,
            content_padding=ft.Padding(14, 0, 14, 0),
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._on_search_change,
        )
        self._contacts_col = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)

        return ft.Container(
            width=320,
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(
                            "联系人",
                            size=Font.PANEL_TITLE,
                            weight=ft.FontWeight.W_600,
                            color=c.TEXT_PRIMARY,
                        ),
                        padding=ft.Padding(20, 16, 20, 12),
                    ),
                    ft.Container(
                        content=self._search_input,
                        padding=ft.Padding(20, 0, 20, 12),
                    ),
                    ft.Container(height=1, bgcolor=c.BORDER_LIGHT),
                    self._contacts_col,
                ],
                spacing=0,
            ),
            bgcolor=c.BG_CARD,
        )

    def _build_empty_view(self) -> ft.Container:
        """右栏空状态"""
        c = self._colors
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.CONTACTS_OUTLINED, size=48,
                                        color=c.TEXT_PLACEHOLDER),
                        width=96, height=96, border_radius=50,
                        bgcolor=c.BG_HOVER, alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "选择联系人查看详情",
                        size=18, weight=ft.FontWeight.W_600, color=c.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "从左侧列表选择一位联系人",
                        size=Font.BODY_SM, color=c.TEXT_PLACEHOLDER,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

    def _build_detail_view(self) -> ft.Column:
        """右栏详情（占位控件，后续用值替换更新）"""
        c = self._colors

        # 大头像（80px）
        self._detail_avatar_letter = ft.Text(
            "?", size=32, color=c.TEXT_ON_PRIMARY, weight=ft.FontWeight.W_700,
        )
        self._detail_avatar_box = ft.Container(
            content=self._detail_avatar_letter,
            width=80, height=80, border_radius=50,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=c.AVATAR_GRADIENT_2,
            ),
        )

        # 姓名 / 邮箱 / 标签
        self._detail_name = ft.Text(
            "", size=22, weight=ft.FontWeight.W_700, color=c.TEXT_PRIMARY,
        )
        self._detail_email = ft.Text(
            "", size=Font.BODY, color=c.TEXT_SECONDARY,
        )
        self._detail_tags_row = ft.Row(spacing=6)

        # 操作按钮行
        self._action_row = ft.Row(spacing=10, controls=[
            self._make_action_button(ft.Icons.MAIL_OUTLINE, "发邮件",
                                     on_click=self._on_send_mail_click, variant="filled"),
            self._make_action_button(ft.Icons.EDIT_OUTLINED, "编辑",
                                     on_click=self._on_edit_click),
            self._make_action_button(ft.Icons.DELETE_OUTLINE, "删除",
                                     on_click=self._on_delete_click, danger=True),
        ])

        # 信息卡片（手机 / 部门 / 职位 / 备注）
        self._detail_phone = ft.Text("—", size=Font.BODY, color=c.TEXT_PRIMARY)
        self._detail_department = ft.Text("—", size=Font.BODY, color=c.TEXT_PRIMARY)
        self._detail_position = ft.Text("—", size=Font.BODY, color=c.TEXT_PRIMARY)
        self._detail_notes = ft.Text("—", size=Font.BODY, color=c.TEXT_PRIMARY)

        info_row = ft.Row(spacing=12, controls=[
            self._build_info_card(ft.Icons.PHONE_OUTLINED, "手机", self._detail_phone),
            self._build_info_card(ft.Icons.BUSINESS_CENTER_OUTLINED, "部门", self._detail_department),
            self._build_info_card(ft.Icons.WORK_OUTLINE, "职位", self._detail_position),
        ])
        notes_card = self._build_info_card(ft.Icons.STICKY_NOTE_2_OUTLINED, "备注",
                                           self._detail_notes)

        # 最近往来邮件
        self._recent_mails_col = ft.Column(spacing=8)

        return ft.Column(
            [
                # 头部：头像 + 姓名 + 邮箱 + 标签 + 操作按钮
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    self._detail_avatar_box,
                                    ft.Column(
                                        [self._detail_name, self._detail_email,
                                         self._detail_tags_row],
                                        spacing=6, expand=True,
                                    ),
                                ],
                                spacing=16,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            self._action_row,
                        ],
                        spacing=16,
                    ),
                    padding=ft.Padding(36, 28, 36, 20),
                ),
                ft.Container(height=1, bgcolor=c.BORDER_LIGHT),
                # 信息卡片
                ft.Container(
                    content=ft.Column([info_row, notes_card], spacing=12),
                    padding=ft.Padding(36, 20, 36, 20),
                ),
                ft.Container(height=1, bgcolor=c.BORDER_LIGHT),
                # 最近往来
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("最近往来", size=Font.BODY_LG,
                                    weight=ft.FontWeight.W_600, color=c.TEXT_PRIMARY),
                            self._recent_mails_col,
                        ],
                        spacing=12,
                    ),
                    padding=ft.Padding(36, 20, 36, 28),
                ),
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _build_info_card(self, icon, label, value_text) -> ft.Container:
        """信息卡片（图标 + 标签 + 值）"""
        c = self._colors
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=18, color=c.PRIMARY_500),
                    ft.Column(
                        [
                            ft.Text(label, size=Font.SMALL, color=c.TEXT_PLACEHOLDER),
                            value_text,
                        ],
                        spacing=2, expand=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=Radius.CARD,
            border=ft.Border.all(1, c.BORDER),
            bgcolor=c.BG_CARD,
            expand=True,
        )

    def _make_action_button(self, icon, label, on_click,
                            variant="outlined", danger=False) -> ft.Container:
        """操作按钮（filled 主操作 / outlined 次操作 / danger 删除）"""
        c = self._colors
        if variant == "filled":
            color = c.TEXT_ON_PRIMARY
            bg = c.PRIMARY_500
            border_color = c.PRIMARY_500
        else:
            color = c.ERROR if danger else c.TEXT_SECONDARY
            bg = None
            border_color = c.ERROR if danger else c.BORDER
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=16, color=color),
                    ft.Text(label, size=Font.BODY_SM, color=color,
                            weight=ft.FontWeight.W_500),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            padding=ft.Padding(16, 9, 16, 9),
            border_radius=Radius.BUTTON,
            bgcolor=bg,
            border=ft.Border.all(1, border_color),
            on_click=on_click,
            ink=True,
        )

    def _build_contact_item(self, contact: Contact, index: int) -> ft.Container:
        """左栏联系人项：头像 + 姓名 + 邮箱 + 标签"""
        c = self._colors
        is_selected = (contact.id == self._selected_id)
        bgcolor = c.BG_SELECTED if is_selected else None

        avatar = ft.Container(
            content=ft.Text(
                _initial(contact.name), size=Font.BODY, color=c.TEXT_ON_PRIMARY,
                weight=ft.FontWeight.W_700,
            ),
            width=36, height=36, border_radius=50,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=_avatar_gradient(index, c),
            ),
        )

        name_text = ft.Text(
            contact.name, size=Font.BODY, color=c.TEXT_PRIMARY,
            weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )
        email_text = ft.Text(
            contact.email, size=Font.SMALL, color=c.TEXT_SECONDARY,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )

        tag_row = ft.Row(spacing=4)
        for tag in contact.tags[:2]:
            bg, txt = _get_tag_colors(tag, c)
            tag_row.controls.append(
                ft.Container(
                    content=ft.Text(tag, size=Font.TINY, color=txt,
                                    weight=ft.FontWeight.W_500),
                    bgcolor=bg, border_radius=Radius.TAB,
                    padding=ft.Padding(6, 1, 6, 1),
                )
            )

        return ft.Container(
            content=ft.Row(
                [
                    avatar,
                    ft.Column([name_text, email_text, tag_row], spacing=2, expand=True),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            data=contact.id,
            on_click=self._on_contact_click,
            padding=ft.Padding(20, 10, 20, 10),
            bgcolor=bgcolor,
            ink=not is_selected,
            border=ft.Border(
                left=ft.border.BorderSide(3, c.PRIMARY_500 if is_selected else "transparent"),
            ),
        )

    def _build_recent_mail_item(self, mail: RecentMail) -> ft.Container:
        """最近往来邮件项"""
        c = self._colors
        is_incoming = mail.direction == "收"
        direction_color = c.PRIMARY_500 if is_incoming else c.SUCCESS
        icon = ft.Icons.ARROW_DOWNWARD if is_incoming else ft.Icons.ARROW_UPWARD
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, size=14, color=direction_color),
                        width=28, height=28, border_radius=50,
                        bgcolor=c.BG_HOVER, alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        [
                            ft.Text(mail.subject, size=Font.BODY_SM, color=c.TEXT_PRIMARY,
                                    weight=ft.FontWeight.W_500, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{mail.direction} · {mail.time}", size=Font.SMALL,
                                    color=c.TEXT_PLACEHOLDER),
                        ],
                        spacing=2, expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=Radius.LIST_ITEM,
            border=ft.Border.all(1, c.BORDER_LIGHT),
        )

    # ---- 列表刷新 ----
    def _populate_list(self):
        """构建联系人列表控件（不调用 update）"""
        c = self._colors
        self._contacts_col.controls.clear()

        # 筛选
        self._filtered = []
        for contact in self._contacts:
            if self._search_keyword:
                kw = self._search_keyword.lower()
                if (kw not in contact.name.lower()
                        and kw not in contact.email.lower()
                        and not any(kw in t.lower() for t in contact.tags)):
                    continue
            self._filtered.append(contact)

        # 空状态
        if not self._filtered:
            self._contacts_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.SEARCH_OFF, size=36, color=c.TEXT_PLACEHOLDER),
                            ft.Text("未找到联系人", size=Font.BODY_SM,
                                    color=c.TEXT_PLACEHOLDER),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.Padding(0, 40, 0, 40),
                    alignment=ft.Alignment(0, 0),
                )
            )
            return

        # 按字母分组
        groups: dict[str, list[Contact]] = {}
        for contact in self._filtered:
            key = _group_key(contact.name)
            groups.setdefault(key, []).append(contact)

        # 排序（# 排最后）
        sorted_keys = sorted(groups.keys(), key=lambda k: (k == "#", k))

        for key in sorted_keys:
            # 字母小标题
            self._contacts_col.controls.append(
                ft.Container(
                    content=ft.Text(key, size=Font.AUX, weight=ft.FontWeight.W_700,
                                    color=c.TEXT_SECONDARY),
                    padding=ft.Padding(20, 10, 20, 4),
                    bgcolor=c.BG_SIDEBAR,
                )
            )
            for contact in groups[key]:
                idx = self._contact_index[contact.id]
                self._contacts_col.controls.append(self._build_contact_item(contact, idx))

    def _refresh_list(self):
        """刷新联系人列表并更新 UI"""
        self._populate_list()
        self._safe_update()

    # ---- 详情更新（值替换，不重建组件）----
    def _show_contact(self, contact: Contact):
        """通过值替换方式更新详情区"""
        c = self._colors
        self._empty_view.visible = False
        self._detail_view.visible = True

        idx = self._contact_index[contact.id]

        # 头像
        self._detail_avatar_letter.value = _initial(contact.name)
        self._detail_avatar_box.gradient = ft.LinearGradient(
            begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
            colors=_avatar_gradient(idx, c),
        )

        # 姓名 / 邮箱
        self._detail_name.value = contact.name
        self._detail_email.value = contact.email

        # 标签
        self._detail_tags_row.controls.clear()
        for tag in contact.tags:
            bg, txt = _get_tag_colors(tag, c)
            self._detail_tags_row.controls.append(
                ft.Container(
                    content=ft.Text(tag, size=Font.TINY, color=txt,
                                    weight=ft.FontWeight.W_500),
                    bgcolor=bg, border_radius=Radius.TAB,
                    padding=ft.Padding(8, 2, 8, 2),
                )
            )

        # 信息卡片
        self._detail_phone.value = contact.phone or "—"
        self._detail_department.value = contact.department or "—"
        self._detail_position.value = contact.position or "—"
        self._detail_notes.value = contact.notes or "—"

        # 最近往来（最多 3 条）
        self._recent_mails_col.controls.clear()
        for mail in contact.recent_mails[:3]:
            self._recent_mails_col.controls.append(self._build_recent_mail_item(mail))

        self._safe_update()

    def _show_empty(self):
        """显示空状态"""
        self._empty_view.visible = True
        self._detail_view.visible = False
        self._safe_update()

    # ---- 事件处理 ----
    def _on_search_change(self, e: ft.ControlEvent):
        self._search_keyword = e.control.value or ""
        self._refresh_list()

    def _on_contact_click(self, e: ft.ControlEvent):
        contact_id = e.control.data
        if not contact_id:
            return
        self._selected_id = contact_id
        contact = next((c for c in self._contacts if c.id == contact_id), None)
        if contact:
            self._refresh_list()
            self._show_contact(contact)
            logger.info(f"选中联系人: {contact.name}")

    def _on_send_mail_click(self, e=None):
        if not self._selected_id:
            return
        contact = next((c for c in self._contacts if c.id == self._selected_id), None)
        if contact:
            logger.info(f"发邮件给: {contact.name}")
            if self._on_send_mail:
                self._on_send_mail(contact)

    def _on_edit_click(self, e=None):
        logger.info("点击编辑联系人")

    def _on_delete_click(self, e=None):
        if not self._selected_id:
            return
        contact = next((c for c in self._contacts if c.id == self._selected_id), None)
        if contact:
            logger.info(f"点击删除联系人: {contact.name}")

    # ---- 公共方法 ----
    def update_theme(self, is_dark: bool):
        """切换主题（重建 UI 并恢复选中态）"""
        self._is_dark = is_dark
        selected_id = self._selected_id
        self._build()
        self._populate_list()
        if selected_id:
            contact = next((c for c in self._contacts if c.id == selected_id), None)
            if contact:
                self._show_contact(contact)
            else:
                self._show_empty()
        else:
            self._show_empty()


# ---------------------------------------------------------------------------
# 独立运行入口
# ---------------------------------------------------------------------------

def main(page: ft.Page):
    page.title = "联系人"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.add(ContactsPage(is_dark=False))


if __name__ == "__main__":
    ft.run(main)
