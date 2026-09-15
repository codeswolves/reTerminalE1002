# 多端协作 Git 推送规范（2026-09-14 ~ 09-15）

## 一、背景

本项目有**多个提交来源**并行工作，都会往 GitHub（`codeswolves/reTerminalE1002`）推送：

| 来源 | 推送内容 | 方式 |
|------|---------|------|
| NAS 每日 cron（00:05） | 看板刷新（PNG/CSV/JSON/页面） | `daily_dashboard_push.sh` |
| Jarvis（老板笔记本的 Hermes） | 代码修复、功能提交 | 手动 push |
| NAS 上的 Hermes（乔伊斯） | 数据更新、任务维护 | 手动 push |
| 老板本人 | 通过公网 task-flow 页面改数据 | 服务写文件，随下次提交推送 |

## 二、踩过的坑（2026-09-12 ~ 09-14）

**现象**：连续 3 天的每日看板推送失败，GitHub 上停留在 9/11 的版本。

**根因**：本地与远程**分叉**（diverged）——

```
本地:  fecd1fc(9-11) → 3521717(9-12) → cc178c0(9-13) → cf243ea(9-14)
远程:  fecd1fc(9-11) → 739612f(owner修复) → 6155687(merge)
```

Jarvis 从别处推了新提交，NAS 本地也积累了每日刷新提交；cron 脚本当时只会 `git push`，不会先拉取——于是被 GitHub 拒绝（non-fast-forward），且脚本失败后只是 exit，没有告警，问题被静默搁置了 3 天。

## 三、规范（强制）

**任何推送前，必须先 fetch + rebase：**

```bash
git add -A
git commit -m "..."
git fetch origin -q
git rebase origin/master -q    # 有冲突则停下人工处理，不要强行 push
git push origin master
```

**禁止**：在未 fetch 的情况下直接 `git push`（多端协作下必然周期性失败）。

## 四、已落实的加固

`~/.hermes/scripts/daily_dashboard_push.sh`（每日 0:05 cron）已改为：

```bash
git commit -m "chore: 每日看板刷新 $(date '+%F')" -q
git fetch origin -q
if ! git rebase origin/master -q; then
    echo "[ERR] rebase 冲突, 已中止, 请人工处理"
    git rebase --abort 2>/dev/null
    exit 1
fi
git push origin master -q
```

- 冲突时**安全中止**（`--abort`），不留半途 rebase 状态
- 日志写入 `/tmp/dashboard_daily.log`，异常时输出 `[ERR]` 行

## 五、排查清单（推送失败时）

1. `git status -sb` → 看是否有 `[ahead N]` / `[behind N]`（分叉信号）
2. `git log --oneline --graph --all -10` → 确认分叉点
3. `tail -30 /tmp/dashboard_daily.log` → 看 cron 是否报了 `[ERR]`
4. 修复：`git pull --rebase origin master` → 解决冲突（如有）→ `git push`

## 六、`rm --cached` 类提交的跨仓库陷阱（2026-09-15 实际踩到）

**现象**：本地执行 `git pull --rebase` 同步"停止跟踪 `data/`"的提交后，`data/`、`output/tasks/`、`output/project/` 下的**工作区文件全部消失**。

**根因**：`--cached` 只对**执行该操作的那台机器**生效。

| 场景 | 工作区文件 |
|------|-----------|
| 在 A 机器执行 `git rm --cached data/` | A 的文件**保留**（只从索引移除） |
| B 机器 pull 这个提交 | B 的文件**被删除**（git 认为 HEAD 里已无此文件） |

也就是说，"停止跟踪"对**其他仓库**而言等同于一个**删除提交**，只是恰好被 `.gitignore` 挡在后续提交之外。

**恢复方法**（文件仍在历史里，可以救回来）：

```bash
# 1. 从最后一个包含这些文件的提交恢复工作区
git checkout <旧commit> -- data/ output/tasks/ output/project/

# 2. 重新移出索引（保留刚恢复的文件），避免下次提交又推上去
git rm -r --cached -q data/ output/tasks/ output/project/

git status -sb      # 应干净, 且文件都还在
```

**预防**：

- 其他端收到"停止跟踪某目录"的通知后，**pull 之前先手动备份该目录**
- 或者 pull 完立刻用上面的方法恢复
- 推送方应在 commit message 里写明目标路径，便于其他端判断是否需要先备份

**约定**：以后做"停止跟踪"，推送方的 commit message 需标注
`[BREAKING] 其他端 pull 前请备份 <路径>`。

### 附：本仓库的隐私同步策略（2026-09-14 起）

`data/`、`output/tasks/`、`output/project/` 已加入 `.gitignore` 并移出跟踪，原因是这些内容含**真实姓名、体重、健身、项目信息**。各端同步时注意：

- 本地数据文件是**唯一副本**，git 不再保护它们，建议定期另行备份
- `output/dashboard/` 与 `output/screenshots/` **仍在同步**（含体重等数据，已知并接受）
