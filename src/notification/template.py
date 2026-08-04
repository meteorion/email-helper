"""通知模板引擎"""

import re
from pathlib import Path
from typing import Any

import yaml

from src.core.logger import get_logger

logger = get_logger("notification.template")

# 匹配 {{ var | filter : arg }} 或 {{ var }}
_VAR_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


class TemplateEngine:
    """通知模板引擎

    模板语法:
      {{variable}}         → 变量替换（支持 dotted 路径，如 extracted.amount）
      {{list|join: ", "}}  → 过滤器（join/upper/lower/truncate）

    模板从 templates/*.yaml 加载，结构:
      name, type(markdown/text), content(模板字符串), mentioned(list)
    """

    def __init__(self, templates_dir: Path):
        self.templates_dir = Path(templates_dir)
        self._templates: dict[str, dict] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """加载 templates 目录下所有 YAML 模板"""
        self._templates = {}
        if not self.templates_dir.exists():
            logger.warning(f"模板目录不存在: {self.templates_dir}")
            return
        for fp in self.templates_dir.glob("*.yaml"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "name" in data:
                    self._templates[data["name"]] = data
                    logger.debug(f"已加载模板: {data['name']}")
            except Exception as e:
                logger.error(f"加载模板失败 {fp}: {e}")

    def reload(self) -> None:
        """重新加载所有模板"""
        self._load_templates()

    def list_templates(self) -> list[dict]:
        """列出所有模板摘要"""
        return [
            {
                "name": t["name"],
                "type": t.get("type", "markdown"),
                "mentioned": t.get("mentioned", []),
            }
            for t in self._templates.values()
        ]

    def render(self, template_name: str, ctx: dict) -> dict:
        """渲染模板

        Args:
            template_name: 模板名（YAML 中的 name 字段）
            ctx: 变量上下文

        Returns:
            {"type": "markdown"|"text", "content": "渲染后", "mentioned": [...]}
        """
        template = self._templates.get(template_name)
        if template is None:
            raise ValueError(f"模板不存在: {template_name}")
        content = template.get("content", "")
        rendered = self._render_content(content, ctx)
        return {
            "type": template.get("type", "markdown"),
            "content": rendered,
            "mentioned": list(template.get("mentioned", [])),
        }

    def _render_content(self, content: str, ctx: dict) -> str:
        """渲染模板字符串：变量替换 + 过滤器"""

        def replace(match: re.Match) -> str:
            expr = match.group(1).strip()
            parts = [p.strip() for p in expr.split("|")]
            value: Any = self._resolve_var(parts[0], ctx)
            for f in parts[1:]:
                value = self._apply_filter(f, value)
            return "" if value is None else str(value)

        return _VAR_PATTERN.sub(replace, content)

    def _resolve_var(self, name: str, ctx: dict) -> Any:
        """解析变量（支持 dotted 路径，如 extracted.amount）"""
        parts = name.split(".")
        value: Any = ctx
        for p in parts:
            if isinstance(value, dict) and p in value:
                value = value[p]
            else:
                return ""
        return value

    def _apply_filter(self, filter_expr: str, value: Any) -> Any:
        """应用过滤器: join / upper / lower / truncate"""
        if ":" in filter_expr:
            name, arg = filter_expr.split(":", 1)
            name = name.strip()
            arg = arg.strip()
            # 去除引号
            if len(arg) >= 2 and arg[0] in "\"'" and arg[-1] == arg[0]:
                arg = arg[1:-1]
        else:
            name = filter_expr.strip()
            arg = ""

        if name == "join":
            if isinstance(value, list):
                sep = arg if arg else ", "
                return sep.join(str(v) for v in value)
            return str(value)
        if name == "upper":
            return str(value).upper()
        if name == "lower":
            return str(value).lower()
        if name == "truncate":
            try:
                length = int(arg) if arg else 100
            except ValueError:
                length = 100
            s = str(value)
            return s[:length] + "..." if len(s) > length else s
        return value
