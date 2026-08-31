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
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "tasks")

# 导入 generate_task_flow 的数据函数
GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from generate_task_flow import read_tasks, read_tasks_raw, write_tasks_raw


class TaskFlowHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OUTPUT_DIR, **kwargs)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/tasks":
            tasks = read_tasks()
            self._send_json(tasks)
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
            progress = int(data.get("progress", 0))
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
            idx = int(data.get("index", -1))
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
                        node["progress"] = int(data["progress"])
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
            idx = int(data.get("index", -1))
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
            priority = data.get("priority", "medium").strip()
            category = data.get("category", "个人").strip()
            today_prog = int(data.get("today", 0))
            note = data.get("note", "").strip()

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
                           "progress": today_prog, "note": note}],
            }
            tasks.append(new_task)
            write_tasks_raw(tasks)

            self._send_json({"ok": True, "no": new_no})

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
                    nodes = item.get("nodes", [])
                    # 如果最后一个节点不是完成节点，添加一个
                    if nodes and nodes[-1].get("progress", 0) < 100:
                        nodes.append({
                            "phase": "完成",
                            "date": today_str,
                            "progress": 100,
                            "note": "一键完成",
                        })
                    elif nodes:
                        nodes[-1]["progress"] = 100
                        nodes[-1]["phase"] = nodes[-1].get("phase", "完成")
                    ok = True
                    break
            write_tasks_raw(tasks)
            self._send_json({"ok": ok})

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        print(f"[serve] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Task Flow 本地服务器")
    parser.add_argument("--port", type=int, default=8080, help="端口号 (默认 8080)")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}/task_flow.html"
    print(f"[serve] 启动服务器 http://localhost:{args.port}")
    print(f"[serve] 访问: {url}")
    print(f"[serve] Ctrl+C 停止")

    server = HTTPServer(("127.0.0.1", args.port), TaskFlowHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] 已停止")
        server.server_close()


if __name__ == "__main__":
    main()
