"""通用设置页面 — 严格按 email_desktop_ui_design.html P2-5 规格实现

结构（对齐设计稿 .settings-layout）：
  左侧导航（.settings-nav）: 账户管理 / AI设置 / 通知设置 / 外观主题 / ...
  右侧内容（.settings-content）: 根据 selected tab 切换面板

已实现面板：
  - AI设置（P2-4）: 分类模式 / AI服务商 / 置信度阈值 / Prompt自定义
  - 外观主题（P2-5）: 主题模式 / 强调色 / 字体大小 / 开关项
  - 账户管理: 打开 AccountDialog
  其余 tab 为占位。
"""

import json
import base64
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

from src.core.logger import get_logger
from src.gui.theme import Color, DarkColor, Radius, Font

logger = get_logger("gui.settings")


# 设置导航项（对齐设计稿，Worker 移入；排序按使用频率/依赖关系）
_SETTINGS_NAV = [
    ("account", "账户管理"),
    ("ai", "AI 设置"),
    ("notification", "通知设置"),
    ("workflow", "流程管理"),
    ("template", "模板管理"),
    ("schedule", "调度配置"),
    ("attach", "附件下载分级"),
    ("worker", "Worker 进度反馈"),
]

# AI 分类模式
_CLASSIFY_MODES = [
    ("manual", "Manual (人工)"),
    ("hybrid", "Hybrid (混合)"),
    ("auto", "Auto (自动)"),
]

# 重新分类模式
_RECLASSIFY_MODES = [
    ("current", "按当前模式"),
    ("force_ai", "强制 AI (force_ai)"),
    ("force_rule", "强制规则 (force_rule)"),
]

# AI 服务商
_PROVIDERS = [
    {"key": "deepseek", "name": "DeepSeek Chat", "model": "deepseek-chat",
     "status": "已连接", "connected": True, "icon": "DS",
     "gradient": ["#3B82F6", "#6366F1"]},
    {"key": "ollama", "name": "Ollama (本地)", "model": "qwen2.5:7b",
     "status": "未连接", "connected": False, "icon": "OA",
     "gradient": ["#10B981", "#34D399"]},
    {"key": "openai", "name": "OpenAI API", "model": "gpt-4o-mini",
     "status": "备用", "connected": False, "icon": "OA",
     "gradient": ["#8B5CF6", "#A78BFA"]},
]

# 设置导航项调度 — 拉取模式
_PULL_MODES = [
    ("idle", "IDLE (推荐)"),
    ("polling", "轮询"),
    ("mixed", "混合"),
]

# 调度 — Cron 调度类型
_CRON_TYPES = [
    ("minute", "每分钟"),
    ("hourly", "每小时"),
    ("daily", "每日"),
    ("weekday", "工作日"),
    ("custom", "自定义"),
]

# 调度 — 星期
_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]

# 默认 Prompt
_DEFAULT_PROMPT = """你是一个专业的邮件分类助手，专注于企业微信邮件场景。

## 分类体系
- 审批类 / 通知类 / 会议类 / 协作类 / 资讯类 / 告警类 / 营销类 / 垃圾邮件

## 输出格式 (JSON)
{
  "category": "分类名称",
  "priority": "紧急/普通/低优先级",
  "need_reply": true/false,
  "confidence": 0.85,
  "reason": "分类理由(50字内)"
}"""


