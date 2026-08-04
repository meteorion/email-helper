# Alpha (v0.2) 开发任务清单

> 目标：实现 AI 智能分类、流程引擎、企微群通知三大核心能力，存储从 JSON 升级到 SQLite，引入密钥安全管理
> 技术栈增量：PyYAML / requests / cryptography / SQLite3 (标准库)
> 存储方案：JSON → SQLite（元数据）+ JSON（正文）混合

---

## 新增目录结构（Alpha 阶段引入）

```
email-helper/
├── config/
│   ├── app.json                 # 全局配置（原）
│   ├── account.json             # 账户配置（密码引用化）
│   ├── ai.json                  # 【新增】AI 分类配置
│   ├── notification_channels.yaml # 【新增】通知渠道配置
│   └── secrets.enc              # 【新增】加密密钥存储（AES-256-GCM）
│
├── workflows/                   # 【新增】流程定义目录
│   ├── approval_handler.yaml
│   ├── alert_handler.yaml
│   └── default_handler.yaml
│
├── templates/                   # 【新增】通知模板目录
│   ├── approval_notification.yaml
│   ├── alert_notification.yaml
│   ├── daily_summary.yaml
│   └── email_templates/         # 【新增】邮件发送模板目录
│       └── approval_reply.yaml
│
├── rules/                       # 【新增】自定义规则目录
│   └── custom_rules.yaml
│
├── migrations/                  # 【新增】数据迁移脚本目录
│   ├── __init__.py
│   └── v0.1.0_to_v0.2.0.py      # MVP → Alpha 数据迁移
│
├── data/
│   ├── data.db                  # 【新增】SQLite 数据库（元数据/记录/缓存）
│   ├── mails/                   # 邮件正文 JSON（保留原结构）
│   ├── attachments/             # 附件（保留原结构）
│   ├── records/                 # 【新增】处理记录（按日期）
│   ├── feedback/                # 【新增】AI 分类反馈数据
│   └── cache/
│       └── classify_cache.json  # 【新增】AI 分类结果缓存
│
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # 需扩展：支持 ai.json / secrets 引用解析
│   │   ├── logger.py            # 需扩展：日志脱敏过滤器
│   │   ├── models.py            # 需扩展：AI 分类字段、流程执行记录
│   │   ├── security/            # 【新增】安全模块
│   │   │   ├── __init__.py
│   │   │   ├── secret_manager.py    # 密钥管理
│   │   │   ├── log_sanitizer.py     # 日志脱敏
│   │   │   └── security_check.py    # 启动安全检查
│   │   ├── storage/             # 【新增】存储层
│   │   │   ├── __init__.py
│   │   │   ├── database.py          # SQLite 连接管理
│   │   │   ├── mail_repository.py   # 邮件元数据仓储
│   │   │   ├── execution_repo.py    # 流程执行记录仓储
│   │   │   └── cache_repository.py  # 去重/分类缓存仓储
│   │   └── recovery/            # 【新增】容错恢复模块
│   │       ├── __init__.py
│   │       └── task_recover.py      # 任务恢复管理器
│   │   ├── config_watcher.py       # 【新增】配置文件热重载
│   │   └── storage/
│   │       └── cleanup_manager.py  # 【新增】数据清理管理器
│   │
│   ├── ai/                      # 【新增】AI 分类引擎
│   │   ├── __init__.py
│   │   ├── classifier.py            # 主分类器（规则+LLM）
│   │   ├── llm_client.py            # LLM API 客户端（OpenAI/DeepSeek/Ollama）
│   │   ├── prompt_builder.py        # Prompt 构建器
│   │   ├── rule_engine.py           # 规则预筛引擎
│   │   ├── feedback_manager.py      # 分类反馈管理器
│   │   └── cache_manager.py         # 分类缓存管理器
│   │
│   ├── workflow/                # 【新增】流程引擎
│   │   ├── __init__.py
│   │   ├── engine.py                # 流程执行引擎
│   │   ├── context.py               # 流程上下文 Context
│   │   ├── loader.py                # YAML 流程定义加载器
│   │   ├── executor.py              # 步骤执行器
│   │   ├── condition.py             # 条件表达式解析器
│   │   ├── actions/                 # 内置 Action 实现
│   │   │   ├── __init__.py
│   │   │   ├── extract_info.py
│   │   │   ├── summarize.py
│   │   │   ├── check_duplicate.py
│   │   │   ├── notify.py
│   │   │   ├── forward.py
│   │   │   ├── auto_reply.py
│   │   │   ├── save_attachment.py
│   │   │   ├── save_record.py
│   │   │   ├── tag.py
│   │   │   ├── move_to_folder.py
│   │   │   ├── http_request.py
│   │   │   ├── set_variable.py
│   │   │   └── log.py
│   │   └── version_manager.py       # 流程版本管理
│   │
│   ├── notification/            # 【新增】通知引擎
│   │   ├── __init__.py
│   │   ├── engine.py                # 通知分发引擎
│   │   ├── channels/                # 通知渠道
│   │   │   ├── __init__.py
│   │   │   └── wecom_webhook.py     # 企微群机器人
│   │   ├── template.py              # 通知模板引擎（变量替换）
│   │   ├── rate_limiter.py          # 令牌桶限流器
│   │   ├── queue.py                 # 通知队列（优先级+聚合）
│   │   ├── retry_handler.py         # 失败重试处理器
│   │   └── failure_queue.py         # 失败通知持久化队列
│   │
│   ├── mail/
│   │   ├── scheduler.py         # 需扩展：拉取后自动触发分类+流程；Cron/工作时间过滤
│   │   ├── parser.py            # 需扩展：chardet检测 + In-Reply-To/References提取
│   │   ├── send_template.py     # 【新增】邮件发送模板
│   │   └── ...                  # 其他保持不变
│   │
│   ├── storage/
│   │   └── mail_store.py        # 需重构：元数据走 SQLite，正文走 JSON
│   │
│   └── gui/
│       ├── main_window.py       # 需扩展：新增 7 个页面入口 + 已发送视图
│       ├── compose_dialog.py    # 【新增】写邮件对话框
│       ├── worker.py            # 需扩展：AI分类/流程执行/邮件发送 Worker
│       ├── pages/               # 【新增】独立页面组件
│       │   ├── __init__.py
│       │   ├── ai_config_page.py     # AI 配置页面
│       │   ├── workflow_page.py      # 流程管理页面
│       │   ├── template_page.py      # 模板管理页面
│       │   ├── notification_page.py  # 通知配置页面
│       │   ├── schedule_page.py      # 【新增】调度配置页面
│       │   ├── log_page.py           # 【新增】运行日志页面
│       │   └── stats_page.py         # 统计面板页面
│       └── components/          # 【新增】可复用 GUI 组件
│           ├── __init__.py
│           ├── category_badge.py     # 分类标签组件
│           ├── ai_summary_card.py    # AI 摘要卡片
│           └── workflow_status.py    # 流程执行状态组件
│
└── tests/
    ├── test_ai_classifier.py   # 【新增】AI 分类测试
    ├── test_workflow_engine.py # 【新增】流程引擎测试
    ├── test_notification.py    # 【新增】通知引擎测试
    ├── test_database.py        # 【新增】SQLite 存储测试
    ├── test_security.py        # 【新增】安全模块测试
    ├── test_migration.py       # 【新增】数据迁移测试
    ├── test_compose_dialog.py  # 【新增】写邮件测试
    ├── test_scheduler_cron.py  # 【新增】调度增强测试
    ├── test_cleanup.py         # 【新增】数据清理测试
    ├── test_attachment.py      # 【新增】附件处理测试
    └── test_config_watcher.py  # 【新增】配置热重载测试
```

---

## 模块依赖关系（Alpha 新增）

```
main.py
  ├── core/security/secret_manager.py      (密钥管理)
  ├── core/security/security_check.py      (启动安全检查)
  ├── core/storage/database.py             (SQLite 初始化)
  ├── migrations/v0.1.0_to_v0.2.0.py       (数据迁移)
  │
  ├── ai/classifier.py                      (AI 分类入口)
  │     ├── ai/rule_engine.py               (规则预筛)
  │     ├── ai/llm_client.py                (LLM 调用)
  │     ├── ai/prompt_builder.py            (Prompt)
  │     ├── ai/cache_manager.py             (分类缓存)
  │     └── ai/feedback_manager.py          (反馈闭环)
  │
  ├── workflow/engine.py                    (流程执行入口)
  │     ├── workflow/loader.py              (YAML 加载)
  │     ├── workflow/context.py             (Context)
  │     ├── workflow/condition.py           (条件解析)
  │     ├── workflow/executor.py            (步骤执行)
  │     ├── workflow/actions/*              (13个内置Action)
  │     └── workflow/version_manager.py     (版本管理)
  │
  ├── notification/engine.py                (通知分发入口)
  │     ├── notification/channels/*         (企微渠道)
  │     ├── notification/template.py        (模板渲染)
  │     ├── notification/rate_limiter.py    (限流)
  │     ├── notification/queue.py           (队列+聚合+免打扰)
  │     ├── notification/retry_handler.py   (重试)
  │     └── notification/failure_queue.py   (失败队列)
  │
  ├── core/recovery/task_recover.py         (启动任务恢复)
  ├── core/config_watcher.py                (配置热重载)
  ├── core/storage/cleanup_manager.py       (数据清理)
  │
  ├── mail/scheduler.py                     (调度增强: Cron/工作时间)
  ├── mail/parser.py                        (解析增强: chardet/线程头)
  ├── mail/send_template.py                 (邮件发送模板)
  │
  └── gui/main_window.py
        ├── gui/compose_dialog.py            (写邮件对话框)
        ├── gui/pages/ai_config_page.py     (AI 配置页)
        ├── gui/pages/workflow_page.py      (流程管理页)
        ├── gui/pages/template_page.py      (模板管理页)
        ├── gui/pages/notification_page.py  (通知配置页)
        ├── gui/pages/schedule_page.py      (调度配置页)
        ├── gui/pages/log_page.py           (运行日志页)
        └── gui/pages/stats_page.py         (统计面板)
```

---

## 开发任务

### 任务 A1：存储层升级 — SQLite 引入

**目标：** 将邮件元数据、去重缓存、处理记录从 JSON 文件迁移到 SQLite，正文 JSON 保留，为 Alpha 功能打基础。

**具体工作：**

#### A1.1 SQLite 基础连接管理
实现 `src/core/storage/database.py`：
```python
class Database:
    def __init__(self, db_path: str)
    def _get_connection() -> sqlite3.Connection   # 每线程独立连接
    @contextmanager
    def transaction()                              # 事务管理
    def execute(sql: str, params=())               # 执行 SQL
    def fetchall(sql: str, params=()) -> list
    def fetchone(sql: str, params=()) -> tuple | None
```
**关键 PRAGMA 配置：**
- `journal_mode=WAL` — 支持并发读写
- `busy_timeout=5000` — 忙等待 5 秒
- `synchronous=NORMAL` — 平衡性能与安全
- `cache_size=-64000` — 64MB 页缓存

#### A1.2 数据表创建
在 `Database.__init__` 中自动执行建表 SQL：
1. `mails` 表（邮件元数据，字段见 design.md 4.5.3）
2. `execution_records` 表（流程执行记录）
3. `seen_message_ids` 表（去重缓存）
4. `classify_cache` 表（分类结果缓存）
5. `tasks` 表（容错恢复的任务状态表，见 design.md 12.1）
6. `failed_notifications` 表（通知失败队列，见 design.md 4.4.5）
7. 配套索引（按 design.md 4.5.3）

#### A1.3 邮件元数据仓储
实现 `src/core/storage/mail_repository.py`：
```python
class MailRepository:
    def __init__(self, db: Database)
    def upsert_mail(mail: MailData) -> None                # 插入或更新元数据
    def get_mail(message_id: str) -> dict | None           # 查询元数据
    def list_mails(category: str | None,                  # 按分类/状态/日期筛选
                  status: str | None,
                  limit: int = 100,
                  offset: int = 0) -> list[dict]
    def update_status(message_id: str, status: str) -> None  # new/processing/processed/archived
    def update_category(message_id: str,                    # 更新 AI 分类结果
                       category: str,
                       priority: str,
                       confidence: float,
                       need_reply: bool) -> None
    def count_by_category() -> dict[str, int]              # 按分类统计（统计面板）
    def count_unread() -> int
```

