"""
generate_project.py
生成项目管理页面。

功能:
    读取 data/projects.json (项目树原始数据) + data/task_flows.json (任务进度),
    生成两个页面到 output/project/:
      1. project_index.html  —— 项目索引, 每个项目一个按钮, 点击进入该项目的树状图
      2. project_tree.html   —— 从左到右的树状拓扑图, 支持在页面上手动创建/编辑/删除节点

用法:
    python3 src/generators/generate_project.py            # 生成页面
    python3 src/generators/generate_project.py --open     # 生成后打开索引页
"""

import argparse
import json
import os
import re
import sys
import webbrowser
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "output", "project")
os.makedirs(OUT_DIR, exist_ok=True)
PROJECTS_JSON = os.path.join(DATA_DIR, "projects.json")
INDEX_HTML = os.path.join(OUT_DIR, "project_index.html")
TREE_HTML = os.path.join(OUT_DIR, "project_tree.html")
TODAY_STR = date.today().strftime("%Y/%m/%d")

GEN_DIR = os.path.dirname(os.path.abspath(__file__))
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from generate_task_flow import read_tasks
from meta import (  # noqa: E402
    CATEGORY_COLOR,
    CATEGORY_ORDER,
    DEFAULT_KIND,
    KIND_CHOICES,
    KIND_META,
    PRIORITY_META,
    js,
)

# 新建项目时的默认分类
DEFAULT_PROJECT_CATEGORY = "工程"


# ----------------------------------------------------------------------------
# 原始数据读写
# ----------------------------------------------------------------------------
def migrate_project(proj):
    """把旧版树结构(root 是嵌套对象)迁移成「节点集合 + 边集合」; 已是新格式则原样返回。"""
    root = proj.get("root")
    if not isinstance(root, dict):
        proj.setdefault("nodes", [])
        proj.setdefault("edges", [])
        # root 缺失/null 时置空串, 避免 str(None) 变成 "None" 污染后续查找
        proj["root"] = "" if root is None else str(root)
        return proj
    nodes, edges = [], []

    def walk(n, parent_id=None):
        nd = {k: v for k, v in n.items() if k != "children"}
        nd.setdefault("tasks", [])
        nodes.append(nd)
        nid = str(nd.get("id", ""))
        if parent_id is not None:
            edges.append({"from": str(parent_id), "to": nid})
        for c in (n.get("children") or []):
            walk(c, nid)

    walk(root)
    proj["nodes"] = nodes
    proj["edges"] = edges
    proj["root"] = str(root.get("id", ""))
    return proj


def read_projects_raw():
    """读取 data/projects.json; 旧版树结构会在内存中自动迁移为节点+边。"""
    if not os.path.exists(PROJECTS_JSON):
        return {"meta": {}, "projects": []}
    with open(PROJECTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    for p in data.get("projects", []):
        migrate_project(p)
    return data


def write_projects_raw(data):
    """写回 data/projects.json。"""
    data.setdefault("meta", {})["updated"] = TODAY_STR
    with open(PROJECTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_date(s):
    """解析 YYYY/MM/DD 为 date 对象; 格式非法或日期不存在时返回 None。"""
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})$", (s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        # 如 2026/09/31 —— 不存在的日期, 当作未设置, 避免拖垮整个接口
        return None


def check_dates(fields):
    """校验节点的 plan / actual 日期, 返回错误信息或 None。"""
    for key, label in (("plan", "计划日期"), ("actual", "实际日期")):
        v = str(fields.get(key, "") or "").strip()
        if v and parse_date(v) is None:
            return f"{label}不合法：{v}（格式 YYYY/MM/DD，或该日期不存在）"
    return None


def get_project_root(data, project_id):
    """按项目 id 取项目对象。"""
    for p in data.get("projects", []):
        if str(p.get("id")) == str(project_id):
            return p
    return None


def _find_project_of(data, project_id):
    return get_project_root(data, project_id)


def find_node(proj, node_id):
    """按 id 取节点。"""
    for n in (proj.get("nodes") or []):
        if str(n.get("id")) == str(node_id):
            return n
    return None


def node_ids(proj):
    """项目的全部节点 id。"""
    return [str(n.get("id")) for n in (proj.get("nodes") or [])]


def successors(proj, node_id):
    """直接下游节点 id 列表。"""
    return [str(e.get("to")) for e in (proj.get("edges") or [])
            if str(e.get("from")) == str(node_id)]


def predecessors(proj, node_id):
    """直接上游节点 id 列表。"""
    return [str(e.get("from")) for e in (proj.get("edges") or [])
            if str(e.get("to")) == str(node_id)]


def reachable_from(proj, start_id):
    """从 start_id 出发能到达的节点集合(含自身)。"""
    seen, stack = set(), [str(start_id)]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(successors(proj, cur))
    return seen


def gen_node_id(proj, parent_id):
    """生成一个项目内不重复的节点编号。"""
    used = set(node_ids(proj))
    base = str(parent_id)
    i = 1
    while f"{base}-C{i}" in used:
        i += 1
    return f"{base}-C{i}"


