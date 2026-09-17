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

## 页面渲染：要转义 + onclick 不要拼参数（2026-09-17）

任务名 / 备注 / 负责人 都是用户输入，可能含 `<`、`&`、引号，处理规则：

1. **插入 HTML 前用 `esc()` 转义** —— 名字里出现 `<b>` 会被浏览器当标签解析，直接破版
2. **不要把名字拼进 `onclick` 属性** —— `onclick="openAddNode('3','DBA's')"` 里的单引号会让 JS 字符串提前闭合，**按钮整个失效**。正确做法：只传编号，函数内用 `TASKS.find()` 查名字（`tasks_view` 和 `task_flow` 都踩过）
3. **`<input type="date">` 只接受 `YYYY-MM-DD`** —— 赋 `2026/09/17` 会被浏览器静默丢弃（输入框空白，控制台一条 WARNING）。提交时再 `.replace(/-/g, '/')` 转成数据格式 `YYYY/MM/DD`；编辑弹窗那侧原来是对的，新增弹窗漏了转换

## 页面弹窗：不要用原生 alert / confirm

IDE 内嵌预览会屏蔽 `window.confirm()` —— 不弹框、直接返回 `false`，表现为"点了按钮没反应"；`alert()` 同样静默失败。所有页面的确认与提示统一用自绘的 `confirmBox()` 和 `toast()`。

**现状（2026-09-15）**：`project_index.html`、`project_tree.html`、`tasks_view.html` 三个页面均已改用自绘弹窗。`tasks_view.html` 是最晚修的一个 —— 它的「一键完成」「删除任务」此前用原生 `confirm()`，所以点了完全没反应，且所有 `alert()` 报错也都看不见。**新增页面时务必沿用同一套 `toast()` / `confirmBox()`。**

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

## 隐私数据已脱离 git 管理（2026-09-14 起）

`data/`、`output/tasks/`、`output/project/` 已加入 `.gitignore` 并移出跟踪（因为含**真实姓名、体重、健身、项目信息**）。由此带来几条必须记住的注意事项：

### ① 这些文件现在是"未跟踪"状态，git 不再保护它们

- 误删**无法**用 `git checkout` 找回，只能从更早的历史提交恢复
- 建议定期手动备份到别处（网盘 / 另一块盘）

### ② 常规 pull 不会删它们（已实测）

`git restore`、`git pull --rebase` 之后文件都还在 —— 因为 git 的 pull / merge / rebase / checkout **只操作索引里已知的路径**，对未跟踪文件完全无视。

### ③ 但有三个例外

| 操作 | 后果 |
|------|------|
| 某端落后时又执行一次 `git rm --cached data/` 并推送 | 产生**新的删除提交** → 其他端 pull 时文件被删 ⚠️ |
| `git clean -fdx` | **会连被忽略的文件一起删**，`data/` 直接清空 ⚠️ 最危险 |
| `git clean -fd`（不带 `x`）、`git reset --hard`、`git checkout -f` | 安全 ✅ 不碰未跟踪文件 |

### ④ pull 前自检（两秒）

```bash
git fetch github
git diff --stat HEAD..github/master -- data/ output/tasks output/project
# 输出为空 = 安全
```

更简单的判断：`git ls-files data/` 为空 ⇒ git 已经管不着它了。

### ⑤ 万一被删，这样恢复

```bash
# 1. 从最后一个含这些文件的提交恢复
git checkout <旧commit> -- data/ output/tasks/ output/project/
# 2. 重新移出索引（保留刚恢复的文件），否则下次提交又会推上去
git rm -r --cached -q data/ output/tasks/ output/project/
```

> 陷阱的完整分析见 `docs/notes/git-multi-end-collaboration.md` 第六节。

### ⑥ 仍在同步的隐私内容（已知并接受）

- `output/dashboard/*.html` —— 含体重、健身、目标进度
- `output/screenshots/*.png` —— 含任务页面截图与姓名
