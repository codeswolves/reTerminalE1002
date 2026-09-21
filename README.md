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
- **任务清单可视化**：按分类分组 + 完成状态/优先级筛选 + 优先级排序 + 执行时间统计 + 卡片内直接编辑任务
- **任务流程跟踪树**：可视化每个任务的推进节点、耗时、负责人，支持交互式增删改节点，可 📌 **置顶**当前重点任务；**已完成任务可就地打开后评估**（卡点归类）
- **项目管理（DAG）**：多项目索引 + 从起点到结束节点的有向无环图，支持里程碑依赖、**多路汇聚**、进度跟踪与页面上直接编辑
- **时间管理四象限**：按重要性 × 紧迫性归类任务（A/B/C/D），对比各象限预估工时占比与目标区间（A 20-25% / B 65-80% / C ≤15% / D 0）并给出偏差诊断；支持拖拽归类、工时录入、7 问自检，已完成任务可做后评估（卡点归类）；含周时间安排（拖拽排期 + 周自评 + 临时任务与每周机动额度）与仪表盘（平均完成时间、每周完成数、产出成果、估时偏差、分类投入占比、12 周趋势）
- **移动端适配**：上述五个交互页面在手机上自动切换单列布局，触屏下放大操作按钮点击区（仪表盘为墨水屏固定 800×480，不参与适配）

## 项目结构

```
reTerminal/
├── data/                        # 数据源（⚠️ 不在仓库中，需自行准备，见上方注意事项）
│   ├── weight.csv               # 体重记录
│   ├── fitness.csv              # 健身打卡（含 yesterday/today 双段数据）
│   ├── task_flows.json          # 任务流程数据（含元数据 + 流程节点）
│   ├── projects.json            # 项目数据（DAG：nodes 节点表 + edges 边表）
│   ├── week_plan.json           # 周时间安排（按周存排期 / 周自评 / 机动额度）
│   ├── goals.csv                # 论文/专利目标进度
│   └── slogan.csv               # 口号记录
├── output/                      # 生成结果
│   ├── dashboard/               # 看板 HTML
│   │   ├── dashboard.html       # 默认看板
│   │   └── dashboard_<style>.html  # 各主题独立文件（--all 生成）
│   ├── screenshots/             # PNG 截图
│   │   └── dashboard.png
│   ├── tasks/                   # 任务相关页面
│   │   ├── tasks_view.html      # 任务清单可视化筛选页面
│   │   ├── task_flow.html       # 任务流程跟踪树页面
│   │   └── quadrant.html        # 时间管理四象限页面
│   └── project/                 # 项目相关页面（⚠️ 不在仓库中，需本地生成）
│       ├── project_index.html   # 项目索引（新建/修改/删除项目）
│       └── project_tree.html    # 项目 DAG 图（里程碑、多路汇聚、连线）
├── src/                         # 全部代码
│   ├── generators/              # HTML 生成器
│   │   ├── meta.py                  # 分类/优先级/状态/节点类型的统一定义（单一来源）
│   │   ├── generate_dashboard.py    # 仪表盘 HTML 生成器（核心）
│   │   ├── generate_tasks_view.py   # 任务清单可视化页生成器
│   │   ├── generate_task_flow.py    # 任务流程跟踪树页生成器（含任务数据层）
│   │   └── generate_project.py      # 项目管理页生成器（含 DAG 数据层）
│   ├── utils/                   # 工具脚本
│   │   ├── serve_task_flow.py       # HTTP 服务器（静态文件 + REST API）
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

## ⚠️ 注意事项（先读）

### 仓库里**没有** `data/` 目录

出于隐私原因，个人数据（体重、健身、任务、项目）不随仓库分发（见 `.gitignore`）。克隆后需要自己创建：

```bash
mkdir -p data
```

然后按下方「数据源格式」章节的说明准备 CSV / JSON 文件。**缺少数据文件时，生成器会报错或产出空看板。**

### 部分页面需要本地生成

`output/tasks/` 与 `output/project/` 下的页面内嵌了个人数据（任务名、责任人等），同样不随仓库分发：

| 路径 | 内容 | 生成命令 |
|------|------|---------|
| `output/tasks/` | 任务清单、流程跟踪树 | `python src/generators/generate_tasks_view.py`<br>`python src/generators/generate_task_flow.py` |
| `output/project/` | 项目索引、项目 DAG 图 | `python src/generators/generate_project.py` |

仓库里**保留**的是 `output/dashboard/`（9 套主题看板）与 `output/screenshots/`，clone 后可直接打开预览。

### 数据文件没有版本控制保护

`data/` 已移出 git 跟踪，**误删无法用 git 找回**，建议定期另行备份（网盘 / 另一块盘）。

另有一条容易踩的：**验证 `data/` 有没有被改动不能靠 `git diff`**（它对未跟踪文件永远返回空，看起来"一切正常"）。
与"脱离 git 管理"相关的其余坑，见 [docs/notes/memory.md](docs/notes/memory.md) 的 ⑥⑦ 两节。

### 多端协作推送

本项目有多个提交来源（本地开发、NAS 定时任务等），**推送前必须先 `fetch` + `rebase`**，否则会被 GitHub 拒绝。规范见 [docs/notes/git-multi-end-collaboration.md](docs/notes/git-multi-end-collaboration.md)。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

核心生成器仅依赖 Python 内置模块（`csv`/`json`/`urllib`/`http.server`），无需额外安装。以下为可选依赖：

```bash
# 可选：截图工具
pip install playwright
playwright install chromium

