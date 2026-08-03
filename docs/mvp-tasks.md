# MVP (v0.1) 开发任务清单

> 目标：实现基础的邮件收发和定时拉取功能
> 技术栈：Python 3.10+ / PyQt6 / APScheduler / IMAP+SMTP SSL
> 存储方案：JSON 文件（MVP 阶段）

---

## 项目目录结构

```
email-helper/
├── main.py                    # 程序入口
├── requirements.txt           # 依赖清单
│
├── config/                    # 配置目录
│   ├── app.json              # 全局配置（首次运行自动生成）
│   └── account.json          # 账户配置
│
├── data/                      # 数据目录
│   ├── mails/                # 邮件缓存（按日期子目录）
│   ├── attachments/          # 附件存储
│   └── cache/                # 缓存（seen_ids 等）
│
├── logs/                      # 日志目录
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── config.py         # 配置管理
│   │   ├── logger.py         # 日志初始化
│   │   └── models.py         # 数据模型（MailData 等）
│   │
│   ├── mail/                  # 邮件引擎
│   │   ├── __init__.py
│   │   ├── imap_client.py    # IMAP 连接与邮件拉取
│   │   ├── smtp_client.py    # SMTP 邮件发送
│   │   ├── parser.py         # 邮件解析（头、正文、附件）
│   │   └── scheduler.py      # 定时拉取调度
│   │
│   ├── storage/               # 存储层
│   │   ├── __init__.py
│   │   └── mail_store.py     # 邮件 JSON 文件存储
│   │
│   └── gui/                   # GUI 层
│       ├── __init__.py
│       ├── main_window.py    # 主窗口
│       ├── mail_list.py      # 邮件列表面板
│       ├── mail_detail.py    # 邮件详情面板
│       ├── account_dialog.py # 账户配置对话框
│       └── worker.py         # 后台工作线程
│
└── tests/                     # 测试目录
    ├── test_imap_client.py
    ├── test_smtp_client.py
    ├── test_parser.py
    └── test_mail_store.py
```

## 模块依赖关系

```
main.py
  └── gui/main_window.py
        ├── core/config.py          (配置加载)
        ├── core/logger.py          (日志初始化)
        ├── mail/scheduler.py       (定时调度)
        │     ├── mail/imap_client.py   (IMAP 拉取)
        │     │     └── mail/parser.py  (邮件解析)
        │     └── storage/mail_store.py (存储)
        ├── mail/smtp_client.py     (邮件发送)
        ├── gui/mail_list.py        (邮件列表 UI)
        ├── gui/mail_detail.py      (邮件详情 UI)
        ├── gui/account_dialog.py   (账户设置 UI)
        └── gui/worker.py           (后台线程)
```

---

## 开发任务

### 任务 1：项目脚手架搭建

**目标：** 建立项目目录结构、依赖管理、基础配置

**具体工作：**
1. 创建上述目录结构和所有 `__init__.py`
2. 编写 `requirements.txt`：
   ```
   PyQt6>=6.6.0
   APScheduler>=3.10.0
   ```
3. 实现 `src/core/config.py`：
   - `AppConfig` 类，加载/保存 `config/app.json`
   - 首次运行自动生成默认配置
   - 配置项：`data_dir`, `log_level`, `log_dir`, `auto_start`
4. 实现 `src/core/logger.py`：
   - 基于 `logging` 模块，输出到 `logs/app.log`
   - `RotatingFileHandler`（10MB 轮转，保留 5 个）
   - 同时输出到控制台（DEBUG 级别时）
   - 格式：`%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s`

**验收标准：**
- [ ] `python main.py` 能正常启动不报错
- [ ] `config/app.json` 首次运行自动生成
- [ ] `logs/app.log` 有日志输出
- [ ] 配置可读写

---

### 任务 2：数据模型定义

**目标：** 定义邮件数据结构，供所有模块共享

**具体工作：**
实现 `src/core/models.py`：

