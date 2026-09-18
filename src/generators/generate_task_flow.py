"""
generate_task_flow.py
生成任务推进流程跟踪树状图页面 (HTML)。

功能:
    读取 data/task_flows.json, 为每个任务生成独立的流程树,
    按分类 (category) 分组展示, 输出到 output/tasks/task_flow.html。
    页面顶部提供统计概览与筛选按钮, 底部提供复盘分析。

用法:
    python3 src/generators/generate_task_flow.py            # 生成页面
    python3 src/generators/generate_task_flow.py --open     # 生成后打开浏览器
"""

import argparse
import json
import os
import re
import sys
import webbrowser
from datetime import date

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "task_flow.html")
TASK_FLOWS_JSON = os.path.join(DATA_DIR, "task_flows.json")

TODAY_STR = date.today().strftime("%Y/%m/%d")

# ----------------------------------------------------------------------------
# 元数据
# ----------------------------------------------------------------------------
# 分类 / 优先级 / 状态 统一取自 meta.py, 避免各生成器各维护一份清单
GEN_DIR = os.path.dirname(os.path.abspath(__file__))
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from meta import (  # noqa: E402
    CATEGORY_FALLBACK_ICON,
    CATEGORY_ICON,
    CATEGORY_ORDER,
    DEFAULT_PRIORITY,
    DELIVERABLE_META,
    PRIORITY_META,
    PRIORITY_ORDER,
    QUADRANT_META,
    STATUS_META,
    STATUS_ORDER,
    collect_categories,
    js,
)


# ----------------------------------------------------------------------------
# 数据读取
# ----------------------------------------------------------------------------
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


