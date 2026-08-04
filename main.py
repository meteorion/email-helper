"""邮件助手 Alpha - Flet 应用入口

初始化顺序（严格按依赖链，不可调换）:
 1. AppConfig
 2. 日志（含 SanitizeFilter）
 3. SecretManager
 4. 安全检查
 5. Database + Repository
 6. MigrationManager
 7. NotificationEngine
 8. LLMClient → RuleEngine → CacheManager → FeedbackManager
 9. WorkflowEngine
10. AIClassifier（延迟注入回调）
11. ConfigWatcher
12. GUI 启动
13. TaskRecovery
14. MailScheduler
15. GUI 数据加载
"""

import sys
import json
import threading
from pathlib import Path
from datetime import datetime

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import AppConfig
from src.core.logger import setup_logging, get_logger
from src.core.security.secret_manager import SecretManager
from src.core.security.log_sanitizer import SanitizeFilter
from src.core.security.security_check import run_security_checks
from src.core.storage.database import Database
from src.core.storage.mail_repository import MailRepository
from src.core.storage.cache_repository import CacheRepository
from src.core.storage.execution_repository import ExecutionRepository
from src.core.storage.task_repository import TaskRepository
from src.core.recovery.task_recovery import TaskRecovery
from src.core.cleanup_manager import CleanupManager
from src.core.config_watcher import ConfigWatcher

from src.mail.imap_client import ImapClient
from src.mail.smtp_client import SmtpClient
from src.storage.mail_store import MailStore
from src.mail.scheduler import MailScheduler

from src.ai.llm_client import LLMClient
from src.ai.rule_engine import RuleEngine
from src.ai.cache_manager import ClassifyCacheManager
from src.ai.feedback_manager import FeedbackManager
from src.ai.classifier import AIClassifier
from src.ai.llm_quota import LLMQuotaTracker

from src.workflow.engine import WorkflowEngine
from src.workflow.loader import WorkflowLoader

from src.notification.engine import NotificationEngine