#### A1.4 去重缓存仓储
实现 `src/core/storage/cache_repository.py`：
```python
class CacheRepository:
    def __init__(self, db: Database)
    def is_seen(message_id: str, account_id: str) -> bool
    def mark_seen(message_id: str, account_id: str) -> None
    def get_all_seen_ids(account_id: str) -> set[str]      # 兼容旧接口
    # classify_cache
    def get_classify_cache(mail_hash: str) -> dict | None  # 返回 {category, confidence, ...}
    def set_classify_cache(mail_hash: str,
                           result: dict,
                           ttl_hours: int = 24) -> None
    def cleanup_expired_classify_cache() -> int            # 返回清理条数
    def cleanup_old_seen_ids(days: int = 30) -> int        # 清理近期缓存（永久保留hash前缀）
```

#### A1.5 执行记录仓储
实现 `src/core/storage/execution_repo.py`：
```python
class ExecutionRepository:
    def __init__(self, db: Database)
    def create_record(execution_id: str,
                      mail_id: str,
                      workflow_name: str,
                      workflow_version: str) -> None
    def update_status(execution_id: str,
                     status: str,
                     step_results: list | None = None,
                     error_message: str | None = None,
                     context_snapshot: dict | None = None) -> None
    def list_by_mail(mail_id: str) -> list[dict]
    def list_recent(days: int = 7) -> list[dict]           # 统计面板用
    def count_by_workflow(days: int = 7) -> dict[str, dict] # 每个流程的成功/失败数
```

#### A1.5.1 多级去重补充
在 `CacheRepository` 中补充内容指纹去重和线程去重（design.md 4.5.4）：
```python
# 内容指纹去重（辅助）
def get_content_fingerprint(subject: str, sender: str, send_date: str) -> str:
    """生成内容指纹: md5(subject + sender + send_date.date())"""
    return hashlib.md5(f"{subject}|{sender}|{send_date}".encode()).hexdigest()

def is_duplicate_by_fingerprint(fp: str, lookback_days: int = 7) -> bool
def mark_fingerprint(fp: str) -> None

# 线程去重（基于 In-Reply-To / References）
def get_thread_id(in_reply_to: str | None, references: str | None) -> str | None
def is_thread_seen(thread_id: str) -> bool
def mark_thread_seen(thread_id: str) -> None
```
- 需在 `mails` 表增加 `content_fingerprint TEXT` 和 `thread_id TEXT` 字段
- `parse_email()` 需提取 `In-Reply-To` 和 `References` 邮件头
- 线程去重缓存保留 90 天，定期清理

#### A1.6 MailStore 重构（兼容模式）
修改 `src/storage/mail_store.py`，读写逻辑改为：
- **保存**：元数据写入 SQLite + 正文写入 JSON（保留原路径）
- **加载**：优先从 SQLite 取元数据 + 从 JSON 取正文
- **list_mails**：改为查 `MailRepository.list_mails()` + 懒加载正文
- **get_seen_ids**：改为查 `CacheRepository.get_all_seen_ids()`（兼容 MVP 接口）
- 保留旧的 `data/cache/seen_ids.json` 读取能力（迁移用）

**验收标准：**
- [ ] 首次启动自动创建 data/data.db 及所有表和索引
- [ ] 邮件保存后，mails 表有记录，正文 JSON 同时存在
- [ ] list_mails 分页查询性能：1000 封邮件 < 100ms
- [ ] 去重缓存命中正确，重启后不丢失
- [ ] classify_cache TTL 过期自动清理
- [ ] 单元测试：test_database.py 覆盖增删改查、事务回滚、并发写入

---

### 任务 A2：安全模块 — 密钥管理与日志脱敏

**目标：** 账户密码、LLM API Key、企微 Webhook 密钥统一加密存储，日志自动脱敏，杜绝明文敏感信息。

**具体工作：**

#### A2.1 密钥管理器 SecretManager
实现 `src/core/security/secret_manager.py`，要点：
1. **跨平台密钥派生：**
   - **Windows**（优先）：DPAPI `CryptProtectData`，绑定当前用户
   - **macOS**（优先）：`keyring` 库访问系统 Keychain
   - **Linux/通用降级**：机器特征派生 `PBKDF2(MAC+主机名, salt, 100000次)`
2. **加密算法：** AES-256-GCM（`cryptography.Fernet` 封装）
3. **文件存储：** `config/secrets.enc`，Linux 下 `chmod 600`
4. **核心接口：**
   ```python
   class SecretManager:
       def get_secret(path: str) -> str       # "accounts.account_1" / "webhooks.approval_group"
       def set_secret(path: str, value: str) -> None
       def resolve_template(template: str) -> str  # 解析 ${secrets.xxx} 引用
       def has_secret(path: str) -> bool
   ```
5. **内存缓存：** 解密后数据缓存到 `_secrets_cache`，避免频繁解密
6. **数据结构：** 明文内部结构见 design.md 9.3（accounts / api_keys / webhooks 三层）

#### A2.2 账户配置迁移
修改账户配置逻辑：
1. `config/account.json` 中 `password` 字段不再存 base64，改为引用 `password_ref: "secrets.accounts.default"`
2. 首次启动升级：如果检测到旧 base64 密码 → 自动迁移到 SecretManager，并修改 account.json 为引用格式
3. `AccountDialog` 保存时：密码 → `set_secret("secrets.accounts.default", pwd)`，不从明文读
4. IMAP/SMTP 连接时：通过 `get_secret()` 取密码

#### A2.3 日志脱敏过滤器
实现 `src/core/security/log_sanitizer.py`：
1. `LogSanitizer.sanitize(text)` 正则替换（见 design.md 9.6 的 6 个 PATTERNS）
2. `LogSanitizer.sanitize_dict(data)` 递归字典脱敏
3. `SanitizeFilter(logging.Filter)`：在 `setup_logging()` 中注册到所有 handler
4. 确保以下内容在日志中一律显示为 `***`：
   - password / api_key / secret / token 字段值
   - `sk-` 开头的 OpenAI/DeepSeek 风格 Key
   - Webhook URL 中 `?key=xxx` 部分

#### A2.4 启动安全检查
实现 `src/core/security/security_check.py`：
```python
def run_security_checks() -> list[CheckResult]:
    """返回检查结果列表，severity: HIGH/WARN/NONE"""
    checks = [
        check_secrets_file_permissions,   # Linux: secrets.enc 必须 0600
        check_no_plaintext_secrets,       # 扫描 config/*.json 有无明文字段
        check_ssl_enforcement,            # IMAP/SMTP 必须 SSL=True
        check_default_pbkdf_not_used,     # 警告用户如果使用机器特征派生降级方案
    ]
```
- HIGH 级别问题：`logger.error + page.snack_bar 警告`（不阻止启动，Beta 再考虑）
- WARN 级别：`logger.warning`

#### A2.5 AI & 通知配置的密钥引用
新增配置文件：
- `config/ai.json`：`api_key` 字段改为引用 `"${secrets.api_keys.deepseek}"`
- 企微 Webhook URL：在 `notification_channels.yaml` 中引用 `secrets.webhooks.xxx`
- `AppConfig` / `WorkflowLoader` 统一调用 `SecretManager.resolve_template()` 解析引用

**验收标准：**
- [ ] `config/secrets.enc` 创建后，Linux 权限为 0600
- [ ] `grep -r password config/` 找不到明文密码（排除引用格式说明文档）
- [ ] 任意日志输出包含 `sk-abc123` → 实际输出为 `sk-***`
- [ ] 重启程序后，密码 / API Key / Webhook 正确解密可使用
- [ ] 删除 secrets.enc 后，程序提示密钥丢失并引导重新配置
- [ ] 单元测试：test_security.py 覆盖加密解密、脱敏正则、密钥解析

---

### 任务 A3：数据迁移框架 + MVP→Alpha 迁移脚本

**目标：** MVP (v0.1.0) 用户升级到 Alpha (v0.2.0) 时，已有数据零丢失自动迁移。

**具体工作：**

#### A3.1 迁移框架
实现 `migrations/__init__.py` 中的基类和管理器：
```python
class Migration:
    from_version: str      # e.g. "0.1.0"
    to_version: str        # e.g. "0.2.0"
    def migrate(data_dir: Path, config_dir: Path) -> None  # 迁移逻辑
    def validate(data_dir: Path, config_dir: Path) -> bool # 迁移后校验
    def rollback(data_dir: Path, config_dir: Path) -> None # 失败回滚（重命名备份）

class MigrationManager:
    def __init__(self, data_dir, config_dir)
    def get_current_version() -> str           # 读 data/schema_version.json
    def set_version(version: str) -> None
    def needs_migration() -> bool
    def run_migrations() -> None               # 备份 → 按顺序执行 → 验证 → 更新版本号
    def _backup() -> Path                      # 备份 data/ 和 config/ 到 backup/时间戳/
```

#### A3.2 MVP→Alpha 具体迁移脚本
实现 `migrations/v0.1.0_to_v0.2.0.py`：

| 序号 | 迁移项 | 具体操作 |
|------|--------|----------|
| 1 | **seen_ids 迁移** | 读取 `data/cache/seen_ids.json` → 写入 SQLite `seen_message_ids` 表 → 原文件重命名 `.migrated` |
| 2 | **邮件元数据迁移** | 遍历 `data/mails/*/mail_*.json` → 解析 → 元数据 upsert 到 `mails` 表 → 正文 JSON 文件保留原地 |
| 3 | **账户密码迁移** | 读取 `config/account.json` 的 `password` base64 → 解码 → `SecretManager.set_secret("accounts.default", pwd)` → 原字段替换为 `password_ref: "secrets.accounts.default"` |
| 4 | **配置文件新增** | 生成默认 `config/ai.json`、`config/notification_channels.yaml`、`rules/custom_rules.yaml` 模板 |
| 5 | **目录创建** | 新建 `workflows/`、`templates/`、`data/records/`、`data/feedback/`，写入内置示例 YAML |
| 6 | **schema_version** | 写入 `{"version": "0.2.0", "migrated_at": "..."}` |

**回滚策略：**
- 迁移前整体备份到 `backup/20260803_153000_{schema}/`
- 任一步骤失败 → 调用 rollback → 把 backup 覆盖回原位 → 保留 schema_version 不变 → 报告错误

**main.py 集成：**
在 `AppConfig` 初始化之后、任何业务启动之前，调用：
```python
MigrationManager(Path("./data"), Path("./config")).run_migrations()
```

**验收标准：**
- [ ] 准备 MVP 数据（30 封邮件+已读标记+缓存）→ 启动 Alpha → 迁移后数据完整可用
- [ ] `get_current_version()` 返回 "0.2.0"
- [ ] mails 表记录数 = 原 JSON 文件数
- [ ] 密码迁移后，IMAP 连接测试成功
- [ ] 中途模拟迁移失败（如抛异常）→ rollback 后 MVP 数据原封不动
- [ ] 单元测试：test_migration.py 构造 mock 数据跑完整流程

---

### 任务 A4：AI 分类引擎

**目标：** 新邮件到达 → 规则预筛（快速通道）→ LLM 智能分类（8大类+优先级+需回复+置信度）→ 置信度阈值判断 → 分类结果落库 + GUI 展示。

**具体工作：**

