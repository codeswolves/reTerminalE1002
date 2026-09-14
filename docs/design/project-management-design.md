# 项目管理模块 — 设计文档

> 日期：2026-09-14
> 状态：已实施 ✅
> 相关文件：`src/generators/generate_project.py`、`src/utils/serve_task_flow.py`、`data/projects.json`

## 1. 目标

在仪表盘之外提供一个**多项目管理**的可视化界面：从项目起点到过程中的里程碑，用一张**从左到右的有向图**展示进度与依赖关系，并支持在页面上直接增删改节点、连线、调整项目信息。

核心诉求演进：

1. 最初是「树状拓扑」——每个节点只能有一个上级
2. 实际使用中需要**多路汇聚**（多个模块的成果汇总到一个节点），树结构无法表达
3. 最终重构为 **DAG（有向无环图）**——一个节点可以有任意多个上游

## 2. 数据模型

### 2.1 存储格式（`data/projects.json`）

每个项目由**节点表 + 边表**组成，不再是嵌套的 `children` 树：

```json
{
  "meta": { "updated": "2026/09/14", "note": "..." },
  "projects": [
    {
      "id": "P02",
      "name": "天地承载网规划优化工具",
      "category": "工程",
      "owner": "李佳伟",
      "priority": "high",
      "start": "2026/09/14",
      "target": "2026/11/30",
      "goal": "集成已有成果，形成演示demo",
      "root": "P02",
      "nodes": [
        {
          "id": "P02",
          "name": "2026天地承载网规划优化工具",
          "kind": "project",
          "owner": "李佳伟",
          "plan": "2026/11/30",
          "actual": "",
          "note": "",
          "tasks": [],
          "progress": 80
        }
      ],
      "edges": [
        { "from": "P02-C2-C1", "to": "P02-C2-C4" },
        { "from": "P02-C2-C2", "to": "P02-C2-C4" }
      ]
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `root` | **字符串**，根节点的 id（不是嵌套对象） |
| `nodes[]` | 全部节点的扁平列表 |
| `edges[]` | `{from, to}` 列表，一条边 = 一次"上游 → 下游"的依赖 |
| `progress` | 节点上的**手工进度**，可选；不填则由下游/任务汇总 |
| `tasks` | 关联的任务编号，引用 `data/task_flows.json` 的 `no`，可选 |

**一个节点有几条入边就有几个上级。** 想让三个模块汇聚到同一个节点，就是三条指向它的边。

### 2.2 节点类型（`kind`）

| 值 | 显示 | 颜色 | 说明 |
|----|------|------|------|
| `project` | 项目 | `#3b6fb0` | 根节点专属，不可修改 |
| `milestone` | 里程碑 | `#d29922` | |
| `task` | 任务 | `#7c6bc4` | |
| `deliverable` | 交付物 | `#2e9e5b` | |
| `end` | 结束 | `#d6453d` | 项目的终点，布局上强制排最后一列 |

### 2.3 旧格式自动迁移

早期版本是嵌套树（`root` 为对象、子节点在 `children` 数组里）。`read_projects_raw()` 读取时会检测并**在内存中自动迁移**，写回时落成新格式：

```python
def migrate_project(proj):
    root = proj.get("root")
    if not isinstance(root, dict):
        return proj               # 已是新格式
    nodes, edges = [], []
    def walk(n, parent_id=None):
        nd = {k: v for k, v in n.items() if k != "children"}
        nodes.append(nd)
        if parent_id is not None:
            edges.append({"from": parent_id, "to": nd["id"]})
        for c in (n.get("children") or []):
            walk(c, nd["id"])
    walk(root)
    proj["nodes"], proj["edges"], proj["root"] = nodes, edges, str(root["id"])
    return proj
```

**旧数据零手工迁移**，`progress`、`tasks`、日期全部保留。迁移已完成并验证，早期的树格式备份文件也已清理。

## 3. 派生计算

### 3.1 进度优先级

`build_graph()` 按以下顺序取第一个命中的值：

