# serve_task_flow 公网部署方案（nginx 反代 + systemd）

> 日期：2026-08-31
> 状态：已实施 ✅

## 背景

`tasks_view.html` / `task_flow.html` 已从纯静态页面升级为**动态编辑页面**：
- 页面加载时 `fetch('/api/tasks')` 拉取最新数据
- 支持添加/删除任务、增删改节点（写 `data/task_flows.json`）
- 动态能力由 `src/utils/serve_task_flow.py` 提供（Python 标准库 HTTP 服务）

目标：在公网 `https://www.jevylee.com/tasks_view.html` 上也能点击添加/删除按钮，**直接修改 NAS 上的 `task_flows.json`**。

## 架构

```
浏览器（公网）
  │  fetch('/api/xxx')
  ▼
Cloudflare Tunnel（cloudflared 容器）
  ▼
blog-nginx 容器（:8095，hugo-blog docker compose）
  │  location /api/ → 反向代理
  ▼
宿主机 172.18.0.1:8080
  ▼
serve_task_flow.py（systemd 用户服务 task-flow.service）
  ▼
data/task_flows.json（读写）
```

## 部署步骤

### 1. serve_task_flow.py 支持 --host（默认 0.0.0.0）

`src/utils/serve_task_flow.py` 的 `main()` 增加 host 参数：

```python
parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
server = HTTPServer((args.host, args.port), TaskFlowHandler)
```

> 必须监听 0.0.0.0 而非 127.0.0.1：nginx 容器通过网关 `172.18.0.1` 访问宿主机，127.0.0.1 只监听回环、网关访问不到。

### 2. nginx.conf 加 /api/ 反向代理

`~/Hugo-blog/nginx.conf`（bind mount 进 blog-nginx 容器）：

```nginx
location /api/ {
    proxy_pass http://172.18.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 30s;
}
```

> `172.18.0.1` 是 hugo-blog_default 网络的网关（即宿主机地址）。修改后 `docker restart blog-nginx`。

### 3. systemd 用户服务（开机自启）

`~/.config/systemd/user/task-flow.service`：

```ini
[Unit]
Description=reTerminal Task Flow server (API for tasks_view/task_flow dynamic editing)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/Lijiawei/Code/reTerminal
ExecStart=/home/Lijiawei/Code/reTerminal/.venv/bin/python /home/Lijiawei/Code/reTerminal/src/utils/serve_task_flow.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

启用：

```bash
systemctl --user daemon-reload
systemctl --user enable task-flow.service
systemctl --user start task-flow.service
```

### 4. Linger（关键）

```bash
loginctl enable-linger Lijiawei
```

> 必须开启 linger，否则用户 systemd 服务只在登录会话中存在，NAS 重启后不会自动运行。
> 当前 NAS 已确认 `Linger=yes`。

## 验证

```bash
# 服务本身
curl -s http://127.0.0.1:8080/api/tasks          # 返回任务 JSON

# nginx 反代
curl -s http://127.0.0.1:8095/api/tasks           # 同上

# 公网（需浏览器 UA 绕过 CF）
curl -s -A 'Mozilla/5.0' https://www.jevylee.com/api/tasks

# 写操作（实测 add_node 返回 {"ok": true}）
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"no":"99","phase":"测试","date":"2026/08/31","progress":50}' \
  https://www.jevylee.com/api/add_node
```

## 重启自启行为

| 组件 | 机制 | 重启后 |
|---|---|---|
| task-flow | systemd 用户服务（enabled + Linger=yes）| ✅ 自动运行 |
| blog-nginx | docker `unless-stopped` | ✅ 自动运行 |
| nginx → 8080 反代 | 动态转发，不依赖启动顺序 | ✅ 自动恢复 |

## API 一览

| 接口 | 方法 | 作用 |
|---|---|---|
| `/api/tasks` | GET | 读取全部任务（含节点树）|
| `/api/add_task` | POST | 新增任务 |
| `/api/delete_task` | POST | 删除任务 |
| `/api/complete_task` | POST | 一键完成（末节点置 100%）|
| `/api/add_node` | POST | 给任务添加推进节点 |
| `/api/edit_node` | POST | 编辑节点（phase/date/progress/note/owner）|
| `/api/delete_node` | POST | 删除节点（空任务自动清理）|

## 已知限制

- 公网 API **无鉴权**（个人博客，暂不设防；如需保护可加 CF Access 门禁或 nginx token 校验）
- 页面打开时若 API 不可达，自动 fallback 到内嵌 `EMBEDDED_TASKS` 数据（只读快照）
- 编辑后需重新生成 HTML（`src/generators/generate_tasks_view.py` + `generate_task_flow.py`）才能更新博客静态页的内嵌快照；API 数据则是实时读写 task_flows.json

## 相关文件

- `src/utils/serve_task_flow.py` — HTTP 服务 + API
- `src/generators/generate_task_flow.py` — 数据读取/写入函数（read_tasks / read_tasks_raw / write_tasks_raw）
- `data/task_flows.json` — 任务流程数据（动态编辑的落盘目标）
- `~/Hugo-blog/nginx.conf` — 反向代理配置
- `~/.config/systemd/user/task-flow.service` — systemd 服务单元