# 可选：中文字体子集嵌入（generate_dashboard.py 默认启用，缺少则自动跳过并在终端提示）
pip install fonttools brotli

# 可选：墨水屏显示（仅在 reTerminal 设备上需要）
pip install Pillow
```

> 字体嵌入能让墨水屏在**没有中文字体**的情况下也正常显示中文，建议安装。缺 `fonttools`/`brotli` 时不会报错，只会打印 `[WARN] 中文字体嵌入失败，已跳过`。

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
- **按分类分组**：任务按 `category` 分成「科研 / 工程 / 标准 / 专利 / 个人 / 管理」若干区块，每块标题带分类图标与任务数（含已完成数）；组内**未完成在前、已完成沉底**。分类顺序与图标统一取自 `src/generators/meta.py`，数据里新增的分类会自动追加到末尾
- **排序规则**：默认按高 → 中 → 低优先级排列
- **优先级标签**：高/中/低优先级仅显示未完成任务，并按创建时间排序（按钮计数同步为未完成数）
- **执行时间**：每张卡片显示任务执行时间——已完成任务显示 `执行时间：N 天`（创建日 → 完成日），未完成任务显示 `已进行 N 天`（创建日 → 今天，随日期自动更新）
- **计划周期与延期**：未完成任务卡片显示 `📅 09/01 → 10/15 · 剩 28 天`。已过期显示红色「已延期 N 天」、3 天内到期显示橙色「剩 N 天」、未设置则灰字「未设计划截止」；已完成任务不显示该行
- **卡片操作**：🌳 查看流程树 / ✏️ **编辑任务** / ✅ 一键完成（仅未完成）/ 🗑️ 删除任务

### 3.5 任务流程跟踪树 & 本地服务器

任务流程跟踪树页面（`task_flow.html`）可视化每个任务的推进节点、耗时和负责人。需要通过本地服务器访问（支持交互式增删改节点）：

```bash
# 先生成页面
python src/generators/generate_task_flow.py
python src/generators/generate_tasks_view.py

# 启动本地服务器（默认端口 8080）
python src/utils/serve_task_flow.py --port 8080