```python
@dataclass
class Attachment:
    filename: str
    size: int
    mime_type: str
    content_id: str | None  # 内联附件

@dataclass
class MailData:
    message_id: str
    sender: str
    sender_domain: str
    recipient: str
    subject: str
    send_time: datetime
    receive_time: datetime
    body_text: str          # 纯文本正文
    body_html: str | None   # HTML 正文（可选）
    attachments: list[Attachment]
    is_read: bool = False
    is_sent: bool = False
    local_file_path: str | None = None  # 本地 JSON 路径
```

**验收标准：**
- [ ] 数据模型可正常实例化
- [ ] 支持序列化为 dict/JSON

---

### 任务 3：邮件解析器

**目标：** 解析 IMAP 原始邮件为 `MailData` 对象

**具体工作：**
实现 `src/mail/parser.py`：

1. `parse_email(raw_bytes: bytes) -> MailData`
2. 邮件头解码（RFC 2047）：
   - 使用 `email.header.decode_header`
   - 字符集回退：UTF-8 -> GBK -> GB2312 -> Latin1
3. 正文提取：
   - 优先 `text/plain`，备选 `text/html`
   - 递归解析 `multipart`
4. 附件提取：
   - 识别 `Content-Disposition: attachment`
   - 解码 `base64` / `quoted-printable`
   - 返回 `Attachment` 列表
5. 编码容错：解码失败时使用 `errors='replace'`

**验收标准：**
- [ ] 能正确解析 UTF-8 编码邮件
- [ ] 能正确解析 GBK/GB2312 编码邮件
- [ ] 能提取附件并保存
- [ ] 异常邮件不会崩溃（容错处理）
- [ ] 单元测试覆盖（准备 2-3 个测试邮件样本）

---

### 任务 4：IMAP 客户端

**目标：** 连接企微邮箱，拉取未读邮件

**具体工作：**
实现 `src/mail/imap_client.py`：

1. `ImapClient` 类：
   - `__init__(host, port, username, password, use_ssl=True)`
   - `connect()` — 建立 IMAP SSL 连接
   - `disconnect()` — 关闭连接
   - `fetch_unseen(seen_ids: set) -> list[MailData]` — 拉取未见邮件
   - `mark_as_read(message_id: str)` — 标记已读
2. 连接参数（企微默认）：
   - `imap.exmail.qq.com:993` (SSL)
3. 拉取逻辑：
   - `SELECT INBOX`
   - `SEARCH UNSEEN` 获取未读邮件 UID
   - 过滤已在 `seen_ids` 中的邮件
   - `FETCH` 获取完整邮件内容
   - 调用 `parser.parse_email()` 解析
4. 异常处理：
   - 连接超时（30s）
   - 认证失败 -> 抛出明确异常
   - 网络中断 -> 捕获并记录日志

**验收标准：**
- [ ] 能成功连接企微邮箱
- [ ] 能拉取未读邮件并解析为 `MailData`
- [ ] 已拉取的邮件 ID 记录到 `seen_ids`
- [ ] 重复运行不会重复拉取
- [ ] 连接失败时有明确错误信息

---

### 任务 5：邮件存储

**目标：** 将邮件以 JSON 文件形式存储到本地

**具体工作：**
实现 `src/storage/mail_store.py`：

1. `MailStore` 类：
   - `__init__(base_dir: str)` — 基础目录 `data/mails/`
   - `save(mail: MailData)` — 保存邮件为 JSON
   - `load(message_id: str) -> MailData | None` — 加载邮件
   - `list_mails(date: str | None = None) -> list[MailData]` — 列出邮件
   - `get_seen_ids() -> set[str]` — 获取已处理邮件 ID 集合
   - `save_seen_ids(seen_ids: set)` — 保存已处理 ID
2. 存储规则：
   - 目录结构：`data/mails/2026-08-03/mail_{message_id_hash}.json`
   - `seen_ids` 存储在 `data/cache/seen_ids.json`
   - `message_id_hash` 使用 MD5 前 8 位（避免文件名过长）
