"""规则预筛引擎模块

从 rules/custom_rules.yaml 加载规则（用 PyYAML），支持 8 种条件类型与多条件 AND 组合，
规则按 priority 降序、同优先级按文件顺序匹配，命中最高优先级规则返回 RuleMatch。
内置默认规则（即使没有 custom_rules.yaml 也生效，priority=0）。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.core.logger import get_logger
from src.core.models import MailData

logger = get_logger("ai.rule_engine")


@dataclass
class RuleMatch:
    """规则命中结果"""

    category: str
    priority: str | None
    override_ai: bool
    auto_tags: list[str] = field(default_factory=list)
    matched_rule_name: str = ""
    run_workflow: str | None = None


# 内置默认规则，priority=0，即使没有 custom_rules.yaml 也生效
DEFAULT_RULES: list[dict] = [
    {
        "name": "监控告警",
        "enabled": True,
        "priority": 0,
        "condition": {
            "subject_contains": ["告警", "ALERT", "CRITICAL"],
            "sender_domain": "monitor.system",
        },
        "action": {
            "set_type": "告警类",
            "set_priority": "紧急",
            "override_ai": True,
        },
    },
    {
        "name": "审批关键词",
        "enabled": True,
        "priority": 0,
        "condition": {"subject_contains": ["审批", "请批", "申请"]},
        "action": {"set_type": "审批类", "override_ai": False},
    },
]

# 支持的 8 种条件类型
SUPPORTED_CONDITIONS: tuple[str, ...] = (
    "sender",
    "sender_domain",
    "subject_contains",
    "subject_regex",
    "body_contains",
    "has_attachment",
    "attachment_count",
    "recipient",
)


class RuleEngine:
    """规则预筛引擎"""

    def __init__(self, rules_file: Path) -> None:
        """初始化规则引擎并加载规则

        Args:
            rules_file: 规则文件路径，如 rules/custom_rules.yaml
        """
        self.rules_file: Path = Path(rules_file)
        self._rules: list[dict] = []
        self.reload()

    def reload(self) -> None:
        """重新加载规则（默认规则 + 自定义规则）"""
        rules: list[dict] = [dict(r) for r in DEFAULT_RULES]
        custom_count = 0
        if self.rules_file.exists():
            try:
                with open(self.rules_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                custom = data.get("rules", []) or []
                if isinstance(custom, list):
                    rules.extend(custom)
                    custom_count = len(custom)
                else:
                    logger.warning(
                        f"规则文件 {self.rules_file} 的 rules 字段不是列表，已忽略"
                    )
            except Exception as e:
                logger.error(f"加载规则文件失败 {self.rules_file}: {e}")
        else:
            logger.info(
                f"规则文件 {self.rules_file} 不存在，仅使用内置默认规则"
            )
        self._rules = rules
        logger.info(
            f"加载规则 {len(rules)} 条（默认 {len(DEFAULT_RULES)} + 自定义 {custom_count}）"
        )

    def match(self, mail: MailData) -> RuleMatch | None:
        """返回最高优先级命中规则，未命中返回 None

        Args:
            mail: 邮件数据

        Returns:
            最高优先级命中规则的 RuleMatch，或 None
        """
        hits = self.match_all(mail)
        return hits[0] if hits else None

    def match_all(self, mail: MailData) -> list[RuleMatch]:
        """返回所有命中规则（按优先级降序、同优先级按文件顺序）

        Args:
            mail: 邮件数据

        Returns:
            命中规则的 RuleMatch 列表，调试用
        """
        hits: list[tuple[dict, int]] = []
        for idx, rule in enumerate(self._rules):
            if not rule.get("enabled", True):
                continue
            ok, _msg = self.test_rule(rule, mail)
            if ok:
                hits.append((rule, idx))
        # priority 降序，同优先级按文件顺序（idx 升序）
        hits.sort(key=lambda x: (-int(x[0].get("priority", 0)), x[1]))
        return [self._to_rule_match(r) for r, _ in hits]

    def test_rule(self, rule: dict, mail: MailData) -> tuple[bool, str]:
        """测试单条规则是否命中

        Args:
            rule: 规则 dict
            mail: 邮件数据

        Returns:
            (是否命中, 匹配说明)
        """
        condition = rule.get("condition", {})
        if not condition:
            return True, "无条件，默认命中"
        if not isinstance(condition, dict):
            return False, f"条件格式非法: {type(condition)}"
        for cond_type, cond_value in condition.items():
            if cond_type not in SUPPORTED_CONDITIONS:
                return False, f"不支持的条件类型: {cond_type}"
            ok, msg = self._eval_single(cond_type, cond_value, mail)
            if not ok:
                return False, f"条件 [{cond_type}] 未满足: {msg}"
        return True, "全部条件满足"

    def _to_rule_match(self, rule: dict) -> RuleMatch:
        """将规则 dict 转为 RuleMatch"""
        action = rule.get("action", {}) or {}
        auto_tag = action.get("auto_tag", [])
        if isinstance(auto_tag, str):
            auto_tag = [auto_tag]
        return RuleMatch(
            category=action.get("set_type", ""),
            priority=action.get("set_priority"),
            override_ai=bool(action.get("override_ai", False)),
            auto_tags=list(auto_tag or []),
            matched_rule_name=rule.get("name", ""),
            run_workflow=action.get("run_workflow"),
        )

    # ----- 单条件评估 -----

    def _eval_single(
        self, cond_type: str, cond_value, mail: MailData
    ) -> tuple[bool, str]:
        """评估单个条件"""
        if cond_type == "sender":
            return self._match_exact(
                mail.sender, cond_value, "发件人"
            )
        if cond_type == "sender_domain":
            return self._match_exact(
                mail.sender_domain, cond_value, "发件人域名"
            )
        if cond_type == "recipient":
            return self._match_contains(
                mail.recipient, cond_value, "收件人"
            )
        if cond_type == "subject_contains":
            return self._match_contains(
                mail.subject, cond_value, "主题"
            )
        if cond_type == "subject_regex":
            return self._match_regex(
                mail.subject, cond_value, "主题"
            )
        if cond_type == "body_contains":
            return self._match_contains(
                mail.body_text or "", cond_value, "正文"
            )
        if cond_type == "has_attachment":
            return self._match_has_attachment(cond_value, mail)
        if cond_type == "attachment_count":
            return self._match_attachment_count(cond_value, mail)
        return False, f"未知条件类型: {cond_type}"

    @staticmethod
    def _as_list(value) -> list[str]:
        """将标量/列表统一为字符串列表"""
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        return [str(value)]

    def _match_exact(
        self, target: str, value, label: str
    ) -> tuple[bool, str]:
        """精确匹配（target 在 value 列表中）"""
        targets = self._as_list(value)
        hit = (target or "") in targets
        return hit, (
            f"{label}={target or '空'} {'命中' if hit else '不在'} {targets}"
        )

    def _match_contains(
        self, text: str, value, label: str
    ) -> tuple[bool, str]:
        """包含匹配（text 中包含 value 中任一关键词，大小写不敏感）"""
        keywords = self._as_list(value)
        text_lower = (text or "").lower()
        for kw in keywords:
            if kw and kw.lower() in text_lower:
                return True, f"{label}包含关键词 [{kw}]"
        return False, f"{label}不包含任一关键词 {keywords}"

    def _match_regex(
        self, text: str, pattern: str, label: str
    ) -> tuple[bool, str]:
        """正则匹配"""
        try:
            if re.search(pattern, text or ""):
                return True, f"{label}匹配正则 /{pattern}/"
            return False, f"{label}不匹配正则 /{pattern}/"
        except re.error as e:
            return False, f"正则表达式非法 /{pattern}/: {e}"

    def _match_has_attachment(
        self, value, mail: MailData
    ) -> tuple[bool, str]:
        """附件存在性匹配"""
        expected = bool(value)
        actual = len(mail.attachments) > 0
        hit = actual == expected
        return hit, (
            f"有附件={actual}, 期望={expected} {'满足' if hit else '不满足'}"
        )

    def _match_attachment_count(
        self, value, mail: MailData
    ) -> tuple[bool, str]:
        """附件数量比较匹配"""
        count = len(mail.attachments)
        # bool 是 int 子类，先排除
        if isinstance(value, bool):
            target = 1 if value else 0
            hit = count >= target
            return hit, f"附件数 {count} >= {target} {'满足' if hit else '不满足'}"
        if isinstance(value, int):
            # 裸整数表示 count > value（0 表示有附件）
            hit = count > value
            return hit, f"附件数 {count} > {value} {'满足' if hit else '不满足'}"
        if isinstance(value, str):
            m = re.match(r"\s*(>=|<=|==|!=|>|<)\s*(\d+)\s*$", value)
            if m:
                op, num = m.group(1), int(m.group(2))
                cmp_map = {
                    ">=": count >= num,
                    "<=": count <= num,
                    "==": count == num,
                    "!=": count != num,
                    ">": count > num,
                    "<": count < num,
                }
                hit = cmp_map[op]
                return hit, f"附件数 {count} {op} {num} {'满足' if hit else '不满足'}"
            # 纯数字字符串按 > 处理
            try:
                n = int(value.strip())
                hit = count > n
                return hit, f"附件数 {count} > {n} {'满足' if hit else '不满足'}"
            except ValueError:
                return False, f"无法解析 attachment_count 条件: {value!r}"
        return False, f"不支持的 attachment_count 值类型: {type(value).__name__}"