# 浏览器访问
# http://localhost:8080/tasks_view.html            任务清单
# http://localhost:8080/task_flow.html             流程跟踪树
# http://localhost:8080/quadrant.html              时间四象限
# http://localhost:8080/project/project_index.html 项目索引
# http://localhost:8080/project/project_tree.html  项目 DAG 图
```

服务器提供 REST API，支持以下操作：

| 接口 | 功能 |
|------|------|
| `GET /api/tasks` | 获取所有任务（含计算字段） |
| `POST /api/add_node` | 添加流程节点 |
| `POST /api/edit_node` | 编辑节点 |
| `POST /api/delete_node` | 删除节点 |
| `POST /api/add_task` | 添加新任务 |
| `POST /api/edit_task` | 编辑任务（名称 / 优先级 / 分类 / 负责人 / 进度 / 备注 / 计划开始 / 计划截止） |
| `POST /api/pin_task` | 置顶 / 取消置顶任务（当前重点），入参 `{"no":"3","pinned":true}` |
| `POST /api/delete_task` | 删除任务 |
| `POST /api/complete_task` | 一键完成任务 |
| `GET /api/projects` | 获取所有项目（DAG 节点 + 边 + 派生进度） |
| `POST /api/project/add` | 新建项目 |
| `POST /api/project/edit` | 修改项目信息 |
| `POST /api/project/delete` | 删除项目（支持批量） |
| `POST /api/pnode/add` | 新增项目节点（自动建立 `parent → 新节点` 的边） |
| `POST /api/pnode/edit` | 修改项目节点 |
| `POST /api/pnode/delete` | 删除项目节点及关联边 |
| `POST /api/pnode/link` | 建立多上游连线（带环路检测） |
| `POST /api/pnode/unlink` | 断开一条连线 |
| `POST /api/pnode/done` | 标记 / 取消完成项目节点 |
| `POST /api/set_quadrant` | 设置 / 取消任务的四象限归类，入参 `{"no":"1","quadrant":"B"}`（`quadrant` 为空串表示取消归类，非法取值会被拒绝） |
| `POST /api/set_estimate` | 设置预估剩余工时（小时），入参 `{"no":"1","estimate_h":3.5}`（空值或 ≤0 删除该字段） |
| `POST /api/set_actual` | 设置实际净投入工时（小时），用于估时校准 |
| `POST /api/set_blockers` | 覆盖任务的卡点数组，入参 `{"no":"1","blockers":[{"type":"依赖他人","from":"2026/08/20","to":"2026/08/26","note":"等评审"}]}` |
| `POST /api/add_temp_task` | 记一笔临时（突发）任务：建任务（`temp: true`）+ 排进周表时段，**一次写完**，入参 `{"name":"临时会议","date":"2026/09/20","from":15,"to":17,"interrupt":"会议"}`；`interrupt` 可留空（= 未标注） |
| `POST /api/set_interrupt` | 补标 / 改标临时任务的机动来源，入参 `{"no":"47","interrupt":"他人求助"}`；空串 = 清掉标注 |
| `POST /api/week_buffer` | 设置某周的机动额度，入参 `{"week_start":"2026/09/14","hours":8}`；空值或等于默认值（5h）= 恢复默认，不留痕 |
| `POST /api/log_actual` | **累加**任务的累计实际投入（不是覆盖），入参 `{"no":"3","hours":0.5}`；累加在服务端做，避免多页面同时记录时互相覆盖 |

页面特性：

- **统计动态计算**：统计数字由 JS 从 API 数据实时计算，增删任务后刷新即同步
- **跨页面导航**：tasks_view 每张卡片有 🌳 按钮跳转到 task_flow 对应任务
- **编辑任务**：tasks_view 每张卡片有 ✏️ 按钮，可改名称 / 优先级 / 分类 / 负责人 / 进度 / 备注。进度写在**最后一个流程节点**上（任务进度 = 最后节点进度），负责人与备注写在**创建节点**上
- **一键完成**：未完成任务卡片有 ✅ 按钮，点击即标记为完成
- **流程节点管理**：支持添加/编辑/删除节点，弹窗表单填写阶段、日期、进度、负责人、备注
- **任务置顶（当前重点）**：每张卡片右上角 📌 可把任务置顶到所有分类之上，形成「📌 当前重点」分区，便于聚焦单件任务、减少上下文切换。置顶任务不再在分类区重复出现；置顶多个时分区标题会提示"建议一次只聚焦 1 个"
- **弹窗约定**：页面内所有确认与提示都用自绘的 `confirmBox()` / `toast()`，**不使用浏览器原生 `confirm()` / `alert()`**（内嵌预览会屏蔽它们，`confirm` 恒返回 `false`，表现为"点了没反应"）

### 3.6 项目管理（DAG）

项目数据采用 **DAG（有向无环图）** 结构：每个项目由扁平的**节点表**（`nodes`）和**边表**（`edges`）组成，**一个节点可以有多个上游**，因此能表达"多个模块的成果汇聚到同一个节点"这类依赖关系。

```bash
# 生成项目页面
python src/generators/generate_project.py

