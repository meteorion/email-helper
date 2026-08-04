"""MVP (v0.1.0) → Alpha (v0.2.0) 数据迁移脚本。

迁移内容：
1. seen_ids 迁移：兼容 list / dict / 嵌套格式，写入 SQLite ``seen_message_ids`` 表。
2. 邮件元数据迁移：遍历 ``data/mails/*/mail_*.json``，解析 MailData 后 upsert 到 ``mails`` 表。
3. 账户密码迁移：解码 base64 密码并存入 SecretManager，原字段替换为 ``password_ref``。
4. 配置文件生成：默认 ``ai.json`` / ``notification_channels.yaml`` / ``rules/custom_rules.yaml``。
5. 目录创建：``workflows/`` / ``templates/`` / ``data/records/`` / ``data/feedback/``。
6. schema_version 写入 ``{"version": "0.2.0", "migrated_at": "..."}``。
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.logger import get_logger
from src.core.models import MailData
from migrations.base import Migration

logger = get_logger("migrations.v0_1_0_to_v0_2_0")


# ── 默认配置模板 ───────────────────────────────────

DEFAULT_AI_CONFIG: dict = {
    "provider": "deepseek",
    "api_key_ref": "secrets.api_keys.deepseek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "temperature": 0.1,
    "max_tokens": 500,
    "timeout": 30,
    "confidence_threshold": 0.8,
    "auto_confirm_threshold": 0.9,
    "manual_confirm_threshold": 0.5,
    "enable_cache": True,
    "cache_ttl_hours": 24,
    "fallback_to_rules": True,
    "enable_quota": False,
    "daily_quota": 50,
    "classify_mode": "hybrid",
}

DEFAULT_NOTIFICATION_CHANNELS_YAML: str = """# 通知渠道配置
channels:
  # 主通知渠道：企微群机器人
  wecom_group:
    type: "wecom_webhook"
    webhook_ref: "${secrets.webhooks.wecom_group}"
    enabled: true
    priority: 1
    rate_limit:
      max_per_minute: 18
      max_per_hour: 200
    message_format: "markdown"
    mention_list:
      default: []
      urgent: ["@all"]

# 渠道选择策略
routing:
  by_category:
    审批类: ["wecom_group"]
    告警类: ["wecom_group"]
    通知类: ["wecom_group"]
    default: ["wecom_group"]
"""

DEFAULT_CUSTOM_RULES_YAML: str = """# 自定义规则
rules:
  - name: "CEO邮件优先"
    enabled: true
    priority: 100
    condition:
      sender: "ceo@company.com"
    action:
      set_type: "审批类"
      set_priority: "紧急"
      override_ai: true
      auto_tag: ["VIP", "领导"]

  - name: "监控告警识别"
    enabled: true
    priority: 90
    condition:
      subject_contains: ["告警", "ALERT", "CRITICAL"]
      sender_domain: ["monitor.system"]
    action:
      set_type: "告警类"
      set_priority: "紧急"

  - name: "周报自动归类"
    enabled: true
    priority: 50
    condition:
      subject_regex: "周报|weekly report"
    action:
      set_type: "资讯类"
      auto_tag: ["周报"]
