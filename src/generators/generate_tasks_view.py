"""
generate_tasks_view.py
生成 task_flows.json 的可视化筛选页面 (HTML)。

功能:
    读取 data/task_flows.json, 生成 output/tasks/tasks_view.html。
    页面顶部提供筛选按钮: 已完成任务 / 未完成任务 / 高优先级 / 中优先级 / 低优先级,
    点击后前端 JS 即时筛选显示任务卡片。
    排序规则: 高优先级 → 中优先级 → 低优先级; "全部"标签下未完成任务排前, 已完成排后。

用法:
    python3 src/generators/generate_tasks_view.py            # 生成页面
    python3 src/generators/generate_tasks_view.py --open     # 生成后打开浏览器
"""

import argparse
import json
import os
import re
import sys
import webbrowser

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录（src/generators/ 的祖父目录）
OUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "tasks_view.html")

# 优先级显示信息: (中文标签, 主题色, 浅色底) —— 供浅色主题徽章使用
PRIORITY_META = {
    "high": ("高优先级", "#d6453d", "#fdeceb"),
    "medium": ("中优先级", "#3b6fb0", "#e8eef8"),
    "low": ("低优先级", "#2e9e5b", "#e7f4ec"),
}

# 复用 generate_task_flow 的 read_tasks（单一数据源: task_flows.json）
GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from generate_task_flow import read_tasks