#### A4.1 LLM API 客户端
实现 `src/ai/llm_client.py`，统一抽象多后端：
```python
class LLMClient:
    def __init__(self, provider: str,           # "deepseek" / "openai" / "ollama"
                       api_key: str,
                       base_url: str,
                       model: str,
                       ollama_host: str | None = None)
    def chat_completion(system_prompt: str,
                        user_prompt: str,
                        temperature: float = 0.1,
                        max_tokens: int = 500,
                        timeout: int = 30) -> str:
        """返回纯文本响应（调用方 JSON 解析）"""
```
**后端实现：**
- **DeepSeek / OpenAI 兼容：** `requests.post(f"{base_url}/chat/completions", headers=Authorization, json={model, messages, temperature, max_tokens})`
- **Ollama 本地：** `requests.post(f"{ollama_host}/api/chat", json={model, messages, stream:false})`
- **错误处理：** 网络/超时/认证/限流分类，抛出明确异常（后续降级判断用）
- **请求日志：** 记录 prompt token 估算、耗时，响应日志截断前 500 字（绝不记录敏感内容）

#### A4.2 Prompt 构建器
实现 `src/ai/prompt_builder.py`：
1. **SYSTEM_PROMPT 常量：** 严格对齐 design.md 4.2.3（分类体系8类、3个判断维度、JSON输出格式、2个Few-Shot示例）
2. `build_user_prompt(mail: MailData) -> str`：填入 `{sender} / {sender_domain} / {subject} / {body_summary[:500]} / {attachments} / {send_time}`
3. `parse_response(json_str: str) -> dict`：
   - 解析 JSON，提取 `category / priority / need_reply / confidence / reason`
   - 容错：LLM 输出废话包裹 JSON → 正则提取 `{...}` 再解析
   - 非法 category / priority → 修正为默认值 + confidence 降 0.1
   - 返回标准化 dict，所有字段保证存在

#### A4.3 规则预筛引擎
实现 `src/ai/rule_engine.py`：
```python
class RuleEngine:
    def __init__(self, rules_file: Path)  # 加载 rules/custom_rules.yaml
    def reload() -> None
    def match(mail: MailData) -> RuleMatch | None:
        """如果命中规则，返回 {category, priority, override_ai, auto_tags, matched_rule_name}, 否则 None"""
    def match_all(mail: MailData) -> list[RuleMatch]:
        """返回所有命中规则（按优先级排序），用于调试/测试"""
    def test_rule(rule: dict, mail: MailData) -> tuple[bool, str]:
        """测试单条规则是否命中，返回 (命中, 匹配说明)"""
```

**支持的条件类型（Alpha 实现 8 种）：**
1. `sender == "ceo@company.com"` 精确匹配
2. `sender_domain in ["monitor.system"]` 域名匹配
3. `subject CONTAINS ["告警", "ALERT"]` 关键词包含
4. `subject REGEX "周报|weekly"` 正则匹配
5. `body CONTAINS ["预算", "Q3"]` 正文关键词包含
6. `has_attachment == true` 附件存在性
7. `attachment_count > 0` 附件数量比较
8. `recipient CONTAINS "group@company.com"` 收件人匹配

**条件组合：** 多个条件字段之间为 AND 关系（全部满足才命中）
```yaml
# 单条件
condition: {subject_contains: ["告警", "ALERT"]}

# 多条件 AND
condition:
  subject_contains: ["审批"]
  sender_domain: ["company.com"]
  has_attachment: true
```

**规则优先级与冲突解决：**
```yaml
rules:
  - name: "CEO邮件优先"
    enabled: true                    # 单条规则启停
    priority: 100                    # 数值越大优先级越高，同优先级按文件顺序
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
      override_ai: true

  - name: "审批关键词"
    enabled: true
    priority: 50
    condition:
      subject_contains: ["审批", "请批", "申请"]
    action:
      set_type: "审批类"
      override_ai: false             # 不 override，给 AI 二次确认
```

**冲突解决策略：**
- 多条规则命中时，取 `priority` 最高的规则结果
- 同 priority 的多条命中 → 按文件中出现顺序，取第一条
- `match()` 返回最高优先级结果；`match_all()` 返回全部命中（调试用）
- 未声明 priority 的规则默认 priority=0

**规则直接触发流程（可选）：**
```yaml
rules:
  - name: "紧急告警直接处理"
    enabled: true
    priority: 100
    condition:
      subject_contains: ["P0", "严重故障"]
    action:
      set_type: "告警类"
      set_priority: "紧急"
      override_ai: true
      run_workflow: "alert_handler"  # 直接触发指定流程，不等分类后自动匹配
```
- `run_workflow` 字段：规则命中后直接调用 `WorkflowEngine.run_workflow()` 执行指定流程
- 与正常 `match_and_run` 的关系：`run_workflow` 先执行，`match_and_run` 仍会执行（可配置 `skip_auto_match: true` 跳过自动匹配）

内置默认规则（即使没有 custom_rules.yaml 也生效，priority=0）：
```yaml
rules:
  - name: "监控告警"
    enabled: true
    priority: 0
    condition: {subject_contains: ["告警", "ALERT", "CRITICAL"], sender_domain: "monitor.system"}
    action: {set_type: "告警类", set_priority: "紧急", override_ai: true}
  - name: "审批关键词"
    enabled: true
    priority: 0
    condition: {subject_contains: ["审批", "请批", "申请"]}
    action: {set_type: "审批类", override_ai: false}
```

#### A4.4 分类缓存管理器
实现 `src/ai/cache_manager.py`，基于 `CacheRepository`：
```python
class ClassifyCacheManager:
    def __init__(self, repo: CacheRepository, enable: bool, ttl_hours: int)
    def _hash(mail: MailData) -> str  # md5(subject + sender + send_time.date().iso + body[:100])
    def get(mail: MailData) -> dict | None
    def set(mail: MailData, result: dict) -> None
```

#### A4.5 分类反馈管理器
实现 `src/ai/feedback_manager.py`：
```python
class FeedbackManager:
    def __init__(self, feedback_dir: Path, auto_update_rules: bool)
    def record_feedback(mail_id: str,
                        original_result: dict,
                        corrected_result: dict,
                        reason: str | None = None) -> None
    # 写入 data/feedback/classification_feedback.jsonl（每行 JSON）
    def get_stats() -> dict  # 返回 {total, accuracy_by_category, low_conf_pct, correction_rate}（统计面板）
    def apply_short_term_rules() -> list[str]  # 返回因反馈新增的规则列表（可选实现）
```

#### A4.6 主分类器 AIClassifier
实现 `src/ai/classifier.py`，串联所有组件：
```python
class AIClassifier:
    def __init__(self,
                 llm: LLMClient,
                 rules: RuleEngine,
                 cache_mgr: ClassifyCacheManager,
                 feedback_mgr: FeedbackManager,
                 confidence_threshold_auto: float = 0.7,  # >= 自动确认
                 confidence_threshold_manual: float = 0.5, # < 人工队列
                 classify_mode: str = "hybrid",            # 分类模式
                 llm_enabled: bool = True,                 # LLM 全局开关
                 daily_llm_quota: int = 0,                 # 每日 LLM 调用上限，0=不限
                 category_llm_overrides: dict | None = None) # 按分类控制 LLM 介入

    def classify(mail: MailData,
                 force_ai: bool = False,        # 手动触发时强制走 AI
                 force_rerun: bool = False      # 忽略缓存重新分类
    ) -> ClassifyResult:
        """
        返回:
        {
          "category": str,         # 8大类之一
          "priority": str,         # 紧急/普通/低优先级
          "need_reply": bool,
          "confidence": float,
          "reason": str,
          "source": str,           # "rule" / "llm" / "cache" / "manual"
          "auto_confirm": bool,    # 是否自动确认（>= threshold）
          "tags": list[str]        # 规则自动打标签
        }
        """
```

**分类模式（classify_mode）说明：**

| 模式 | 说明 | LLM 是否介入 |
|------|------|-------------|
| `"hybrid"` | 混合模式（默认）：规则优先，未命中或 override_ai=false 时走 LLM | 视规则结果决定 |
| `"rule_only"` | 仅规则模式：完全不调用 LLM，规则未命中 → 标记"未分类"进入人工队列 | 否 |
| `"ai_only"` | 仅 AI 模式：跳过规则预筛，直接走 LLM（规则仅用于打标签，不决定分类） | 是，必走 |
| `"manual"` | 手动模式：不自动分类，新邮件标记 status="pending_manual" 等待用户手动触发 | 否，需手动触发 |

**按分类 LLM 控制（category_llm_overrides）：**
```python
# config/ai.json 中配置
"category_llm_overrides": {
    "告警类": {"use_llm": false},      # 告警类仅用规则，不走 LLM
    "审批类": {"use_llm": true},       # 审批类必须走 LLM（即使规则命中也不 override）
    "营销类": {"use_llm": false}       # 营销类仅用规则，节省 API 成本
}
```
- 优先级：`category_llm_overrides` > 规则 `override_ai` > `classify_mode` 全局设定
- 例如：classify_mode="hybrid" + 告警类 override use_llm=false → 告警邮件永远不走 LLM

**LLM 调用配额控制：**
```python
# 每日 LLM 调用计数（SQLite tasks 表或单独计数器）
def _check_quota() -> bool:
    """检查今日 LLM 调用是否超限"""
    if self.daily_llm_quota == 0:
        return True  # 不限
    today_count = self._get_today_llm_count()
    return today_count < self.daily_llm_quota

# 配额耗尽时：
# → 降级为规则分类
# → GUI 状态栏显示 "今日 AI 配额已用完 (50/50)"
# → 日志 WARNING 级别
```

**分类流程图（代码逻辑）：**
```
0. 检查 classify_mode
   ├─ "manual" → 直接返回 {category: null, source: "manual", auto_confirm: false}
   │              邮件进入 pending_manual 队列，等用户手动触发
   ├─ "rule_only" → 跳到步骤 2，但步骤 3（LLM）永不执行
   └─ "ai_only" → 跳过步骤 2 的分类判断，直接到步骤 3（规则仅打标签）

1. 查 cache (force_rerun=False 时) → 命中 → 返回 (source="cache")

2. 跑 RuleEngine.match() → 命中
   ├─ 检查 category_llm_overrides[命中分类].use_llm
   │   ├─ false → 直接用规则结果，跳过 LLM → 返回 (source="rule")
   │   └─ true  → 继续走 LLM（即使 override_ai=true 也走）
   └─ 无 override 配置 → 判断 override_ai
       ├─ True 且 classify_mode != "ai_only" → 直接用规则 → 返回 (source="rule")
       └─ False → 规则结果记为 suggestion，继续走 AI

3. 检查 llm_enabled 和 _check_quota()
   ├─ llm_enabled=False 或配额耗尽 → 降级：有规则 suggestion 用规则(confidence-0.1)
   │                                 无规则 → 返回 {category: null, confidence: 0.0}（人工）
   └─ 通过 → 调用 LLM (system_prompt + user_prompt) → parse_response
       └─ 失败/超时 → 有规则 suggestion → 用规则，confidence 降 0.1
                      否则 → 返回 {category: null, confidence: 0.0, auto_confirm: false}（人工）

4. 如果有规则 suggestion 但 AI 不同 → confidence 取 min(ai_confidence, 0.85)（降低）

5. 判断 auto_confirm = confidence >= confidence_threshold_auto

6. 写 cache（仅 source="llm" 时写）

7. _increment_today_llm_count()（仅实际调用了 LLM 时）

8. 返回结果
```

#### A4.7 与邮件拉取集成
修改 `MailScheduler` + `MailFetchWorker`：
1. 拉取到新邮件 → `MailStore.save()` → 保存后立即调用 `AIClassifier.classify(mail)`
2. 分类结果调用 `MailRepository.update_category()` 写入 mails 表
3. 如果 `auto_confirm=True` → 自动触发 `WorkflowEngine.match_and_run(mail)`（见任务A5）
4. 如果 `auto_confirm=False` 或 `classify_mode="manual"` → 标记邮件 status = `"pending_manual"`，GUI 中邮件列表行高亮黄色边框
5. 所有 AI 操作运行在独立 `AIClassifyWorker(QThread)` 中，绝不阻塞拉取线程
6. **手动触发分类**：GUI 中邮件详情页"🔄 重新分类"按钮 → 调用 `classify(mail, force_ai=True, force_rerun=True)`（强制走 AI，忽略缓存和模式限制）

