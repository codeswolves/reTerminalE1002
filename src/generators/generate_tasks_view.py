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
import sys
import webbrowser

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录（src/generators/ 的祖父目录）
OUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "tasks_view.html")

# 分类 / 优先级 统一取自 meta.py（单一数据源: task_flows.json 与枚举都不再各写一份）
GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from meta import (  # noqa: E402
    CATEGORY_COLOR,
    CATEGORY_FALLBACK_COLOR,
    CATEGORY_FALLBACK_ICON,
    CATEGORY_ICON,
    CATEGORY_ORDER,
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    PRIORITY_META,
    PRIORITY_ORDER,
    QUADRANT_META,
    QUADRANT_ORDER,
    collect_categories,
    js,
)
from generate_task_flow import read_tasks  # noqa: E402


def build_html(tasks):
    """拼装筛选可视化页面 HTML (数据内嵌, 双击即可用, 白底浅色主题)。"""
    # 按 No. 升序
    tasks = sorted(tasks, key=lambda t: int(t["no"]) if t["no"].isdigit() else 0)
    data_json = json.dumps(tasks, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")  # 防止 </script> 注入破坏页面

    # 下拉选项从 meta 统一生成, 避免与枚举不同步(历史上曾漏掉"管理"分类)
    cat_options = "".join(
        '      <option value="%s"%s>%s</option>\n'
        % (c, " selected" if c == DEFAULT_CATEGORY else "", c)
        for c in CATEGORY_ORDER
    )
    pri_options = "".join(
        '      <option value="%s"%s>%s</option>\n'
        % (k, " selected" if k == DEFAULT_PRIORITY else "", v["label"])
        for k, v in PRIORITY_META.items()
    )
    # 四象限(可选的第二维度): 默认"未归类" —— 不自动判定, 由人来定
    quad_options = '      <option value="">未归类</option>\n' + "".join(
        '      <option value="%s">%s · %s（%s）</option>\n'
        % (q, q, QUADRANT_META[q]["label"], QUADRANT_META[q]["action"])
        for q in QUADRANT_ORDER
    )

    # 分类分组的展示信息: 顺序取实际出现过的分类(未预设的自动追加末尾)
    cat_order = collect_categories(tasks)
    cat_meta = {
        c: {
            "icon": CATEGORY_ICON.get(c, CATEGORY_FALLBACK_ICON),
            "color": CATEGORY_COLOR.get(c, CATEGORY_FALLBACK_COLOR),
        }
        for c in cat_order
    }

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

  /* 顶部标题行: 窄屏时靠媒体查询换成纵向堆叠 */
  .head-left {{ display: flex; align-items: center; min-width: 0; }}
  .head-title {{ min-width: 0; }}

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
  /* 四象限角标 (A 重要且紧迫 / B 重要不紧迫 / C 紧迫不重要 / D 不重要不紧迫) */
  .qtag {{
    flex: none; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 12px;
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
  .edit-task {{ font-size: 13px; cursor: pointer; opacity: .35; transition: opacity .15s; border: none; background: none; padding: 0 2px }}
  .edit-task:hover {{ opacity: 1; color: #3b6fb0 }}
  .empty {{ text-align: center; color: #8893a7; padding: 60px 0; font-size: 14px; }}

  /* 计划日期 (开始 → 截止) */
  .plan-line {{ font-size: 11px; margin-top: 5px; color: #5a6577; }}
  .plan-line.over {{ color: #d6453d; font-weight: 600; }}
  .plan-line.soon {{ color: #b7791f; font-weight: 600; }}
  .plan-line.none {{ color: #b0b8c6; }}
  .two {{ display: flex; gap: 10px; }}
  .two > div {{ flex: 1; min-width: 0; }}

  /* 分类分组 */
  .section {{ margin-bottom: 30px; }}
  .section:last-child {{ margin-bottom: 4px; }}
  .section-head {{
    display: flex; align-items: center; gap: 9px; margin-bottom: 13px; padding-bottom: 9px;
    font-size: 14px; font-weight: 700; color: #1f2733; border-bottom: 2px solid #e8edf5;
  }}
  .section-head .sh-icon {{ font-size: 15px; flex: none; }}
  .section-head .sh-cnt {{ font-weight: 400; font-size: 12px; color: #8893a7; }}
  .section-head .sh-done {{ font-weight: 400; font-size: 12px; color: #2e9e5b; }}

  /* 添加任务按钮 */
  .add-task-btn {{
    background: #3b6fb0; color: #fff; border: none; border-radius: 20px;
    padding: 8px 18px; font-size: 13px; cursor: pointer; font-weight: 600;
    transition: all .15s; margin-left: 12px;
  }}
  .add-task-btn:hover {{ background: #2d5a94; }}

  /* 跳转到项目管理 */
  .proj-link {{
    background: #fff; color: #3b6fb0; border: 1px solid #c8d8ee; border-radius: 20px;
    padding: 8px 16px; font-size: 13px; font-weight: 600; text-decoration: none;
    margin-left: 10px; transition: all .15s; white-space: nowrap;
  }}
  .proj-link:hover {{ background: #e8eef8; border-color: #3b6fb0; }}

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

  /* 页面内提示条 / 确认框 (浏览器原生 alert/confirm 在部分内嵌预览里会被屏蔽) */
  #toast {{
    position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%) translateY(14px);
    background: rgba(31,39,51,.93); color: #fff; font-size: 13px; padding: 10px 18px;
    border-radius: 10px; opacity: 0; pointer-events: none; transition: all .22s;
    z-index: 2000; max-width: 80vw; line-height: 1.5; box-shadow: 0 6px 22px rgba(0,0,0,.18);
  }}
  #toast.on {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
  #toast.ok {{ background: rgba(46,158,91,.95); }}
  #toast.err {{ background: rgba(214,69,61,.95); }}
  #cfm-msg {{ font-size: 13px; color: #5a6577; line-height: 1.6; }}

  /* ---- 移动端适配 ----
     窄屏下横向 header 会把 title / 按钮挤成逐字竖排, 这里改为分层堆叠 */
  @media (max-width: 640px) {{
    body {{ padding: 18px 14px 40px; }}
    .header {{ flex-direction: column; align-items: stretch; gap: 14px; }}
    .head-left {{ flex-wrap: wrap; }}
    .head-title {{ flex: 1 1 100%; }}
    .title {{ font-size: 22px; white-space: nowrap; }}
    .subtitle {{ font-size: 12px; }}
    .add-task-btn {{ margin-left: 0; white-space: nowrap; }}
    .proj-link {{ margin-left: 8px; }}
    .stats {{ width: 100%; }}
    .stat {{ flex: 1; min-width: 0; padding: 8px 6px; }}
    .filters {{ gap: 8px; margin-bottom: 16px; }}
    .filter-btn {{ padding: 6px 12px; font-size: 12px; }}
    .grid {{ grid-template-columns: 1fr; }}
    .section-head {{ flex-wrap: wrap; }}
    .two {{ flex-direction: column; }}
    .modal {{ padding: 18px; }}
  }}

  /* 触屏没有 hover, 操作按钮不要藏得太深, 同时放大点击区域 */
  @media (hover: none) {{
    .flow-link, .edit-task, .done-task, .del-task {{ opacity: .6; padding: 4px 6px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="head-left">
      <div class="head-title">
        <div class="title">任务清单</div>
        <div class="subtitle" id="subtitle"></div>
      </div>
      <button class="add-task-btn" onclick="openAddTask()">＋ 添加任务</button>
      <a class="proj-link" href="quadrant.html" title="打开时间四象限页">🧭 四象限</a>
      <a class="proj-link" href="project_index.html" title="打开项目索引页">📁 项目管理</a>
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

  <div id="sections"></div>
</div>

<script>
let TASKS = [];
const EMBEDDED_TASKS = {data_json};

const PRIORITY = {js(PRIORITY_META)};
const PRIO_ORDER = {js({k: i for i, k in enumerate(PRIORITY_ORDER)})};
const QMETA = {js(QUADRANT_META)};
// 分类分组顺序(实际出现过的分类) 与展示信息(图标/颜色)
const CAT_ORDER = {js(cat_order)};
const CAT_META = {js(cat_meta)};

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}}

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

// YYYY/MM/DD -> MM/DD (卡片上紧凑显示计划日期)
function fmtShort(s) {{
  const m = String(s || '').split('/');
  return m.length === 3 ? (m[1].padStart(2, '0') + '/' + m[2].padStart(2, '0')) : String(s || '');
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

// 当前筛选
let curFilter = 'all';

// 单个任务卡片
function cardHtml(t) {{
  const p = PRIORITY[t.priority] || PRIORITY.medium;
  const days = execDays(t);
  const status = t.finished
    ? '<span class="meta-done">✓ 已完成' + (t.completed_date ? ' · ' + t.completed_date : '') + '</span>'
    : '<span>进行中</span>';
  const timeInfo = days != null
    ? '<span class="meta-time">' + (t.finished ? '执行时间：' + days + ' 天' : (days === 0 ? '今天创建' : '已进行 ' + days + ' 天')) + '</span>'
    : '';
  // 计划周期: 已完成的任务不再提示
  let planHtml = '';
  if (!t.finished) {{
    if (t.due) {{
      const left = t.days_left;
      const cls = t.delayed ? 'over' : ((left != null && left <= 3) ? 'soon' : '');
      const span = t.start ? (fmtShort(t.start) + ' → ' + fmtShort(t.due)) : ('截止 ' + fmtShort(t.due));
      let tail = '';
      if (t.delayed) tail = ' · 已延期 ' + Math.abs(left) + ' 天';
      else if (left === 0) tail = ' · 今天到期';
      else if (left != null) tail = ' · 剩 ' + left + ' 天';
      planHtml = '<div class="plan-line ' + cls + '">📅 ' + span + tail + '</div>';
    }} else {{
      planHtml = '<div class="plan-line none">📅 未设计划截止</div>';
    }}
  }}
  return `
    <div class="card ${{t.finished ? 'done' : 'todo'}}">
      <div class="card-head">
        <div>
          <div class="card-no">No.${{esc(t.no)}} · 创建于 ${{esc(t.date)}}</div>
          <div class="card-name">${{esc(t.name)}}</div>
        </div>
        <span style="display:flex;gap:4px;flex:none;align-items:flex-start">
          ${{t.quadrant && QMETA[t.quadrant] ? '<span class="qtag" style="color:' + QMETA[t.quadrant].color + ';background:' + QMETA[t.quadrant].bg + '" title="四象限：' + QMETA[t.quadrant].label + '（' + QMETA[t.quadrant].action + '）">' + t.quadrant + '</span>' : ''}}
          <span class="badge" style="color:${{p.color}};background:${{p.bg}}">${{p.label}}</span>
        </span>
      </div>
      <div class="progress-row">
        <div class="bar"><div class="bar-fill" style="width:${{t.today}}%;background:${{p.color}}"></div></div>
        <span class="bar-pct">${{t.today}}%</span>
      </div>
      ${{planHtml}}
      <div class="card-meta">${{status}}${{timeInfo}}
        <a class="flow-link" href="task_flow.html?task=${{encodeURIComponent(t.no)}}" title="查看流程树">🌳</a>
        <button class="edit-task" title="编辑任务" onclick="openEditTask('${{esc(t.no)}}')">✏️</button>
                  ${{!t.finished ? '<button class="done-task" title="一键完成" onclick="completeTask(\\'' + esc(t.no) + '\\')">✅</button>' : ''}}
        <button class="del-task" title="删除任务" onclick="deleteTask('${{esc(t.no)}}')">🗑️</button>
      </div>
    </div>`;
}}

// 排序: 高/中/低优先级标签按创建时间升序; 其余按 优先级 → 编号
function sortList(list, filter) {{
  return list.sort((a, b) => {{
    if (filter === 'high' || filter === 'medium' || filter === 'low') {{
      return dateVal(a) - dateVal(b);
    }}
    const pa = PRIO_ORDER[a.priority] != null ? PRIO_ORDER[a.priority] : 1;
    const pb = PRIO_ORDER[b.priority] != null ? PRIO_ORDER[b.priority] : 1;
    if (pa !== pb) return pa - pb;
    return (Number(a.no) || 0) - (Number(b.no) || 0);
  }});
}}

// 一个分类分组: 标题(图标 + 分类名 + 数量) + 卡片网格; 组内未完成在前
function sectionHtml(cat, items, filter) {{
  const meta = CAT_META[cat] || {{}};
  const todo = sortList(items.filter(t => !t.finished), filter);
  const done = sortList(items.filter(t => t.finished), filter);
  const doneTag = done.length ? '<span class="sh-done">· 已完成 ' + done.length + '</span>' : '';
  return `
    <div class="section">
      <div class="section-head">
        <span class="sh-icon">${{meta.icon || '📁'}}</span>
        <span>${{esc(cat)}}</span>
        <span class="sh-cnt">${{items.length}} 个任务 ${{doneTag}}</span>
      </div>
      <div class="grid">${{todo.concat(done).map(cardHtml).join('')}}</div>
    </div>`;
}}

function render(filter) {{
  curFilter = filter;
  const box = document.getElementById('sections');
  if (!box) return;
  const list = TASKS.filter(t => matches(t, filter));
  if (!list.length) {{ box.innerHTML = '<div class="empty">该筛选下暂无任务</div>'; return; }}
  // 按分类归组
  const groups = {{}};
  list.forEach(t => {{
    const c = (t.category || '其他').trim() || '其他';
    (groups[c] = groups[c] || []).push(t);
  }});
  // 分类顺序以 CAT_ORDER 为准, 数据里新增的分类追加到末尾
  const cats = Object.keys(groups).sort((a, b) => {{
    const ia = CAT_ORDER.indexOf(a), ib = CAT_ORDER.indexOf(b);
    return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib) || a.localeCompare(b);
  }});
  box.innerHTML = cats.map(c => sectionHtml(c, groups[c], filter)).join('');
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

// 页面内提示条 / 确认框 (部分内嵌预览会屏蔽浏览器原生 alert/confirm,
// 屏蔽后 confirm 恒返回 false, 表现为"点了没反应")
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

// 添加 / 编辑任务弹窗 (两者共用同一套表单, 用 editingTaskNo 区分)
let editingTaskNo = null;

function openAddTask() {{
  editingTaskNo = null;
  document.getElementById('task-modal-title').textContent = '＋ 添加新任务';
  document.getElementById('task-progress-label').textContent = '初始进度 (%)';
  document.getElementById('task-submit-btn').textContent = '确认添加';
  document.getElementById('task-name').value = '';
  document.getElementById('task-priority').value = 'medium';
  document.getElementById('task-quadrant').value = '';
  document.getElementById('task-category').value = '个人';
  document.getElementById('task-progress').value = '0';
  document.getElementById('task-start').value = '';
  document.getElementById('task-due').value = '';
  document.getElementById('task-note').value = '';
  document.getElementById('task-owner').value = '';
  document.getElementById('add-modal-bg').classList.remove('hide');
}}

// 编辑任务: 回填任务级字段 + 创建节点上的责任人/备注 + 最后节点的进度
function openEditTask(no) {{
  const t = TASKS.find(x => String(x.no) === String(no));
  if (!t) {{ toast('任务不存在', 'err'); return; }}
  editingTaskNo = String(no);
  document.getElementById('task-modal-title').textContent = '✏️ 编辑任务 No.' + no;
  document.getElementById('task-progress-label').textContent = '当前进度 (%)';
  document.getElementById('task-submit-btn').textContent = '保存修改';
  document.getElementById('task-name').value = t.name || '';
  document.getElementById('task-priority').value = t.priority || 'medium';
  document.getElementById('task-category').value = t.category || '个人';
  document.getElementById('task-progress').value = t.today || 0;
  // 数据存 YYYY/MM/DD, 而 <input type="date"> 只认 YYYY-MM-DD
  document.getElementById('task-start').value = (t.start || '').split('/').join('-');
  document.getElementById('task-due').value = (t.due || '').split('/').join('-');
  const first = (t.nodes && t.nodes[0]) || {{}};
  document.getElementById('task-owner').value = first.owner || '';
  document.getElementById('task-note').value = first.note || '';
  document.getElementById('add-modal-bg').classList.remove('hide');
}}

function closeAddModal() {{
  document.getElementById('add-modal-bg').classList.add('hide');
  editingTaskNo = null;
}}

function submitTask() {{
  const name = document.getElementById('task-name').value.trim();
  const priority = document.getElementById('task-priority').value;
  const category = document.getElementById('task-category').value;
  const today = parseInt(document.getElementById('task-progress').value) || 0;
  const note = document.getElementById('task-note').value.trim();
  const owner = document.getElementById('task-owner').value.trim();
  // <input type="date"> 给的是 YYYY-MM-DD, 而数据统一存 YYYY/MM/DD
  const start = document.getElementById('task-start').value.split('-').join('/');
  const due = document.getElementById('task-due').value.split('-').join('/');
  if (!name) {{ toast('请填写任务名称', 'err'); return; }}
  if (today < 0 || today > 100) {{ toast('进度请填 0-100 之间的数字', 'err'); return; }}
  if (start && due && due < start) {{ toast('计划截止不能早于计划开始', 'err'); return; }}
  const isEdit = editingTaskNo !== null;
  const quadrant = document.getElementById('task-quadrant').value;
  const payload = {{name, priority, category, quadrant, today, note, owner, start, due}};
  if (isEdit) payload.no = editingTaskNo;
  fetch(isEdit ? '/api/edit_task' : '/api/add_task', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(payload)
  }}).then(r => r.json()).then(data => {{
    if (data.ok) {{
      toast(isEdit ? '已保存修改' : '任务已添加', 'ok');
      setTimeout(() => location.reload(), 600);   // 留一点时间让提示可见
    }} else toast(data.error || (isEdit ? '保存失败' : '添加失败'), 'err');
  }}).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}}

// 点遮罩关闭弹窗; 确认框按钮在 DOM 就绪后绑定(脚本位于弹窗 DOM 之前)
document.addEventListener('click', e => {{
  if (e.target.id === 'add-modal-bg') closeAddModal();
  if (e.target.id === 'cfm-bg') closeConfirm();
}});
document.addEventListener('DOMContentLoaded', () => {{
  const ok = document.getElementById('cfm-ok');
  if (ok) ok.onclick = () => {{ const fn = confirmCb; closeConfirm(); if (fn) fn(); }};
}});

// 一键完成任务 (自绘确认框: 原生 confirm 在部分内嵌预览里被屏蔽且恒返回 false)
function completeTask(no) {{
  confirmBox('确认将任务 No.' + esc(no) + ' 标记为已完成？', () => {{
    fetch('/api/complete_task', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{no}})
    }}).then(r => r.json()).then(data => {{
      if (data.ok) {{
        toast('已标记完成', 'ok');
        setTimeout(() => location.reload(), 600);
      }} else toast(data.error || '操作失败', 'err');
    }}).catch(() => toast('连接服务器失败', 'err'));
  }}, '标记完成');
}}

// 删除任务 (任务名改为从 TASKS 里查, 不再拼接进 onclick 属性)
function deleteTask(no) {{
  const t = TASKS.find(x => String(x.no) === String(no));
  if (!t) {{ toast('任务不存在', 'err'); return; }}
  confirmBox('确认删除任务 No.' + esc(no) + ' 「' + esc(t.name) + '」？<br><br>'
    + '该操作将删除该任务及其全部流程节点，不可恢复。', () => {{
    fetch('/api/delete_task', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{no}})
    }}).then(r => r.json()).then(data => {{
      if (data.ok) {{
        toast('已删除任务', 'ok');
        setTimeout(() => location.reload(), 600);
      }} else toast(data.error || '删除失败', 'err');
    }}).catch(() => toast('连接服务器失败', 'err'));
  }}, '删除');
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
    <h3 id="task-modal-title">＋ 添加新任务</h3>
    <label>任务名称</label>
    <input type="text" id="task-name" placeholder="如：完成XX论文编写">
    <label>优先级</label>
    <select id="task-priority">
{pri_options}    </select>
    <label>四象限（时间管理）</label>
    <select id="task-quadrant">
{quad_options}    </select>
    <label>分类</label>
    <select id="task-category">
{cat_options}    </select>
    <label>责任人</label>
    <input type="text" id="task-owner" placeholder="可选，填写负责人姓名">
    <label id="task-progress-label">初始进度 (%)</label>
    <input type="number" id="task-progress" min="0" max="100" value="0" placeholder="0-100">
    <div class="two">
      <div>
        <label>计划开始 (可选)</label>
        <input type="date" id="task-start">
      </div>
      <div>
        <label>计划截止 (可选)</label>
        <input type="date" id="task-due">
      </div>
    </div>
    <label>备注</label>
    <textarea id="task-note" placeholder="可选，记录任务说明"></textarea>
    <div class="modal-actions">
      <button onclick="closeAddModal()">取消</button>
      <button class="btn-primary" id="task-submit-btn" onclick="submitTask()">确认添加</button>
    </div>
  </div>
</div>

<!-- 操作确认弹窗 (替代浏览器原生 confirm, 后者在部分内嵌预览里被屏蔽) -->
<div class="modal-bg hide" id="cfm-bg">
  <div class="modal" style="width:370px">
    <h3 id="cfm-title">确认操作</h3>
    <div id="cfm-msg"></div>
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
