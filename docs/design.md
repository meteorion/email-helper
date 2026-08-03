# 邮件助手 - 系统设计方案

## 1. 产品定位

一款轻量级桌面端邮件助手，面向企业微信（企微）邮件场景，提供定时收发、自定义处理流程、AI 智能分类与差异化处理等能力。无需数据库，所有配置与数据均存储在本地。

---

## 2. 技术选型

| 层面 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 生态丰富，AI/邮件库成熟 |
| GUI | Flet | 基于 Flutter 渲染，Material Design 3，跨平台桌面 UI |
| 邮件协议 | IMAP4 + SMTP | 兼容企微邮箱，支持收发 |
| 定时调度 | APScheduler | 轻量级进程内调度 |
| AI 分类 | 本地 LLM (Ollama) 或远程 API (OpenAI/DeepSeek) | 可配置切换 |
| 数据存储 | JSON 文件 + SQLite(可选) | 配置用 JSON，邮件元数据用 SQLite 轻量存储 |
| 打包 | PyInstaller / Nuitka | 打包为单文件 exe 分发 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    桌面客户端 (GUI) — 主线程                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐          │
│  │ 账户管理  │ │ 流程配置  │ │ 邮件列表  │ │ 运行日志  │          │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘          │
│       │              │              │             │              │
│       └──────────────┴──────┬───────┴─────────────┘              │
│                             │ 回调函数 / page.update()            │
├─────────────────────────────┼───────────────────────────────────┤
│                    后台工作线程 (threading.Thread)                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐ │     │
│  │  │ 邮件引擎    │ │ 调度引擎    │ │ AI 分类引擎        │ │     │
│  │  │ (IMAP/SMTP)│ │ (Scheduler)│ │ (LLM Classifier)  │ │     │
│  │  └────────────┘ └────────────┘ └────────────────────┘ │     │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐ │     │
│  │  │ 流程引擎    │ │ 通知引擎    │ │ 模板引擎          │ │     │
│  │  │ (Workflow) │ │ (Notifier) │ │ (Template)        │ │     │
│  │  └────────────┘ └────────────┘ └────────────────────┘ │     │
│  └────────────────────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────────────────┤
│                    数据层                                        │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────┐           │
│  │ 配置文件  │ │ 本地邮件缓存  │ │ 流程定义文件     │           │
│  │ (JSON)   │ │ (JSON/SQLite)│ │ (YAML)          │           │
│  └──────────┘ └──────────────┘ └──────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 线程模型

```
┌─────────────────────────────────────────────────────────────────┐
│                        主线程 (GUI Thread)                       │
│  - Flet 页面渲染、用户交互 (ft.Page)                             │
│  - 接收后台线程回调，通过 page.update() 刷新 UI                  │
│  - 绝不执行任何阻塞操作                                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 回调函数 (on_finished / on_error)
        ┌──────────────────┼──────────────────────┐
        ▼                  ▼                      ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────────────┐
│ 邮件工作线程   │ │ AI 工作线程    │ │ 流程/通知工作线程      │
│               │ │               │ │                       │
│ - IMAP 连接   │ │ - LLM API调用 │ │ - 流程执行             │
│ - 邮件拉取    │ │ - 分类推理     │ │ - Webhook 通知         │
│ - 邮件发送    │ │ - 摘要生成     │ │ - 文件写入             │
│ - IDLE 监听   │ │               │ │                       │
│ (threading)   │ │ (threading)   │ │ (threading)           │
└───────────────┘ └───────────────┘ └───────────────────────┘

线程间通信方式:
  GUI → 工作线程:  直接调用线程方法 (如 worker.start())
  工作线程 → GUI:  回调函数 (on_finished / on_error / on_progress)
                  回调内部调用 page.update() 刷新 UI
  工作线程间:      通过共享的线程安全队列 (queue.Queue)

关键设计:
  - 每个工作线程独立运行，互不阻塞
  - 长时间任务 (邮件拉取、AI调用) 全部异步化
  - 使用 daemon 线程，确保程序退出时自动清理
  - 支持任务取消 (CancellationToken 模式)
  - 线程崩溃不影响 GUI，错误通过回调回报
```

---

## 4. 核心模块设计

### 4.1 邮件引擎 (MailEngine)

#### 4.1.1 企微邮件获取

```
企微邮箱
    │
    ├── IMAP 连接 ──→ 拉取未读邮件列表
    │       │
    │       ├── 按时间范围筛选
    │       ├── 按发件人筛选
    │       ├── 按主题关键词筛选
    │       └── 按邮件文件夹筛选 (收件箱/自定义文件夹)
    │
    └── 邮件解析
            ├── 基本信息: 发件人、收件人、主题、时间
            ├── 正文内容: 纯文本 / HTML
            ├── 附件处理: 下载、保存、类型识别
            └── 邮件头解析: Message-ID、In-Reply-To (用于线程关联)
```

**连接配置参数:**

| 参数 | 说明 | 示例 |
|------|------|------|
| imap_host | IMAP 服务器地址 | imap.exmail.qq.com |
| imap_port | IMAP 端口 | 993 (SSL) |
| smtp_host | SMTP 服务器地址 | smtp.exmail.qq.com |
| smtp_port | SMTP 端口 | 465 (SSL) |
| username | 邮箱账号 | user@company.com |
| password | 授权码/密码 | **** |
| use_ssl | 是否启用 SSL | true |

#### 4.1.2 邮件发送

```
发送流程:
    构建邮件 ──→ 设置收件人/抄送/密送
         │
         ├── 纯文本/HTML 正文
         ├── 附件列表
         ├── 邮件模板 (可复用)
         └── 发送记录 ──→ 本地日志
```

**发送能力:**
- 单发 / 群发
- 支持 HTML 富文本
- 支持附件
- 支持邮件模板 (预设模板 + 变量替换)
- 发送队列 (失败重试机制)

#### 4.1.3 定时获取与实时推送

```
调度策略 (双模式):
    ┌─────────────────────────────────────────────────────────┐
    │                    混合调度模式                          │
    ├─────────────────────────────────────────────────────────┤
    │  模式1: 定时轮询 (APScheduler)                          │
    │  ┌─────────┐  ┌──────────────────┐                     │
    │  │ Cron 触发│  │ 间隔触发 (N分钟) │                     │
    │  └────┬────┘  └────────┬─────────┘                     │
    │       └────────┬───────┘                                │
    │                ▼                                         │
    │        ┌──────────────┐                                  │
    │        │ 邮件拉取任务  │                                  │
    │        └──────────────┘                                  │
    ├─────────────────────────────────────────────────────────┤
    │  模式2: IMAP IDLE 实时推送 (推荐)                        │
    │  ┌─────────────────────────────────────────────────┐   │
    │  │  1. 建立 IMAP 长连接                             │   │
    │  │  2. 发送 IDLE 命令进入监听状态                    │   │
    │  │  3. 服务器推送新邮件通知 (EXISTS/RECENT)          │   │
    │  │  4. 收到通知后拉取新邮件                          │   │
    │  │  5. 每 25 分钟发送 DONE 并重新 IDLE (防止超时)    │   │
    │  └─────────────────────────────────────────────────┘   │
    │                                                         │
    │  降级策略: IDLE 失败/不支持时自动切换为定时轮询           │
    └─────────────────────────────────────────────────────────┘
```

**IDLE 模式优势:**
- 实时性高，新邮件到达后秒级通知
- 减少无效请求，不浪费服务器资源
- 企微邮箱支持 IMAP4rev1 IDLE (RFC 2177)

**调度配置:**
- 拉取模式: `idle` (推荐) / `polling` / `mixed`
- 定时间隔: 每 N 分钟拉取一次 (轮询模式)
- Cron 表达式: 支持复杂调度 (如工作日 9:00-18:00 每小时)
- 手动触发: GUI 按钮即时拉取
- 多账户独立调度
- IDLE 超时重连: 25 分钟 (自动重发 IDLE)

#### 4.1.4 附件处理策略

```
附件处理流程:
    邮件解析
        │
        ▼
    ┌─────────────────────────────────────────┐
    │  附件大小检查                             │
    ├─────────────────────────────────────────┤
    │  < 5MB    │  自动下载，保存到本地         │
    │  5-50MB   │  按需下载，仅显示信息         │
    │  > 50MB   │  警告提示，需用户确认下载     │
    │  > 200MB  │  拒绝下载，仅记录元信息       │
    └─────────────────────────────────────────┘
        │
        ▼
    ┌─────────────────────────────────────────┐
    │  存储策略                                 │
    ├─────────────────────────────────────────┤
    │  - 按日期目录组织: attachments/2026-08/   │
    │  - 文件名: {日期}_{发件人}_{原文件名}     │
    │  - 自动去重: 同名文件追加序号             │
    │  - 类型识别: 基于扩展名 + Magic Number    │
    │  - 危险类型拦截: .exe, .bat, .scr 等      │
    └─────────────────────────────────────────┘
```

**附件配置:**
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

#### 4.1.5 邮件编码兼容

```
编码处理策略:
    ┌─────────────────────────────────────────────────────────┐
    │  1. 字符集检测                                            │
    │     - 优先读取邮件头 Content-Type: charset=xxx           │
    │     - 未声明时按优先级尝试: UTF-8 → GBK → GB2312 → Latin1│
    │     - 使用 chardet 库进行自动检测 (置信度 > 0.8 采用)    │
    ├─────────────────────────────────────────────────────────┤
    │  2. 主题/发件人解码                                       │
    │     - 支持 RFC 2047 编码字: =?charset?encoding?text?=    │
    │     - 支持 Base64 / Quoted-Printable 编码                │
    │     - 连续编码字合并处理                                  │
    ├─────────────────────────────────────────────────────────┤
    │  3. 正文解码                                              │
    │     - multipart 邮件递归解析各 part                       │
    │     - 每个 part 独立处理编码                              │
    │     - 优先使用 text/plain，备选 text/html                │
    ├─────────────────────────────────────────────────────────┤
    │  4. 容错处理                                              │
    │     - 解码失败时记录原始字节，使用 replacement 字符       │
    │     - 日志记录异常编码情况，便于排查                      │
    └─────────────────────────────────────────────────────────┘
```

**编码处理代码示例:**
```python
def decode_header_value(value: str) -> str:
    """解码邮件头 (主题/发件人等)"""
    decoded_parts = []
    for part, charset in email.header.decode_header(value):
        if isinstance(part, bytes):
            # 尝试声明的 charset，失败则依次尝试
            for enc in filter(None, [charset, 'utf-8', 'gbk', 'gb2312', 'latin1']):
                try:
                    decoded_parts.append(part.decode(enc))
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                decoded_parts.append(part.decode('utf-8', errors='replace'))
        else:
            decoded_parts.append(part)
    return ''.join(decoded_parts)
```

---

### 4.2 AI 分类引擎 (AIClassifier)

#### 4.2.1 分类体系

```
邮件类型 (一级分类):
    ├── 📋 工作邮件
    │     ├── 审批/流程类   ──→ 需要操作处理
    │     ├── 通知/公告类   ──→ 仅需知晓
    │     ├── 会议/日程类   ──→ 日程提醒
    │     └── 协作/沟通类   ──→ 需要回复
    │
    ├── 📰 资讯邮件
    │     ├── 内部通讯/周报
    │     └── 行业资讯/订阅
    │
    ├── 🛡️ 系统邮件
    │     ├── 告警/监控通知
    │     ├── 系统运维通知
    │     └── 自动化报告
    │
    ├── 📢 营销邮件
    │     ├── 推广/广告
    │     └── 活动邀请
    │
    └── 🗑️ 垃圾/无关邮件
          └── 自动归档/忽略
```

#### 4.2.2 分类流程