**验收标准：**
- [ ] 规则命中 + override_ai=True → 不调用 LLM，source="rule"
- [ ] 多条规则命中 → priority 最高的规则胜出
- [ ] 规则 enabled=false → 该规则不参与匹配
- [ ] body CONTAINS 条件 → 正文包含关键词时命中
- [ ] has_attachment=true 条件 → 有附件的邮件命中
- [ ] 规则 run_workflow 字段 → 命中后直接触发指定流程
- [ ] RuleEngine.test_rule() → 返回命中状态和匹配说明
- [ ] classify_mode="rule_only" → 任何邮件都不调用 LLM，规则未命中的进入人工队列
- [ ] classify_mode="ai_only" → 跳过规则分类，直接走 LLM（规则仅打标签）
- [ ] classify_mode="manual" → 新邮件不自动分类，全部进入 pending_manual 队列
- [ ] llm_enabled=False → 不调用 LLM，降级为规则/人工
- [ ] category_llm_overrides["告警类"].use_llm=false → 告警邮件即使规则 override_ai=false 也不走 LLM
- [ ] daily_llm_quota=50 且今日已调用 50 次 → 第 51 次降级为规则分类，状态栏显示配额耗尽
- [ ] 构造测试邮件（含审批关键词）→ AI 返回 category="审批类"，confidence>0.7
- [ ] 构造监控告警邮件（含 [ALERT]）→ 规则直接命中，source="rule"
- [ ] LLM 调用超时时 → 自动降级规则/默认，程序不崩溃
- [ ] 相同邮件第二次分类 → 从缓存返回，耗时 < 10ms
- [ ] "重新分类"按钮 → force_ai=True + force_rerun=True，强制走 AI 且忽略缓存
- [ ] 分类结果写入 mails 表 category/priority/confidence/source 字段正确
- [ ] GUI 邮件列表显示分类标签（📋审批/⚠️告警/📰资讯...）
- [ ] 置信度 <0.5 的邮件 → 列表行黄色边框标记 "待人工确认"
- [ ] 单元测试：test_ai_classifier.py 覆盖四种模式、LLM 开关、配额控制、按分类 override、规则命中、LLM 成功/失败/降级、缓存命中、手动强制重分类

---

### 任务 A5：流程引擎 WorkflowEngine

**目标：** 根据 YAML 定义自动匹配并执行邮件处理流程，支持 13 个内置 Action、条件分支/多分支/循环、步骤错误处理、流程版本管理。

**具体工作：**

#### A5.1 流程上下文 WorkflowContext
实现 `src/workflow/context.py`：
```python
class WorkflowContext:
    def __init__(self, mail: MailData,
                 classify_result: dict,
                 variables: dict,
                 secret_mgr: SecretManager)
    def get(path: str) -> Any    # "${mail.subject}" / "${steps.step1.output.amount}" / "${variables.timeout:-30}"
    def set(path: str, value: Any) -> None
    def set_step_output(step_id: str, output: Any) -> None
    def snapshot() -> dict       # 持久化断点续传用
    @classmethod
    def from_snapshot(cls, data: dict) -> "WorkflowContext"
```
**变量解析规则：**
- `${mail.xxx}` → 只读邮件字段
- `${classification.xxx}` → 只读分类结果
- `${variables.xxx:-default}` → 可读写流程变量，支持默认值
- `${steps.step_id.output.xxx}` → 可读写步骤输出
- `${secrets.xxx}` → 委托 `SecretManager.resolve_template`，结果**不写入 snapshot**（安全）

#### A5.2 条件表达式解析器
实现 `src/workflow/condition.py`：
```python
def evaluate_condition(expr: str, ctx: WorkflowContext) -> bool:
    """
    支持的运算（按优先级实现，MVP先实现前80%常见）：
    1. 比较: == != > < >= <=  支持字符串和数字
    2. 逻辑: AND OR NOT (括号)
    3. 包含: xxx CONTAINS "yyy"
    4. 空值: xxx IS NULL / IS NOT NULL
    5. 正则: xxx MATCHES "^\\[紧急\\]"
    """
```
- 表达式先做变量替换 → 再用 AST + 自定义安全 eval（严禁 `eval()` 裸执行）
- 异常：表达式解析失败 → 记录错误日志 → 结果按 False 处理，不崩溃整个流程

#### A5.3 YAML 流程加载器 + 版本管理
实现 `src/workflow/loader.py` 和 `src/workflow/version_manager.py`：

**目录结构（见 design.md 4.3.6）：**
```
workflows/approval_handler/
  ├── 1.0/workflow.yaml
  ├── 1.1/workflow.yaml
  ├── current          # 软链接/或CURRENT文件记录
  └── versions.json    # 版本历史
```

**加载器接口：**
```python
class WorkflowLoader:
    def __init__(self, workflows_dir: Path)
    def list_workflows() -> list[dict]  # [{name, current_version, enabled, description}, ...]
    def load_workflow(name: str, version: str | None = None) -> WorkflowDefinition
    def save_new_version(name: str, yaml_content: str, description: str) -> str  # 返回新版本号
    def rollback(name: str, to_version: str) -> None
```

#### A5.4 步骤执行器 + 内置 Action
实现 `src/workflow/executor.py` 作为调度器，`src/workflow/actions/*.py` 每个 Action 一个文件：

**Action 基类：**
```python
class BaseAction:
    action_name: str
    def __init__(self, ctx: WorkflowContext, config: dict, logger: Logger)
    def execute(self) -> Any   # 返回输出值，写入 ctx.set_step_output
```

**Alpha 阶段必须实现的 13 个 Action（按优先级排序）：**

| 优先级 | Action | 说明 | 核心实现要点 |
|--------|--------|------|--------------|
| 1 | **notify** | 发送企微通知 | 调用 `NotificationEngine.send()`，支持模板变量 |
| 2 | **extract_info** | AI 提取关键字段 | 复用 `LLMClient`，新 Prompt："从以下邮件提取 {fields} 字段，严格 JSON 返回" |
| 3 | **summarize** | AI 生成摘要 | LLM 调用，max_length 控制 |
| 4 | **auto_reply** | 自动回复邮件 | 复用 `SmtpClient`，模板变量渲染正文 |
| 5 | **forward** | 转发邮件 | 复用 `SmtpClient.forward()` |
| 6 | **tag** | 打标签 | 更新 mails 表 tags 字段（JSON 数组） |
| 7 | **move_to_folder** | 移动邮件夹 | IMAP `MOVE` 命令，可选实现（企微 IMAP 支持则启用） |
| 8 | **check_duplicate** | 重复检测 | 查询 execution_repo 相同 key_fields 在 lookback_hours 内的记录数 |
| 9 | **save_attachment** | 保存附件 | 写入 attachments/ 目录，返回保存路径列表 |
| 10 | **save_record** | 保存处理记录 | JSON/CSV 格式，写入 data/records/YYYY-MM-DD/ |
| 11 | **http_request** | 调用外部 API | requests，支持 GET/POST/JSON body，超时 10s |
| 12 | **set_variable** | 设置变量 | `ctx.set()` |
| 13 | **log** | 记录日志 | `logger.log(level, message)` |
| 14 | **execute_script** | 执行自定义脚本 | subprocess 运行 `script_path`，args 变量替换，超时 30s，输出 stdout/stderr |

**每个 Action 的 on_error 策略实现（executor 层统一处理）：**
- `skip` → 记 warn 日志 → continue
- `abort` → 抛异常 → 流程 status=failed
- `retry_then_skip` → 循环 N 次（默认 3）→ 都失败 skip
- `retry_then_abort` → 循环 N 次 → 都失败 abort
- 每次 retry 间隔指数退避 1s/3s/9s

#### A5.5 流程执行引擎
实现 `src/workflow/engine.py`：
```python
class WorkflowEngine:
    def __init__(self, loader: WorkflowLoader,
                       execution_repo: ExecutionRepository,
                       secret_mgr: SecretManager)
    def match_and_run(mail: MailData,
                      classify_result: dict,
                      account_id: str = "default") -> list[str]
        """
        匹配所有 enabled 且 trigger 条件满足的流程，逐一异步执行
        返回执行的 execution_id 列表

        触发模式（trigger_mode，在 workflow YAML 中配置）:
        - "all"（默认）: 所有匹配的流程都执行
        - "first_match": 按流程 priority 降序，仅执行第一个匹配的流程
        - "priority_order": 按 priority 降序顺序执行，前一个失败则不执行后续

        流程优先级:
        - workflow YAML 中 trigger.priority 字段（默认 0，数值越大越优先）
        - first_match 模式下取 priority 最高的流程执行
        """

    def run_workflow(workflow_name: str,
                     mail: MailData,
                     classify_result: dict,
                     force_version: str | None = None) -> str
        """
        执行指定流程（手动触发），返回 execution_id
        异步：内部起 WorkflowExecuteWorker 线程
        """

    def _execute_sync(workflow_def: WorkflowDefinition,
                      ctx: WorkflowContext,
                      execution_id: str) -> None
        """
        真正的同步执行逻辑（Worker 中调用）：
        1. execution_repo.create → status=running
        2. 步骤循环:
           - condition 步骤: evaluate_condition → if_true/if_false goto
           - switch 步骤: 匹配 cases → goto
           - loop 步骤: for items, 内联执行子步骤
           - action 步骤:
               a) 解析 config 中所有变量引用
               b) on_error 策略循环重试
               c) set_step_output
               d) execution_repo.update_status（记录 step_results）
               e) ctx.snapshot() 持久化
        3. 正常结束 → execution_repo.update → status=success
        4. 异常 → execution_repo.update → status=failed + error_message
        5. 邮件状态 mails.status = processed（至少一个流程成功才算）
        """

    def resume_from_step(execution_id: str,
                         from_step_id: str) -> None
        """
        断点续传：从 snapshot 恢复 Context，从指定步骤之后继续执行
        被 TaskRecovery 重启恢复时调用
        """
```

#### A5.6 内置 3 个示例流程
在 `workflows/` 目录生成 YAML 示例：
1. **approval_handler.yaml**（见 design.md 4.3.1）：审批类邮件 → 提取金额 → 金额判断分支 → 大额@所有人 / 普通@审批组 → 群通知 → 保存记录
2. **alert_handler.yaml**：告警类 + 紧急 → 立即通知告警群 + @all + HTTP 调用（可选调用内部告警接口）
3. **default_handler.yaml**：所有邮件兜底 → 普通类汇总通知（可选），确保 match_and_run 不会完全空跑

**流程触发配置示例（trigger 完整结构）：**
```yaml
# workflows/alert_handler.yaml
version: "1.0"
name: "告警邮件处理流程"
enabled: true

trigger:
  mail_type: "告警类"            # 按分类匹配
  priority: 90                   # 流程优先级（数值越大越优先）
  match_mode: "all"              # all / first_match / priority_order
  conditions:                    # 可选：额外过滤条件
    - field: "classification.priority"
      operator: "in"
      value: ["紧急", "普通"]
    - field: "mail.sender_domain"
      operator: "not_in"
      value: ["test.system"]     # 排除测试系统告警
  # 也可以按邮件字段直接匹配（不依赖分类）
  # mail_conditions:
  #   - field: "subject"
  #     operator: "contains"
  #     value: ["P0", "严重故障"]
```

**match_mode 详解：**
| 模式 | 说明 | 使用场景 |
|------|------|---------|
| `all`（默认） | 所有匹配的流程都执行 | 审批流程 + 记录流程同时跑 |
| `first_match` | 按 priority 降序，仅执行第一个匹配的 | 告警有多个处理流程但只想跑最高优先级的 |
| `priority_order` | 按 priority 降序顺序执行，前一个失败则不执行后续 | 串行依赖：先提取信息，成功后再通知 |