3. 附件存储：
   - 附件内容不存入 JSON，单独保存到 `data/attachments/`
   - JSON 中仅记录附件元信息（文件名、大小、路径）

**验收标准：**
- [ ] 邮件保存为可读的 JSON 文件
- [ ] 能按日期列出所有邮件
- [ ] `seen_ids` 持久化，重启后不重复拉取
- [ ] 附件文件正确保存

---

### 任务 6：SMTP 客户端

**目标：** 发送邮件（纯文本 + HTML + 附件）

**具体工作：**
实现 `src/mail/smtp_client.py`：

1. `SmtpClient` 类：
   - `__init__(host, port, username, password, use_ssl=True)`
   - `connect()` — 建立 SMTP SSL 连接
   - `disconnect()` — 关闭连接
   - `send_mail(to, subject, body, html=None, attachments=None, cc=None) -> bool`
2. 连接参数（企微默认）：
   - `smtp.exmail.qq.com:465` (SSL)
3. 邮件构建：
   - 使用 `email.mime` 构建 MIME 邮件
   - 支持纯文本 + HTML 双版本
   - 支持多附件
4. 发送失败重试：
   - 最多重试 2 次，间隔 3 秒

**验收标准：**
- [ ] 能发送纯文本邮件
- [ ] 能发送带附件的邮件
- [ ] 发送失败有重试
- [ ] 发送记录写入日志

---

### 任务 7：定时调度器

**目标：** 定时触发邮件拉取任务

**具体工作：**
实现 `src/mail/scheduler.py`：

1. `MailScheduler` 类：
   - `__init__(imap_client, mail_store, config)`
   - `start()` — 启动调度
   - `stop()` — 停止调度
   - `fetch_now()` — 手动触发一次拉取
2. 使用 APScheduler 的 `BackgroundScheduler`：
   - 默认每 5 分钟拉取一次（可配置）
   - 在后台线程执行，不阻塞 GUI
3. 拉取流程：
   - `imap_client.fetch_unseen(seen_ids)`
   - 对每封新邮件：`mail_store.save(mail)`
   - 更新 `seen_ids`
   - 通过 Qt Signal 通知 GUI 更新

**验收标准：**
- [ ] 定时拉取正常工作
- [ ] 手动触发拉取正常
- [ ] 拉取完成后 GUI 收到通知
- [ ] 可停止/重启调度

---

### 任务 8：后台工作线程

**目标：** 将耗时操作从 GUI 主线程分离

**具体工作：**
实现 `src/gui/worker.py`：

1. `MailFetchWorker(QThread)`：
   - 执行邮件拉取任务
   - 信号：`finished(list[MailData])`, `error(str)`
2. `MailSendWorker(QThread)`：
   - 执行邮件发送任务
   - 信号：`finished(bool)`, `error(str)`
3. 所有 IMAP/SMTP 操作都在 Worker 中执行
4. GUI 通过信号槽接收结果，更新界面

**验收标准：**
- [ ] 拉取邮件时 GUI 不卡顿
- [ ] 发送邮件时 GUI 不卡顿
- [ ] 错误信息能正确传递到 GUI

---

### 任务 9：GUI 主窗口

**目标：** 搭建简洁、美观、清新风格的主界面框架

---

#### 9.1 整体风格定义

**设计关键词：** 简洁、清新、呼吸感、克制

**风格参考：** 类似 Notion / Fluent Design / macOS Mail 的视觉感受 — 大量留白、淡色背景、柔和阴影、圆润边角，避免密集信息和重色块。

**配色方案（浅色主题）：**