# 通过本地服务器访问（需先启动 serve_task_flow.py）
python src/utils/serve_task_flow.py --port 8080
# http://localhost:8080/project/project_index.html   项目索引
# http://localhost:8080/project/project_tree.html    项目 DAG 图
```

**项目索引页** — 卡片展示每个项目的分类、优先级、整体进度、节点完成数、负责人、目标日期：

| 操作 | 说明 |
|------|------|
| `＋ 新建项目` | 填写名称 / 分类 / 优先级 / 负责人 / 周期 / 目标 |
| `✏️`（卡片右上角，悬停显示） | 修改项目信息 |
| 勾选框 + `删除选中项目` | 批量删除项目 |

**项目 DAG 图** — 从左到右展示项目从起点到结束的完整拓扑，节点悬停出现操作按钮：

| 按钮 | 作用 |
|------|------|
| `＋` | 添加下游节点 |
| `🔗` | 连接到其它节点（建立额外上游，实现**多路汇聚**） |
| `✏️` | 编辑节点（名称 / 类型 / 负责人 / 日期 / 进度 / 备注） |
| `✅` | 标记完成 / 取消完成 |
| `🗑️` | 删除节点及其专属下游（被多个上游共享的节点会保留） |

**节点类型**：项目 / 里程碑 / 任务 / 交付物 / **结束节点**（布局上强制排在最后一列）。

**进度规则**（按优先级）：完成日期 > 手工填写 > 关联任务平均 > 下游节点平均 > 0。

> **怎么做多路汇聚**：例如三个模块开发完成后统一进入「集成联调」——先在其中一条分支下点 `＋` 新建该节点，再到另外两个模块上分别点 `🔗` 选中它即可。注意连线语义是**「当前节点 → 目标节点」**（当前节点在上游），方向别选反了，否则层级会颠倒。

详细设计（布局算法、删除语义、已知坑）见 [docs/design/project-management-design.md](docs/design/project-management-design.md)。

### 3.7 时间管理四象限

按**重要性 × 紧迫性**把任务归入四个象限，并诊断时间结构是否合理：

| 象限 | 含义 | 目标投入占比 | 每天目标（7h 基准） |
|------|------|--------------|--------------------|
| A | 重要且紧迫 | 20% – 25% | 1.40 – 1.75h |
| B | 重要但不紧迫 | 65% – 80% | 4.55 – 5.60h |
| C | 紧迫但不重要 | ≤ 15% | ≤ 1.05h |
| D | 不重要不紧迫 | 0% | 0h |

> 三个区间的**下界之和恰好 100%**（20 + 65 + 15），构成一个精确可行解；**上界之和 120%，不可能同时达到**。
> 因此页面把下界当达标线、上界当警戒线，展示原始比例而不做归一化。

```bash
# 生成四象限页面
python src/generators/generate_quadrant.py
python src/generators/generate_quadrant.py --open    # 生成后打开浏览器