**验收标准：**
- [ ] `evaluate_condition("${mail.subject} CONTAINS '审批' AND ${classification.priority} == '紧急'")` 正确返回 bool
- [ ] `${variables.x:-30}` 默认值语法正确解析
- [ ] 审批流程执行：步骤1 extract → 步骤2 金额分支 → 步骤3 大额通知 链路完整，每步输出写入 ctx
- [ ] on_error: retry_then_skip 模拟 action 连续失败 3 次 → 跳过不崩溃，execution 状态仍 success（带 warning）
- [ ] on_error: abort → 中途失败 → execution 状态 failed，错误信息记录入库
- [ ] 流程版本：v1.0/v1.1 并存，切换 current 不影响已保存的执行记录关联版本
- [ ] 断点续传：模拟 step2 后崩溃 → 恢复后从 step3 开始，step1/step2 结果不重算
- [ ] match_mode=first_match：2 个流程都匹配 → 仅执行 priority 更高的
- [ ] match_mode=priority_order：前一个失败 → 后续不执行
- [ ] execute_script Action：执行测试脚本 → stdout 正确写入 ctx step output
- [ ] 规则 run_workflow 字段：规则命中 → 直接触发指定流程
- [ ] 单元测试：test_workflow_engine.py 覆盖条件解析、变量解析、各 Action mock、错误策略、分支跳转、触发模式

---

### 任务 A6：通知引擎 NotificationEngine

**目标：** 企微群机器人 Webhook 通知，支持 markdown/text/image/file、令牌桶限流、消息聚合、频率冷却、指数退避重试、失败持久化队列。

**具体工作：**

#### A6.1 企微渠道实现
实现 `src/notification/channels/wecom_webhook.py`：
```python
class WecomWebhookChannel:
    channel_type = "wecom_webhook"
    def __init__(self, webhook_url: str, timeout: int = 10)
    def send_text(content: str, mentioned_list: list[str] | None = None) -> Response
    def send_markdown(content: str) -> Response
    def send_image(base64_image: str, md5: str) -> Response
    def send_file(media_id: str) -> Response  # (可选 Alpha 不实现文件上传)

    @staticmethod
    def _handle_error(resp: requests.Response) -> None:
        """
        解析企微返回 {"errcode":xxx, "errmsg":...}
        errcode=0  OK
        errcode=45009  rate_limit → 抛出 RateLimitError
        errcode=40014/41001  invalid → 抛出 InvalidParamError
        其他 → 分类为 network/auth/...
        """
```

#### A6.2 模板引擎
实现 `src/notification/template.py`，加载 `templates/*.yaml`：
```python
class TemplateEngine:
    def __init__(self, templates_dir: Path)
    def list_templates() -> list[dict]
    def render(template_name: str, ctx: dict) -> RenderedNotification
        # 返回 {type: "markdown"|"text", content: "渲染后", mentioned: [...]}
        """
        模板语法（自定义轻量，不用 Jinja2 减少依赖）：
          {{subject}}             → 变量替换
          {{attachments | join}}  → 过滤器（join/upper/lower/truncate）
          {% if cond %}...{% endif %} → 条件片段（Alpha 可选实现，MVP 版纯变量替换）
        """
```

#### A6.3 令牌桶限流器
实现 `src/notification/rate_limiter.py`，严格按 design.md 4.4.4：
```python
class TokenBucket:
    def __init__(self, capacity: int, refill_interval_ms: int)
    def acquire(timeout: float | None) -> bool  # 线程安全
        # 先 _refill() → 有令牌 return True
        # 没令牌 → 等下一次 refill 时间，最多 timeout
```
默认配置：`capacity=20, refill_interval_ms=3000`（每 3 秒补充 1 个，上限 20，符合企微 20 条/分钟限制）

#### A6.4 通知队列（优先级 + 聚合 + 冷却）
实现 `src/notification/queue.py`：
```python
class NotificationQueue:
    """
    入队时:
    1. 检查冷却（same_sender 5min / same_subject 10min / global 3条后暂停1min）
    2. 冷却未通过 → return False
    3. 队列满 overflow_strategy=drop_oldest → 弹出旧的入新的

    出队（process_queue 循环线程）:
    1. 优先取紧急 priority 队列
    2. aggregation.enabled 情况下，普通邮件 5 分钟窗口合并:
       相同分类的 N 条 → 变成 "您有 N 封新审批邮件待处理..." 汇总消息
    3. token_bucket.acquire() → 成功 → _send_notification()
    4. 发送成功 → update_cooldown_tracker
    5. 发送失败 → 交给 retry_handler（见下）
    """
```

#### A6.5 重试处理器 + 失败持久化队列
实现 `src/notification/retry_handler.py` 和 `failure_queue.py`：
- **指数退避**：5s → 15s → 45s，`backoff_multiplier=3`，抖动 ±10%
- **错误分类**：`network/timeout/rate_limit` 可重试，`invalid_param/auth_failed` 不重试
- **RateLimitError 特殊处理**：固定等待 60 秒
- **失败后**：写入 `failed_notifications` SQLite 表（含 next_retry_at）
- **后台重试线程**：每 30 分钟扫描一次 `failure_queue.get_retryable()`，过期（24h）自动放弃并记 ERROR 日志

#### A6.6 免打扰时段（DND）
在 `NotificationEngine` 中实现：
```python
def _check_dnd(now: datetime) -> bool:
    """检查当前是否在免打扰时段"""
    dnd_start = config.get("notification.dnd_start", "22:00")
    dnd_end = config.get("notification.dnd_end", "08:00")
    # 跨天逻辑：22:00-08:00 → 当前时间 >= 22:00 或 < 08:00
```
- 紧急邮件（priority="紧急"）：**忽略 DND，立即发送** + @all
- 普通/低优先级邮件：进入 DND 延迟队列，次日 08:00 统一发送汇总
- DND 配置项加入 `notification_channels.yaml`：
  ```yaml
  dnd:
    enabled: true
    start: "22:00"
    end: "08:00"
    bypass_for_urgent: true
  ```
- DND 延迟队列复用 `NotificationQueue`，标记 `deferred_until: 次日08:00`

#### A6.7 通知分发主引擎
实现 `src/notification/engine.py`：
```python
class NotificationEngine:
    def __init__(self,
                 channels_config_path: Path,    # notification_channels.yaml
                 templates_dir: Path,
                 secret_mgr: SecretManager,
                 db: Database,                  # 失败队列表
                 rate_limit_config: dict,
                 retry_config: dict)
    def send_async(notification: OutboundNotification) -> None
        """
        OutboundNotification:
          {
            "category": "审批类",
            "priority": "紧急" | "普通" | "低优先级",
            "template_name": "approval_notification",
            "context": {mail, classification, extracted},
            "mention_override": ["@all"] | None
          }
        流程:
        1. 根据 routing.by_category + by_priority 选择 channels
        2. template.render → 渲染 markdown/text
        3. 入 NotificationQueue
        """
```

**验收标准：**
- [ ] 企微 markdown 消息：标题、加粗、列表、链接渲染正确，@审批组 实际 @人
- [ ] 令牌桶：连续发 22 条 → 前 20 条立即发送，第 21 条等 3 秒（观察日志时间差）
- [ ] 冷却：同一发件人 2 分钟内连发 3 封同类 → 只通知 1 次（日志显示丢弃原因）
- [ ] 聚合：5 分钟内 5 封审批普通邮件 → 合成 1 条汇总通知
- [ ] 频率限制 45009：mock 返回 → 触发 60 秒等待后重试
- [ ] 失败持久化：模拟 3 次重试都失败 → 写入 failed_notifications 表，下次扫描可取出
- [ ] 禁用 `低优先级` 路由（空列表）→ 资讯类邮件不发通知，正确返回
- [ ] 免打扰时段 22:00-08:00 发送通知 → 延迟到次日 08:00 发送（日志记录延迟原因）
- [ ] 单元测试：test_notification.py 覆盖令牌桶线程安全、冷却逻辑、聚合、重试、错误分类、免打扰延迟

---

### 任务 A7：容错恢复（任务状态 + 重启恢复 + 断点续传）

**目标：** 程序崩溃/重启后，正在执行的流程、待发送的通知、待分类的邮件自动恢复继续，不丢任务。

**具体工作：**

#### A7.1 任务状态机 + 仓储
实现 `src/core/recovery/task_recover.py` 中的 TaskRecovery：
```python
class TaskRecovery:
    def __init__(self, db: Database)
    def create_task(type: str,            # mail_fetch / ai_classify / workflow_execute / notification_send
                    mail_id: str | None,
                    workflow_name: str | None,
                    notification_data: dict | None,
                    max_retries: int = 3) -> str  # 返回 task_id

    def update_task_status(task_id: str,
                           status: str,   # pending / running / success / failed / aborted
                           current_step: str | None = None,
                           context_data: dict | None = None,
                           error_message: str | None = None) -> None

    def recover_on_startup(self,
                           classifier: AIClassifier | None,
                           workflow_engine: WorkflowEngine | None,
                           notification_engine: NotificationEngine | None) -> None:
        """
        启动时调用：
        1. status=running → 标记为 failed + error="程序异常退出中断"（因为 running 实际上已中断）
        2. status=pending / failed & attempt_count < max_retries → 按 type 恢复：
           - mail_fetch     → 不特殊处理，下次调度周期会覆盖
           - ai_classify    → 直接 classifier.classify()（邮件已在库）
           - workflow_execute → workflow_engine.resume_from_step(从 snapshot)
           - notification_send → 通知引擎再入队
        3. 清理超过 7 天仍 pending 的 task → status=aborted
        """
```
各引擎执行任务时必须：
- 开始前 `create_task(...)` → 得 task_id
- 步骤中 `update_task_status(running, current_step=xxx, context_data=snapshot)`
- 成功/失败后 `update_task_status(success/failed, ...)`

**main.py 集成时机：** 所有组件初始化完毕后，最后调用 `task_recovery.recover_on_startup(...)`

**验收标准：**
- [ ] 手动构造 data.db 中一条 status=running 的 workflow_execute task → 启动 → 状态变为 failed 并触发 retry
- [ ] 模拟 step2 后崩溃（有 context_data snapshot）→ 恢复后从 step3 开始
- [ ] 清理：pending task created_at 8 天前 → 启动后自动标记 aborted
- [ ] 单元测试：与 workflow_engine 联动测试断点续传

---

### 任务 A8：GUI 增强（AI/流程/模板/通知/统计页面 + 列表增强）

**目标：** Alpha 阶段新增的 5 个配置/展示页面 + 邮件列表/详情的 AI 信息展示组件。

**具体工作：**

#### A8.1 邮件列表增强
修改 `src/gui/mail_list.py`，每行增加：
- **分类标签**（`CategoryBadge` 组件）：📋审批 蓝底白字 / ⚠️告警 红底 / 📰资讯 绿底 / ...
- **置信度指示**：>=0.9 绿色圆点 / 0.7-0.9 蓝点 / 0.5-0.7 黄点 "待确认" / <0.5 红边框
- **优先级标识**：紧急邮件 🔥 emoji 前缀
- **标签展示**：邮件 tags 字段以小标签形式显示（如 "周报"、"VIP"），来自规则自动打标或手动添加
- **筛选下拉框**（列表标题栏右侧）：全部 / 待确认 / 审批类 / 告警类 / ...
- **搜索框**（列表标题栏右侧）：支持按主题、发件人、正文关键词搜索（查 SQLite `WHERE subject LIKE OR sender LIKE`），实时过滤
- **人工确认入口**：右键菜单 "修正分类" → 弹对话框选择正确分类 + 可选原因 → 写入 `FeedbackManager.record_feedback()`
- **手动打标签**：右键菜单 "添加标签" → 输入标签名 → 更新 mails 表 tags 字段