```
背景色:
  主背景        #F7F8FA    (极浅灰蓝，非纯白，减少刺眼感)
  侧栏背景      #FFFFFF    (纯白，与主背景形成微妙层次)
  卡片/面板背景  #FFFFFF
  选中行背景     #EEF4FF    (淡蓝，表示选中态)
  悬停行背景     #F2F5FA    (极淡灰，悬停反馈)

主色调:
  主色          #4A90D9    (清爽蓝，用于按钮、链接、选中高亮)
  主色悬停      #3A7BC8    (略深，hover 状态)
  主色按下      #2E6AB5    (更深，pressed 状态)

文字色:
  主文字        #1D2129    (近黑，非纯黑，柔和)
  次要文字      #86909C    (中灰，用于时间、描述等辅助信息)
  占位文字      #C9CDD4    (浅灰，placeholder)

分割线/边框:
  分割线        #E5E6EB    (极淡灰，1px)
  边框          #E5E6EB

语义色:
  成功/在线     #00B42A    (绿色，连接正常)
  警告          #FF7D00    (橙色)
  错误/断开     #F53F3F    (红色，连接失败)
  未读标记      #4A90D9    (蓝色小圆点)
```

**字体规范：**

```
字体族:
  中文: "Microsoft YaHei UI", "PingFang SC", sans-serif
  英文: "Segoe UI", "SF Pro Text", sans-serif
  等宽: "JetBrains Mono", "Cascadia Code", "Consolas" (仅日志/代码)

字号层级:
  窗口标题       16px  Bold    #1D2129
  面板标题       14px  Medium  #1D2129
  正文/邮件主题   13px  Regular #1D2129
  辅助文字       12px  Regular #86909C  (时间、发件人等)
  状态栏文字     12px  Regular #86909C
  按钮文字       13px  Medium

行高: 1.5 倍字号
字间距: 默认 (不额外加宽)
```

**圆角与间距：**

```
圆角:
  按钮          6px
  输入框        6px
  卡片/面板     8px
  列表项        4px
  对话框        12px

间距系统 (4px 基准):
  组件内间距     8px / 12px
  组件间距       16px
  面板间距       20px
  面板内边距     16px ~ 20px
  窗口最小边距   12px
```

**阴影（极轻量，仅关键元素）：**

```
侧栏: 无阴影 (靠分割线区分)
工具栏按钮: 无阴影 (扁平风格)
弹窗/对话框: 0 4px 12px rgba(0,0,0,0.08)  (轻浮起)
下拉菜单: 0 2px 8px rgba(0,0,0,0.06)
```

---

#### 9.2 主窗口布局

```
┌──────────────────────────────────────────────────────────────┐
│  [邮件助手]                              [_]  [□]  [×]       │  ← 标题栏 (36px高)
├──────────┬───────────────────────────────────────────────────┤
│          │  工具栏 (48px高)                                   │
│  侧栏    │  [🔄 拉取邮件]  [✉️ 写邮件]  [⚙️ 设置]            │
│ (200px)  │────────────────────────────────────────────────── │
│          │  邮件列表 (左)      │  邮件详情 (右)               │
│  📥 收件箱│  ┌──────────────┐  │  ┌──────────────────────┐   │
│  📤 已发送│  │ 邮件条目 1   │  │  │ 发件人 / 主题 / 时间  │   │
│  ⚠️ 告警  │  │ 邮件条目 2   │  │  │                      │   │
│  📋 审批  │  │ 邮件条目 3   │  │  │ 正文内容区域          │   │
│  📰 资讯  │  │ ...          │  │  │                      │   │
│          │  └──────────────┘  │  │                      │   │
│──────────│                    │  │                      │   │
│  📊 统计  │  可拖拽分割条 →    │  │                      │   │
│  📝 模板  │  (2px, #E5E6EB)   │  └──────────────────────┘   │
│          │                    │  附件栏: 📎 file.xlsx 2.3MB  │
├──────────┴────────────────────┴─────────────────────────────┤
│  状态栏 (28px高)                                             │
│  🟢 已连接 | 上次拉取: 10:35 | 待处理: 3 | 下次: 10:40      │
└──────────────────────────────────────────────────────────────┘
```

**窗口尺寸：**
- 默认尺寸: 1100 x 720 px
- 最小尺寸: 800 x 540 px
- 侧栏宽度: 200px (固定，不可拖拽调整)
- 邮件列表/详情分割条: 可拖拽，默认 30%:70%