def main(page):
    """Flet 应用主入口（Alpha 初始化链）"""
    import flet as ft

    # ── 1. 加载配置 ──────────────────────────────
    config = AppConfig()
    config.set("version", "0.2.0")  # Alpha 版本

    # ── 2. 初始化日志 ────────────────────────────
    log_dir = config.get("log_dir", "./logs")
    log_level = config.get("log_level", "INFO")
    setup_logging(log_dir=log_dir, log_level=log_level)

    # 注册日志脱敏过滤器
    for handler in __import__("logging").getLogger().handlers:
        handler.addFilter(SanitizeFilter())

    logger = get_logger("app")
    logger.info("=" * 50)
    logger.info("邮件助手 Alpha 启动")
    logger.info(f"版本: {config.get('version')}")
    logger.info("=" * 50)

    # ── 3. SecretManager ─────────────────────────
    data_dir = Path(config.get("data_dir", "./data"))
    config_dir = Path("config")
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    secret_mgr = SecretManager(config_dir / "secrets.enc")
    logger.info("SecretManager 初始化完成")

    # ── 4. 安全检查 ──────────────────────────────
    checks = run_security_checks()
    for check in checks:
        if check["severity"] == "HIGH":
            logger.warning(f"安全检查: {check['check']} - {check['message']}")
        elif check["severity"] == "WARN":
            logger.info(f"安全检查: {check['check']} - {check['message']}")

    # ── 5. Database + Repository ─────────────────
    db = Database(data_dir / "data.db")
    mail_repo = MailRepository(db)
    cache_repo = CacheRepository(db)
    exec_repo = ExecutionRepository(db)
    task_repo = TaskRepository(db)
    logger.info("数据库 + Repository 初始化完成")

    # ── 6. MigrationManager ──────────────────────
    try:
        from migrations.base import MigrationManager
        migration_mgr = MigrationManager(data_dir, config_dir, db, secret_mgr)
        if migration_mgr.needs_migration():
            logger.info("检测到需要数据迁移，开始执行...")
            migration_mgr.run_migrations()
            logger.info("数据迁移完成")
        else:
            logger.debug("无需数据迁移")
    except Exception as e:
        logger.error(f"数据迁移失败: {e}", exc_info=True)

    # ── 7. NotificationEngine ────────────────────
    notification_engine = None
    try:
        notification_engine = NotificationEngine(
            channels_config_path=config_dir / "notification_channels.yaml",
            templates_dir=Path("templates"),
            secret_mgr=secret_mgr,
            db=db,
            rate_limit_config={"capacity": 20, "refill_interval_ms": 3000},
            retry_config={"max_retries": 3, "base_delay": 5.0, "backoff_multiplier": 3.0},
        )
        logger.info("NotificationEngine 初始化完成")
    except Exception as e:
        logger.error(f"NotificationEngine 初始化失败: {e}")

    # ── 8. LLMClient + AI 组件 ───────────────────
    classifier = None
    try:
        ai_config = _load_ai_config(config_dir)
        llm_client = None
        if ai_config.get("llm_enabled", False):
            llm_client = LLMClient(
                provider=ai_config.get("provider", "deepseek"),
                api_key=secret_mgr.get_secret("api_keys.deepseek") or "",
                base_url=ai_config.get("base_url", "https://api.deepseek.com"),
                model=ai_config.get("model", "deepseek-chat"),
                temperature=ai_config.get("temperature", 0.1),
                max_tokens=ai_config.get("max_tokens", 500),
                timeout=ai_config.get("timeout", 30),
            )

        rule_engine = RuleEngine(Path("rules/custom_rules.yaml"))
        cache_mgr = ClassifyCacheManager(cache_repo)
        feedback_mgr = FeedbackManager(data_dir / "feedback")
        quota_tracker = LLMQuotaTracker(
            daily_quota=ai_config.get("daily_llm_quota", 0))

        classifier = AIClassifier(
            llm=llm_client,
            rules=rule_engine,
            cache_mgr=cache_mgr,
            feedback_mgr=feedback_mgr,
            confidence_threshold_auto=ai_config.get("confidence_threshold_auto", 0.7),
            confidence_threshold_manual=ai_config.get("confidence_threshold_manual", 0.5),
            classify_mode=ai_config.get("classify_mode", "hybrid"),
            llm_enabled=ai_config.get("llm_enabled", False),
            daily_llm_quota=ai_config.get("daily_llm_quota", 0),
            category_llm_overrides=ai_config.get("category_llm_overrides"),
        )
        logger.info(f"AIClassifier 初始化完成 (mode={ai_config.get('classify_mode', 'hybrid')})")
    except Exception as e:
        logger.error(f"AI 分类引擎初始化失败: {e}", exc_info=True)

    # ── 9. WorkflowEngine ────────────────────────
    workflow_engine = None
    try:
        workflow_loader = WorkflowLoader(Path("workflows"))
        workflow_engine = WorkflowEngine(
            loader=workflow_loader,
            execution_repo=exec_repo,
            secret_mgr=secret_mgr,
            notification_engine=notification_engine,
            llm_client=classifier.llm if classifier else None,
            smtp_client=None,  # 延迟注入
            mail_repository=mail_repo,
            imap_client=None,  # 延迟注入
        )
        logger.info("WorkflowEngine 初始化完成")
    except Exception as e:
        logger.error(f"WorkflowEngine 初始化失败: {e}")

    # ── 10. AIClassifier 回调注入 ─────────────────
    if classifier and workflow_engine:
        def _on_classified(mail, result):
            """分类完成回调 → 触发流程"""
            try:
                if result.get("auto_confirm"):
                    workflow_engine.match_and_run(mail, result)
            except Exception as e:
                logger.error(f"分类回调触发流程失败: {e}")

        classifier.set_classified_callback(_on_classified)
        logger.info("AIClassifier 回调注入完成")

    # ── 11. ConfigWatcher ────────────────────────
    config_watcher = ConfigWatcher(
        watch_paths=[],
        callbacks={},
    )
    if classifier:
        config_watcher.register(
            Path("rules/custom_rules.yaml"),
            lambda: classifier._rules.reload(),
        )
    config_watcher.start()
    logger.info("ConfigWatcher 启动")

    # ── 12. GUI 启动 ─────────────────────────────
    from src.gui.theme import LIGHT_THEME, DARK_THEME
    page.theme = LIGHT_THEME
    page.dark_theme = DARK_THEME
    page.theme_mode = ft.ThemeMode.LIGHT

    from src.gui.main_window import MailApp
    app = MailApp(page)

    # ── 账户配置加载 ─────────────────────────────
    account_config = _load_account_config(config_dir, secret_mgr)

    def _init_mail_services(acct: dict):
        """初始化邮件服务"""
        imap_client = None
        smtp_client = None
        scheduler = None

        try:
            imap_config = acct.get("imap", {})
            smtp_config = acct.get("smtp", {})
            password = acct.get("password", "")
            email_addr = acct.get("email", "")

            imap_client = ImapClient(
                host=imap_config.get("host", "mail.yeahka.com"),
                port=imap_config.get("port", 993),
                username=email_addr,
                password=password,
                use_ssl=imap_config.get("ssl", True),
            )
            smtp_client = SmtpClient(
                host=smtp_config.get("host", "mail.yeahka.com"),
                port=smtp_config.get("port", 465),
                username=email_addr,
                password=password,
                use_ssl=smtp_config.get("ssl", True),
            )

            # 注入到 workflow_engine
            if workflow_engine:
                workflow_engine._smtp_client = smtp_client
                workflow_engine._imap_client = imap_client

            # 连接 IMAP
            try:
                imap_client.connect()
                app.update_connection_status(True)
                logger.info("IMAP 连接成功")
            except Exception as e:
                logger.error(f"IMAP 连接失败: {e}")
                app.update_connection_status(False)

            # ── 13. TaskRecovery ─────────────────
            task_recovery = TaskRecovery(task_repo, mail_repo, exec_repo)
            recovery_report = task_recovery.recover_on_startup(
                classifier=classifier,
                workflow_engine=workflow_engine,
                notification_engine=notification_engine,
            )
            if recovery_report:
                logger.info(f"任务恢复: {len(recovery_report)} 个任务已处理")

            # ── 14. MailScheduler ────────────────
            mail_store = MailStore(base_dir=str(data_dir))
            interval = config.get("schedule.interval_minutes", 5)
            scheduler = MailScheduler(
                imap_client=imap_client,
                mail_store=mail_store,
                interval_minutes=interval,
                trigger_type=config.get("schedule.trigger_type", "interval"),
                cron_expression=config.get("schedule.cron_expression"),
                work_hours_only=config.get("schedule.work_hours_only", False),
                work_hours=config.get("schedule.work_hours"),
                work_days=config.get("schedule.work_days"),
                mail_repository=mail_repo,
                classifier=classifier,
                workflow_engine=workflow_engine,
                cache_repository=cache_repo,
            )
            # ── GUI 回调辅助 ─────────────────────
            def _reload_mails_to_gui():
                """从 DB 直接构建 MailData 并推送到 GUI（避免逐文件读磁盘）"""
                from src.core.models import MailData, Attachment
                try:
                    rows = mail_repo.list_mails(limit=200)
                    mail_objects = []
                    for row in rows:
                        try:
                            send_t = datetime.fromisoformat(row["send_time"])
                            recv_t = datetime.fromisoformat(
                                row.get("receive_time") or row["send_time"])
                            tags = json.loads(row.get("tags") or "[]")
                            m = MailData(
                                message_id=row["message_id"],
                                sender=row.get("sender", ""),
                                sender_domain=row.get("sender_domain", ""),
                                recipient=row.get("recipient", ""),
                                subject=row.get("subject", ""),
                                send_time=send_t,
                                receive_time=recv_t,
                                body_text=row.get("body_text") or "",
                                body_html=row.get("body_html"),
                                attachments=[],
                                is_read=bool(row.get("is_read", 0)),
                                is_sent=bool(row.get("is_sent", 0)),
                                local_file_path=row.get("body_file_path"),
                                category=row.get("category"),
                                priority=row.get("priority"),
                                confidence=row.get("confidence", 0.0),
                                need_reply=bool(row.get("need_reply", 0)),
                                tags=tags if isinstance(tags, list) else [],
                                classify_source=row.get("classify_source"),
                                status=row.get("status", "new"),
                            )
                            mail_objects.append(m)
                        except Exception as ex:
                            logger.warning(f"构建 MailData 行失败: {ex}")
                    if mail_objects:
                        app.set_mails(mail_objects)
                    logger.info(f"GUI 邮件列表已刷新: {len(mail_objects)} 封")
                except Exception as ex:
                    logger.error(f"GUI 邮件列表刷新失败: {ex}")

            def _update_status_bar_after_fetch(new_mails: list, success: bool):
                """fetch 完成后更新底部状态栏（在 APScheduler 后台线程中调用）"""
                try:
                    now_str = datetime.now().strftime("%H:%M")
                    if success:
                        app.update_last_fetch_time(now_str)
                    # 下次拉取时间
                    nxt = scheduler.get_next_run_time()
                    if nxt:
                        app.update_next_fetch_time(nxt.strftime("%H:%M"))
                    # 新邮件 → 刷新列表并更新待处理数
                    if new_mails:
                        _reload_mails_to_gui()
                        pending = mail_repo.count_unread() if hasattr(mail_repo, "count_unread") else len(new_mails)
                        app.update_pending_count(pending)
                except Exception as ex:
                    logger.error(f"状态栏更新失败: {ex}")

            def _on_new_mails_gui(new_mails: list):
                """scheduler.on_new_mails 回调：新邮件到达时更新 GUI"""
                _reload_mails_to_gui()

            # 注入回调
            scheduler.on_new_mails    = _on_new_mails_gui
            scheduler.on_fetch_complete = _update_status_bar_after_fetch

            # ── 手动拉取 + 邮件选中 回调 ─────────
            def _on_fetch_action(action: str, data):
                if action == "fetch":
                    def _run():
                        try:
                            new_mails = scheduler.fetch_now()
                            now_str = datetime.now().strftime("%H:%M")
                            app.update_last_fetch_time(now_str)
                            nxt = scheduler.get_next_run_time()
                            if nxt:
                                app.update_next_fetch_time(nxt.strftime("%H:%M"))
                            if new_mails:
                                _reload_mails_to_gui()
                            app.update_pending_count(mail_repo.count_unread())
                        except Exception as ex:
                            logger.error(f"手动拉取失败: {ex}")
                        finally:
                            app.set_fetch_button_enabled(True)
                    threading.Thread(target=_run, daemon=True).start()

                elif action == "mark_read":
                    # GUI 层已显示邮件，这里只做 DB 标记
                    message_id = data
                    def _mark(mid=message_id):
                        try:
                            mail_repo.mark_as_read(mid)
                            app.update_pending_count(mail_repo.count_unread())
                        except Exception as ex:
                            logger.error(f"标记已读失败: {ex}")
                    threading.Thread(target=_mark, daemon=True).start()

                elif action == "select":
                    # 降级路径：GUI 层找不到 mail 对象时才触发
                    message_id = data
                    mail = app.get_mail_by_id(message_id)
                    if mail is None:
                        return
                    was_unread = not mail.is_read
                    app.show_mail_detail(mail)
                    if was_unread:
                        def _mark(mid=message_id):
                            try:
                                mail_repo.mark_as_read(mid)
                                app.update_pending_count(mail_repo.count_unread())
                            except Exception as ex:
                                logger.error(f"标记已读失败: {ex}")
                        threading.Thread(target=_mark, daemon=True).start()

            app._on_fetch = _on_fetch_action

            scheduler.start()
            logger.info(f"邮件调度器启动 (间隔 {interval} 分钟)")

            # 首次启动后更新"下次拉取"时间
            nxt = scheduler.get_next_run_time()
            if nxt:
                app.update_next_fetch_time(nxt.strftime("%H:%M"))

            # ── 15. GUI 数据加载 ─────────────────
            _reload_mails_to_gui()

            # 初始化底部状态栏
            try:
                app.update_pending_count(mail_repo.count_unread())
                app.update_last_fetch_time(datetime.now().strftime("%H:%M"))
            except Exception as ex:
                logger.warning(f"初始化状态栏失败: {ex}")

            # 存储引用
            app._scheduler = scheduler
            app._imap_client = imap_client
            app._smtp_client = smtp_client
            app._mail_store = mail_store
            app._mail_repo = mail_repo
            app._classifier = classifier
            app._workflow_engine = workflow_engine
            app._notification_engine = notification_engine

            page.update()

        except Exception as e:
            logger.error(f"邮件服务初始化失败: {e}", exc_info=True)
            _sb = ft.SnackBar(content=ft.Text(f"初始化失败: {e}"), open=True)
            page.overlay.append(_sb)
            page.update()

    # 启动流程
    if account_config:
        _init_mail_services(account_config)
    else:
        # 未检测到账户配置：不再弹出设置对话框，用户可在设置页 → 账户管理中配置
        logger.info("未检测到账户配置，跳过服务初始化（可在设置页 → 账户管理配置）")