#### A8.2 邮件详情增强
修改 `src/gui/mail_detail.py`，在正文上方增加：
- **AISummaryCard 组件**：
  ```
  ┌─ AI 智能分类 ──────────────────────────────────────────┐
  │ 分类: 📋 审批类    优先级: 普通    需回复: ✅ 是       │
  │ 置信度: 0.92 (自动确认)    来源: AI                    │
  │ 理由: 包含审批关键词和附件                              │
  │                                                         │
  │ [📝 修正分类]  [🔄 重新分类 ▾]                          │
  │                  ├ 重新分类（按当前模式）               │
  │                  ├ 强制 AI 分类（忽略模式和缓存）       │
  │                  └ 强制规则分类（不走 LLM）             │
  ├─ AI 摘要 ──────────────────────────────────────────────┤
  │ 这是 Q3 部门预算审批邮件，申请金额 125,000 元...       │
  │ [生成摘要]（如果还没生成则显示按钮，已生成显示文本）    │
  ├─ 执行流程 ──────────────────────────────────────────────┤
  │ ✅ approval_handler v1.1 (成功)   耗时: 2.3s   [详情] │
  │ ❌ alert_handler v1.0 (跳过-不满足触发)                  │
  └─────────────────────────────────────────────────────────┘
  ```
- **"重新分类"按钮三种行为（下拉菜单）：**
  - **重新分类（按当前模式）**：`classify(mail, force_rerun=True)` — 忽略缓存，按当前 classify_mode 重跑
  - **强制 AI 分类**：`classify(mail, force_ai=True, force_rerun=True)` — 无论 classify_mode/llm_enabled/配额如何，强制走 LLM
  - **强制规则分类**：临时以 rule_only 模式运行一次 — 不走 LLM，仅用规则
- **分类来源标识**：AISummaryCard 显示 `来源: AI` / `来源: 规则` / `来源: 缓存` / `来源: 人工`，让用户清楚分类是如何产生的
- **流程执行详情按钮** → 弹出对话框显示步骤列表：step1 ✅ extract_info → step2 ✅ check_duplicate → step3 ➡️ 金额分支(>10万) → step4_high ✅ notify...
- **操作按钮功能实现**（当前 MVP 中 4 个按钮无 on_click 事件，需全部接入）：
  - [回复] → 打开写邮件对话框（见任务 A10），预填收件人 = 原发件人，主题 = "Re: " + 原主题，正文引用原邮件
  - [转发] → 打开写邮件对话框，主题 = "Fwd: " + 原主题，正文附带原邮件全文
  - [标记已读/未读] → 调用 `ImapClient.mark_as_read()` + 更新 mails 表 `is_read` 字段 + 列表刷新
  - [删除] → 确认对话框 → 标记 mails 表 `status='archived'`（不物理删除）+ 列表移除
- **HTML 正文渲染修正**（当前直接把 `body_html` 塞给 `ft.Markdown` 导致标签显示为明文）：
  - 有 `body_html` 时：使用 `ft.Markdown` 先做 HTML→Markdown 转换（或用 `ft.Container` + `ft.Text` selectable 模式显示纯文本 fallback）
  - 仅 `body_text` 时：直接 `ft.Markdown` 渲染
  - 提供"切换 HTML/纯文本"按钮供用户选择渲染模式

#### A8.3 新增页面（侧栏扩展）
修改 `src/gui/main_window.py`，侧栏在原有 5 个分类下，增加分割线 + 7 个新入口：
```
─── 分割线 ───
📊 统计面板
🤖 AI 设置
⚙️ 流程管理
📝 模板管理
📢 通知配置
⏰ 调度配置
📜 运行日志
```
点击 → 中间区域（邮件列表+详情位置整体替换）显示对应独立页面。

**已发送邮件视图**：侧栏"📤 已发送"点击后，邮件列表切换为查询 `mails` 表 `is_sent=1` 的记录，复用同一列表组件。

#### A8.4 统计面板页面（stats_page.py）
卡片式布局：
```
[ 今日概览 ]
  收到: 28   已分类: 28   自动确认: 23   待人工: 5   流程成功: 18
[ 分类分布 (饼图或柱状条形图，Flet 无内置图表用彩色进度条比例替代) ]
  审批类 ████████░░░░ 40%  12封
  告警类 ████░░░░░░░░ 20%   6封
  ...
[ AI 准确率 (近7天) ]
  总体 92%  ██████████░░
  分类明细: 审批 95% / 告警 100% / 协作 85% / ...
[ 处理效率 (近7天折线替代: 列表式每日数据) ]
  08-03: 平均分类耗时 0.8s  流程平均耗时 3.2s
  ...
[ 通知统计 (24h) ]
  成功发送: 42  失败重试: 2  聚合发送: 8批  冷却丢弃: 5
```
数据来源：`MailRepository.count_by_category()`、`FeedbackManager.get_stats()`、`ExecutionRepository.count_by_workflow()`、通知引擎自己的 stats 计数器。

#### A8.5 AI 设置页面（ai_config_page.py）
```
─── 分类模式 ────────────────────────────────────
分类模式: [混合模式（规则优先） ▾]
  ├ 混合模式（规则优先）  — 规则命中且 override_ai 时跳过 LLM，其余走 AI
  ├ 仅规则模式            — 完全不调用 LLM，规则未命中的进人工队列
  ├ 仅 AI 模式            — 跳过规则预筛，直接走 LLM（规则仅打标签）
  └ 手动模式              — 不自动分类，新邮件等用户手动触发

[x] 启用 LLM 分类         ← 全局开关，关闭后等同"仅规则模式"
    今日已用: 12 / [50] 次  ← 配额显示（0=不限）

─── LLM 后端 ────────────────────────────────────
Provider: [DeepSeek ▾]    OpenAI / DeepSeek / Ollama
API Key: [••••••••••] [显示] [测试连接]
Base URL: [https://api.deepseek.com]
Model: [deepseek-chat]
Temperature: [0.1]
超时 (秒): [30]

─── LLM 调用配额 ────────────────────────────────
[ ] 启用每日配额限制    每日上限: [50] 次
    配额耗尽时: [降级为规则分类 ▾]  / 降级为规则分类 / 进入人工队列

─── 按分类控制 LLM 介入 ─────────────────────────
  分类         使用 LLM
  审批类       [☑] 是    ← 即使规则命中也走 AI 二次确认
  告警类       [☐] 否    ← 仅用规则，不走 LLM
  通知类       [☑] 是
  会议类       [☑] 是
  协作类       [☑] 是
  资讯类       [☐] 否    ← 节省 API 成本
  营销类       [☐] 否
  垃圾类       [☐] 否

─── 置信度阈值 ──────────────────────────────────
  自动确认阈值: [0.7 ━━━━●━━━━━ 0.9] 滑块
  人工确认阈值: [0.5 ━━━●━━━━━━ 0.7] 滑块

─── 分类缓存 ────────────────────────────────────
  [x] 启用分类缓存    缓存有效期: [24] 小时

─── 规则引擎 ────────────────────────────────────
  [x] 启用规则预筛    规则文件: ./rules/custom_rules.yaml [编辑] [重载]

  规则列表:
  ┌──────────────────────────────────────────────────────────────┐
  │ 启用  优先级  名称             条件              动作         │
  │ [☑]   100    CEO邮件优先      sender==ceo...    审批/紧急     │
  │ [☑]    90    监控告警识别      subject含告警...  告警/紧急     │
  │ [☑]    50    审批关键词        subject含审批...  审批/override │
  │ [☐]     0    周报自动归类      subject正则...    资讯/标签     │
  │                                                               │
  │ [测试规则]  [+ 新增]  [导入]                                   │
  └──────────────────────────────────────────────────────────────┘

  规则测试:
  ┌──────────────────────────────────────────────────────────────┐
  │ 选择测试邮件: [从收件箱选择 ▾]  或手动输入:                   │
  │   发件人: [____________________________]                      │
  │   主题:   [____________________________]                      │
  │   正文:   [____________________________]                      │
  │   附件:   [☐ 有附件]  数量: [0]                               │
  │                                                               │
  │ [运行测试]                                                    │
  │                                                               │
  │ 测试结果:                                                     │
  │ ✅ 命中规则: "CEO邮件优先" (priority=100)                     │
  │    分类: 审批类  优先级: 紧急  override_ai: true             │
  │    标签: VIP, 领导                                            │
  │ ❌ 未命中: "监控告警识别" - subject 不包含 [告警/ALERT/CRITICAL]│
  │ ❌ 未命中: "审批关键词" - 被 priority=100 规则覆盖            │
  └──────────────────────────────────────────────────────────────┘
```
- 规则列表中每行可单独启停（checkbox）、编辑（点击行）、删除
- [测试规则] 按钮 → 弹出测试面板，可选已有邮件或手动输入邮件字段 → 运行 `RuleEngine.match_all()` → 显示所有规则的命中/未命中详情
- 测试结果包含未命中原因（如"subject 不包含关键词"），方便用户调试规则
- [编辑] 按钮 → 弹出 YAML 编辑器（Alpha 不实现可视化表单编辑器，Beta 再做）

─── 反馈学习 ────────────────────────────────────
  [x] 自动更新规则引擎    反馈数据目录: ./data/feedback/

[保存] [重置默认]
```
保存后写入 `config/ai.json`，密码走 `SecretManager.set_secret("api_keys."+provider, key)`。

**ai.json 完整配置结构：**
```json
{
  "classify_mode": "hybrid",
  "llm_enabled": true,
  "daily_llm_quota": 50,
  "quota_exhausted_action": "fallback_rule",
  "category_llm_overrides": {
    "审批类": {"use_llm": true},
    "告警类": {"use_llm": false},
    "资讯类": {"use_llm": false},
    "营销类": {"use_llm": false},
    "垃圾类": {"use_llm": false}
  },
  "provider": "deepseek",
  "api_key_ref": "secrets.api_keys.deepseek",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "temperature": 0.1,
  "max_tokens": 500,
  "timeout": 30,
  "confidence_threshold_auto": 0.7,
  "confidence_threshold_manual": 0.5,
  "cache_enabled": true,
  "cache_ttl_hours": 24,
  "rule_engine_enabled": true,
  "feedback_auto_update_rules": true
}
```

#### A8.6 流程管理页面（workflow_page.py）
左侧：流程列表 + 启停开关：
```
审批邮件处理流程  v1.1  [✅启用] [编辑] [版本] [运行一次测试]
告警邮件处理流程  v1.0  [✅启用]
默认处理流程      v1.0  [✅启用]
                          [+ 新建流程]
```
右侧：选中后的 YAML 编辑器（`ft.TextField` multiline，等宽字体）+ [语法检查] [保存为新版本] [回滚到 v1.0]
流程运行测试按钮 → 弹选择邮件对话框 → 选一封 → 立即 run_workflow → 弹窗显示 step 执行过程。

#### A8.7 模板管理页面（template_page.py）
类似流程页：左侧模板列表（approval_notification / alert_notification / daily_summary），右侧：
```
模板类型: [markdown ▾]
模板内容:
  ## 📋 新审批邮件通知
  **审批标题:** {{subject}}
  **申请人:** {{sender_name}}
  ...
[变量参考面板]  可用变量: {{subject}} / {{sender_name}} / {{extracted.amount}} / ...
[保存] [渲染预览]（选一封测试邮件，右侧显示渲染效果）
```

#### A8.8 通知配置页面（notification_page.py）
```
通知渠道 (企微群机器人):
  渠道名称: 审批组
  Webhook URL: [https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=••••••••]
  [x] 启用    优先级: [1]
  [发送测试消息]

路由规则:
  审批类 → [审批组 ▾]   优先级: [紧急→立即, 普通→汇总]
  告警类 → [告警组 ▾]   优先级: [全部→立即+@all]
  资讯类 → [不通知]
  默认   → [审批组 ▾]

频率控制:
  单群每分钟上限: [18] 条
  汇总窗口: [5] 分钟
  冷却: 同发件人 [5] 分钟  同主题 [10] 分钟