def _to_hours(value):
    """宽松解析小时数: 非法或 <= 0 一律视为未填写, 返回 None(不按 0 计入统计, 见 §7.3)。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        hours = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return round(hours, 2) if hours > 0 else None


def suggest_quadrant(priority, delayed, days_left):
    """按 §2.4 推导建议象限 —— 仅作页面角标提示, 永不自动落盘。

    两条刻意的限制:
    1. **不产出 D 建议**。D 意味着"这件事不该进清单", 而它已经在清单里了 ——
       这是个需要人判断的矛盾状态, 算法不该替人决定(§2.9.4)。
    2. **low 且不紧迫时不给建议**。"优先级排在后面"不等于"不重要不紧迫",
       只凭 priority 区分不了这两者(§2.2 已说明 priority 是单维的)。
    """
    urgent = bool(delayed) or (days_left is not None and days_left <= 7)
    pri = str(priority or "").strip().lower()
    if pri == "high":
        return "A" if urgent else "B"
    if pri == "medium":
        return "C" if urgent else "B"
    return "C" if urgent else ""


def set_task_field(task_no, key, value):
    """写入/删除任务的顶层字段(value 为 None 时删除字段)。返回 (ok, error)。"""
    tasks = read_tasks_raw()
    for item in tasks:
        if str(item.get("no", "")) == str(task_no).strip():
            if value is None:
                item.pop(key, None)
            else:
                item[key] = value
            write_tasks_raw(tasks)
            return True, ""
    return False, f"任务 No.{task_no} 不存在"


def read_tasks_raw():
    """读取 task_flows.json 原始数据（不含计算字段）。"""
    if not os.path.exists(TASK_FLOWS_JSON):
        return []
    with open(TASK_FLOWS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def write_tasks_raw(tasks):
    """写入 task_flows.json。"""
    with open(TASK_FLOWS_JSON, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def read_tasks():
    """读取 task_flows.json, 返回任务 dict 列表（含计算字段和流程节点）。"""
    raw = read_tasks_raw()
    if not raw:
        # 库函数不终止进程: 调用方(生成器 / HTTP 服务)自行决定如何处理空数据
        print(f"[警告] {TASK_FLOWS_JSON} 中没有任务数据，按空列表处理")
        return []

    tasks = []
    for item in raw:
        task_no = str(item.get("no", ""))
        name = (item.get("name") or "").strip()
        date_str = (item.get("date") or "").strip()
        priority = (item.get("priority") or "medium").strip().lower()
        category = (item.get("category") or "个人").strip()
        nodes_raw = item.get("nodes", [])

        create_d = parse_date(date_str)

        # 计划周期(可选): 未完成任务用它跟踪进度、判断延期; 已完成的任务一般不需要填
        plan_start = (item.get("start") or "").strip()
        plan_due = (item.get("due") or "").strip()
        start_d = parse_date(plan_start)
        due_d = parse_date(plan_due)

        # 从节点推导完成状态
        finished = False
        completed_date = ""
        if nodes_raw:
            last = nodes_raw[-1]
            # 最后一个节点进度达到 100% 即视为完成, 不限制阶段名称
            if last.get("progress", 0) >= 100:
                finished = True
                completed_date = last.get("date", "")

        today_prog = nodes_raw[-1]["progress"] if nodes_raw else 0
        yesterday_prog = nodes_raw[-2]["progress"] if len(nodes_raw) >= 2 else 0

        status = (item.get("status") or "").strip()
        if not status:
            status = "已完成" if finished else ("未开始" if today_prog == 0 else "进行中")

        # 计算耗时
        if finished and create_d:
            comp_d = parse_date(completed_date)
            total_days = (comp_d - create_d).days if comp_d else 0
        elif create_d:
            total_days = (date.today() - create_d).days
        else:
            total_days = 0

        # 停滞检测
        stalled = False
        if not finished and status == "进行中":
            if create_d and (date.today() - create_d).days > 7 and today_prog == 0:
                stalled = True

        # 构建带 days_from_prev 的节点
        nodes = []
        for i, n in enumerate(nodes_raw):
            prev_d = parse_date(nodes_raw[i - 1]["date"]) if i > 0 else None
            curr_d = parse_date(n["date"])
            gap = (curr_d - prev_d).days if prev_d and curr_d else None
            node = {
                "phase": n.get("phase", "推进"),
                "date": n.get("date", ""),
                "progress": n.get("progress", 0),
                "days_from_prev": gap,
            }
            if n.get("note"):
                node["note"] = n["note"]
            if n.get("owner"):
                node["owner"] = n["owner"]
            nodes.append(node)

        days_left = (due_d - date.today()).days if (due_d and not finished) else None
        delayed = bool(due_d and not finished and due_d < date.today())

        # 最长空档: 相邻节点的最大间隔, 后评估页据此定位停滞区间 —— 见 §2.9.2
        max_gap, max_gap_from, max_gap_to = None, "", ""
        for i, n in enumerate(nodes):
            gap = n.get("days_from_prev")
            if gap is not None and (max_gap is None or gap > max_gap):
                max_gap, max_gap_from, max_gap_to = gap, nodes[i - 1]["date"], n["date"]

        # 预期成果类型: 只接受枚举内的值, 非法取值按"未填"处理。
        # 与 category 正交 —— 领域是"科研"不代表产出是"论文"。
        deliverable = str(item.get("deliverable") or "").strip()
        if deliverable not in DELIVERABLE_META:
            deliverable = ""

        # ---- 时间管理四象限相关字段(全部可选, 缺失即保持缺失) ----
        quadrant = str(item.get("quadrant") or "").strip().upper()
        if quadrant not in QUADRANT_META:
            quadrant = ""   # 非法取值按"未标记"处理, 只影响这一个字段
        estimate_h = _to_hours(item.get("estimate_h"))
        actual_h = _to_hours(item.get("actual_h"))

        blockers = []
        if isinstance(item.get("blockers"), list):
            for b in item["blockers"]:
                if not isinstance(b, dict) or not str(b.get("type") or "").strip():
                    continue
                blockers.append({
                    "type": str(b.get("type")).strip(),
                    "from": str(b.get("from") or "").strip(),
                    "to": str(b.get("to") or "").strip(),
                    "note": str(b.get("note") or "").strip(),
                })

        tasks.append({
            "no": task_no,
            "name": name,
            "date": date_str,
            "yesterday": yesterday_prog,
            "today": today_prog,
            "priority": priority,
            "finished": finished,
            "completed_date": completed_date,
            "category": category,
            "status": status,
            "total_days": total_days,
            "nodes": nodes,
            "stalled": stalled,
            # 置顶(当前重点): 由页面上的 📌 按钮写入 task_flows.json
            "pinned": bool(item.get("pinned")),
            # 计划周期与延期判定(已完成的任务不参与延时计算)
            "start": plan_start,
            "due": plan_due,
            "plan_days": (due_d - start_d).days if (due_d and start_d) else None,
            "days_left": days_left,
            "delayed": delayed,
            # ---- 四象限 / 估时 / 卡点 (docs/design/time-quadrant-design.md) ----
            "quadrant": quadrant,
            "estimate_h": estimate_h,
            "actual_h": actual_h,
            "blockers": blockers,
            "q_hint": suggest_quadrant(priority, delayed, days_left),
            # 预期成果类型; 空 = 事务性任务(无产出), 是合法状态而非缺数据
            "deliverable": deliverable,
            "max_gap": max_gap,
            "max_gap_from": max_gap_from,
            "max_gap_to": max_gap_to,
            "json_backed": True,
        })
    return tasks


# ----------------------------------------------------------------------------
# HTML 生成
# ----------------------------------------------------------------------------
def build_html(tasks):
    tasks = sorted(tasks, key=lambda t: int(t["no"]) if t["no"].isdigit() else 0)
    data_json = json.dumps(tasks, ensure_ascii=False).replace("</", "<\\/")

    # 分类从数据动态收集: 数据里出现的新分类不会再被白名单漏掉
    cats = collect_categories(tasks)

    cat_stats = {}
    for cat in cats:
        ct = [t for t in tasks if t["category"] == cat]
        cat_stats[cat] = {
            "total": len(ct),
            "done": sum(1 for t in ct if t["finished"]),
            "avg_days": round(sum(t["total_days"] for t in ct if t["finished"]) / max(sum(1 for t in ct if t["finished"]), 1), 1),
        }

    # 分类筛选按钮
    cat_btns = "".join(
        f'<button class="fbtn" data-cat="{c}">{CATEGORY_ICON.get(c, CATEGORY_FALLBACK_ICON)} {c}</button>'
        for c in cats
    )
    # 状态筛选按钮：data-st 用纯文本，避免 emoji 编码问题
    status_btns = "".join(
        f'<button class="fbtn" data-st="{s}">{STATUS_META[s]["icon"]} {s}</button>'
        for s in STATUS_ORDER
    )

    pri_meta_json = js({k: [v["short"], v["color"]] for k, v in PRIORITY_META.items()})

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>任务流程跟踪树</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#f5f6f8;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;color:#1f2733;min-height:100vh;padding:24px 16px 60px}}
.wrap{{max-width:1020px;margin:0 auto}}

/* 头部 */
.hdr{{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:12px}}
.hdr h1{{font-size:24px;font-weight:700;letter-spacing:1px}}
.hdr .sub{{font-size:13px;color:#5a6577;margin-top:4px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap}}
.st{{background:#fff;border:1px solid #e3e8f0;border-radius:10px;padding:8px 14px;text-align:center;min-width:70px}}
.st b{{display:block;font-size:20px;color:#1f2733}}
.st span{{font-size:11px;color:#5a6577}}

/* 筛选 */
.fbar{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px;align-items:center}}
.fbar .label{{font-size:12px;color:#8893a7;margin-right:2px;font-weight:600}}
.fbtn{{background:#fff;color:#3a4456;border:1px solid #d8dee9;border-radius:18px;padding:5px 14px;font-size:12px;cursor:pointer;transition:all .15s;user-select:none}}
.fbtn:hover{{border-color:#60a5fa;color:#1f2733}}
.fbtn.on{{background:#3b6fb0;border-color:#3b6fb0;color:#fff;font-weight:600}}
.fbtn .cnt{{opacity:.6;margin-left:3px;font-weight:400}}
.sep{{width:1px;height:20px;background:#d8dee9;margin:0 6px}}

/* 分类组 */
.cat-group{{margin-bottom:24px}}
.cat-hdr{{display:flex;align-items:center;gap:8px;margin-bottom:12px;cursor:pointer;user-select:none}}
.cat-hdr .icon{{font-size:20px}}
.cat-hdr .name{{font-size:17px;font-weight:700;color:#1f2733}}
.cat-hdr .cnt{{font-size:12px;color:#8893a7;background:#eef1f6;border-radius:10px;padding:2px 10px}}
.cat-hdr .arrow{{font-size:12px;color:#8893a7;transition:transform .2s}}
.cat-hdr.collapsed .arrow{{transform:rotate(-90deg)}}
.cat-body{{display:flex;flex-direction:column;gap:14px}}
.cat-body.hide{{display:none}}

/* 任务卡片 */
.task{{background:#fff;border:1px solid #e3e8f0;border-radius:12px;padding:16px 18px;transition:all .2s}}
.task:hover{{border-color:#c8d1de;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
.task.highlight{{border-color:#3b6fb0;box-shadow:0 0 0 3px rgba(59,111,176,.18)}}
.task-hdr{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}}
.task-title{{display:flex;align-items:center;gap:8px;flex:1;min-width:0}}
.task-title .sicon{{font-size:16px;flex:none}}
.task-title .tname{{font-size:15px;font-weight:600;color:#1f2733;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.task-title .tno{{font-size:11px;color:#8893a7;flex:none}}
.task-meta{{display:flex;gap:8px;align-items:center;flex:none}}
.badge{{font-size:11px;font-weight:600;padding:2px 10px;border-radius:10px}}
.time-tag{{font-size:11px;color:#5a6577;background:#f0f2f5;border-radius:8px;padding:2px 8px}}
.plan-tag{{font-size:11px;color:#5a6577;background:#f0f2f5;border-radius:8px;padding:2px 8px;white-space:nowrap}}
.plan-tag.over{{color:#d6453d;background:#fdeceb;font-weight:600}}
.plan-tag.none{{color:#b0b8c6;background:#f7f8fa}}

/* 置顶(当前重点) */
.pin-btn{{font-size:14px;cursor:pointer;opacity:.25;transition:opacity .15s;line-height:1;user-select:none}}
.pin-btn:hover{{opacity:.7}}
.pin-btn.on{{opacity:1}}
.task.pinned{{border-color:#e0b055;box-shadow:0 0 0 3px rgba(210,153,34,.13);background:#fffdf8}}
.task.pinned .tname{{color:#8a5d00}}
.cat-group.pin-group{{margin-bottom:20px}}
.cat-group.pin-group .cat-hdr .name{{color:#8a5d00}}
.cat-group.pin-group .cat-hdr .cnt{{background:#fdf0d8;color:#8a5d00}}
.pin-hint{{font-size:12px;color:#b7791f;font-weight:400}}

/* 流程树 */
.tree{{position:relative;padding-left:24px;margin-top:8px}}
.tree::before{{content:"";position:absolute;left:9px;top:4px;bottom:4px;width:2px;background:#e3e8f0;border-radius:1px}}
.node{{position:relative;padding:6px 0 6px 16px}}
.node::before{{content:"";position:absolute;left:-16px;top:14px;width:12px;height:2px;background:#e3e8f0}}
.node-dot{{position:absolute;left:-20px;top:10px;width:12px;height:12px;border-radius:50%;border:2px solid #e3e8f0;background:#fff}}
.node-dot.create{{border-color:#3b6fb0;background:#e8eef8}}
.node-dot.progress{{border-color:#d29922;background:#fef8e8}}
.node-dot.done{{border-color:#2e9e5b;background:#e7f4ec}}
.node-dot.current{{border-color:#d29922;background:#fef8e8;box-shadow:0 0 0 3px rgba(210,153,34,.15)}}
.node-dot.stalled{{border-color:#d6453d;background:#fdeceb;box-shadow:0 0 0 3px rgba(214,69,61,.15)}}
.node-row{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.node-phase{{font-size:12px;font-weight:600;color:#3a4456;min-width:36px}}
.node-date{{font-size:12px;color:#5a6577}}
.node-prog{{font-size:12px;font-weight:600}}
.node-gap{{font-size:11px;color:#8893a7;background:#f5f6f8;border-radius:6px;padding:1px 6px}}
.node-warn{{font-size:11px;color:#d6453d}}
.node-note{{font-size:11px;color:#5a6577;margin-top:3px;padding-left:2px}}
.node-owner{{font-size:11px;color:#7c6bc4;background:#f0ecf8;border-radius:6px;padding:1px 6px;margin-left:4px}}

/* 汇总行 */
.summary{{margin-top:10px;padding-top:8px;border-top:1px dashed #e3e8f0;display:flex;align-items:center;gap:8px;font-size:12px;color:#5a6577}}
.summary b{{color:#1f2733}}
.add-btn{{font-size:11px;color:#3b6fb0;cursor:pointer;border:1px solid #c8d8ee;border-radius:8px;padding:2px 8px;background:#e8eef8;transition:all .15s}}
.add-btn:hover{{background:#3b6fb0;color:#fff}}
.node-actions{{display:inline-flex;gap:4px;margin-left:6px}}
.node-act{{font-size:11px;cursor:pointer;opacity:.4;transition:opacity .15s;border:none;background:none;padding:0 2px}}
.node-act:hover{{opacity:1}}
.node-act.edit:hover{{color:#3b6fb0}}
.node-act.del:hover{{color:#d6453d}}

/* 弹窗 */
.modal-bg{{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:1000}}
.modal-bg.hide{{display:none}}
.modal{{background:#fff;border-radius:14px;padding:24px;width:380px;max-width:90vw;box-shadow:0 8px 32px rgba(0,0,0,.12)}}
.modal h3{{font-size:16px;font-weight:700;margin-bottom:16px;color:#1f2733}}
.modal label{{display:block;font-size:12px;color:#5a6577;margin-bottom:4px;margin-top:12px}}
.modal input,.modal select,.modal textarea{{width:100%;padding:8px 10px;border:1px solid #d8dee9;border-radius:8px;font-size:13px;box-sizing:border-box;font-family:inherit}}
.modal textarea{{resize:vertical;min-height:50px}}
.modal-actions{{display:flex;gap:10px;margin-top:18px;justify-content:flex-end}}
.modal-actions button{{padding:7px 18px;border-radius:8px;font-size:13px;cursor:pointer;border:1px solid #d8dee9;background:#fff;color:#3a4456;transition:all .15s}}
.modal-actions .btn-primary{{background:#3b6fb0;color:#fff;border-color:#3b6fb0}}
.modal-actions .btn-primary:hover{{background:#2d5a94}}

/* 页面内提示条 / 确认框 (部分内嵌预览会屏蔽原生 alert/confirm) */
#toast{{position:fixed;left:50%;bottom:34px;transform:translateX(-50%) translateY(14px);background:rgba(31,39,51,.93);color:#fff;font-size:13px;padding:10px 18px;border-radius:10px;opacity:0;pointer-events:none;transition:all .22s;z-index:2000;max-width:80vw;line-height:1.5;box-shadow:0 6px 22px rgba(0,0,0,.18)}}
#toast.on{{opacity:1;transform:translateX(-50%) translateY(0)}}
#toast.ok{{background:rgba(46,158,91,.95)}}
#toast.err{{background:rgba(214,69,61,.95)}}
.cfm-msg{{font-size:13px;color:#5a6577;line-height:1.6}}

/* 底部复盘 */
.review{{margin-top:32px;background:#fff;border:1px solid #e3e8f0;border-radius:12px;padding:20px 24px}}
.review h2{{font-size:18px;font-weight:700;margin-bottom:14px;color:#1f2733}}
.rev-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
.rev-card{{background:#f8f9fb;border:1px solid #eef1f6;border-radius:10px;padding:14px 16px}}
.rev-card h3{{font-size:13px;font-weight:600;color:#3a4456;margin-bottom:8px}}
.rev-row{{display:flex;justify-content:space-between;font-size:12px;color:#5a6577;padding:3px 0}}
.rev-row b{{color:#1f2733}}
.rev-list{{font-size:12px;color:#5a6577}}
.rev-list div{{padding:2px 0}}

/* 空态 */
.empty{{text-align:center;color:#8893a7;padding:48px 0;font-size:14px}}

/* 返回任务清单 */
.back-link{{display:inline-flex;align-items:center;gap:4px;font-size:12px;color:#3b6fb0;text-decoration:none;margin-bottom:5px}}
.back-link:hover{{text-decoration:underline}}

/* 排序 */
.sort-bar{{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}}
.sort-btn{{font-size:12px;color:#5a6577;cursor:pointer;padding:3px 10px;border-radius:12px;border:1px solid transparent;transition:all .15s}}
.sort-btn:hover{{border-color:#d8dee9}}
.sort-btn.on{{background:#e8eef8;color:#3b6fb0;border-color:#c8d8ee;font-weight:600}}

/* ---- 移动端适配 ---- */
@media (max-width: 640px) {{
  body {{ padding: 18px 14px 40px; }}
  .hdr {{ flex-direction: column; align-items: stretch; gap: 12px; }}
  .hdr > div:first-child {{ min-width: 0; }}
  .hdr h1 {{ font-size: 20px; }}
  .stats {{ width: 100%; }}
  .st {{ padding: 8px 6px; }}
  .sep {{ display: none; }}
  .task {{ padding: 14px; }}
  .task-hdr {{ flex-wrap: wrap; }}
  .rev-grid {{ grid-template-columns: 1fr; }}
  .review {{ padding: 16px; }}
  .modal {{ padding: 18px; }}
}}

/* 触屏没有 hover, 置顶与节点操作按钮默认太淡会点不到 */
@media (hover: none) {{
  .pin-btn, .node-act {{ opacity: .6; padding: 4px 6px; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div>
      <a class="back-link" href="https://www.jevylee.com/tasks_view.html">← 返回任务清单</a>
      <h1>🌳 任务流程跟踪树</h1>
      <div class="sub" id="sub"></div>
    </div>
    <div class="stats">
      <div class="st"><b id="st-done">-</b><span>已完成</span></div>
      <div class="st"><b id="st-inprog">-</b><span>进行中</span></div>
      <div class="st"><b id="st-notstart">-</b><span>未开始</span></div>
      <div class="st"><b id="st-avg">-</b><span>平均耗时(天)</span></div>
      <div class="st"><b id="st-max">-</b><span>最长耗时(天)</span></div>
    </div>
  </div>

  <div class="fbar">
    <span class="label">分类</span>
    <button class="fbtn on" data-cat="all">📋 全部</button>
    {cat_btns}
    <div class="sep"></div>
    <span class="label">状态</span>
    <button class="fbtn on" data-st="all">全部</button>
    <button class="fbtn" data-st="unfinished">⏳ 未完成<span class="cnt" id="cnt-unfinished"></span></button>
    {status_btns}
  </div>

  <div class="sort-bar">
    <span class="label" style="font-size:12px;color:#8893a7;font-weight:600">排序</span>
    <span class="sort-btn on" data-sort="default">默认</span>
    <span class="sort-btn" data-sort="priority">优先级</span>
    <span class="sort-btn" data-sort="days-desc">耗时↓</span>
    <span class="sort-btn" data-sort="days-asc">耗时↑</span>
    <span class="sort-btn" data-sort="date">创建时间</span>
  </div>

  <div id="trees"></div>

  <div class="review" id="review">
    <h2>📊 复盘分析</h2>
    <div class="rev-grid" id="rev-grid"></div>
  </div>
</div>

<script>
let TASKS = [];
const EMBEDDED_TASKS = {data_json};
const CAT_ORDER = {js(cats)};
const CAT_ICON = {js(CATEGORY_ICON)};
const ST_META = {js(STATUS_META)};
const PRI_META = {pri_meta_json};
const PRI_ORD = {js({k: i for i, k in enumerate(PRIORITY_ORDER)})};

let curCat = 'all', curSt = 'all', curSort = 'default';

function fmtDate(s) {{
  if (!s) return '-';
  const m = String(s).match(/(\\d{{4}})\\/(\\d{{1,2}})\\/(\\d{{1,2}})/);
  return m ? `${{m[1]}}/${{m[2].padStart(2,'0')}}/${{m[3].padStart(2,'0')}}` : s;
}}

function shortDate(s) {{
  if (!s) return '-';
  const m = String(s).match(/(\\d{{1,2}})\\/(\\d{{1,2}})/);
  return m ? `${{m[1]}}/${{m[2]}}` : s;
}}

function nodeClass(phase, stalled) {{
  if (stalled && (phase === '当前' || phase === '推进')) return 'stalled';
  if (phase === '创建') return 'create';
  if (phase === '完成') return 'done';
  if (phase === '当前') return 'current';
  return 'progress';
}}

function progColor(p) {{
  if (p >= 80) return '#2e9e5b';
  if (p >= 40) return '#d29922';
  return '#d6453d';
}}

// HTML 转义: 任务名 / 备注 / 负责人 等可能含 < > & " , 直接插值会破版
function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}}

function renderTree(t) {{
  const sm = ST_META[t.status] || ST_META['进行中'];
  const pm = PRI_META[t.priority] || PRI_META.medium;
  const timeLabel = t.finished
    ? `总耗时 <b>${{t.total_days}}</b> 天`
    : `已耗时 <b>${{t.total_days}}</b> 天`;

  // 计划周期标签(已完成的任务不再提示)
  let planTag = '';
  if (!t.finished) {{
    if (t.due) {{
      const cls = t.delayed ? 'plan-tag over' : 'plan-tag';
      const tail = t.delayed
        ? ('已延期 ' + Math.abs(t.days_left) + ' 天')
        : (t.days_left === 0 ? '今天到期' : ('剩 ' + t.days_left + ' 天'));
      planTag = `<span class="${{cls}}" title="计划 ${{t.start || '未设'}} → ${{t.due}}">📅 ${{t.due}} · ${{tail}}</span>`;
    }} else {{
      planTag = '<span class="plan-tag none">📅 未设计划截止</span>';
    }}
  }}

  let nodesHtml = '';
  for (let _ni = 0; _ni < t.nodes.length; _ni++) {{
    const n = t.nodes[_ni];
    const nc = nodeClass(n.phase, t.stalled);
    const gapHtml = n.days_from_prev != null
      ? `<span class="node-gap">⏱ ${{n.days_from_prev}}天</span>` : '';
    const warn_html = (t.stalled && n.phase === '当前') ? '<span class="node-warn">⚠️ 疑似停滞</span>' : '';
    const pColor = progColor(n.progress);
    const noteHtml = n.note ? `<div class="node-note">${{esc(n.note)}}</div>` : '';
    const ownerHtml = n.owner ? `<span class="node-owner">👤 ${{esc(n.owner)}}</span>` : '';
    const actHtml = t.json_backed ? `<span class="node-actions"><span class="node-act edit" title="编辑" onclick="openEditNode('${{esc(t.no)}}',${{_ni}})">✏️</span><span class="node-act del" title="删除" onclick="deleteNode('${{esc(t.no)}}',${{_ni}})">🗑️</span></span>` : '';
    nodesHtml += `
      <div class="node">
        <div class="node-dot ${{nc}}"></div>
        <div class="node-row">
          <span class="node-phase">[${{n.phase}}]</span>
          <span class="node-date">${{fmtDate(n.date)}}</span>
          <span class="node-prog" style="color:${{pColor}}">${{n.progress}}%</span>
          ${{gapHtml}}${{warn_html}}${{ownerHtml}}${{actHtml}}
        </div>
        ${{noteHtml}}
      </div>`;
  }}

  const summaryHtml = `
    <div class="summary">
      📊 ${{t.finished ? '全流程总耗时' : '已耗时'}}: <b>${{t.total_days}}天</b>
      ${{t.stalled ? '&nbsp;<span class="node-warn">⚠️ 疑似停滞</span>' : ''}}
      ${{!t.finished ? `<span class="add-btn" onclick="openAddNode('${{esc(t.no)}}')">＋ 添加节点</span>` : ''}}
    </div>`;

  return `
    <div class="task${{t.pinned ? ' pinned' : ''}}" data-no="${{t.no}}" data-cat="${{t.category}}" data-st="${{t.status}}" data-pri="${{t.priority}}" data-days="${{t.total_days}}" data-date="${{t.date}}">
      <div class="task-hdr">
        <div class="task-title">
          <span class="sicon">${{sm.icon}}</span>
          <span class="tname">${{esc(t.name)}}</span>
          <span class="tno">No.${{esc(t.no)}}</span>
        </div>
        <div class="task-meta">
          ${{planTag}}
          <span class="badge" style="color:${{pm[1]}};background:${{pm[1]}}18">${{pm[0]}}优先级</span>
          <span class="time-tag">${{timeLabel}}</span>
          <span class="pin-btn${{t.pinned ? ' on' : ''}}" title="${{t.pinned ? '取消置顶' : '置顶：设为当前重点'}}" onclick="togglePin('${{esc(t.no)}}')">📌</span>
        </div>
      </div>
      <div class="tree">${{nodesHtml}}</div>
      ${{summaryHtml}}
    </div>`;
}}

function sortTasks(list) {{
  const sorted = [...list];
  switch (curSort) {{
    case 'priority':
      sorted.sort((a,b) => (PRI_ORD[a.priority]??1) - (PRI_ORD[b.priority]??1));
      break;
    case 'days-desc':
      sorted.sort((a,b) => b.total_days - a.total_days);
      break;
    case 'days-asc':
      sorted.sort((a,b) => a.total_days - b.total_days);
      break;
    case 'date':
      sorted.sort((a,b) => {{
        const da = (a.date||'').match(/(\\d{{4}})\\/(\\d+)\\/(\\d+)/);
        const db = (b.date||'').match(/(\\d{{4}})\\/(\\d+)\\/(\\d+)/);
        if (!da || !db) return 0;
        return (+da[1])*10000+(+da[2])*100+(+da[3]) - ((+db[1])*10000+(+db[2])*100+(+db[3]));
      }});
      break;
    default:
      sorted.sort((a,b) => (Number(a.no)||0) - (Number(b.no)||0));
  }}
  return sorted;
}}

function render() {{
  const container = document.getElementById('trees');
  const filtered = TASKS.filter(t => {{
    if (curCat !== 'all' && t.category !== curCat) return false;
    if (curSt === 'unfinished') {{ if (t.finished) return false; }}
    else if (curSt !== 'all' && t.status !== curSt) return false;
    return true;
  }});

  if (!filtered.length) {{
    container.innerHTML = '<div class="empty">该筛选下暂无任务</div>';
    return;
  }}

  let html = '';

  // 置顶区: 跨分类排在最前, 便于聚焦当前重点
  const pinned = sortTasks(filtered.filter(t => t.pinned));
  if (pinned.length) {{
    const hint = pinned.length > 1 ? '<span class="pin-hint">· 建议一次只聚焦 1 个</span>' : '';
    html += `
      <div class="cat-group pin-group">
        <div class="cat-hdr" onclick="this.classList.toggle('collapsed');this.nextElementSibling.classList.toggle('hide')">
          <span class="icon">📌</span>
          <span class="name">当前重点</span>
          <span class="cnt">${{pinned.length}} 个任务</span>
          ${{hint}}
          <span class="arrow">▼</span>
        </div>
        <div class="cat-body">
          ${{pinned.map(renderTree).join('')}}
        </div>
      </div>`;
  }}

  // 分类分组: 置顶的任务只在上面出现, 不在分类里重复
  const rest = filtered.filter(t => !t.pinned);
  const catList = CAT_ORDER.slice();
  for (const t of rest) {{
    if (t.category && !catList.includes(t.category)) catList.push(t.category);
  }}
  for (const cat of catList) {{
    const items = sortTasks(rest.filter(t => t.category === cat));
    if (!items.length) continue;
    const icon = CAT_ICON[cat] || '📁';
    const doneCnt = items.filter(t => t.finished).length;
    html += `
      <div class="cat-group">
        <div class="cat-hdr" onclick="this.classList.toggle('collapsed');this.nextElementSibling.classList.toggle('hide')">
          <span class="icon">${{icon}}</span>
          <span class="name">${{cat}}</span>
          <span class="cnt">${{items.length}} 个 · 已完成 ${{doneCnt}}</span>
          <span class="arrow">▼</span>
        </div>
        <div class="cat-body">
          ${{items.map(renderTree).join('')}}
        </div>
      </div>`;
  }}

  container.innerHTML = html;
}}

function renderReview() {{
  const grid = document.getElementById('rev-grid');
  const total = TASKS.length;
  const done = TASKS.filter(t => t.finished);
  const inProg = TASKS.filter(t => t.status === '进行中');
  const notStart = TASKS.filter(t => t.status === '未开始');

  // 1. 按分类统计
  let catHtml = '';
  for (const cat of CAT_ORDER) {{
    const ct = TASKS.filter(t => t.category === cat);
    if (!ct.length) continue;
    const cd = ct.filter(t => t.finished);
    const avg = cd.length ? (cd.reduce((s,t) => s+t.total_days, 0) / cd.length).toFixed(1) : '-';
    catHtml += `<div class="rev-row"><span>${{CAT_ICON[cat]||''}} ${{cat}}</span><b>${{ct.length}}个 / 完成${{cd.length}} / 均${{avg}}天</b></div>`;
  }}

  // 2. 超期 TOP5
  const topLong = [...done].sort((a,b) => b.total_days - a.total_days).slice(0, 5);
  let longHtml = topLong.map((t,i) =>
    `<div>${{i+1}}. ${{esc(t.name)}} — <b>${{t.total_days}}天</b></div>`
  ).join('') || '<div>暂无</div>';

  // 3. 停滞任务
  const stalled = TASKS.filter(t => t.stalled);
  let stalledHtml = stalled.length
    ? stalled.map(t => `<div>⚠️ ${{esc(t.name)}} — 已${{t.total_days}}天</div>`).join('')
    : '<div>暂无停滞任务 👍</div>';

  // 4. 优先级倒挂
  const lowDone = TASKS.filter(t => t.priority === 'low' && t.finished);
  const highUndone = TASKS.filter(t => t.priority === 'high' && !t.finished);
  let invertHtml = '';
  if (highUndone.length && lowDone.length) {{
    invertHtml = highUndone.map(t =>
      `<div>🔴 ${{esc(t.name)}} (高优未完成) ←→ ${{esc(lowDone.find(d=>true)?.name || '')}} (低优已完成)</div>`
    ).join('');
  }} else {{
    invertHtml = '<div>暂无倒挂 ✅</div>';
  }}

  grid.innerHTML = `
    <div class="rev-card">
      <h3>📂 按分类统计</h3>
      ${{catHtml}}
    </div>
    <div class="rev-card">
      <h3>🐢 超期任务 TOP5</h3>
      <div class="rev-list">${{longHtml}}</div>
    </div>
    <div class="rev-card">
      <h3>⚠️ 停滞任务</h3>
      <div class="rev-list">${{stalledHtml}}</div>
    </div>
    <div class="rev-card">
      <h3>🔄 优先级倒挂</h3>
      <div class="rev-list">${{invertHtml}}</div>
    </div>
  `;
}}

// 事件绑定
document.querySelector('.fbar').addEventListener('click', e => {{
  const btn = e.target.closest('.fbtn');
  if (!btn) return;
  if (btn.dataset.cat !== undefined) {{
    curCat = btn.dataset.cat;
    document.querySelectorAll('.fbtn[data-cat]').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
  }}
  if (btn.dataset.st !== undefined) {{
    curSt = btn.dataset.st;
    document.querySelectorAll('.fbtn[data-st]').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
  }}
  render();
}});

document.querySelector('.sort-bar').addEventListener('click', e => {{
  const btn = e.target.closest('.sort-btn');
  if (!btn) return;
  curSort = btn.dataset.sort;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  render();
}});

// 动态加载数据并渲染
function updateStats() {{
  const total = TASKS.length;
  const done = TASKS.filter(t => t.finished).length;
  const inProg = TASKS.filter(t => t.status === '\u8fdb\u884c\u4e2d').length;
  const notStart = TASKS.filter(t => t.status === '\u672a\u5f00\u59cb').length;
  const unfinished = total - done;
  const doneTasks = TASKS.filter(t => t.finished);
  const avgDays = doneTasks.length ? (doneTasks.reduce((s,t) => s + t.total_days, 0) / doneTasks.length).toFixed(1) : '0';
  const maxDays = doneTasks.length ? Math.max(...doneTasks.map(t => t.total_days)) : 0;
  const sub = document.getElementById('sub');
  if (sub) sub.textContent = '\u5171 ' + total + ' \u4e2a\u4efb\u52a1 \u00b7 \u6570\u636e\u622a\u81f3 ' + new Date().toISOString().slice(0,10).replace(/-/g, '/');
  const setTxt = (id, v) => {{ const el = document.getElementById(id); if (el) el.textContent = v; }};
  setTxt('st-done', done);
  setTxt('st-inprog', inProg);
  setTxt('st-notstart', notStart);
  setTxt('st-avg', avgDays);
  setTxt('st-max', maxDays);
  setTxt('cnt-unfinished', unfinished);
}}

// ------- 页面内提示条 / 确认框 (原生 alert/confirm 在部分内嵌预览里会被屏蔽) -------
let toastTimer = null;
function toast(msg, type) {{
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'on' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {{ el.className = ''; }}, 2800);
}}

let confirmCb = null;
function confirmBox(msg, onOk, okText) {{
  confirmCb = onOk;
  document.getElementById('cfm-msg').innerHTML = msg;
  document.getElementById('cfm-ok').textContent = okText || '确定';
  document.getElementById('cfm-bg').classList.remove('hide');
}}

function closeConfirm() {{
  document.getElementById('cfm-bg').classList.add('hide');
  confirmCb = null;
}}

// 确认框按钮在 DOM 就绪后绑定(脚本位于弹窗 DOM 之前)
document.addEventListener('DOMContentLoaded', () => {{
  const ok = document.getElementById('cfm-ok');
  if (ok) ok.onclick = () => {{ const fn = confirmCb; closeConfirm(); if (fn) fn(); }};
}});

// ------- 置顶(当前重点) -------
function togglePin(no) {{
  const t = TASKS.find(x => String(x.no) === String(no));
  if (!t) {{ toast('任务不存在', 'err'); return; }}
  const next = !t.pinned;
  fetch('/api/pin_task', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{no: String(no), pinned: next}})
  }}).then(r => r.json()).then(d => {{
    if (!d.ok) {{ toast(d.error || '操作失败', 'err'); return; }}
    t.pinned = next;        // 本地同步后重绘, 不必整页刷新
    render();
    toast(next ? '已置顶：No.' + no + ' ' + t.name : '已取消置顶：No.' + no, next ? 'ok' : '');
  }}).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}}

function loadDataAndRender() {{
  fetch('/api/tasks').then(r => r.json()).then(data => {{
    TASKS = data;
    updateStats();
    render();
    renderReview();
    // URL 参数 ?task=No. 自动定位并高亮任务
    const params = new URLSearchParams(window.location.search);
    const taskNo = params.get('task');
    if (taskNo) {{
      setTimeout(() => {{
        const el = document.querySelector(`.task[data-no="${{taskNo}}"]`);
        if (el) {{
          el.classList.add('highlight');
          el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
          setTimeout(() => el.classList.remove('highlight'), 3000);
        }}
      }}, 100);
    }}
  }}).catch(() => {{
    // 如果 API 不可用，使用嵌入数据（file:// 模式）
    TASKS = EMBEDDED_TASKS;
    updateStats();
    render();
    renderReview();
  }});
}}
loadDataAndRender();

// 添加节点弹窗 (任务名在函数内查, 不再由 onclick 传参 —— 名字里的引号会破坏 onclick 属性)
function openAddNode(no) {{
  const t = TASKS.find(x => String(x.no) === String(no));
  document.getElementById('modal-no').value = no;
  document.getElementById('modal-name').textContent = 'No.' + no + ' ' + (t ? t.name : '');
  // <input type="date"> 只接受 YYYY-MM-DD, 写成 2026/09/17 会被浏览器丢弃(输入框空白)
  document.getElementById('modal-date').value = new Date().toISOString().slice(0, 10);
  document.getElementById('modal-progress').value = '';
  document.getElementById('modal-note').value = '';
  document.getElementById('modal-owner').value = '';
  document.getElementById('modal-bg').classList.remove('hide');
}}
function closeModal() {{
  document.getElementById('modal-bg').classList.add('hide');
}}
function submitNode() {{
  const no = document.getElementById('modal-no').value;
  const phase = document.getElementById('modal-phase').value;
  const dateVal = document.getElementById('modal-date').value.replace(/-/g, '/');   // 数据统一存 YYYY/MM/DD
  const progress = document.getElementById('modal-progress').value;
  const note = document.getElementById('modal-note').value;
  const owner = document.getElementById('modal-owner').value;
  if (!dateVal || progress === '') {{ toast('请填写日期和进度', 'err'); return; }}
  fetch('/api/add_node', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{no, phase, date: dateVal, progress: parseInt(progress), note, owner}})
  }}).then(r => r.json()).then(data => {{
    if (data.ok) {{
      toast('节点已添加', 'ok');
      setTimeout(() => location.reload(), 600);
    }} else toast(data.error || '添加失败', 'err');
  }}).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}}
// 点击背景关闭弹窗
document.addEventListener('click', e => {{
  if (e.target.id === 'modal-bg') closeModal();
  if (e.target.id === 'edit-modal-bg') closeEditModal();
  if (e.target.id === 'cfm-bg') closeConfirm();
}});

// 编辑节点弹窗
function openEditNode(no, idx) {{
  const task = TASKS.find(t => t.no === no);
  if (!task || !task.json_backed) return;
  const node = task.nodes[idx];
  document.getElementById('edit-no').value = no;
  document.getElementById('edit-idx').value = idx;
  document.getElementById('edit-name').textContent = 'No.' + no + ' ' + task.name;
  document.getElementById('edit-phase').value = node.phase;
  document.getElementById('edit-date').value = node.date.replace(/(\\d{{4}})\\/(\\d+)\\/(\\d+)/, (m,y,mo,d) => y + '-' + String(mo).padStart(2,'0') + '-' + String(d).padStart(2,'0'));
  document.getElementById('edit-progress').value = node.progress;
  document.getElementById('edit-note').value = node.note || '';
  document.getElementById('edit-owner').value = node.owner || '';
  document.getElementById('edit-modal-bg').classList.remove('hide');
}}
function closeEditModal() {{
  document.getElementById('edit-modal-bg').classList.add('hide');
}}
function submitEdit() {{
  const no = document.getElementById('edit-no').value;
  const idx = parseInt(document.getElementById('edit-idx').value);
  const phase = document.getElementById('edit-phase').value;
  const dateVal = document.getElementById('edit-date').value.replace(/-/g, '/');
  const progress = document.getElementById('edit-progress').value;
  const note = document.getElementById('edit-note').value;
  const owner = document.getElementById('edit-owner').value;
  if (!dateVal || progress === '') {{ toast('请填写日期和进度', 'err'); return; }}
  fetch('/api/edit_node', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{no, index: idx, phase, date: dateVal, progress: parseInt(progress), note, owner}})
  }}).then(r => r.json()).then(data => {{
    if (data.ok) {{
      toast('节点已更新', 'ok');
      setTimeout(() => location.reload(), 600);
    }} else toast(data.error || '编辑失败', 'err');
  }}).catch(() => toast('连接服务器失败', 'err'));
}}

// 删除节点 (自绘确认框: 原生 confirm 在内嵌预览里被屏蔽且恒返回 false)
function deleteNode(no, idx) {{
  const t = TASKS.find(x => String(x.no) === String(no));
  const node = (t && t.nodes) ? t.nodes[idx] : null;
  const desc = node ? ('[' + node.phase + '] ' + node.date + ' · ' + node.progress + '%') : '该节点';
  const warn = (t && t.nodes && t.nodes.length === 1)
    ? '<br><span style="color:#d6453d">这是该任务的最后一个节点，删除后整个任务也会一并移除。</span>' : '';
  confirmBox('确认删除节点 ' + desc + '？' + warn, () => {{
    fetch('/api/delete_node', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{no, index: idx}})
    }}).then(r => r.json()).then(data => {{
      if (data.ok) {{
        toast('节点已删除', 'ok');
        setTimeout(() => location.reload(), 600);
      }} else toast(data.error || '删除失败', 'err');
    }}).catch(() => toast('连接服务器失败', 'err'));
  }}, '删除');
}}
</script>

<!-- 添加节点弹窗 -->
<div id="modal-bg" class="modal-bg hide">
  <div class="modal">
    <h3>＋ 添加流程节点</h3>
    <div id="modal-name" style="font-size:13px;color:#5a6577;margin-bottom:8px"></div>
    <input type="hidden" id="modal-no">
    <label>阶段</label>
    <select id="modal-phase">
      <option value="推进">推进</option>
      <option value="完成">完成</option>
    </select>
    <label>日期</label>
    <input type="date" id="modal-date">
    <label>进度 (%)</label>
    <input type="number" id="modal-progress" min="0" max="100" placeholder="0-100">
    <label>责任人</label>
    <input type="text" id="modal-owner" placeholder="可选，如：张三">
    <label>备注</label>
    <textarea id="modal-note" placeholder="可选，记录本次推进内容"></textarea>
    <div class="modal-actions">
      <button onclick="closeModal()">取消</button>
      <button class="btn-primary" onclick="submitNode()">确认添加</button>
    </div>
  </div>
</div>

<!-- 编辑节点弹窗 -->
<div id="edit-modal-bg" class="modal-bg hide">
  <div class="modal">
    <h3>✏️ 编辑流程节点</h3>
    <div id="edit-name" style="font-size:13px;color:#5a6577;margin-bottom:8px"></div>
    <input type="hidden" id="edit-no">
    <input type="hidden" id="edit-idx">
    <label>阶段</label>
    <select id="edit-phase">
      <option value="创建">创建</option>
      <option value="推进">推进</option>
      <option value="当前">当前</option>
      <option value="完成">完成</option>
    </select>
    <label>日期</label>
    <input type="date" id="edit-date">
    <label>进度 (%)</label>
    <input type="number" id="edit-progress" min="0" max="100" placeholder="0-100">
    <label>责任人</label>
    <input type="text" id="edit-owner" placeholder="可选">
    <label>备注</label>
    <textarea id="edit-note" placeholder="可选"></textarea>
    <div class="modal-actions">
      <button onclick="closeEditModal()">取消</button>
      <button class="btn-primary" onclick="submitEdit()">保存修改</button>
    </div>
  </div>
</div>

<!-- 操作确认弹窗 (替代浏览器原生 confirm, 后者在部分内嵌预览里被屏蔽) -->
<div id="cfm-bg" class="modal-bg hide">
  <div class="modal" style="width:370px">
    <h3 id="cfm-title">确认操作</h3>
    <div id="cfm-msg" class="cfm-msg"></div>
    <div class="modal-actions">
      <button onclick="closeConfirm()">取消</button>
      <button class="btn-primary" id="cfm-ok" style="background:#d6453d;border-color:#d6453d">确定</button>
    </div>
  </div>
</div>

<div id="toast"></div>
</body>
</html>
"""


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="生成任务流程跟踪树页面")
    parser.add_argument("--open", action="store_true", help="生成后打开浏览器")
    args = parser.parse_args()

    tasks = read_tasks()
    if not tasks:
        print(f"[错误] {TASK_FLOWS_JSON} 中没有可展示的任务数据")
        sys.exit(1)

    html = build_html(tasks)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    done = sum(1 for t in tasks if t["finished"])
    print(f"[完成] 已生成: {OUT_HTML}")
    print(f"       任务总数: {len(tasks)}, 已完成: {done}, 进行中: {len(tasks) - done}")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(OUT_HTML).replace("\\", "/"))


if __name__ == "__main__":
    main()