# 通过本地服务器访问（需先启动 serve_task_flow.py，交互功能依赖它）
# http://localhost:8080/quadrant.html
```

**时间预算**：四象限比例的分母是**净可安排时间** —— `8h/天 × 5 天 = 40h`，减**每周机动 5h** 得 `35h/周`。
机动专门用于突发事项，**不参与象限分配**（算进分母等于预先给"未知"分配了确定的时间）。

机动**按周预留，不按天**。早期版本写的是"每天 1h"，但它不合现实：突发事件不可能每天恰好 1h，
拿刚性日配额去量弹性的事，周三出一次 3h 的事故就会被判成"超支 2h"，而真相只是那天事多；
反过来一整周没事的日子，那 1h 也白白作废、挪不到别的天。改成每周一个池子后**总量不变**（1h × 5 天 = 5h），
但允许跨天挪用。

页面顶部的「每天几小时 / 一周几天」可临时调整，只影响小时换算、**不落盘**；
**每周机动额度按周调整并落盘**（存 `week_plan.json` 的 `buffers`，只存偏离默认值的周），
所以翻到不同周看到的额度可以不同。

**页面特性**：

- **时间结构诊断**：每个象限一行，占比条上以浅色带标出目标区间，超界数字变红；命中偏差时给出诊断文案 ——
  如 `B < 65%` → "最危险的信号：长期价值投入不足，优先从 C 类回收时间"，`A > 25%` → "检查 A 类里有多少其实是拖成的 A"
- **口径透明**：标注"基于 n / m 个已估算任务"，且**未估算 ≠ 0**（未填工时的任务只参与计数，不参与占比计算，否则会让所有象限系统性偏低）
- **拖拽归类**：卡片可直接拖到目标象限，或用卡片上的 A/B/C/D 按钮（触屏下拖拽不可靠，按钮是主路径）
- **推导建议**：未标记的任务按 `priority` 与紧迫程度推导出建议象限，显示为虚线角标、**点击即采纳**；推导结果永不自动落盘
- **工时录入**：点卡片上的 `⏱` / "未估算" 填写**预计总投入**（`estimate_h`）与**累计实际投入**（`actual_h`）。后者用于估时校准（"实际是估算的多少倍"比"估得更准"更有用），也可以**边做边累加** —— 在周表的时段块弹窗里记一句"这次做了多少"，待安排里的「还差 Xh」会立刻跟着变
- **超预估不隐藏**：实际投入超过估时后，任务**仍留在待安排区**并标红 `超 Xh`，而不是"凭空消失"（它确实还没做完，只是估时失效了）。同时仪表盘的估时偏差**只统计已完成的任务**，免得进行中的低比值把系数带偏
- **完成与录入的两个衔接**：记完实际投入若剩余正好归零，会问一句「要顺便标记为完成吗」；反过来点 ✅ 完成时，若估过时却从没记过实际投入，会弹框问一句（**预填预估工时**，可跳过）。两处都**只提示、不自动执行** ——「投入 = 预估」不等于「做完了」，完成与否是你的判断，而它会牵动仪表盘
- **7 问自检**：待归类任务可点"7 问自检"，按"价值 × 能否推卸"推导象限；四问全否且拒绝无成本时，建议**直接拒绝、不入清单**（D 象限的正解是入口拒绝）
- **任务后评估**：已完成任务的复盘入口有两处，共用同一份数据 —— **流程跟踪页**在汇总行（与「＋ 添加节点」对称，一层就能看到）；**四象限页**在已完成卡片底部（注意：象限里的已完成任务是**从列表收起**、不是消失，要先点象限右上角「已完成 N ▾」展开）。内容：完成时间、总历时、估时偏差、最长空档、推进时间轴全部自动算出，只在检测到异常时才定向提问（带日期锚点 + 预填选项），人只需点选卡点类型。它**没有"提交"这一步**：打开看一眼、记下卡点即算评估完，是个随时可回看的记录

- **周时间安排**：拖动任务卡片到时间表即可排期（按 `estimate_h` 自动铺开，遇到午休或已占用时段会跳过并继续往后排）；支持查看上一周 / 下一周，**到新的一周自动切换，旧周数据保留**。**移出时段**有两个入口（时段块右上角的 `✕`、点开块后弹窗里的 `🗑️`），是同一个动作、都会回退该时段记过的实际投入；**临时任务只剩最后一个时段时删的是整条记录**（按钮文案会变成「删除记录」），免得留下一条没有任何时间记录、页面上又看不见的幽灵任务
- **临时（突发）任务**：点「＋ 临时任务」记一笔突发事项并落到时间表（虚线框 + 琥珀色，矮块自动切换紧凑布局）。时间**可直接输入**，精确到 10 分钟（`14:20–14:30` 这种也能录）；可标**状态**（已完成 / 进行中 / 未开始，默认已完成）、**预估工时**（留空则按 时长 算）和**机动来源**（会议 / 他人求助 / 行政事务 / 计划外沟通 / 其他，**可留空**）。它**只做时间记录、不进待办池** —— 不进待归类、不计入象限占比、不进仪表盘；但**未完成的会出现在待安排池**（带「临时」角标），因为突发的活常常一笔排不完，需要能继续占时间。周表底部汇总为 `机动：已用 X / 额度 Y`（不足 1 小时按分钟显示），超支标红，下一行按来源列出**构成**（如 `他人求助 2h · 会议 1h · 未标注 1h`）；周自评弹窗里同样显示这份构成，便于复盘。**在周表里点它的时段块就能收工**：``✅ 完成`` 会按 结束−开始 自动补上实际投入；**同一处也能补标/改标机动来源**（临时任务默认已完成、会离开待安排池，不在这里留个入口就再也补不上）
- **任务编排（一键排期）**：点周表工具栏的「🗓 任务编排」勾一批本周要做的任务，程序按 **优先级 → 象限 → 最久未推进** 的顺序铺进工作时间（09:00–18:00 去掉午休 = 7h/天 × 5 天，正好 = 每周净可安排 35h），不用一个个拖。每个任务排它的**剩余工作量**（超预估 / 未估算按 1h 兜底）；**只替换非临时时段** —— 临时任务的记录是已发生的事实，不会被抹掉、也不会被压到；**不足 1 小时的零碎空档跳过**（拖拽不受此限）。弹窗里实时显示"已选 N 个 · 需要 X h"，超出本周容量当场标红。默认只勾"估过时且还有剩余"的任务
- **每周机动额度**：默认 5h，可按周调整并落盘。**调整这个动作本身就是信号** —— 偶尔调高很正常，连着几周往上调才说明基线定低了、或突发已常态化
- **周自评**：每周可写一段自我评述；保存时会记下当时的**两类快照**（已排工时/时段数、本周已完成数与净投入），避免日后只能用今天的数字去解释当时的结论
- **预期成果**：创建任务时可标"这个任务要产出什么"（论文/标准/专利/报告/系统工具/文章/其他，**可留空 = 事务性任务**）。它与任务分类**正交** —— 分类是"工作领域"，成果是"产出类型"，不能互相推导（旧版用分类推成果，把"看完指南""联系某人"算成成果、又把工程类真实产出全排除）。卡片上的角标可就地修改
- **临时任务（机动记录）面板**（仪表盘上方）：一行一条列出所有临时任务 —— `[来源角标] 名称 …… 日期 · 时长 · 状态`，点一行直接打开它的工时弹窗。**已完成的默认收起**，用与象限矩阵同一个 `已完成 N ▾` 折叠胶囊；未完成的排在前面。标题旁给 `（N 条 · 合计 X h）`。独立成块是因为仪表盘衡量的全是计划内工作（已排除临时任务），而"机动被什么吃掉了"必须看得见 —— 它正好解释"计划外的时间去哪了"
- **仪表盘**：平均完成时间（同时给中位数，并单独列出"当天完成"与"跨天任务"两个口径）、本周完成数、产出成果（读 `deliverable`，未标记时显示 `—` 而非编数）、**估时偏差系数**（`实际 ÷ 预估`，即 §2.8 要的校准数）、各类任务的时间投入占比（实际 vs 计划对照）、近 12 周完成趋势

卡点类型（`需求不清 / 依赖他人 / 技术难点 / 返工 / 被打断 / 精力不足 / 外部阻塞 / 估算失误`）定义在 `src/generators/meta.py`。
归类而非自由文本，是为了能统计"最常因为什么卡住"并反哺配额调整。

**相关接口**：`/api/set_quadrant`（象限）、`/api/set_estimate`、`/api/set_actual`（工时，覆盖）、`/api/log_actual`（累加实际投入）、`/api/set_deliverable`（预期成果）、`/api/set_interrupt`（临时任务的机动来源）、`/api/set_blockers`（卡点）、`/api/complete_task`（完成任务）、`/api/delete_task`（删除任务，连带清掉它在各周的排期）、`/api/week_plan`（周排期，支持 `?week=`）、`/api/week_review`（周自评）、`/api/week_buffer`（每周机动额度）、`/api/add_temp_task`（记一笔临时任务，同时建任务 + 排时段）。
**注意**：改动 `serve_task_flow.py` 的接口后**必须重启服务端** —— 否则旧进程的响应里会缺字段，页面表现为"数据莫名消失"（文件里其实还在）。

详细设计（象限判定、区间张力、三条定律、估时方法、后评估、第二期排程）见 [docs/design/time-quadrant-design.md](docs/design/time-quadrant-design.md)。

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

### `src/generators/generate_project.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--open` | 生成后打开浏览器预览 | 关闭 |

### `src/generators/generate_quadrant.py`

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
  "start": "2026/08/01",
  "due": "2026/08/20",
  "pinned": true,
  "nodes": [
    {"phase": "创建", "date": "2026/08/01", "progress": 70, "note": ""},
    {"phase": "完成", "date": "2026/08/01", "progress": 100, "note": "", "owner": "张三"}
  ]
}
```