def _parse_task_list(raw):
    """把 '1, 2,3' 或 ['1','2'] 统一转成分号列表。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = raw
    else:
        items = str(raw).replace("，", ",").split(",")
    out = []
    for it in items:
        v = str(it).strip()
        if v and v not in out:
            out.append(v)
    return out


def _clean_fields(src):
    """从前端提交的数据中提取并清洗节点字段。"""
    return {
        "name": str(src.get("name", "")).strip(),
        "kind": str(src.get("kind", "task")).strip() or "task",
        "owner": str(src.get("owner", "")).strip(),
        "plan": str(src.get("plan", "")).strip(),
        "actual": str(src.get("actual", "")).strip(),
        "note": str(src.get("note", "")).strip(),
        "tasks": _parse_task_list(src.get("tasks", [])),
    }


def apply_progress(node, src):
    """按提交的 progress 写入或清除手工进度; 返回错误信息或 None。"""
    raw = src.get("progress", None)
    if raw is None or str(raw).strip() == "":
        # 留空 -> 清除手工进度, 恢复按子节点/关联任务自动计算
        node.pop("progress", None)
        return None
    txt = str(raw).strip()
    try:
        val = int(round(float(txt)))
    except (TypeError, ValueError):
        return f"进度不合法：{txt}（请填 0-100 的数字）"
    if val < 0 or val > 100:
        return f"进度不合法：{txt}（请填 0-100 的数字）"
    node["progress"] = val
    return None


def add_node(project_id, parent_id, node_data):
    """在 parent_id 下新增节点并建立 parent -> 新节点 的边; 返回新节点 id。"""
    data = read_projects_raw()
    proj = _find_project_of(data, project_id)
    if not proj:
        return None, "项目不存在"
    if find_node(proj, parent_id) is None:
        return None, "父节点不存在"
    fields = _clean_fields(node_data)
    if not fields["name"]:
        return None, "节点名称不能为空"
    err = check_dates(fields)
    if err:
        return None, err
    fields["id"] = gen_node_id(proj, parent_id)
    err = apply_progress(fields, node_data)
    if err:
        return None, err
    proj.setdefault("nodes", []).append(fields)
    proj.setdefault("edges", []).append({"from": str(parent_id), "to": fields["id"]})
    write_projects_raw(data)
    return fields["id"], None


def edit_node(project_id, node_id, node_data):
    """编辑节点字段。"""
    data = read_projects_raw()
    proj = _find_project_of(data, project_id)
    if not proj:
        return False, "项目不存在"
    n = find_node(proj, node_id)
    if n is None:
        return False, "节点不存在"
    fields = _clean_fields(node_data)
    # 页面已不再编辑关联任务, 未提交 tasks 时保留原有取值
    if "tasks" not in node_data:
        fields["tasks"] = list(n.get("tasks", []) or [])
    if not fields["name"]:
        return False, "节点名称不能为空"
    err = check_dates(fields)
    if err:
        return False, err
    if str(node_id) == str(proj.get("root")):
        # 根节点不允许改类型
        fields["kind"] = n.get("kind", "project")
    n.update(fields)
    err = apply_progress(n, node_data)
    if err:
        return False, err
    write_projects_raw(data)
    return True, None


def link_node(project_id, from_id, to_id):
    """建立 from -> to 的连线(一个节点可有多个上游), 带环路检测。"""
    data = read_projects_raw()
    proj = _find_project_of(data, project_id)
    if not proj:
        return False, "项目不存在"
    if str(from_id) == str(to_id):
        return False, "不能连接到自己"
    if find_node(proj, from_id) is None:
        return False, "起点节点不存在"
    if find_node(proj, to_id) is None:
        return False, "目标节点不存在"
    edges = proj.setdefault("edges", [])
    for e in edges:
        if str(e.get("from")) == str(from_id) and str(e.get("to")) == str(to_id):
            return False, "这条连线已经存在"
    # 如果 to 已经能到达 from, 再加这条边就会形成环
    if str(from_id) in reachable_from(proj, to_id):
        return False, "会形成环路，已阻止"
    edges.append({"from": str(from_id), "to": str(to_id)})
    write_projects_raw(data)
    return True, None


def unlink_node(project_id, from_id, to_id):
    """断开一条连线; 目标节点只剩这一条上游时拒绝断开。"""
    data = read_projects_raw()
    proj = _find_project_of(data, project_id)
    if not proj:
        return False, "项目不存在"
    edges = proj.get("edges") or []
    hit = [e for e in edges
           if str(e.get("from")) == str(from_id) and str(e.get("to")) == str(to_id)]
    if not hit:
        return False, "连线不存在"
    if len(predecessors(proj, to_id)) <= 1:
        return False, "这是目标节点唯一的上游，请直接删除该节点"
    proj["edges"] = [e for e in edges
                     if not (str(e.get("from")) == str(from_id) and str(e.get("to")) == str(to_id))]
    write_projects_raw(data)
    return True, None


def delete_node(project_id, node_id):
    """删除节点及关联连线, 并清理因此不再连通的专属下游。"""
    data = read_projects_raw()
    proj = _find_project_of(data, project_id)
    if not proj:
        return False, "项目不存在"
    if str(node_id) == str(proj.get("root")):
        return False, "不能删除项目根节点"
    if find_node(proj, node_id) is None:
        return False, "节点不存在"
    nid = str(node_id)
    proj["nodes"] = [n for n in (proj.get("nodes") or []) if str(n.get("id")) != nid]
    proj["edges"] = [e for e in (proj.get("edges") or [])
                     if str(e.get("from")) != nid and str(e.get("to")) != nid]
    # 从根重新做可达性分析: 只清掉变为孤立的节点, 被别的上游连着的会保留
    alive = reachable_from(proj, proj.get("root"))
    dead = {i for i in node_ids(proj) if i not in alive}
    if dead:
        proj["nodes"] = [n for n in proj["nodes"] if str(n.get("id")) not in dead]
        proj["edges"] = [e for e in proj["edges"]
                         if str(e.get("from")) not in dead and str(e.get("to")) not in dead]
    write_projects_raw(data)
    return True, None


def set_done(project_id, node_id, done=True):
    """标记节点完成 / 取消完成(写入或清空 actual 日期)。"""
    data = read_projects_raw()
    proj = _find_project_of(data, project_id)
    if not proj:
        return False, "项目不存在"
    n = find_node(proj, node_id)
    if n is None:
        return False, "节点不存在"
    n["actual"] = TODAY_STR if done else ""
    write_projects_raw(data)
    return True, None


def gen_project_id(data):
    """生成下一个不重复的项目 id: P01 -> P02 ..."""
    used = {str(p.get("id", "")) for p in data.get("projects", [])}
    i = 1
    while True:
        cand = f"P{i:02d}"
        if cand not in used:
            return cand
        i += 1


def add_project(info):
    """新建项目(自带根节点), 返回项目 id。"""
    data = read_projects_raw()
    name = str(info.get("name", "")).strip()
    if not name:
        return None, "项目名称不能为空"
    for p in data.get("projects", []):
        if str(p.get("name", "")).strip() == name:
            return None, f"已存在同名项目: {name}"
    pid = gen_project_id(data)
    owner = str(info.get("owner", "")).strip()
    target = str(info.get("target", "")).strip()
    root_node = {
        "id": pid,
        "name": name,
        "kind": "project",
        "owner": owner,
        "plan": target,
        "actual": "",
        "note": str(info.get("note", "")).strip(),
        "tasks": [],
    }
    proj = {
        "id": pid,
        "name": name,
        "category": str(info.get("category", "个人")).strip() or "个人",
        "owner": owner,
        "priority": str(info.get("priority", "medium")).strip() or "medium",
        "start": str(info.get("start", "")).strip() or TODAY_STR,
        "target": target,
        "goal": str(info.get("goal", "")).strip(),
        "root": pid,
        "nodes": [root_node],
        "edges": [],
    }
    data.setdefault("projects", []).append(proj)
    write_projects_raw(data)
    return pid, None


def update_project(info):
    """修改项目基本信息(名称/分类/优先级/负责人/周期/目标), 返回 (项目id, 错误信息)。"""
    data = read_projects_raw()
    pid = str(info.get("id", "")).strip()
    if not pid:
        return None, "缺少项目 id"
    proj = _find_project_of(data, pid)
    if proj is None:
        return None, "项目不存在"
    name = str(info.get("name", "")).strip()
    if not name:
        return None, "项目名称不能为空"
    for p in data.get("projects", []):
        if str(p.get("id")) != pid and str(p.get("name", "")).strip() == name:
            return None, f"已存在同名项目: {name}"
    for key, label in (("start", "开始日期"), ("target", "目标日期")):
        v = str(info.get(key, "")).strip()
        if v and parse_date(v) is None:
            return None, f"{label}不合法：{v}（格式 YYYY/MM/DD，或该日期不存在）"
    owner = str(info.get("owner", "")).strip()
    target = str(info.get("target", "")).strip()
    old_name = str(proj.get("name", ""))
    proj["name"] = name
    proj["category"] = str(info.get("category", "")).strip() or proj.get("category", "个人")
    proj["owner"] = owner
    proj["priority"] = str(info.get("priority", "")).strip() or proj.get("priority", "medium")
    proj["start"] = str(info.get("start", "")).strip()
    proj["target"] = target
    proj["goal"] = str(info.get("goal", "")).strip()
    # 根节点是项目在树上的体现。名称只在根节点没被单独改过时跟随
    # (避免覆盖用户自定义的名字, 如 "2026XXX"), 负责人与目标日期始终同步
    root = find_node(proj, proj.get("root"))
    if root is not None:
        if str(root.get("name", "")) == old_name:
            root["name"] = name
        root["owner"] = owner
        root["plan"] = target
    write_projects_raw(data)
    return pid, None


def delete_project(project_ids):
    """删除一个或多个项目(含整棵树), 返回 (删除数量, 错误信息)。"""
    data = read_projects_raw()
    if isinstance(project_ids, str):
        project_ids = [project_ids]
    ids = {str(x).strip() for x in (project_ids or []) if str(x).strip()}
    if not ids:
        return 0, "未指定要删除的项目"
    projects = data.get("projects", [])
    kept = [p for p in projects if str(p.get("id", "")) not in ids]
    removed = len(projects) - len(kept)
    if not removed:
        return 0, "项目不存在或已被删除"
    data["projects"] = kept
    write_projects_raw(data)
    return removed, None


# ----------------------------------------------------------------------------
# 派生计算
# ----------------------------------------------------------------------------
def build_graph(proj, taskmap, today):
    """把项目的「节点+边」计算成带派生字段的有向图。

    返回 (节点列表(按原始顺序), 边列表, root_id, 统计)。
    进度优先级: 完成日期 > 手工填写 > 关联任务 > 下游平均 > 0
    """
    raw_nodes = list(proj.get("nodes") or [])
    edges = [{"from": str(e.get("from")), "to": str(e.get("to"))}
             for e in (proj.get("edges") or [])]
    root_id = str(proj.get("root", ""))
    node_map = {str(n.get("id")): n for n in raw_nodes}
    succ, pred = {}, {}
    for e in edges:
        succ.setdefault(e["from"], []).append(e["to"])
        pred.setdefault(e["to"], []).append(e["from"])

    built, visiting = {}, set()

    def build_one(nid):
        if nid in built:
            return built[nid]
        raw = node_map.get(nid)
        if raw is None:
            return None
        if nid in visiting:
            # 理论上 link 的环路检测已挡住, 这里兜底避免死递归
            return None
        visiting.add(nid)
        downs = [build_one(c) for c in succ.get(nid, [])]
        visiting.discard(nid)
        downs = [d for d in downs if d]

        linked = []
        for no in (raw.get("tasks") or []):
            t = taskmap.get(str(no))
            if t:
                linked.append({
                    "no": str(t.get("no")),
                    "name": t.get("name", ""),
                    "progress": int(t.get("today", 0)),
                    "finished": bool(t.get("finished")),
                    "status": t.get("status", ""),
                })

        manual = None
        raw_p = raw.get("progress", None)
        if raw_p is not None and str(raw_p).strip() != "":
            try:
                manual = max(0, min(100, int(round(float(raw_p)))))
            except (TypeError, ValueError):
                manual = None

        if (raw.get("actual") or "").strip():
            progress = 100
        elif manual is not None:
            # 显式填过进度 -> 以手工值为准, 不会被新增的下游节点带跑
            progress = manual
        elif linked:
            progress = round(sum(x["progress"] for x in linked) / len(linked))
        elif downs:
            progress = round(sum(d["progress"] for d in downs) / len(downs))
        else:
            progress = 0

        plan_d = parse_date(raw.get("plan"))
        if progress >= 100:
            status = "已完成"
        elif progress > 0:
            status = "进行中"
        else:
            status = "未开始"
        delayed = status != "已完成" and bool(plan_d) and plan_d < today

        item = {
            "id": nid,
            "name": raw.get("name", ""),
            "kind": raw.get("kind", "task"),
            "owner": raw.get("owner", ""),
            "plan": raw.get("plan", ""),
            "actual": raw.get("actual", ""),
            "note": raw.get("note", ""),
            "tasks": [str(x) for x in (raw.get("tasks") or [])],
            "linked": linked,
            "manual_progress": manual,
            "progress": progress,
            "status": status,
            "delayed": delayed,
            "pred": pred.get(nid, []),
            "succ": succ.get(nid, []),
        }
        built[nid] = item
        return item

    for n in raw_nodes:
        build_one(str(n.get("id")))

    ordered = [built[str(n.get("id"))] for n in raw_nodes if str(n.get("id")) in built]
    acc = {"total": 0, "done": 0, "delayed": 0}
    for it in ordered:
        acc["total"] += 1
        if it["status"] == "已完成":
            acc["done"] += 1
        if it["delayed"]:
            acc["delayed"] += 1
    return ordered, edges, root_id, acc


def build_projects():
    """返回 {projects:[...]}, 每个项目含 DAG 节点、边与派生统计。"""
    raw_data = read_projects_raw()
    tasks = read_tasks()
    taskmap = {str(t.get("no")): t for t in tasks}
    today = date.today()

    out = []
    for p in raw_data.get("projects", []):
        nodes, edges, root_id, acc = build_graph(p, taskmap, today)
        root_item = next((n for n in nodes if n["id"] == root_id), None)
        out.append({
            "id": str(p.get("id", "")),
            "name": p.get("name", ""),
            "category": p.get("category", "个人"),
            "owner": p.get("owner", ""),
            "priority": p.get("priority", "medium"),
            "start": p.get("start", ""),
            "target": p.get("target", ""),
            "goal": p.get("goal", ""),
            "root": root_id,
            "nodes": nodes,
            "edges": edges,
            "stats": acc,
            "progress": root_item["progress"] if root_item else 0,
        })
    return {"projects": out, "meta": raw_data.get("meta", {})}


# ----------------------------------------------------------------------------
# 页面模板
# ----------------------------------------------------------------------------
COMMON_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f5f6f8;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;color:#1f2733;min-height:100vh;padding:24px 16px 60px}
.wrap{max-width:1180px;margin:0 auto}
a{text-decoration:none;color:inherit}
button{font-family:inherit}

/* 头部 */
.hdr{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:12px}
.hdr h1{font-size:24px;font-weight:700;letter-spacing:1px}
.hdr .sub{font-size:13px;color:#5a6577;margin-top:4px}
.stats{display:flex;gap:10px;flex-wrap:wrap}
.st{background:#fff;border:1px solid #e3e8f0;border-radius:10px;padding:8px 14px;text-align:center;min-width:70px}
.st b{display:block;font-size:20px;color:#1f2733}
.st span{font-size:11px;color:#5a6577}

/* 筛选 */
.fbar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px;align-items:center}
.fbar .label{font-size:12px;color:#8893a7;margin-right:2px;font-weight:600}
.fbtn{background:#fff;color:#3a4456;border:1px solid #d8dee9;border-radius:18px;padding:5px 14px;font-size:12px;cursor:pointer;transition:all .15s;user-select:none}
.fbtn:hover{border-color:#60a5fa;color:#1f2733}
.fbtn.on{background:#3b6fb0;border-color:#3b6fb0;color:#fff;font-weight:600}
.fbtn .cnt{opacity:.6;margin-left:3px;font-weight:400}

.empty{text-align:center;color:#8893a7;padding:60px 0;font-size:14px}

/* 页面内提示条 (不依赖浏览器原生 alert) */
#toast{position:fixed;left:50%;bottom:34px;transform:translateX(-50%) translateY(14px);background:rgba(31,39,51,.93);color:#fff;font-size:13px;padding:10px 18px;border-radius:10px;opacity:0;pointer-events:none;transition:all .22s;z-index:2000;max-width:80vw;line-height:1.5;box-shadow:0 6px 22px rgba(0,0,0,.18)}
#toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
#toast.ok{background:rgba(46,158,91,.95)}
#toast.err{background:rgba(214,69,61,.95)}
"""


