# 移动端适配 — 设计文档

## 1. 背景

最初的四个交互页面（任务清单、任务流程树、项目索引、项目图）只针对桌面浏览器设计，
CSS 里没有任何 `@media` 规则。在手机窄屏上会出现两类问题：

1. **横向 flex 被挤压**：顶栏用 `justify-content: space-between`，右侧统计卡带固定
   `min-width` 不肯让位，把左侧标题区压到只剩约 110px，于是标题、副标题、按钮被挤成
   **逐字竖排**（内层 flex 没有 `flex-wrap`，无法折行）
2. **依赖 `:hover` 的按钮在触屏上不可用**：编辑、置顶、节点操作等按钮默认
   `opacity: 0` 或极低，只在鼠标悬停时才显示，触屏永远点不到

## 2. 适配范围

| 页面 | 生成器 | 是否适配 |
|------|--------|----------|
| 任务清单 `tasks_view.html` | `generate_tasks_view.py` | ✅ |
| 任务流程树 `task_flow.html` | `generate_task_flow.py` | ✅ |
| 项目索引 `project_index.html` | `generate_project.py` | ✅ |
| 项目图 `project_tree.html` | `generate_project.py` | ✅ |
| 时间四象限 `quadrant.html` | `generate_quadrant.py` | ✅ |
| 仪表盘 `dashboard.html` | `generate_dashboard.py` | ❌ 墨水屏固定 800×480 |

仪表盘的 `.dash` 是硬编码的 `width: 800px; height: 480px`，输出目标就是 E1002
墨水屏的物理分辨率，**不做响应式** —— 改了反而会破坏截图与推送流程。

> 注意区分两个"仪表盘"：§2 表格里 **❌ 的 `dashboard.html`** 是墨水屏那个；
> `quadrant.html` 页面**内部**也有一块叫"仪表盘"的区域（平均完成时间 / 每周完成 /
> 产出成果 / 估时偏差），它属于四象限页，**是参与适配的**。

四象限页是后来新增的，建它时这份文档已经写完、也不在它的适配范围内，
所以第一版漏掉了窄屏处理（见 §5.4）。

## 3. 断点与规则

统一只用 `640px` 一个断点，规则写在每个页面 `</style>` 之前：

- `@media (max-width: 640px)` —— 布局：顶栏纵向堆叠、网格改单列、统计卡自然换行、
  弹窗内双列输入改竖排
- `@media (hover: none)` —— 触屏：把依赖 hover 的按钮改为常显并放大点击区

## 4. 各页面改动

### 4.1 任务清单 `tasks_view.html`

- 顶栏 DOM 补 `.head-left` / `.head-title` 类名，便于媒体查询精确控制
- 窄屏：`.header` 改纵向堆叠，标题独占整行且 `white-space: nowrap`，
  统计卡拉满宽度平分，任务网格改单列
- 触屏：卡片上的 ✏️ / ✅ / 🗑️ 不透明度从 `.35` 提到 `.6`，并放大点击区

### 4.2 任务流程树 `task_flow.html`

- `.sort-bar` 原本没有 `flex-wrap`，≤360px 时 6 个排序按钮会被压成逐字竖排 —— 补上
- 窄屏：顶栏纵向堆叠、复盘卡片网格改单列
- 触屏：置顶星标 `.pin-btn`（默认 `opacity: .25`）与节点操作按钮 `.node-act` 常显

### 4.3 项目索引 `project_index.html`

- 卡片网格原为 `repeat(auto-fill, minmax(320px, 1fr))`，视口 ≤352px 时轨道撑破容器
  产生横向滚动 —— 窄屏改为单列
- 触屏：卡片编辑按钮 `.pedit` 原为 `opacity: 0`，改为常显

### 4.4 项目图 `project_tree.html`

- 窄屏：隐藏顶栏 `.spacer`、画布高度解锁（`max-height: none`）便于整页滚动
- 触屏：节点操作按钮 `.pn-acts` 原依赖 `.pnode:hover` 显示，改为常显

### 4.5 时间四象限 `quadrant.html`

- 窄屏：四象限矩阵 `.matrix` 改单列、诊断行 `.diag-row` 与后评估事实表 `.facts` 改单列、
  卡片底部 `.card-foot` 由左右两端改为上下堆叠
- **仪表盘区域** `.dash` 由 4 列改 **2 列** —— 4 列时每格只剩约 78px，24px 的大数字会被挤到换行
- **分类占比** `.dist-row` 隐藏"计划 / pp 差"两列，只留名称、占比条、百分比
- **趋势图** 12 组柱与日期标签的间距、字号一并缩小
- 触屏：`.est` / `.hint` / `.qbtn` 放大点击区（`.qbtn` 24×24）

**周时间表是唯一需要横向滚动的部分**：7 天 × 105px = 820px，物理上放不进 390px。
它被包在 `.wk-scroll` 里横向滚动，这是有意的 —— 拖动排期需要格子够大。
（若日后要改，方向是"只显示今天 + 左右切日期"或"每天一屏"，而不是压缩格子。）