---

#### 9.3 标题栏

```
高度: 36px
背景: #F7F8FA (与主背景一致)
左侧: 应用图标 (16x16) + "邮件助手" 文字 (14px Medium #1D2129)
右侧: 最小化 / 最大化 / 关闭 按钮 (系统原生风格)
底边: 1px 分割线 #E5E6EB
```

---

#### 9.4 侧栏

```
宽度: 200px
背景: #FFFFFF
右边: 1px 分割线 #E5E6EB
内边距: 上 12px, 左右 12px

分类项:
  高度: 36px
  圆角: 6px
  图标: 16x16, 与文字间距 8px
  文字: 13px Regular
  未选中: 文字 #1D2129, 背景透明
  悬停: 背景 #F2F5FA
  选中: 背景 #EEF4FF, 文字 #4A90D9
  未读计数: 右对齐, 12px, 白字, 蓝色圆角背景 (#4A90D9), 最小宽度 20px

分组:
  主要分类 (收件箱/已发送/告警/审批/资讯) — 间距 2px
  ─── 1px 分割线 ───
  功能入口 (统计/模板) — 间距 2px

底部:
  账户信息: 邮箱地址缩写 (12px #86909C)
```

---

#### 9.5 工具栏

```
高度: 48px (含底部分割线)
背景: #FFFFFF
底边: 1px 分割线 #E5E6EB
内边距: 左 20px

按钮样式:
  类型: 文字按钮 (无边框，无背景)
  高度: 32px
  内边距: 左右 16px
  圆角: 6px
  图标: 16x16, 与文字间距 6px
  文字: 13px Medium

  默认态: 文字 #4A90D9, 背景透明
  悬停态: 背景 #EEF4FF
  按下态: 背景 #DDE8FA

  [拉取邮件] — 主操作, 蓝色文字
  [写邮件]   — 主操作, 蓝色文字
  [设置]     — 次操作, 灰色文字 #86909C, 靠右对齐

按钮间距: 8px
```

---

#### 9.6 邮件列表区域

```
背景: #F7F8FA
内边距: 8px

列表项 (每封邮件):
  高度: 自适应 (约 64px)
  背景: #FFFFFF
  圆角: 8px
  间距: 项间 4px
  内边距: 12px 16px
  阴影: 无

  悬停: 背景 #F2F5FA
  选中: 背景 #EEF4FF, 左边框 2px solid #4A90D9

  布局 (水平):
  ┌──────────────────────────────────────────┐
  │ 🔵 发件人名称              时间 (12px灰) │
  │    邮件主题 (13px, 未读加粗)              │
  │    正文预览前40字... (12px #86909C)       │
  └──────────────────────────────────────────┘

  未读标记: 🔵 4px 蓝色圆点, 在发件人左侧
  已读: 无圆点, 主题常规字重
  附件标记: 📎 图标在时间左侧 (仅当有附件时显示)

空状态:
  居中显示: 图标 + "暂无邮件" (14px #C9CDD4)

滚动条:
  宽度: 6px
  圆角: 3px
  颜色: #C9CDD4 (悬停 #86909C)
  背景: 透明
```

---

#### 9.7 邮件详情区域

```
背景: #FFFFFF
内边距: 24px

邮件头部:
  发件人: 15px Medium #1D2129
  邮箱地址: 13px Regular #86909C, 跟在发件人后
  时间: 13px Regular #86909C, 右对齐
  主题: 16px Bold #1D2129, 独立一行, 上间距 8px

分割线: 1px #E5E6EB, 上下间距 16px

正文区域:
  字体: 13px Regular #1D2129
  行高: 1.6
  最大宽度: 不限 (自适应)
  支持: 纯文本渲染 (MVP), HTML 渲染 (可选)

附件栏:
  位置: 正文下方, 分割线后
  高度: 40px
  背景: #F7F8FA
  圆角: 6px
  内边距: 0 12px
  每个附件: 图标 + 文件名 (13px) + 大小 (12px #86909C)
  附件间距: 12px
  悬停: 背景 #EEF4FF, 可点击

操作按钮栏:
  位置: 窗口底部 / 附件栏下方
  按钮: [回复] [转发] [标记已读] [删除]
  样式: 文字按钮, 13px, #4A90D9
  间距: 16px
  危险操作 (删除): #F53F3F

空状态 (未选中邮件):
  居中: 信封图标 (48x48, #E5E6EB) + "选择一封邮件查看详情" (14px #C9CDD4)
```