```
新邮件到达
    │
    ▼
┌─────────────────────────┐
│  预处理                  │
│  - 提取主题、发件人域名  │
│  - 提取正文摘要 (前500字)│
│  - 提取附件列表          │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  规则预筛 (快速通道)     │
│  - 发件人白名单/黑名单   │
│  - 主题关键词匹配        │
│  - 域名匹配              │
│  (命中则直接分类,跳过AI) │
└───────────┬─────────────┘
            │ (未命中)
            ▼
┌─────────────────────────┐
│  AI 智能分类             │
│  - 构建 Prompt           │
│  - 调用 LLM API          │
│  - 解析分类结果          │
│  - 置信度评估            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  分类结果处理            │
│  - 置信度 > 阈值 → 确认  │
│  - 置信度 < 阈值 → 标记  │
│    为"待人工确认"         │
│  - 记录分类日志          │
└─────────────────────────┘
```

#### 4.2.3 Prompt 设计

```
系统提示词 (System Prompt):
    你是一个专业的邮件分类助手，专注于企业微信邮件场景。
    
    ## 分类体系
    请根据邮件内容判断属于以下类别之一:
    - 审批类: 需要审批流程、签字确认、权限申请等
    - 通知类: 公告、政策变更、系统通知等仅需知晓的信息
    - 会议类: 会议邀请、日程安排、时间协调
    - 协作类: 工作沟通、问题讨论、需要回复的邮件
    - 资讯类: 内部通讯、周报月报、行业资讯、订阅内容
    - 告警类: 系统告警、监控通知、异常报告
    - 营销类: 产品推广、广告、活动邀请
    - 垃圾邮件: 无关、诈骗、恶意内容
    
    ## 判断维度
    1. 紧急程度: [紧急, 普通, 低优先级]
       - 紧急: 包含截止时间<24h、"紧急"、"ASAP"等关键词
       - 普通: 常规工作邮件
       - 低优先级: 资讯、营销、可延后处理
    
    2. 是否需要回复: [是, 否]
       - 是: 需要明确回复、提供反馈、确认收到
       - 否: 仅通知、公告、自动发送
    
    3. 置信度: [0.0-1.0]
       - 0.9-1.0: 非常确定，特征明显
       - 0.7-0.9: 较确定，有一定模糊性
       - 0.5-0.7: 不确定，需要人工确认
       - <0.5: 非常不确定，建议人工处理
    
    ## 输出格式
    严格按以下JSON格式返回，不要包含其他内容:
    {
      "category": "分类名称",
      "priority": "紧急/普通/低优先级",
      "need_reply": true/false,
      "confidence": 0.85,
      "reason": "分类理由(50字内)"
    }
    
    ## 示例
    示例1:
    发件人: hr@company.com
    主题: Q3预算审批申请
    正文: 请审批附件中的Q3部门预算...
    输出: {"category":"审批类","priority":"普通","need_reply":true,"confidence":0.95,"reason":"包含审批关键词和附件"}
    
    示例2:
    发件人: system@monitor.com
    主题: [ALERT] CPU使用率超过90%
    正文: 服务器192.168.1.100 CPU使用率持续超过90%...
    输出: {"category":"告警类","priority":"紧急","need_reply":false,"confidence":0.98,"reason":"系统告警，包含ALERT标记"}

用户输入:
    发件人: {sender}
    发件人域名: {sender_domain}
    主题: {subject}
    正文摘要(前500字): {body_summary}
    附件列表: {attachments}
    发送时间: {send_time}
```

**Prompt 优化策略:**
- 使用 Few-Shot Learning，在系统提示词中提供 2-3 个典型示例
- 明确置信度定义，让模型自我评估确定性
- 要求输出分类理由，便于调试和人工审核
- 提供发件人域名、发送时间等上下文信息

#### 4.2.5 置信度定义与处理

```
置信度来源:
    1. LLM 自评估: 模型在输出中直接给出 confidence 字段 (0.0-1.0)
    2. 规则加权: 根据特征匹配程度调整
       - 发件人在白名单: +0.1
       - 主题包含明确关键词: +0.05
       - 历史同类邮件匹配: +0.05
    
置信度处理策略:
    ┌─────────────────────────────────────────────────────────┐
    │  置信度范围    │  处理策略                                │
    ├─────────────────────────────────────────────────────────┤
    │  >= 0.9       │  自动确认，直接执行流程                   │
    │  0.7 - 0.9    │  自动确认，但记录日志供审计               │
    │  0.5 - 0.7    │  标记为"待人工确认"，GUI高亮显示          │
    │  < 0.5        │  不自动分类，进入人工处理队列             │
    └─────────────────────────────────────────────────────────┘
    
阈值配置:
    confidence_threshold_auto: 0.7    # 自动确认阈值
    confidence_threshold_manual: 0.5  # 人工确认阈值
```

#### 4.2.6 分类反馈与学习机制

```
反馈闭环流程:
    ┌─────────────────────────────────────────────────────────┐
    │  1. 用户修正分类                                         │
    │     - 在GUI中修改AI分类结果                              │
    │     - 记录: 原分类、修正后分类、修正原因(可选)           │
    ├─────────────────────────────────────────────────────────┤
    │  2. 反馈数据存储                                         │
    │     - 存储路径: data/feedback/classification_feedback.jsonl│
    │     - 格式: {"timestamp":..., "mail_id":...,              │
    │              "original":{...}, "corrected":{...},         │
    │              "reason":"..."}                              │
    ├─────────────────────────────────────────────────────────┤
    │  3. 反馈应用方式                                         │
    │     a) 短期: 更新规则引擎，相同发件人/主题直接命中规则   │
    │     b) 中期: 累积反馈数据，定期分析优化Prompt示例        │
    │     c) 长期: 导出反馈数据，用于微调本地模型(可选)        │
    ├─────────────────────────────────────────────────────────┤
    │  4. 反馈统计                                             │
    │     - 分类准确率统计 (按类别)                            │
    │     - 低置信度邮件占比                                   │
    │     - 人工修正率                                         │
    │     - 在GUI统计面板展示                                  │
    └─────────────────────────────────────────────────────────┘
```

**反馈配置:**
```json
{
  "feedback": {
    "enabled": true,
    "storage_path": "./data/feedback/",
    "auto_update_rules": true,
    "max_feedback_records": 10000,
    "prompt_optimization_interval_days": 30
  }
}
```

#### 4.2.4 LLM 后端配置

```yaml
ai:
  provider: "deepseek"          # openai / deepseek / ollama (本地)
  api_key: "sk-xxx"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
  temperature: 0.1               # 低温度保证分类稳定性
  max_tokens: 500
  # 本地 Ollama 配置
  ollama_host: "http://localhost:11434"
  ollama_model: "qwen2:7b"
```

---

### 4.3 流程引擎 (WorkflowEngine)

#### 4.3.1 流程定义 (YAML)

每个邮件类型可绑定一个或多个处理流程，流程以 YAML 文件定义，存储在本地 `workflows/` 目录。

**流程定义结构:**
```yaml
# workflows/approval_handler.yaml
version: "1.0"                    # 流程版本号
name: "审批邮件处理流程"
description: "处理审批类邮件，提取关键信息并通知相关人"
enabled: true                     # 是否启用

# 触发条件
trigger:
  mail_type: "审批类"
  # 可选: 额外过滤条件
  conditions:
    - field: "sender_domain"
      operator: "in"
      value: ["company.com", "partner.com"]
    - field: "priority"
      operator: "in"
      value: ["紧急", "普通"]

# 全局变量 (可在步骤中引用)
variables:
  approval_group_webhook: "${secrets.wecom_approval_webhook}"
  max_retry: 3

# 流程步骤
steps:
  - id: "step1"                   # 步骤ID (用于分支引用)
    name: "提取审批信息"
    action: "extract_info"
    config:
      fields: ["审批标题", "审批金额", "申请人", "审批截止时间"]
      use_ai: true
    output: "extracted_info"      # 输出到context的键名
    on_error: "retry_then_skip"   # 错误处理策略

  - id: "step2"
    name: "检查重复"
    action: "check_duplicate"
    config:
      key_fields: ["${extracted_info.审批标题}", "${extracted_info.申请人}"]
      lookback_hours: 24
    output: "is_duplicate"

  - id: "step3"
    name: "金额判断分支"
    type: "condition"             # 条件分支步骤
    condition: "${extracted_info.审批金额} > 100000"
    if_true: "step4_high"         # 条件为真时跳转
    if_false: "step4_normal"      # 条件为假时跳转

  - id: "step4_high"
    name: "大额审批通知"
    action: "notify"
    config:
      channel: "wecom_group"
      webhook: "${approval_group_webhook}"
      template: "high_amount_approval"
      mention: ["@所有人"]
    next: "step5"                 # 显式指定下一步

  - id: "step4_normal"
    name: "普通审批通知"
    action: "notify"
    config:
      channel: "wecom_group"
      webhook: "${approval_group_webhook}"
      template: "normal_approval"
      mention: ["@审批组"]
    next: "step5"

  - id: "step5"
    name: "保存记录"
    action: "save_record"
    config:
      format: "json"
      path: "./data/approvals/"
      data:
        mail_id: "${mail.id}"
        extracted: "${extracted_info}"
        is_duplicate: "${is_duplicate}"
```

#### 4.3.2 条件分支语法

**支持的表达式:**
```yaml
# 比较运算
condition: "${extracted.amount} > 100000"
condition: "${mail.priority} == '紧急'"
condition: "${extracted.category} != '营销类'"

# 逻辑运算
condition: "${extracted.amount} > 50000 AND ${mail.has_attachment} == true"
condition: "${mail.sender_domain} == 'ceo.com' OR ${mail.priority} == '紧急'"

# 包含运算
condition: "${mail.subject} CONTAINS '审批'"
condition: "${mail.tags} CONTAINS 'VIP'"

# 正则匹配
condition: "${mail.subject} MATCHES '^\\[紧急\\].*'"

# 空值判断
condition: "${extracted.deadline} IS NOT NULL"
condition: "${extracted.amount} IS NULL"
```

**分支类型:**
```yaml
# 1. 简单条件分支 (if/else)
- id: "branch1"
  type: "condition"
  condition: "..."
  if_true: "step_true_id"
  if_false: "step_false_id"

# 2. 多分支选择 (switch/case)
- id: "branch2"
  type: "switch"
  field: "${extracted.category}"
  cases:
    - value: "审批类"
      goto: "approval_steps"
    - value: "告警类"
      goto: "alert_steps"
    - value: ["通知类", "资讯类"]
      goto: "info_steps"
  default: "default_steps"

# 3. 循环 (loop) - 用于批量处理
- id: "loop1"
  type: "loop"
  items: "${mail.attachments}"
  item_var: "current_attachment"
  steps:
    - id: "loop_step1"
      action: "save_attachment"
      config:
        file: "${current_attachment.path}"
```

#### 4.3.3 Context 数据结构

**Context 定义:**
```python
# Context 是流程执行过程中的数据容器
# 所有步骤通过 Context 传递数据

class WorkflowContext:
    """流程执行上下文"""
    
    def __init__(self, mail: MailData):
        self.data = {
            # 邮件原始数据 (只读)
            "mail": {
                "id": mail.message_id,
                "subject": mail.subject,
                "sender": mail.sender,
                "sender_domain": mail.sender_domain,
                "recipient": mail.recipient,
                "body": mail.body,
                "body_summary": mail.body_summary[:500],
                "attachments": [
                    {"name": att.filename, "size": att.size, "type": att.mime_type}
                    for att in mail.attachments
                ],
                "send_time": mail.send_time.isoformat(),
                "priority": mail.priority,
                "has_attachment": len(mail.attachments) > 0,
                "tags": mail.tags
            },
            
            # 分类结果 (只读)
            "classification": {
                "category": mail.category,
                "confidence": mail.confidence,
                "need_reply": mail.need_reply
            },
            
            # 流程变量 (可读写)
            "variables": {},  # 从流程定义的 variables 字段初始化
            
            # 步骤输出 (可读写)
            # 格式: {step_id: output_data}
            "steps": {}
        }
    
    def get_value(self, path: str) -> Any:
        """
        通过路径获取值
        示例: "${extracted_info.amount}" -> self.data["extracted_info"]["amount"]
        """
        # 解析路径并获取值
        ...
    
    def set_value(self, path: str, value: Any):
        """设置值"""
        ...
```

