"""邮件助手 - Flet 应用入口"""

import sys
import json
import base64
from pathlib import Path
from datetime import datetime

import flet as ft

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import AppConfig
from src.core.logger import setup_logging, get_logger
from src.gui.theme import LIGHT_THEME, DARK_THEME
from src.gui.main_window import MailApp
from src.gui.account_dialog import AccountDialog
from src.gui.worker import MailFetchWorker


def load_account_config():
    """加载账户配置"""
    config_path = Path("config/account.json")
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        pwd_b64 = data.get("password", "")
        if pwd_b64:
            try:
                data["password_decoded"] = base64.b64decode(pwd_b64).decode("utf-8")
            except Exception:
                pass

        return data
    except Exception as e:
        print(f"加载账户配置失败: {e}")
        return None


def main(page: ft.Page):
    """Flet 应用主入口"""

    # 1. 加载配置
    config = AppConfig()

    # 2. 初始化日志
    log_dir = config.get("log_dir", "./logs")
    log_level = config.get("log_level", "INFO")
    setup_logging(log_dir=log_dir, log_level=log_level)

    logger = get_logger("app")
    logger.info("=" * 50)
    logger.info("邮件助手启动 (Flet)")
    logger.info(f"版本: {config.get('version', 'unknown')}")
    logger.info(f"数据目录: {config.get('data_dir', './data')}")
    logger.info(f"日志目录: {log_dir}")
    logger.info(f"日志级别: {log_level}")
    logger.info("=" * 50)

    # 3. 应用主题（深浅双主题，默认浅色）
    page.theme = LIGHT_THEME
    page.dark_theme = DARK_THEME
    page.theme_mode = ft.ThemeMode.LIGHT

    # 4. 检查账户配置
    account_config = load_account_config()
    if not account_config:
        logger.info("未检测到账户配置，需要用户配置")

    # 5. 构建 UI
    app = MailApp(page)

    # 6. 如果没有账户配置，先弹出配置对话框
    def _show_account_dialog(done_callback):
        dialog = AccountDialog(page)

        def _on_dialog_close(e):
            data = dialog.get_account_data()
            if data:
                done_callback(data)
            else:
                logger.info("用户取消账户配置，退出程序")
                page.window.close()

        dialog._dialog.on_dismiss = _on_dialog_close
        dialog.show()

    # 7. 初始化邮件组件
    def _init_app(acct_config: dict):
        from src.mail.imap_client import ImapClient
        from src.mail.smtp_client import SmtpClient
        from src.storage.mail_store import MailStore
        from src.mail.scheduler import MailScheduler

        data_dir = config.get("data_dir", "./data")
        mail_store = MailStore(base_dir=data_dir)

        imap_config = acct_config.get("imap", {})
        imap_client = ImapClient(
            host=imap_config.get("host", "imap.exmail.qq.com"),
            port=imap_config.get("port", 993),
            username=acct_config.get("email", ""),
            password=acct_config.get("password_decoded", ""),
            use_ssl=imap_config.get("ssl", True),
        )

        smtp_config = acct_config.get("smtp", {})
        smtp_client = SmtpClient(
            host=smtp_config.get("host", "smtp.exmail.qq.com"),
            port=smtp_config.get("port", 465),
            username=acct_config.get("email", ""),
            password=acct_config.get("password_decoded", ""),
            use_ssl=smtp_config.get("ssl", True),
        )

        # 连接 IMAP
        try:
            imap_client.connect()
            app.update_connection_status(True)
            logger.info("IMAP 连接成功")
        except Exception as e:
            logger.error(f"IMAP 连接失败: {e}")
            app.update_connection_status(False)

        # 调度器
        interval = config.get("schedule.interval_minutes", 5)
        scheduler = MailScheduler(
            imap_client=imap_client,
            mail_store=mail_store,
            interval_minutes=interval,
        )

        # 注册事件回调
        def _on_action(action: str, data):
            if action == "fetch":
                _do_fetch()
            elif action == "select":
                _do_select(data)
            elif action == "settings":
                _show_settings()

        def _do_fetch():
            worker = MailFetchWorker(
                imap_client,
                mail_store,
                on_finished=lambda mails: _on_fetch_finished(mails),
                on_error=lambda msg: _on_fetch_error(msg),
            )
            worker.start()
            app._fetch_worker = worker

        def _on_fetch_finished(mails):
            app.set_fetch_button_enabled(True)
            if mails:
                app.set_mails(mails)
                app.update_pending_count(len(mails))
            app.update_last_fetch_time(datetime.now().strftime("%H:%M"))

        def _on_fetch_error(msg):
            app.set_fetch_button_enabled(True)
            logger.error(f"拉取失败: {msg}")
            _sb = ft.SnackBar(content=ft.Text(f"拉取失败: {msg}"), open=True)
            page.overlay.append(_sb)
            page.update()

        def _do_select(message_id):
            mail = mail_store.load(message_id)
            if mail:
                app.show_mail_detail(mail)

        def _show_settings():
            dialog = AccountDialog(page)

            def _on_settings_close(e):
                new_data = dialog.get_account_data()
                if new_data:
                    logger.info("账户配置已更新")
                    _sb = ft.SnackBar(content=ft.Text("配置已更新，重启后生效"), open=True)
                    page.overlay.append(_sb)
                    page.update()

            dialog._dialog.on_dismiss = _on_settings_close
            dialog.show()

        app._on_fetch = _on_action

        # 加载已有邮件
        existing_mails = mail_store.list_mails()
        if existing_mails:
            app.set_mails(existing_mails)
            app.update_pending_count(
                len([m for m in existing_mails if not m.is_read])
            )
            logger.info(f"加载 {len(existing_mails)} 封已有邮件")

        # 启动调度器
        scheduler.start()
        logger.info(f"邮件调度器已启动，间隔: {interval} 分钟")

        # 存储引用用于清理
        app._scheduler = scheduler
        app._imap_client = imap_client
        app._smtp_client = smtp_client
        app._mail_store = mail_store

        page.update()

    # 8. 账户配置处理
    if account_config:
        _init_app(account_config)
    else:
        _show_account_dialog(_init_app)


if __name__ == "__main__":
    import os
    if os.environ.get("FLET_FORCE_WEB_SERVER"):
        ft.run(main, view=ft.AppView.FLET_APP_WEB, host="0.0.0.0", port=8765)
    else:
        ft.run(main)