INDEX_HTML_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>项目管理 · 项目索引</title>
<style>
__COMMON_CSS__
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.pcard{display:block;text-align:left;background:#fff;border:1px solid #e3e8f0;border-radius:14px;padding:18px 20px 36px;cursor:pointer;transition:all .18s;position:relative;overflow:hidden}
.pcard:hover{border-color:#3b6fb0;box-shadow:0 4px 14px rgba(59,111,176,.12);transform:translateY(-2px)}
.pcard::after{content:"查看树状图 →";position:absolute;right:20px;bottom:13px;font-size:11px;color:#3b6fb0;opacity:0;transition:opacity .18s}
.pcard:hover::after{opacity:1}
.pc-top{display:flex;align-items:center;gap:6px;margin-bottom:8px}
.chip{font-size:11px;font-weight:600;padding:2px 10px;border-radius:10px}
.pc-name{font-size:17px;font-weight:700;color:#1f2733;margin-bottom:6px;line-height:1.35}
.pc-goal{font-size:12px;color:#5a6577;line-height:1.5;min-height:36px;margin-bottom:10px}
.bar{height:6px;background:#eef1f6;border-radius:4px;overflow:hidden;margin-bottom:8px}
.bar i{display:block;height:100%;border-radius:4px;transition:width .3s}
.pc-foot{display:flex;flex-wrap:wrap;gap:10px;font-size:11px;color:#8893a7}
.pc-foot b{color:#1f2733;font-weight:600}
.pc-warn{color:#d6453d}

/* 新建项目按钮与弹窗 */
.spacer{flex:1}
.newproj{background:#3b6fb0;border-color:#3b6fb0;color:#fff;font-weight:600}
.newproj:hover{opacity:.88;color:#fff;border-color:#3b6fb0}
.pcard.hl{border-color:#2e9e5b;box-shadow:0 0 0 3px rgba(46,158,91,.18)}
.modal-bg{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:1000}
.modal-bg.hide{display:none}
.modal{background:#fff;border-radius:14px;padding:24px;width:420px;max-width:92vw;box-shadow:0 8px 32px rgba(0,0,0,.12);max-height:92vh;overflow:auto}
.modal h3{font-size:16px;font-weight:700;color:#1f2733}
.modal label{display:block;font-size:12px;color:#5a6577;margin:12px 0 4px}
.modal input,.modal select,.modal textarea{width:100%;padding:8px 10px;border:1px solid #d8dee9;border-radius:8px;font-size:13px;box-sizing:border-box;font-family:inherit}
.modal textarea{resize:vertical;min-height:52px}
.modal input:focus,.modal select:focus,.modal textarea:focus{outline:none;border-color:#60a5fa}
.modal-actions{display:flex;gap:10px;margin-top:20px;justify-content:flex-end}
.modal-actions button{padding:7px 18px;border-radius:8px;font-size:13px;cursor:pointer;border:1px solid #d8dee9;background:#fff;color:#3a4456}
.modal-actions .btn-primary{background:#3b6fb0;color:#fff;border-color:#3b6fb0}
.two{display:flex;gap:10px}
.two>div{flex:1;min-width:0}
.hint{font-size:12px;color:#8893a7;margin-top:6px;line-height:1.5}

/* 删除项目 */
.pcard.picked{border-color:#d6453d;box-shadow:0 0 0 3px rgba(214,69,61,.14)}
.pchk{position:absolute;top:14px;right:16px;width:16px;height:16px;cursor:pointer;accent-color:#d6453d;z-index:2}
.pedit{position:absolute;top:12px;right:42px;width:24px;height:24px;border:none;background:transparent;cursor:pointer;font-size:13px;line-height:1;opacity:0;transition:opacity .15s;border-radius:6px;padding:0;z-index:2}
.pcard:hover .pedit{opacity:.65}
.pedit:hover{opacity:1;background:#eef1f6}
.delproj{color:#d6453d;border-color:#e6bcb9}
.delproj:hover:not(:disabled){background:#d6453d;border-color:#d6453d;color:#fff}
.delproj:disabled{opacity:.45;cursor:not-allowed}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div>
      <h1>项目管理</h1>
      <div class="sub" id="subtitle">加载中…</div>
    </div>
    <div class="stats">
      <div class="st"><b id="s-total">-</b><span>项目</span></div>
      <div class="st"><b id="s-doing">-</b><span>进行中</span></div>
      <div class="st"><b id="s-done">-</b><span>已完成</span></div>
      <div class="st"><b id="s-delay">-</b><span>延期节点</span></div>
    </div>
  </div>
  <div class="fbar">
    <span id="filters" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"></span>
    <span class="spacer"></span>
    <button class="fbtn delproj" id="del-proj" onclick="delSelected()" disabled>删除选中项目</button>
    <button class="fbtn newproj" onclick="openNewProject()">＋ 新建项目</button>
  </div>
  <div class="grid" id="grid"></div>
</div>

<!-- 新建项目弹窗 -->
<div class="modal-bg hide" id="np-bg">
  <div class="modal">
    <h3 id="np-title">新建项目</h3>
    <div class="hint" id="np-hint">创建后进入项目卡片即可在树状图中添加里程碑、任务等节点。</div>
    <label>项目名称 *</label>
    <input type="text" id="np-name" placeholder="如：reTerminal 固件升级">
    <div class="two">
      <div>
        <label>分类</label>
        <select id="np-cat">
__CAT_OPTIONS__        </select>
      </div>
      <div>
        <label>优先级</label>
        <select id="np-pri">
          <option value="high">高优先级</option>
          <option value="medium" selected>中优先级</option>
          <option value="low">低优先级</option>
        </select>
      </div>
    </div>
    <label>负责人</label>
    <input type="text" id="np-owner" placeholder="可选">
    <div class="two">
      <div>
        <label>开始日期 (YYYY/MM/DD)</label>
        <input type="text" id="np-start" placeholder="2026/09/14">
      </div>
      <div>
        <label>目标日期 (YYYY/MM/DD)</label>
        <input type="text" id="np-target" placeholder="2026/12/31">
      </div>
    </div>
    <label>项目目标</label>
    <textarea id="np-goal" placeholder="一句话说明项目要达成的结果"></textarea>
    <div class="modal-actions">
      <button onclick="closeNewProject()">取消</button>
      <button class="btn-primary" id="np-submit" onclick="submitProject()">创建</button>
    </div>
  </div>
</div>

<!-- 删除确认弹窗 (替代浏览器原生 confirm) -->
<div class="modal-bg hide" id="cfm-bg">
  <div class="modal" style="width:410px">
    <h3>确认删除</h3>
    <div class="hint" id="cfm-msg"></div>
    <div class="modal-actions">
      <button onclick="closeConfirm()">取消</button>
      <button class="btn-primary" id="cfm-ok" style="background:#d6453d;border-color:#d6453d">删除</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
const EMBEDDED = __PROJECTS_JSON__;
const CAT_COLOR = __CAT_COLOR__;
const PRIORITY = __PRIORITY__;
let DATA = {projects: []};
let curCat = 'all';
let hlId = null;
let picked = new Set();
let editingPid = null;

function progColor(p){ if(p>=80) return '#2e9e5b'; if(p>=40) return '#d29922'; return '#d6453d'; }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function todayStr(){ const d = new Date(); const p = n => String(n).padStart(2,'0'); return d.getFullYear() + '/' + p(d.getMonth()+1) + '/' + p(d.getDate()); }

let toastTimer = null;
function toast(msg, type){
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'on' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, 2800);
}

function init(){
  fetch('/api/projects').then(r => r.json()).then(d => { DATA = d; renderAll(); })
    .catch(() => { DATA = EMBEDDED; renderAll(); });
}

function renderAll(){
  const cats = [];
  for (const p of DATA.projects){ if (!cats.includes(p.category)) cats.push(p.category); }
  const box = document.getElementById('filters');
  box.innerHTML = '<span class="label">分类</span>';
  const mk = (key, label, cnt) => {
    const b = document.createElement('button');
    b.className = 'fbtn' + (curCat === key ? ' on' : '');
    b.innerHTML = label + '<span class="cnt">' + cnt + '</span>';
    b.onclick = () => { curCat = key; renderAll(); };
    box.appendChild(b);
  };
  mk('all', '全部', DATA.projects.length);
  for (const c of cats) mk(c, c, DATA.projects.filter(p => p.category === c).length);
  renderStats();
  renderGrid();
}

function renderStats(){
  const ps = DATA.projects;
  const delayed = ps.reduce((s, p) => s + p.stats.delayed, 0);
  document.getElementById('s-total').textContent = ps.length;
  document.getElementById('s-doing').textContent = ps.filter(p => p.progress < 100).length;
  document.getElementById('s-done').textContent = ps.filter(p => p.progress >= 100).length;
  document.getElementById('s-delay').textContent = delayed;
  document.getElementById('subtitle').textContent =
    '共 ' + ps.length + ' 个项目 · ' + ps.filter(p => p.progress < 100).length + ' 个推进中 · ' + delayed + ' 个节点延期';
}

function renderGrid(){
  const grid = document.getElementById('grid');
  const list = DATA.projects.filter(p => curCat === 'all' || p.category === curCat);
  if (!list.length){ grid.innerHTML = '<div class="empty">该分类下暂无项目</div>'; return; }
  grid.innerHTML = list.map(p => {
    const pri = PRIORITY[p.priority] || PRIORITY.medium;
    const cc = CAT_COLOR[p.category] || '#5a6577';
    const done = p.stats.done, total = p.stats.total;
    const cls = 'pcard' + (p.id === hlId ? ' hl' : '') + (picked.has(p.id) ? ' picked' : '');
    return `
      <div class="${cls}" onclick="location.href='project_tree.html?project=' + escape('${p.id}')">
        <input type="checkbox" class="pchk" title="勾选后可批量删除" data-id="${p.id}"${picked.has(p.id) ? ' checked' : ''}
               onclick="event.stopPropagation(); togglePick(this)">
        <button class="pedit" title="修改项目信息" onclick="event.stopPropagation(); openEditProject('${p.id}')">✏️</button>
        <div class="pc-top">
          <span class="chip" style="color:${cc};background:${cc}18">${p.category}</span>
          <span class="chip" style="color:${pri[1]};background:${pri[1]}18">${pri[0]}</span>
        </div>
        <div class="pc-name">${p.name}</div>
        <div class="pc-goal">${p.goal || '—'}</div>
        <div class="bar"><i style="width:${p.progress}%;background:${progColor(p.progress)}"></i></div>
        <div class="pc-foot">
          <span>👤 <b>${p.owner || '未指派'}</b></span>
          <span>节点 <b>${done}/${total}</b></span>
          <span>整体 <b>${p.progress}%</b></span>
          ${p.stats.delayed ? '<span class="pc-warn">⚠️ 延期 ' + p.stats.delayed + '</span>' : ''}
          ${p.target ? '<span>目标 ' + p.target + '</span>' : ''}
        </div>
      </div>`;
  }).join('');
  renderDelBtn();
}

// ------- 勾选与删除项目 -------
function togglePick(cb){
  const id = cb.getAttribute('data-id');
  if (cb.checked) picked.add(id); else picked.delete(id);
  const card = cb.closest('.pcard');
  if (card) card.classList.toggle('picked', cb.checked);
  renderDelBtn();
}

function renderDelBtn(){
  const btn = document.getElementById('del-proj');
  if (!btn) return;
  btn.disabled = picked.size === 0;
  btn.textContent = picked.size ? ('删除选中项目 (' + picked.size + ')') : '删除选中项目';
}

let confirmCb = null;
function confirmBox(msg, onOk, okText){
  confirmCb = onOk;
  document.getElementById('cfm-msg').innerHTML = msg;
  document.getElementById('cfm-ok').textContent = okText || '确定';
  document.getElementById('cfm-bg').classList.remove('hide');
}

function closeConfirm(){
  document.getElementById('cfm-bg').classList.add('hide');
  confirmCb = null;
}

document.addEventListener('DOMContentLoaded', () => {
  const bg = document.getElementById('cfm-bg');
  if (bg) bg.addEventListener('click', e => { if (e.target.id === 'cfm-bg') closeConfirm(); });
  const ok = document.getElementById('cfm-ok');
  if (ok) ok.onclick = () => { const fn = confirmCb; closeConfirm(); if (fn) fn(); };
});

function delSelected(){
  if (!picked.size) return;
  const ids = Array.from(picked);
  const names = ids.map(id => { const p = DATA.projects.find(x => x.id === id); return p ? p.name : id; });
  const msg = '确定删除以下 ' + ids.length + ' 个项目？'
    + '<div style="margin:8px 0;color:#d6453d;font-weight:600;line-height:1.7">'
    + names.map(n => '· ' + esc(n)).join('<br>')
    + '</div>项目下的所有节点会一并删除，且不可恢复。';
  confirmBox(msg, () => {
    fetch('/api/project/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ids: ids})})
      .then(r => r.json())
      .then(d => {
        if (!d.ok){ toast(d.error || '删除失败', 'err'); return; }
        picked.clear();
        curCat = 'all';
        toast('已删除 ' + d.removed + ' 个项目', 'ok');
        pull(null);
      })
      .catch(() => toast('连接服务器失败', 'err'));
  }, '删除');
}

// ------- 新建项目 -------
function openNewProject(){
  editingPid = null;
  document.getElementById('np-title').textContent = '新建项目';
  document.getElementById('np-hint').textContent = '创建后进入项目卡片即可在树状图中添加里程碑、任务等节点。';
  document.getElementById('np-submit').textContent = '创建';
  document.getElementById('np-name').value = '';
  document.getElementById('np-cat').value = '工程';
  document.getElementById('np-pri').value = 'medium';
  document.getElementById('np-owner').value = '';
  document.getElementById('np-start').value = todayStr();
  document.getElementById('np-target').value = '';
  document.getElementById('np-goal').value = '';
  document.getElementById('np-bg').classList.remove('hide');
  setTimeout(() => document.getElementById('np-name').focus(), 50);
}

function openEditProject(id){
  const p = DATA.projects.find(x => x.id === id);
  if (!p){ toast('项目不存在', 'err'); return; }
  editingPid = id;
  document.getElementById('np-title').textContent = '修改项目';
  document.getElementById('np-hint').textContent = '修改后立即生效；项目树的根节点会同步更新名称、负责人与目标日期。';
  document.getElementById('np-submit').textContent = '保存';
  document.getElementById('np-name').value = p.name || '';
  document.getElementById('np-cat').value = p.category || '工程';
  document.getElementById('np-pri').value = p.priority || 'medium';
  document.getElementById('np-owner').value = p.owner || '';
  document.getElementById('np-start').value = p.start || '';
  document.getElementById('np-target').value = p.target || '';
  document.getElementById('np-goal').value = p.goal || '';
  document.getElementById('np-bg').classList.remove('hide');
  setTimeout(() => document.getElementById('np-name').focus(), 50);
}

function closeNewProject(){ document.getElementById('np-bg').classList.add('hide'); }

document.addEventListener('DOMContentLoaded', () => {
  const bg = document.getElementById('np-bg');
  bg.addEventListener('click', e => { if (e.target.id === 'np-bg') closeNewProject(); });
  bg.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeNewProject();
    else if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') submitProject();
  });
});

function submitProject(){
  const name = document.getElementById('np-name').value.trim();
  if (!name){ toast('请填写项目名称', 'err'); return; }
  const payload = {
    name: name,
    category: document.getElementById('np-cat').value,
    priority: document.getElementById('np-pri').value,
    owner: document.getElementById('np-owner').value.trim(),
    start: document.getElementById('np-start').value.trim(),
    target: document.getElementById('np-target').value.trim(),
    goal: document.getElementById('np-goal').value.trim(),
  };
  const isEdit = !!editingPid;
  if (isEdit) payload.id = editingPid;
  fetch(isEdit ? '/api/project/edit' : '/api/project/add',
        {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
    .then(r => r.json())
    .then(d => {
      if (!d.ok){ toast(d.error || (isEdit ? '保存失败' : '创建失败'), 'err'); return; }
      closeNewProject();
      toast(isEdit ? '项目已更新' : '项目已创建', 'ok');
      pull(isEdit ? null : d.id);
    })
    .catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function pull(newId){
  fetch('/api/projects')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => {
      DATA = d;
      if (newId){
        const np = DATA.projects.find(x => x.id === newId);
        if (np) curCat = np.category;
        hlId = newId;
      }
      renderAll();
      if (newId) setTimeout(() => { hlId = null; renderGrid(); }, 3000);
    })
    .catch(e => toast('刷新数据失败：' + e.message, 'err'));
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
</script>
</body>
</html>
"""


TREE_HTML_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>项目树状图</title>
<style>
__COMMON_CSS__
.wrap{max-width:none;padding:0 16px}
.topbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.back{font-size:13px;color:#3b6fb0;background:#e8eef8;border:1px solid #c8d8ee;border-radius:8px;padding:5px 12px}
.back:hover{background:#3b6fb0;color:#fff}
select{padding:5px 10px;border:1px solid #d8dee9;border-radius:8px;font-size:13px;background:#fff;color:#3a4456;font-family:inherit}
.spacer{flex:1}
.btn{padding:5px 12px;border-radius:8px;font-size:12px;cursor:pointer;border:1px solid #d8dee9;background:#fff;color:#3a4456;transition:all .15s}
.btn:hover{border-color:#60a5fa}
.btn.primary{background:#3b6fb0;border-color:#3b6fb0;color:#fff}
.btn.primary:hover{background:#2d5a94}
#zoom-lbl{font-size:12px;color:#5a6577;min-width:40px;text-align:center}

.board{max-width:1180px;margin:0 auto 18px}
.pmeta{background:#fff;border:1px solid #e3e8f0;border-radius:12px;padding:16px 20px}
.pmeta .ptop{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.pmeta h1{font-size:20px;font-weight:700}
.pmeta .goal{font-size:12px;color:#5a6577;line-height:1.6;margin-bottom:10px}
.pmeta .bar{height:8px;background:#eef1f6;border-radius:5px;overflow:hidden;margin-bottom:8px}
.pmeta .bar i{display:block;height:100%;border-radius:5px}
.pmeta .row{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#5a6577}
.pmeta .row b{color:#1f2733}

.canvas-wrap{border:1px solid #e3e8f0;border-radius:12px;background:#fff;overflow:auto;max-height:70vh;position:relative}
.canvas{position:relative;transform-origin:0 0}
#wires{position:absolute;left:0;top:0;overflow:visible}
#nodes{position:absolute;left:0;top:0}
.pnode{position:absolute;width:236px;height:118px;background:#fff;border:1px solid #e3e8f0;border-radius:10px;padding:10px 12px;border-left:3px solid #8893a7;transition:box-shadow .15s}
.pnode:hover{box-shadow:0 3px 12px rgba(0,0,0,.08);z-index:5}
.pnode.s-done{border-left-color:#2e9e5b}
.pnode.s-doing{border-left-color:#d29922}
.pnode.s-todo{border-left-color:#8893a7}
.pnode.s-delay{border-left-color:#d6453d;background:#fffbfb}
.pn-hd{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.pn-kind{font-size:10px;font-weight:600;padding:1px 7px;border-radius:8px;flex:none}
.pn-name{font-size:13px;font-weight:600;color:#1f2733;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pn-date{font-size:11px;color:#5a6577;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pn-bar{height:4px;background:#eef1f6;border-radius:3px;overflow:hidden;margin-bottom:5px}
.pn-bar i{display:block;height:100%}
.pn-meta{display:flex;gap:8px;font-size:11px;color:#8893a7;white-space:nowrap;overflow:hidden}
.pn-tasks{font-size:10px;color:#7c6bc4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}
.pn-acts{position:absolute;right:6px;bottom:6px;display:flex;gap:2px;opacity:0;transition:opacity .15s}
.pnode:hover .pn-acts{opacity:1}
.pn-act{border:none;background:none;cursor:pointer;font-size:12px;padding:1px 3px;opacity:.55;border-radius:4px}
.pn-act:hover{opacity:1;background:#f0f2f5}

/* 弹窗 */
.modal-bg{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:1000}
.modal-bg.hide{display:none}
.modal{background:#fff;border-radius:14px;padding:24px;width:400px;max-width:92vw;box-shadow:0 8px 32px rgba(0,0,0,.12);max-height:92vh;overflow:auto}
.modal h3{font-size:16px;font-weight:700;margin-bottom:14px;color:#1f2733}
.modal label{display:block;font-size:12px;color:#5a6577;margin-bottom:4px;margin-top:12px}
.modal input,.modal select,.modal textarea{width:100%;padding:8px 10px;border:1px solid #d8dee9;border-radius:8px;font-size:13px;box-sizing:border-box;font-family:inherit}
.modal textarea{resize:vertical;min-height:50px}
.modal-actions{display:flex;gap:10px;margin-top:18px;justify-content:flex-end}
.modal-actions button{padding:7px 18px;border-radius:8px;font-size:13px;cursor:pointer;border:1px solid #d8dee9;background:#fff;color:#3a4456}
.modal-actions .btn-primary{background:#3b6fb0;color:#fff;border-color:#3b6fb0}
.hint{font-size:12px;color:#8893a7;margin-top:8px}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <a class="back" href="project_index.html">← 项目列表</a>
    <select id="proj-sel" onchange="switchProject(this.value)"></select>
    <div class="spacer"></div>
    <button class="btn" onclick="zoom(-0.1)">−</button>
    <span id="zoom-lbl">100%</span>
    <button class="btn" onclick="zoom(0.1)">＋</button>
  </div>

  <div class="board">
    <div class="pmeta" id="pmeta"></div>
  </div>

  <div class="canvas-wrap" id="canvas-wrap">
    <div class="canvas" id="canvas">
      <svg id="wires"></svg>
      <div id="nodes"></div>
    </div>
  </div>
</div>

<!-- 节点编辑弹窗 -->
<div class="modal-bg hide" id="modal-bg">
  <div class="modal">
    <h3 id="modal-title">新增节点</h3>
    <label>节点名称</label>
    <input type="text" id="n-name" placeholder="如：完成基线方案评审">
    <label>节点类型</label>
    <select id="n-kind">
__KIND_OPTIONS__    </select>
    <label>责任人</label>
    <input type="text" id="n-owner" placeholder="可选">
    <label>计划完成日期 (YYYY/MM/DD)</label>
    <input type="text" id="n-plan" placeholder="2026/09/30">
    <label>实际完成日期 (YYYY/MM/DD，留空表示未完成)</label>
    <input type="text" id="n-actual" placeholder="留空">
    <label>进度 (%)</label>
    <input type="text" id="n-progress" placeholder="0-100，填了就以它为准；留空则按子节点 / 关联任务汇总">
    <label>备注</label>
    <textarea id="n-note" placeholder="可选"></textarea>
    <div class="modal-actions">
      <button onclick="closeModal()">取消</button>
      <button class="btn-primary" onclick="submitNode()">保存</button>
    </div>
  </div>
</div>

<!-- 删除确认弹窗 (替代浏览器原生 confirm) -->
<div class="modal-bg hide" id="cfm-bg">
  <div class="modal" style="width:360px">
    <h3 id="cfm-title">确认删除</h3>
    <div class="hint" id="cfm-msg"></div>
    <div class="modal-actions">
      <button onclick="closeConfirm()">取消</button>
      <button class="btn-primary" id="cfm-ok" style="background:#d6453d;border-color:#d6453d">删除</button>
    </div>
  </div>
</div>

<!-- 连线弹窗 -->
<div class="modal-bg hide" id="link-bg">
  <div class="modal" style="width:430px">
    <h3 id="link-title">连线</h3>
    <div class="hint">建立「当前节点 → 目标节点」的连线。一个节点可以有多个上游，这样就实现了多路汇聚。</div>
    <label>连接到（下游节点）</label>
    <select id="link-target"></select>
    <div class="modal-actions">
      <button onclick="closeLink()">取消</button>
      <button class="btn-primary" onclick="submitLink()">连接</button>
    </div>
    <div id="link-preds" style="margin-top:16px"></div>
  </div>
</div>

<div id="toast"></div>

<script>
const EMBEDDED = __PROJECTS_JSON__;
const KIND_META = __KIND_META__;
const LEVEL_W = 300, ROW_H = 148, NODE_H = 118, NODE_W = 236, PAD = 40;
const CAT_COLOR = __CAT_COLOR__;
const PRIORITY = __PRIORITY__;

let DATA = {projects: []};
let curProj = null;
let zoomVal = 1;
let editing = {mode:'add', parentId:null, nodeId:null};

function progColor(p){ if(p>=80) return '#2e9e5b'; if(p>=40) return '#d29922'; return '#d6453d'; }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function currentId(){
  const m = location.search.match(/[?&]project=([^&]*)/);
  return m ? decodeURIComponent(m[1]) : (EMBEDDED.projects[0] ? EMBEDDED.projects[0].id : '');
}

function init(){
  fetch('/api/projects').then(r => r.json()).then(d => { DATA = d; boot(); })
    .catch(() => { DATA = EMBEDDED; boot(); });
}

function boot(){
  const sel = document.getElementById('proj-sel');
  sel.innerHTML = DATA.projects.map(p =>
    '<option value="' + esc(p.id) + '">' + esc(p.name) + '</option>').join('');
  const id = currentId();
  curProj = DATA.projects.find(p => p.id === id) || DATA.projects[0];
  if (!curProj){ document.getElementById('pmeta').innerHTML = '<div class="empty">暂无项目</div>'; return; }
  sel.value = curProj.id;
  renderMeta();
  renderTree();
}

function switchProject(id){
  location.href = 'project_tree.html?project=' + encodeURIComponent(id);
}

function renderMeta(){
  const p = curProj;
  const cc = CAT_COLOR[p.category] || '#5a6577';
  const pri = PRIORITY[p.priority] || PRIORITY.medium;
  document.getElementById('pmeta').innerHTML = `
    <div class="ptop">
      <h1>${esc(p.name)}</h1>
      <span class="chip" style="font-size:11px;font-weight:600;padding:2px 10px;border-radius:10px;color:${cc};background:${cc}18">${esc(p.category)}</span>
      <span class="chip" style="font-size:11px;font-weight:600;padding:2px 10px;border-radius:10px;color:${pri[1]};background:${pri[1]}18">${pri[0]}</span>
    </div>
    <div class="goal">${esc(p.goal || '—')}</div>
    <div class="bar"><i style="width:${p.progress}%;background:${progColor(p.progress)}"></i></div>
    <div class="row">
      <span>👤 <b>${esc(p.owner || '未指派')}</b></span>
      <span>周期 <b>${esc(p.start || '—')}</b> → <b>${esc(p.target || '—')}</b></span>
      <span>整体进度 <b>${p.progress}%</b></span>
      <span>节点 <b>${p.stats.done}/${p.stats.total}</b> 完成</span>
      ${p.stats.delayed ? '<span style="color:#d6453d">⚠️ 延期 ' + p.stats.delayed + '</span>' : '<span style="color:#2e9e5b">✓ 无延期</span>'}
    </div>`;
}

function statusClass(n){
  if (n.status === '已完成') return 's-done';
  if (n.delayed) return 's-delay';
  if (n.status === '进行中') return 's-doing';
  return 's-todo';
}

function renderTree(){
  const nodesBox = document.getElementById('nodes');
  const svg = document.getElementById('wires');
  const canvas = document.getElementById('canvas');
  const nodes = curProj.nodes || [];
  const edges = curProj.edges || [];

  const pred = {}, succ = {};
  edges.forEach(e => {
    (succ[e.from] = succ[e.from] || []).push(e.to);
    (pred[e.to] = pred[e.to] || []).push(e.from);
  });

  // 1. 分层: x = 从 root 起的最长路径深度 (带环保护)
  const level = {};
  function calc(id, seen){
    if (level[id] !== undefined) return level[id];
    const ps = pred[id] || [];
    if (!ps.length || seen.has(id)){ level[id] = 0; return 0; }
    seen.add(id);
    let v = 0;
    ps.forEach(p => { v = Math.max(v, calc(p, seen) + 1); });
    seen.delete(id);
    level[id] = v;
    return v;
  }
  nodes.forEach(n => calc(n.id, new Set()));

  // 结束节点排在最后一列(所有非结束节点的右边); 若它自己还有下游则不强制, 交给最长路径
  let maxLv = 0;
  nodes.forEach(n => { if (n.kind !== 'end') maxLv = Math.max(maxLv, level[n.id] || 0); });
  nodes.forEach(n => {
    if (n.kind === 'end' && !(succ[n.id] || []).length) level[n.id] = maxLv + 1;
  });

  // 2. 层内排 y: 先对齐到上游节点的平均位置(汇聚节点自然居中), 再向下消除重叠
  const layers = {};
  nodes.forEach(n => { const lv = level[n.id] || 0; (layers[lv] = layers[lv] || []).push(n); });
  const yMap = {};
  Object.keys(layers).map(Number).sort((a, b) => a - b).forEach(lv => {
    const arr = layers[lv];
    const upY = n => {
      const ys = (pred[n.id] || []).map(p => yMap[p]).filter(v => v !== undefined);
      return ys.length ? ys.reduce((s, v) => s + v, 0) / ys.length : 1e9;
    };
    arr.sort((a, b) => upY(a) - upY(b));
    arr.forEach(n => { const v = upY(n); yMap[n.id] = (v === 1e9) ? 0 : v; });
    for (let i = 1; i < arr.length; i++){
      const cur = arr[i].id, prev = arr[i - 1].id;
      if (yMap[cur] - yMap[prev] < ROW_H) yMap[cur] = yMap[prev] + ROW_H;
    }
  });

  const pos = {};
  nodes.forEach(n => { pos[n.id] = {x: (level[n.id] || 0) * LEVEL_W, y: yMap[n.id] || 0, n: n}; });

  // 3. 连线 (每条边一条曲线, 多上游时几条线收拢到同一节点)
  let paths = '';
  edges.forEach(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    const x1 = a.x + NODE_W, y1 = a.y + NODE_H / 2;
    const x2 = b.x, y2 = b.y + NODE_H / 2;
    const dx = Math.max(30, (x2 - x1) / 2);
    const color = b.n.status === '已完成' ? '#a8d5ba' : (b.n.delayed ? '#f0bcb8' : '#cfd6e2');
    paths += '<path d="M ' + x1 + ' ' + y1 + ' C ' + (x1 + dx) + ' ' + y1 + ', ' + (x2 - dx) + ' ' + y2 + ', ' + x2 + ' ' + y2 + '" fill="none" stroke="' + color + '" stroke-width="2"/>';
  });

  let maxX = 0, maxY = 0;
  nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  });
  const w = maxX + NODE_W + PAD * 2, h = maxY + NODE_H + PAD * 2;
  svg.setAttribute('width', w);
  svg.setAttribute('height', h);
  svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
  svg.innerHTML = paths;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';

  // 4. 节点卡片
  nodesBox.innerHTML = nodes.map(n => {
    const {x, y} = pos[n.id] || {x: 0, y: 0};
    const km = KIND_META[n.kind] || KIND_META.task;
    const stColor = n.status === '已完成' ? '#2e9e5b' : (n.delayed ? '#d6453d' : (n.status === '进行中' ? '#d29922' : '#8893a7'));
    const linkedHtml = n.linked && n.linked.length
      ? '<div class="pn-tasks">🔗 ' + n.linked.slice(0, 2).map(t => 'No.' + t.no + ' ' + t.progress + '%').join(' · ') + (n.linked.length > 2 ? ' +' + (n.linked.length - 2) : '') + '</div>'
      : (n.tasks && n.tasks.length ? '<div class="pn-tasks">🔗 任务 ' + n.tasks.join(',') + ' (未匹配)</div>' : '');
    const dateHtml = n.plan
      ? '计划 ' + esc(n.plan) + (n.actual ? ' · 实际 ' + esc(n.actual) : (n.delayed ? ' · <span style="color:#d6453d">已延期</span>' : ''))
      : (n.actual ? '实际 ' + esc(n.actual) : '未设日期');
    const doneBtn = n.status === '已完成'
      ? '<button class="pn-act" title="取消完成" onclick="toggleDone(\\'' + n.id + '\\',false)">↩️</button>'
      : '<button class="pn-act" title="标记完成" onclick="toggleDone(\\'' + n.id + '\\',true)">✅</button>';
    const up = (n.pred || []).length, down = (n.succ || []).length;
    return `
      <div class="pnode ${statusClass(n)}" style="left:${x + PAD}px;top:${y + PAD}px">
        <div class="pn-hd">
          <span class="pn-kind" style="color:${km[1]};background:${km[1]}1a">${km[0]}</span>
          <span class="pn-name" title="${esc(n.name)}">${esc(n.name)}</span>
        </div>
        <div class="pn-date">${dateHtml}</div>
        <div class="pn-bar"><i style="width:${n.progress}%;background:${progColor(n.progress)}"></i></div>
        <div class="pn-meta">
          <span style="color:${stColor}">${n.status}</span>
          <span>${n.progress}%</span>
          ${n.owner ? '<span>👤 ' + esc(n.owner) + '</span>' : ''}
          ${up > 1 ? '<span style="color:#7c6bc4" title="上游节点数">↑' + up + '</span>' : ''}
          ${down > 1 ? '<span style="color:#7c6bc4" title="下游节点数">↓' + down + '</span>' : ''}
        </div>
        ${linkedHtml}
        <div class="pn-acts">
          <button class="pn-act" title="添加子节点" onclick="openAdd('${n.id}')">＋</button>
          <button class="pn-act" title="连接到其它节点" onclick="openLink('${n.id}')">🔗</button>
          <button class="pn-act" title="编辑" onclick="openEdit('${n.id}')">✏️</button>
          ${doneBtn}
          <button class="pn-act" title="删除" onclick="delNode('${n.id}')">🗑️</button>
        </div>
      </div>`;
  }).join('');

  canvas.style.transform = 'scale(' + zoomVal + ')';
}

function zoom(delta){
  zoomVal = Math.min(1.6, Math.max(0.4, Math.round((zoomVal + delta) * 10) / 10));
  document.getElementById('zoom-lbl').textContent = Math.round(zoomVal * 100) + '%';
  document.getElementById('canvas').style.transform = 'scale(' + zoomVal + ')';
}

function findNode(id){
  return (curProj.nodes || []).find(n => n.id === id) || null;
}

// ------- 弹窗 -------
function openModal(){ document.getElementById('modal-bg').classList.remove('hide'); }
function closeModal(){ document.getElementById('modal-bg').classList.add('hide'); }

// ------- 页面内提示条 / 确认框 (浏览器原生 alert/confirm 在部分内嵌预览里被屏蔽) -------
let toastTimer = null;
function toast(msg, type){
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'on' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, 2800);
}

let confirmCb = null;
function confirmBox(msg, onOk, okText){
  confirmCb = onOk;
  document.getElementById('cfm-msg').innerHTML = msg;
  document.getElementById('cfm-ok').textContent = okText || '确定';
  document.getElementById('cfm-bg').classList.remove('hide');
}
function closeConfirm(){
  document.getElementById('cfm-bg').classList.add('hide');
  confirmCb = null;
}

document.addEventListener('DOMContentLoaded', () => {
  const bg = document.getElementById('modal-bg');
  if (bg) bg.addEventListener('click', e => { if (e.target.id === 'modal-bg') closeModal(); });
  const cb = document.getElementById('cfm-bg');
  if (cb) cb.addEventListener('click', e => { if (e.target.id === 'cfm-bg') closeConfirm(); });
  const ok = document.getElementById('cfm-ok');
  if (ok) ok.onclick = () => { const fn = confirmCb; closeConfirm(); if (fn) fn(); };
  const lb = document.getElementById('link-bg');
  if (lb) lb.addEventListener('click', e => { if (e.target.id === 'link-bg') closeLink(); });
});

function setKindOptions(kind){
  const sel = document.getElementById('n-kind');
  const extra = sel.querySelector('option[value="project"]');
  if (kind === 'project'){
    // 「项目」是根节点专属类型且不允许修改: 仅在编辑根节点时临时补上并锁定
    if (!extra){
      const o = document.createElement('option');
      o.value = 'project';
      o.textContent = '项目';
      sel.appendChild(o);
    }
    sel.value = 'project';
    sel.disabled = true;
  } else {
    if (extra) extra.remove();
    sel.disabled = false;
    sel.value = kind || 'task';
  }
}

function openAdd(parentId){
  editing = {mode:'add', parentId: parentId, nodeId: null};
  document.getElementById('modal-title').textContent = '在 ' + (findNode(parentId) || {}).name + ' 下新增节点';
  ['n-name','n-owner','n-plan','n-actual','n-progress','n-note'].forEach(id => { document.getElementById(id).value = ''; });
  setKindOptions('milestone');
  openModal();
}

function openEdit(nodeId){
  const n = findNode(nodeId);
  if (!n) return;
  editing = {mode:'edit', parentId: null, nodeId: nodeId};
  document.getElementById('modal-title').textContent = '编辑节点';
  document.getElementById('n-name').value = n.name || '';
  setKindOptions(n.kind || 'task');
  document.getElementById('n-owner').value = n.owner || '';
  document.getElementById('n-plan').value = n.plan || '';
  document.getElementById('n-actual').value = n.actual || '';
  const mp = n.manual_progress;
  document.getElementById('n-progress').value = (mp === null || mp === undefined) ? '' : mp;
  document.getElementById('n-note').value = n.note || '';
  openModal();
}

function post(url, payload){
  return fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
}

function reload(){
  const pid = curProj ? curProj.id : '';
  fetch('/api/projects')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(d => {
      DATA = d;
      curProj = DATA.projects.find(p => p.id === pid) || DATA.projects[0];
      if (!curProj) return;
      document.getElementById('proj-sel').value = curProj.id;
      renderMeta(); renderTree();
    })
    .catch(e => toast('刷新数据失败：' + e.message + '（请检查服务器终端是否有报错）', 'err'));
}

function badDate(s){
  if (!s) return false;
  const parts = s.split('/');
  if (parts.length !== 3) return true;
  if (!/^[0-9]{1,4}$/.test(parts[0]) || !/^[0-9]{1,2}$/.test(parts[1]) || !/^[0-9]{1,2}$/.test(parts[2])) return true;
  const y = +parts[0], mo = +parts[1], d = +parts[2];
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return true;
  const dt = new Date(y, mo - 1, d);
  return dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d;
}

function submitNode(){
  const payload = {
    name: document.getElementById('n-name').value.trim(),
    kind: document.getElementById('n-kind').value,
    owner: document.getElementById('n-owner').value.trim(),
    plan: document.getElementById('n-plan').value.trim(),
    actual: document.getElementById('n-actual').value.trim(),
    progress: document.getElementById('n-progress').value.trim(),
    note: document.getElementById('n-note').value.trim(),
  };
  if (!payload.name){ toast('请填写节点名称', 'err'); return; }
  const bad = badDate(payload.plan) ? '计划日期' : (badDate(payload.actual) ? '实际日期' : '');
  if (bad){ toast(bad + '不合法，请按 YYYY/MM/DD 填写真实存在的日期', 'err'); return; }
  if (payload.progress !== ''){
    const pv = Number(payload.progress);
    if (!isFinite(pv) || pv < 0 || pv > 100){ toast('进度请填 0-100 之间的数字', 'err'); return; }
  }
  let req;
  if (editing.mode === 'add'){
    req = post('/api/pnode/add', {project: curProj.id, parent: editing.parentId, node: payload});
  } else {
    req = post('/api/pnode/edit', {project: curProj.id, id: editing.nodeId, node: payload});
  }
  req.then(r => r.json()).then(d => {
    if (d.ok){
      closeModal();
      toast(editing.mode === 'add' ? '节点已创建' : '节点已更新', 'ok');
      reload();
    } else toast(d.error || '操作失败', 'err');
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function toggleDone(id, done){
  post('/api/pnode/done', {project: curProj.id, id: id, done: done})
    .then(r => r.json()).then(d => {
      if (d.ok){ toast(done ? '已标记完成' : '已取消完成', 'ok'); reload(); }
      else toast(d.error || '操作失败', 'err');
    })
    .catch(() => toast('连接服务器失败', 'err'));
}

// ------- 连线 (一个节点可以有多个上游) -------
let linkFrom = null;

function openLink(nodeId){
  const n = findNode(nodeId);
  if (!n) return;
  linkFrom = nodeId;
  document.getElementById('link-title').textContent = '「' + n.name + '」的连接';
  const sel = document.getElementById('link-target');
  const others = (curProj.nodes || []).filter(x => x.id !== nodeId);
  sel.innerHTML = others.map(x => '<option value="' + esc(x.id) + '">' + esc(x.name) + '</option>').join('');
  const box = document.getElementById('link-preds');
  const ps = (n.pred || []).map(id => findNode(id)).filter(Boolean);
  if (ps.length > 1){
    box.innerHTML = '<div class="hint" style="margin-bottom:6px">当前上游 ' + ps.length + ' 个，可断开多余的：</div>'
      + ps.map(p => '<div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;padding:4px 0;border-top:1px solid #eef1f6">'
          + '<span>' + esc(p.name) + '</span>'
          + '<button class="btn" style="padding:2px 10px;font-size:11px" onclick="unlinkFrom(\\'' + p.id + '\\')">断开</button>'
        + '</div>').join('');
  } else {
    box.innerHTML = '';
  }
  document.getElementById('link-bg').classList.remove('hide');
}

function closeLink(){
  document.getElementById('link-bg').classList.add('hide');
  linkFrom = null;
}

function submitLink(){
  const to = document.getElementById('link-target').value;
  if (!to){ toast('没有可连接的目标节点', 'err'); return; }
  post('/api/pnode/link', {project: curProj.id, from: linkFrom, to: to})
    .then(r => r.json())
    .then(d => {
      if (d.ok){ closeLink(); toast('已建立连线', 'ok'); reload(); }
      else toast(d.error || '连线失败', 'err');
    })
    .catch(() => toast('连接服务器失败', 'err'));
}

function unlinkFrom(fromId){
  post('/api/pnode/unlink', {project: curProj.id, from: fromId, to: linkFrom})
    .then(r => r.json())
    .then(d => {
      if (d.ok){ closeLink(); toast('已断开连线', 'ok'); reload(); }
      else toast(d.error || '断开失败', 'err');
    })
    .catch(() => toast('连接服务器失败', 'err'));
}

function delNode(id){
  const n = findNode(id);
  if (!n) return;
  // 统计删除后会被连带清理的下游(仅靠它连通的节点; 被其它上游连着的会保留)
  const edges = (curProj.edges || []).filter(e => e.from !== id && e.to !== id);
  const succ = {};
  edges.forEach(e => { (succ[e.from] = succ[e.from] || []).push(e.to); });
  const seen = new Set([curProj.root]);
  const stack = [curProj.root];
  while (stack.length){
    const cur = stack.pop();
    (succ[cur] || []).forEach(t => { if (!seen.has(t)){ seen.add(t); stack.push(t); } });
  }
  const dead = (curProj.nodes || []).filter(x => x.id !== id && !seen.has(x.id)).length;
  const msg = '确定删除「' + esc(n.name) + '」'
    + (dead ? ' 及其下游 ' + dead + ' 个节点' : '') + '？此操作不可恢复。';
  confirmBox(msg, () => {
    post('/api/pnode/delete', {project: curProj.id, id: id})
      .then(r => r.json())
      .then(d => {
        if (d.ok){ toast('已删除「' + n.name + '」', 'ok'); reload(); }
        else toast(d.error || '删除失败', 'err');
      })
      .catch(() => toast('连接服务器失败', 'err'));
  }, '删除');
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
</script>
</body>
</html>
"""


def _embed(obj):
    """JSON 嵌入 HTML 时的安全转义。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def main():
    parser = argparse.ArgumentParser(description="生成项目管理页面")
    parser.add_argument("--open", action="store_true", help="生成后打开索引页")
    args = parser.parse_args()

    data = build_projects()
    embedded = _embed(data)

    # 分类 / 优先级 / 节点类型 统一从 meta.py 注入, 模板里不再手写清单
    cat_options = "".join(
        '          <option value="%s"%s>%s</option>\n'
        % (c, " selected" if c == DEFAULT_PROJECT_CATEGORY else "", c)
        for c in CATEGORY_ORDER
    )
    kind_options = "".join(
        '      <option value="%s"%s>%s</option>\n'
        % (k, " selected" if k == DEFAULT_KIND else "", KIND_META[k]["label"])
        for k in KIND_CHOICES
    )
    cat_js = js(CATEGORY_COLOR)
    pri_js = js({k: [v["label"], v["color"]] for k, v in PRIORITY_META.items()})
    kind_js = js({k: [v["label"], v["color"]] for k, v in KIND_META.items()})

    def render(tpl):
        return (tpl
                .replace("__COMMON_CSS__", COMMON_CSS)
                .replace("__PROJECTS_JSON__", embedded)
                .replace("__CAT_COLOR__", cat_js)
                .replace("__PRIORITY__", pri_js)
                .replace("__KIND_META__", kind_js)
                .replace("__CAT_OPTIONS__", cat_options)
                .replace("__KIND_OPTIONS__", kind_options))

    index_html = render(INDEX_HTML_TPL)
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(index_html)

    tree_html = render(TREE_HTML_TPL)
    with open(TREE_HTML, "w", encoding="utf-8") as f:
        f.write(tree_html)

    print(f"[完成] 已生成:")
    print(f"       {INDEX_HTML}")
    print(f"       {TREE_HTML}")
    print(f"       项目数: {len(data['projects'])}")
    for p in data["projects"]:
        print(f"       - {p['id']} {p['name']}: {p['stats']['done']}/{p['stats']['total']} 节点完成, 整体 {p['progress']}%")

    if args.open:
        webbrowser.open("file://" + os.path.abspath(INDEX_HTML).replace("\\", "/"))


if __name__ == "__main__":
    main()
