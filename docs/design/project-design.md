# reTerminal E-Ink Dashboard — 项目设计文档

## 1. 项目概述

reTerminal E-Ink Dashboard 是一个为 [Seeed Studio reTerminal](https://wiki.seeedstudio.com/reTerminal/) + E1002 5" 墨水屏设计的**个人仪表盘系统**。系统从 CSV/JSON 数据源生成 800×480 的 HTML 看板，经截图后推送到墨水屏显示，同时提供任务清单可视化和流程跟踪树等 Web 页面。

### 1.1 核心目标

- 在 5 寸墨水屏上展示每日个人关键指标（体重、健身、任务、天气、口号）
- 提供任务管理的 Web 可视化界面（筛选、排序、流程跟踪）
- 支持每日自动化流水线：数据刷新 → HTML 生成 → PNG 截图 → 墨水屏推送
- 9 套主题风格可切换

### 1.2 硬件规格

| 参数 | 值 |
|------|-----|
| 目标设备 | Seeed Studio reTerminal (CM4) |
| 屏幕 | E1002 5" E-Ink |
| 驱动芯片 | IT8951 |
| 分辨率 | 800×480 |

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据层 (data/)                            │
│  weight.csv  fitness.csv  goals.csv  slogan.csv  task_flows.json│
└────────────┬──────────────────────────────────┬─────────────────┘
             │                                  │
    ┌────────▼────────┐               ┌─────────▼─────────┐
    │  refresh_csv.py │               │ serve_task_flow.py │
    │  (每日CSV刷新)   │               │ (HTTP服务器+API)   │
    └────────┬────────┘               └─────────┬─────────┘
             │                                  │
    ┌────────▼────────────────────────────────▼──────────┐
    │                   生成层 (generators/)               │
    │  generate_dashboard.py  generate_tasks_view.py      │
    │  generate_task_flow.py (含数据层 read_tasks 等)      │
    └────────┬────────────────────────────────┬──────────┘
             │                                │
    ┌────────▼────────┐              ┌────────▼─────────┐
    │  output/        │              │  output/tasks/   │
    │  dashboard/     │              │  tasks_view.html │
    │  dashboard.html │              │  task_flow.html  │
    └────────┬────────┘              └──────────────────┘
             │
    ┌────────▼────────┐
    │ render_screenshot│
    │ (HTML → PNG)    │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ display_on_eink │
    │ (PNG → 墨水屏)  │
    └─────────────────┘
```

### 2.1 分层说明

| 层 | 目录/文件 | 职责 |
|----|-----------|------|
| 数据层 | `data/` | 存储 CSV 和 JSON 数据源 |
| 刷新层 | `src/pipeline/refresh_csv.py` | 每日更新 CSV 进度数据 |
| 生成层 | `src/generators/` | 读取数据源，生成 HTML 页面 |
| 服务层 | `src/utils/serve_task_flow.py` | 本地 HTTP 服务器，提供静态文件和 REST API |
| 工具层 | `src/utils/` | 截图、墨水屏显示、字体嵌入等工具 |
| 流水线 | `src/pipeline/run_daily.py` | 一键编排：生成 → 截图 → 显示 |
| 部署 | `src/setup/setup_reterminal.sh` | 设备端安装脚本 |

## 3. 数据源

### 3.1 CSV 文件

| 文件 | 用途 | 格式 |
|------|------|------|
| `weight.csv` | 体重记录 | `date,weight` |
| `fitness.csv` | 健身打卡 | `date,checkin,content,yesterday,today` |
| `goals.csv` | 目标进度 | `goal,target,done` |
| `slogan.csv` | 每日口号 | 单列文本 |

CSV 文件由 `refresh_csv.py` 每日刷新，支持日期清洗（防表格软件格式污染）。

### 3.2 JSON 文件

`task_flows.json` 是任务数据的**唯一数据源**，包含任务元数据和流程节点：

```json
{
  "no": "1",
  "name": "任务名称",
  "date": "2026/08/01",
  "priority": "high",
  "category": "工程",
  "nodes": [
    {"phase": "创建", "date": "2026/08/01", "progress": 70},
    {"phase": "完成", "date": "2026/08/01", "progress": 100, "owner": "张三"}
  ]
}
```

派生字段（`finished`、`status`、`total_days`、`stalled`、`days_from_prev`）由 `read_tasks()` 在读取时动态计算，不持久化存储。

## 4. 页面与生成器

### 4.1 仪表盘 (`generate_dashboard.py`)

**输出**：`output/dashboard/dashboard.html`（800×480）

**页面模块**：
- 三环目标进度环（SVG）：减重 / 论文 / 专利
- 天气信息：调用 open-meteo API，WMO 天气码 → 中文描述 + SVG 图标
- 每日任务进度条：双段设计（昨天实色 + 今天半透明）
- 月历健身打卡：周一起算，今天高亮
- 每日口号

**主题系统**：通过 CSS 变量实现 9 套主题一键换肤，`THEMES` 字典定义每套主题的配色。

### 4.2 任务清单 (`generate_tasks_view.py`)

**输出**：`output/tasks/tasks_view.html`

**功能**：
- 按状态筛选（全部/已完成/未完成）
- 按优先级筛选和排序
- 动态统计（JS `updateStats()` 从 API 数据实时计算）
- 每张卡片可跳转到流程跟踪树（🌳 按钮）
- 一键完成任务（✅ 按钮）

### 4.3 流程跟踪树 (`generate_task_flow.py`)

**输出**：`output/tasks/task_flow.html`

**功能**：
- 按分类分组展示每个任务的流程树
- 每个节点显示阶段、日期、进度、负责人、距上节点耗时
- 统计概览（已完成/进行中/未开始/平均耗时/最长耗时）
- 复盘分析区（分类统计、超期 TOP5、停滞任务、优先级倒挂）
- 筛选/排序/折叠
- 交互式节点管理（添加/编辑/删除）

**数据层**：`generate_task_flow.py` 同时承担数据层职责，提供：
- `read_tasks_raw()` / `write_tasks_raw()` — JSON 原始读写
- `read_tasks()` — 读取并计算派生字段
- 被 `generate_tasks_view.py` 和 `serve_task_flow.py` 复用

## 5. 本地服务器

`serve_task_flow.py` 基于 Python 标准库 `http.server`，提供：

**静态文件服务**：以 `output/tasks/` 为根目录

**REST API**：

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/tasks` | GET | 获取所有任务（含计算字段） |
| `/api/add_node` | POST | 添加流程节点 |
| `/api/edit_node` | POST | 编辑节点 |
| `/api/delete_node` | POST | 删除节点 |
| `/api/add_task` | POST | 添加新任务 |
| `/api/delete_task` | POST | 删除任务 |
| `/api/complete_task` | POST | 一键完成任务 |

所有 API 直接操作 `task_flows.json`，无需额外数据库。

## 6. 流水线

### 6.1 每日刷新 (`run_daily.py`)

```
Step 1: 生成仪表盘 HTML (generate_dashboard.py)
Step 2: 生成任务页面 (generate_tasks_view.py + generate_task_flow.py)
Step 3: 渲染 PNG 截图 (render_screenshot.py)  [可选]
Step 4: 推送墨水屏 (display_on_eink.py)       [可选，需设备]
```

### 6.2 CSV 刷新 (`refresh_csv.py`)

每日更新 CSV 数据：
- `weight.csv`：覆盖/追加今日体重
- `fitness.csv`：覆盖/填入今日打卡
- `goals.csv`：目标 done +1
- `slogan.csv`：追加新口号

任务数据不再通过 CSV 管理，而是通过 `serve_task_flow.py` 的 REST API 操作。

### 6.3 定时任务

reTerminal 设备上通过 crontab 设置每日自动执行：
```bash
0 8 * * * cd /home/pi/reTerminal && python3 src/pipeline/run_daily.py
```

## 7. 工具脚本

| 脚本 | 功能 | 依赖 |
|------|------|------|
| `render_screenshot.py` | HTML → 800×480 PNG | playwright（优先用系统 Edge/Chrome） |
| `display_on_eink.py` | PNG → 墨水屏显示 | Pillow + IT8951 驱动 |
| `embed_cjk_font.py` | CJK 字体子集嵌入 | — |
| `serve_task_flow.py` | 本地 HTTP 服务器 | Python 标准库 |

## 8. 技术选型

| 决策 | 选型 | 理由 |
|------|------|------|
| HTML 生成 | Python f-string 拼接 | 轻量、无前端构建依赖、适合模板化页面 |
| 主题系统 | CSS 变量 + THEMES 字典 | 一键换肤，生成时注入 |
| 任务数据 | 单一 JSON 文件 | 30 条任务规模无需数据库，JSON 支持嵌套节点 |
| 页面交互 | 原生 JS + fetch API | 无框架依赖，页面加载快 |
| 截图 | Playwright | 支持 headless Chrome，渲染准确 |
| 天气 | open-meteo.com | 免费 API，无需 key |
| 字体 | 系统 CJK 字体子集嵌入 | 墨水屏需要中文字体，子集化减小体积 |

## 9. 文件清单

```
reTerminal/
├── data/                           # 数据源
│   ├── weight.csv                  # 体重
│   ├── fitness.csv                 # 健身打卡
│   ├── goals.csv                   # 目标进度
│   ├── slogan.csv                  # 口号
│   └── task_flows.json             # 任务流程数据（唯一数据源）
├── output/                         # 生成产物
│   ├── dashboard/                  # 仪表盘 HTML（9 套主题）
│   ├── screenshots/                # PNG 截图
│   └── tasks/                      # 任务页面
│       ├── tasks_view.html         # 任务清单
│       └── task_flow.html          # 流程跟踪树
├── src/
│   ├── generators/
│   │   ├── generate_dashboard.py   # 仪表盘生成（核心，~850 行）
│   │   ├── generate_tasks_view.py  # 任务清单页生成（~430 行）
│   │   └── generate_task_flow.py   # 流程树页生成 + 数据层（~830 行）
│   ├── utils/
│   │   ├── serve_task_flow.py      # HTTP 服务器 + REST API（~230 行）
│   │   ├── render_screenshot.py    # HTML → PNG（~110 行）
│   │   ├── display_on_eink.py      # PNG → 墨水屏（~180 行）
│   │   └── embed_cjk_font.py       # CJK 字体嵌入
│   ├── pipeline/
│   │   ├── run_daily.py            # 一键流水线（~180 行）
│   │   └── refresh_csv.py          # CSV 每日刷新（~230 行）
│   └── setup/
│       └── setup_reterminal.sh     # 设备部署脚本
├── docs/
│   ├── design/                     # 设计文档
│   └── notes/                      # 技术笔记 & 项目约定
└── requirements.txt
```