- `no`：任务编号（字符串，自增）
- `name`：任务名称
- `date`：创建日期（`YYYY/MM/DD`）—— 相当于任务的实际开始时间
- `priority`：`high` / `medium` / `low`
- `category`：任务分类（`科研` / `工程` / `标准` / `专利` / `个人` / `管理`）
- `start`：**计划开始**日期（可选，`YYYY/MM/DD`）
- `due`：**计划截止**日期（可选，`YYYY/MM/DD`）
- `pinned`：是否置顶为「当前重点」（可选，布尔；取消置顶时字段会被移除）
- `nodes`：流程节点列表，每个节点包含 `phase`（阶段）、`date`、`progress`（0~100）、`note`（可选）、`owner`（可选）

派生字段（由 `read_tasks()` 计算，不存储在 JSON 中）：`finished`、`completed_date`、`status`、`total_days`、`stalled`、`days_from_prev`、`pinned`、`plan_days`、`days_left`、`delayed`

> **任务的"结束时间"没有独立字段**：未完成时看 `due`（计划截止），完成后由最后一个流程节点的日期派生出 `completed_date`。`delayed`（是否延期）和 `days_left`（剩余天数）只对未完成任务计算。

### `data/projects.json`

项目数据，采用 **DAG（有向无环图）** 结构。每个项目含扁平的节点表和边表，`root` 指向根节点 id：