---

#### 9.8 状态栏

```
高度: 28px
背景: #F7F8FA
顶边: 1px 分割线 #E5E6EB
内边距: 左 16px

内容 (水平排列, 各项用 | 分隔):
  连接状态: 🟢 已连接 / 🔴 未连接 (12px)
  上次拉取: "上次拉取: HH:mm" (12px #86909C)
  待处理: "待处理: N" (12px #86909C)
  下次拉取: "下次: HH:mm" (12px #86909C)

各项间距: 20px
分隔符: " | " (12px #E5E6EB)
```

---

#### 9.9 全局交互规范

```
鼠标悬停:
  所有可点击元素: cursor = pointer
  悬停反馈延迟: 0ms (即时)
  悬停背景过渡: 150ms ease

按钮点击:
  按下反馈: 背景色加深 (见 9.5)
  过渡动画: 100ms ease

列表选中:
  过渡: 背景色 100ms ease

加载状态:
  拉取邮件时: [拉取] 按钮变为 "拉取中..." + 旋转图标
  禁用其他操作按钮 (防重复点击)

窗口缩放:
  侧栏宽度固定 200px
  邮件列表/详情分割条可拖拽
  最小窗口 800x540, 低于此尺寸禁用分割条拖拽
```

---

ix#### 9.10 PyQt6 样式实现方案

**方案：全局 QSS 样式表 + 少量代码微调**

```python
# src/gui/theme.py — 统一管理样式常量与 QSS

class Theme:
    # 颜色常量
    BG_MAIN = "#F7F8FA"
    BG_SIDEBAR = "#FFFFFF"
    BG_CARD = "#FFFFFF"
    BG_SELECTED = "#EEF4FF"
    BG_HOVER = "#F2F5FA"

    PRIMARY = "#4A90D9"
    PRIMARY_HOVER = "#3A7BC8"
    PRIMARY_PRESS = "#2E6AB5"

    TEXT_PRIMARY = "#1D2129"
    TEXT_SECONDARY = "#86909C"
    TEXT_PLACEHOLDER = "#C9CDD4"

    BORDER = "#E5E6EB"

    SUCCESS = "#00B42A"
    WARNING = "#FF7D00"
    ERROR = "#F53F3F"

    # QSS 样式表
    STYLESHEET = """
        QMainWindow { background: #F7F8FA; }

        /* 侧栏 */
        #sidebar {
            background: #FFFFFF;
            border-right: 1px solid #E5E6EB;
        }
        #sidebar QListWidget {
            border: none;
            outline: none;
            background: transparent;
        }
        #sidebar QListWidget::item {
            height: 36px;
            border-radius: 6px;
            padding: 0 12px;
            font-size: 13px;
            color: #1D2129;
        }
        #sidebar QListWidget::item:hover {
            background: #F2F5FA;
        }
        #sidebar QListWidget::item:selected {
            background: #EEF4FF;
            color: #4A90D9;
        }

        /* 工具栏 */
        #toolbar {
            background: #FFFFFF;
            border-bottom: 1px solid #E5E6EB;
            max-height: 48px;
        }
        #toolbar QPushButton {
            border: none;
            background: transparent;
            color: #4A90D9;
            font-size: 13px;
            font-weight: 500;
            padding: 6px 16px;
            border-radius: 6px;
        }
        #toolbar QPushButton:hover {
            background: #EEF4FF;
        }
        #toolbar QPushButton:pressed {
            background: #DDE8FA;
        }

        /* 邮件列表 */
        #mailList {
            background: #F7F8FA;
            border: none;
        }

        /* 邮件详情 */
        #mailDetail {
            background: #FFFFFF;
            border: none;
        }

        /* 状态栏 */
        #statusBar {
            background: #F7F8FA;
            border-top: 1px solid #E5E6EB;
            font-size: 12px;
            color: #86909C;
            max-height: 28px;
        }

        /* 滚动条 */
        QScrollBar:vertical {
            width: 6px;
            background: transparent;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: #C9CDD4;
            border-radius: 3px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #86909C;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        /* 分割条 */
        QSplitter::handle {
            background: #E5E6EB;
            width: 2px;
        }
        QSplitter::handle:hover {
            background: #4A90D9;
        }
    """
```

