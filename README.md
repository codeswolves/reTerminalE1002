# reTerminal E-Ink Dashboard

一个为 [Seeed Studio reTerminal](https://wiki.seeedstudio.com/reTerminal/) + E1002 5" 墨水屏设计的个人仪表盘生成器。读取数据源（CSV + JSON），生成 800x480 的 HTML 看板，可截图后推送到墨水屏显示。

**在线预览**：[codeswolves.github.io/reTerminalE1002](https://codeswolves.github.io/reTerminalE1002/output/dashboard/dashboard.html)

## 功能概览

- **三环目标仪表盘**：减重、论文、专利三环同心进度环
- **每日任务双段进度条**：昨天完成（实色）+ 今天推进（半透明）
- **月历健身打卡**：今天黄色高亮，已打卡绿色
- **北京实时天气**：SVG 图标 + 中文描述 + 温度
- **9 套主题风格**：一键换肤
- **全流水线**：生成 HTML → 截图 PNG → 推送墨水屏
- **任务清单可视化**：完成状态/优先级筛选 + 优先级排序 + 执行时间统计
- **任务流程跟踪树**：可视化每个任务的推进节点、耗时、负责人，支持交互式增删改节点

## 项目结构

```
reTerminal/
├── data/                        # 数据源
│   ├── weight.csv               # 体重记录
│   ├── fitness.csv              # 健身打卡（含 yesterday/today 双段数据）
│   ├── task_flows.json          # 任务流程数据（含元数据 + 流程节点）
│   ├── goals.csv                # 论文/专利目标进度
│   └── slogan.csv               # 口号记录
├── output/                      # 生成结果
│   ├── dashboard/               # 看板 HTML
│   │   ├── dashboard.html       # 默认看板
│   │   └── dashboard_<style>.html  # 各主题独立文件（--all 生成）
│   ├── screenshots/             # PNG 截图
│   │   └── dashboard.png
│   └── tasks/                   # 任务相关页面
│       ├── tasks_view.html      # 任务清单可视化筛选页面
│       └── task_flow.html       # 任务流程跟踪树页面
├── src/                         # 全部代码
│   ├── generators/              # HTML 生成器
│   │   ├── generate_dashboard.py    # 仪表盘 HTML 生成器（核心）
│   │   ├── generate_tasks_view.py   # 任务清单可视化页生成器
│   │   └── generate_task_flow.py    # 任务流程跟踪树页生成器（含数据层）
│   ├── utils/                   # 工具脚本
│   │   ├── serve_task_flow.py       # 任务页面 HTTP 服务器（静态文件 + REST API）
│   │   ├── render_screenshot.py     # HTML → PNG 截图工具
│   │   ├── embed_cjk_font.py        # 中文字体子集嵌入工具
│   │   └── display_on_eink.py       # PNG → 墨水屏显示工具
│   ├── pipeline/                # 流水线
│   │   ├── run_daily.py             # 一键流水线（生成+截图+显示）
│   │   └── refresh_csv.py           # 每日刷新 CSV 进度数据
│   └── setup/                   # 设备部署
│       └── setup_reterminal.sh      # reTerminal 设备端安装脚本
├── docs/                        # 文档
│   ├── design/                  # 设计文档
│   └── notes/                   # 技术笔记
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

核心生成器仅依赖 Python 内置模块（`csv`/`json`/`urllib`），无需额外安装。截图和墨水屏功能需可选依赖：

```bash
# 可选：截图工具
pip install playwright
playwright install chromium

# 可选：墨水屏显示（仅在 reTerminal 设备上需要）
pip install Pillow
```

### 2. 生成看板

```bash
# 生成默认风格（输出到 output/dashboard/dashboard.html）
python src/generators/generate_dashboard.py

# 指定日期
python src/generators/generate_dashboard.py --date 2026-08-01

# 生成后自动打开浏览器预览
python src/generators/generate_dashboard.py --open

# 生成指定主题
python src/generators/generate_dashboard.py --style cyberpunk

# 一次性生成所有 9 套主题到独立文件
python src/generators/generate_dashboard.py --all
```

### 3. 生成任务清单可视化页

```bash
# 生成 output/tasks/tasks_view.html（数据内嵌，双击即用）
python src/generators/generate_tasks_view.py

# 生成后自动打开浏览器
python src/generators/generate_tasks_view.py --open
```

页面顶部提供筛选按钮：全部 / 已完成任务 / 未完成任务 / 高优先级 / 中优先级 / 低优先级。

页面特性：

- **浅色主题**：白底浅色模式，配色与 `dashboard.html` 的 `light` 风格一致
- **排序规则**：默认按高 → 中 → 低优先级排列；"全部"标签下未完成任务在前、已完成在后
- **优先级标签**：高/中/低优先级仅显示未完成任务，并按创建时间排序（按钮计数同步为未完成数）
- **执行时间**：每张卡片显示任务执行时间——已完成任务显示 `执行时间：N 天`（创建日 → 完成日），未完成任务显示 `已进行 N 天`（创建日 → 今天，随日期自动更新）

### 3.5 任务流程跟踪树 & 本地服务器

任务流程跟踪树页面（`task_flow.html`）可视化每个任务的推进节点、耗时和负责人。需要通过本地服务器访问（支持交互式增删改节点）：

```bash
# 先生成页面
python src/generators/generate_task_flow.py
python src/generators/generate_tasks_view.py

# 启动本地服务器（默认端口 8080）
python src/utils/serve_task_flow.py --port 8080

# 浏览器访问
# http://localhost:8080/tasks_view.html   任务清单
# http://localhost:8080/task_flow.html    流程跟踪树
```

服务器提供 REST API，支持以下操作：

| 接口 | 功能 |
|------|------|
| `GET /api/tasks` | 获取所有任务（含计算字段） |
| `POST /api/add_node` | 添加流程节点 |
| `POST /api/edit_node` | 编辑节点 |
| `POST /api/delete_node` | 删除节点 |
| `POST /api/add_task` | 添加新任务 |
| `POST /api/delete_task` | 删除任务 |
| `POST /api/complete_task` | 一键完成任务 |

页面特性：

- **统计动态计算**：统计数字由 JS 从 API 数据实时计算，增删任务后刷新即同步
- **跨页面导航**：tasks_view 每张卡片有 🌳 按钮跳转到 task_flow 对应任务
- **一键完成**：未完成任务卡片有 ✅ 按钮，点击即标记为完成
- **流程节点管理**：支持添加/编辑/删除节点，弹窗表单填写阶段、日期、进度、负责人、备注

### 4. 截图为 PNG

```bash
# 将 output/dashboard/dashboard.html 截图为 output/screenshots/dashboard.png（800x480）
python src/utils/render_screenshot.py
```

### 5. 显示到墨水屏（仅 reTerminal 设备）

```bash
# 将 output/screenshots/dashboard.png 推送到墨水屏
python src/utils/display_on_eink.py

# 清屏（全白）
python src/utils/display_on_eink.py --clear
```

### 6. 一键流水线

```bash
# 默认流程：生成 HTML → 截图 PNG（不推送墨水屏）
python src/pipeline/run_daily.py

# 指定主题风格（默认 light）
python src/pipeline/run_daily.py --style cyberpunk

# 完整流程：生成 HTML → 截图 PNG → 推送墨水屏（需在 reTerminal 上运行）
python src/pipeline/run_daily.py --display

# 只生成 HTML，不截图不显示
python src/pipeline/run_daily.py --no-screenshot
```

## 主题风格

通过 `--style` 参数切换，共 9 套：

| 风格 | 说明 | 配色特征 |
|------|------|---------|
| `default` | 默认（对齐设计模板） | 深蓝灰 + 蓝/红/绿环 |
| `cyberpunk` | 赛博朋克 | 霓虹紫青黄 |
| `dracula` | 德古拉 | 深紫 + 紫/粉/绿 |
| `fui` | GitHub 风 | 深黑 + 蓝/红/绿 |
| `light` | 浅色明亮 | 白底 + 深色文字 |
| `macaron` | 马卡龙 | 粉嫩糖果色 |
| `morandi` | 莫兰迪 | 高级灰调 |
| `pixel` | 像素风 | 深紫 + 黄/绿/红 |
| `tactical` | 战术风 | 军绿配色 |

```bash
# 预览所有风格（生成独立文件后用浏览器打开）
python src/generators/generate_dashboard.py --all
# 然后访问 output/dashboard/dashboard_<style>.html
```

## CLI 参数详解

### `src/generators/generate_dashboard.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--date YYYY-MM-DD` | 目标日期 | 今天 |
| `--style <名称>` | 主题风格 | `light` |
| `--all` | 循环生成所有主题到独立文件 | 关闭 |
| `--open` | 生成后打开浏览器预览 | 关闭 |

### `src/generators/generate_tasks_view.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--open` | 生成后打开浏览器预览 | 关闭 |

### `src/generators/generate_task_flow.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--open` | 生成后打开浏览器预览 | 关闭 |

### `src/utils/serve_task_flow.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--port <端口>` | HTTP 服务器端口 | `8080` |

### `src/utils/render_screenshot.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--html <路径>` | 输入 HTML 文件 | `output/dashboard/dashboard.html` |
| `--output <路径>` | 输出 PNG 路径 | `output/screenshots/dashboard.png` |
| `--width <像素>` | 视口宽度 | `800` |
| `--height <像素>` | 视口高度 | `480` |

### `src/utils/display_on_eink.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--image <路径>` | 输入 PNG 图片 | `output/screenshots/dashboard.png` |
| `--clear` | 清屏（全白） | 关闭 |
| `--simple` | 简易 framebuffer 模式 | 关闭 |

### `src/pipeline/run_daily.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--date YYYY-MM-DD` | 目标日期 | 今天 |
| `--style <名称>` | 主题风格（9 套可选） | `light` |
| `--no-screenshot` | 跳过 PNG 截图步骤 | 关闭 |
| `--display` | 推送到墨水屏（需 reTerminal 设备） | 关闭 |

## 数据源格式

### `data/weight.csv`

体重记录，用于计算减重进度。

```csv
date,weight
2026-07-01,95.5
2026-08-01,89.8
```

减重目标默认为 **40 斤**（20kg），从首条记录的起始体重计算进度。修改 `src/generators/generate_dashboard.py` 中 `get_weight_info` 的 `target_loss = 40.0` 可调整目标。

### `data/fitness.csv`

健身打卡记录，`yesterday`/`today` 两列用于任务面板的双段进度条数据。

```csv
date,checkin,content,yesterday,today
2026-07-31,1,游泳1000米,1,1
2026-08-01,1,晨跑6公里,1,1
```

- `checkin`：`1` = 打卡，`0` = 未打卡
- `yesterday`/`today`：`0.0` ~ `1.0`，表示完成比例

### `data/task_flows.json`

任务流程数据（单一 JSON 文件），包含任务元数据和流程节点。仪表盘和任务页面均从此文件读取。

```json
{
  "no": "1",
  "name": "完成进度看板项目",
  "date": "2026/08/01",
  "priority": "high",
  "category": "工程",
  "nodes": [
    {"phase": "创建", "date": "2026/08/01", "progress": 70, "note": ""},
    {"phase": "完成", "date": "2026/08/01", "progress": 100, "note": "", "owner": "张三"}
  ]
}
```

- `no`：任务编号（字符串，自增）
- `name`：任务名称
- `date`：创建日期（`YYYY/MM/DD`）
- `priority`：`high` / `medium` / `low`
- `category`：任务分类（`科研` / `工程` / `标准` / `专利` / `个人`）
- `nodes`：流程节点列表，每个节点包含 `phase`（阶段）、`date`、`progress`（0~100）、`note`（可选）、`owner`（可选）

派生字段（由 `read_tasks()` 计算，不存储在 JSON 中）：`finished`、`status`、`total_days`、`stalled`、`days_from_prev`

### `data/goals.csv`

论文/专利目标进度，驱动三环仪表盘的中环和内环。

```csv
goal,target,done
paper,3,2
patent,3,1
```

## reTerminal 设备部署

### 一键安装

在 reTerminal 上执行：

```bash
chmod +x src/setup/setup_reterminal.sh
./src/setup/setup_reterminal.sh
```

安装脚本会：
1. 安装 Python 依赖（Pillow + playwright）
2. 安装 Chromium 浏览器
3. 创建数据目录和示例 CSV
4. 设置每日 07:00 的 crontab 定时任务

### 定时任务

安装后，每天早上 7 点自动刷新看板：

```bash
# 查看定时任务
crontab -l

# 日志位置
cat /tmp/dashboard_cron.log
```

手动修改 crontab 调整时间：

```bash
crontab -e
# 改为每天早上 8:00
0 8 * * * cd /home/pi/reTerminal && python3 src/pipeline/run_daily.py >> /tmp/dashboard_cron.log 2>&1
```

## 在开发机上预览

无需 reTerminal 设备，普通电脑也可生成和预览：

```bash
# 方式一：简单静态文件服务器（仅查看，不支持交互 API）
cd reTerminal/output
python -m http.server 8080

# 浏览器访问
# http://localhost:8080/dashboard/dashboard.html          默认主题
# http://localhost:8080/dashboard/dashboard_cyberpunk.html 赛博朋克
# http://localhost:8080/dashboard/dashboard_light.html     浅色

# 方式二：任务页面专用服务器（支持增删改 API）
python src/utils/serve_task_flow.py --port 8080

# 浏览器访问
# http://localhost:8080/tasks_view.html   任务清单
# http://localhost:8080/task_flow.html    流程跟踪树
```

## 技术细节

- **HTML 生成**：Python f-string 拼接，CSS 变量化主题系统（`THEMES` 字典）
- **天气获取**：[open-meteo.com](https://open-meteo.com) 免费 API（`/v1/forecast?current=temperature_2m,weather_code`），WMO 天气码 → 中文描述 + SVG 图标，北京固定经纬度（39.9042, 116.4074），8 秒超时，失败时静默降级（不阻塞生成）
- **三环 SVG**：`viewBox 0 0 210 210`，`r=92/58/24`，`stroke-width=20`，`rotate(-120 105 105)`
- **任务双段条**：每条任务一个 `.bar` 内含两段 `.seg`（昨天实色 + 今天半透明），合计宽度 = 任务总进度
- **月历**：周一起算，`.cell` 高 14px / 字号 10px，今天黄色高亮，已打卡绿色
- **动态日期**：`<script>` 在浏览器端用 `new Date()` 覆盖服务端生成时的日期

## 硬件要求

- **目标设备**：Seeed Studio reTerminal（CM4）+ E1002 5" 墨水屏
- **驱动芯片**：IT8951
- **分辨率**：800x480
- **开发预览**：任意现代浏览器

## 许可证

个人使用。