[保存]
```

#### A8.9 Worker 扩展（GUI 端）
`src/gui/worker.py` 新增：
- **AIClassifyWorker**：后台分类，信号 `finished(result: dict)` / `error(msg)`
- **WorkflowExecuteWorker**：后台执行流程，信号 `progress(step_id, status)` / `finished(success)` / `error`
- **SendNotificationWorker**：后台通知，Fire-and-forget 为主

**验收标准：**
- [ ] 邮件列表分类标签颜色正确，置信度圆点与数据一致
- [ ] 邮件列表搜索框输入关键词 → 实时过滤显示匹配邮件
- [ ] 邮件列表标签展示正确，手动添加标签后列表即时刷新
- [ ] 右键修正分类 → 反馈数据写入 feedback/*.jsonl
- [ ] 邮件详情回复按钮 → 打开写邮件对话框，收件人/主题预填正确
- [ ] 邮件详情转发按钮 → 打开写邮件对话框，正文附带原邮件
- [ ] 邮件详情标记已读 → IMAP 标记 + 列表未读圆点消失
- [ ] 邮件详情删除 → 确认后归档，列表移除
- [ ] HTML 邮件正文渲染正确，不显示原始 HTML 标签
- [ ] 已发送视图 → 显示已发送邮件列表
- [ ] AI 设置切换 Provider → 保存后 ai.json 字段正确，密码走 secrets.enc
- [ ] AI 设置页切换分类模式 → 保存后立即生效，新邮件按新模式分类
- [ ] AI 设置页关闭 LLM 开关 → 新邮件不再调用 LLM，降级规则/人工
- [ ] AI 设置页按分类控制：取消"告警类"使用 LLM → 告警邮件不走 LLM
- [ ] AI 设置页配额设为 50，今日已用 50 → 状态栏显示"AI 配额已用完"
- [ ] 邮件详情"重新分类"下拉菜单 → 三种模式可选，结果正确更新
- [ ] 邮件详情 AISummaryCard 显示分类来源（AI/规则/缓存/人工）
- [ ] AI 设置页规则列表 → 可单条启停、编辑、删除
- [ ] AI 设置页规则测试 → 选邮件或手动输入 → 显示命中/未命中详情和原因
- [ ] 流程管理页 YAML 语法检查：${未定义变量引用} / 未定义 action 名称 → 红色错误提示
- [ ] 模板渲染预览：选择测试邮件 → 显示渲染后的最终 markdown 纯文本预览
- [ ] 统计面板数字与实际数据库查询一致
- [ ] 通知配置保存后 notification_channels.yaml 写入正确，Webhook 密钥走 secrets.enc 不存明文
- [ ] 调度配置页面保存后 → 调度器实际按新规则运行
- [ ] 运行日志页面 → 实时显示最新日志，可按级别过滤

---

### 任务 A9：端到端集成联调 + 文档

**目标：** 全链路跑通 + 代码健壮性 + 配置文档。

**具体工作：**

#### A9.1 main.py 初始化顺序
最终启动流程：
```
1. 加载配置 AppConfig
2. 初始化日志（加载 SanitizeFilter）
3. MigrationManager.run_migrations()  ← MVP→Alpha
4. 安全检查 run_security_checks()
5. SecretManager 初始化
6. Database (SQLite) + 所有 Repository 初始化
7. LLMClient → RuleEngine → CacheManager → FeedbackManager → AIClassifier
8. WorkflowLoader → WorkflowEngine（注入所有 Action 依赖）
9. TemplateEngine → 各 Channel → NotificationEngine
10. GUI MailApp 启动
11. TaskRecovery.recover_on_startup(三大引擎注入)
12. ImapClient 连接 / MailScheduler 启动
13. GUI 上已有邮件元数据加载显示
```

#### A9.2 失败链路测试清单
手动验证：
- [ ] 断网启动 → 所有组件降级可用，分类结果 confidence=0.0 进入人工，程序不崩溃
- [ ] LLM API Key 错误 → 自动降级规则分类，GUI  SnackBar："AI 连接失败，已降级为规则"
- [ ] 企微 Webhook 失效 → 通知失败后进入失败队列，24h 内不丢失
- [ ] 删除 secrets.enc → 启动引导重新输入密码/API Key/Webhook
- [ ] 高并发场景：连续 50 封邮件到达 → AI/流程/通知队列不丢，SQLite 无写冲突

#### A9.3 requirements.txt 增量
```
# 新增 Alpha 依赖
PyYAML>=6.0
requests>=2.31.0
cryptography>=41.0.0
chardet>=5.0.0
# 可选：keyring>=24.0.0 (macOS/Windows 系统密钥链优化)
```

#### A9.4 设计文档同步
`docs/` 下新增（如不存在则简单写）：
- `README_ALPHA.md`：升级说明、常见问题（"看不到分类标签→检查AI配置" 等）
- `WORKFLOW_GUIDE.md`：内置流程编写指南（给用户写自定义流程看）

**验收标准：**
- [ ] 全新机器（无 config/ 和 data/）首次启动 → 引导配置邮箱 → 配置 AI → 配置通知 → 跑通一封完整的"拉取→分类→流程→通知"链路
- [ ] MVP v0.1.0 旧数据目录 → 升级启动 → 所有旧邮件在库 + 分类字段 null（可手动重新分类）+ 密码不丢失
- [ ] 关闭 LLM（网络断开），连续拉 10 封规则可命中的告警邮件 → 规则分类成功 + 流程执行 + 通知发送，全程无异常日志 ERROR 级

---

### 任务 A10：邮件撰写与发送功能

**目标：** 实现 MVP 中缺失的"写邮件"功能，包括新建邮件、回复、转发，支持纯文本/HTML 正文、附件、发送模板。

**具体工作：**

#### A10.1 写邮件对话框
实现 `src/gui/compose_dialog.py`：
```python
class ComposeDialog:
    """邮件撰写对话框"""
    def __init__(self, page: ft.Page, smtp_client: SmtpClient,
                 mail_store: MailStore, mode: str = "new",
                 reply_to: MailData | None = None,
                 forward_from: MailData | None = None)
    # mode: "new" / "reply" / "forward"
```
**表单字段：**
- 收件人（支持多个，逗号分隔）
- 抄送（可折叠展开）
- 主题（reply 模式自动 "Re: "，forward 模式自动 "Fwd: "）
- 正文编辑区（`ft.TextField` multiline，支持纯文本编辑）
- 附件区（拖拽/点击上传，显示文件名+大小，可删除）
- [发送] [存草稿] [取消] 按钮

**回复/转发预填逻辑：**
- Reply: 收件人 = 原邮件发件人，正文末尾追加 `\n\n--- 原邮件 ---\n发件人: xxx\n主题: xxx\n时间: xxx\n\n{原正文}`
- Forward: 收件人为空，正文追加原邮件全文 + 附件自动附带

#### A10.2 发送模板（邮件发送用）
实现 `src/mail/send_template.py`，加载 `templates/email_templates/*.yaml`：
```yaml
# templates/email_templates/approval_reply.yaml
name: "审批回复模板"
subject: "Re: {{original_subject}}"
body: |
  您好，

  关于{{original_subject}}，已处理完毕。

  此致
  敬礼
attachments: []
```
- 与通知模板（notification templates）是两套独立体系
- 写邮件对话框中可选模板 → 变量替换后填入正文

#### A10.3 发送流程
1. 用户点 [发送] → 校验收件人格式
2. 构建 MIME 邮件（复用 `SmtpClient.send_mail()`）
3. 后台 `MailSendWorker` 线程发送（不阻塞 UI）
4. 发送成功 → 邮件元数据存入 `mails` 表（`is_sent=True`）→ SnackBar 提示成功
5. 发送失败 → SnackBar 显示错误 + 对话框不关闭（允许修改后重试）

#### A10.4 集成到主界面
- [main_window.py](file:////workspace/src/gui/main_window.py) 的"写邮件"按钮 `on_click` → 打开 `ComposeDialog(mode="new")`
- [mail_detail.py](file:///workspace/src/gui/mail_detail.py) 的回复/转发按钮 → 打开 `ComposeDialog(mode="reply/forward")`
- 发送 Worker 结果回调 → 更新 GUI

**验收标准：**
- [ ] 新建邮件：填写收件人/主题/正文 → 发送成功 → "已发送"列表可见
- [ ] 回复邮件：自动预填收件人和主题，正文引用原邮件
- [ ] 转发邮件：自动附带原附件
- [ ] 带附件发送：附件正确送达
- [ ] 发送失败：SnackBar 显示错误，对话框保留内容可重试
- [ ] 发送时不阻塞 UI（Worker 线程）

---

### 任务 A11：调度增强 + 调度配置页面

**目标：** 调度器从单一 IntervalTrigger 升级为支持 Cron 表达式 + 工作时间过滤，GUI 提供可视化配置页面。

**具体工作：**

#### A11.1 调度器增强
修改 [scheduler.py](file:///workspace/src/mail/scheduler.py)：
```python
class MailScheduler:
    def __init__(self, ...,
                 trigger_mode: str = "interval",  # "interval" / "cron" / "mixed"
                 cron_expression: str | None = None,  # "0 */2 * * 1-5" = 工作日每2小时
                 work_hours_only: bool = False,
                 work_hours: dict = {"start": "08:30", "end": "18:30"},
                 work_days: list[int] = [1,2,3,4,5])  # 1=周一

    def start(self):
        if self.trigger_mode == "cron":
            trigger = CronTrigger.from_crontab(self.cron_expression)
        elif self.trigger_mode == "interval":
            trigger = IntervalTrigger(minutes=self.interval_minutes)
        # work_hours_only 过滤：在 trigger 上叠加 hour/day_of_week 限制
        if self.work_hours_only:
            trigger = CronTrigger(
                hour=f"{start_hour}-{end_hour}",
                day_of_week="mon-fri"
            )
```
- [config.py](file:///workspace/src/core/config.py) 已有 `work_hours` 和 `work_days` 字段，但当前从未使用 → 需接入
- 新增配置项 `schedule.trigger_mode` 和 `schedule.cron_expression`

#### A11.2 调度配置页面（schedule_page.py）
```
拉取模式: [定时间隔 ▾]    定时间隔 / Cron 表达式 / 混合模式

定时间隔模式:
  每隔 [5] 分钟拉取一次

Cron 模式:
  Cron 表达式: [0 */2 * * 1-5]
  说明: 秒 分 时 日 月 周
  [ human-readable 预览: "工作日每2小时整点" ]

工作时间过滤:
  [x] 仅在工作时间拉取
  工作日: [☑一][☑二][☑三][☑四][☑五][☐六][☐日]
  工作时间: [08:30] 至 [18:30]

失败重试:
  [x] 拉取失败后自动重试
  重试间隔: [1] 分钟

[保存] [立即拉取一次] [停止调度]
```

#### A11.3 下次拉取时间计算
- 状态栏"下次: HH:mm" → 从 `scheduler.get_next_run_time()` 获取
- Cron 模式下正确显示下一次触发时间

**验收标准：**
- [ ] 间隔模式：每 5 分钟拉取 → 下次时间显示正确
- [ ] Cron 模式：`0 9 * * 1-5` → 仅工作日 9:00 拉取
- [ ] 工作时间过滤：非工作时间段不触发拉取
- [ ] 页面保存后 → 调度器实际按新规则运行
- [ ] "立即拉取一次"按钮 → 手动触发不影响定时计划
- [ ] "停止调度"按钮 → 停止后状态栏显示"调度已停止"

---

### 任务 A12：数据清理策略

**目标：** 按 design.md 4.5.6 定时清理过期数据，避免磁盘膨胀。

**具体工作：**

#### A12.1 清理任务管理器
实现 `src/core/storage/cleanup_manager.py`：
```python
class CleanupManager:
    def __init__(self, db: Database, data_dir: Path, config: dict)
    def run_cleanup(self) -> dict:
        """执行清理，返回 {mails_cleaned: N, attachments_cleaned: N, ...}"""
    def schedule_daily(self, scheduler: BackgroundScheduler):
        """注册每日 03:00 的清理 Cron 任务"""