**变量引用语法:**
```yaml
# 在配置中引用 context 变量
config:
  webhook: "${variables.approval_webhook}"
  amount: "${steps.step1.output.amount}"
  subject: "${mail.subject}"
  
# 支持默认值
config:
  timeout: "${variables.timeout:-30}"  # 如果变量不存在，使用默认值30
```

#### 4.3.4 内置 Action 类型

| Action | 说明 | 配置项 | 输出 |
|--------|------|--------|------|
| `extract_info` | AI 提取邮件关键信息 | fields, use_ai | 提取的字段字典 |
| `summarize` | AI 生成邮件摘要 | max_length | 摘要文本 |
| `check_duplicate` | 重复邮件检测 | key_fields, lookback_hours | bool |
| `notify` | 发送群通知 | channel, webhook, template | 发送结果 |
| `forward` | 转发邮件 | to, cc | 转发结果 |
| `auto_reply` | 自动回复 | template | 回复结果 |
| `save_attachment` | 保存附件 | path, filename_pattern | 保存路径列表 |
| `save_record` | 保存处理记录 | format, path, data | 文件路径 |
| `tag` | 打标签/标记 | tags | - |
| `move_to_folder` | 移动到指定文件夹 | folder_name | - |
| `execute_script` | 执行自定义脚本 | script_path, args | 脚本输出 |
| `http_request` | 调用外部 API | url, method, headers, body | 响应数据 |
| `set_variable` | 设置流程变量 | name, value | - |
| `log` | 记录日志 | level, message | - |

#### 4.3.5 流程执行引擎

```
邮件进入流程
    │
    ▼
┌───────────────────┐
│  1. 加载流程定义   │
│  2. 检查触发条件   │──(不满足)──→ 跳过，记录日志
└───────┬───────────┘
        │ (满足)
        ▼
┌───────────────────┐
│  3. 初始化 Context │
│     - 注入邮件数据  │
│     - 注入分类结果  │
│     - 初始化变量    │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  4. 执行步骤       │◄────────────────┐
│     - 解析变量引用  │                 │
│     - 执行 Action   │                 │
│     - 保存输出到Ctx │                 │
└───────┬───────────┘                 │
        │                              │
        ▼                              │
┌───────────────────┐                 │
│  5. 错误处理       │                 │
│  - 成功: 继续下一步│                 │
│  - 失败: 重试/跳过 │                 │
│  - 记录错误日志    │                 │
└───────┬───────────┘                 │
        │                              │
        ▼                              │
┌───────────────────┐                 │
│  6. 判断下一步     │                 │
│  - 有next: 跳转    │─────────────────┘
│  - 条件分支: 计算  │
│  - 无下一步: 完成  │
└───────┬───────────┘
        │ (完成)
        ▼
┌───────────────────┐
│  7. 流程完成       │
│  - 记录执行日志    │
│  - 更新邮件状态    │
│  - 持久化 Context  │
└───────────────────┘

异常处理策略 (on_error):
  - retry: 重试 N 次后失败
  - skip: 跳过当前步骤，继续执行
  - abort: 中止整个流程
  - retry_then_skip: 重试 N 次，仍失败则跳过
  - retry_then_abort: 重试 N 次，仍失败则中止
```

#### 4.3.6 流程版本管理

**版本控制机制:**
```
workflows/
├── approval_handler/
│   ├── 1.0/
│   │   └── workflow.yaml
│   ├── 1.1/
│   │   └── workflow.yaml
│   ├── current -> 1.1/          # 符号链接指向当前版本
│   └── versions.json            # 版本历史
└── alert_handler/
    └── ...
```

**versions.json 结构:**
```json
{
  "workflow_name": "审批邮件处理流程",
  "current_version": "1.1",
  "versions": [
    {
      "version": "1.0",
      "created_at": "2026-08-01T10:00:00",
      "description": "初始版本",
      "status": "archived"
    },
    {
      "version": "1.1",
      "created_at": "2026-08-10T14:30:00",
      "description": "增加大额审批判断分支",
      "status": "active",
      "changes": ["新增金额判断分支", "调整通知模板"]
    }
  ]
}
```

**执行记录与版本关联:**
```json
// data/records/2026-08-10/execution_001.json
{
  "execution_id": "exec_20260810_001",
  "mail_id": "msg_12345",
  "workflow_name": "approval_handler",
  "workflow_version": "1.1",        // 记录执行时使用的版本
  "started_at": "2026-08-10T15:00:00",
  "completed_at": "2026-08-10T15:00:05",
  "status": "success",
  "context_snapshot": { ... },       // 执行结束时的 Context 快照
  "step_results": [
    {"step_id": "step1", "status": "success", "output": {...}},
    {"step_id": "step2", "status": "success", "output": true}
  ]
}
```

**版本管理功能:**
- 流程修改时自动创建新版本
- 支持版本回滚 (GUI 操作)
- 执行记录永久关联当时的流程版本
- 支持多版本并存 (A/B 测试)
- 版本差异对比 (GUI 展示)

---

### 4.4 通知引擎 (NotificationEngine)

#### 4.4.1 企微群机器人通知

```
通知渠道:
    ┌──────────────────────────────────────┐
    │         企微群机器人 Webhook          │
    │                                       │
    │  支持的消息类型:                       │
    │  ├── text      纯文本消息             │
    │  ├── markdown  Markdown 富文本        │
    │  ├── image     图片消息               │
    │  ├── news      图文消息               │
    │  └── file      文件消息               │
    │                                       │
    │  高级功能:                             │
    │  ├── @指定人 (mentioned_list)          │
    │  ├── 消息模板 (变量替换)               │
    │  ├── 多群通知 (多个 webhook)           │
    │  └── 频率控制 (防刷屏)                 │
    └──────────────────────────────────────┘
```

#### 4.4.2 通知模板

```yaml
# templates/approval_notification.yaml
name: "审批通知模板"
type: "markdown"
content: |
  ## 📋 新审批邮件通知

  **审批标题:** {{subject}}
  **申请人:** {{sender_name}}
  **申请时间:** {{send_time}}
  **审批金额:** {{extracted.amount}}
  **截止时间:** {{extracted.deadline}}

  > {{summary}}

  **附件:** {{attachments | join: ", "}}

  ---
  请及时处理 [查看详情](mail://{{message_id}})
mentioned:
  - "@审批组"
```

#### 4.4.3 通知策略

```
通知规则:
  - 紧急邮件: 立即通知 + @所有人
  - 普通邮件: 汇总通知 (每 N 分钟)
  - 低优先级: 不通知，仅记录
  - 免打扰时段: 22:00 - 08:00 延迟到次日
```

#### 4.4.4 频率限制策略

```
企微群机器人限制:
  - 官方限制: 每个机器人每分钟最多发送 20 条消息
  - 超过限制会返回错误码 45009
  
频率控制机制:
  ┌─────────────────────────────────────────────────────────────┐
  │  1. 令牌桶算法 (Token Bucket)                                │
  │     - 桶容量: 20 个令牌                                      │
  │     - 填充速率: 每 3 秒 1 个令牌                             │
  │     - 发送前检查令牌，不足则等待或丢弃                       │
  ├─────────────────────────────────────────────────────────────┤
  │  2. 消息合并策略                                             │
  │     - 普通邮件: 5 分钟内合并为一条汇总通知                   │
  │     - 同类邮件: 同一流程的邮件合并通知                       │
  │     - 格式: "您有 N 封新审批邮件待处理"                      │
  ├─────────────────────────────────────────────────────────────┤
  │  3. 优先级队列                                               │
  │     - 紧急邮件: 立即发送，占用令牌                           │
  │     - 普通邮件: 进入队列，批量发送                           │
  │     - 低优先级: 仅在空闲时发送                               │
  ├─────────────────────────────────────────────────────────────┤
  │  4. 冷却期设置                                               │
  │     - 同一发件人: 5 分钟内不重复通知                         │
  │     - 同一主题: 10 分钟内不重复通知                          │
  │     - 全局冷却: 连续 3 条通知后暂停 1 分钟                   │
  └─────────────────────────────────────────────────────────────┘
```

**频率限制配置:**
```json
{
  "notification": {
    "rate_limit": {
      "max_per_minute": 18,
      "token_bucket_size": 20,
      "token_refill_interval_ms": 3000
    },
    "aggregation": {
      "enabled": true,
      "window_minutes": 5,
      "max_batch_size": 10
    },
    "cooldown": {
      "same_sender_minutes": 5,
      "same_subject_minutes": 10,
      "global_pause_after_count": 3,
      "global_pause_duration_ms": 60000
    },
    "queue": {
      "max_size": 100,
      "overflow_strategy": "drop_oldest"
    }
  }
}
```

**频率限制代码示例:**
```python
# core/notification/rate_limiter.py

import time
import threading
from collections import deque

class TokenBucket:
    """令牌桶限流器"""
    
    def __init__(self, capacity: int, refill_interval: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_interval = refill_interval
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, timeout: float = None) -> bool:
        """获取令牌，返回是否成功"""
        start_time = time.time()
        
        while True:
            with self.lock:
                self._refill()
                
                if self.tokens > 0:
                    self.tokens -= 1
                    return True
                
                # 计算下一个令牌的时间
                wait_time = self.refill_interval - (time.time() - self.last_refill)
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
            
            time.sleep(min(wait_time, 0.1))
    
    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed >= self.refill_interval:
            new_tokens = int(elapsed / self.refill_interval)
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now


class NotificationQueue:
    """通知队列管理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.queue = deque(maxsize=config['queue']['max_size'])
        self.rate_limiter = TokenBucket(
            capacity=config['rate_limit']['token_bucket_size'],
            refill_interval=config['rate_limit']['token_refill_interval_ms'] / 1000
        )
        self.cooldown_tracker = {}  # key -> last_send_time
        self.lock = threading.Lock()
    
    def enqueue(self, notification: dict, priority: str = 'normal'):
        """添加通知到队列"""
        item = {
            'notification': notification,
            'priority': priority,
            'enqueued_at': time.time()
        }
        
        with self.lock:
            # 检查冷却期
            if not self._check_cooldown(notification):
                return False
            
            # 队列满时处理
            if len(self.queue) >= self.queue.maxlen:
                if self.config['queue']['overflow_strategy'] == 'drop_oldest':
                    self.queue.popleft()
                else:
                    return False
            
            self.queue.append(item)
            return True
    
    def _check_cooldown(self, notification: dict) -> bool:
        """检查是否在冷却期"""
        now = time.time()
        
        # 检查发件人冷却
        sender_key = f"sender:{notification.get('sender', '')}"
        if sender_key in self.cooldown_tracker:
            elapsed = now - self.cooldown_tracker[sender_key]
            if elapsed < self.config['cooldown']['same_sender_minutes'] * 60:
                return False
        
        # 检查主题冷却
        subject_key = f"subject:{notification.get('subject', '')}"
        if subject_key in self.cooldown_tracker:
            elapsed = now - self.cooldown_tracker[subject_key]
            if elapsed < self.config['cooldown']['same_subject_minutes'] * 60:
                return False
        
        return True
    
    def _update_cooldown(self, notification: dict):
        """更新冷却期记录"""
        now = time.time()
        sender_key = f"sender:{notification.get('sender', '')}"
        subject_key = f"subject:{notification.get('subject', '')}"
        
        self.cooldown_tracker[sender_key] = now
        self.cooldown_tracker[subject_key] = now
    
    def process_queue(self):
        """处理队列中的通知"""
        while self.queue:
            # 获取令牌
            if not self.rate_limiter.acquire(timeout=1.0):
                continue
            
            # 从队列取出
            with self.lock:
                if not self.queue:
                    break
                item = self.queue.popleft()
            
            # 发送通知
            try:
                self._send_notification(item['notification'])
                self._update_cooldown(item['notification'])
            except Exception as e:
                logger.error(f"发送通知失败: {e}")
                # 失败重试逻辑见下一节
```

