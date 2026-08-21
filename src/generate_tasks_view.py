"""
generate_tasks_view.py
生成 tasks.csv 的可视化筛选页面 (HTML)。

功能:
    读取 data/tasks.csv, 生成 output/tasks_view.html。
    页面顶部提供筛选按钮: 已完成任务 / 未完成任务 / 高优先级 / 中优先级 / 低优先级,
    点击后前端 JS 即时筛选显示任务卡片。
    排序规则: 高优先级 → 中优先级 → 低优先级; "全部"标签下未完成任务排前, 已完成排后。

用法:
    python3 src/generate_tasks_view.py            # 生成页面
    python3 src/generate_tasks_view.py --open     # 生成后打开浏览器
"""

import argparse
import csv
import json
import os
import re
import sys
import webbrowser

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录（src/ 的父目录）
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "tasks_view.html")

TASKS_CSV = os.path.join(DATA_DIR, "tasks.csv")

# 优先级显示信息: (中文标签, 主题色, 浅色底) —— 供浅色主题徽章使用
PRIORITY_META = {
    "high": ("高优先级", "#d6453d", "#fdeceb"),
    "medium": ("中优先级", "#3b6fb0", "#e8eef8"),
    "low": ("低优先级", "#2e9e5b", "#e7f4ec"),
}


def read_tasks():
    """读取 tasks.csv, 按 No. 去重并保留最新日期记录。

    返回: 任务 dict 列表, 每个含:
        no, name, date, yesterday, today, priority, finished, completed_date
    """
    if not os.path.exists(TASKS_CSV):
        print(f"[错误] 文件不存在: {TASKS_CSV}")
        sys.exit(1)

    with open(TASKS_CSV, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if (r.get("task_name") or "").strip()]

    def norm_date(v):
        m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", (v or "").strip())
        return m.groups() if m else ("0", "0", "0")

    # 按 No. 去重: 同一任务保留日期最新的一条记录
    task_map = {}
    for r in rows:
        no = (r.get("No.") or "").strip()
        if not no:
            continue
        if no not in task_map or norm_date(r.get("date")) > norm_date(task_map[no].get("date")):
            task_map[no] = r

    def to_int(v):
        try:
            return int(float((v or "0").strip() or 0))
        except (ValueError, TypeError):
            return 0

    tasks = []
    for r in task_map.values():
        finished = (r.get("finished") or "").strip().lower() == "yes"
        tasks.append({
            "no": (r.get("No.") or "").strip(),
            "name": (r.get("task_name") or "").strip(),
            "date": (r.get("date") or "").strip(),
            "yesterday": to_int(r.get("yesterday progress")),
            "today": to_int(r.get("today progress")),
            "priority": (r.get("priority") or "medium").strip().lower(),
            "finished": finished,
            "completed_date": (r.get("completed date") or "").strip(),
        })
    return tasks