```

#### A12.2 清理规则
| 数据类型 | 保留期限 | 清理方式 |
|----------|----------|----------|
| 邮件正文 JSON | 30 天 | 删除文件 + SQLite 记录标记 `status='archived'` |
| 附件文件 | 7 天（可配置） | 删除文件，保留元信息 |
| 处理记录 | 90 天 | SQLite DELETE |
| 日志文件 | 30 天 | 删除旧轮转文件 |
| 去重缓存（近期） | 30 天 | SQLite DELETE |
| 分类缓存 | TTL 24h | SQLite DELETE（已过期） |
| 失败通知队列 | 24h 后放弃 | SQLite DELETE |

#### A12.3 配置项
在 `config/app.json` 增加：
```json
{
  "cleanup": {
    "enabled": true,
    "schedule_cron": "0 3 * * *",
    "mail_retention_days": 30,
    "attachment_retention_days": 7,
    "record_retention_days": 90,
    "log_retention_days": 30
  }
}
```

#### A12.4 清理日志
- 清理前记录各类型条数
- 清理后记录释放空间大小
- 清理结果写入运行日志（INFO 级别）

**验收标准：**
- [ ] 手动触发清理 → 30 天前的邮件正文文件被删除，SQLite 记录标记 archived
- [ ] 7 天前的附件文件被删除
- [ ] 清理后日志显示 "清理完成：邮件 15 封，附件 8 个，释放空间 125MB"
- [ ] 每日 03:00 自动执行（Cron 任务注册成功）
- [ ] 清理过程中不影响正常邮件拉取/分类/流程

---

### 任务 A13：附件处理策略升级 + 解析器增强

**目标：** 按 design.md 4.1.4 实现附件大小分级下载、危险类型拦截、规范化存储；按 4.1.5 引入 chardet 自动字符集检测。

**具体工作：**

#### A13.1 附件下载与存储
修改 [parser.py](file:///workspace/src/mail/parser.py) 的 `extract_attachments()` 和 [imap_client.py](file:////workspace/src/mail/imap_client.py) 的邮件拉取流程：

**大小分级策略（design.md 4.1.4）：**
| 大小 | 策略 |
|------|------|
| < 5MB | 自动下载，保存到本地 |
| 5-50MB | 仅记录元信息，按需下载（GUI 提供"下载"按钮） |
| > 50MB | 警告提示，需用户确认 |
| > 200MB | 拒绝下载，仅记录元信息 |

**存储规则：**
- 目录：`data/attachments/2026-08/`（按年月）
- 文件名：`{日期}_{发件人}_{原文件名}`，同名追加序号
- 危险扩展名拦截：`.exe / .bat / .scr / .cmd / .ps1` → 不下载，标记 `blocked=True`

**附件配置（加入 app.json）：**
```json
{
  "attachment": {
    "auto_download_max_size": 5242880,
    "manual_download_max_size": 52428800,
    "blocked_extensions": [".exe", ".bat", ".scr", ".cmd", ".ps1"],
    "storage_path": "./data/attachments/",
    "cleanup_days": 7
  }
}
```

#### A13.2 chardet 字符集自动检测
修改 [parser.py](file:///workspace/src/mail/parser.py) 的 `decode_payload()`：
```python
import chardet

def decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset()
    if charset:
        try:
            return payload.decode(charset)
        except (UnicodeDecodeError, LookupError):
            pass
    # chardet 自动检测
    detected = chardet.detect(payload)
    if detected['confidence'] > 0.8:
        try:
            return payload.decode(detected['encoding'])
        except (UnicodeDecodeError, LookupError):
            pass
    # 最终回退
    for enc in CHARSET_FALLBACK:
        try:
            return payload.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return payload.decode("utf-8", errors="replace")
```

#### A13.3 In-Reply-To / References 提取
修改 `parse_email()`，提取邮件头中的线程关联字段：
```python
in_reply_to = msg.get("In-Reply-To", "")
references = msg.get("References", "")
```
存入 `MailData` 新增字段 `in_reply_to: str | None` 和 `references: str | None`，供 A1.5.1 线程去重使用。

#### A13.4 GUI 附件交互
修改 [mail_detail.py](file:///workspace/src/gui/mail_detail.py) 附件区域：
- 已下载附件：显示 [打开] [在文件夹中显示] 按钮
- 未下载附件（5-50MB）：显示 [下载] 按钮
- 被拦截附件：显示 ⚠️ "已拦截危险文件类型"
- 超大附件（>50MB）：显示 [确认下载] 按钮 + 警告

**验收标准：**
- [ ] 3MB 附件 → 自动下载到 `data/attachments/2026-08/` 目录
- [ ] 10MB 附件 → 仅显示元信息，点"下载"后保存
- [ ] `.exe` 附件 → 标记拦截，不下载，GUI 显示警告
- [ ] chardet 检测：构造 GBK 编码但未声明 charset 的邮件 → 正确解码
- [ ] In-Reply-To 和 References 字段正确提取到 MailData
- [ ] 附件文件名包含发件人和日期前缀，同名文件自动追加序号

---

### 任务 A14：运行日志页面 + 配置热重载

**目标：** GUI 提供实时日志查看页面；配置文件修改后引擎自动感知重载。

**具体工作：**

#### A14.1 运行日志页面（log_page.py）
实现 `src/gui/pages/log_page.py`：
```
┌─ 运行日志 ──────────────────────────────────────────────────┐
│ 级别: [全部 ▾]  模块: [全部 ▾]  搜索: [___________]  [暂停] │
│──────────────────────────────────────────────────────────────│
│ 2026-08-03 10:30:15 | INFO  | mail.imap       | 连接成功     │
│ 2026-08-03 10:30:16 | INFO  | mail.imap       | 发现 3 封... │
│ 2026-08-03 10:30:18 | DEBUG | ai.classifier   | 规则未命中... │
│ 2026-08-03 10:30:20 | INFO  | workflow.engine | 执行审批流程  │
│ 2026-08-03 10:30:22 | ERROR | notification    | Webhook 超时  │
│ ...                                                          │
│                                                              │
│ [清空显示] [导出日志]              自动滚动: [☑]            │
└──────────────────────────────────────────────────────────────┘
```
**实现方式：**
- 自定义 `logging.Handler` 子类 `MemoryLogHandler`：缓存最近 1000 条日志到内存 deque
- 日志页面定时（每 2 秒）从 `MemoryLogHandler` 拉取新日志 → 追加到 `ft.ListView`
- 级别/模块过滤：前端过滤，不重新读文件
- 搜索：前端全文匹配
- 自动滚动：新日志到达时自动滚动到底部（可暂停）
- 历史日志：[加载更多] 按钮 → 从 `logs/app.log` 文件读取更早的日志

#### A14.2 配置热重载
实现 `src/core/config_watcher.py`：
```python
class ConfigWatcher:
    """监听配置文件变化，触发对应引擎重载"""
    def __init__(self):
        self._watchers = {}  # path -> (callback, last_mtime)

    def watch(self, path: Path, callback: Callable):
        """注册文件监听"""
        self._watchers[path] = (callback, path.stat().st_mtime)

    def check_all(self):
        """定时检查所有监听文件是否变化（每 5 秒由调度器触发）"""
        for path, (callback, last_mtime) in self._watchers.items():
            if not path.exists():
                continue
            current_mtime = path.stat().st_mtime
            if current_mtime != last_mtime:
                logger.info(f"配置文件已变更: {path}")
                try:
                    callback()
                except Exception as e:
                    logger.error(f"重载配置失败: {path}: {e}")
                self._watchers[path] = (callback, current_mtime)
```
**注册的监听项：**
| 文件 | 回调 |
|------|------|
| `rules/custom_rules.yaml` | `rule_engine.reload()` |
| `workflows/*/current/workflow.yaml` | `workflow_loader.reload_current()` |
| `templates/*.yaml` | `template_engine.reload()` |
| `config/ai.json` | `classifier.reload_config()` |
| `config/notification_channels.yaml` | `notification_engine.reload_config()` |

- 使用 mtime 轮询而非 watchdog/inotify，避免额外依赖
- 每 5 秒检查一次（注册到 APScheduler 的 interval trigger）
- 重载失败 → 记录 ERROR 日志 + SnackBar 提示，继续使用旧配置

**验收标准：**
- [ ] 日志页面实时显示新产生的日志（延迟 < 3 秒）
- [ ] 级别过滤：选 "ERROR" → 仅显示错误日志
- [ ] 搜索 "IMAP" → 仅显示包含 IMAP 的日志行
- [ ] 暂停按钮 → 新日志不自动追加，恢复后继续
- [ ] 修改 `rules/custom_rules.yaml` → 5 秒内规则引擎自动重载（日志记录 "规则已重载"）
- [ ] 修改 `config/ai.json` → 分类器重载配置，新阈值立即生效
- [ ] 修改 workflow YAML → 流程引擎重载，下次执行使用新版本

---

## 开发顺序与依赖

```
A1 (SQLite存储)  ──┐
A2 (安全/密钥)    ├── 并行开发
A3 (数据迁移框架) ─┘        A13 (附件+解析器增强) ← 可与第1批并行
          │
          ▼
A1+A2+A3 验收通过
          │
          ▼
A4 (AI分类引擎) ─────────┐
                         ├── 并行开发
A5 (流程引擎)            │
                         │
A6 (通知引擎)   ─────────┘
          │
          ▼
A7 (容错恢复) （依赖 A4/A5/A6 引擎 API）
          │
          ▼
A8 (GUI增强) ─── A10 (写邮件) ─── A11 (调度增强) ── 并行
          │
          ▼
A12 (数据清理)   A14 (日志页+热重载) ← 也可与 A8 并行
          │
          ▼
A9 (集成联调)
```

**开发批次：**

| 批次 | 任务 | 预计工作量 | 依赖 |
|------|------|-----------|------|
| 第1批 | A1 + A2 + A3 + A13 | 基础设施 + 解析器增强 | 无，可独立开发与测试 |
| 第2批 | A4 + A5 + A6 | 三大核心引擎 | 依赖 A1（存储）/A2（密钥）/A3（迁移已跑） |
| 第3批 | A7 + A8 + A10 + A11 | 容错 + GUI + 写邮件 + 调度 | 依赖 A4+A5+A6 的引擎接口定义稳定 |
| 第4批 | A12 + A14 | 数据清理 + 日志/热重载 | 依赖 A8 GUI 框架就绪 |
| 第5批 | A9 | 集成联调 | 全部 |

---

## Alpha 明确排除（留给 Beta/后续）

| 功能 | 排除原因 | 版本 |
|------|----------|------|
| 多账户支持 | 工作量大，需重构 UI 多处 | Beta |
| IMAP IDLE 实时推送 | 需长连接管理+重连策略 | Beta |
| DPAPI/Keychain 原生密钥封装加密 | Alpha 用 PBKDF 机器特征派生方案 | Beta |
| 邮件线程（会话）聚合展示 | Alpha 已实现线程去重（In-Reply-To），但 UI 会话视图留给 Beta | Beta |
| 批量操作（批量标记已读/删除）| GUI 交互 | Beta |
| 自定义规则 GUI 编辑器 | Alpha 仅 YAML 编辑 + 热重载 | Beta |
| 飞书/钉钉等更多通知渠道 | Alpha 仅企微 Webhook | 按需 |
| AI 回复建议生成 | design 6.7 提及，Alpha 仅实现摘要和分类 | Beta |
| 邮件富文本编辑器 | Alpha 写邮件仅纯文本编辑 | Beta |
| 插件系统 (自定义 Action/Classifier/Notifier) | 架构预留，代码不实现 | 远期 |
| EML/PDF 导出 | 低优先级 | 按需 |

---

## 技术约束（Alpha 阶段）

- Python 3.10+
- 新增第三方库：`PyYAML`, `requests`, `cryptography`, `chardet`（`keyring` 可选）
- SQLite 使用标准库 `sqlite3`，WAL 模式
- GUI 不变：Flet，不引入额外 GUI 依赖
- 网络请求全部超时设置（AI/HTTP/Webhook 一律 ≤ 30s）
- 所有新增线程：`daemon=True`，确保程序退出自动结束
- 错误分级：**绝不允许任何引擎异常导致主程序崩溃**，永远降级或进入失败队列
- 敏感数据：配置/代码/日志中绝不明文出现 password / api_key / webhook key