#### 4.4.5 失败重试机制

```
重试策略:
  ┌─────────────────────────────────────────────────────────────┐
  │  1. 指数退避重试                                             │
  │     - 第 1 次: 等待 5 秒                                     │
  │     - 第 2 次: 等待 15 秒                                    │
  │     - 第 3 次: 等待 45 秒                                    │
  │     - 最大重试次数: 3 次                                     │
  ├─────────────────────────────────────────────────────────────┤
  │  2. 错误分类处理                                             │
  │     - 网络错误: 重试                                         │
  │     - 超时错误: 重试                                         │
  │     - 频率限制 (45009): 等待 60 秒后重试                     │
  │     - 参数错误: 不重试，记录错误                             │
  │     - 认证失败: 不重试，告警                                 │
  ├─────────────────────────────────────────────────────────────┤
  │  3. 失败后处理                                               │
  │     - 重试耗尽: 写入失败队列，稍后重试                       │
  │     - 告警通知: 在 GUI 和日志中显示                          │
  │     - 降级方案: 尝试备用通知渠道 (如果有)                    │
  └─────────────────────────────────────────────────────────────┘
```

**重试配置:**
```json
{
  "notification": {
    "retry": {
      "max_attempts": 3,
      "initial_delay_seconds": 5,
      "backoff_multiplier": 3,
      "max_delay_seconds": 60,
      "retryable_errors": [
        "network_error",
        "timeout",
        "rate_limit_exceeded"
      ]
    },
    "failure_queue": {
      "enabled": true,
      "retry_interval_minutes": 30,
      "max_retry_hours": 24
    }
  }
}
```

**重试代码示例:**
```python
# core/notification/retry_handler.py

import time
import random
from enum import Enum

class NotificationError(Enum):
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit_exceeded"
    INVALID_PARAM = "invalid_param"
    AUTH_FAILED = "auth_failed"

class RetryHandler:
    """重试处理器"""
    
    def __init__(self, config: dict):
        self.max_attempts = config['retry']['max_attempts']
        self.initial_delay = config['retry']['initial_delay_seconds']
        self.backoff_multiplier = config['retry']['backoff_multiplier']
        self.max_delay = config['retry']['max_delay_seconds']
        self.retryable_errors = set(config['retry']['retryable_errors'])
    
    def execute_with_retry(self, func, *args, **kwargs):
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)
                
                # 不可重试的错误
                if error_type not in self.retryable_errors:
                    logger.error(f"通知发送失败 (不可重试): {error_type}")
                    raise
                
                # 计算等待时间
                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt, error_type)
                    logger.warning(
                        f"通知发送失败 (第 {attempt + 1} 次)，"
                        f"{delay} 秒后重试: {error_type}"
                    )
                    time.sleep(delay)
        
        # 重试耗尽
        logger.error(f"通知发送失败 (重试 {self.max_attempts} 次): {last_error}")
        raise last_error
    
    def _calculate_delay(self, attempt: int, error_type: NotificationError) -> float:
        """计算重试延迟"""
        # 频率限制错误，固定等待 60 秒
        if error_type == NotificationError.RATE_LIMIT:
            return 60.0
        
        # 指数退避 + 抖动
        base_delay = self.initial_delay * (self.backoff_multiplier ** attempt)
        delay = min(base_delay, self.max_delay)
        
        # 添加随机抖动，避免多个任务同时重试
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
    
    def _classify_error(self, error: Exception) -> NotificationError:
        """分类错误类型"""
        error_str = str(error).lower()
        
        if 'timeout' in error_str:
            return NotificationError.TIMEOUT
        elif '45009' in error_str or 'rate limit' in error_str:
            return NotificationError.RATE_LIMIT
        elif 'network' in error_str or 'connection' in error_str:
            return NotificationError.NETWORK_ERROR
        elif 'auth' in error_str or '401' in error_str or '403' in error_str:
            return NotificationError.AUTH_FAILED
        else:
            return NotificationError.INVALID_PARAM


class FailureQueue:
    """失败通知队列"""
    
    def __init__(self, db_path: str, config: dict):
        self.db = Database(db_path)
        self.config = config
        self._init_table()
    
    def _init_table(self):
        """初始化失败队列表"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS failed_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_data TEXT NOT NULL,
                error_message TEXT,
                attempt_count INTEGER DEFAULT 0,
                first_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                next_retry_at DATETIME,
                status TEXT DEFAULT 'pending'
            )
        """)
    
    def add_failure(self, notification: dict, error: str):
        """添加失败通知"""
        now = time.time()
        next_retry = now + self.config['failure_queue']['retry_interval_minutes'] * 60
        
        self.db.execute(
            """INSERT INTO failed_notifications 
               (notification_data, error_message, next_retry_at)
               VALUES (?, ?, ?)""",
            (json.dumps(notification), error, next_retry)
        )
    
    def get_retryable(self) -> list:
        """获取可重试的通知"""
        now = time.time()
        max_hours = self.config['failure_queue']['max_retry_hours']
        cutoff = now - max_hours * 3600
        
        rows = self.db.fetchall(
            """SELECT id, notification_data, attempt_count 
               FROM failed_notifications
               WHERE status = 'pending' 
                 AND next_retry_at <= ?
                 AND first_failed_at > ?""",
            (now, cutoff)
        )
        
        return [
            {
                'id': row[0],
                'notification': json.loads(row[1]),
                'attempt_count': row[2]
            }
            for row in rows
        ]
    
    def mark_success(self, notification_id: int):
        """标记成功"""
        self.db.execute(
            "UPDATE failed_notifications SET status = 'success' WHERE id = ?",
            (notification_id,)
        )
    
    def mark_failed(self, notification_id: int, error: str, next_retry: float):
        """标记失败"""
        self.db.execute(
            """UPDATE failed_notifications 
               SET attempt_count = attempt_count + 1,
                   error_message = ?,
                   next_retry_at = ?,
                   last_failed_at = ?
               WHERE id = ?""",
            (error, next_retry, time.time(), notification_id)
        )
    
    def cleanup_expired(self):
        """清理过期记录"""
        max_hours = self.config['failure_queue']['max_retry_hours']
        cutoff = time.time() - max_hours * 3600
        
        self.db.execute(
            "DELETE FROM failed_notifications WHERE first_failed_at < ?",
            (cutoff,)
        )
```

#### 4.4.6 通知渠道配置

```yaml
# config/notification_channels.yaml

channels:
  # 企微群机器人
  wecom_group:
    type: "wecom_webhook"
    webhook_ref: "${secrets.webhooks.approval_group}"
    enabled: true
    priority: 1
    
    # 渠道级别的频率限制
    rate_limit:
      max_per_minute: 18
      max_per_hour: 200
    
    # 消息格式
    message_format: "markdown"
    
    # @配置
    mention_list:
      default: []
      urgent: ["@all"]
  
  # 备用渠道 (可选)
  wecom_backup:
    type: "wecom_webhook"
    webhook_ref: "${secrets.webhooks.backup_group}"
    enabled: false
    priority: 2
    
    # 仅在主渠道失败时使用
    fallback_only: true

# 渠道选择策略
routing:
  # 按邮件类型路由
  by_category:
    审批类: ["wecom_group"]
    告警类: ["wecom_group"]
    通知类: ["wecom_group"]
    default: ["wecom_group"]
  
  # 按优先级路由
  by_priority:
    紧急: ["wecom_group"]
    普通: ["wecom_group"]
    低优先级: []  # 不通知
```

---

### 4.5 本地存储设计

#### 4.5.1 目录结构

```
email-helper/
├── config/
│   ├── app.json              # 全局配置
│   ├── accounts.json         # 邮箱账户配置 (加密存储密码)
│   ├── schedule.json         # 调度配置
│   └── ai.json               # AI 分类配置
│
├── workflows/                # 流程定义目录
│   ├── approval_handler.yaml
│   ├── alert_handler.yaml
│   ├── newsletter_handler.yaml
│   └── default_handler.yaml
│
├── templates/                # 通知模板目录
│   ├── approval_notification.yaml
│   ├── alert_notification.yaml
│   └── daily_summary.yaml
│
├── data/
│   ├── mails/                # 邮件缓存 (按日期)
│   │   ├── 2026-08-03/
│   │   │   ├── mail_{id}.json
│   │   │   └── ...
│   │   └── ...
│   ├── attachments/          # 附件存储
│   ├── records/              # 处理记录
│   │   ├── 2026-08-03.json
│   │   └── ...
│   └── cache/
│       ├── seen_ids.json     # 已处理邮件 ID (去重)
│       └── classify_cache.json  # 分类缓存
│
├── logs/                     # 运行日志
│   ├── app.log
│   ├── mail.log
│   └── workflow.log
│
└── main.py                   # 入口文件
```

#### 4.5.2 账户密码安全