def build_html(tasks):
    """拼装筛选可视化页面 HTML (数据内嵌, 双击即可用, 白底浅色主题)。"""
    # 按 No. 升序
    tasks = sorted(tasks, key=lambda t: int(t["no"]) if t["no"].isdigit() else 0)
    data_json = json.dumps(tasks, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")  # 防止 </script> 注入破坏页面

    total = len(tasks)
    done = sum(1 for t in tasks if t["finished"])
    pending = total - done
    # 高/中/低优先级按钮只统计未完成任务
    high = sum(1 for t in tasks if t["priority"] == "high" and not t["finished"])
    medium = sum(1 for t in tasks if t["priority"] == "medium" and not t["finished"])
    low = sum(1 for t in tasks if t["priority"] == "low" and not t["finished"])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>任务清单</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #f5f6f8;
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
    color: #1f2733;
    min-height: 100vh;
    padding: 28px 20px 48px;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}

  /* 顶部 */
  .header {{
    display: flex; align-items: flex-end; justify-content: space-between;
    margin-bottom: 18px;
  }}
  .title {{ font-size: 26px; font-weight: 700; color: #1f2733; letter-spacing: 1px; }}
  .subtitle {{ font-size: 13px; color: #5a6577; margin-top: 6px; }}
  .stats {{ display: flex; gap: 10px; }}
  .stat {{
    background: #ffffff; border: 1px solid #e3e8f0; border-radius: 10px;
    padding: 8px 14px; text-align: center; min-width: 76px;
  }}
  .stat b {{ display: block; font-size: 20px; color: #1f2733; }}
  .stat span {{ font-size: 11px; color: #5a6577; }}

  /* 筛选按钮 */
  .filters {{
    display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px;
  }}
  .filter-btn {{
    background: #ffffff; color: #3a4456;
    border: 1px solid #d8dee9; border-radius: 20px;
    padding: 7px 16px; font-size: 13px; cursor: pointer;
    transition: all .15s ease; user-select: none;
  }}
  .filter-btn:hover {{ border-color: #60a5fa; color: #1f2733; }}
  .filter-btn.active {{
    background: #3b6fb0; border-color: #3b6fb0; color: #ffffff; font-weight: 600;
  }}
  .filter-btn .cnt {{ opacity: .65; margin-left: 4px; font-weight: 400; }}

  /* 任务卡片 */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }}
  .card {{
    background: #ffffff; border: 1px solid #e3e8f0; border-radius: 12px;
    padding: 14px 16px; display: flex; flex-direction: column; gap: 10px;
    transition: all .2s ease;
  }}
  .card:hover {{ border-color: #c8d1de; transform: translateY(-2px); }}
  .card.hidden {{ display: none; }}
  .card.done {{ border-left: 3px solid #2e9e5b; }}
  .card.todo {{ border-left: 3px solid #d29922; }}

  .card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }}
  .card-no {{ font-size: 11px; color: #8893a7; margin-bottom: 3px; }}
  .card-name {{ font-size: 15px; font-weight: 600; color: #1f2733; line-height: 1.4; }}
  .badge {{
    flex: none; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 12px;
  }}

  .progress-row {{ display: flex; align-items: center; gap: 10px; }}
  .bar {{ flex: 1; height: 8px; background: #eef1f6; border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; transition: width .3s ease; }}
  .bar-pct {{ font-size: 13px; font-weight: 700; color: #1f2733; width: 42px; text-align: right; }}

  .card-meta {{ display: flex; justify-content: space-between; font-size: 11px; color: #8893a7; }}
  .meta-done {{ color: #2e9e5b; }}
  .meta-time {{ color: #3b6fb0; }}
  .empty {{ text-align: center; color: #8893a7; padding: 60px 0; font-size: 14px; grid-column: 1 / -1; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div>
      <div class="title">任务清单</div>
      <div class="subtitle">共 {total} 个任务 · 已完成 {done} · 进行中 {pending}</div>
    </div>
    <div class="stats">
      <div class="stat"><b>{done}</b><span>已完成</span></div>
      <div class="stat"><b>{pending}</b><span>进行中</span></div>
    </div>
  </div>

  <div class="filters" id="filters">
    <button class="filter-btn active" data-filter="all">全部<span class="cnt">{total}</span></button>
    <button class="filter-btn" data-filter="done">已完成任务<span class="cnt">{done}</span></button>
    <button class="filter-btn" data-filter="todo">未完成任务<span class="cnt">{pending}</span></button>
    <button class="filter-btn" data-filter="high">高优先级<span class="cnt">{high}</span></button>
    <button class="filter-btn" data-filter="medium">中优先级<span class="cnt">{medium}</span></button>
    <button class="filter-btn" data-filter="low">低优先级<span class="cnt">{low}</span></button>
  </div>

  <div class="grid" id="grid"></div>
</div>

<script>
const TASKS = {data_json};

const PRIORITY = {{
  high: {{ label: '高优先级', color: '#d6453d', bg: '#fdeceb' }},
  medium: {{ label: '中优先级', color: '#3b6fb0', bg: '#e8eef8' }},
  low: {{ label: '低优先级', color: '#2e9e5b', bg: '#e7f4ec' }},
}};
const PRIO_ORDER = {{ high: 0, medium: 1, low: 2 }};

// 任务创建时间转可比较数值 (YYYY/MM/DD)
function dateVal(t) {{
  const m = String(t.date || '').match(/^(\\d{{4}})\\/(\\d{{1,2}})\\/(\\d{{1,2}})/);
  return m ? (+m[1]) * 10000 + (+m[2]) * 100 + (+m[3]) : 0;
}}

// 解析 YYYY/MM/DD 为本地日期
function parseDate(s) {{
  const m = String(s || '').match(/^(\\d{{4}})\\/(\\d{{1,2}})\\/(\\d{{1,2}})/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}}

// 任务执行时间(天): 已完成=创建日→完成日, 未完成=创建日→今天
function execDays(t) {{
  const start = parseDate(t.date);
  const end = t.finished ? parseDate(t.completed_date) : new Date();
  if (!start || !end) return null;
  return Math.round((end - start) / 86400000) + 1;
}}

function matches(t, f) {{
  switch (f) {{
    case 'all': return true;
    case 'done': return t.finished;
    case 'todo': return !t.finished;
    case 'high': return t.priority === 'high' && !t.finished;
    case 'medium': return t.priority === 'medium' && !t.finished;
    case 'low': return t.priority === 'low' && !t.finished;
    default: return true;
  }}
}}

function render(filter) {{
  const grid = document.getElementById('grid');
  if (!grid) return;
  const list = TASKS.filter(t => matches(t, filter));
  // 排序: 高 → 中 → 低优先级; "全部"标签下未完成任务在前
  list.sort((a, b) => {{
    // 高/中/低优先级标签: 只显示未完成任务, 按创建时间(升序)排序
    if (filter === 'high' || filter === 'medium' || filter === 'low') {{
      return dateVal(a) - dateVal(b);
    }}
    const pa = PRIO_ORDER[a.priority] != null ? PRIO_ORDER[a.priority] : 1;
    const pb = PRIO_ORDER[b.priority] != null ? PRIO_ORDER[b.priority] : 1;
    if (pa !== pb) return pa - pb;
    if (filter === 'all' && a.finished !== b.finished) return a.finished ? 1 : -1;
    return (Number(a.no) || 0) - (Number(b.no) || 0);
  }});
  if (!list.length) {{
    grid.innerHTML = '<div class="empty">该筛选下暂无任务</div>';
    return;
  }}
  grid.innerHTML = list.map(t => {{
    const p = PRIORITY[t.priority] || PRIORITY.medium;
    const days = execDays(t);
    const status = t.finished
      ? '<span class="meta-done">✓ 已完成' + (t.completed_date ? ' · ' + t.completed_date : '') + '</span>'
      : '<span>进行中</span>';
    const timeInfo = days != null
      ? '<span class="meta-time">' + (t.finished ? '执行时间：' + days + ' 天' : '已进行 ' + days + ' 天') + '</span>'
      : '';
    return `
      <div class="card ${{t.finished ? 'done' : 'todo'}}">
        <div class="card-head">
          <div>
            <div class="card-no">No.${{t.no}} · 创建于 ${{t.date}}</div>
            <div class="card-name">${{t.name}}</div>
          </div>
          <span class="badge" style="color:${{p.color}};background:${{p.bg}}">${{p.label}}</span>
        </div>
        <div class="progress-row">
          <div class="bar"><div class="bar-fill" style="width:${{t.today}}%;background:${{p.color}}"></div></div>
          <span class="bar-pct">${{t.today}}%</span>
        </div>
        <div class="card-meta">${{status}}${{timeInfo}}</div>
      </div>`;
  }}).join('');
}}

function init() {{
  const filtersEl = document.getElementById('filters');
  if (!filtersEl) return;
  filtersEl.addEventListener('click', e => {{
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    render(btn.dataset.filter);
  }});
  render('all');
}}

// 等 DOM 就绪再初始化, 避免元素未加载时出现空引用
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', init);
}} else {{
  init();
}}
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 tasks.csv 可视化筛选页面")
    parser.add_argument("--open", action="store_true", help="生成后打开浏览器")
    args = parser.parse_args()

    tasks = read_tasks()
    if not tasks:
        print(f"[错误] {TASKS_CSV} 中没有可展示的任务数据")
        sys.exit(1)

    html = build_html(tasks)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[完成] 已生成: {OUT_HTML}")
    print(f"       任务总数: {len(tasks)}, "
          f"已完成: {sum(1 for t in tasks if t['finished'])}, "
          f"进行中: {sum(1 for t in tasks if not t['finished'])}")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(OUT_HTML).replace("\\", "/"))


if __name__ == "__main__":
    main()
