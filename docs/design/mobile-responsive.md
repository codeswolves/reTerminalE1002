# 移动端适配 — 设计文档

## 1. 背景

四个交互页面（任务清单、任务流程树、项目索引、项目图）最初只针对桌面浏览器设计，
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
| 仪表盘 `dashboard.html` | `generate_dashboard.py` | ❌ 墨水屏固定 800×480 |

仪表盘的 `.dash` 是硬编码的 `width: 800px; height: 480px`，输出目标就是 E1002
墨水屏的物理分辨率，**不做响应式** —— 改了反而会破坏截图与推送流程。

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

## 6. 相关文件

- `src/generators/generate_tasks_view.py`
- `src/generators/generate_task_flow.py`
- `src/generators/generate_project.py`