def _load_ai_config(config_dir: Path) -> dict:
    """加载 AI 配置"""
    ai_config_path = config_dir / "ai.json"
    if not ai_config_path.exists():
        return {
            "classify_mode": "hybrid",
            "llm_enabled": False,
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "temperature": 0.1,
            "max_tokens": 500,
            "timeout": 30,
            "daily_llm_quota": 0,
            "confidence_threshold_auto": 0.7,
            "confidence_threshold_manual": 0.5,
        }
    with open(ai_config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_account_config(config_dir: Path, secret_mgr: SecretManager) -> dict | None:
    """加载账户配置，从 SecretManager 获取密码"""
    config_path = config_dir / "account.json"
    if not config_path.exists():
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 从 SecretManager 获取密码
    password = secret_mgr.get_secret("accounts.default") or ""
    if not password:
        # 兼容旧格式：base64 密码
        import base64
        pwd_b64 = data.get("password", "")
        if pwd_b64:
            try:
                password = base64.b64decode(pwd_b64).decode("utf-8")
            except Exception:
                pass

    data["password"] = password
    return data


if __name__ == "__main__":
    import flet as ft
    import os
    if os.environ.get("FLET_FORCE_WEB_SERVER"):
        ft.run(main, view=ft.AppView.FLET_APP_WEB, host="0.0.0.0", port=8765)
    else:
        ft.run(main)