def build_html(tasks):
    """拼装筛选可视化页面 HTML (数据内嵌, 双击即可用, 白底浅色主题)。"""
    # 按 No. 升序
    tasks = sorted(tasks, key=lambda t: int(t["no"]) if t["no"].isdigit() else 0)
    data_json = json.dumps(tasks, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")  # 防止 </script> 注入破坏页面

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
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", system-ui, sans-serif;
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
  .flow-link {{ font-size: 14px; text-decoration: none; cursor: pointer; opacity: .5; transition: opacity .15s }}
  .flow-link:hover {{ opacity: 1 }}
  .del-task {{ font-size: 13px; cursor: pointer; opacity: .35; transition: opacity .15s; border: none; background: none; padding: 0 2px }}
  .del-task:hover {{ opacity: 1; color: #d6453d }}
  .done-task {{ font-size: 13px; cursor: pointer; opacity: .35; transition: opacity .15s; border: none; background: none; padding: 0 2px }}
  .done-task:hover {{ opacity: 1; color: #2e9e5b }}
  .empty {{ text-align: center; color: #8893a7; padding: 60px 0; font-size: 14px; grid-column: 1 / -1; }}

  /* 添加任务按钮 */
  .add-task-btn {{
    background: #3b6fb0; color: #fff; border: none; border-radius: 20px;
    padding: 8px 18px; font-size: 13px; cursor: pointer; font-weight: 600;
    transition: all .15s; margin-left: 12px;
  }}
  .add-task-btn:hover {{ background: #2d5a94; }}

  /* 弹窗 */
  .modal-bg {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }}
  .modal-bg.hide {{ display: none; }}
  .modal {{ background: #fff; border-radius: 14px; padding: 24px; width: 400px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,.12); }}
  .modal h3 {{ font-size: 16px; font-weight: 700; margin-bottom: 16px; color: #1f2733; }}
  .modal label {{ display: block; font-size: 12px; color: #5a6577; margin-bottom: 4px; margin-top: 12px; }}
  .modal input, .modal select, .modal textarea {{ width: 100%; padding: 8px 10px; border: 1px solid #d8dee9; border-radius: 8px; font-size: 13px; box-sizing: border-box; font-family: inherit; }}
  .modal textarea {{ resize: vertical; min-height: 50px; }}
  .modal-actions {{ display: flex; gap: 10px; margin-top: 18px; justify-content: flex-end; }}
  .modal-actions button {{ padding: 7px 18px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid #d8dee9; background: #fff; color: #3a4456; transition: all .15s; }}
  .modal-actions .btn-primary {{ background: #3b6fb0; color: #fff; border-color: #3b6fb0; }}
  .modal-actions .btn-primary:hover {{ background: #2d5a94; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div style="display:flex;align-items:center">
      <div>
        <div class="title">任务清单</div>
        <div class="subtitle" id="subtitle"></div>
      </div>
      <button class="add-task-btn" onclick="openAddTask()">＋ 添加任务</button>
    </div>
    <div class="stats">
      <div class="stat"><b id="stat-done">-</b><span>已完成</span></div>
      <div class="stat"><b id="stat-pending">-</b><span>进行中</span></div>
    </div>
  </div>

  <div class="filters" id="filters">
    <button class="filter-btn active" data-filter="all">全部<span class="cnt" id="cnt-all"></span></button>
    <button class="filter-btn" data-filter="done">已完成任务<span class="cnt" id="cnt-done"></span></button>
    <button class="filter-btn" data-filter="todo">未完成任务<span class="cnt" id="cnt-todo"></span></button>
    <button class="filter-btn" data-filter="high">高优先级<span class="cnt" id="cnt-high"></span></button>
    <button class="filter-btn" data-filter="medium">中优先级<span class="cnt" id="cnt-medium"></span></button>
    <button class="filter-btn" data-filter="low">低优先级<span class="cnt" id="cnt-low"></span></button>
  </div>

  <div class="grid" id="grid"></div>
</div>

<script>
let TASKS = [];
const EMBEDDED_TASKS = {data_json};

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
  if (!start) return null;
  if (t.finished) {{
    const end = parseDate(t.completed_date);
    if (!end) return null;
    return Math.round((end - start) / 86400000) + 1;
  }} else {{
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((today - start) / 86400000);
  }}
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
      ? '<span class="meta-time">' + (t.finished ? '执行时间：' + days + ' 天' : (days === 0 ? '今天创建' : '已进行 ' + days + ' 天')) + '</span>'
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
        <div class="card-meta">${{status}}${{timeInfo}}
          <a class="flow-link" href="task_flow.html?task=${{t.no}}" title="查看流程树">🌳</a>
                    ${{!t.finished ? '<button class="done-task" title="一键完成" onclick="completeTask(\\'' + t.no + '\\')">✅</button>' : ''}}
          <button class="del-task" title="删除任务" onclick="deleteTask('${{t.no}}','${{t.name.replace(/'/g, "\\'")}}')">🗑️</button>
        </div>
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
  // 动态加载数据
  loadData();
}}

function loadData() {{
  fetch('/api/tasks').then(r => r.json()).then(data => {{
    TASKS = data;
    updateStats();
    render('all');
  }}).catch(() => {{
    TASKS = EMBEDDED_TASKS;
    updateStats();
    render('all');
  }});
}}

function updateStats() {{
  const total = TASKS.length;
  const done = TASKS.filter(t => t.finished).length;
  const pending = total - done;
  const high = TASKS.filter(t => t.priority === 'high' && !t.finished).length;
  const medium = TASKS.filter(t => t.priority === 'medium' && !t.finished).length;
  const low = TASKS.filter(t => t.priority === 'low' && !t.finished).length;
  const sub = document.getElementById('subtitle');
  if (sub) sub.textContent = '\u5171 ' + total + ' \u4e2a\u4efb\u52a1 \u00b7 \u5df2\u5b8c\u6210 ' + done + ' \u00b7 \u8fdb\u884c\u4e2d ' + pending;
  const sd = document.getElementById('stat-done');
  if (sd) sd.textContent = done;
  const sp = document.getElementById('stat-pending');
  if (sp) sp.textContent = pending;
  const ids = {{ all: total, done: done, todo: pending, high: high, medium: medium, low: low }};
  for (const [k, v] of Object.entries(ids)) {{
    const el = document.getElementById('cnt-' + k);
    if (el) el.textContent = v;
  }}
}}

// 添加任务弹窗
function openAddTask() {{
  document.getElementById('task-name').value = '';
  document.getElementById('task-priority').value = 'medium';
  document.getElementById('task-category').value = '个人';
  document.getElementById('task-progress').value = '0';
  document.getElementById('task-note').value = '';
  document.getElementById('add-modal-bg').classList.remove('hide');
}}
function closeAddModal() {{
  document.getElementById('add-modal-bg').classList.add('hide');
}}
function submitTask() {{
  const name = document.getElementById('task-name').value.trim();
  const priority = document.getElementById('task-priority').value;
  const category = document.getElementById('task-category').value;
  const today = parseInt(document.getElementById('task-progress').value) || 0;
  const note = document.getElementById('task-note').value.trim();
  if (!name) {{ alert('请填写任务名称'); return; }}
  fetch('/api/add_task', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name, priority, category, today, note}})
  }}).then(r => r.json()).then(data => {{
    if (data.ok) {{ location.reload(); }}
    else {{ alert(data.error || '添加失败'); }}
  }}).catch(() => alert('连接服务器失败，请确认已启动 serve_task_flow.py'));
}}
document.addEventListener('click', e => {{
  if (e.target.id === 'add-modal-bg') closeAddModal();
}});

// 一键完成任务
function completeTask(no) {{
  if (!confirm('确认将任务 No.' + no + ' 标记为已完成？')) return;
  fetch('/api/complete_task', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{no}})
  }}).then(r => r.json()).then(data => {{
    if (data.ok) {{ location.reload(); }}
    else {{ alert(data.error || '操作失败'); }}
  }}).catch(() => alert('连接服务器失败'));
}}

// 删除任务
function deleteTask(no, name) {{
  if (!confirm('确认删除任务 No.' + no + ' ' + name + '？\\n\\n该操作将同时删除 CSV 和流程树数据，不可恢复。')) return;
  fetch('/api/delete_task', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{no}})
  }}).then(r => r.json()).then(data => {{
    if (data.ok) {{ location.reload(); }}
    else {{ alert(data.error || '删除失败'); }}
  }}).catch(() => alert('连接服务器失败'));
}}

// 等 DOM 就绪再初始化, 避免元素未加载时出现空引用
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', init);
}} else {{
  init();
}}
</script>

<!-- 添加任务弹窗 -->
<div id="add-modal-bg" class="modal-bg hide">
  <div class="modal">
    <h3>＋ 添加新任务</h3>
    <label>任务名称</label>
    <input type="text" id="task-name" placeholder="如：完成XX论文编写">
    <label>优先级</label>
    <select id="task-priority">
      <option value="high">高优先级</option>
      <option value="medium" selected>中优先级</option>
      <option value="low">低优先级</option>
    </select>
    <label>分类</label>
    <select id="task-category">
      <option value="科研">科研</option>
      <option value="工程">工程</option>
      <option value="标准">标准</option>
      <option value="专利">专利</option>
      <option value="个人" selected>个人</option>
    </select>
    <label>初始进度 (%)</label>
    <input type="number" id="task-progress" min="0" max="100" value="0" placeholder="0-100">
    <label>备注</label>
    <textarea id="task-note" placeholder="可选，记录任务说明"></textarea>
    <div class="modal-actions">
      <button onclick="closeAddModal()">取消</button>
      <button class="btn-primary" onclick="submitTask()">确认添加</button>
    </div>
  </div>
</div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="生成任务可视化筛选页面")
    parser.add_argument("--open", action="store_true", help="生成后打开浏览器")
    args = parser.parse_args()

    tasks = read_tasks()
    if not tasks:
        print("[错误] 没有可展示的任务数据")
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
