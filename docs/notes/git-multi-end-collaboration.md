# 多端协作 Git 推送规范（2026-09-14）

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