---

#### 9.11 具体实现要求

实现 `src/gui/main_window.py` 和 `src/gui/theme.py`：

1. **创建 `theme.py`** — 集中管理所有颜色常量和 QSS 样式表
2. **主窗口类 `MainWindow(QMainWindow)`**：
   - 窗口标题: "邮件助手"
   - 默认尺寸: 1100x720, 最小尺寸: 800x540
   - 应用全局 QSS 样式表
3. **侧栏** (QWidget, objectName="sidebar")：
   - 使用 QVBoxLayout + QListWidget
   - 分类项: 📥收件箱 / 📤已发送 / ⚠️告警 / 📋审批 / 📰资讯
   - 分割线后: 📊统计 / 📝模板
   - 底部: 当前账户邮箱地址
4. **工具栏** (QWidget, objectName="toolbar")：
   - QHBoxLayout, 左侧: [拉取邮件] [写邮件], 右侧: [设置]
   - 按钮使用 QIcon + 文字 (图标可用 SVG 或 Unicode emoji 替代)
5. **内容区** (QSplitter, 水平):
   - 左侧: 邮件列表面板 (objectName="mailList")
   - 右侧: 邮件详情面板 (objectName="mailDetail")
   - 分割比例: 3:7, 可拖拽
6. **状态栏** (QStatusBar, objectName="statusBar")：
   - 4 个 QLabel: 连接状态 / 上次拉取 / 待处理 / 下次拉取
7. **菜单栏**：文件(退出) / 帮助(关于)
8. **空状态**：详情区默认显示占位图标+文字

---

#### 9.12 验收标准

- [ ] 主窗口正常显示，整体视觉清新简洁
- [ ] 配色统一，无刺眼纯白/纯黑，层次分明
- [ ] 侧栏分类项可点击，选中态明显（蓝底蓝字）
- [ ] 工具栏按钮悬停/点击有反馈
- [ ] 邮件列表/详情分割条可拖拽
- [ ] 状态栏 4 项信息区域划分清晰
- [ ] 滚动条纤细 (6px)，风格统一
- [ ] 窗口缩放到最小尺寸时布局不崩坏
- [ ] 空状态有友好提示（非空白）
- [ ] 整体风格一致，无突兀的原生控件样式

---

### 任务 10：邮件列表面板

**目标：** 展示邮件列表，支持选择

**具体工作：**
实现 `src/gui/mail_list.py`：

1. 使用 `QListWidget` 或 `QTableWidget`
2. 每行显示：发件人、主题、时间、是否已读
3. 点击邮件 -> 右侧显示详情
4. 已读/未读视觉区分（加粗/普通）
5. 支持从 `MailStore` 加载邮件列表
6. 新邮件到达时自动刷新

**验收标准：**
- [ ] 邮件列表正确显示
- [ ] 点击邮件切换详情
- [ ] 新邮件到达后列表自动更新
- [ ] 已读/未读有视觉区分

---

### 任务 11：邮件详情面板

**目标：** 展示单封邮件的完整信息

**具体工作：**
实现 `src/gui/mail_detail.py`：

1. 显示字段：
   - 发件人、收件人、主题、时间
   - 正文内容（纯文本渲染，HTML 可选）
   - 附件列表（显示文件名和大小）