```json
{
  "id": "P01",
  "name": "天地承载网规划优化工具",
  "category": "工程",
  "owner": "李佳伟",
  "priority": "high",
  "start": "2026/09/14",
  "target": "2026/11/30",
  "goal": "集成已有成果，形成演示demo",
  "root": "P01",
  "nodes": [
    {
      "id": "P01-C2-C1",
      "name": "完成“评估子系统”开发",
      "kind": "task",
      "owner": "李佳伟",
      "plan": "2026/09/30",
      "actual": "",
      "note": "",
      "tasks": [],
      "progress": 80
    }
  ],
  "edges": [
    { "from": "P01-C2-C1", "to": "P01-C2-C4" },
    { "from": "P01-C2-C2", "to": "P01-C2-C4" }
  ]
}
```

- `nodes[].kind`：`project` / `milestone` / `task` / `deliverable` / `end`
- `nodes[].progress`：手工进度（可选）。不填时按下游节点或关联任务汇总
- `nodes[].tasks`：关联任务编号，引用 `task_flows.json` 的 `no`（可选）
- `edges[]`：每条边表示一次「上游 → 下游」的依赖；**一个节点有几条入边就有几个上级**

> 旧版的嵌套树格式（`root` 为对象 + `children` 数组）会在读取时**自动迁移**成新格式，无需手工转换。

### `data/week_plan.json`

周时间安排的数据文件，**按周存储**（key 是该周周一）：

```json
{
  "weeks": {
    "2026/09/14": [
      {"no": "37", "day": 1, "from": 9, "to": 11}
    ]
  },
  "reviews": {
    "2026/09/14": {
      "text": "本周...",
      "at": "2026/09/18 22:40",
      "plan_h": 11.0, "slot_n": 2, "done_n": 3, "done_h": 17.5
    }
  },
  "buffers": {
    "2026/09/21": 8
  }
}
```

- `weeks`：该周的时段。`day` 为 `1`（周一）~ `7`（周日），`from`/`to` 是 24 进制小时，只允许落在 `08:30–22:30` 并对齐到 **10 分钟网格**（所以能精确记录 `14:20–14:30` 这样的短时段）
- `reviews`：周自评。`plan_*` / `done_*` 是**写自评那一刻的快照**，用于日后回看时能对上当时的数字口径
- `buffers`：该周的机动额度（小时）。**只存偏离默认值（`WEEK_BUFFER_H = 5`）的周** —— 等于默认值时该键会被删掉，这样"哪几周真的调过额度"一眼可见
- 三个字段**必须一起读写**：它们共用同一个文件，只写其中一个会静默抹掉另外两个
- 到新的一周自动切换到空白的新周（**不需要手动清空**），旧周数据保留，可翻回去看

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

# 方式二：任务/项目页面专用服务器（支持增删改 API）
python src/utils/serve_task_flow.py --port 8080