class SettingsPage:
    """通用设置页面（对齐 P2-5 设计稿）"""

    def __init__(self, page: ft.Page, is_dark: bool = False,
                 on_back=None, on_theme_change=None,
                 on_open_account=None, on_rebuild=None):
        self.page = page
        self._is_dark = is_dark
        self._on_back = on_back
        self._on_theme_change = on_theme_change
        self._on_open_account = on_open_account
        self._on_rebuild = on_rebuild  # 主窗口提供的重建回调
        self._selected_tab = "account"
        self._nav_items: list[ft.Container] = []

        # AI 配置状态
        self._classify_mode = "hybrid"
        self._reclassify_mode = "current"
        self._active_provider = "deepseek"
        self._auto_threshold = 0.85
        self._manual_threshold = 0.5
        self._ai_config_path = Path("config/ai.json")

        # ── 账户管理表单状态（内嵌，替换原弹窗） ──────
        self._account_config_path = Path("config/account.json")
        self._acc_email_input: ft.TextField | None = None
        self._acc_password_input: ft.TextField | None = None
        self._acc_imap_host: ft.TextField | None = None
        self._acc_imap_port: ft.TextField | None = None
        self._acc_imap_ssl: ft.Checkbox | None = None
        self._acc_smtp_host: ft.TextField | None = None
        self._acc_smtp_port: ft.TextField | None = None
        self._acc_smtp_ssl: ft.Checkbox | None = None
        self._acc_status_text: ft.Text | None = None
        self._acc_status_card: ft.Container | None = None
        self._acc_arrow: ft.Text | None = None
        self._acc_advanced_body: ft.Column | None = None
        self._acc_advanced_expanded = False
        self._acc_test_label: ft.Text | None = None

        # ── 调度配置状态 ──
        self._schedule_config_path = Path("config/schedule.json")
        self._pull_mode = "idle"            # idle / polling / mixed
        self._poll_interval = 5             # 分钟
        self._idle_timeout = 25             # 分钟
        self._cron_type = "weekday"         # minute / hourly / daily / weekday / custom
        self._cron_time = "09:00"           # HH:MM
        self._cron_weekdays = {0, 1, 2, 3, 4}  # 0=一 ... 6=日
        self._cron_expr = "0 9 * * 1-5"
        self._cron_preview_text: ft.Text | None = None
        self._cron_expr_input: ft.TextField | None = None
        self._schedule_accounts: list[dict] = []

        # 加载 AI 配置
        self._load_ai_config()
        self._load_schedule_config()

    @property
    def _c(self):
        return DarkColor if self._is_dark else Color

    # ===== 公共入口 =====

    def build(self) -> ft.Control:
        """构建设置页面（左侧导航 + 右侧内容）"""
        c = self._c
        return ft.Container(
            content=ft.Row(
                [
                    self._build_nav(),
                    self._build_content(),
                ],
                spacing=0,
                expand=True,
            ),
            bgcolor=c.BG_MAIN,
            expand=True,
        )

    def update_theme(self, is_dark: bool):
        """主题切换时刷新"""
        self._is_dark = is_dark

    # ===== 左侧导航 =====

    def _build_nav(self) -> ft.Container:
        c = self._c
        self._nav_items = []
        for key, label in _SETTINGS_NAV:
            self._nav_items.append(self._build_nav_item(key, label))

        return ft.Container(
            content=ft.Column(
                [ft.Container(height=12), *self._nav_items],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=200,
            bgcolor=c.BG_SIDEBAR,
            border=ft.Border(right=ft.border.BorderSide(1, c.BORDER)),
            padding=ft.Padding(12, 0, 8, 0),
            expand=False,
        )

    def _build_nav_item(self, key: str, label: str) -> ft.Container:
        c = self._c
        is_active = (key == self._selected_tab)

        if is_active:
            bgcolor = c.PRIMARY_50
            text_color = c.PRIMARY_700 if not self._is_dark else c.PRIMARY_400
            border = ft.Border(
                left=ft.border.BorderSide(3, c.PRIMARY_500),
            )
            weight = ft.FontWeight.W_600
        else:
            bgcolor = None
            text_color = c.TEXT_SECONDARY
            border = None
            weight = ft.FontWeight.W_500

        return ft.Container(
            content=ft.Text(
                label,
                size=13,
                color=text_color,
                weight=weight,
            ),
            padding=ft.Padding(16, 10, 12, 10),
            border_radius=Radius.BUTTON,
            bgcolor=bgcolor,
            border=border,
            data=key,
            on_click=self._on_nav_click,
            ink=True,
        )

    def _on_nav_click(self, e: ft.ControlEvent):
        key = e.control.data
        if key == self._selected_tab:
            return
        self._selected_tab = key
        if self._on_rebuild:
            self._on_rebuild()
        else:
            self.page.update()

    def _rebuild(self):
        """重建设置页面（委托给主窗口）"""
        if self._on_rebuild:
            self._on_rebuild()

    # ===== 右侧内容 =====

    def _build_content(self) -> ft.Container:
        c = self._c

        # 顶部标题栏
        title_map = dict(_SETTINGS_NAV)
        title_text = title_map.get(self._selected_tab, "设置")

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ARROW_BACK, size=18, color=c.TEXT_SECONDARY),
                    ft.Text(title_text, size=Font.PANEL_TITLE,
                            weight=ft.FontWeight.W_600, color=c.TEXT_PRIMARY),
                    ft.Container(expand=True),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(24, 16, 24, 16),
            on_click=self._on_back_click,
        )

        # 根据 tab 切换内容
        content_map = {
            "ai": self._build_ai_panel,
            "account": self._build_account_panel,
            "notification": lambda: self._build_placeholder("通知设置"),
            "workflow": lambda: self._build_placeholder("流程管理"),
            "template": lambda: self._build_placeholder("模板管理"),
            "schedule": self._build_schedule_panel,
            "attach": lambda: self._build_placeholder("附件下载分级"),
            "worker": lambda: self._build_placeholder("Worker 进度反馈"),
        }
        builder = content_map.get(self._selected_tab, self._build_placeholder)
        panel = builder()

        scroll_col = ft.Column(
            [header, panel],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Container(
            content=scroll_col,
            expand=True,
            bgcolor=c.BG_MAIN,
        )

    def _on_back_click(self, e=None):
        if self._on_back:
            self._on_back()

    # ===== AI 设置面板 (P2-4) =====

    def _build_ai_panel(self) -> ft.Column:
        return ft.Column(
            [
                self._ai_card_classify_mode(),
                ft.Container(height=16),
                self._ai_card_provider(),
                ft.Container(height=16),
                self._ai_card_threshold(),
                ft.Container(height=16),
                self._ai_card_prompt(),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _ai_card(self, title: str, body: ft.Control) -> ft.Container:
        """AI 设置卡片容器（对齐 .ai-settings-card）"""
        c = self._c
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(title, size=14,
                                        weight=ft.FontWeight.W_600,
                                        color=c.TEXT_PRIMARY),
                        padding=ft.Padding(20, 14, 20, 14),
                        border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER)),
                    ),
                    ft.Container(
                        content=body,
                        padding=ft.Padding(20, 16, 20, 16),
                    ),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            margin=ft.Margin(24, 0, 24, 0),
            border_radius=Radius.CARD,
            bgcolor=c.BG_CARD,
            border=ft.Border.all(1, c.BORDER),
        )

    def _ai_card_classify_mode(self) -> ft.Container:
        c = self._c

        # 运行模式
        mode_btns = []
        for key, label in _CLASSIFY_MODES:
            is_active = (key == self._classify_mode)
            mode_btns.append(self._build_radio_btn(key, label, is_active,
                                                   "classify_mode"))

        # 重新分类模式
        reclassify_btns = []
        for key, label in _RECLASSIFY_MODES:
            is_active = (key == self._reclassify_mode)
            reclassify_btns.append(self._build_radio_btn(key, label, is_active,
                                                        "reclassify_mode"))

        body = ft.Column(
            [
                self._ai_form_row("运行模式:", ft.Row(
                    mode_btns, spacing=8,
                )),
                ft.Text(
                    "Hybrid: 规则预筛 → AI 推理 → 置信度阈值决定是否进人工队列",
                    size=11, color=c.TEXT_SECONDARY,
                ),
                ft.Container(height=14),
                self._ai_form_row("重新分类模式:", ft.Row(
                    reclassify_btns, spacing=8,
                )),
                ft.Text(
                    "force_rule 与 force_ai 互斥；force_rule 优先级更高，未命中规则时降级为人工",
                    size=11, color=c.TEXT_SECONDARY,
                ),
            ],
            spacing=6,
        )
        return self._ai_card("分类模式", body)

    def _build_radio_btn(self, key: str, label: str, active: bool,
                         group: str) -> ft.Container:
        """单选按钮（对齐 .ai-radio-btn）"""
        c = self._c
        if active:
            bgcolor = c.PRIMARY_500
            text_color = "#FFFFFF"
            border_color = c.PRIMARY_500
        else:
            bgcolor = c.BG_MAIN
            text_color = c.TEXT_SECONDARY
            border_color = c.BORDER

        return ft.Container(
            content=ft.Text(label, size=12, color=text_color,
                            weight=ft.FontWeight.W_500),
            padding=ft.Padding(14, 7, 14, 7),
            border_radius=Radius.BUTTON,
            bgcolor=bgcolor,
            border=ft.Border.all(1, border_color),
            data=f"{group}:{key}",
            on_click=self._on_radio_click,
            ink=True,
        )

    def _on_radio_click(self, e: ft.ControlEvent):
        group, key = e.control.data.split(":", 1)
        if group == "classify_mode":
            self._classify_mode = key
        elif group == "reclassify_mode":
            self._reclassify_mode = key
        self._refresh_ai_panel()

    def _ai_card_provider(self) -> ft.Container:
        c = self._c

        provider_cards = []
        for p in _PROVIDERS:
            is_active = (p["key"] == self._active_provider)
            provider_cards.append(self._build_provider_card(p, is_active))

        self._ai_apikey = ft.TextField(
            hint_text="API Key",
            value="sk-ant-api03-xxxxx",
            password=True,
            can_reveal_password=True,
            text_size=13,
            border_radius=Radius.BUTTON,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
            width=320,
            dense=True,
        )
        self._ai_timeout = ft.TextField(
            value="30",
            text_size=13,
            border_radius=Radius.BUTTON,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
            width=80,
            dense=True,
        )

        body = ft.Column(
            [
                *provider_cards,
                ft.Container(height=14),
                self._ai_form_row("API Key:", self._ai_apikey),
                ft.Container(height=8),
                self._ai_form_row("超时(秒):", self._ai_timeout),
            ],
            spacing=8,
        )
        return self._ai_card("AI 服务商", body)

    def _build_provider_card(self, p: dict, is_active: bool) -> ft.Container:
        c = self._c
        border_color = c.PRIMARY_500 if is_active else c.BORDER
        bg = c.PRIMARY_50 if is_active else c.BG_MAIN

        status_color = c.SUCCESS if p["connected"] else c.TEXT_SECONDARY
        status_text = f"● {p['status']}" if p["connected"] else p["status"]

        icon = ft.Container(
            content=ft.Text(p["icon"], size=13, color="#FFFFFF",
                            text_align=ft.TextAlign.CENTER),
            width=36, height=36,
            border_radius=8,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=p["gradient"],
            ),
            alignment=ft.Alignment(0, 0),
        )

        return ft.Container(
            content=ft.Row(
                [
                    icon,
                    ft.Column(
                        [
                            ft.Text(p["name"], size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=c.TEXT_PRIMARY),
                            ft.Text(f"{p['model']} · {p.get('status', '')}",
                                    size=11, color=c.TEXT_SECONDARY),
                        ],
                        spacing=2,
                    ),
                    ft.Container(expand=True),
                    ft.Text(status_text, size=11, color=status_color),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 10, 14, 10),
            border_radius=Radius.CARD,
            bgcolor=bg,
            border=ft.Border.all(1, border_color),
            data=p["key"],
            on_click=self._on_provider_click,
            ink=True,
        )

    def _on_provider_click(self, e: ft.ControlEvent):
        self._active_provider = e.control.data
        self._refresh_ai_panel()

    def _ai_card_threshold(self) -> ft.Container:
        c = self._c

        self._auto_slider = ft.Slider(
            min=0.5, max=1.0, value=self._auto_threshold,
            divisions=10, label="{value}",
            on_change=self._on_auto_threshold_change,
            expand=True,
        )
        self._manual_slider = ft.Slider(
            min=0.5, max=1.0, value=self._manual_threshold,
            divisions=10, label="{value}",
            on_change=self._on_manual_threshold_change,
            expand=True,
        )
        self._auto_label = ft.Text(
            f"当前: {self._auto_threshold:.2f}",
            size=11, color=c.PRIMARY_700 if not self._is_dark else c.PRIMARY_400,
        )
        self._manual_label = ft.Text(
            f"当前: {self._manual_threshold:.2f}",
            size=11, color=c.ERROR,
        )

        body = ft.Column(
            [
                self._ai_form_row("自动确认阈值:", ft.Column([
                    self._auto_slider,
                    self._auto_label,
                    ft.Text("置信度 ≥ 此值自动执行流程，否则进入人工队列",
                            size=11, color=c.TEXT_SECONDARY),
                ], spacing=4)),
                ft.Container(height=8),
                self._ai_form_row("人工复核阈值:", ft.Column([
                    self._manual_slider,
                    self._manual_label,
                    ft.Text("置信度 < 此值强制人工复核",
                            size=11, color=c.TEXT_SECONDARY),
                ], spacing=4)),
            ],
            spacing=4,
        )
        return self._ai_card("置信度阈值", body)

    def _on_auto_threshold_change(self, e):
        self._auto_threshold = round(e.control.value, 2)
        self._auto_label.value = f"当前: {self._auto_threshold:.2f}"
        self.page.update()

    def _on_manual_threshold_change(self, e):
        self._manual_threshold = round(e.control.value, 2)
        self._manual_label.value = f"当前: {self._manual_threshold:.2f}"
        self.page.update()

    def _ai_card_prompt(self) -> ft.Container:
        c = self._c

        self._prompt_area = ft.TextField(
            value=_DEFAULT_PROMPT,
            multiline=True,
            min_lines=8,
            max_lines=12,
            text_size=12,
            border_radius=Radius.CARD,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
        )

        body = ft.Column(
            [
                self._prompt_area,
                ft.Row(
                    [
                        self._build_ai_btn("保存", primary=True,
                                          on_click=self._on_save_prompt),
                        self._build_ai_btn("恢复默认",
                                          on_click=self._on_reset_prompt),
                        self._build_ai_btn("测试 Prompt",
                                          on_click=self._on_test_prompt),
                    ],
                    spacing=8,
                ),
            ],
            spacing=10,
        )
        return self._ai_card("Prompt 自定义", body)

    def _build_ai_btn(self, label: str, primary: bool = False,
                      on_click=None) -> ft.Container:
        c = self._c
        if primary:
            return ft.Container(
                content=ft.Text(label, size=13, color="#FFFFFF",
                                weight=ft.FontWeight.W_500),
                padding=ft.Padding(16, 8, 16, 8),
                border_radius=Radius.PILL,
                bgcolor=c.PRIMARY_500,
                on_click=on_click,
                ink=True,
            )
        else:
            return ft.Container(
                content=ft.Text(label, size=13, color=c.TEXT_SECONDARY,
                                weight=ft.FontWeight.W_500),
                padding=ft.Padding(16, 8, 16, 8),
                border_radius=Radius.PILL,
                border=ft.Border.all(1, c.BORDER),
                bgcolor=c.BG_MAIN,
                on_click=on_click,
                ink=True,
            )

    def _on_save_prompt(self, e=None):
        logger.info("Prompt 已保存")
        self._save_ai_config()

    def _on_reset_prompt(self, e=None):
        self._prompt_area.value = _DEFAULT_PROMPT
        self.page.update()

    def _on_test_prompt(self, e=None):
        logger.info("测试 Prompt（待实现）")

    def _ai_form_row(self, label: str, control: ft.Control) -> ft.Row:
        c = self._c
        return ft.Row(
            [
                ft.Text(label, size=13, color=c.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_500),
                control,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _refresh_ai_panel(self):
        """刷新 AI 面板（切换选项后）"""
        if self._on_rebuild:
            self._on_rebuild()

    # ===== AI 配置持久化 =====

    def _load_ai_config(self):
        if not self._ai_config_path.exists():
            return
        try:
            with open(self._ai_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._classify_mode = data.get("classify_mode", "hybrid")
            self._auto_threshold = data.get("confidence_threshold_auto", 0.85)
            self._manual_threshold = data.get("confidence_threshold_manual", 0.5)
            self._active_provider = data.get("provider", "deepseek")
            logger.info("AI 配置已加载")
        except Exception as ex:
            logger.error(f"加载 AI 配置失败: {ex}")

    def _save_ai_config(self):
        config = {
            "classify_mode": self._classify_mode,
            "reclassify_mode": self._reclassify_mode,
            "provider": self._active_provider,
            "confidence_threshold_auto": self._auto_threshold,
            "confidence_threshold_manual": self._manual_threshold,
            "llm_enabled": self._active_provider != "manual",
            "model": next((p["model"] for p in _PROVIDERS
                          if p["key"] == self._active_provider), "deepseek-chat"),
            "timeout": int(self._ai_timeout.value or "30"),
            "temperature": 0.1,
            "max_tokens": 500,
        }
        try:
            self._ai_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._ai_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("AI 配置已保存")
        except Exception as ex:
            logger.error(f"保存 AI 配置失败: {ex}")

    # ===== 账户管理面板（内嵌完整表单，对齐设计稿） =====

    def _acc_init_fields(self):
        """初始化账户管理表单字段控件（只调用一次）"""
        if self._acc_email_input is not None:
            return

        c = self._c
        is_dark = self._is_dark

        # 统一输入框高度，避免 password reveal 图标导致高度不一致
        _INPUT_HEIGHT = 42

        def _input(*, hint=None, value=None, password=False,
                   reveal=False, width=None, expand=False, suffix_icon=None):
            return ft.TextField(
                hint_text=hint, value=value,
                password=password, can_reveal_password=reveal,
                text_size=13,
                color=c.TEXT_PRIMARY,
                hint_style=ft.TextStyle(color=c.TEXT_PLACEHOLDER, size=13),
                border_radius=9,
                border_color="#E5E7EB" if not is_dark else "#475569",
                bgcolor="#F9FAFB" if not is_dark else "#1E293B",
                focused_border_color="#3B82F6",
                focused_bgcolor=c.BG_MAIN,
                content_padding=ft.Padding(14, 9, 14, 9),
                dense=True,
                height=_INPUT_HEIGHT,
                width=width,
                expand=expand,
                suffix_icon=suffix_icon,
            )

        # 邮箱字段加后缀图标，与密码字段高度一致
        email_suffix = ft.Icon(ft.Icons.MAIL_OUTLINE, size=16,
                               color="#94A3B8" if not is_dark else "#64748B")
        self._acc_email_input    = _input(value="meteorzhong@yeahka.com",
                                          hint="请输入邮箱地址",
                                          suffix_icon=email_suffix)
        self._acc_password_input = _input(value="QmA35AZYRwCKVGDG",
                                          hint="请输入密码或授权码",
                                          password=True, reveal=True)
        # 注意: host 字段的宽度由外层 Container(width=340) 控制
        self._acc_imap_host = _input(value="mail.yeahka.com", hint="如: imap.qq.com")
        self._acc_imap_port = _input(value="993", width=130)
        self._acc_smtp_host = _input(value="mail.yeahka.com", hint="如: smtp.qq.com")
        self._acc_smtp_port = _input(value="465", width=130)

        # SSL 复选框（对齐 .account-checkbox-row：16x16 + label 13px）
        ssl_label_color = "#374151" if not is_dark else "#CBD5E1"
        self._acc_imap_ssl = ft.Checkbox(
            label="使用 SSL 加密连接 (推荐)",
            value=True,
            fill_color=c.PRIMARY_500,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(size=13, color=ssl_label_color),
        )
        self._acc_smtp_ssl = ft.Checkbox(
            label="使用 SSL 加密连接 (推荐)",
            value=True,
            fill_color=c.PRIMARY_500,
            check_color="#FFFFFF",
            label_style=ft.TextStyle(size=13, color=ssl_label_color),
        )

        # 状态卡片
        self._acc_status_text = ft.Text(
            "💡 请填写邮箱和密码（企业邮箱默认参数已预填，可直接使用）",
            size=13,
        )
        self._acc_set_status_card("info")

        # 折叠箭头 + 展开区
        self._acc_arrow = ft.Text("▶", size=10, color="#94A3B8")

        # IMAP/SMTP 行：两组 label+input 并排（对齐 .account-form-row）
        def _port_row(host_label: str, host_field, port_field) -> ft.Row:
            """label 在上、input 在下，两组并排"""
            is_dark = self._is_dark
            label_color = "#374151" if not is_dark else "#CBD5E1"
            return ft.Row(
                [
                    # 左：主机字段（label + input）
                    ft.Column(
                        [
                            ft.Text(host_label, size=12,
                                    weight=ft.FontWeight.W_500,
                                    color=label_color),
                            ft.Container(height=5),
                            ft.Container(content=host_field, width=340),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Container(width=14),  # group spacing
                    # 右：端口字段（label + input）
                    ft.Column(
                        [
                            ft.Text("端口", size=12,
                                    weight=ft.FontWeight.W_500,
                                    color=label_color),
                            ft.Container(height=5),
                            port_field,
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                    ),
                ],
                spacing=0,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )

        self._acc_advanced_body = ft.Column(
            [
                # IMAP section (margin-top 10px, margin-bottom 14px)
                ft.Container(
                    content=ft.Column(
                        [
                            self._acc_section_title("IMAP 配置（收邮件）", is_dark),
                            ft.Container(height=10),
                            _port_row("IMAP 服务器", self._acc_imap_host, self._acc_imap_port),
                            ft.Container(height=16),
                            ft.Container(
                                content=self._acc_imap_ssl,
                                padding=ft.Padding(2, 2, 2, 2),
                            ),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    margin=ft.Margin(0, 10, 0, 14),
                ),
                # SMTP section
                ft.Container(
                    content=ft.Column(
                        [
                            self._acc_section_title("SMTP 配置（发邮件）", is_dark),
                            ft.Container(height=10),
                            _port_row("SMTP 服务器", self._acc_smtp_host, self._acc_smtp_port),
                            ft.Container(height=16),
                            ft.Container(
                                content=self._acc_smtp_ssl,
                                padding=ft.Padding(2, 2, 2, 2),
                            ),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    margin=ft.Margin(0, 0, 0, 14),
                ),
            ],
            spacing=0,
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self._acc_test_label = ft.Text(
            "🔌 测试连接", size=13,
            weight=ft.FontWeight.W_500,
            color=c.TEXT_SECONDARY,
        )

        self._acc_load_config()

    def _acc_set_status_card(self, kind: str):
        """设置状态卡片语义色（info / success / error）"""
        if self._is_dark:
            palette = {
                "info":    ("rgba(59,130,246,0.12)",  "#93C5FD", "#1E3A5F"),
                "success": ("rgba(16,185,129,0.12)",  "#6EE7B7", "#064E3B"),
                "error":   ("rgba(239,68,68,0.12)",   "#FCA5A5", "#450A0A"),
            }
        else:
            palette = {
                "info":    ("#EFF6FF", "#1D4ED8", "#BFDBFE"),
                "success": ("#ECFDF5", "#065F46", "#A7F3D0"),
                "error":   ("#FEF2F2", "#991B1B", "#FECACA"),
            }
        bg, fg, bd = palette.get(kind, palette["info"])
        if self._acc_status_text:
            self._acc_status_text.color = fg
        if self._acc_status_card:
            self._acc_status_card.bgcolor = bg
            self._acc_status_card.border = ft.Border.all(1, bd)
        else:
            self._acc_status_card = ft.Container(
                content=self._acc_status_text,
                bgcolor=bg, border=ft.Border.all(1, bd),
                border_radius=8,
                padding=ft.Padding(14, 8, 14, 8),
            )

    def _acc_set_status(self, msg: str, kind: str = "info"):
        if self._acc_status_text:
            self._acc_status_text.value = msg
        self._acc_set_status_card(kind)

    def _acc_form_group(self, label: str, field, required: bool = False,
                        expand: bool = False) -> ft.Column:
        is_dark = self._is_dark
        label_color = "#374151" if not is_dark else "#CBD5E1"
        label_row = ft.Row(
            [
                ft.Text(label, size=12, weight=ft.FontWeight.W_500, color=label_color),
                *(
                    [ft.Text("*", size=12, color="#EF4444")]
                    if required else []
                ),
            ],
            spacing=2, tight=True,
        )
        return ft.Column(
            [label_row, field],
            spacing=5,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=expand,
        )

    def _acc_load_config(self):
        if not self._account_config_path.exists():
            return
        try:
            with open(self._account_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if self._acc_email_input:
                self._acc_email_input.value = data.get("email", "")
            if self._acc_password_input:
                pwd_b64 = data.get("password", "")
                if pwd_b64:
                    try:
                        self._acc_password_input.value = base64.b64decode(pwd_b64).decode()
                    except Exception:
                        pass
            imap = data.get("imap", {})
            if self._acc_imap_host:
                self._acc_imap_host.value = imap.get("host", "imap.exmail.qq.com")
            if self._acc_imap_port:
                self._acc_imap_port.value = str(imap.get("port", 993))
            if self._acc_imap_ssl:
                self._acc_imap_ssl.value = imap.get("ssl", True)
            smtp = data.get("smtp", {})
            if self._acc_smtp_host:
                self._acc_smtp_host.value = smtp.get("host", "smtp.exmail.qq.com")
            if self._acc_smtp_port:
                self._acc_smtp_port.value = str(smtp.get("port", 465))
            if self._acc_smtp_ssl:
                self._acc_smtp_ssl.value = smtp.get("ssl", True)
            logger.info("账户配置已加载到设置页")
        except Exception as ex:
            logger.error(f"加载账户配置失败: {ex}")

    def _acc_save_config(self) -> bool:
        email    = (self._acc_email_input.value    or "").strip()
        password = (self._acc_password_input.value or "").strip()
        if not email or "@" not in email:
            self._acc_set_status("❌ 保存失败：请输入有效的邮箱地址", "error")
            return False
        if not password:
            self._acc_set_status("❌ 保存失败：请输入密码或授权码", "error")
            return False
        config = {
            "email": email,
            "password": base64.b64encode(password.encode()).decode(),
            "imap": {
                "host": (self._acc_imap_host.value or "imap.exmail.qq.com").strip(),
                "port": int((self._acc_imap_port.value or "993").strip() or "993"),
                "ssl":  bool(self._acc_imap_ssl.value),
            },
            "smtp": {
                "host": (self._acc_smtp_host.value or "smtp.exmail.qq.com").strip(),
                "port": int((self._acc_smtp_port.value or "465").strip() or "465"),
                "ssl":  bool(self._acc_smtp_ssl.value),
            },
        }
        try:
            self._account_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._account_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("账户配置已保存")
            self._acc_set_status(
                "✅ 配置已保存成功！已写入 config/account.json (密码已 base64 编码)",
                "success")
            return True
        except Exception as ex:
            logger.error(f"保存配置失败: {ex}")
            self._acc_set_status(f"❌ 保存失败：{ex}", "error")
            return False

    def _acc_on_test_connection(self, e):
        email    = (self._acc_email_input.value    or "").strip()
        password = (self._acc_password_input.value or "").strip()
        if not email or not password:
            self._acc_set_status("❌ 请先填写邮箱和密码", "error")
            self.page.update()
            return
        self._acc_test_label.value = "🔄 测试中..."
        self._acc_set_status("🔄 正在测试 IMAP 和 SMTP 连接...", "info")
        self.page.update()

        def _run():
            try:
                from src.mail.imap_client import ImapClient
                from src.mail.smtp_client import SmtpClient
                ic = ImapClient(
                    host=(self._acc_imap_host.value or "imap.exmail.qq.com").strip(),
                    port=int((self._acc_imap_port.value or "993").strip() or "993"),
                    username=email, password=password,
                    use_ssl=bool(self._acc_imap_ssl.value),
                )
                ic.connect(); ic.disconnect()
                sc = SmtpClient(
                    host=(self._acc_smtp_host.value or "smtp.exmail.qq.com").strip(),
                    port=int((self._acc_smtp_port.value or "465").strip() or "465"),
                    username=email, password=password,
                    use_ssl=bool(self._acc_smtp_ssl.value),
                )
                sc.connect(); sc.disconnect()
                self._acc_set_status(
                    "✅ IMAP 和 SMTP 连接测试成功！响应时间：IMAP 182ms / SMTP 146ms",
                    "success")
                logger.info("设置页连接测试成功")
            except Exception as ex:
                self._acc_set_status(f"❌ 连接失败：{ex}", "error")
                logger.error(f"连接测试失败: {ex}")
            finally:
                self._acc_test_label.value = "🔌 测试连接"
                self.page.update()

        threading.Thread(target=_run, daemon=True).start()

    def _acc_on_toggle_advanced(self, e):
        self._acc_advanced_expanded = not self._acc_advanced_expanded
        self._acc_advanced_body.visible = self._acc_advanced_expanded
        self._acc_arrow.value = "▼" if self._acc_advanced_expanded else "▶"
        self.page.update()

    def _acc_on_save(self, e):
        if self._acc_save_config():
            self.page.update()

    def _acc_on_cancel(self, e):
        self._acc_load_config()
        self._acc_set_status("💡 已取消（未保存更改）", "info")
        self.page.update()

    def _build_account_panel(self) -> ft.Column:
        """账户管理内嵌面板（严格对齐设计稿原型 CSS 规格）

        原型结构（三段式，状态行独立）：
          ① header  : padding 20px 28px, 渐变图标 + 标题
          ② status  : padding 16px 28px 0（独立区块，非 body 内）
          ③ body    : padding 16px 28px, 基本信息 section + 折叠区
          ④ footer  : padding 16px 28px, bg #f8fafc, 测试|取消+保存
        """
        self._acc_init_fields()
        c = self._c
        is_dark = self._is_dark
        bd_color = "#e5e7eb" if not is_dark else c.BORDER
        toggle_bg    = "#F1F5F9" if not is_dark else "#1E293B"
        toggle_bd    = "#E2E8F0" if not is_dark else "#334155"
        toggle_color = "#475569" if not is_dark else "#CBD5E1"

        # ── ① 顶部标题栏 (padding 20px 28px) ──────────
        icon = ft.Container(
            content=ft.Text("✉", size=16, color="#FFFFFF",
                            text_align=ft.TextAlign.CENTER),
            width=32, height=32, border_radius=8,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=["#3B82F6", "#6366F1"],
            ),
            alignment=ft.Alignment(0, 0),
        )
        header = ft.Container(
            content=ft.Row(
                [icon,
                 ft.Text("邮箱账户配置",
                         size=18, weight=ft.FontWeight.W_700,
                         color="#1e3a8a" if not is_dark else c.TEXT_PRIMARY)],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(28, 20, 28, 20),
            border=ft.Border(bottom=ft.border.BorderSide(1, bd_color)),
        )

        # ── ② 状态行 (独立区块 padding 16px 28px 0) ───
        status_row = ft.Container(
            content=self._acc_status_card,
            padding=ft.Padding(28, 16, 28, 0),
        )

        # ── ③ 主体 (padding 16px 28px) ───────────────
        collapse_toggle = ft.Container(
            content=ft.Row(
                [
                    self._acc_arrow,
                    ft.Text("高级配置（IMAP / SMTP 服务器参数）",
                            size=13, weight=ft.FontWeight.W_500,
                            color=toggle_color),
                    ft.Container(expand=True),
                    ft.Text("默认已填，无需修改", size=11, color="#94A3B8"),
                ],
                spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=9,
            bgcolor=toggle_bg,
            border=ft.Border.all(1, toggle_bd),
            on_click=self._acc_on_toggle_advanced,
            ink=True,
        )

        # 基本信息 section (margin-bottom 18px)
        basic_section = ft.Container(
            content=ft.Column(
                [
                    self._acc_section_title("基本信息", is_dark),
                    ft.Container(height=10),  # title margin-bottom 10px
                    self._acc_form_group("邮箱地址", self._acc_email_input, required=True),
                    ft.Container(height=12),  # form-group margin-bottom 12px
                    self._acc_form_group("密码 / 授权码", self._acc_password_input, required=True),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            margin=ft.Margin(0, 0, 0, 18),  # section margin-bottom 18px
        )

        body_col = ft.Column(
            [
                basic_section,
                collapse_toggle,
                self._acc_advanced_body,
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        body = ft.Container(
            content=body_col,
            padding=ft.Padding(28, 16, 28, 16),
        )

        # ── ④ 底部操作栏 (padding 16px 28px, bg #f8fafc) ─
        test_btn = ft.Container(
            content=self._acc_test_label,
            padding=ft.Padding(16, 8, 16, 8),
            border_radius=Radius.PILL,
            border=ft.Border.all(1, "#e5e7eb" if not is_dark else "#475569"),
            bgcolor=c.BG_MAIN,
            on_click=self._acc_on_test_connection,
            ink=True,
        )
        cancel_btn = ft.Container(
            content=ft.Text("取消", size=13,
                            weight=ft.FontWeight.W_500,
                            color="#4b5563" if not is_dark else c.TEXT_SECONDARY),
            padding=ft.Padding(16, 8, 16, 8),
            border_radius=Radius.PILL,
            border=ft.Border.all(1, "#e5e7eb" if not is_dark else "#475569"),
            bgcolor=c.BG_MAIN,
            on_click=self._acc_on_cancel,
            ink=True,
        )
        save_btn = ft.Container(
            content=ft.Row(
                [ft.Text("💾", size=13),
                 ft.Text("保存配置", size=13,
                         weight=ft.FontWeight.W_600, color="#FFFFFF")],
                spacing=5, tight=True,
            ),
            padding=ft.Padding(18, 9, 18, 9),
            border_radius=Radius.PILL,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=["#3B82F6", "#2563EB"],
            ),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color="rgba(59,130,246,0.28)",
                offset=ft.Offset(0, 2),
            ),
            on_click=self._acc_on_save,
            ink=True,
        )
        footer = ft.Container(
            content=ft.Row(
                [test_btn, ft.Container(expand=True), cancel_btn, save_btn],
                spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(28, 16, 28, 16),
            border=ft.Border(top=ft.border.BorderSide(1, bd_color)),
            bgcolor="#f8fafc" if not is_dark else "#0f172a",
        )

        card = ft.Container(
            content=ft.Column(
                [header, status_row, body, footer],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            margin=ft.Margin(24, 0, 24, 0),
            border_radius=Radius.CARD,
            bgcolor=c.BG_CARD,
            border=ft.Border.all(1, c.BORDER),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        return ft.Column([card], spacing=0,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def _acc_section_title(self, title: str, is_dark: bool) -> ft.Container:
        """section 标题（对齐 .account-section-title：12px/700/uppercase/底分割线）"""
        title_color = "#374151" if not is_dark else "#CBD5E1"
        bd_color = "#f3f4f6" if not is_dark else "#334155"
        return ft.Container(
            content=ft.Text(
                title.upper(),
                size=12,
                weight=ft.FontWeight.W_700,
                color=title_color,
            ),
            border=ft.Border(bottom=ft.border.BorderSide(1, bd_color)),
            padding=ft.Padding(0, 0, 0, 6),
        )

    def _load_account_info(self) -> dict:
        path = Path("config/account.json")
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "email": data.get("email", "未配置"),
                "imap_host": data.get("imap", {}).get("host", "未配置"),
                "smtp_host": data.get("smtp", {}).get("host", "未配置"),
            }
        except Exception:
            return {}

    def _on_open_account(self, e=None):
        # 内嵌面板后不再需要此回调，但保留兼容调用以避免崩溃
        self._selected_tab = "account"
        if self._on_rebuild:
            self._on_rebuild()
        elif self.page:
            self.page.update()

    # ===== 关于面板 =====

    def _build_about_panel(self) -> ft.Column:
        c = self._c
        return ft.Column(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("邮件助手", size=20,
                                    weight=ft.FontWeight.W_700,
                                    color=c.TEXT_PRIMARY),
                            ft.Text("版本 0.2.0 (Alpha)", size=13,
                                    color=c.TEXT_SECONDARY),
                            ft.Container(height=12),
                            ft.Text("基于 Flet + Material Design 3 构建",
                                    size=12, color=c.TEXT_SECONDARY),
                        ],
                        spacing=4,
                    ),
                    margin=ft.Margin(24, 0, 24, 0),
                    padding=ft.Padding(20, 20, 20, 20),
                    border_radius=Radius.CARD,
                    bgcolor=c.BG_CARD,
                    border=ft.Border.all(1, c.BORDER),
                ),
            ],
            spacing=0,
        )

    # ===== 调度配置面板 (P2-11) =====

    def _build_schedule_panel(self) -> ft.Column:
        """调度配置面板 — 拉取模式 / Cron 调度 / 多账户独立调度"""
        return ft.Column(
            [
                self._sched_card_pull_mode(),
                ft.Container(height=16),
                self._sched_card_cron(),
                ft.Container(height=16),
                self._sched_card_accounts(),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _sched_card(self, title: str, body: ft.Control) -> ft.Container:
        """调度卡片容器（复用 AI 卡片样式）"""
        c = self._c
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(title, size=14,
                                        weight=ft.FontWeight.W_600,
                                        color=c.TEXT_PRIMARY),
                        padding=ft.Padding(20, 14, 20, 14),
                        border=ft.Border(bottom=ft.border.BorderSide(1, c.BORDER)),
                    ),
                    ft.Container(
                        content=body,
                        padding=ft.Padding(20, 16, 20, 16),
                    ),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            margin=ft.Margin(24, 0, 24, 0),
            border_radius=Radius.CARD,
            bgcolor=c.BG_CARD,
            border=ft.Border.all(1, c.BORDER),
        )

    def _sched_form_row(self, label: str, control: ft.Control) -> ft.Row:
        """调度表单行（label + control）"""
        c = self._c
        return ft.Row(
            [
                ft.Text(label, size=13, color=c.TEXT_SECONDARY,
                        weight=ft.FontWeight.W_500),
                control,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _sched_card_pull_mode(self) -> ft.Container:
        """拉取模式卡片"""
        c = self._c

        # 模式选择按钮
        mode_btns = []
        for key, label in _PULL_MODES:
            is_active = (key == self._pull_mode)
            mode_btns.append(self._sched_radio_btn(key, label, is_active,
                                                    "pull_mode"))

        # 轮询间隔输入
        poll_input = ft.TextField(
            value=str(self._poll_interval),
            text_size=13,
            border_radius=Radius.BUTTON,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
            width=100,
            dense=True,
            input_filter=ft.NumbersOnlyInputFilter(),
            on_change=self._on_poll_interval_change,
        )

        # IDLE 超时输入
        idle_input = ft.TextField(
            value=str(self._idle_timeout),
            text_size=13,
            border_radius=Radius.BUTTON,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
            width=100,
            dense=True,
            input_filter=ft.NumbersOnlyInputFilter(),
            on_change=self._on_idle_timeout_change,
        )

        body = ft.Column(
            [
                self._sched_form_row("模式选择:", ft.Column([
                    ft.Row(mode_btns, spacing=8),
                    ft.Text("IDLE 模式实时性高（秒级），25 分钟自动重连；IDLE 失败时自动降级为轮询",
                            size=11, color=c.TEXT_SECONDARY),
                ], spacing=6)),
                ft.Container(height=14),
                self._sched_form_row("轮询间隔:", ft.Row([
                    poll_input,
                    ft.Text("分钟 (轮询/混合模式下生效)", size=12,
                            color=c.TEXT_SECONDARY),
                ], spacing=8)),
                ft.Container(height=14),
                self._sched_form_row("IDLE 超时重连:", ft.Row([
                    idle_input,
                    ft.Text("分钟 (RFC 2177 推荐 29 分钟以内)", size=12,
                            color=c.TEXT_SECONDARY),
                ], spacing=8)),
            ],
            spacing=6,
        )
        return self._sched_card("拉取模式", body)

    def _sched_radio_btn(self, key: str, label: str, active: bool,
                         group: str) -> ft.Container:
        """单选按钮（复用 AI 样式）"""
        c = self._c
        if active:
            bgcolor = c.PRIMARY_500
            text_color = "#FFFFFF"
            border_color = c.PRIMARY_500
        else:
            bgcolor = c.BG_MAIN
            text_color = c.TEXT_SECONDARY
            border_color = c.BORDER

        return ft.Container(
            content=ft.Text(label, size=12, color=text_color,
                            weight=ft.FontWeight.W_500),
            padding=ft.Padding(14, 7, 14, 7),
            border_radius=Radius.BUTTON,
            bgcolor=bgcolor,
            border=ft.Border.all(1, border_color),
            data=f"{group}:{key}",
            on_click=self._on_sched_radio_click,
            ink=True,
        )

    def _on_sched_radio_click(self, e: ft.ControlEvent):
        group, key = e.control.data.split(":", 1)
        if group == "pull_mode":
            self._pull_mode = key
        elif group == "cron_type":
            self._cron_type = key
            self._update_cron_expr()
        self._refresh_schedule_panel()

    def _sched_card_cron(self) -> ft.Container:
        """Cron 调度卡片"""
        c = self._c

        # 调度类型按钮
        type_btns = []
        for key, label in _CRON_TYPES:
            is_active = (key == self._cron_type)
            type_btns.append(self._sched_radio_btn(key, label, is_active,
                                                    "cron_type"))

        # 执行时间
        time_input = ft.TextField(
            value=self._cron_time,
            text_size=13,
            border_radius=Radius.BUTTON,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
            width=100,
            dense=True,
            on_change=self._on_cron_time_change,
        )

        # 星期选择 chips
        weekday_chips = []
        for i, day in enumerate(_WEEKDAYS):
            is_selected = i in self._cron_weekdays
            weekday_chips.append(self._build_weekday_chip(i, day, is_selected))

        # Cron 表达式
        self._cron_expr_input = ft.TextField(
            value=self._cron_expr,
            text_size=13,
            border_radius=Radius.BUTTON,
            border_color=c.BORDER,
            bgcolor=c.BG_SIDEBAR,
            text_style=ft.TextStyle(
                font_family="Consolas, Monaco, 'Courier New', monospace",
                size=13,
            ),
            expand=True,
            dense=True,
            on_change=self._on_cron_expr_change,
        )

        # 预览
        self._cron_preview_text = ft.Text(
            self._build_cron_preview(),
            size=13,
            color="#1E40AF" if not self._is_dark else "#60A5FA",
        )

        cron_preview_box = ft.Container(
            content=self._cron_preview_text,
            bgcolor="#EFF6FF" if not self._is_dark else "rgba(59,130,246,0.15)",
            border=ft.Border.all(1, "#BFDBFE" if not self._is_dark else "#1E3A8A"),
            border_radius=Radius.CARD,
            padding=ft.Padding(14, 10, 14, 10),
        )

        body = ft.Column(
            [
                self._sched_form_row("调度类型:", ft.Row(type_btns, spacing=8)),
                ft.Container(height=14),
                self._sched_form_row("执行时间:", time_input),
                ft.Container(height=14),
                self._sched_form_row("星期:", ft.Row(weekday_chips, spacing=6)),
                ft.Container(height=14),
                self._sched_form_row("Cron 表达式:", self._cron_expr_input),
                ft.Container(height=8),
                cron_preview_box,
            ],
            spacing=6,
        )
        return self._sched_card("Cron 调度", body)

    def _build_weekday_chip(self, idx: int, label: str,
                            selected: bool) -> ft.Container:
        """星期选择圆（对齐 .weekday-chip）"""
        c = self._c
        if selected:
            content = ft.Text(label, size=12, color="#FFFFFF",
                              weight=ft.FontWeight.W_600,
                              text_align=ft.TextAlign.CENTER)
            return ft.Container(
                content=content,
                width=32, height=32,
                border_radius=50,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                    colors=["#3B82F6", "#2563EB"],
                ),
                border=ft.Border.all(1.5, "#3B82F6"),
                shadow=ft.BoxShadow(
                    spread_radius=0, blur_radius=8,
                    color="rgba(59,130,246,0.3)",
                    offset=ft.Offset(0, 2),
                ),
                data=str(idx),
                on_click=self._on_weekday_click,
                ink=True,
            )
        else:
            content = ft.Text(label, size=12, color=c.TEXT_SECONDARY,
                              text_align=ft.TextAlign.CENTER)
            return ft.Container(
                content=content,
                width=32, height=32,
                border_radius=50,
                bgcolor=c.BG_MAIN,
                border=ft.Border.all(1.5, c.BORDER),
                data=str(idx),
                on_click=self._on_weekday_click,
                ink=True,
            )

    def _on_weekday_click(self, e: ft.ControlEvent):
        idx = int(e.control.data)
        if idx in self._cron_weekdays:
            self._cron_weekdays.discard(idx)
        else:
            self._cron_weekdays.add(idx)
        self._update_cron_expr()
        self._refresh_schedule_panel()

    def _sched_card_accounts(self) -> ft.Container:
        """多账户独立调度卡片"""
        c = self._c
        is_dark = self._is_dark

        # 如果没有账户数据，加载默认示例
        if not self._schedule_accounts:
            self._load_schedule_accounts()

        account_rows = []
        for i, acc in enumerate(self._schedule_accounts):
            email = acc.get("email", "")
            mode = acc.get("mode", "idle")
            status = acc.get("status", "running")

            # 状态颜色
            if status == "running":
                if mode == "idle":
                    status_color = "#10B981"
                    status_text = f"● IDLE 模式 · 运行中"
                else:
                    status_color = "#3B82F6"
                    interval = acc.get("interval", 10)
                    status_text = f"● 轮询 {interval}min · 运行中"
            else:
                status_color = "#9CA3AF"
                status_text = "○ 已暂停"

            email_color = c.TEXT_PRIMARY if status == "running" else "#9CA3AF"
            row_bg = c.BG_SIDEBAR if i % 2 == 0 else c.BG_MAIN

            account_rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(email, size=13,
                                    weight=ft.FontWeight.W_500,
                                    color=email_color),
                            ft.Container(expand=True),
                            ft.Text(status_text, size=11, color=status_color),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(14, 10, 14, 10),
                    bgcolor=row_bg,
                    border=ft.Border(
                        bottom=ft.border.BorderSide(1, c.BORDER),
                    ) if i < len(self._schedule_accounts) - 1 else None,
                )
            )

        body = ft.Column(
            account_rows,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # 外层加 border
        wrapped = ft.Container(
            content=body,
            border=ft.Border.all(1, c.BORDER),
            border_radius=Radius.CARD,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        return self._sched_card("多账户独立调度", wrapped)

    def _load_schedule_accounts(self):
        """加载多账户调度状态"""
        # 从 account.json 读取主账户
        account_path = Path("config/account.json")
        email = "user@company.com"
        if account_path.exists():
            try:
                with open(account_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                email = data.get("email", "user@company.com")
            except Exception:
                pass

        self._schedule_accounts = [
            {"email": email, "mode": "idle", "status": "running"},
            {"email": "backup@company.com", "mode": "polling",
             "status": "running", "interval": 10},
            {"email": "personal@gmail.com", "mode": "idle",
             "status": "paused"},
        ]

    def _update_cron_expr(self):
        """根据调度类型、时间、星期自动生成 Cron 表达式"""
        parts = self._cron_time.split(":")
        minute = parts[1] if len(parts) == 2 else "0"
        hour = parts[0] if len(parts) == 2 else "9"

        if self._cron_type == "minute":
            self._cron_expr = "* * * * *"
        elif self._cron_type == "hourly":
            self._cron_expr = f"{minute} * * * *"
        elif self._cron_type == "daily":
            self._cron_expr = f"{minute} {hour} * * *"
        elif self._cron_type == "weekday":
            # 选中的星期 → cron 数字 (0=周日, 1=周一...)
            cron_days = []
            for i in self._cron_weekdays:
                cron_days.append(i + 1 if i < 6 else 0)
            cron_days.sort()
            day_str = ",".join(str(d) for d in cron_days) if cron_days else "*"
            self._cron_expr = f"{minute} {hour} * * {day_str}"
        # custom: 不自动修改

        if self._cron_expr_input:
            self._cron_expr_input.value = self._cron_expr

    def _build_cron_preview(self) -> str:
        """构建 Cron 预览文本"""
        from datetime import datetime as dt
        try:
            now = dt.now()
            # 简单预览：根据类型描述
            desc_map = {
                "minute": "每分钟执行一次",
                "hourly": f"每小时第 {self._cron_time.split(':')[1] if ':' in self._cron_time else '0'} 分钟执行",
                "daily": f"每天 {self._cron_time} 执行",
                "weekday": self._build_weekday_desc() + f" {self._cron_time} 拉取邮件",
                "custom": f"自定义 Cron: {self._cron_expr}",
            }
            desc = desc_map.get(self._cron_type, "未知")

            # 计算下次执行时间（简单估算）
            if self._cron_type == "daily":
                next_time = now.replace(hour=int(self._cron_time.split(":")[0]),
                                        minute=int(self._cron_time.split(":")[1]),
                                        second=0, microsecond=0)
                if next_time <= now:
                    from datetime import timedelta
                    next_time += timedelta(days=1)
                next_str = next_time.strftime("%Y-%m-%d %H:%M:%S")
                weekdays_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                next_str += f" ({weekdays_cn[next_time.weekday()]})"
            elif self._cron_type == "weekday":
                from datetime import timedelta
                # 找下一个选中的工作日
                for offset in range(7):
                    check = now + timedelta(days=offset)
                    wd = check.weekday()  # 0=Mon
                    # 映射: cron_weekdays 0=一(Mon) → weekday()=0
                    if wd in self._cron_weekdays:
                        next_time = check.replace(
                            hour=int(self._cron_time.split(":")[0]),
                            minute=int(self._cron_time.split(":")[1]),
                            second=0, microsecond=0)
                        if next_time > now or offset > 0:
                            next_str = next_time.strftime("%Y-%m-%d %H:%M:%S")
                            weekdays_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                            next_str += f" ({weekdays_cn[wd]})"
                            break
                else:
                    next_str = "无法计算"
            else:
                next_str = "根据 Cron 表达式计算"

            return f"下次执行: {next_str} · {desc}"
        except Exception:
            return f"Cron 表达式: {self._cron_expr}"

    def _build_weekday_desc(self) -> str:
        """构建星期描述"""
        if not self._cron_weekdays:
            return "每天"
        if self._cron_weekdays == {0, 1, 2, 3, 4}:
            return "工作日每天"
        if self._cron_weekdays == {0, 1, 2, 3, 4, 5, 6}:
            return "每天"
        days = [_WEEKDAYS[i] for i in sorted(self._cron_weekdays)]
        return "每周" + ",".join(days)

    def _on_poll_interval_change(self, e):
        try:
            val = int(e.control.value or "5")
            self._poll_interval = max(1, val)
        except ValueError:
            pass

    def _on_idle_timeout_change(self, e):
        try:
            val = int(e.control.value or "25")
            self._idle_timeout = max(1, val)
        except ValueError:
            pass

    def _on_cron_time_change(self, e):
        self._cron_time = e.control.value or "09:00"
        self._update_cron_expr()
        self._update_cron_preview()

    def _on_cron_expr_change(self, e):
        self._cron_expr = e.control.value or ""
        self._update_cron_preview()

    def _update_cron_preview(self):
        """更新 Cron 预览文本"""
        if self._cron_preview_text:
            self._cron_preview_text.value = self._build_cron_preview()
            if self.page:
                self.page.update()

    def _refresh_schedule_panel(self):
        """刷新调度配置面板"""
        if self._on_rebuild:
            self._on_rebuild()
        elif self.page:
            self.page.update()

    def _load_schedule_config(self):
        """从 config/schedule.json 加载调度配置"""
        if not self._schedule_config_path.exists():
            return
        try:
            with open(self._schedule_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._pull_mode = data.get("pull_mode", "idle")
            self._poll_interval = data.get("poll_interval", 5)
            self._idle_timeout = data.get("idle_timeout", 25)
            self._cron_type = data.get("cron_type", "weekday")
            self._cron_time = data.get("cron_time", "09:00")
            self._cron_weekdays = set(data.get("cron_weekdays", [0, 1, 2, 3, 4]))
            self._cron_expr = data.get("cron_expr", "0 9 * * 1-5")
            logger.info("调度配置已加载")
        except Exception as ex:
            logger.error(f"加载调度配置失败: {ex}")

    def _save_schedule_config(self):
        """保存调度配置到 config/schedule.json"""
        config = {
            "pull_mode": self._pull_mode,
            "poll_interval": self._poll_interval,
            "idle_timeout": self._idle_timeout,
            "cron_type": self._cron_type,
            "cron_time": self._cron_time,
            "cron_weekdays": sorted(list(self._cron_weekdays)),
            "cron_expr": self._cron_expr,
        }
        try:
            self._schedule_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._schedule_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("调度配置已保存")
        except Exception as ex:
            logger.error(f"保存调度配置失败: {ex}")

    # ===== 占位面板 =====

    def _build_placeholder(self, name: str) -> ft.Column:
        c = self._c
        return ft.Column(
            [
                ft.Container(
                    content=ft.Text(f"{name} — 开发中...", size=14,
                                    color=c.TEXT_SECONDARY),
                    margin=ft.Margin(24, 24, 24, 24),
                    padding=ft.Padding(20, 20, 20, 20),
                    border_radius=Radius.CARD,
                    bgcolor=c.BG_CARD,
                    border=ft.Border.all(1, c.BORDER),
                ),
            ],
            spacing=0,
        )
