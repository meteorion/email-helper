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
│   └── daily_summary.yaml
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
│   │   ├── scheduler.py         # 需扩展：拉取后自动触发分类+流程
│   │   └── ...                  # 其他保持不变
│   │
│   ├── storage/
│   │   └── mail_store.py        # 需重构：元数据走 SQLite，正文走 JSON
│   │
│   └── gui/
│       ├── main_window.py       # 需扩展：新增 AI配置/流程/模板/统计 入口
│       ├── worker.py            # 需扩展：AI分类Worker / 流程执行Worker
│       ├── pages/               # 【新增】独立页面组件
│       │   ├── __init__.py
│       │   ├── ai_config_page.py     # AI 配置页面
│       │   ├── workflow_page.py      # 流程管理页面
│       │   ├── template_page.py      # 模板管理页面
│       │   ├── notification_page.py  # 通知配置页面
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
    └── test_migration.py       # 【新增】数据迁移测试
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
  │     ├── notification/queue.py           (队列+聚合)
  │     ├── notification/retry_handler.py   (重试)
  │     └── notification/failure_queue.py   (失败队列)
  │
  ├── core/recovery/task_recover.py         (启动任务恢复)
  │
  └── gui/main_window.py
        ├── gui/pages/ai_config_page.py     (AI 配置页)
        ├── gui/pages/workflow_page.py      (流程管理页)
        ├── gui/pages/template_page.py      (模板管理页)
        ├── gui/pages/notification_page.py  (通知配置页)
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
        """如果命中规则，返回 {category, priority, override_ai, auto_tags}，否则 None"""
```
**支持的条件类型（MVP 精简版先实现前 4 个）：**
1. `sender == "ceo@company.com"` 精确匹配
2. `sender_domain in ["monitor.system"]` 域名匹配
3. `subject CONTAINS ["告警", "ALERT"]` 关键词包含
4. `subject REGEX "周报|weekly"` 正则匹配
5. `send_time IN "friday 17:00-23:59"` 时间窗口（可选延后）

内置默认规则（即使没有 custom_rules.yaml 也生效）：
```yaml
rules:
  - name: "监控告警"
    condition: {subject_contains: ["告警", "ALERT", "CRITICAL"], sender_domain: "monitor.system"}
    action: {set_type: "告警类", set_priority: "紧急", override_ai: true}
  - name: "审批关键词"
    condition: {subject_contains: ["审批", "请批", "申请"]}
    action: {set_type: "审批类", override_ai: false}  # 不 override，给 AI 二次确认
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
                 confidence_threshold_manual: float = 0.5) # < 人工队列

    def classify(mail: MailData) -> ClassifyResult:
        """
        返回:
        {
          "category": str,         # 8大类之一
          "priority": str,         # 紧急/普通/低优先级
          "need_reply": bool,
          "confidence": float,
          "reason": str,
          "source": str,           # "rule" / "llm" / "cache"
          "auto_confirm": bool,    # 是否自动确认（>= threshold）
          "tags": list[str]        # 规则自动打标签
        }
        """
```
**分类流程图（代码逻辑）：**
```
1. 查 cache → 命中 → 返回 (source="cache")
2. 跑 RuleEngine.match() → 命中 → 判断 override_ai
   ├─ True:  直接用规则结果，confidence 规则给 +0.1 加权 → 返回 (source="rule")
   └─ False: 规则结果记为 suggestion，继续走 AI
3. 调用 LLM (system_prompt + user_prompt) → parse_response
   └─ 失败/超时 → 如果有规则 suggestion → 用规则，confidence 降 0.1
                  否则 → 返回 {category: "协作类", confidence: 0.0, auto_confirm: false}（进入人工）