```
完成日期(actual)  >  手工填写(progress)  >  关联任务平均  >  下游节点平均  >  0
```

- **完成日期**：填了 `actual` 即视为 100%
- **手工填写**：优先级高于下游汇总 —— 这是关键规则。否则给一个 80% 的节点挂上新子节点（0%）后，父节点会被平均成 0%。详见 §7.1
- **下游平均**：只在没有 `actual` 和手工进度时生效，即"父节点进度由子节点汇总"

### 3.2 状态与延期

| 状态 | 条件 |
|------|------|
| 已完成 | `progress >= 100` |
| 进行中 | `0 < progress < 100` |
| 未开始 | `progress == 0` |

`delayed = 状态 != 已完成 且 plan < 今天`。

日期解析（`parse_date`）对非法值（如 `2026/09/31`）返回 `None` 而不是抛异常——否则一个脏日期会打挂整个 `/api/projects` 接口。

### 3.3 环路保护

`link` 建边前做可达性检测：如果 `to` 已经能到达 `from`，加这条边会成环，直接拒绝。`build_graph()` 里另有 `visiting` 集合兜底，防止意外数据导致递归死循环。

## 4. 布局算法（分层 DAG）

前端 `renderTree()` 用两趟计算坐标：

**第一趟 — x 坐标（分层）**：按从 root 出发的**最长路径深度**

```js
function calc(id, seen){
  const ps = pred[id] || [];
  if (!ps.length || seen.has(id)) { level[id] = 0; return 0; }
  let v = 0;
  ps.forEach(p => { v = Math.max(v, calc(p, seen) + 1); });
  level[id] = v;
  return v;
}
// 结束节点强制排在最后一列（若它自己还有下游则不强制）
```

**第二趟 — y 坐标（层内排布）**：先对齐到上游节点的平均位置，再向下消除重叠

```js
arr.forEach(n => { yMap[n.id] = upY(n); });           // 汇聚节点落在上游中间
for (let i = 1; i < arr.length; i++){                 // 避免同层重叠
  if (yMap[arr[i].id] - yMap[arr[i-1].id] < ROW_H)
    yMap[arr[i].id] = yMap[arr[i-1].id] + ROW_H;
}
```

上游平均定位让汇聚节点自然居中（实测三个上游在 `y=188/336/484` 时，汇聚节点落在 `336`）。

## 5. 页面

### 5.1 项目索引（`output/project/project_index.html`）

- 卡片网格，显示分类 / 优先级 / 整体进度 / 节点完成数 / 负责人 / 目标日期
- 右上角 **✏️** 修改项目信息（名称、分类、优先级、负责人、周期、目标）
- 右上角 **勾选框** + 顶部「删除选中项目」批量删除
- 顶部「＋ 新建项目」

### 5.2 项目图（`output/project/project_tree.html`）

- 从左到右的有向图，节点卡片 + 贝塞尔曲线连线
- 节点悬停出现 5 个操作按钮：`＋` 加子节点 / `🔗` 连线 / `✏️` 编辑 / `✅` 完成 / `🗑️` 删除
- 卡片上 `↑n` / `↓n` 显示上游 / 下游数量，便于识别汇聚点
- 缩放、节点类型下拉（不含 `project`，编辑根节点时临时补上并锁定）

## 6. REST API