同一张卡片上，"待安排"区的小时数是可点击的（改预估工时），
卡片主体的点击也会打开工时弹窗 —— 触屏下这两处都依赖点击，
不要把它们改成需要 hover 才显示。

## 5. 踩过的坑

### 5.1 不要覆盖统计卡的 `min-width`

`.stats` 自带 `flex-wrap: wrap`，`.st` 自带 `min-width: 70px`，**两者配合本来就能
自然换行**。适配时若给 `.st` 加 `min-width: 0`，会覆盖掉基础样式的 70px 保护，
导致卡片被无限压缩：流程树有 5 个统计卡，375px 屏上每卡文字区只剩约 48px，
而"平均耗时(天)"约需 66px，会折成两行、卡片高矮不一。

改用 `flex: 1` 拉伸同样不行：5 个卡换行后若最后一行只剩 1 个，会被拉伸到满宽
（4+1 布局），比留白更难看。**正确做法是只调 `padding`，不碰 `flex` 与 `min-width`。**

### 5.2 触屏没有 hover

所有"hover 才显示"的按钮在触屏设备上等价于不存在。排查时可全局搜索
`opacity: 0` 与 `:hover`，逐个确认是否需要 `@media (hover: none)` 兜底。

### 5.3 验证产物要用 `findstr`，别用搜索工具

`output/` 被 `.gitignore` 忽略，ripgrep 默认尊重 ignore 规则，**即使显式指定文件
路径也会跳过**，对 `output/` 下的产物搜索会返回 0 结果（假阴性）。验证生成结果请用：

```bash
findstr /C:"@media" output\tasks\task_flow.html output\project\project_index.html
```

### 5.4 flex 项目的 `min-width` 默认不是 0

趋势图的 X 轴是 12 个 `flex: 1` 的日期标签（`06/29`、`07/06` …），
在 390px 屏上把容器撑破了 26px。

原因不是空间不够，而是 **flex 项目的 `min-width` 默认值是 `auto`** ——
意思是"宽度不能小于我的内容宽度"。所以 `flex: 1` 分配下来的结果若小于内容宽度，
它不会压缩，而是直接溢出。

```css
/* 加 min-width:0 才允许压到内容宽度以下 */
.dash-x div { flex: 1; min-width: 0; }
```

这与 §5.1 是同一类问题的两面：**§5.1 是 `min-width: 0` 加错了地方（覆盖了保护值），
这里是该加而没加。** 判断方法：需要"允许压缩"才加 `min-width: 0`；
本来就有最小值保护的（如统计卡 `min-width: 70px`）不要碰。

### 5.5 新建页面容易漏进这份文档

四象限页是后加的，第一版上线时**仪表盘仍是 4 列、趋势图标签溢出** ——
因为这份文档的适配范围表里没有它，改动时不会想到要对照检查。

**新增页面时，除了写生成器，还要回到本文档的 §2 范围表加上一行**，
否则"已适配"这个结论会随页面增加而悄悄失效。

验证方法（用真实手机视口跑，而不是肉眼看桌面缩小版）：

```python
# Playwright: 排除可滚动容器内部的元素, 只找真正撑破容器的
pg = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
# 检查每个元素的 getBoundingClientRect().right 是否 > document.documentElement.clientWidth
```

### 5.6 弹窗必须设 `max-height` + 滚动

**这是硬性要求，不是美化。** `.modal-bg` 是 `display:flex; align-items:center; justify-content:center`
—— **垂直居中**。弹窗一旦高过视口，它就会**上下两端同时被裁**；此时若弹窗本身没有滚动，
底部那排「取消 / 确认」就彻底够不着，连滑都滑不出来。

任务清单页的「添加/编辑任务」就踩过：弹窗高 **825px**，在 720px 高的视口下，
提交按钮落在 `y 716→748`（视口外），且 `scrollHeight == clientHeight`（不可滚动）。

```css
.modal { max-height: 90vh; overflow-y: auto; }
```

**配套建议（同一页已采用）**：把底部留白从 `.modal` 的 `padding-bottom` 挪到
`.modal-actions` 自己身上，并给它 `position: sticky; bottom: 0; background: #fff` ——
这样内容高过视口时按钮行一直吸在底部，**不用先滑到底**就能点。

```css
.modal { padding: 18px 20px 0; }                 /* 底部留白交给下一行 */
.modal-actions { position: sticky; bottom: 0; background: #fff; padding: 9px 0 14px; }
```

各页现状（**改弹窗时对照一下**）：

| 页面 | `max-height` + 滚动 | 吸底按钮 |
|---|---|---|
| 任务清单 `tasks_view.html` | ✅ | ✅ |
| 四象限 `quadrant.html` | ✅（88vh）| ❌ |
| 项目索引 / 项目图 | ✅（92vh）| ❌ |
| 任务流程树 `task_flow.html` | ✅（90vh）| ❌ |

## 6. 相关文件

- `src/generators/generate_tasks_view.py`
- `src/generators/generate_task_flow.py`
- `src/generators/generate_project.py`
- `src/generators/generate_quadrant.py`
