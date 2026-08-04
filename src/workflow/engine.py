"""流程执行引擎 WorkflowEngine

职责：
1. 匹配流程：根据 enabled + trigger 条件筛选匹配的流程，按 match_mode 调度
   - all（默认）：所有匹配流程都执行
   - first_match：按 priority 降序仅执行第一个匹配流程
   - priority_order：按 priority 降序顺序执行，前一个失败则不执行后续
2. 执行流程：异步线程内同步执行步骤循环，写执行记录，持久化 context 快照
3. 断点续传：从 snapshot 恢复 Context，从指定步骤继续执行
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any

from src.core.logger import get_logger
from src.workflow.context import WorkflowContext
from src.workflow.executor import StepExecutor
from src.workflow.loader import WorkflowLoader

logger = get_logger("workflow.engine")


class WorkflowEngine:
    """流程执行引擎入口。"""

    def __init__(
        self,
        loader: WorkflowLoader,
        execution_repo,
        secret_mgr,
        notification_engine,
        llm_client,
        smtp_client,
        mail_repository,
        imap_client,
    ):
        """初始化引擎。

        Args:
            loader: 流程加载器。
            execution_repo: 执行记录仓储。
            secret_mgr: 密钥管理器。
            notification_engine: 通知引擎（notify Action 依赖）。
            llm_client: LLM 客户端（extract_info/summarize Action 依赖）。
            smtp_client: SMTP 客户端（auto_reply/forward Action 依赖）。
            mail_repository: 邮件仓储（tag/move_to_folder Action 依赖）。
            imap_client: IMAP 客户端（move_to_folder Action 依赖）。
        """
        self.loader = loader
        self.execution_repo = execution_repo
        self.secret_mgr = secret_mgr
        self.notification_engine = notification_engine
        self.llm_client = llm_client
        self.smtp_client = smtp_client
        self.mail_repository = mail_repository
        self.imap_client = imap_client

        action_deps = {
            "notification_engine": notification_engine,
            "llm_client": llm_client,
            "smtp_client": smtp_client,
            "mail_repository": mail_repository,
            "imap_client": imap_client,
            "execution_repo": execution_repo,
            "secret_mgr": secret_mgr,
        }
        self.executor = StepExecutor(action_deps)

    # ------------------------------------------------------------------
    # 匹配并执行
    # ------------------------------------------------------------------
    def match_and_run(
        self, mail, classify_result: dict, account_id: str = "default"
    ) -> list[str]:
        """匹配 enabled 且 trigger 满足的流程，按 match_mode 调度执行。

        Args:
            mail: MailData 邮件对象。
            classify_result: 分类结果字典。
            account_id: 账户 ID（用于多账户隔离，Alpha 默认 default）。

        Returns:
            execution_id 列表。
        """
        try:
            workflows = self.loader.list_workflows()
        except Exception as exc:
            logger.error(f"列出流程失败: {exc}")
            return []

        matched: list[tuple[int, dict]] = []
        match_mode = "all"
        for wf_meta in workflows:
            if not wf_meta.get("enabled", True):
                continue
            name = wf_meta.get("name")
            if not name:
                continue
            try:
                wf_def = self.loader.load_workflow(name)
            except Exception as exc:
                logger.error(f"加载流程 {name} 失败: {exc}")
                continue
            if not self._matches_trigger(wf_def, mail, classify_result):
                continue
            priority = wf_def.get("trigger", {}).get("priority", 0) or 0
            matched.append((priority, wf_def))
            # match_mode 以第一个匹配流程的配置为准（同一批应保持一致）
            if match_mode == "all":
                match_mode = wf_def.get("trigger", {}).get("match_mode", "all")

        if not matched:
            logger.info("无匹配的流程")
            return []

        # 按 priority 降序
        matched.sort(key=lambda x: x[0], reverse=True)
        execution_ids: list[str] = []

        if match_mode == "first_match":
            matched = matched[:1]

        if match_mode == "priority_order":
            for _, wf_def in matched:
                try:
                    eid = self.run_workflow(
                        wf_def.get("name", ""), mail, classify_result
                    )
                    execution_ids.append(eid)
                except Exception as exc:
                    logger.error(
                        f"流程 {wf_def.get('name')} 执行失败，priority_order 模式停止后续: {exc}"
                    )
                    break
            return execution_ids

        # all
        for _, wf_def in matched:
            try:
                eid = self.run_workflow(
                    wf_def.get("name", ""), mail, classify_result
                )
                execution_ids.append(eid)
            except Exception as exc:
                logger.error(f"流程 {wf_def.get('name')} 启动失败: {exc}")
        return execution_ids

    # ------------------------------------------------------------------
    # 手动执行指定流程
    # ------------------------------------------------------------------
    def run_workflow(
        self,
        workflow_name: str,
        mail,
        classify_result: dict,
        force_version: str | None = None,
    ) -> str:
        """手动执行指定流程，返回 execution_id。

        异步执行：内部起 daemon 线程，不阻塞调用方。
        """
        wf_def = self.loader.load_workflow(workflow_name, force_version)
        execution_id = self._gen_execution_id(workflow_name)
        variables = dict(wf_def.get("variables", {}) or {})
        ctx = WorkflowContext(mail, classify_result, variables, self.secret_mgr)
        version = str(wf_def.get("version", "1.0"))

        # 创建执行记录
        mail_id = getattr(mail, "message_id", "") or ""
        try:
            self.execution_repo.create_record(
                execution_id, mail_id, workflow_name, version
            )
        except Exception as exc:
            logger.warning(f"创建执行记录失败: {exc}")

        thread = threading.Thread(
            target=self._safe_execute_sync,
            args=(wf_def, ctx, execution_id),
            daemon=True,
            name=f"workflow-{execution_id}",
        )
        thread.start()
        logger.info(
            f"流程 {workflow_name}@{version} 启动 execution_id={execution_id}"
        )
        return execution_id

    # ------------------------------------------------------------------
    # 同步执行（线程入口）
    # ------------------------------------------------------------------
    def _safe_execute_sync(self, wf_def: dict, ctx: WorkflowContext, execution_id: str) -> None:
        """线程入口：捕获所有异常，更新执行记录状态。"""
        try:
            self._execute_sync(wf_def, ctx, execution_id)
        except Exception as exc:
            logger.exception(f"流程执行异常 execution_id={execution_id}: {exc}")
            self._safe_update_status(
                execution_id, "failed", error_message=str(exc)
            )

    def _execute_sync(self, wf_def: dict, ctx: WorkflowContext, execution_id: str) -> None:
        """同步执行流程：建记录 → 步骤循环 → 更新记录。"""
        self._safe_update_status(execution_id, "running")
        steps = wf_def.get("steps", []) or []
        step_results: list[dict] = []
        step_index = {s.get("id"): s for s in steps if s.get("id")}
        current_step = steps[0] if steps else None
        visited: set[str] = set()

        while current_step is not None:
            step_id = current_step.get("id", "") or ""
            if step_id and step_id in visited:
                logger.warning(f"检测到步骤循环引用: {step_id}，停止执行")
                break
            if step_id:
                visited.add(step_id)

            try:
                logger.info(
                    f"[{execution_id}] 执行步骤 [{step_id}]: {current_step.get('name', '')}"
                )
                result = self.executor.execute_step(current_step, ctx)
                step_results.append(
                    {"step_id": step_id, "status": "success", "output": result}
                )
                # 写入步骤输出别名
                output_alias = current_step.get("output")
                if output_alias and result is not None:
                    ctx.set_step_output(step_id, output_alias, result)

                # 计算下一步
                current_step = self._next_step(current_step, result, steps, step_index)
                # 持久化快照
                self._safe_update_status(
                    execution_id,
                    "running",
                    step_results=step_results,
                    context_snapshot=ctx.snapshot(),
                )
            except Exception as exc:
                logger.error(f"[{execution_id}] 步骤 [{step_id}] 执行失败: {exc}")
                step_results.append(
                    {"step_id": step_id, "status": "failed", "error": str(exc)}
                )
                self._safe_update_status(
                    execution_id,
                    "failed",
                    step_results=step_results,
                    error_message=str(exc),
                    context_snapshot=ctx.snapshot(),
                )
                # 失败时回退邮件状态
                self._safe_update_mail_status(ctx, "new")
                return

        # 正常完成
        self._safe_update_status(
            execution_id,
            "success",
            step_results=step_results,
            context_snapshot=ctx.snapshot(),
        )
        self._safe_update_mail_status(ctx, "processed")
        logger.info(f"[{execution_id}] 流程执行完成")

    # ------------------------------------------------------------------
    # 断点续传
    # ------------------------------------------------------------------
    def resume_from_step(self, execution_id: str, from_step_id: str) -> None:
        """从指定步骤恢复执行（从 from_step_id 之后继续）。

        1. 从 execution_repo 读取执行记录与 context 快照
        2. 用 WorkflowContext.from_snapshot 恢复上下文，重新注入 secret_mgr
        3. 加载当时版本的流程定义
        4. 从 from_step_id 的下一步开始执行
        """
        record = self._load_execution_record(execution_id)
        if record is None:
            logger.error(f"未找到执行记录: {execution_id}")
            return

        snapshot = record.get("context_snapshot")
        if isinstance(snapshot, str):
            import json

            try:
                snapshot = json.loads(snapshot)
            except json.JSONDecodeError:
                snapshot = None
        if not isinstance(snapshot, dict):
            logger.error(f"无法恢复：缺少 context 快照 execution_id={execution_id}")
            return

        ctx = WorkflowContext.from_snapshot(snapshot)
        ctx.secret_mgr = self.secret_mgr

        wf_name = record.get("workflow_name")
        wf_version = record.get("workflow_version")
        if not wf_name:
            logger.error("执行记录缺少 workflow_name，无法恢复")
            return
        try:
            wf_def = self.loader.load_workflow(wf_name, wf_version)
        except Exception as exc:
            logger.error(f"加载流程 {wf_name}@{wf_version} 失败: {exc}")
            return

        steps = wf_def.get("steps", []) or []
        step_index = {s.get("id"): s for s in steps if s.get("id")}

        # 定位起始步骤（from_step_id 的下一步）
        start_step = self._step_after(steps, from_step_id)
        if start_step is None:
            logger.info(
                f"[{execution_id}] from_step_id={from_step_id} 之后无更多步骤，恢复完成"
            )
            self._safe_update_status(execution_id, "success")
            return

        logger.info(
            f"[{execution_id}] 从步骤 {start_step.get('id', '')} 恢复执行"
        )
        thread = threading.Thread(
            target=self._safe_resume,
            args=(wf_def, ctx, execution_id, start_step, step_index),
            daemon=True,
            name=f"workflow-resume-{execution_id}",
        )
        thread.start()

    def _safe_resume(
        self,
        wf_def: dict,
        ctx: WorkflowContext,
        execution_id: str,
        start_step: dict | None,
        step_index: dict[str, dict],
    ) -> None:
        """resume_from_step 的线程入口。"""
        try:
            self._run_from_step(wf_def, ctx, execution_id, start_step, step_index)
        except Exception as exc:
            logger.exception(f"恢复执行异常 execution_id={execution_id}: {exc}")
            self._safe_update_status(execution_id, "failed", error_message=str(exc))

    def _run_from_step(
        self,
        wf_def: dict,
        ctx: WorkflowContext,
        execution_id: str,
        start_step: dict | None,
        step_index: dict[str, dict],
    ) -> None:
        """从指定步骤继续执行循环（复用 _execute_sync 的步骤逻辑）。"""
        self._safe_update_status(execution_id, "running")
        steps = wf_def.get("steps", []) or []
        step_results: list[dict] = []
        current_step = start_step
        visited: set[str] = set()

        while current_step is not None:
            step_id = current_step.get("id", "") or ""
            if step_id and step_id in visited:
                logger.warning(f"检测到步骤循环引用: {step_id}，停止执行")
                break
            if step_id:
                visited.add(step_id)

            try:
                logger.info(
                    f"[{execution_id}] 恢复执行步骤 [{step_id}]: {current_step.get('name', '')}"
                )
                result = self.executor.execute_step(current_step, ctx)
                step_results.append(
                    {"step_id": step_id, "status": "success", "output": result}
                )
                output_alias = current_step.get("output")
                if output_alias and result is not None:
                    ctx.set_step_output(step_id, output_alias, result)
                current_step = self._next_step(current_step, result, steps, step_index)
                self._safe_update_status(
                    execution_id,
                    "running",
                    step_results=step_results,
                    context_snapshot=ctx.snapshot(),
                )
            except Exception as exc:
                logger.error(f"[{execution_id}] 步骤 [{step_id}] 执行失败: {exc}")
                step_results.append(
                    {"step_id": step_id, "status": "failed", "error": str(exc)}
                )
                self._safe_update_status(
                    execution_id,
                    "failed",
                    step_results=step_results,
                    error_message=str(exc),
                    context_snapshot=ctx.snapshot(),
                )
                self._safe_update_mail_status(ctx, "new")
                return

        self._safe_update_status(
            execution_id,
            "success",
            step_results=step_results,
            context_snapshot=ctx.snapshot(),
        )
        self._safe_update_mail_status(ctx, "processed")
        logger.info(f"[{execution_id}] 恢复执行完成")

    # ------------------------------------------------------------------
    # 触发条件匹配
    # ------------------------------------------------------------------
    def _matches_trigger(self, wf_def: dict, mail, classify_result: dict) -> bool:
        """检查流程是否满足触发条件。"""
        trigger = wf_def.get("trigger")
        if not trigger:
            return True  # 无 trigger 视为始终匹配

        # 按分类匹配
        mail_type = trigger.get("mail_type")
        if mail_type and classify_result.get("category") != mail_type:
            return False

        # 额外条件
        conditions = trigger.get("conditions", []) or []
        if not conditions:
            return True

        variables = wf_def.get("variables", {}) or {}
        ctx = WorkflowContext(mail, classify_result, variables, self.secret_mgr)
        for cond in conditions:
            if not self._check_condition(cond, ctx):
                return False
        return True

    def _check_condition(self, cond: dict, ctx: WorkflowContext) -> bool:
        """评估单个 trigger 条件。"""
        field = cond.get("field", "")
        op = cond.get("operator", "==")
        value = cond.get("value")
        field_value = ctx.get(field)

        # value 中可能含 ${...}
        if isinstance(value, str) and "${" in value:
            value = ctx.get(value)

        try:
            if op == "==":
                return field_value == value
            if op == "!=":
                return field_value != value
            if op == "in":
                return field_value in (value or [])
            if op == "not_in":
                return field_value not in (value or [])
            if op == "contains":
                if field_value is None:
                    return False
                return value in field_value
            if op == "not_contains":
                if field_value is None:
                    return True
                return value not in field_value
            if op == ">":
                return field_value is not None and value is not None and field_value > value
            if op == "<":
                return field_value is not None and value is not None and field_value < value
            if op == ">=":
                return field_value is not None and value is not None and field_value >= value
            if op == "<=":
                return field_value is not None and value is not None and field_value <= value
            logger.warning(f"未知 trigger 操作符: {op}")
            return False
        except TypeError as exc:
            logger.warning(
                f"trigger 条件类型错误: {field_value!r} {op} {value!r}: {exc}"
            )
            return False

    # ------------------------------------------------------------------
    # 步骤导航辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _next_step(
        current_step: dict,
        result: Any,
        steps: list[dict],
        step_index: dict[str, dict],
    ) -> dict | None:
        """根据当前步骤与执行结果决定下一个步骤。"""
        # condition / switch 返回 {goto: ...}
        if isinstance(result, dict) and "goto" in result:
            goto_id = result.get("goto")
            if not goto_id:
                return None
            return step_index.get(goto_id)
        # 显式 next
        next_id = current_step.get("next")
        if next_id:
            return step_index.get(next_id)
        # 顺序下一步
        try:
            idx = steps.index(current_step)
        except ValueError:
            return None
        return steps[idx + 1] if idx + 1 < len(steps) else None

    @staticmethod
    def _step_after(steps: list[dict], from_step_id: str) -> dict | None:
        """返回 from_step_id 之后的第一个步骤。"""
        for i, step in enumerate(steps):
            if step.get("id") == from_step_id:
                return steps[i + 1] if i + 1 < len(steps) else None
        return None

    # ------------------------------------------------------------------
    # 仓储调用辅助（容错）
    # ------------------------------------------------------------------
    def _load_execution_record(self, execution_id: str) -> dict | None:
        """从 execution_repo 读取执行记录，兼容不同仓储接口。"""
        repo = self.execution_repo
        if repo is None:
            return None
        # 优先调用专用接口
        for method_name in ("get_record", "get", "find_by_id"):
            fn = getattr(repo, method_name, None)
            if fn is None:
                continue
            try:
                record = fn(execution_id)
                if record:
                    return record
            except Exception:
                continue
        # 兜底：扫描近期记录
        list_recent = getattr(repo, "list_recent", None)
        if list_recent is None:
            return None
        try:
            for r in list_recent(days=365) or []:
                if isinstance(r, dict) and r.get("id") == execution_id:
                    return r
        except Exception:
            pass
        return None

    def _safe_update_status(
        self,
        execution_id: str,
        status: str,
        step_results: list | None = None,
        error_message: str | None = None,
        context_snapshot: dict | None = None,
    ) -> None:
        """更新执行记录状态，吞掉异常避免影响主流程。"""
        if self.execution_repo is None:
            return
        update = getattr(self.execution_repo, "update_status", None)
        if update is None:
            return
        try:
            update(
                execution_id,
                status,
                step_results=step_results,
                error_message=error_message,
                context_snapshot=context_snapshot,
            )
        except Exception as exc:
            logger.warning(f"更新执行记录状态失败 execution_id={execution_id}: {exc}")

    def _safe_update_mail_status(self, ctx: WorkflowContext, status: str) -> None:
        """更新邮件状态，吞掉异常。"""
        if self.mail_repository is None:
            return
        mail_id = getattr(ctx.mail, "message_id", None) if ctx.mail else None
        if not mail_id:
            return
        update_status = getattr(self.mail_repository, "update_status", None)
        if update_status is None:
            return
        try:
            update_status(mail_id, status)
        except Exception as exc:
            logger.warning(f"更新邮件状态失败 mail_id={mail_id}: {exc}")

    @staticmethod
    def _gen_execution_id(workflow_name: str) -> str:
        """生成唯一执行 ID。"""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        safe_name = "".join(c if c.isalnum() else "_" for c in workflow_name)[:32]
        return f"exec_{ts}_{safe_name}_{short_uuid}"
