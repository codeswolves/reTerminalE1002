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
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
PROJECT_DIR = os.path.join(BASE_DIR, "output", "project")

# 项目页面文件名: 公网博客是把它们平铺在站点根目录(/project_index.html),
# 本地则放在 output/project/ 下。两种写法都支持, 页面里的相对链接才能通用。
PROJECT_PAGES = ("project_index.html", "project_tree.html")

# 导入 generate_task_flow 的数据函数
GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from generate_task_flow import (  # noqa: E402
    _to_hours,
    parse_date,
    read_tasks,
    read_tasks_raw,
    set_task_field,
    write_tasks_raw,
)
from meta import (  # noqa: E402
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    DELIVERABLE_META,
    is_quadrant,
)
from week_plan import (  # noqa: E402
    clean_slots,
    read_week_plan,
    week_start_of,
    write_week_buffer,
    write_week_plan,
    write_week_review,
)
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

    def _set_hours(self, data, key):
        """写入工时字段(estimate_h / actual_h)。

        空白或 <= 0 一律视为"取消填写"并删除字段 —— 不能按 0 存进去,
        否则会把"没估算"伪装成"不需要时间"(设计文档 §7.3)。
        返回 (ok, error, hours)。
        """
        task_no = str(data.get("no", "")).strip()
        if not task_no:
            return False, "缺少任务编号", None
        raw = data.get(key)
        hours = None
        if raw is not None and str(raw).strip() != "":
            try:
                hours = float(str(raw).strip())
            except (TypeError, ValueError):
                return False, f"{key} 不是合法数字", None
            hours = round(hours, 2) if hours > 0 else None
        ok, err = set_task_field(task_no, key, hours)
        return ok, err, hours

    @staticmethod
    def _clean_blockers(raw):
        """清洗卡点数组: 丢弃非 dict 或缺类型的项, 字段统一转字符串。"""
        out = []
        if isinstance(raw, list):
            for b in raw:
                if not isinstance(b, dict) or not str(b.get("type") or "").strip():
                    continue
                out.append({
                    "type": str(b.get("type")).strip(),
                    "from": str(b.get("from") or "").strip(),
                    "to": str(b.get("to") or "").strip(),
                    "note": str(b.get("note") or "").strip(),
                })
        return out

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
        elif path == "/api/week_plan":
            # ?week=YYYY/MM/DD 可查指定周(页面翻看上一周/下一周); 缺省为本周
            week = (parse_qs(parsed.query).get("week") or [""])[0]
            self._send_json(read_week_plan(week))
        elif path == "/api/projects":
            self._send_json(build_projects())
        elif path.startswith("/project/"):
            rel = unquote(path[len("/project/"):]) or "project_index.html"
            self._send_file(self._safe_project_path(rel))
        elif path.lstrip("/") in PROJECT_PAGES:
            # 兼容博客的平铺部署路径: /project_index.html -> output/project/project_index.html
            self._send_file(self._safe_project_path(path.lstrip("/")))
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
            quadrant = str(data.get("quadrant") or "").strip().upper()
            if quadrant and not is_quadrant(quadrant):
                self._send_json({"ok": False, "error": f"非法象限: {quadrant}"})
                return
            today_prog = max(0, min(100, self._to_int(data.get("today", 0), 0)))
            note = data.get("note", "").strip()
            owner = data.get("owner", "").strip()
            # 预期成果类型(可空); 非法取值直接拒绝, 不静默丢弃用户的输入
            deliverable = str(data.get("deliverable") or "").strip()
            if deliverable and deliverable not in DELIVERABLE_META:
                self._send_json({"ok": False, "error": f"非法成果类型: {deliverable}"})
                return

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
            # 未归类时不写该字段(与"取消归类 = 删除字段"保持一致)
            if quadrant:
                new_task["quadrant"] = quadrant
            # 工时: 空或 0 = 不写字段 —— "未估算"是合法状态, 不能按 0 计入统计(§7.3)
            for key in ("estimate_h", "actual_h"):
                h = _to_hours(data.get(key))
                if h is not None:
                    new_task[key] = h
            # 预期成果: 空 = 事务性任务(无产出), 也是合法状态, 同样不写字段
            if deliverable:
                new_task["deliverable"] = deliverable
            tasks.append(new_task)
            write_tasks_raw(tasks)

            self._send_json({"ok": True, "no": new_no})

        elif path == "/api/add_temp_task":
            """记一笔临时(突发)任务: 建任务 + 排进周表时段, 一次写完。

            为什么要放在服务端一次完成, 而不是让前端先 add_task 再存周计划:
            两步之间存在"任务建了但时段没排上"的窗口 —— 而时段块要靠 no 回任务里
            取名称(slotHtml 找不到任务就整块不渲染), 留下一笔看不见的脏数据。
            两份文件各有各的锁, 这里也做不到一个事务, 所以第二步失败时明确回报
            "任务已建、时段没排上", 而不是笼统说失败。
            """
            data = self._read_body()
            name = str(data.get("name") or "").strip()
            if not name:
                self._send_json({"ok": False, "error": "请填写这件事是什么"})
                return

            sel = str(data.get("date") or "").strip() or date.today().strftime("%Y/%m/%d")
            sel_d = parse_date(sel)
            if not sel_d:
                self._send_json({"ok": False, "error": f"日期格式不对: {sel}"})
                return

            # 先自己判"结束晚于开始", 再交给 clean_slots 做夹取与半小时对齐。
            # 不能只靠 clean_slots: 它会把 20:00→05:00 这种倒置区间静默"修正"成
            # 20:00→20:30, 用户看到的是保存成功却排在了别的时间。
            try:
                h_from = float(data.get("from"))
                h_to = float(data.get("to"))
            except (TypeError, ValueError):
                self._send_json({"ok": False, "error": "时间不合法"})
                return
            if h_to <= h_from:
                self._send_json({"ok": False, "error": "结束时间要晚于开始时间"})
                return

            week = week_start_of(sel_d)
            span = clean_slots([{"no": "0", "day": 1, "from": h_from, "to": h_to}])
            if not span:
                self._send_json({"ok": False, "error": "时间不合法"})
                return
            slot = span[0]

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
                "name": name,
                "date": today_str,
                "priority": DEFAULT_PRIORITY,
                "category": str(data.get("category") or DEFAULT_CATEGORY).strip(),
                # 标记: 只做时间记录, 不进待办池(不参与象限诊断与完成类统计)
                "temp": True,
                # 估时 = 这段时长本身。"花了/要花 N 小时"就是它的全部工作量语义
                "estimate_h": round(float(slot["to"]) - float(slot["from"]), 2),
                "nodes": [{"phase": "临时", "date": sel, "progress": 0,
                           "note": str(data.get("note") or "").strip(), "owner": ""}],
            }
            tasks.append(new_task)
            write_tasks_raw(tasks)

            try:
                plan = read_week_plan(sel)
                saved = write_week_plan(plan["week_start"], plan["slots"] + [{
                    "no": new_no,
                    "day": (sel_d - parse_date(week)).days + 1,
                    "from": slot["from"],
                    "to": slot["to"],
                }])
            except (OSError, ValueError) as exc:
                self._send_json({"ok": False, "no": new_no,
                                 "error": f"任务已创建（No.{new_no}），"
                                          f"但写入时间表失败：{exc}"})
                return

            created = next((t for t in read_tasks()
                            if str(t.get("no")) == new_no), None)
            self._send_json({
                "ok": True, "no": new_no, "task": created,
                "week_start": saved["week_start"], "slots": saved["slots"],
                "review": saved.get("review"),
                "hours": round(float(slot["to"]) - float(slot["from"]), 2),
            })

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
            # 四象限: 传空值 = 取消归类(删除字段), 与置顶的处理方式一致
            if "quadrant" in data:
                q = str(data.get("quadrant") or "").strip().upper()
                if q and not is_quadrant(q):
                    self._send_json({"ok": False, "error": f"非法象限: {q}"})
                    return
                if q:
                    target["quadrant"] = q
                else:
                    target.pop("quadrant", None)

            # 计划周期: 传空值 = 清除该字段(未完成任务用它跟踪延期)
            for key, label in (("start", "计划开始"), ("due", "计划截止")):
                if key not in data:
                    continue
                v = str(data.get(key) or "").strip()
                if v and parse_date(v) is None:
                    self._send_json({"ok": False, "error": f"{label}日期不合法：{v}（格式 YYYY/MM/DD，或该日期不存在）"})
                    return
                if v:
                    target[key] = v
                else:
                    target.pop(key, None)
            s_d, d_d = parse_date(target.get("start", "")), parse_date(target.get("due", ""))
            if s_d and d_d and d_d < s_d:
                self._send_json({"ok": False, "error": "计划截止日期不能早于计划开始日期"})
                return

            # 估时 / 实际净投入: 传空值或 0 = 清除字段
            for key, label in (("estimate_h", "预估工时"), ("actual_h", "实际净投入")):
                if key not in data:
                    continue
                h = _to_hours(data.get(key))
                if h is None:
                    target.pop(key, None)
                else:
                    target[key] = h

            # 预期成果: 传空值 = 清除(事务性任务). 非法取值拒绝, 不静默丢弃
            if "deliverable" in data:
                dl = str(data.get("deliverable") or "").strip()
                if dl and dl not in DELIVERABLE_META:
                    self._send_json({"ok": False, "error": f"非法成果类型: {dl}"})
                    return
                if dl:
                    target["deliverable"] = dl
                else:
                    target.pop("deliverable", None)

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

        # ---- 时间管理四象限 (docs/design/time-quadrant-design.md §5) ----
        elif path == "/api/set_quadrant":
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            if not task_no:
                self._send_json({"ok": False, "error": "缺少任务编号"})
                return
            raw = str(data.get("quadrant") or "").strip().upper()
            # 空值 = 取消归类(删除字段); 非法取值必须报错, 不能悄悄写坏数据
            if raw and not is_quadrant(raw):
                self._send_json({"ok": False, "error": f"非法象限: {raw}"})
                return
            ok, err = set_task_field(task_no, "quadrant", raw or None)
            self._send_json({"ok": True, "no": task_no, "quadrant": raw} if ok
                            else {"ok": False, "error": err})

        elif path == "/api/set_estimate":
            data = self._read_body()
            ok, err, hours = self._set_hours(data, "estimate_h")
            self._send_json({"ok": True, "estimate_h": hours} if ok
                            else {"ok": False, "error": err})

        elif path == "/api/set_actual":
            data = self._read_body()
            ok, err, hours = self._set_hours(data, "actual_h")
            self._send_json({"ok": True, "actual_h": hours} if ok
                            else {"ok": False, "error": err})

        elif path == "/api/set_blockers":
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            if not task_no:
                self._send_json({"ok": False, "error": "缺少任务编号"})
                return
            blockers = self._clean_blockers(data.get("blockers"))
            ok, err = set_task_field(task_no, "blockers", blockers or None)
            self._send_json({"ok": True, "count": len(blockers)} if ok
                            else {"ok": False, "error": err})

        elif path == "/api/set_deliverable":
            # 四象限页卡片上的成果角标直接改这里, 不必绕到编辑弹窗
            data = self._read_body()
            task_no = str(data.get("no", "")).strip()
            dl = str(data.get("deliverable") or "").strip()
            if dl and dl not in DELIVERABLE_META:
                self._send_json({"ok": False, "error": f"非法成果类型: {dl}"})
                return
            ok, err = set_task_field(task_no, "deliverable", dl or None)
            self._send_json({"ok": ok, "deliverable": dl} if ok
                            else {"ok": False, "error": err})

        elif path == "/api/week_review":
            # 周自评: 与排期同存 week_plan.json, 但分成两个端点 ——
            # 写自评不该触碰 slots, 写排期也不该触碰 review
            data = self._read_body()
            res = write_week_review(
                data.get("week_start"),
                data.get("text"),
                data.get("at"),
                {
                    "plan_h": data.get("plan_h"),
                    "slot_n": data.get("slot_n"),
                    "done_n": data.get("done_n"),
                    "done_h": data.get("done_h"),
                },
            )
            self._send_json({"ok": True, "week_start": res["week_start"],
                             "review": res["review"]})

        elif path == "/api/week_buffer":
            # 每周机动额度: 同样存 week_plan.json, 单独端点 ——
            # 改额度不该触碰 slots 与 review(同 week_review 的理由)
            data = self._read_body()
            res, err = write_week_buffer(data.get("week_start"), data.get("hours"))
            if err:
                self._send_json({"ok": False, "error": err})
            else:
                self._send_json({"ok": True, "week_start": res["week_start"],
                                 "buffer_h": res["buffer_h"]})

        elif path == "/api/week_plan":
            data = self._read_body()
            plan = write_week_plan(data.get("week_start"), data.get("slots"))
            # 把清洗后的 slots 与 review 一并带回: 前端据此更新本地状态,
            # 少带一个就会让它在下次重绘时"忘掉"这件事(自评曾因此从界面上消失)
            self._send_json({"ok": True, "count": len(plan["slots"]),
                             "week_start": plan["week_start"],
                             "slots": plan["slots"],
                             "review": plan["review"]})

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