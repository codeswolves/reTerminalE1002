# 项目约定记忆

## 健身打卡日历图例位置

- 页面元素：`output/dashboard/dashboard.html` 中"今天、已打卡"图例（`.cal-legend`）
- 当前参数：`margin-top: 4px`
- **约定**：用户说"上移'今天、已打卡'图例"时，直接**缩小** `margin-top: 4px` 这个值；用户说"下移"时，**增大**该值。

## 健身打卡日历头部间距

- `.cal-header` 的 `margin-bottom`：当前 `2px`
- `.cal-grid.wk` 的 `margin-bottom`：当前 `2px`
- 这两处控制"健身打卡"标题行与星期行（一 二 三…）之间的间距；用户说"调整标题和星期行间距"时改这两个值。

## 通用注意

- 修改以上样式后，需同步到生成脚本 `src/generators/generate_dashboard.py` 中对应的样式，避免重新生成页面时被覆盖。

## Python f-string 中 JS 引号转义规则

**错误模式（犯了两次）：** 在 f-string 模板中嵌入 JS 代码时，`onclick="func(\'' + var + '\')"` 中的 `\'` 在 f-string 中只输出 `'`（因为 `\'` 就是转义的单引号，等于 `'`），导致生成的 JS 变成 `func('' + var + '')`，引号被吞掉，产生语法错误。

**正确做法：** 使用 `\\'` 输出 `\'`。在 f-string 中：
- `\'` → 输出 `'`（只是转义引号，不是两个字符）
- `\\'` → 输出 `\'`（反斜杠 + 引号，JS 中识别为转义引号）

**示例：**
```python
# 错误：\' 在 f-string 中只输出 '，JS 变成 func('' + t.no + '')
f"onclick=\"func(\'' + t.no + '\')\"" 

# 正确：\\' 输出 \', JS 正确识别为 func(\'5\')
f"onclick=\"func(\\'' + t.no + '\\')\""
```

**教训：** 在 Python f-string 中生成 JS 字符串拼接时，始终用 `\\'` 而不是 `\'`。

## Python 三引号模板中的反斜杠（同一类坑，犯过一次）

`generate_project.py` 用 Python 三引号字符串承载 HTML/JS。写 `alert('a\nb')` 时 `\n` 会被 Python 解释成**真实换行**，生成的 JS 字符串被截断，整个脚本报 `Invalid or unexpected token` 直接不执行。

- 模板里的 JS 尽量**不要用反斜杠转义**；确实要换行就避免，或改用 `String.fromCharCode(10)`
- JS 正则里的 `\d` 会触发 Python `SyntaxWarning`，改用 `[0-9]`

## 页面弹窗：不要用原生 alert / confirm

IDE 内嵌预览会屏蔽 `window.confirm()` —— 不弹框、直接返回 `false`，表现为"点了按钮没反应"；`alert()` 同样静默失败。所有页面的确认与提示统一用自绘的 `confirmBox()` 和 `toast()`。

## 项目数据是 DAG，不是树

`data/projects.json` 用的是 **`nodes` 节点表 + `edges` 边表**（一个节点可以有多个上游），不是嵌套的 `children` 树。改代码时不要按树递归写；旧的树格式会在 `migrate_project()` 里自动迁移。详见 `docs/design/project-management-design.md`。

## 分类 / 优先级枚举只有一份（`src/generators/meta.py`）

所有分类、优先级、任务状态、项目节点类型的定义都在 `src/generators/meta.py`，**不要在各生成器里另写一份**。

历史问题：同一份分类清单曾在 4 个文件里各写一份，结果流程页的 `CATEGORY_ORDER` 漏了 `"管理"`，那条分类的任务在流程页整个消失（项目页却正常），并且**不报任何错**。

约定：

- 新增分类 / 改配色 → **只改 `meta.py`**
- 页面里需要这些常量时用 `meta.js(xxx)` 注入，不要手写 JS 字面量
- 下拉选项用 Python 循环生成，不要手写 `<option>`
- 渲染分组优先"从数据动态收集分类"，白名单只用来决定展示顺序

## 日期解析必须容错

`parse_date()` 遇到 `2026/09/31` 这类不存在的日期必须返回 `None` 而不是抛异常 —— 一个脏日期会让 `/api/projects` 或 `/api/tasks` 整个接口返回空响应，前端 fetch 失败后静默回退到生成页面时的旧快照，表现成"改的东西没生效"。这个坑已踩过两次（`generate_project.py`、`generate_task_flow.py`）。