> 详见 [第9章 安全设计](#9-安全设计)

#### 4.5.3 并发写入控制

```
问题场景:
  - 多账户同时拉取邮件，并发写入 data/mails/ 目录
  - 流程引擎和邮件引擎同时读写同一封邮件的状态
  - 定时清理任务和正在写入的任务冲突

解决方案: 分级存储策略
  ┌─────────────────────────────────────────────────────────────┐
  │  层级          │  存储方式          │  并发控制              │
  ├─────────────────────────────────────────────────────────────┤
  │  邮件元数据    │  SQLite (推荐)     │  WAL模式，支持并发读写  │
  │  处理记录      │  SQLite            │  WAL模式               │
  │  去重缓存      │  SQLite            │  WAL模式               │
  │  邮件正文      │  独立JSON文件       │  每封邮件独立文件，无冲突│
  │  配置文件      │  JSON + 文件锁      │  filelock 库           │
  │  流程定义      │  YAML (只读)        │  运行时不写入          │
  └─────────────────────────────────────────────────────────────┘
```

**SQLite 存储方案:**
```sql
-- 邮件元数据表
CREATE TABLE mails (
    message_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    sender TEXT,
    sender_domain TEXT,
    recipient TEXT,
    subject TEXT,
    send_time DATETIME,
    receive_time DATETIME,
    category TEXT,
    priority TEXT,
    confidence REAL,
    need_reply INTEGER,
    tags TEXT,  -- JSON数组
    status TEXT DEFAULT 'new',  -- new/processing/processed/archived
    body_file_path TEXT,  -- 正文JSON文件路径
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_mails_account ON mails(account_id);
CREATE INDEX idx_mails_category ON mails(category);
CREATE INDEX idx_mails_send_time ON mails(send_time);
CREATE INDEX idx_mails_status ON mails(status);

-- 处理记录表
CREATE TABLE execution_records (
    id TEXT PRIMARY KEY,
    mail_id TEXT NOT NULL,
    workflow_name TEXT,
    workflow_version TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    status TEXT,  -- success/failed/skipped
    step_results TEXT,  -- JSON
    error_message TEXT,
    FOREIGN KEY (mail_id) REFERENCES mails(message_id)
);

-- 去重缓存表
CREATE TABLE seen_message_ids (
    message_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 分类缓存表
CREATE TABLE classify_cache (
    mail_hash TEXT PRIMARY KEY,  -- 基于主题+发件人+时间的hash
    category TEXT,
    confidence REAL,
    classified_at DATETIME,
    expires_at DATETIME
);
```

**SQLite 连接管理:**
```python
# core/storage/database.py

import sqlite3
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
    
    def _get_connection(self) -> sqlite3.Connection:
        """每个线程独立的连接"""
        if not hasattr(self._local, 'conn'):
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")     # WAL模式，支持并发
            conn.execute("PRAGMA busy_timeout=5000")     # 忙等待5秒
            conn.execute("PRAGMA synchronous=NORMAL")    # 平衡性能与安全
            conn.execute("PRAGMA cache_size=-64000")     # 64MB缓存
            self._local.conn = conn
        return self._local.conn
    
    @contextmanager
    def transaction(self):
        """事务管理"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

#### 4.5.4 去重缓存策略

```
去重机制:
  ┌─────────────────────────────────────────────────────────────┐
  │  层级            │  保留时间    │  说明                      │
  ├─────────────────────────────────────────────────────────────┤
  │  近期缓存        │  30 天       │  覆盖常规邮件周期          │
  │  长期缓存        │  永久        │  仅保留 message_id hash    │
  │  线程关联缓存    │  90 天       │  In-Reply-To/References    │
  └─────────────────────────────────────────────────────────────┘

去重维度:
  1. Message-ID 精确去重 (主要)
  2. 内容指纹去重 (辅助): hash(subject + sender + date)
  3. 线程去重: 基于 In-Reply-To / References

定期清理:
  - 每日凌晨执行清理任务
  - 清理超过保留期限的记录
  - 清理前自动备份
```

#### 4.5.5 数据迁移方案

```
版本升级时的数据迁移:
  ┌─────────────────────────────────────────────────────────────┐
  │  1. 版本号管理                                               │
  │     - data/schema_version.json 记录当前数据结构版本          │
  │     - 格式: {"version": "1.2.0", "migrated_at": "..."}      │
  ├─────────────────────────────────────────────────────────────┤
  │  2. 迁移脚本                                                 │
  │     migrations/                                              │
  │     ├── v1.0.0_to_v1.1.0.py                                 │
  │     ├── v1.1.0_to_v1.2.0.py                                 │
  │     └── ...                                                  │
  ├─────────────────────────────────────────────────────────────┤
  │  3. 迁移流程                                                 │
  │     启动时检查 → 比较版本 → 备份数据 → 执行迁移 → 验证      │
  │     → 成功: 更新版本号                                       │
  │     → 失败: 回滚备份，报告错误，拒绝启动                     │
  ├─────────────────────────────────────────────────────────────┤
  │  4. 迁移脚本接口                                             │
  │     class Migration:                                         │
  │       from_version: str                                      │
  │       to_version: str                                        │
  │       def migrate(data_dir: Path) -> None                    │
  │       def rollback(data_dir: Path) -> None                   │
  │       def validate(data_dir: Path) -> bool                   │
  └─────────────────────────────────────────────────────────────┘
```

**迁移代码示例:**
```python
# migrations/v1.0.0_to_v1.1.0.py

class MigrationV1_0_to_V1_1(Migration):
    from_version = "1.0.0"
    to_version = "1.1.0"
    
    def migrate(self, data_dir: Path):
        """将 JSON 去重缓存迁移到 SQLite"""
        old_cache = data_dir / "cache" / "seen_ids.json"
        if old_cache.exists():
            with open(old_cache) as f:
                ids = json.load(f)
            
            db = Database(data_dir / "data.db")
            with db.transaction():
                for mid in ids:
                    db.execute(
                        "INSERT OR IGNORE INTO seen_message_ids (message_id) VALUES (?)",
                        (mid,)
                    )
            old_cache.rename(old_cache.with_suffix(".json.migrated"))
    
    def rollback(self, data_dir: Path):
        """回滚: SQLite 导出回 JSON"""
        ...
    
    def validate(self, data_dir: Path) -> bool:
        """验证迁移后数据完整性"""
        ...
```

#### 4.5.6 数据清理策略

```
自动清理规则:
  - 邮件缓存 (正文JSON): 保留最近 30 天
  - 附件文件: 保留最近 7 天 (可配置)
  - 处理记录 (SQLite): 保留最近 90 天
  - 日志文件: 保留最近 30 天，单文件最大 10MB
  - 去重缓存 (近期): 保留最近 30 天
  - 去重缓存 (长期): 永久保留 message_id hash
  - 分类缓存: 过期自动清除 (TTL 24小时)

清理执行:
  - 每日凌晨 03:00 自动执行
  - 清理前记录日志
  - 大文件删除使用安全擦除 (可选)
  - 清理结果统计 (释放空间大小)
```

---

## 5. GUI 界面设计

### 5.1 技术方案

采用 **Flet** (Flutter 引擎 Python 绑定) 构建桌面 GUI，基于 Material Design 3 设计规范，具备以下优势：

- 使用 `ft.AppBar`、`ft.NavigationRail`、`ft.ListView` 等原生 Material 组件
- 主题通过 `ft.Theme` + `ft.ColorScheme` 统一管理，支持亮色/暗色模式
- 后台任务使用 `threading.Thread`，UI 更新通过 `page.update()` 触发
- 对话框使用 `ft.AlertDialog`，支持表单验证和异步操作
- 响应式布局：`ft.Row` / `ft.Column` 配合 `expand` 属性自适应窗口大小

### 5.2 主界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  AppBar                                      [🔄] [✏️] [⚙️] │
├────────┬────────────────────────────────────────────────────┤
│        │  📧 收件箱 (3)                                      │
│ 📥 收件箱│  ┌─────────────────────────────────────────────┐ │
│ 📤 已发送│  │ ● [审批] 张三 - Q3预算审批申请    10:30      │ │
│ ⚠️ 告警  │  │   [审批] 系统部 - 服务器维护通知   09:15    │ │
│ 📋 审批  │  │ ● [会议] 李四 - 周一项目评审会     昨天     │ │
│ 📰 资讯  │  │   [营销] xxx公司 - 产品推广        昨天     │ │
│        │  └─────────────────────────────────────────────┘ │
│        │                                                    │
│        │  📖 邮件详情                                        │
│        │  ┌─────────────────────────────────────────────┐ │
│        │  │ 发件人: 张三 <zhangsan@company.com>         │ │
│        │  │ 主题: Q3预算审批申请                         │ │
│        │  │ 时间: 2026-08-03 10:30:00                   │ │
│        │  │                                               │ │
│        │  │ [正文内容...]                                  │ │
│        │  │                                               │ │
│        │  │ 附件: 📎 budget_q3.xlsx (2.3MB)              │ │
│        │  │                                               │ │
│        │  │ [回复] [转发] [标记已读]      [删除]          │ │
│        │  └─────────────────────────────────────────────┘ │
├────────┴────────────────────────────────────────────────────┤
│  🟢 已连接 | 上次拉取: 10:35 | 待处理: 3 | 下次: 10:40     │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 核心组件

| 组件 | Flet 实现 | 功能 |
|------|-----------|------|
| 顶部导航栏 | `ft.AppBar` + `ft.IconButton` | 拉取邮件、写邮件、设置入口 |
| 侧栏导航 | `ft.NavigationRail` | 邮件分类切换（收件箱/已发送/告警/审批/资讯） |
| 邮件列表 | `ft.ListView` + 自定义 `ft.Container` 项 | 展示邮件摘要，支持 ripple 点击效果 |
| 邮件详情 | `ft.Column` + `ft.Markdown` | 展示邮件完整内容，支持 HTML/Markdown 渲染 |
| 账户配置 | `ft.AlertDialog` + `ft.TextField` | 表单式配置，支持后台测试连接 |
| 状态栏 | `ft.Container` + `ft.Row` | 显示连接状态、拉取时间、待处理数 |
| 后台任务 | `threading.Thread` + 回调 | 异步拉取/发送邮件，不阻塞 UI |

### 5.4 核心页面

| 页面 | 功能 |
|------|------|
| 邮件列表 | 按分类展示邮件，支持搜索、筛选、批量操作 |
| 邮件详情 | 查看邮件内容、AI 摘要、分类结果、执行操作 |
| 账户管理 | 添加/编辑/删除邮箱账户，测试连接 |
| 流程管理 | 可视化编辑 YAML 流程定义，启用/禁用流程 |
| 模板管理 | 编辑通知模板，预览效果 |
| 调度配置 | 设置定时拉取规则，Cron 表达式可视化编辑 |
| AI 配置 | 配置 LLM 后端、分类规则、置信度阈值 |
| 通知配置 | 配置企微群 Webhook、通知策略 |
| 运行日志 | 实时日志、历史日志查看 |
| 统计面板 | 邮件数量统计、分类分布、处理效率 |

---

## 6. 扩展设计

### 6.1 规则引擎 (增强版分类)

除了 AI 分类外，增加可配置的规则引擎作为补充:

```yaml
# rules/custom_rules.yaml
rules:
  - name: "CEO邮件优先"
    condition:
      sender: "ceo@company.com"
    action:
      set_type: "审批类"
      set_priority: "urgent"
      override_ai: true        # 覆盖 AI 分类结果

  - name: "监控告警识别"
    condition:
      subject_contains: ["告警", "ALERT", "CRITICAL"]
      sender_domain: "monitor.system"
    action:
      set_type: "告警类"
      set_priority: "urgent"

  - name: "周报自动归类"
    condition:
      subject_regex: "周报|weekly report"
      send_time: "friday 17:00-23:59"
    action:
      set_type: "资讯类"
      auto_tag: ["周报"]
```

**规则优先级:** 自定义规则 > AI 分类 (规则可配置是否覆盖 AI)

### 6.2 邮件线程管理

```
线程聚合:
  - 基于 In-Reply-To / References 邮件头
  - 同一对话的邮件聚合展示
  - 线程级别的状态跟踪 (待处理/已处理/已回复)
```

### 6.3 批量操作与自动化

```
批量操作:
  - 批量标记已读/未读
  - 批量移动/归档
  - 批量删除
  - 批量打标签

自动化规则:
  - "如果...那么..." 形式的自动化规则
  - 例: 如果发件人包含 boss@ → 自动标记为紧急
  - 例: 如果主题是"日报" → 自动移动到"日报"文件夹
```

### 6.4 数据导出与备份

```
导出能力:
  - 邮件导出为 EML / PDF / HTML
  - 处理记录导出为 CSV / Excel
  - 配置一键备份/恢复 (打包为 zip)
  - 定时自动备份 (可配置周期)
```

### 6.5 插件系统 (高级扩展)

```
插件接口:
  plugins/
  ├── custom_action.py       # 自定义 Action
  ├── custom_classifier.py   # 自定义分类器
  └── custom_notifier.py     # 自定义通知渠道

插件能力:
  - 注册新的 Action 类型
  - 注册新的通知渠道 (如钉钉、飞书)
  - 注册新的分类器 (如本地模型)
  - 钩子: 邮件到达前/后、分类前/后、流程执行前/后
```

### 6.6 多账户与权限

```
多账户支持:
  - 添加多个企微邮箱账户
  - 每个账户独立配置调度、流程、通知
  - 统一收件箱 (聚合视图) 或 独立视图切换
  - 账户级别的启停控制
```

### 6.7 智能摘要与回复建议

```
AI 增强能力:
  ├── 邮件智能摘要 (长邮件一键总结)
  ├── 回复建议生成 (基于邮件内容生成回复草稿)
  ├── 关键信息提取 (时间、金额、人名、待办事项)
  ├── 多语言翻译 (收到外文邮件自动翻译)
  └── 情感分析 (判断邮件语气: 紧急/不满/中性)
```

---

## 7. 核心流程总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        完整处理流程                               │
│                                                                  │
│  ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐    ┌──────────┐ │
│  │ 定时  │───→│ 拉取 │───→│ 去重 │───→│ 解析 │───→│ 规则预筛 │ │
│  │ 触发  │    │ 邮件 │    │ 检查 │    │ 邮件 │    │          │ │
│  └──────┘    └──────┘    └──────┘    └──────┘    └────┬─────┘ │
│                                                        │       │
│                                              ┌─────────┤       │
│                                              │ 命中规则 │       │
│                                              └────┬────┘       │
│                                                   │            │
│                                                   ▼            │
│  ┌──────────┐    ┌──────┐    ┌──────┐    ┌──────────────┐    │
│  │ 群通知   │←──│ 执行 │←───│ 匹配 │←───│ AI 智能分类  │    │
│  │          │    │ 流程 │    │ 流程 │    │ (未命中规则) │    │
│  └──────────┘    └──────┘    └──────┘    └──────────────┘    │
│       │                                                       │
│       ▼                                                       │
│  ┌──────────┐                                                 │
│  │ 记录日志 │                                                 │
│  │ 更新状态 │                                                 │
│  └──────────┘                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 配置文件示例

### 8.1 全局配置 (app.json)

```json
{
  "app_name": "邮件助手",
  "version": "1.0.0",
  "language": "zh-CN",
  "theme": "light",
  "data_dir": "./data",
  "log_level": "INFO",
  "auto_start": true,
  "minimize_to_tray": true,
  "start_minimized": false
}
```

### 8.2 调度配置 (schedule.json)

```json
{
  "accounts": {
    "account_1": {
      "enabled": true,
      "interval_minutes": 5,
      "cron": null,
      "work_hours_only": true,
      "work_hours": { "start": "08:30", "end": "18:30" },
      "work_days": [1, 2, 3, 4, 5],
      "retry_on_failure": true,
      "retry_interval_minutes": 1
    }
  }
}
```

### 8.3 AI 配置 (ai.json)

```json
{
  "provider": "deepseek",
  "api_key": "sk-encrypted-xxx",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "temperature": 0.1,
  "max_tokens": 500,
  "confidence_threshold": 0.8,
  "enable_cache": true,
  "cache_ttl_hours": 24,
  "fallback_to_rules": true
}
```

---

## 9. 安全设计

### 9.1 敏感信息分类

| 敏感级别 | 信息类型 | 示例 |
|----------|----------|------|
| **高敏感** | 账户密码 | 邮箱密码、授权码 |
| **高敏感** | API 密钥 | LLM API Key |
| **中敏感** | Webhook 密钥 | 企微群机器人 Webhook URL 中的 key |
| **中敏感** | 访问令牌 | OAuth Token |
| **低敏感** | 配置信息 | 邮箱地址、服务器地址 |

### 9.2 密钥管理架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      密钥管理架构                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  方案 A: 系统级密钥管理 (推荐)                             │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  Windows: DPAPI (Data Protection API)                     │  │
│  │    - 使用 CryptProtectData / CryptUnprotectData          │  │
│  │    - 密钥与当前用户绑定，无需管理主密钥                    │  │
│  │    - 代码示例:                                            │  │
│  │      import win32crypt                                    │  │
│  │      encrypted = win32crypt.CryptProtectData(             │  │
│  │          password.encode('utf-8'), None)                  │  │
│  │                                                           │  │
│  │  macOS: Keychain                                          │  │
│  │    - 使用 keyring 库                                      │  │
│  │    - 系统级安全存储                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  方案 B: 应用级加密 (降级方案)                             │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  加密算法: AES-256-GCM                                    │  │
│  │  密钥派生: PBKDF2 (用户主密码 + 盐)                       │  │
│  │                                                           │  │
│  │  密钥存储:                                                │  │
│  │    - 主密码由用户设置 (首次运行时)                         │  │
│  │    - 不存储主密码，每次启动时输入                          │  │
│  │    - 或: 使用机器特征 (MAC地址+主机名) 派生密钥            │  │
│  │      (安全性较低，但无需用户记忆密码)                      │  │
│  │                                                           │  │
│  │  加密文件: config/secrets.enc                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 密钥存储结构

**secrets.json 结构 (加密后):**
```json
{
  "version": "1.0",
  "encrypted_data": "base64_encoded_encrypted_content",
  "iv": "initialization_vector",
  "salt": "pbkdf2_salt",
  "iterations": 100000
}
```

**解密后的明文结构:**
```json
{
  "accounts": {
    "account_1": {
      "password": "邮箱密码/授权码"
    }
  },
  "api_keys": {
    "deepseek": "sk-xxx",
    "openai": "sk-yyy"
  },
  "webhooks": {
    "approval_group": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    "alert_group": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=yyy"
  }
}
```

### 9.4 配置文件中的敏感信息处理

**原则: 配置文件中不存储明文敏感信息**

```yaml
# workflows/approval_handler.yaml (正确示例)
steps:
  - name: "发送群通知"
    action: "notify"
    config:
      # 使用 ${secrets.xxx} 引用密钥存储
      webhook: "${secrets.webhooks.approval_group}"
      # 而不是直接写明文:
      # webhook: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"  ❌
```

**账户配置示例:**
```json
// config/accounts.json (不含密码)
{
  "accounts": {
    "account_1": {
      "name": "工作邮箱",
      "email": "user@company.com",
      "imap_host": "imap.exmail.qq.com",
      "imap_port": 993,
      "smtp_host": "smtp.exmail.qq.com",
      "smtp_port": 465,
      "use_ssl": true,
      "password_ref": "secrets.accounts.account_1"  // 引用密钥存储
    }
  }
}
```

### 9.5 密钥管理代码示例

```python
# core/security/secret_manager.py

import json
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class SecretManager:
    """敏感信息管理器"""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.secrets_file = config_dir / "secrets.enc"
        self._secrets_cache = None  # 内存缓存，避免频繁解密
    
    def _get_master_key(self) -> bytes:
        """
        获取主密钥
        方案1: 使用系统级密钥管理 (推荐)
        方案2: 使用机器特征派生
        """
        if sys.platform == "win32":
            # Windows: 使用 DPAPI
            return self._get_windows_dpapi_key()
        elif sys.platform == "darwin":
            # macOS: 使用 Keychain
            return self._get_macos_keychain_key()
        else:
            # Linux/其他: 使用机器特征派生
            return self._get_derived_key()
    
    def _get_windows_dpapi_key(self) -> bytes:
        """Windows DPAPI 密钥"""
        import win32crypt
        # 使用固定标识符，DPAPI 会自动绑定到当前用户
        identifier = b"email-helper-secret-key-v1"
        encrypted = win32crypt.CryptProtectData(identifier, None, None, None, None, 0)
        return encrypted[1]  # 返回加密后的数据作为密钥材料
    
    def _get_derived_key(self) -> bytes:
        """基于机器特征派生密钥"""
        import uuid
        # 获取机器特征
        machine_id = str(uuid.getnode())  # MAC地址
        hostname = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', ''))
        
        # 派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"email-helper-fixed-salt",  # 固定盐值
            iterations=100000,
        )
        key_material = f"{machine_id}-{hostname}".encode()
        return base64.urlsafe_b64encode(kdf.derive(key_material))
    
    def get_secret(self, path: str) -> str:
        """
        获取密钥
        path 格式: "accounts.account_1.password" 或 "webhooks.approval_group"
        """
        if self._secrets_cache is None:
            self._load_secrets()
        
        # 解析路径
        keys = path.split('.')
        value = self._secrets_cache
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                raise KeyError(f"Secret not found: {path}")
        
        return value
    
    def set_secret(self, path: str, value: str):
        """设置密钥"""
        if self._secrets_cache is None:
            self._load_secrets()
        
        # 解析路径并设置值
        keys = path.split('.')
        data = self._secrets_cache
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value
        
        # 保存
        self._save_secrets()
    
    def _load_secrets(self):
        """加载并解密密钥文件"""
        if not self.secrets_file.exists():
            self._secrets_cache = {}
            return
        
        # 读取加密文件
        with open(self.secrets_file, 'rb') as f:
            data = json.load(f)
        
        # 解密
        key = self._get_master_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(data['encrypted_data'].encode())
        self._secrets_cache = json.loads(decrypted)
    
    def _save_secrets(self):
        """加密并保存密钥"""
        key = self._get_master_key()
        fernet = Fernet(key)
        
        # 加密
        plaintext = json.dumps(self._secrets_cache).encode()
        encrypted = fernet.encrypt(plaintext)
        
        # 保存
        data = {
            'version': '1.0',
            'encrypted_data': encrypted.decode()
        }
        with open(self.secrets_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # 设置文件权限 (仅当前用户可读写)
        if sys.platform != "win32":
            os.chmod(self.secrets_file, 0o600)
    
    def resolve_template(self, template: str) -> str:
        """
        解析模板中的密钥引用
        示例: "${secrets.webhooks.approval_group}" -> 实际密钥
        """
        import re
        pattern = r'\$\{secrets\.([^}]+)\}'
        
        def replace(match):
            path = match.group(1)
            return self.get_secret(path)
        
        return re.sub(pattern, replace, template)
```

### 9.6 日志脱敏

```python
# core/utils/log_sanitizer.py

import re
from typing import Any

class LogSanitizer:
    """日志脱敏处理器"""
    
    # 敏感模式
    PATTERNS = [
        (r'(password["\s:=]+)[^\s,}]+', r'\1***'),
        (r'(api[_-]?key["\s:=]+)[^\s,}]+', r'\1***'),
        (r'(secret["\s:=]+)[^\s,}]+', r'\1***'),
        (r'(token["\s:=]+)[^\s,}]+', r'\1***'),
        (r'(key=)[a-zA-Z0-9-]+', r'\1***'),  # Webhook key
        (r'(sk-)[a-zA-Z0-9]+', r'\1***'),  # OpenAI style key
    ]
    
    @classmethod
    def sanitize(cls, text: str) -> str:
        """脱敏处理"""
        for pattern, replacement in cls.PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
    
    @classmethod
    def sanitize_dict(cls, data: dict) -> dict:
        """脱敏字典"""
        result = {}
        sensitive_keys = {'password', 'api_key', 'secret', 'token', 'key'}
        
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                result[k] = '***'
            elif isinstance(v, dict):
                result[k] = cls.sanitize_dict(v)
            elif isinstance(v, str):
                result[k] = cls.sanitize(v)
            else:
                result[k] = v
        
        return result

# 配置 logging 过滤器
class SanitizeFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = LogSanitizer.sanitize(record.msg)
        elif isinstance(record.msg, dict):
            record.msg = LogSanitizer.sanitize_dict(record.msg)
        return True
```

### 9.7 安全配置检查

**启动时安全检查:**
```python
# core/security/security_check.py

def run_security_checks():
    """启动时运行安全检查"""
    checks = [
        check_secrets_file_permissions,
        check_no_plaintext_secrets,
        check_ssl_enforcement,
    ]
    
    for check in checks:
        result = check()
        if not result.passed:
            logger.warning(f"安全检查失败: {result.message}")
            if result.severity == "HIGH":
                raise SecurityError(result.message)

def check_no_plaintext_secrets() -> CheckResult:
    """检查配置文件中是否有明文敏感信息"""
    sensitive_patterns = ['password', 'api_key', 'secret', 'token']
    
    for config_file in Path('config').glob('*.json'):
        with open(config_file) as f:
            content = f.read().lower()
            for pattern in sensitive_patterns:
                # 检查是否有明文密码 (排除引用形式 ${secrets.xxx})
                if f'"{pattern}"' in content and '${secrets.' not in content:
                    return CheckResult(False, f"发现明文敏感信息: {config_file}", "HIGH")
    
    return CheckResult(True, "检查通过", "NONE")
```

### 9.8 安全设计总结

| 安全点 | 措施 | 实现状态 |
|--------|------|----------|
| 密码存储 | 系统级加密 (DPAPI/Keychain) 或 AES-256-GCM | 必须 |
| API Key | 加密存储于 secrets.enc，配置文件仅存引用 | 必须 |
| Webhook Key | 同 API Key，统一密钥管理 | 必须 |
| 本地数据 | 仅存储在本地，不上传任何云端 | 必须 |
| 日志脱敏 | 自动过滤密码、密钥、Token 等敏感信息 | 必须 |
| 网络通信 | 强制 SSL/TLS 加密传输 | 必须 |
| 权限控制 | 最小权限原则，密钥文件仅当前用户可访问 | 必须 |
| 启动检查 | 检测明文敏感信息，发出警告或阻止启动 | 推荐 |

---

## 10. 部署与分发

```
打包方案:
  1. PyInstaller 打包为单文件 exe
  2. 包含 Python 运行时，用户无需安装 Python
  3. 首次运行引导: 配置邮箱账户 → 测试连接 → 启动调度
  4. 支持开机自启 (可选)
  5. 系统托盘常驻，最小化后台运行

更新方案:
  - 本地检查更新 (可选)
  - 配置文件与数据目录独立，更新不丢失用户数据
```

---

## 11. 技术风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| 企微 IMAP 限制 (频率/连接数) | 拉取失败 | 合理设置间隔，支持退避重试 |
| AI 分类不准确 | 流程误触发 | 置信度阈值 + 人工确认机制 + 规则覆盖 |
| 本地数据丢失 | 记录缺失 | 自动备份 + 邮件可从服务器重新拉取 |
| 密码泄露 | 安全风险 | 系统级加密 + 日志脱敏 |
| LLM API 不可用 | 分类失败 | 降级为规则引擎分类 + 本地模型备选 |
| 数据库文件损坏 | 数据丢失 | SQLite WAL 模式 + 定期备份 + 自动恢复 |
| 网络中断 | 功能暂停 | 离线缓存 + 自动重连 + 任务队列 |
| 流程执行中断 | 状态不一致 | 事务管理 + 状态持久化 + 断点续传 |

---

## 12. 错误恢复与容错设计

### 12.1 任务状态持久化

```
问题场景:
  - 程序崩溃时，正在执行的流程中断
  - 邮件已拉取但流程未执行完成
  - 通知已发送但记录未保存

解决方案: 任务状态机
  ┌─────────────────────────────────────────────────────────────┐
  │  任务状态流转                                                 │
  │                                                              │
  │  pending → running → completed                              │
  │              ↓                                               │
  │           failed → retry → running                          │
  │              ↓                                               │
  │           aborted (人工干预)                                 │
  └─────────────────────────────────────────────────────────────┘

持久化存储:
  - 任务状态存储在 SQLite 的 tasks 表
  - 每个状态变更立即写入数据库
  - 程序重启时自动恢复未完成的任务
```

**任务表结构:**
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- mail_fetch/workflow_execute/notification_send
    mail_id TEXT,
    workflow_name TEXT,
    status TEXT DEFAULT 'pending',  -- pending/running/completed/failed/aborted
    current_step TEXT,  -- 当前执行的步骤ID
    context_data TEXT,  -- JSON，流程上下文快照
    attempt_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    error_message TEXT,
    next_retry_at DATETIME
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_type ON tasks(type);
```

### 12.2 程序重启恢复

```python
# core/recovery/task_recover.py

class TaskRecovery:
    """任务恢复管理器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def recover_on_startup(self):
        """启动时恢复未完成的任务"""
        # 1. 恢复 running 状态的任务 (程序崩溃)
        running_tasks = self.db.fetchall(
            "SELECT * FROM tasks WHERE status = 'running'"
        )
        for task in running_tasks:
            logger.warning(f"发现未完成的任务: {task['id']}，准备恢复")
            # 将 running 改为 failed，等待重试
            self.db.execute(
                "UPDATE tasks SET status = 'failed', error_message = ? WHERE id = ?",
                ("程序异常退出，任务中断", task['id'])
            )
        
        # 2. 恢复 pending 和 failed 的任务
        pending_tasks = self.db.fetchall(
            """SELECT * FROM tasks 
               WHERE status IN ('pending', 'failed')
                 AND attempt_count < max_retries"""
        )
        for task in pending_tasks:
            logger.info(f"恢复任务: {task['id']}，类型: {task['type']}")
            self._schedule_retry(task)
        
        # 3. 清理超时的任务
        self._cleanup_stale_tasks()
    
    def _schedule_retry(self, task: dict):
        """安排任务重试"""
        # 根据任务类型决定恢复策略
        if task['type'] == 'mail_fetch':
            # 邮件拉取：直接重新拉取
            self._retry_mail_fetch(task)
        elif task['type'] == 'workflow_execute':
            # 流程执行：从断点继续
            self._retry_workflow(task)
        elif task['type'] == 'notification_send':
            # 通知发送：重新发送
            self._retry_notification(task)
    
    def _retry_workflow(self, task: dict):
        """恢复流程执行"""
        # 从 context_data 恢复上下文
        context = json.loads(task['context_data'])
        current_step = task['current_step']
        
        # 从当前步骤的下一步开始执行
        workflow_engine = WorkflowEngine()
        workflow_engine.resume_from_step(
            workflow_name=task['workflow_name'],
            mail_id=task['mail_id'],
            context=context,
            from_step=current_step
        )
    
    def _cleanup_stale_tasks(self):
        """清理超时任务"""
        # 清理超过 7 天仍在 pending 的任务
        cutoff = time.time() - 7 * 86400
        self.db.execute(
            """UPDATE tasks SET status = 'aborted', error_message = ?
               WHERE status = 'pending' AND created_at < ?""",
            ("任务超时，自动取消", cutoff)
        )
```

### 12.3 断点续传

```yaml
# 流程执行断点续传示例

steps:
  - id: "step1"
    action: "extract_info"
    # ... 执行完成，状态写入 context

  - id: "step2"
    action: "notify"
    # ... 执行失败，程序崩溃

# 恢复时:
# 1. 从 context_data 加载已完成的步骤结果
# 2. 从 step2 重新开始执行
# 3. step1 的结果已在 context 中，无需重新执行
```

**断点续传关键设计:**
- 每个步骤执行完成后，立即将输出写入 context
- context 定期持久化到数据库 (每步完成后)
- 恢复时从最后一个成功的步骤之后开始
- 幂等性设计：步骤可重复执行而不产生副作用

### 12.4 数据一致性保障

```
事务管理:
  ┌─────────────────────────────────────────────────────────────┐
  │  1. 邮件拉取事务                                             │
  │     BEGIN                                                    │
  │     - 插入邮件元数据到 mails 表                              │
  │     - 插入 Message-ID 到 seen_message_ids                  │
  │     - 保存邮件正文到文件                                     │
  │     - 创建任务记录                                           │
  │     COMMIT                                                   │
  ├─────────────────────────────────────────────────────────────┤
  │  2. 流程执行事务                                             │
  │     BEGIN                                                    │
  │     - 更新任务状态为 running                                 │
  │     - 执行各步骤                                             │
  │     - 更新邮件状态为 processed                               │
  │     - 保存执行记录                                           │
  │     - 更新任务状态为 completed                               │
  │     COMMIT                                                   │
  │                                                              │
  │     失败时:                                                  │
  │     ROLLBACK                                                 │
  │     - 任务状态改为 failed                                    │
  │     - 邮件状态保持 new                                       │
  │     - 记录错误信息                                           │
  └─────────────────────────────────────────────────────────────┘
```

---

## 13. 健康检查与监控

### 13.1 健康检查项

```
检查项目:
  ┌─────────────────────────────────────────────────────────────┐
  │  1. IMAP 连接健康                                            │
  │     - 检查项: 连接状态、响应时间、最近成功时间               │
  │     - 告警条件: 连续 3 次连接失败                            │
  │     - 恢复动作: 自动重连，失败后切换轮询模式                 │
  ├─────────────────────────────────────────────────────────────┤
  │  2. SMTP 连接健康                                            │
  │     - 检查项: 连接状态、认证状态                             │
  │     - 告警条件: 连接失败或认证失败                           │
  │     - 恢复动作: 尝试重连，失败后通知用户                     │
  ├─────────────────────────────────────────────────────────────┤
  │  3. LLM API 健康                                             │
  │     - 检查项: API 可用性、响应时间、错误率                   │
  │     - 检查方式: 每分钟发送一次简单测试请求                   │
  │     - 告警条件: 连续 5 次请求失败或响应时间 > 10s            │
  │     - 恢复动作: 降级为规则引擎分类                           │
  ├─────────────────────────────────────────────────────────────┤
  │  4. 数据库健康                                               │
  │     - 检查项: 文件大小、查询响应时间、WAL 文件大小           │
  │     - 告警条件: 文件 > 1GB 或查询时间 > 1s                   │
  │     - 恢复动作: 执行 VACUUM 优化                             │
  ├─────────────────────────────────────────────────────────────┤
  │  5. 磁盘空间健康                                             │
  │     - 检查项: 数据目录剩余空间                               │
  │     - 告警条件: 剩余空间 < 500MB                             │
  │     - 恢复动作: 触发数据清理，通知用户                       │
  ├─────────────────────────────────────────────────────────────┤
  │  6. 内存使用健康                                             │
  │     - 检查项: 进程内存占用                                   │
  │     - 告警条件: 内存 > 500MB                                 │
  │     - 恢复动作: 清理缓存，记录警告                           │
  └─────────────────────────────────────────────────────────────┘
```

### 13.2 健康检查实现

```python
# core/monitoring/health_checker.py

import time
import psutil
import threading
from dataclasses import dataclass
from enum import Enum

class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class HealthCheckResult:
    name: str
    status: HealthStatus
    message: str
    details: dict
    checked_at: float

class HealthChecker:
    """健康检查管理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.checks = []
        self.results = {}
        self.lock = threading.Lock()
        
        # 注册检查项
        self._register_checks()
    
    def _register_checks(self):
        """注册所有健康检查"""
        self.checks = [
            self._check_imap_connection,
            self._check_smtp_connection,
            self._check_llm_api,
            self._check_database,
            self._check_disk_space,
            self._check_memory_usage,
        ]
    
    def run_all_checks(self) -> list:
        """运行所有健康检查"""
        results = []
        for check in self.checks:
            try:
                result = check()
                results.append(result)
                with self.lock:
                    self.results[result.name] = result
            except Exception as e:
                results.append(HealthCheckResult(
                    name=check.__name__,
                    status=HealthStatus.ERROR,
                    message=f"检查异常: {e}",
                    details={},
                    checked_at=time.time()
                ))
        
        return results
    
    def _check_imap_connection(self) -> HealthCheckResult:
        """检查 IMAP 连接"""
        # 实际实现中检查各账户的 IMAP 连接状态
        # 这里简化示例
        return HealthCheckResult(
            name="imap_connection",
            status=HealthStatus.HEALTHY,
            message="IMAP 连接正常",
            details={"accounts": 2, "last_check": time.time()},
            checked_at=time.time()
        )
    
    def _check_llm_api(self) -> HealthCheckResult:
        """检查 LLM API"""
        # 发送测试请求，检查响应时间和错误率
        return HealthCheckResult(
            name="llm_api",
            status=HealthStatus.HEALTHY,
            message="LLM API 正常",
            details={"response_time_ms": 150, "error_rate": 0.01},
            checked_at=time.time()
        )
    
    def _check_disk_space(self) -> HealthCheckResult:
        """检查磁盘空间"""
        data_dir = self.config.get('data_dir', './data')
        usage = psutil.disk_usage(data_dir)
        
        free_gb = usage.free / (1024**3)
        if free_gb < 0.5:  # < 500MB
            status = HealthStatus.ERROR
            message = f"磁盘空间不足: {free_gb:.2f}GB"
        elif free_gb < 2:  # < 2GB
            status = HealthStatus.WARNING
            message = f"磁盘空间偏低: {free_gb:.2f}GB"
        else:
            status = HealthStatus.HEALTHY
            message = f"磁盘空间充足: {free_gb:.2f}GB"
        
        return HealthCheckResult(
            name="disk_space",
            status=status,
            message=message,
            details={"free_gb": free_gb, "percent_used": usage.percent},
            checked_at=time.time()
        )
    
    def _check_memory_usage(self) -> HealthCheckResult:
        """检查内存使用"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024**2)
        
        if memory_mb > 500:
            status = HealthStatus.WARNING
            message = f"内存使用偏高: {memory_mb:.0f}MB"
        else:
            status = HealthStatus.HEALTHY
            message = f"内存使用正常: {memory_mb:.0f}MB"
        
        return HealthCheckResult(
            name="memory_usage",
            status=status,
            message=message,
            details={"memory_mb": memory_mb},
            checked_at=time.time()
        )
    
    def get_health_summary(self) -> dict:
        """获取健康摘要"""
        with self.lock:
            return {
                "overall_status": self._calculate_overall_status(),
                "checks": {
                    name: {
                        "status": result.status.value,
                        "message": result.message,
                        "checked_at": result.checked_at
                    }
                    for name, result in self.results.items()
                },
                "last_check": max(r.checked_at for r in self.results.values()) if self.results else None
            }
    
    def _calculate_overall_status(self) -> str:
        """计算整体状态"""
        if not self.results:
            return "unknown"
        
        statuses = [r.status for r in self.results.values()]
        if HealthStatus.ERROR in statuses:
            return "error"
        elif HealthStatus.WARNING in statuses:
            return "warning"
        else:
            return "healthy"
```

### 13.3 健康检查调度

```python
# 定期执行健康检查
class HealthCheckScheduler:
    def __init__(self, health_checker: HealthChecker, interval_seconds: int = 60):
        self.health_checker = health_checker
        self.interval = interval_seconds
        self.running = False
    
    def start(self):
        """启动健康检查调度"""
        self.running = True
        self._run_loop()
    
    def stop(self):
        """停止健康检查"""
        self.running = False
    
    def _run_loop(self):
        """检查循环"""
        while self.running:
            results = self.health_checker.run_all_checks()
            
            # 检查是否有异常
            for result in results:
                if result.status == HealthStatus.ERROR:
                    logger.error(f"健康检查异常: {result.name} - {result.message}")
                    # 发送告警通知
                    self._send_alert(result)
                elif result.status == HealthStatus.WARNING:
                    logger.warning(f"健康检查警告: {result.name} - {result.message}")
            
            time.sleep(self.interval)
    
    def _send_alert(self, result: HealthCheckResult):
        """发送告警"""
        # 通过通知引擎发送告警
        notification = {
            "title": "系统健康告警",
            "content": f"{result.name}: {result.message}",
            "level": "error"
        }
        # 调用通知引擎发送
```

### 13.4 GUI 健康状态展示

```
主界面状态栏增强:
  ┌─────────────────────────────────────────────────────────────┐
  │  ● 运行中 | 🟢 IMAP | 🟢 LLM | 💾 2.3GB | 上次检查: 10:35 │
  └─────────────────────────────────────────────────────────────┘
  
  状态指示:
    🟢 绿色: 正常
    🟡 黄色: 警告
    🔴 红色: 异常
    ⚪ 灰色: 未检查/未知

健康检查页面:
  ┌─────────────────────────────────────────────────────────────┐
  │  系统健康状态                                                 │
  ├─────────────────────────────────────────────────────────────┤
  │  🟢 IMAP 连接        正常        最近检查: 10:35:00         │
  │  🟢 SMTP 连接        正常        最近检查: 10:35:00         │
  │  🟢 LLM API          正常        响应时间: 150ms            │
  │  🟢 数据库           正常        大小: 45MB                 │
  │  🟡 磁盘空间         警告        剩余: 1.8GB                │
  │  🟢 内存使用         正常        占用: 120MB                │
  ├─────────────────────────────────────────────────────────────┤
  │  [立即检查]  [查看详情]  [导出报告]                          │
  └─────────────────────────────────────────────────────────────┘
```

---

## 14. 日志分级与管理

### 14.1 日志分级

```
日志级别定义:
  ┌─────────────────────────────────────────────────────────────┐
  │  级别        │  用途                    │  输出目标          │
  ├─────────────────────────────────────────────────────────────┤
  │  DEBUG       │  调试信息，开发时使用    │  文件              │
  │  INFO        │  正常运行信息            │  文件 + GUI        │
  │  WARNING     │  警告信息，需要关注      │  文件 + GUI + 通知 │
  │  ERROR       │  错误信息，需要处理      │  文件 + GUI + 通知 │
  │  CRITICAL    │  严重错误，程序可能崩溃  │  文件 + GUI + 通知 │
  └─────────────────────────────────────────────────────────────┘

日志分类:
  - app.log: 应用主日志，所有模块的关键信息
  - mail.log: 邮件相关日志，收发、解析、存储
  - workflow.log: 流程执行日志，步骤执行详情
  - ai.log: AI 分类日志，Prompt、响应、分类结果
  - notification.log: 通知日志，发送、重试、失败
  - security.log: 安全日志，登录、密钥操作、异常访问
```

### 14.2 日志配置

```python
# core/utils/logger.py

import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

def setup_logging(config: dict):
    """配置日志系统"""
    log_dir = Path(config.get('log_dir', './logs'))
    log_dir.mkdir(exist_ok=True)
    
    log_level = config.get('log_level', 'INFO')
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 脱敏过滤器
    sanitize_filter = SanitizeFilter()
    
    # 主应用日志 (按大小轮转)
    app_handler = RotatingFileHandler(
        log_dir / 'app.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    app_handler.setFormatter(formatter)
    app_handler.addFilter(sanitize_filter)
    
    # 邮件日志 (按时间轮转，每天一个文件)
    mail_handler = TimedRotatingFileHandler(
        log_dir / 'mail.log',
        when='midnight',
        backupCount=30,  # 保留 30 天
        encoding='utf-8'
    )
    mail_handler.setFormatter(formatter)
    mail_handler.addFilter(sanitize_filter)
    
    # 配置各模块的 logger
    loggers = {
        'app': {'handlers': [app_handler], 'level': log_level},
        'mail': {'handlers': [mail_handler], 'level': log_level},
        'workflow': {'handlers': [mail_handler], 'level': log_level},
        'ai': {'handlers': [mail_handler], 'level': log_level},
        'notification': {'handlers': [mail_handler], 'level': log_level},
        'security': {'handlers': [app_handler], 'level': 'INFO'},
    }
    
    for name, cfg in loggers.items():
        logger = logging.getLogger(name)
        logger.setLevel(cfg['level'])
        for handler in cfg['handlers']:
            logger.addHandler(handler)
    
    # 控制台输出 (仅 DEBUG 模式)
    if log_level == 'DEBUG':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(sanitize_filter)
        logging.getLogger().addHandler(console_handler)
```

### 14.3 日志查看与搜索

```
GUI 日志查看器:
  ┌─────────────────────────────────────────────────────────────┐
  │  日志查看器                                    [级别: INFO ▼]│
  ├─────────────────────────────────────────────────────────────┤
  │  [搜索...] [筛选] [清空] [导出] [打开文件]                   │
  ├─────────────────────────────────────────────────────────────┤
  │  时间         │ 级别  │ 模块     │ 内容                     │
  │  ─────────────────────────────────────────────────────────  │
  │  10:35:00     │ INFO  │ mail     │ 拉取邮件: 5封新邮件      │
  │  10:35:01     │ INFO  │ ai       │ 分类: 审批类 (0.95)      │
  │  10:35:02     │ INFO  │ workflow │ 执行流程: approval_handler│
  │  10:35:03     │ INFO  │ notify   │ 发送通知: 成功           │
  │  10:35:04     │ WARN  │ disk     │ 磁盘空间偏低: 1.8GB      │
  └─────────────────────────────────────────────────────────────┘

日志搜索功能:
  - 关键词搜索
  - 时间范围筛选
  - 级别筛选
  - 模块筛选
  - 正则表达式搜索
  - 上下文查看 (前后 N 行)
```

---

## 15. 分阶段交付计划

### 15.1 阶段划分

```
┌─────────────────────────────────────────────────────────────────┐
│  阶段          │  目标                          │  核心功能      │
├─────────────────────────────────────────────────────────────────┤
│  MVP (0.1)     │  基础收发 + 定时拉取           │  2周           │
│  Alpha (0.5)   │  AI分类 + 基础流程             │  4周           │
│  Beta (0.9)    │  完整流程 + 多账户             │  4周           │
│  RC (1.0)      │  稳定版 + 完善GUI              │  2周           │
│  Release       │  正式发布                      │  -             │
└─────────────────────────────────────────────────────────────────┘
```

### 15.2 MVP (v0.1) - 最小可行产品

**目标:** 实现基础的邮件收发和定时拉取功能

**功能清单:**
- [ ] 单账户配置 (企微邮箱)
- [ ] IMAP 连接与邮件拉取 (定时轮询模式)
- [ ] SMTP 邮件发送
- [ ] 基础 GUI (邮件列表、邮件详情)
- [ ] 本地邮件存储 (JSON 文件)
- [ ] 简单日志记录

**不包含:**
- AI 分类
- 流程引擎
- 通知功能
- 多账户支持

### 15.3 Alpha (v0.5) - AI 分类与基础流程

**目标:** 实现 AI 智能分类和简单的流程执行

**新增功能:**
- [ ] AI 分类引擎 (LLM API 调用)
- [ ] 规则预筛
- [ ] 基础流程引擎 (线性执行，无分支)
- [ ] 企微群通知
- [ ] 置信度显示与人工确认
- [ ] 线程模型 (GUI 不阻塞)

**改进:**
- [ ] SQLite 存储替代 JSON
- [ ] 日志分级与轮转
- [ ] 基础健康检查

### 15.4 Beta (v0.9) - 完整功能

**目标:** 实现所有核心功能，支持多账户

**新增功能:**
- [ ] 多账户支持
- [ ] IMAP IDLE 实时推送
- [ ] 完整流程引擎 (条件分支、循环)
- [ ] 流程版本管理
- [ ] 通知频率限制与重试
- [ ] 密钥管理 (DPAPI/AES)
- [ ] 数据迁移框架
- [ ] 完整健康检查
- [ ] 错误恢复与断点续传

**改进:**
- [ ] GUI 完善 (所有配置页面)
- [ ] 性能优化
- [ ] 测试覆盖

### 15.5 RC (v1.0) - 发布候选版

**目标:** 稳定化，准备正式发布

**工作内容:**
- [ ] Bug 修复
- [ ] 性能调优
- [ ] 文档完善 (用户手册、配置说明)
- [ ] 打包发布 (PyInstaller)
- [ ] 自动更新机制
- [ ] 用户反馈收集

### 15.6 后续版本规划

```
v1.1 - v1.x:
  - 插件系统
  - 邮件线程管理
  - 智能摘要与回复建议
  - 数据导出与备份
  - 更多通知渠道 (钉钉、飞书)

v2.0:
  - 本地 LLM 支持 (Ollama)
  - 离线模式
  - 移动端适配 (可选)
```

### 15.7 交付检查清单

**MVP 检查清单:**
- [ ] 能够连接企微邮箱
- [ ] 能够拉取邮件并显示
- [ ] 能够发送邮件
- [ ] 定时拉取正常工作
- [ ] GUI 响应流畅
- [ ] 日志正常记录

**Alpha 检查清单:**
- [ ] AI 分类准确率 > 70%
- [ ] 流程能够正确执行
- [ ] 通知能够正常发送
- [ ] GUI 不阻塞
- [ ] 错误能够正确处理

**Beta 检查清单:**
- [ ] 多账户独立运行
- [ ] IDLE 模式稳定
- [ ] 流程分支正确
- [ ] 密钥安全存储
- [ ] 错误能够恢复
- [ ] 健康检查正常

**RC 检查清单:**
- [ ] 无严重 Bug
- [ ] 性能达标
- [ ] 文档完整
- [ ] 打包成功
- [ ] 用户测试通过
