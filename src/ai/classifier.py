"""主分类器模块

串联规则预筛、LLM 调用、缓存、配额、反馈等组件，实现 hybrid/rule_only/ai_only/manual
四种分类模式，支持按分类 LLM 控制、配额降级、置信度自动确认与失败降级。
"""

import hashlib
import json
import re
from typing import Any, Callable, Optional

from src.ai.cache_manager import ClassifyCacheManager
from src.ai.feedback_manager import FeedbackManager
from src.ai.llm_client import LLMClient
from src.ai.llm_quota import LLMQuotaTracker
from src.ai.prompt_builder import CATEGORIES, PRIORITIES, PromptBuilder
from src.ai.rule_engine import RuleEngine, RuleMatch
from src.core.logger import get_logger
from src.core.models import MailData

logger = get_logger("ai.classifier")


# 合法分类集合（"垃圾类" 视为 "垃圾邮件" 的别名）
_VALID_CATEGORIES: set[str] = set(CATEGORIES) | {"垃圾类"}
_VALID_PRIORITIES: set[str] = set(PRIORITIES)


class AIClassifier:
    """AI 主分类器，串联规则与 LLM 完成邮件分类"""

    def __init__(
        self,
        llm: LLMClient,
        rules: RuleEngine,
        cache_mgr: ClassifyCacheManager,
        feedback_mgr: FeedbackManager,
        confidence_threshold_auto: float = 0.7,
        confidence_threshold_manual: float = 0.5,
        classify_mode: str = "hybrid",
        llm_enabled: bool = True,
        daily_llm_quota: int = 0,
        category_llm_overrides: dict | None = None,
    ) -> None:
        """初始化分类器

        Args:
            llm: LLM 客户端
            rules: 规则预筛引擎
            cache_mgr: 分类缓存管理器
            feedback_mgr: 反馈管理器
            confidence_threshold_auto: 自动确认置信度阈值
            confidence_threshold_manual: 人工确认置信度阈值
            classify_mode: 分类模式 hybrid/rule_only/ai_only/manual
            llm_enabled: LLM 全局开关
            daily_llm_quota: 每日 LLM 调用上限，0=不限
            category_llm_overrides: 按分类控制 LLM 介入，如
                {"告警类": {"use_llm": False}, "审批类": {"use_llm": True}}
        """
        if classify_mode not in ("hybrid", "rule_only", "ai_only", "manual"):
            raise ValueError(f"不支持的 classify_mode: {classify_mode}")
        self.llm: LLMClient = llm
        self.rules: RuleEngine = rules
        self.cache_mgr: ClassifyCacheManager = cache_mgr
        self.feedback_mgr: FeedbackManager = feedback_mgr
        self.confidence_threshold_auto: float = confidence_threshold_auto
        self.confidence_threshold_manual: float = confidence_threshold_manual
        self.classify_mode: str = classify_mode
        self.llm_enabled: bool = llm_enabled
        self.category_llm_overrides: dict = category_llm_overrides or {}
        self.quota_tracker: LLMQuotaTracker = LLMQuotaTracker(daily_llm_quota)
        self._prompt_builder: PromptBuilder = PromptBuilder()
        self._on_classified: Optional[Callable[[MailData, dict], None]] = None

    def set_classified_callback(
        self, callback: Callable[[MailData, dict], None]
    ) -> None:
        """延迟注入分类完成回调

        Args:
            callback: 分类完成回调，签名 callback(mail, result)
        """
        self._on_classified = callback

    def classify(
        self,
        mail: MailData,
        force_ai: bool = False,
        force_rerun: bool = False,
    ) -> dict:
        """对邮件进行分类

        Args:
            mail: 邮件数据
            force_ai: 强制走 LLM（忽略模式/规则 override/开关/配额）
            force_rerun: 忽略缓存重新分类

        Returns:
            {category, priority, need_reply, confidence, reason, source,
             auto_confirm, tags}，规则命中 run_workflow 时额外携带 run_workflow 字段
        """
        # 步骤 0：manual 模式（force_ai 时跳过）
        if not force_ai and self.classify_mode == "manual":
            result = self._build_manual_result()
            logger.info(f"邮件 {mail.message_id} 走 manual 模式，进入人工队列")
            self._trigger_callback(mail, result)
            return result

        mail_hash = self._hash_mail(mail)

        # 步骤 1：查缓存（force_rerun 时跳过）
        if not force_rerun:
            cached = self.cache_mgr.get(mail_hash)
            if cached is not None:
                cached = dict(cached)
                cached["source"] = "cache"
                cached["auto_confirm"] = (
                    cached.get("confidence", 0.0) >= self.confidence_threshold_auto
                )
                cached.setdefault("tags", [])
                logger.info(f"邮件 {mail.message_id} 命中分类缓存")
                self._trigger_callback(mail, cached)
                return cached

        # 步骤 2：规则预筛
        rule_match: RuleMatch | None = self.rules.match(mail)
        rule_tags: list[str] = list(rule_match.auto_tags) if rule_match else []

        use_rule_result: bool = False
        rule_suggestion: RuleMatch | None = None

        if force_ai:
            # 强制走 LLM，规则仅保留标签
            logger.debug(f"邮件 {mail.message_id} force_ai=True，规则仅保留标签")
        elif self.classify_mode == "ai_only":
            # ai_only：规则仅打标签，不决定分类
            logger.debug(f"邮件 {mail.message_id} ai_only 模式，规则仅打标签")
        elif rule_match is not None:
            # 检查 category_llm_overrides（优先级最高）
            override = self.category_llm_overrides.get(rule_match.category, {}) or {}
            use_llm_for_cat = override.get("use_llm")
            if use_llm_for_cat is False:
                # 该分类明确不走 LLM
                use_rule_result = True
            elif use_llm_for_cat is True:
                # 该分类必须走 LLM（即使 override_ai=True）
                rule_suggestion = rule_match
            else:
                # 无 override 配置，按 override_ai 判断
                if rule_match.override_ai:
                    use_rule_result = True
                else:
                    rule_suggestion = rule_match

        # 直接采用规则结果
        if use_rule_result and rule_match is not None:
            result = self._build_rule_result(rule_match, rule_tags)
            logger.info(
                f"邮件 {mail.message_id} 规则命中 [{rule_match.matched_rule_name}]，"
                f"source=rule"
            )
            self._trigger_callback(mail, result)
            return result

        # 步骤 3：检查 llm_enabled 与配额（force_ai 时跳过）
        if not force_ai:
            if not self.llm_enabled:
                logger.warning(
                    f"邮件 {mail.message_id} LLM 未启用，降级为规则/人工"
                )
                result = self._degrade_result(rule_suggestion, rule_tags)
                self._trigger_callback(mail, result)
                return result
            if self.classify_mode == "rule_only":
                logger.info(
                    f"邮件 {mail.message_id} rule_only 模式未命中规则或需人工，"
                    f"进入人工队列"
                )
                result = self._degrade_result(rule_suggestion, rule_tags)
                self._trigger_callback(mail, result)
                return result
            if not self.quota_tracker.check():
                logger.warning(
                    f"邮件 {mail.message_id} 今日 LLM 配额已用完 "
                    f"({self.quota_tracker.get_today_count()}/"
                    f"{self.quota_tracker.daily_quota})，降级为规则/人工"
                )
                result = self._degrade_result(rule_suggestion, rule_tags)
                self._trigger_callback(mail, result)
                return result

        # 步骤 4：调用 LLM
        llm_result: dict | None = None
        try:
            system_prompt, user_prompt = self._prompt_builder.build_classify_prompt(mail)
            response = self.llm.chat(system_prompt, user_prompt)
            llm_result = self._parse_llm_response(response)
            # 仅实际调用 LLM 时增加计数
            self.quota_tracker.increment()
        except Exception as e:
            logger.error(
                f"邮件 {mail.message_id} LLM 调用失败，降级: {e}"
            )
            result = self._degrade_result(rule_suggestion, rule_tags)
            self._trigger_callback(mail, result)
            return result

        # 步骤 4.1：规则 suggestion 与 AI 不一致 → 降低置信度
        if rule_suggestion is not None and llm_result.get("category") != rule_suggestion.category:
            original_conf = llm_result.get("confidence", 0.0)
            llm_result["confidence"] = min(original_conf, 0.85)
            logger.info(
                f"邮件 {mail.message_id} AI 分类({llm_result.get('category')}) "
                f"与规则建议({rule_suggestion.category})不一致，"
                f"置信度 {original_conf} -> {llm_result['confidence']}"
            )

        # 步骤 5：判断 auto_confirm
        confidence = float(llm_result.get("confidence", 0.0))
        auto_confirm = confidence >= self.confidence_threshold_auto

        # 合并标签（规则标签 + LLM 无标签）
        final_tags = list(dict.fromkeys(rule_tags + list(llm_result.get("tags", []))))

        result: dict[str, Any] = {
            "category": llm_result.get("category"),
            "priority": llm_result.get("priority", "普通"),
            "need_reply": bool(llm_result.get("need_reply", False)),
            "confidence": confidence,
            "reason": llm_result.get("reason", ""),
            "source": "llm",
            "auto_confirm": auto_confirm,
            "tags": final_tags,
        }
        # 规则命中的 run_workflow 透传给回调消费方
        if rule_match is not None and rule_match.run_workflow:
            result["run_workflow"] = rule_match.run_workflow

        # 步骤 6：写缓存（仅 source=llm 时写）
        try:
            self.cache_mgr.set(mail_hash, result)
        except Exception as e:
            logger.warning(f"邮件 {mail.message_id} 写缓存失败: {e}")

        logger.info(
            f"邮件 {mail.message_id} LLM 分类完成: {result['category']} "
            f"({confidence:.2f}), auto_confirm={auto_confirm}"
        )

        # 步骤 7：触发回调
        self._trigger_callback(mail, result)
        return result

    # ----- 内部辅助方法 -----

    def _trigger_callback(self, mail: MailData, result: dict) -> None:
        """触发分类完成回调（吞掉回调异常，避免影响主流程）"""
        if self._on_classified is None:
            return
        try:
            self._on_classified(mail, result)
        except Exception as e:
            logger.error(f"分类完成回调执行失败: {e}")

    def _build_manual_result(self) -> dict:
        """构建 manual 模式结果"""
        return {
            "category": None,
            "priority": None,
            "need_reply": False,
            "confidence": 0.0,
            "reason": "手动模式，等待人工分类",
            "source": "manual",
            "auto_confirm": False,
            "tags": [],
        }

    def _build_rule_result(
        self, rule_match: RuleMatch, rule_tags: list[str]
    ) -> dict:
        """构建规则命中结果"""
        result: dict[str, Any] = {
            "category": rule_match.category or None,
            "priority": rule_match.priority or "普通",
            "need_reply": False,
            "confidence": 0.95,
            "reason": f"规则命中: {rule_match.matched_rule_name}",
            "source": "rule",
            "auto_confirm": True,
            "tags": rule_tags,
        }
        if rule_match.run_workflow:
            result["run_workflow"] = rule_match.run_workflow
        return result

    def _degrade_result(
        self, rule_suggestion: RuleMatch | None, rule_tags: list[str]
    ) -> dict:
        """降级结果：有规则建议用规则(confidence-0.1)，否则进入人工"""
        if rule_suggestion is not None:
            conf = max(0.0, 0.9 - 0.1)
            result: dict[str, Any] = {
                "category": rule_suggestion.category or None,
                "priority": rule_suggestion.priority or "普通",
                "need_reply": False,
                "confidence": conf,
                "reason": f"LLM 不可用，降级使用规则建议: {rule_suggestion.matched_rule_name}",
                "source": "rule",
                "auto_confirm": conf >= self.confidence_threshold_auto,
                "tags": rule_tags,
            }
            if rule_suggestion.run_workflow:
                result["run_workflow"] = rule_suggestion.run_workflow
            return result
        # 无规则建议，进入人工
        return {
            "category": None,
            "priority": None,
            "need_reply": False,
            "confidence": 0.0,
            "reason": "LLM 不可用且无规则命中，进入人工处理",
            "source": "manual",
            "auto_confirm": False,
            "tags": rule_tags,
        }

    def _hash_mail(self, mail: MailData) -> str:
        """计算邮件内容哈希: md5(subject + sender + send_time.date + body[:100])"""
        send_date = ""
        if mail.send_time:
            send_date = mail.send_time.date().isoformat()
        body_prefix = (mail.body_text or "")[:100]
        raw = f"{mail.subject}|{mail.sender}|{send_date}|{body_prefix}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _parse_llm_response(self, response: str) -> dict:
        """解析 LLM 返回的 JSON，容错提取并校验字段

        Args:
            response: LLM 原始文本响应

        Returns:
            标准化 dict，包含 category/priority/need_reply/confidence/reason 字段。
            非法 category/priority 修正为默认值并降低 confidence 0.1。
        """
        if not response:
            logger.warning("LLM 响应为空")
            return self._default_llm_result()

        data: dict | None = None
        # 直接解析
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # 容错：从废话中提取 {...}
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    data = None

        if not isinstance(data, dict):
            logger.warning(f"LLM 响应无法解析为 JSON: {response[:200]}")
            return self._default_llm_result()

        category = str(data.get("category", "")).strip()
        priority = str(data.get("priority", "")).strip()
        need_reply = bool(data.get("need_reply", False))
        confidence = data.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        reason = str(data.get("reason", "")).strip()

        penalty = 0.0
        # 垃圾类 -> 垃圾邮件 归一化
        if category == "垃圾类":
            category = "垃圾邮件"
        if category not in _VALID_CATEGORIES:
            logger.warning(f"LLM 返回非法 category [{category}]，修正为默认")
            category = "协作类"
            penalty += 0.1
        if priority not in _VALID_PRIORITIES:
            logger.warning(f"LLM 返回非法 priority [{priority}]，修正为默认")
            priority = "普通"
            penalty += 0.1

        confidence = max(0.0, confidence - penalty)

        return {
            "category": category,
            "priority": priority,
            "need_reply": need_reply,
            "confidence": confidence,
            "reason": reason,
        }

    @staticmethod
    def _default_llm_result() -> dict:
        """LLM 解析失败时的默认结果"""
        return {
            "category": "协作类",
            "priority": "普通",
            "need_reply": False,
            "confidence": 0.4,
            "reason": "LLM 响应解析失败，使用默认结果",
        }