由 `src/utils/serve_task_flow.py` 提供：

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/projects` | GET | 全部项目（含 DAG 节点、边与派生字段） |
| `/api/project/add` | POST | 新建项目（自动生成 id + 根节点） |
| `/api/project/edit` | POST | 修改项目信息（同步根节点名称/负责人/目标日期） |
| `/api/project/delete` | POST | 删除项目（支持批量，传 `ids` 数组） |
| `/api/pnode/add` | POST | 新增节点并建立 `parent → 新节点` 的边 |
| `/api/pnode/edit` | POST | 修改节点属性 |
| `/api/pnode/delete` | POST | 删除节点及关联边，并清理失去连通的专属下游 |
| `/api/pnode/link` | POST | 建立额外上游边（多路汇聚），带环路检测 |
| `/api/pnode/unlink` | POST | 断开一条边（仅剩一个上游时拒绝） |
| `/api/pnode/done` | POST | 标记 / 取消完成 |

### 6.1 删除语义（DAG 特化）

删除节点时，先移除该节点与所有相关边，然后**从 root 重新做可达性分析**：

- 被其它上游连着的节点 → **保留**
- 只靠被删节点连通的下游 → **一起清理**（符合"删子树"的直觉）

### 6.2 项目名与根节点名

项目名和树上的根节点名是**两个字段**。`update_project()` 的同步规则：

- 根节点名 == 旧项目名 → 跟随项目名一起改
- 根节点名被单独改过（如加了"2026"前缀）→ **保留**，不覆盖

## 7. 已知坑与约定

### 7.1 手工进度必须高于下游汇总

第一版把优先级定成「完成日期 → 关联任务 → 子节点 → 手工进度」，导致：给一个 80% 的节点加了个 0% 的子节点，父节点被平均成 0%。**手工进度是被显式设置的意图，必须优先**。

### 7.2 Python 模板里的 `\n` 会变成真实换行

`generate_project.py` 用 Python 三引号字符串承载 HTML/JS。写 `alert('a\nb')` 时，`\n` 会被 Python 解释成换行符，生成的 JS 字符串被截断 → 整个脚本 `Invalid or unexpected token` 不执行。**模板里的 JS 不要用反斜杠转义**，需要换行就用 `String.fromCharCode(10)` 或干脆避免。

同理，JS 正则里的 `\d` 会触发 Python `SyntaxWarning`，改用 `[0-9]`。

### 7.3 原生 `alert()` / `confirm()` 会被内嵌预览屏蔽

在 IDE 的内嵌浏览器里 `window.confirm()` 直接返回 `false` 且不弹框，表现为"点删除没反应"；`alert()` 同样静默失败。所以页面统一用**自绘的确认框（`confirmBox`）和提示条（`toast`）**，不依赖原生弹窗。

### 7.4 一条脏数据能打挂整个接口

`parse_date()` 必须容错。曾经因为一个 `2026/09/31` 让 `/api/projects` 抛 `ValueError` 返回空响应，前端 fetch 失败后静默回退到生成页面时的旧快照，表现成"添加的节点没出现"。

### 7.5 分类/优先级枚举必须来自单一来源（已重构）

历史上分类枚举（科研/工程/标准/专利/个人/管理）和优先级配色在 **4 个文件里各写一份**，结果流程页的 `CATEGORY_ORDER` 漏了 `"管理"`，而项目页的 `CAT_COLOR` 有 —— 同一条任务在两个页面一个显示、一个消失，且**不报任何错**。

现已统一到 `src/generators/meta.py`，并改成"不依赖白名单渲染"：

| 措施 | 说明 |
|------|------|
| 单一来源 | `CATEGORY_ORDER` / `CATEGORY_ICON` / `CATEGORY_COLOR` / `PRIORITY_META` / `STATUS_META` / `KIND_META` 只在 `meta.py` 定义 |
| 注入而非手写 | 生成器用 `meta.js()` 把常量注入 `<script>`，下拉选项用 Python 循环生成 |
| 动态收集 | `collect_categories()` 从数据里收集实际出现的分类；前端 `render()` 也有一层兜底 —— 数据里出现新分类**不会**再被白名单漏掉 |
| 顺序可控 | `order_categories()` 让预设分类按固定顺序排，未预设的追加到末尾 |

**约定：以后新增分类只需改 `meta.py` 一处。**

## 8. 相关文件

```
data/projects.json                     # 项目数据（DAG 格式）
output/project/project_index.html      # 项目索引页
output/project/project_tree.html       # 项目图页面
src/generators/generate_project.py     # 数据层 + 模板 + 生成逻辑
src/utils/serve_task_flow.py           # HTTP 服务（路由 /project/、/api/project*、/api/pnode*）
```