# 浏览器访问
# http://localhost:8080/tasks_view.html            任务清单
# http://localhost:8080/task_flow.html             流程跟踪树
# http://localhost:8080/quadrant.html              时间四象限
# http://localhost:8080/project/project_index.html 项目索引
# http://localhost:8080/project/project_tree.html  项目 DAG 图
```

## 技术细节

- **HTML 生成**：Python f-string 拼接，CSS 变量化主题系统（`THEMES` 字典）
- **天气获取**：[open-meteo.com](https://open-meteo.com) 免费 API（`/v1/forecast?current=temperature_2m,weather_code`），WMO 天气码 → 中文描述 + SVG 图标，北京固定经纬度（39.9042, 116.4074），8 秒超时，失败时静默降级（不阻塞生成）
- **三环 SVG**：`viewBox 0 0 210 210`，`r=92/58/24`，`stroke-width=20`，`rotate(-120 105 105)`
- **任务双段条**：每条任务一个 `.bar` 内含两段 `.seg`（昨天实色 + 今天半透明），合计宽度 = 任务总进度
- **月历**：周一起算，`.cell` 高 14px / 字号 10px，今天黄色高亮，已打卡绿色
- **动态日期**：`<script>` 在浏览器端用 `new Date()` 覆盖服务端生成时的日期
- **枚举单一来源**：分类、优先级、任务状态、项目节点类型统一在 `src/generators/meta.py` 定义，生成器通过 `meta.js()` 注入到页面，下拉选项也由 Python 循环生成。**新增一个分类只需改 `meta.py` 一处**；流程页还会从数据里动态收集实际出现的分类，即使漏改也不会丢数据
- **移动端适配**：五个交互页面各带 `@media (max-width: 640px)`（布局）与 `@media (hover: none)`（触屏点击区）两组规则，写在各自 `</style>` 之前；墨水屏仪表盘固定 800×480 不参与适配。详见 [移动端适配设计文档](docs/design/mobile-responsive.md)

## 硬件要求

- **目标设备**：Seeed Studio reTerminal（CM4）+ E1002 5" 墨水屏
- **驱动芯片**：IT8951
- **分辨率**：800x480
- **开发预览**：任意现代浏览器

## 待办（TODO）

### 与 NAS 上的真实数据打通

个人数据只存在 NAS 上（`data/` 不进版本库，见上方「注意事项」），开发机上的这份是**测试副本**。
这带来两个限制：基于真实数据的分析做不了（机动额度校准、估时偏差走势、象限长期漂移），
本地跑出来的结论也只对测试数据有效。

分析其实只需要三个文件就够：`data/task_flows.json`（任务）、`data/week_plan.json`（排期 + 自评 + 机动额度）、
`data/projects.json`（项目）。可选方案按成本从低到高：

| 方案 | 做法 | 适用 |
|------|------|------|
| **A. 拷文件** | 把 NAS 上的 `data/*.json` 拷到本地 | 只要分析，不需要在真实数据上跑脚本 |
| **B. 挂载目录** | `net use Z: \\NAS\share`，让本地 `data/` 指向它 | 想在真实数据上直接跑脚本与验证 |
| **C. 局域网直连 API** | 读 `http://<NAS_IP>:8080/api/tasks` 等接口 | 想实时读 |

**建议先走 A** —— 零风险（本地进程碰不到 NAS）、零配置、够用；觉得每次拷太麻烦再升级到 B 或 C。

> ⚠️ **动手前必须先确认端口暴露情况**：`serve_task_flow.py` 的 REST API **没有任何鉴权**
> （代码里没有 token / `Authorization` 校验），任何能访问该端口的人都能读到全部任务数据。
> 如果 NAS 上的 8080 做过端口映射 / DMZ / UPnP 自动映射，等于把工作数据实时公开到公网 ——
> 静态页面泄露的只是"生成那一刻的快照"，API 泄露的是实时数据。
> 需要跨网络访问时，先加一层简单的 token 校验（默认只放行本机，需要时才开）。

### 机动额度的数据驱动校准

`WEEK_BUFFER_H = 5` 目前是拍的值。等积累满 8 周左右的真实突发记录后，可以用历史数据反推：
取**中位数或 P75**（不要取平均数 —— 会被单次大事故拉高，同估时偏差踩过的坑），
得到一个比 5h 更贴合实际的额度。数据量不够之前做不了。

有了**机动来源**之后，这个校准还能再分一层：如果"会议"一类就吃掉了大半个额度，
结论不是"额度该调高"，而是"会议该压缩" —— 一个是加时间、一个是省时间，动作完全相反。
来源构成在周表底部和周自评弹窗里都能看到（见上方「临时（突发）任务」）。

### 日粒度的机动消耗

现在的机动记录是**周粒度**（本周共多少小时突发）。日粒度（那几小时具体落在哪一天）
在额度改成按周之后价值已下降，只剩一个参考价值：看突发是**集中在某一天**（单次大事件）
还是**每天都在漏**（常态）—— 两者的结论完全不同。详见
[设计文档 §8](docs/design/time-quadrant-design.md)。

## 许可证

个人使用。