2. 操作按钮：
   - [回复] — 打开写邮件窗口（预填收件人和主题）
   - [转发] — 打开写邮件窗口
   - [标记已读/未读]
   - [删除]（仅标记，不物理删除）
3. 附件点击 -> 用系统默认程序打开（保存到临时目录）

**验收标准：**
- [ ] 邮件详情正确显示
- [ ] 回复/转发功能可用
- [ ] 附件可打开

---

### 任务 12：账户配置对话框

**目标：** 配置邮箱账户信息

**具体工作：**
实现 `src/gui/account_dialog.py`：

1. 表单字段：
   - 邮箱地址
   - 密码/授权码（密码输入框）
   - IMAP 服务器/端口（默认企微值）
   - SMTP 服务器/端口（默认企微值）
   - SSL 开关
2. [测试连接] 按钮 — 验证 IMAP/SMTP 连接
3. [保存] 按钮 — 保存到 `config/account.json`
4. 密码明文不存入配置文件，使用 base64 编码（MVP 阶段简单处理，Beta 阶段改用加密）

**验收标准：**
- [ ] 能配置账户信息
- [ ] 测试连接功能正常
- [ ] 配置保存后重启可加载
- [ ] 密码不以明文存储

---

### 任务 13：程序入口与集成

**目标：** 串联所有模块，完成 MVP

**具体工作：**
修改 `main.py`：

1. 初始化流程：
   - 加载配置 (`AppConfig`)
   - 初始化日志 (`setup_logging`)
   - 初始化存储 (`MailStore`)
   - 检查账户配置，无配置则弹出设置对话框
   - 启动 GUI (`QApplication`)
   - 启动调度器 (`MailScheduler`)
2. 退出流程：
   - 停止调度器
   - 断开 IMAP/SMTP 连接
   - 保存配置

**验收标准：**
- [ ] 程序完整启动流程正常
- [ ] 首次运行引导配置账户
- [ ] 退出时资源正确释放
- [ ] 无内存泄漏、无崩溃

---

## 开发顺序与依赖

```
任务1 脚手架 --> 任务2 数据模型 --> 任务3 解析器
                                        |
                    +-------------------+
                    v
              任务4 IMAP客户端 --> 任务5 存储 --> 任务6 SMTP
                    |                                |
                    v                                v
              任务7 调度器 --> 任务8 Worker --> 任务9 主窗口
                                                     |
                                        +------------+------------+
                                        v            v            v
                                   任务10 列表  任务11 详情  任务12 设置
                                        |            |            |
                                        +------------+------------+
                                                     v
                                               任务13 集成
```

**开发批次：**

| 批次 | 任务 | 说明 |
|------|------|------|
| 第1批 | 1 -> 2 -> 3 | 基础设施，无 UI 依赖 |
| 第2批 | 4 -> 5 -> 6 | 邮件引擎核心 |
| 第3批 | 7 -> 8 | 调度与线程 |
| 第4批 | 9 -> 10 -> 11 -> 12 | GUI 全部 |
| 第5批 | 13 | 集成联调 |

---

## MVP 不包含的功能（明确排除）

| 功能 | 排除原因 |
|------|----------|
| AI 分类 | Alpha 阶段实现 |
| 流程引擎 | Alpha 阶段实现 |
| 企微群通知 | Alpha 阶段实现 |
| 多账户 | Beta 阶段实现 |
| IMAP IDLE | Beta 阶段实现 |
| 密钥加密 (DPAPI) | Beta 阶段实现 |
| SQLite | Alpha 阶段引入 |
| 健康检查 | Beta 阶段实现 |
| 数据迁移 | Beta 阶段实现 |

---

## 技术约束

- Python 3.10+
- GUI 框架：PyQt6
- 定时调度：APScheduler
- 邮件协议：IMAP4 SSL + SMTP SSL
- 存储格式：JSON（MVP 阶段）
- 日志：标准库 `logging`
- 无外部数据库依赖
