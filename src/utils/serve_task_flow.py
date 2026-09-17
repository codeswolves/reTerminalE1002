"""
serve_task_flow.py
本地 HTTP 服务器，提供 task_flow.html 静态文件 + 节点增删改 API。

用法:
    python src/utils/serve_task_flow.py          # 默认端口 8080
    python src/utils/serve_task_flow.py --port 9000
"""

import argparse
import json
import os
import sys
from datetime import date
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
PROJECT_DIR = os.path.join(BASE_DIR, "output", "project")

# 导入 generate_task_flow 的数据函数
GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from generate_task_flow import read_tasks, read_tasks_raw, write_tasks_raw  # noqa: E402
from meta import DEFAULT_CATEGORY, DEFAULT_PRIORITY  # noqa: E402
from generate_project import (  # noqa: E402
    build_projects,
    add_project as proj_add,
    update_project as proj_update,
    delete_project as proj_delete,
    add_node as pnode_add,
    edit_node as pnode_edit,
    delete_node as pnode_delete,
    set_done as pnode_done,
    link_node as pnode_link,
    unlink_node as pnode_unlink,
)


class TaskFlowHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OUTPUT_DIR, **kwargs)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body(self):
        """读取并解析 JSON 请求体; 非法请求返回空 dict, 避免抛异常中断连接。"""
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0 or length > 8 * 1024 * 1024:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _safe_project_path(self, rel):
        """把 /project/xxx 映射到 PROJECT_DIR 内, 阻止 ../ 目录穿越; 越界返回空串。"""
        root = os.path.realpath(PROJECT_DIR)
        target = os.path.realpath(os.path.join(root, rel))
        if target != root and not target.startswith(root + os.sep):
            return ""
        return target

    @staticmethod
    def _to_int(value, default):
        """宽松转 int: 非法或缺失时返回 default, 避免请求参数错误打断连接。"""
        try:
            return int(round(float(str(value).strip())))
        except (TypeError, ValueError):
            return default

    def _send_file(self, file_path):
        """发送本地静态文件（用于 output/project 下的页面）。"""
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        ext = os.path.splitext(file_path)[1].lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
        }.get(ext, "application/octet-stream")
        with open(file_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/tasks":
            self._send_json(read_tasks())
        elif path == "/api/projects":
            self._send_json(build_projects())
        elif path.startswith("/project/"):
            rel = unquote(path[len("/project/"):]) or "project_index.html"
            self._send_file(self._safe_project_path(rel))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/add_node":
            data = self._read_body()
            task_no = data.get("no", "")
            phase = data.get("phase", "推进")
            date_val = data.get("date", "")
            progress = max(0, min(100, self._to_int(data.get("progress", 0), 0)))
            note = data.get("note", "")
            owner = data.get("owner", "")

            tasks = read_tasks_raw()
            found = False
            for item in tasks:
                if item.get("no") == task_no:
                    item["nodes"].append({
                        "phase": phase, "date": date_val,
                        "progress": progress, "note": note, "owner": owner,
                    })
                    found = True
                    break
            if not found:
                tasks.append({
                    "no": task_no, "name": "", "date": date_val,
                    "priority": "medium", "category": "个人",
                    "nodes": [{"phase": phase, "date": date_val,
                               "progress": progress, "note": note, "owner": owner}],
                })
            write_tasks_raw(tasks)
            self._send_json({"ok": True})

        elif path == "/api/edit_node":
            data = self._read_body()
            task_no = data.get("no", "")
            idx = self._to_int(data.get("index", -1), -1)
            tasks = read_tasks_raw()
            ok = False
            for item in tasks:
                if item.get("no") == task_no and 0 <= idx < len(item.get("nodes", [])):
                    node = item["nodes"][idx]
                    if "phase" in data:
                        node["phase"] = data["phase"]
                    if "date" in data:
                        node["date"] = data["date"]
                    if "progress" in data:
                        node["progress"] = max(0, min(100, self._to_int(
                            data["progress"], node.get("progress", 0))))
                    if "note" in data:
                        node["note"] = data["note"]
                    if "owner" in data:
                        node["owner"] = data["owner"]
                    ok = True
                    break
            write_tasks_raw(tasks)
            self._send_json({"ok": ok})

        elif path == "/api/delete_node":
            data = self._read_body()
            task_no = data.get("no", "")
            idx = self._to_int(data.get("index", -1), -1)
            tasks = read_tasks_raw()
            ok = False
            for item in tasks:
                if item.get("no") == task_no and 0 <= idx < len(item.get("nodes", [])):
                    item["nodes"].pop(idx)
                    ok = True
                    break
            tasks = [item for item in tasks if item.get("nodes")]
            write_tasks_raw(tasks)
            self._send_json({"ok": ok})

        elif path == "/api/add_task":
            data = self._read_body()
            task_name = data.get("name", "").strip()
            priority = data.get("priority", DEFAULT_PRIORITY).strip()
            category = data.get("category", DEFAULT_CATEGORY).strip()
            today_prog = max(0, min(100, self._to_int(data.get("today", 0), 0)))
            note = data.get("note", "").strip()
            owner = data.get("owner", "").strip()

            if not task_name:
                self._send_json({"ok": False, "error": "任务名不能为空"})
                return

            tasks = read_tasks_raw()
            max_no = 0
            for t in tasks:
                try:
                    n = int(str(t.get("no", "0")))
                    if n > max_no:
                        max_no = n
                except (ValueError, TypeError):
                    pass
            new_no = str(max_no + 1)
            today_str = date.today().strftime("%Y/%m/%d")

            new_task = {
                "no": new_no,
                "name": task_name,
                "date": today_str,
                "priority": priority,
                "category": category,
                "nodes": [{"phase": "创建", "date": today_str,
                           "progress": today_prog, "note": note, "owner": owner}],
            }
            tasks.append(new_task)
            write_tasks_raw(tasks)

            self._send_json({"ok": True, "no": new_no})

        elif path == "/api/edit_task":
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            if not task_no:
                self._send_json({"ok": False, "error": "缺少任务编号"})
                return

            tasks = read_tasks_raw()
            target = None
            for item in tasks:
                if str(item.get("no", "")) == task_no:
                    target = item
                    break
            if target is None:
                self._send_json({"ok": False, "error": f"任务 No.{task_no} 不存在"})
                return

            if "name" in data:
                name = str(data.get("name") or "").strip()
                if not name:
                    self._send_json({"ok": False, "error": "任务名不能为空"})
                    return
                target["name"] = name
            if "priority" in data:
                target["priority"] = str(data.get("priority") or DEFAULT_PRIORITY).strip()
            if "category" in data:
                target["category"] = str(data.get("category") or DEFAULT_CATEGORY).strip()

            nodes = target.setdefault("nodes", [])
            if not nodes:
                # 兜底: 老数据可能没有节点, 补一个创建节点来承载进度
                nodes.append({"phase": "创建", "date": target.get("date", ""), "progress": 0})
            # 进度存在最后一个节点上(任务进度 = 最后节点进度, 100% 即视为完成)
            if "today" in data:
                cur = self._to_int(nodes[-1].get("progress", 0), 0)
                nodes[-1]["progress"] = max(0, min(100, self._to_int(data.get("today"), cur)))
            # 责任人 / 备注存在创建节点上(与新增任务时的落点保持一致)
            if "owner" in data:
                nodes[0]["owner"] = str(data.get("owner") or "").strip()
            if "note" in data:
                nodes[0]["note"] = str(data.get("note") or "").strip()

            write_tasks_raw(tasks)
            self._send_json({"ok": True, "no": task_no})

        elif path == "/api/pin_task":
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            if not task_no:
                self._send_json({"ok": False, "error": "缺少任务编号"})
                return
            pinned = bool(data.get("pinned", True))

            tasks = read_tasks_raw()
            ok = False
            for item in tasks:
                if str(item.get("no", "")) == task_no:
                    if pinned:
                        item["pinned"] = True
                    else:
                        # 取消置顶时移除字段, 保持 JSON 干净
                        item.pop("pinned", None)
                    ok = True
                    break
            if not ok:
                self._send_json({"ok": False, "error": f"任务 No.{task_no} 不存在"})
                return
            write_tasks_raw(tasks)
            self._send_json({"ok": True, "no": task_no, "pinned": pinned})

        elif path == "/api/delete_task":
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            if not task_no:
                self._send_json({"ok": False, "error": "缺少任务编号"})
                return

            tasks = read_tasks_raw()
            tasks = [t for t in tasks if str(t.get("no", "")) != task_no]
            write_tasks_raw(tasks)

            self._send_json({"ok": True})

        elif path == "/api/complete_task":
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            if not task_no:
                self._send_json({"ok": False, "error": "缺少任务编号"})
                return

            tasks = read_tasks_raw()
            today_str = date.today().strftime("%Y/%m/%d")
            ok = False
            for item in tasks:
                if str(item.get("no", "")) == task_no:
                    nodes = item.setdefault("nodes", [])
                    last = nodes[-1] if nodes else None
                    if last is None or last.get("phase") != "完成":
                        # 末节点不是完成节点(无论当前进度多少), 追加一个完成节点
                        nodes.append({
                            "phase": "完成",
                            "date": today_str,
                            "progress": 100,
                            "note": "一键完成",
                        })
                    else:
                        # 已有完成节点, 确保为 100% 并刷新完成日期
                        last["progress"] = 100
                        last["date"] = today_str
                    ok = True
                    break
            write_tasks_raw(tasks)
            self._send_json({"ok": ok})

        elif path == "/api/project/add":
            data = self._read_body()
            new_id, err = proj_add(data)
            if err:
                self._send_json({"ok": False, "error": err})
            else:
                self._send_json({"ok": True, "id": new_id})

        elif path == "/api/project/edit":
            data = self._read_body()
            pid, err = proj_update(data)
            if err:
                self._send_json({"ok": False, "error": err})
            else:
                self._send_json({"ok": True, "id": pid})

        elif path == "/api/project/delete":
            data = self._read_body()
            removed, err = proj_delete(data.get("ids", []))
            if err:
                self._send_json({"ok": False, "error": err})
            else:
                self._send_json({"ok": True, "removed": removed})

        elif path == "/api/pnode/add":
            data = self._read_body()
            new_id, err = pnode_add(data.get("project"), data.get("parent"), data.get("node", {}))
            if err:
                self._send_json({"ok": False, "error": err})
            else:
                self._send_json({"ok": True, "id": new_id})

        elif path == "/api/pnode/edit":
            data = self._read_body()
            ok, err = pnode_edit(data.get("project"), data.get("id"), data.get("node", {}))
            self._send_json({"ok": True} if ok else {"ok": False, "error": err})

        elif path == "/api/pnode/delete":
            data = self._read_body()
            ok, err = pnode_delete(data.get("project"), data.get("id"))
            self._send_json({"ok": True} if ok else {"ok": False, "error": err})

        elif path == "/api/pnode/link":
            data = self._read_body()
            ok, err = pnode_link(data.get("project"), data.get("from"), data.get("to"))
            self._send_json({"ok": True} if ok else {"ok": False, "error": err})

        elif path == "/api/pnode/unlink":
            data = self._read_body()
            ok, err = pnode_unlink(data.get("project"), data.get("from"), data.get("to"))
            self._send_json({"ok": True} if ok else {"ok": False, "error": err})

        elif path == "/api/pnode/done":
            data = self._read_body()
            ok, err = pnode_done(data.get("project"), data.get("id"), bool(data.get("done", True)))
            self._send_json({"ok": True} if ok else {"ok": False, "error": err})

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        print(f"[serve] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Task Flow 本地服务器")
    parser.add_argument("--port", type=int, default=8080, help="端口号 (默认 8080)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}/task_flow.html"
    print(f"[serve] 启动服务器 http://{args.host}:{args.port}")
    print(f"[serve] 访问: {url}")
    print(f"[serve] Ctrl+C 停止")

    # 多线程: 避免浏览器 keep-alive 连接占满导致后续请求全部挂起
    server = ThreadingHTTPServer((args.host, args.port), TaskFlowHandler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] 已停止")
        server.server_close()


if __name__ == "__main__":
    main()