"""


class MigrationV01ToV02(Migration):
    """v0.1.0 → v0.2.0 迁移脚本。

    实现 MVP 阶段 JSON 文件存储到 Alpha 阶段 SQLite + 密钥管理 的平滑升级。
    """

    from_version: str = "0.1.0"
    to_version: str = "0.2.0"

    # ── migrate ─────────────────────────────────────

    def migrate(
        self,
        data_dir: Path,
        config_dir: Path,
        db: Any,
        secret_mgr: Any,
    ) -> None:
        """执行 MVP → Alpha 完整迁移。

        Args:
            data_dir: 数据目录。
            config_dir: 配置目录。
            db: Database 实例。
            secret_mgr: SecretManager 实例。
        """
        logger.info("开始执行 v0.1.0 → v0.2.0 迁移")

        # 步骤 1: seen_ids 迁移
        self._migrate_seen_ids(data_dir, db)

        # 步骤 2: 邮件元数据迁移
        self._migrate_mail_metadata(data_dir, db)

        # 步骤 3: 账户密码迁移
        self._migrate_account_password(config_dir, secret_mgr)

        # 步骤 4: 配置文件生成
        self._generate_default_configs(config_dir)

        # 步骤 5: 目录创建
        self._create_directories(data_dir, config_dir)

        # 步骤 6: schema_version 写入
        self._write_schema_version(data_dir, self.to_version)

        logger.info("v0.1.0 → v0.2.0 迁移执行完毕")

    # ── validate ────────────────────────────────────

    def validate(self, data_dir: Path, config_dir: Path, db: Any) -> bool:
        """迁移后校验。

        Args:
            data_dir: 数据目录。
            config_dir: 配置目录。
            db: Database 实例。

        Returns:
            校验通过返回 True。
        """
        try:
            # 校验 seen_message_ids 表存在且有数据（如果原文件存在）
            seen_count_row = db.query_one(
                "SELECT COUNT(*) AS cnt FROM seen_message_ids"
            )
            logger.info(f"校验: seen_message_ids 记录数 = "
                        f"{seen_count_row['cnt'] if seen_count_row else 0}")

            # 校验 mails 表存在
            mails_count_row = db.query_one(
                "SELECT COUNT(*) AS cnt FROM mails"
            )
            logger.info(f"校验: mails 记录数 = "
                        f"{mails_count_row['cnt'] if mails_count_row else 0}")

            # 校验目录创建
            for d in [
                data_dir / "records",
                data_dir / "feedback",
                data_dir.parent / "workflows",
                data_dir.parent / "templates",
                config_dir.parent / "rules",
            ]:
                if not d.exists():
                    logger.warning(f"校验: 目录不存在 {d}")
                    return False

            # 校验 schema_version.json
            version_file = data_dir / "schema_version.json"
            if not version_file.exists():
                logger.warning("校验: schema_version.json 不存在")
                return False
            with open(version_file, "r", encoding="utf-8") as f:
                vdata = json.load(f)
            if vdata.get("version") != self.to_version:
                logger.warning(f"校验: schema 版本不是 {self.to_version}")
                return False

            logger.info("v0.1.0 → v0.2.0 校验通过")
            return True
        except Exception as e:
            logger.error(f"校验失败: {e}", exc_info=True)
            return False

    # ── rollback ────────────────────────────────────

    def rollback(
        self,
        data_dir: Path,
        config_dir: Path,
        backup_dir: Path,
    ) -> None:
        """回滚：交给 ``MigrationManager._restore`` 完成覆盖式恢复。

        Args:
            data_dir: 数据目录。
            config_dir: 配置目录。
            backup_dir: 备份目录。
        """
        logger.info(
            f"v0.1.0 → v0.2.0 回滚：依赖 MigrationManager._restore({backup_dir})"
        )

    # ── 步骤 1: seen_ids 迁移 ───────────────────────

    def _migrate_seen_ids(self, data_dir: Path, db: Any,
                          account_id: str = "default") -> None:
        """迁移 seen_ids.json 到 SQLite seen_message_ids 表。

        兼容三种 MVP 格式：
        - list: ``["msg1", "msg2"]``
        - dict[str, str]: ``{"msg1": "timestamp"}``
        - dict[str, list]: 嵌套 ``{"account1": ["msg1", ...]}``

        Args:
            data_dir: 数据目录。
            db: Database 实例。
            account_id: 默认账户 ID。
        """
        cache_file = data_dir / "cache" / "seen_ids.json"
        if not cache_file.exists():
            logger.info("seen_ids.json 不存在，跳过迁移")
            return

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取 seen_ids.json 失败: {e}，跳过迁移")
            return

        migrated = 0
        try:
            if isinstance(data, list):
                # ["msg1", "msg2", ...]
                ids = [str(x) for x in data if isinstance(x, str)]
                for mid in ids:
                    db.execute(
                        "INSERT OR IGNORE INTO seen_message_ids "
                        "(message_id, account_id) VALUES (?, ?)",
                        (mid, account_id),
                    )
                    migrated += 1
            elif isinstance(data, dict):
                values = list(data.values())
                if values and all(isinstance(v, list) for v in values):
                    # 嵌套格式 {"account1": ["msg1", ...]}
                    for acct, msg_list in data.items():
                        acct_id = str(acct) if acct else account_id
                        if not isinstance(msg_list, list):
                            continue
                        for mid in msg_list:
                            if not isinstance(mid, str):
                                continue
                            db.execute(
                                "INSERT OR IGNORE INTO seen_message_ids "
                                "(message_id, account_id) VALUES (?, ?)",
                                (mid, acct_id),
                            )
                            migrated += 1
                else:
                    # {"msg1": "timestamp", ...} 或混合格式
                    ids = [str(k) for k in data.keys()]
                    for mid in ids:
                        db.execute(
                            "INSERT OR IGNORE INTO seen_message_ids "
                            "(message_id, account_id) VALUES (?, ?)",
                            (mid, account_id),
                        )
                        migrated += 1
            else:
                logger.warning(f"seen_ids.json 格式无法识别: {type(data)}，跳过迁移")
                return

            # 原文件改名为 .json.migrated
            migrated_path = cache_file.with_suffix(".json.migrated")
            try:
                cache_file.rename(migrated_path)
                logger.info(f"seen_ids.json 已重命名为 {migrated_path.name}")
            except OSError as e:
                logger.warning(f"重命名 seen_ids.json 失败: {e}")

            logger.info(f"seen_ids 迁移完成，共 {migrated} 条")
        except Exception as e:
            logger.error(f"seen_ids 迁移过程出错: {e}", exc_info=True)
            raise

    # ── 步骤 2: 邮件元数据迁移 ──────────────────────

    def _migrate_mail_metadata(self, data_dir: Path, db: Any,
                               account_id: str = "default") -> None:
        """遍历 data/mails/*/mail_*.json，upsert 到 mails 表。

        Args:
            data_dir: 数据目录。
            db: Database 实例。
            account_id: 默认账户 ID。
        """
        mails_dir = data_dir / "mails"
        if not mails_dir.exists():
            logger.info("data/mails 目录不存在，跳过邮件元数据迁移")
            return

        migrated = 0
        failed = 0
        for mail_file in mails_dir.glob("*/mail_*.json"):
            try:
                with open(mail_file, "r", encoding="utf-8") as f:
                    mail = MailData.from_json(f.read())

                tags_json = json.dumps(mail.tags, ensure_ascii=False)
                db.execute(
                    """INSERT OR REPLACE INTO mails
                    (message_id, account_id, sender, sender_domain, recipient, subject,
                     send_time, receive_time, body_text, body_html, body_file_path,
                     category, priority, confidence, need_reply, tags, classify_source,
                     content_fingerprint, thread_id, in_reply_to, references_hdr,
                     status, is_read, is_sent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        mail.message_id,
                        account_id,
                        mail.sender,
                        mail.sender_domain,
                        mail.recipient,
                        mail.subject,
                        mail.send_time.isoformat()
                        if hasattr(mail.send_time, "isoformat")
                        else str(mail.send_time),
                        mail.receive_time.isoformat()
                        if hasattr(mail.receive_time, "isoformat")
                        else str(mail.receive_time),
                        mail.body_text,
                        mail.body_html,
                        mail.local_file_path,
                        mail.category,
                        mail.priority,
                        mail.confidence,
                        int(mail.need_reply),
                        tags_json,
                        mail.classify_source,
                        mail.content_fingerprint,
                        mail.thread_id,
                        mail.in_reply_to,
                        mail.references,
                        mail.status,
                        int(mail.is_read),
                        int(mail.is_sent),
                    ),
                )
                migrated += 1
            except Exception as e:
                failed += 1
                logger.warning(f"迁移邮件文件失败 {mail_file}: {e}")

        logger.info(f"邮件元数据迁移完成: 成功 {migrated} 封, 失败 {failed} 封")

    # ── 步骤 3: 账户密码迁移 ────────────────────────

    def _migrate_account_password(
        self,
        config_dir: Path,
        secret_mgr: Any,
        secret_path: str = "secrets.accounts.default",
    ) -> None:
        """迁移账户密码到 SecretManager，原 password 字段替换为 password_ref。

        Args:
            config_dir: 配置目录。
            secret_mgr: SecretManager 实例。
            secret_path: 密钥存储路径。
        """
        account_file = config_dir / "account.json"
        if not account_file.exists():
            logger.info("config/account.json 不存在，跳过账户密码迁移")
            return

        try:
            with open(account_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取 account.json 失败: {e}，跳过账户密码迁移")
            return

        # 兼容 password 在顶层或在 imap/smtp 子结构中的写法
        pwd_b64 = data.get("password")
        if not pwd_b64:
            logger.info("account.json 中未找到 password 字段，跳过密码迁移")
            return

        try:
            pwd_plain = base64.b64decode(pwd_b64).decode("utf-8")
        except Exception as e:
            logger.warning(f"密码 base64 解码失败: {e}，跳过密码迁移")
            return

        # 写入 SecretManager
        secret_mgr.set_secret(secret_path, pwd_plain)
        logger.info(f"账户密码已迁移到 SecretManager ({secret_path})")

        # 原字段替换为 password_ref
        if "password" in data:
            data.pop("password", None)
        data["password_ref"] = secret_path

        # 同步处理嵌套结构中的 password 字段（imap / smtp）
        for section in ("imap", "smtp"):
            if isinstance(data.get(section), dict) and "password" in data[section]:
                data[section].pop("password", None)
                data[section]["password_ref"] = secret_path

        try:
            with open(account_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"account.json 已更新 password → password_ref")
        except OSError as e:
            logger.warning(f"写回 account.json 失败: {e}")

    # ── 步骤 4: 配置文件生成 ────────────────────────

    def _generate_default_configs(self, config_dir: Path) -> None:
        """生成默认的 ai.json / notification_channels.yaml / rules/custom_rules.yaml。

        已存在的文件不会被覆盖。

        Args:
            config_dir: 配置目录。
        """
        config_dir.mkdir(parents=True, exist_ok=True)

        # ai.json
        ai_file = config_dir / "ai.json"
        if not ai_file.exists():
            try:
                with open(ai_file, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_AI_CONFIG, f, ensure_ascii=False, indent=2)
                logger.info(f"已生成默认配置: {ai_file}")
            except OSError as e:
                logger.warning(f"生成 ai.json 失败: {e}")
        else:
            logger.info(f"ai.json 已存在，跳过生成")

        # notification_channels.yaml
        notif_file = config_dir / "notification_channels.yaml"
        if not notif_file.exists():
            try:
                with open(notif_file, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_NOTIFICATION_CHANNELS_YAML)
                logger.info(f"已生成默认配置: {notif_file}")
            except OSError as e:
                logger.warning(f"生成 notification_channels.yaml 失败: {e}")
        else:
            logger.info(f"notification_channels.yaml 已存在，跳过生成")

        # rules/custom_rules.yaml（位于项目根目录下的 rules/）
        rules_dir = config_dir.parent / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rules_file = rules_dir / "custom_rules.yaml"
        if not rules_file.exists():
            try:
                with open(rules_file, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_CUSTOM_RULES_YAML)
                logger.info(f"已生成默认配置: {rules_file}")
            except OSError as e:
                logger.warning(f"生成 custom_rules.yaml 失败: {e}")
        else:
            logger.info(f"custom_rules.yaml 已存在，跳过生成")

    # ── 步骤 5: 目录创建 ────────────────────────────

    def _create_directories(self, data_dir: Path, config_dir: Path) -> None:
        """创建 Alpha 阶段需要的新目录。

        Args:
            data_dir: 数据目录。
            config_dir: 配置目录（用于定位项目根）。
        """
        project_root = data_dir.parent
        new_dirs = [
            project_root / "workflows",
            project_root / "templates",
            data_dir / "records",
            data_dir / "feedback",
        ]
        for d in new_dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
                logger.info(f"确保目录存在: {d}")
            except OSError as e:
                logger.warning(f"创建目录失败 {d}: {e}")

    # ── 步骤 6: schema_version 写入 ─────────────────

    def _write_schema_version(self, data_dir: Path, version: str) -> None:
        """写入 schema_version.json。

        Args:
            data_dir: 数据目录。
            version: 目标版本字符串。
        """
        data_dir.mkdir(parents=True, exist_ok=True)
        version_file = data_dir / "schema_version.json"
        payload = {
            "version": version,
            "migrated_at": datetime.now().isoformat(),
        }
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"schema_version.json 已写入: {payload}")
        except OSError as e:
            logger.error(f"写入 schema_version.json 失败: {e}")
            raise


__all__ = ["MigrationV01ToV02"]