4. 如果有规则 suggestion 但 AI 不同 → confidence 取 min(ai_confidence, 0.85)（降低）
5. 判断 auto_confirm = confidence >= confidence_threshold_auto
6. 写 cache
7. 返回结果
```

#### A4.7 与邮件拉取集成
修改 `MailScheduler` + `MailFetchWorker`：
1. 拉取到新邮件 → `MailStore.save()` → 保存后立即调用 `AIClassifier.classify(mail)`
2. 分类结果调用 `MailRepository.update_category()` 写入 mails 表
3. 如果 `auto_confirm=True` → 自动触发 `WorkflowEngine.match_and_run(mail)`（见任务A5）
4. 如果 `auto_confirm=False` → 标记邮件 status = `"pending_manual"`，GUI 中邮件列表行高亮黄色边框
5. 所有 AI 操作运行在独立 `AIClassifyWorker(QThread)` 中，绝不阻塞拉取线程

**验收标准：**
- [ ] 规则命中 + override_ai=True → 不调用 LLM，source="rule"
- [ ] 构造测试邮件（含审批关键词）→ AI 返回 category="审批类"，confidence>0.7
- [ ] 构造监控告警邮件（含 [ALERT]）→ 规则直接命中，source="rule"
- [ ] LLM 调用超时时 → 自动降级规则/默认，程序不崩溃
- [ ] 相同邮件第二次分类 → 从缓存返回，耗时 < 10ms
- [ ] 分类结果写入 mails 表 category/priority/confidence 字段正确
- [ ] GUI 邮件列表显示分类标签（📋审批/⚠️告警/📰资讯...）
- [ ] 置信度 <0.5 的邮件 → 列表行黄色边框标记 "待人工确认"
- [ ] 单元测试：test_ai_classifier.py 覆盖规则命中、LLM 成功/失败/降级、缓存命中、置信度阈值判断

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

**验收标准：**
- [ ] `evaluate_condition("${mail.subject} CONTAINS '审批' AND ${classification.priority} == '紧急'")` 正确返回 bool
- [ ] `${variables.x:-30}` 默认值语法正确解析
- [ ] 审批流程执行：步骤1 extract → 步骤2 金额分支 → 步骤3 大额通知 链路完整，每步输出写入 ctx
- [ ] on_error: retry_then_skip 模拟 action 连续失败 3 次 → 跳过不崩溃，execution 状态仍 success（带 warning）
- [ ] on_error: abort → 中途失败 → execution 状态 failed，错误信息记录入库
- [ ] 流程版本：v1.0/v1.1 并存，切换 current 不影响已保存的执行记录关联版本
- [ ] 断点续传：模拟 step2 后崩溃 → 恢复后从 step3 开始，step1/step2 结果不重算
- [ ] 单元测试：test_workflow_engine.py 覆盖条件解析、变量解析、各 Action mock、错误策略、分支跳转

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

#### A6.6 通知分发主引擎
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
- [ ] 单元测试：test_notification.py 覆盖令牌桶线程安全、冷却逻辑、聚合、重试、错误分类

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
- **筛选下拉框**（列表标题栏右侧）：全部 / 待确认 / 审批类 / 告警类 / ...
- **人工确认入口**：右键菜单 "修正分类" → 弹对话框选择正确分类 + 可选原因 → 写入 `FeedbackManager.record_feedback()`

#### A8.2 邮件详情增强
修改 `src/gui/mail_detail.py`，在正文上方增加：
- **AISummaryCard 组件**：
  ```
  ┌─ AI 智能分类 ──────────────────────────────────────────┐
  │ 分类: 📋 审批类    优先级: 普通    需回复: ✅ 是       │
  │ 置信度: 0.92 (自动确认)                                │
  │ 理由: 包含审批关键词和附件                              │
  │                                                         │
  │ [📝 修正分类]  [🔄 重新分类]                            │
  ├─ AI 摘要 ──────────────────────────────────────────────┤
  │ 这是 Q3 部门预算审批邮件，申请金额 125,000 元...       │
  │ [生成摘要]（如果还没生成则显示按钮，已生成显示文本）    │
  ├─ 执行流程 ──────────────────────────────────────────────┤
  │ ✅ approval_handler v1.1 (成功)   耗时: 2.3s   [详情] │
  │ ❌ alert_handler v1.0 (跳过-不满足触发)                  │
  └─────────────────────────────────────────────────────────┘
  ```
- **流程执行详情按钮** → 弹出对话框显示步骤列表：step1 ✅ extract_info → step2 ✅ check_duplicate → step3 ➡️ 金额分支(>10万) → step4_high ✅ notify...

#### A8.3 新增页面（侧栏扩展）
修改 `src/gui/main_window.py`，侧栏在原有 5 个分类下，增加分割线 + 5 个新入口：
```
─── 分割线 ───
📊 统计面板
🤖 AI 设置
⚙️ 流程管理
📝 模板管理
📢 通知配置
```
点击 → 中间区域（邮件列表+详情位置整体替换）显示对应独立页面。

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
LLM 后端:
  Provider: [DeepSeek ▾]    OpenAI / DeepSeek / Ollama
  API Key: [••••••••••] [显示] [测试连接]
  Base URL: [https://api.deepseek.com]
  Model: [deepseek-chat]
  Temperature: [0.1]
  超时 (秒): [30]

置信度阈值:
  自动确认阈值: [0.7 ━━━━●━━━━━ 0.9] 滑块
  人工确认阈值: [0.5 ━━━●━━━━━━ 0.7] 滑块

分类缓存:
  [x] 启用分类缓存    缓存有效期: [24] 小时

规则引擎:
  [x] 启用规则预筛    规则文件: ./rules/custom_rules.yaml [编辑] [重载]

反馈学习:
  [x] 自动更新规则引擎    反馈数据目录: ./data/feedback/

[保存] [重置默认]
```
保存后写入 `config/ai.json`，密码走 `SecretManager.set_secret("api_keys."+provider, key)`。

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
- [ ] 右键修正分类 → 反馈数据写入 feedback/*.jsonl
- [ ] AI 设置切换 Provider → 保存后 ai.json 字段正确，密码走 secrets.enc
- [ ] 流程管理页 YAML 语法检查：${未定义变量引用} / 未定义 action 名称 → 红色错误提示
- [ ] 模板渲染预览：选择测试邮件 → 显示渲染后的最终 markdown 纯文本预览
- [ ] 统计面板数字与实际数据库查询一致
- [ ] 通知配置保存后 notification_channels.yaml 写入正确，Webhook 密钥走 secrets.enc 不存明文

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

## 开发顺序与依赖

```
A1 (SQLite存储)
   ├── A2 (安全/密钥)       并行开发
   └── A3 (数据迁移框架)
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
A8 (GUI增强)
          │
          ▼
A9 (集成联调)
```

**开发批次：**

| 批次 | 任务 | 预计工作量 | 依赖 |
|------|------|-----------|------|
| 第1批 | A1 + A2 + A3 | 基础设施 | 无，可独立开发与测试 |
| 第2批 | A4 + A5 + A6 | 三大核心引擎 | 依赖 A1（存储）/A2（密钥）/A3（迁移已跑） |
| 第3批 | A7 + A8 | 容错 + GUI | 依赖 A4+A5+A6 的引擎接口定义稳定 |
| 第4批 | A9 | 集成联调 | 全部 |

---

## Alpha 明确排除（留给 Beta/后续）

| 功能 | 排除原因 | 版本 |
|------|----------|------|
| 多账户支持 | 工作量大，需重构 UI 多处 | Beta |
| IMAP IDLE 实时推送 | 需长连接管理+重连策略 | Beta |
| DPAPI/Keychain 原生密钥封装加密 | Alpha 用 PBKDF 机器特征派生方案 | Beta |
| 邮件线程（会话）聚合展示 | 邮件头 References 解析 + 前端 UI | Beta |
| 批量操作（批量标记已读/删除）| GUI 交互 | Beta |
| 自定义规则 GUI 编辑器 | Alpha 仅 YAML 编辑 | Beta |
| 飞书/钉钉等更多通知渠道 | Alpha 仅企微 Webhook | 按需 |
| 插件系统 (自定义 Action/Classifier/Notifier) | 架构预留，代码不实现 | 远期 |
| EML/PDF 导出 | 低优先级 | 按需 |

---

## 技术约束（Alpha 阶段）

- Python 3.10+
- 新增第三方库：`PyYAML`, `requests`, `cryptography`（`keyring` 可选）
- SQLite 使用标准库 `sqlite3`，WAL 模式
- GUI 不变：Flet，不引入额外 GUI 依赖
- 网络请求全部超时设置（AI/HTTP/Webhook 一律 ≤ 30s）
- 所有新增线程：`daemon=True`，确保程序退出自动结束
- 错误分级：**绝不允许任何引擎异常导致主程序崩溃**，永远降级或进入失败队列
- 敏感数据：配置/代码/日志中绝不明文出现 password / api_key / webhook key
