"""
generate_ideas.py
生成灵感胶囊页 (ideas.html)。

用途:
    读取 data/ideas.json, 生成 output/tasks/ideas.html。
    这是一个**专利 / 论文 idea 的存放处**: 先封存, 需要的时候才打开。
    页面设计见 docs/design/inspiration-capsule-design.md §5。

为什么用 .replace() 拼而不是 f-string(与 generate_tasks_view.py 不同):
    本页 JS 里用到大量模板字面量(${{...}}), f-string 下每个花括号都要写成 {{{{ }}}},
    错一个就是"页面白屏、还看不出哪错了"。占位符方案里花括号可以原样写。

用法:
    python src/generators/generate_ideas.py            # 生成页面
    python src/generators/generate_ideas.py --open      # 生成后打开浏览器

设计文档: docs/design/inspiration-capsule-design.md
"""

import argparse
import json
import os
import sys
import webbrowser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "ideas.html")

GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from meta import (  # noqa: E402
    DEFAULT_IDEA_STATUS,
    DELIVERABLE_META,
    IDEA_DELIVERABLE_ORDER,
    IDEA_STATUS_META,
    IDEA_STATUS_ORDER,
    PRIORITY_META,
    PRIORITY_ORDER,
    js,
)
from ideas_store import STALE_DAYS, read_ideas  # noqa: E402


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>灵感胶囊</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #f6f8fb; color: #2b3444;
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 14px; line-height: 1.6;
  }
  .wrap { max-width: 940px; margin: 0 auto; padding: 22px 18px 60px; }

  /* ---- 页头 ---- */
  .header { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
  .head-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
  .head-title { min-width: 0; }
  .title { font-size: 21px; font-weight: 700; }
  .subtitle { font-size: 12px; color: #8893a7; margin-top: 2px; }
  .nav-link {
    background: #fff; color: #3b6fb0; border: 1px solid #c8d8ee; border-radius: 20px;
    padding: 5px 13px; font-size: 12px; text-decoration: none; white-space: nowrap;
  }
  .nav-link:hover { background: #eef4fc; }

  .panel {
    background: #fff; border: 1px solid #e3e8f0; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 14px;
  }
  .panel-title { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
  .cnt { font-size: 12px; color: #8893a7; font-weight: 400; }

  /* ---- 快速捕获框 ---- */
  /* 永远在页面最上方、不折叠不弹窗: 它承载的是"随手记"这个最高频动作(§5.2) */
  .cap-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  #cap-text {
    width: 100%; padding: 11px 13px; border: 1px solid #d8dee9; border-radius: 9px;
    font-size: 14px; font-family: inherit; resize: vertical; min-height: 62px; line-height: 1.6;
  }
  #cap-text:focus { outline: none; border-color: #3b6fb0; }
  .cap-meta { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-top: 9px; }
  .cap-meta label { font-size: 12px; color: #5a6577; margin-right: 4px; }
  select, input[type=text] {
    padding: 7px 10px; border: 1px solid #d8dee9; border-radius: 8px;
    font-size: 13px; font-family: inherit; background: #fff; color: #2b3444;
  }
  select:focus, input[type=text]:focus { outline: none; border-color: #3b6fb0; }
  .btn-primary {
    background: #3b6fb0; color: #fff; border: 1px solid #3b6fb0; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; cursor: pointer; font-family: inherit;
  }
  .btn-primary:hover { background: #325f98; }
  button.plain {
    background: #fff; color: #5a6577; border: 1px solid #d8dee9; border-radius: 8px;
    padding: 6px 12px; font-size: 12px; cursor: pointer; font-family: inherit;
  }
  button.plain:hover { border-color: #3b6fb0; color: #3b6fb0; }
  button.danger:hover { border-color: #d6453d; color: #d6453d; }

  /* ---- 久置区 ---- */
  /* 只列事实、不排序、不带评价性措辞(§4.3)。它**不受视角与筛选影响**(§5.3):
     一筛就看不见另一边搁下的了, 而那正是它要防的事 */
  .stale-row {
    display: flex; align-items: baseline; gap: 9px; padding: 4px 0;
    font-size: 12px; cursor: pointer; border-top: 1px solid #f0f3f8;
  }
  .stale-row:first-child { border-top: none; }
  .stale-row:hover { background: #fafbfd; }
  .stale-row .si { flex: none; color: #8893a7; font-variant-numeric: tabular-nums; }
  .stale-row .sn { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #2b3444; }
  .stale-row .sd { flex: none; color: #d29922; }
  .stale-none { font-size: 12px; color: #b0b8c6; }

  /* ---- 视角 / 筛选 ---- */
  .views { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
  .views .lab { font-size: 12px; color: #8893a7; margin-right: 2px; }
  .view-btn {
    background: #fff; color: #5a6577; border: 1px solid #d8dee9; border-radius: 7px;
    padding: 5px 12px; font-size: 12px; cursor: pointer; font-family: inherit;
  }
  .view-btn.on { background: #3b6fb0; border-color: #3b6fb0; color: #fff; }
  .filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
  .tab {
    background: #fff; color: #5a6577; border: 1px solid #d8dee9; border-radius: 20px;
    padding: 4px 12px; font-size: 12px; cursor: pointer; font-family: inherit;
  }
  .tab.on { background: #2b3444; border-color: #2b3444; color: #fff; }
  .tab .cnt { color: #a8b0bd; margin-left: 3px; }
  .tab.on .cnt { color: #cfd9e6; }

  /* ---- 分组 ---- */
  .group { margin-bottom: 14px; }
  .group-head {
    display: flex; align-items: center; gap: 8px; cursor: pointer;
    padding: 6px 2px; font-size: 13px; font-weight: 700; color: #5a6577;
  }
  .group-head:hover { color: #2b3444; }
  .group-head .gt { flex: none; }
  .group-head .gc { font-size: 12px; color: #8893a7; font-weight: 400; }
  .group-head .gshare { font-size: 11px; color: #a8b0bd; font-weight: 400; }
  .group-head .gdrop { font-size: 10px; color: #b0b8c6; }
  .group-body { display: flex; flex-direction: column; gap: 9px; }

  /* ---- 卡片 ---- */
  .card {
    background: #fff; border: 1px solid #e3e8f0; border-radius: 12px; padding: 12px 14px;
  }
  .card.archived { background: #fbfcfd; }
  .card-head { display: flex; align-items: flex-start; gap: 8px; }
  .card-id { font-size: 11px; color: #a8b0bd; font-variant-numeric: tabular-nums; }
  .card-name { font-size: 14px; font-weight: 600; color: #2b3444; margin-top: 1px; word-break: break-word; }
  .card-name.raw { font-weight: 500; color: #5a6577; }
  .card-badges { display: flex; gap: 4px; flex: none; align-items: flex-start; flex-wrap: wrap; justify-content: flex-end; }
  .badge {
    font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px;
    border: 1px solid transparent; white-space: nowrap;
  }
  .badge.dlib { background: #fff; cursor: pointer; }
  .badge.dlib.off { color: #c3cad5 !important; border-color: #e8ecf2 !important; border-style: dashed; }
  .badge.prib { cursor: pointer; }
  .badge.prib:hover, .badge.dlib:hover { filter: brightness(.95); }
  .card-text { font-size: 12px; color: #8893a7; margin-top: 5px; word-break: break-word; }
  .card-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 7px; font-size: 12px; color: #8893a7; }
  .st { cursor: pointer; border-bottom: 1px dashed transparent; }
  .st:hover { border-bottom-color: #c8cfda; }
  .st.locked { cursor: default; border-bottom: none; }
  .tag {
    color: #5a6577; background: #f0f3f8; border-radius: 6px; padding: 1px 7px;
    font-size: 11px; cursor: pointer;
  }
  .tag:hover { background: #e3e8f0; }
  .card-src { font-size: 11px; color: #a8b0bd; margin-top: 4px; }
  .card-notes { margin-top: 7px; border-left: 3px solid #eef1f6; padding-left: 9px; }
  .note-line { font-size: 12px; color: #5a6577; padding: 1px 0; }
  .note-line .nd { color: #a8b0bd; margin-right: 6px; font-variant-numeric: tabular-nums; }
  .card-link { font-size: 12px; margin-top: 6px; }
  .card-link a { color: #3b6fb0; }
  .warn { color: #d29922; }
  .card-acts { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 9px; align-items: center; }
  .note-in { padding: 5px 9px !important; font-size: 12px !important; flex: 1; min-width: 130px; }

  /* ---- 弹窗 ---- */
  .modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
  .modal-bg.hide { display: none; }
  .modal {
    background: #fff; border-radius: 14px; padding: 20px 22px; width: 460px; max-width: 100%;
    /* max-height + overflow 是必需的: 否则内容一高, 居中的弹窗上下两端同时被裁、按钮够不着 */
    max-height: 88vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,.14);
  }
  .modal h3 { font-size: 16px; font-weight: 700; margin: 0 0 4px; }
  .modal .sub { font-size: 12px; color: #8893a7; margin-bottom: 14px; }
  .modal label { display: block; font-size: 12px; color: #5a6577; margin: 12px 0 5px; }
  .modal input[type=text], .modal select { width: 100%; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 9px; margin-top: 18px; }
  .pick {
    display: flex; align-items: center; gap: 9px; width: 100%; text-align: left;
    background: #fff; border: 1px solid #d8dee9; border-radius: 9px;
    padding: 9px 12px; margin-top: 7px; font-size: 13px; cursor: pointer; font-family: inherit;
  }
  .pick:hover { border-color: #3b6fb0; background: #f7fafd; }
  .pick.on { border-color: #3b6fb0; background: #eef4fc; }
  .pick .pi { flex: none; }
  .pick .pd { font-size: 11px; color: #8893a7; }
  .mini { font-size: 11px; color: #8893a7; line-height: 1.7; }

  #toast {
    position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%);
    background: #2b3444; color: #fff; padding: 9px 18px; border-radius: 9px;
    font-size: 13px; opacity: 0; pointer-events: none; transition: opacity .18s;
    max-width: 88vw; text-align: center; z-index: 2000;
  }
  #toast.on { opacity: 1; }

  .cfm-bg { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1500; padding: 16px; }
  .cfm-bg.hide { display: none; }
  .cfm { background: #fff; border-radius: 12px; padding: 20px 22px; width: 400px; max-width: 100%; }
  .cfm-msg { font-size: 13px; line-height: 1.75; }
  .cfm-acts { display: flex; justify-content: flex-end; gap: 9px; margin-top: 16px; }
  .empty { font-size: 13px; color: #a8b0bd; text-align: center; padding: 26px 0; }

  @media (max-width: 620px) {
    /* flex 子项默认 min-width:auto, 压不到内容宽度以下 —— 窄屏会把容器撑破
       (docs/design/mobile-responsive.md §5.4) */
    .wrap { padding: 16px 12px 50px; }
    .card-acts button, .card-acts a { font-size: 11px; }
    .cap-meta { gap: 9px; }
  }
</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <div class="head-left">
      <div class="head-title">
        <div class="title">💡 灵感胶囊</div>
        <div class="subtitle" id="subtitle"></div>
      </div>
      <a class="nav-link" href="tasks_view.html">任务清单</a>
      <a class="nav-link" href="quadrant.html">四象限</a>
      <a class="nav-link" href="task_flow.html">流程跟踪</a>
      <a class="nav-link" href="project_index.html">项目管理</a>
    </div>
  </div>

  <!-- 快速捕获: 只要求一段话。标题 / 标签 / 可能产出都能留空、之后在卡片上补(§3.1) -->
  <div class="panel">
    <div class="panel-title">快速捕获</div>
    <textarea id="cap-text" placeholder="想到什么？（回车即存，Ctrl+回车换行）"></textarea>
    <div class="cap-meta">
      <span><label>可能产出</label>
        <select id="cap-deliv">
          <option value="">未定</option>
          <option value="专利">专利</option>
          <option value="论文">论文</option>
        </select>
      </span>
      <span><label>标签</label><input type="text" id="cap-tags" placeholder="逗号分隔，可留空" style="width:190px"></span>
      <button class="btn-primary" onclick="saveCapture()">存进胶囊 ⏎</button>
    </div>
    <div class="mini" style="margin-top:8px">
      只要求一段话。标题、标签、可能产出都可以之后在卡片上补 ——
      要求当场想清楚，就是把最该省事的这一步变成了负担。
    </div>
  </div>

  <!-- 久置: 只列事实, 不做判断, 不受视角与筛选影响 -->
  <div class="panel" id="stale-panel"></div>

  <div class="views">
    <span class="lab">看：</span>
    <button class="view-btn" data-view="status" onclick="setView('status')">按状态</button>
    <button class="view-btn" data-view="deliverable" onclick="setView('deliverable')">按产出</button>
  </div>
  <div class="filters" id="filters"></div>

  <div id="list"></div>
</div>

<!-- 状态 -->
<div class="modal-bg hide" id="m-status">
  <div class="modal" style="width:420px">
    <h3>状态</h3>
    <div class="sub" id="st-sub"></div>
    <div id="st-opts"></div>
    <div id="st-why-wrap" style="display:none">
      <label>为什么先放下？（可留空）</label>
      <input type="text" id="st-why" placeholder="技术路线走不通？数据拿不到？没时间？">
      <div class="mini" style="margin-top:6px">
        你迟早会再次想到同一个想法。那时最有用的不是"它是什么"（你刚想到），
        而是"上次为什么放下了" —— 只有"技术路线走不通"这类才值得重新投入。
      </div>
    </div>
    <div class="modal-actions">
      <button class="plain" onclick="closeModal('m-status')">取消</button>
      <button class="btn-primary" id="st-ok" onclick="saveStatus()" style="display:none">确认</button>
    </div>
  </div>
</div>

<!-- 优先级 -->
<div class="modal-bg hide" id="m-prio">
  <div class="modal" style="width:420px">
    <h3>优先级</h3>
    <div class="sub" id="pr-sub"></div>
    <div id="pr-opts"></div>
    <div class="mini" style="margin-top:10px">
      优先级**不参与排序** —— 这个页面没有"按价值排序"，它只是一个标记，
      让值得先想的几条在扫列表时看得出来。留空 = 还没评，是合法状态。
    </div>
  </div>
</div>

<!-- 标签 -->
<div class="modal-bg hide" id="m-tags">
  <div class="modal" style="width:440px">
    <h3>标签</h3>
    <div class="sub" id="tg-sub"></div>
    <label>标签（逗号或空格分隔，可留空）</label>
    <input type="text" id="tg-in" placeholder="承载网, GNN, 流量预测">
    <div class="mini" style="margin-top:8px">
      标签只服务检索（"我那个跟 GNN 有关的想法呢"），**不参与任何统计** ——
      硬把领域枚举出来的话，捕获时只会从列表里挑一个不相干的。
    </div>
    <div class="modal-actions">
      <button class="plain" onclick="closeModal('m-tags')">取消</button>
      <button class="btn-primary" onclick="saveTags()">保存</button>
    </div>
  </div>
</div>

<!-- 转成任务 -->
<div class="modal-bg hide" id="m-promote">
  <div class="modal" style="width:480px">
    <h3>转成任务</h3>
    <div class="sub" id="pm-sub"></div>
    <label>任务名</label>
    <input type="text" id="pm-name" placeholder="任务的显示名">
    <div id="pm-deliv-wrap"></div>
    <div class="mini" style="margin-top:10px" id="pm-hint"></div>
    <div class="modal-actions">
      <button class="plain" onclick="closeModal('m-promote')">取消</button>
      <button class="btn-primary" onclick="savePromote()">创建任务</button>
    </div>
  </div>
</div>

<div class="cfm-bg hide" id="cfm-bg">
  <div class="cfm">
    <div class="cfm-msg" id="cfm-msg"></div>
    <div class="cfm-acts">
      <button class="plain" onclick="closeConfirm()">取消</button>
      <button class="btn-primary" id="cfm-ok">确认</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
/* ================= 数据 ================= */
let IDEAS = [];
const EMBEDDED_IDEAS = __IDEAS_JSON__;

const DELIV = __DELIV_META__;              // 可能的产出 -> DELIVERABLE_META(子集共用同一套配色)
const DELIV_ORDER = __DELIV_ORDER__;
const ST_META = __STATUS_META__;
const ST_ORDER = __STATUS_ORDER__;
const DEFAULT_ST = __DEFAULT_STATUS__;
const PRIO = __PRIORITY_META__;
const PRIO_ORDER = __PRIO_ORDER__;
const STALE_DAYS = __STALE_DAYS__;

let curView = 'status';      // status | deliverable
let curStatus = 'all';
let curDeliv = 'all';
let curTag = 'all';
// 分组的展开状态**只记用户显式动过的** —— 默认值放函数里, 这样两套视角各有各的默认
// (按产出全展开、按状态收起两组), 又不会互相污染(§5.3)
const openGroups = {};

/* ================= 小工具 ================= */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function toast(msg, type) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.background = type === 'err' ? '#d6453d' : '#2b3444';
  el.classList.add('on');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('on'), 2600);
}
function post(url, payload) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(r => {
    // 路由没匹配上时服务端返回的是 HTML(404 页), 直接 r.json() 会抛异常,
    // 而异常信息里看不出真正的原因 —— 先看 content-type
    const ct = r.headers.get('content-type') || '';
    if (!r.ok || ct.indexOf('json') < 0) {
      throw new Error(r.ok ? '服务端返回了非 JSON 响应' : '服务端返回 HTTP ' + r.status);
    }
    return r.json();
  });
}
function openModal(id) { document.getElementById(id).classList.remove('hide'); }
function closeModal(id) { document.getElementById(id).classList.add('hide'); }

let cfmCb = null;
function confirmBox(msg, cb, okText) {
  document.getElementById('cfm-msg').innerHTML = msg;
  document.getElementById('cfm-ok').textContent = okText || '确认';
  cfmCb = cb;
  document.getElementById('cfm-bg').classList.remove('hide');
}
function closeConfirm() { document.getElementById('cfm-bg').classList.add('hide'); cfmCb = null; }
document.getElementById('cfm-ok').onclick = function () {
  const cb = cfmCb; closeConfirm(); if (cb) cb();
};

function byId(id) { return IDEAS.filter(x => x.id === id)[0] || null; }
function poolsOf(idea) {
  const ds = idea.deliverable || [];
  return ds.length ? ds : ['未定'];
}
function titleOf(idea) {
  return idea.title || idea.text.split('\n')[0].slice(0, 60) || '(没有内容)';
}
function truncate(s, n) {
  s = String(s || '');
  return s.length > n ? s.slice(0, n) + '…' : s;
}

/* ================= 读数据 ================= */
/* 内嵌 JSON 兜底(双击 html 也能只读查看), 有服务时走接口拿计算字段 */
function loadData(reveal, expect) {
  return fetch('/idea_api/list').then(r => r.json()).then(d => {
    IDEAS = Array.isArray(d) ? d : (d.ideas || []);
    render();
    // 变更后把目标分组展开 —— 必须在重绘**之后**, 否则这次展开会被随后的重绘盖掉
    if (reveal) {
      const it = byId(expect.id);
      if (it) revealGroup(it);
      render();
    }
    return true;
  }).catch(() => {
    IDEAS = EMBEDDED_IDEAS || [];
    render();
    return false;
  });
}

/* ================= 分组与展开 ================= */
function groupDefaultOpen(view, key) {
  // 按产出: 全部展开 —— 那个视角的用途就是一眼看全两个池
  if (view === 'deliverable') return true;
  // 按状态: 已转出 / 封存 默认收起(页面首先是"当前还在想的事"), 种子 / 设计中 默认展开
  return key !== '已转出' && key !== '封存';
}
function isOpen(view, key) {
  const k = view + '|' + key;
  return (k in openGroups) ? openGroups[k] : groupDefaultOpen(view, key);
}
function toggleGroup(view, key) {
  openGroups[view + '|' + key] = !isOpen(view, key);
  render();
}
/* 状态/分组变动后, 把**目标分组**自动展开(§5.3)。
   三处变更(切状态 / 封存 / 转成任务)共用这一个出口 —— 各写一遍一定会漏掉其中一处,
   而漏掉的那次表现为"卡片当场消失了", 人只会以为操作没生效或自己点错了。
   两套视角一起展开: 用户随时可能切过去。 */
function revealGroup(idea) {
  openGroups['status|' + idea.status] = true;
  poolsOf(idea).forEach(d => { openGroups['deliverable|' + d] = true; });
}

/* 按产出视角下的分组: 用到的每种 + 子集外的 + 末尾"未定"(§5.3) */
function poolKeys() {
  const keys = [];
  DELIV_ORDER.forEach(d => {
    if (IDEAS.some(x => poolsOf(x).indexOf(d) >= 0)) keys.push(d);
  });
  // 子集外的值也各成一组: 读路径不丢数据, 藏起来比显示出来更危险(§2.3)
  IDEAS.forEach(x => poolsOf(x).forEach(d => {
    if (DELIV_ORDER.indexOf(d) < 0 && keys.indexOf(d) < 0) keys.push(d);
  }));
  if (IDEAS.some(x => poolsOf(x).indexOf('未定') >= 0)) keys.push('未定');
  return keys;
}
function groupsFor(view) {
  const keys = view === 'deliverable' ? poolKeys() : ST_ORDER;
  return keys.map(k => {
    const items = IDEAS.filter(x => view === 'deliverable'
      ? poolsOf(x).indexOf(k) >= 0
      : x.status === k);
    return { key: k, items: items };
  });
}

/* ================= 渲染 ================= */
function filtered() {
  return IDEAS.filter(x => {
    if (curStatus !== 'all' && x.status !== curStatus) return false;
    // 按产出视角下, 产出已经成了分组维度 —— 那个下拉同时收起来了(§5.3)
    if (curView !== 'deliverable' && curDeliv !== 'all'
        && poolsOf(x).indexOf(curDeliv) < 0) return false;
    if (curTag !== 'all' && (x.tags || []).indexOf(curTag) < 0) return false;
    return true;
  });
}

function render() {
  renderSubtitle();
  renderStale();
  renderViews();
  renderFilters();
  renderList();
}

function renderSubtitle() {
  const cnt = {};
  ST_ORDER.forEach(k => { cnt[k] = 0; });
  IDEAS.forEach(x => { cnt[x.status] = (cnt[x.status] || 0) + 1; });
  const parts = ST_ORDER.map(k => k + ' ' + (cnt[k] || 0));
  document.getElementById('subtitle').textContent =
    '共 ' + IDEAS.length + ' 条 · ' + parts.join(' · ');
}

/* 久置区: 只列条目、不排序、不带评价性措辞(§4.3)。不受视角与筛选影响(§5.3) */
function renderStale() {
  const box = document.getElementById('stale-panel');
  const list = IDEAS.filter(x => x.stale);
  let html = '<div class="panel-title">⏳ 久置<span class="cnt">' +
    '（' + list.length + ' 条 · 设计中超过 ' + STALE_DAYS + ' 天没有新进展）</span></div>';
  if (!list.length) {
    html += '<div class="stale-none">没有搁下的想法</div>';
  } else {
    html += '<div class="mini" style="margin-bottom:6px">只列事实，不做判断 —— 要不要捞起来、还是封存，由你定</div>';
    html += list.map(x =>
      '<div class="stale-row" onclick="jumpTo(\'' + esc(x.id) + '\')">' +
        '<span class="si">' + esc(x.id) + '</span>' +
        '<span class="sn">' + esc(titleOf(x)) + '</span>' +
        '<span class="sd">' + esc(x.status) + ' · ' + x.idle_days + ' 天未动</span>' +
      '</div>').join('');
  }
  box.innerHTML = html;
}
function jumpTo(id) {
  const el = document.getElementById('idea-' + id);
  if (!el) { toast('这条当前被筛选条件挡住了', 'err'); return; }
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.style.transition = 'box-shadow .3s';
  el.style.boxShadow = '0 0 0 3px #cfe0f5';
  setTimeout(() => { el.style.boxShadow = ''; }, 1200);
}

function renderViews() {
  document.querySelectorAll('.view-btn').forEach(b => {
    b.classList.toggle('on', b.dataset.view === curView);
  });
}
function setView(v) {
  curView = v;
  if (v === 'deliverable') curDeliv = 'all';
  render();
}
function renderFilters() {
  const cnt = { all: IDEAS.length };
  ST_ORDER.forEach(k => { cnt[k] = 0; });
  IDEAS.forEach(x => { cnt[x.status] = (cnt[x.status] || 0) + 1; });

  let html = '<button class="tab' + (curStatus === 'all' ? ' on' : '') +
    '" onclick="setStatus(\'all\')">全部<span class="cnt">' + cnt.all + '</span></button>';
  html += ST_ORDER.map(k =>
    '<button class="tab' + (curStatus === k ? ' on' : '') + '" onclick="setStatus(\'' + esc(k) + '\')">' +
      esc(k) + '<span class="cnt">' + cnt[k] + '</span></button>').join('');

  // 按产出视角下要把同义的产出下拉收起来(§5.3): 它已经成了分组维度, 再摆一个只会让人
  // 以为它还有别的用处
  if (curView !== 'deliverable') {
    html += '<span style="margin-left:6px"></span><select onchange="curDeliv=this.value;render()">' +
      '<option value="all">类型：全部</option>' +
      DELIV_ORDER.map(d => '<option value="' + esc(d) + '"' +
        (curDeliv === d ? ' selected' : '') + '>' + esc(d) + '</option>').join('') +
      '<option value="未定"' + (curDeliv === '未定' ? ' selected' : '') + '>未定</option>' +
      '</select>';
  }
  const tags = [];
  IDEAS.forEach(x => (x.tags || []).forEach(t => { if (tags.indexOf(t) < 0) tags.push(t); }));
  if (tags.length) {
    html += '<select onchange="curTag=this.value;render()">' +
      '<option value="all">标签：全部</option>' +
      tags.map(t => '<option value="' + esc(t) + '"' +
        (curTag === t ? ' selected' : '') + '>#' + esc(t) + '</option>').join('') +
      '</select>';
  }
  document.getElementById('filters').innerHTML = html;
}
function setStatus(s) { curStatus = s; render(); }
function setTag(t) { curTag = t; render(); }

function renderList() {
  const list = filtered();
  const box = document.getElementById('list');
  if (!IDEAS.length) {
    box.innerHTML = '<div class="empty">还没有灵感。上面那个框里写一句，回车就存下了。</div>';
    return;
  }
  const groups = groupsFor(curView);
  let html = '';
  let shown = 0;
  groups.forEach(g => {
    const items = g.items.filter(x => list.indexOf(x) >= 0);
    if (!items.length) return;
    shown += items.length;
    const open = isOpen(curView, g.key);
    // "同时也在别的池"必须说出来: 一条灵感会因为多选产出出现在两个池里,
    // 不提示的话会被当成重复条目(§5.3)
    const shared = curView === 'deliverable'
      ? items.filter(x => poolsOf(x).length > 1).length : 0;
    // 关联失效的条数**在收起状态下也要看得见**: 已转出组默认收起, 卡片里那句 ⚠
    // 就跟着藏起来了 —— 而"标着已转出、点进去什么都没有"正是 §7.6 要防的事
    const broken = items.filter(x => x.linked_task_missing).length;
    html += '<div class="group">' +
      '<div class="group-head" onclick="toggleGroup(\'' + esc(curView) + '\',\'' + esc(g.key) + '\')">' +
        '<span class="gt">' + (curView === 'deliverable' && g.key !== '未定' ? '📄 ' : '') + esc(g.key) + '</span>' +
        '<span class="gc">' + items.length + ' 条</span>' +
        (shared ? '<span class="gshare">· ' + shared + ' 条同时也在别的池</span>' : '') +
        (broken ? '<span class="gshare" style="color:#d29922">· ⚠ ' + broken + ' 条关联的任务已删除</span>' : '') +
        '<span class="gdrop">' + (open ? '▾' : '▸') + '</span>' +
      '</div>';
    html += '<div class="group-body"' + (open ? '' : ' style="display:none"') + '>' +
      items.map(cardHtml).join('') + '</div></div>';
  });
  box.innerHTML = shown
    ? html
    : '<div class="empty">当前筛选条件下没有条目</div>';
}

function cardHtml(t) {
  const p = PRIO[t.priority] || null;
  const sm = ST_META[t.status] || { icon: '·', color: '#8893a7' };
  const isTransferred = t.status === '已转出';
  const hasTitle = !!(t.title || '').trim();

  // 产出: 两个**可点**的角标 —— 点一下就地加/去, 不必开弹窗(它是多选, 只有两个值)
  let dlHtml = DELIV_ORDER.map(d => {
    const on = (t.deliverable || []).indexOf(d) >= 0;
    const c = (DELIV[d] || {}).color || '#8893a7';
    return '<span class="badge dlib' + (on ? '' : ' off') + '"' +
      ' style="color:' + c + ';border-color:' + c + '"' +
      ' title="' + (on ? '点一下去掉「' + esc(d) + '」' : '点一下标为「' + esc(d) + '」') + '"' +
      ' onclick="toggleDeliv(\'' + esc(t.id) + '\',\'' + esc(d) + '\')">' + esc(d) + '</span>';
  }).join('');
  // 子集外的值: 读路径不丢数据, 显示出来(不能点, 免得把它点没了)
  (t.deliverable || []).forEach(d => {
    if (DELIV_ORDER.indexOf(d) < 0) {
      dlHtml += '<span class="badge" style="color:#8893a7;background:#f0f2f5" title="不在可选范围内，按原样显示">' +
        esc(d) + '</span>';
    }
  });

  // 优先级: **未评时用灰**，不冒充"中"。它不参与排序, 只是一个标记
  const priHtml = '<span class="badge prib"' +
    (p ? ' style="color:' + p.color + ';background:' + p.bg + '"' : ' style="color:#b0b8c6;background:#f5f6f8"') +
    ' title="优先级：' + (p ? p.label : '未评') + '（点击修改）"' +
    ' onclick="openPriority(\'' + esc(t.id) + '\')">' + (p ? p.short : '未评') + '</span>';

  const notesHtml = (t.notes || []).length
    ? '<div class="card-notes">' + (t.notes || []).map(n =>
        '<div class="note-line"><span class="nd">' + esc(n.date) + '</span>' + esc(n.text) + '</div>').join('') +
      '</div>'
    : '';

  const linkHtml = t.linked_task
    ? (t.linked_task_missing
        ? '<div class="card-link warn">⚠ 关联的任务已被删除（No.' + esc(t.linked_task) + '）——' +
          ' 状态仍是「已转出」但点进去什么都没有。要么重新转出，要么把它退回设计中：' +
          ' <button class="plain" onclick="unlinkIdea(\'' + esc(t.id) + '\')">解除关联</button></div>'
        : '<div class="card-link">→ 已转成任务 No.' + esc(t.linked_task) + '：' +
          ' <a href="task_flow.html?task=' + encodeURIComponent(t.linked_task) + '">看它的流程树</a></div>')
    : '';

  return '<div class="card' + (t.status === '封存' ? ' archived' : '') + '" id="idea-' + esc(t.id) + '">' +
    '<div class="card-head">' +
      '<div style="flex:1;min-width:0">' +
        '<div class="card-id">' + esc(t.id) + '</div>' +
        '<div class="card-name' + (hasTitle ? '' : ' raw') + '" title="' + esc(t.text) + '">' +
          esc(titleOf(t)) + '</div>' +
      '</div>' +
      '<span class="card-badges">' + dlHtml + priHtml + '</span>' +
    '</div>' +
    // 有标题时把**原文**也摆出来: 想法会演化, 原始表述有独立价值(§5.4)
    (hasTitle ? '<div class="card-text">' + esc(truncate(t.text, 200)) + '</div>' : '') +
    '<div class="card-meta">' +
      '<span class="st' + (isTransferred ? ' locked' : '') + '"' +
        (isTransferred ? ' title="「已转出」只能通过「转成任务」进入"' : ' title="点击切换状态"') +
        ' style="color:' + sm.color + '"' +
        (isTransferred ? '' : ' onclick="openStatus(\'' + esc(t.id) + '\')"') + '>' +
        sm.icon + ' ' + esc(t.status) + '</span>' +
      (t.age_days != null ? '<span>记下 ' + t.age_days + ' 天' + (t.age_days === 0 ? '（今天）' : '') + '</span>' : '') +
      (t.note_n ? '<span>' + t.note_n + ' 条推进记录</span>' : '') +
      (t.stale && t.idle_days != null ? '<span class="warn">⚠ ' + t.idle_days + ' 天未动</span>' : '') +
      (t.tags || []).map(g =>
        '<span class="tag" onclick="curTag=\'' + esc(g) + '\';render()">#' + esc(g) + '</span>').join('') +
      '<span class="tag" title="编辑标签" onclick="openTags(\'' + esc(t.id) + '\')">＋标签</span>' +
    '</div>' +
    (t.source ? '<div class="card-src">来源：' + esc(t.source) + '</div>' : '') +
    notesHtml + linkHtml +
    '<div class="card-acts">' +
      '<input type="text" class="note-in" id="note-' + esc(t.id) + '" placeholder="后来又想通了什么？回车记下"' +
        ' onkeydown="if(event.key===\'Enter\'){event.preventDefault();addNote(\'' + esc(t.id) + '\');}">' +
      '<button class="plain" onclick="addNote(\'' + esc(t.id) + '\')">＋ 推进记录</button>' +
      (t.status === '封存'
        ? '<button class="plain" onclick="openStatus(\'' + esc(t.id) + '\')">捞回来</button>'
        : '<button class="plain" onclick="openStatus(\'' + esc(t.id) + '\')">状态</button>') +
      '<button class="plain" onclick="openPriority(\'' + esc(t.id) + '\')">优先级</button>' +
      '<button class="plain" onclick="openTags(\'' + esc(t.id) + '\')">标签</button>' +
      (isTransferred ? '' : '<button class="plain" onclick="openPromote(\'' + esc(t.id) + '\')">转成任务</button>') +
      '<button class="plain danger" onclick="delIdea(\'' + esc(t.id) + '\')">🗑 删除</button>' +
    '</div>' +
  '</div>';
}

/* ================= 捕获 ================= */
function saveCapture() {
  const ta = document.getElementById('cap-text');
  const text = ta.value.trim();
  if (!text) { toast('写一句再存', 'err'); return; }
  const deliv = document.getElementById('cap-deliv').value;
  const tags = document.getElementById('cap-tags').value.trim();
  post('/idea_api/add', { text: text, deliverable: deliv, tags: tags }).then(d => {
    if (!d.ok) { toast(d.error || '存失败', 'err'); return; }
    ta.value = '';
    document.getElementById('cap-tags').value = '';
    document.getElementById('cap-deliv').value = '';
    ta.focus();
    toast('已存进胶囊 ' + d.id, 'ok');
    // 新条目是"种子", 状态视角下那个组默认就是展开的 —— 不必特意 reveal
    loadData().then(() => {});
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}
document.addEventListener('DOMContentLoaded', function () {
  const ta = document.getElementById('cap-text');
  // 回车即存、Ctrl+回车换行(§3.1)
  ta.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) {
      e.preventDefault();
      saveCapture();
    }
  });
});

/* ================= 状态 ================= */
let stEditing = null;
function openStatus(id) {
  const t = byId(id);
  if (!t) return;
  stEditing = id;
  document.getElementById('st-sub').textContent = t.id + ' ' + titleOf(t);
  const opts = [];
  const add = (k, label) => {
    const m = ST_META[k] || {};
    opts.push('<button class="pick' + (t.status === k ? ' on' : '') + '"' +
      ' data-k="' + esc(k) + '"' +
      ' onclick="pickStatus(this,\'' + esc(k) + '\')">' +
      '<span class="pi" style="color:' + (m.color || '#8893a7') + '">' + (m.icon || '·') + '</span>' +
      '<span>' + esc(label || k) + '</span>' +
      '<span class="pd" style="margin-left:auto">' + esc(m.hint || '') + '</span></button>');
  };
  if (t.status === '已转出') {
    // 已转出只能走向封存: 状态机里 已转出 → 设计中等路径不存在(§2.4),
    // 想退回得先"解除关联"(那会把状态一起退回去)
    add('封存');
  } else if (t.status === '封存') {
    add('种子');
    add('设计中');
  } else {
    add(t.status === '种子' ? '设计中' : '种子');
    add('封存');
  }
  document.getElementById('st-opts').innerHTML = opts.join('');
  document.getElementById('st-why-wrap').style.display = 'none';
  document.getElementById('st-why').value = t.why || '';
  document.getElementById('st-ok').style.display = 'none';
  openModal('m-status');
}
/* 选目标状态。选"封存"要先问一句为什么(§2.5) —— 那个原因比"这个想法是什么"更值钱 */
function pickStatus(btn, k) {
  const t = byId(stEditing);
  if (!t) return;
  // 用 data-k 定位而不是按文字找 —— 按文字找会在"提示语里恰好含同一个词"时选错
  document.querySelectorAll('#st-opts .pick').forEach(b => b.classList.remove('on'));
  if (btn) btn.classList.add('on');
  if (k === '封存') {
    document.getElementById('st-why-wrap').style.display = 'block';
    document.getElementById('st-ok').style.display = '';
    window.__pendingStatus = '封存';
    return;
  }
  closeModal('m-status');
  applyStatus(t.id, k, null);
}
function saveStatus() {
  const t = byId(stEditing);
  if (!t || window.__pendingStatus !== '封存') return;
  const why = document.getElementById('st-why').value.trim();
  closeModal('m-status');
  applyStatus(t.id, '封存', why);
}
function applyStatus(id, status, why) {
  // 先写 why 再写状态: 反过来的话, 中途失败会留下"已封存但没写原因" ——
  // 而 §2.5 整个小节就是在说那句 why 才是回过头最需要的东西
  const chain = why ? post('/idea_api/set_field', { id: id, key: 'why', value: why })
                          .then(d => { if (!d.ok) throw new Error(d.error || '封存原因没存上'); })
                    : Promise.resolve();
  chain.then(() => post('/idea_api/set_field', { id: id, key: 'status', value: status }))
    .then(d => {
      if (!d.ok) { toast(d.error || '状态没改成功', 'err'); return; }
      toast(id + ' → ' + status, 'ok');
      loadData(true, { id: id });
    })
    .catch(e => toast(e && e.message ? e.message : '连接服务器失败', 'err'));
}

/* ================= 优先级 ================= */
/* 就地设。**不进捕获框**: 捕获时每多一个决定, 就多一批想法根本没被记下来,
   而"没记下来"是查不出来的。允许留空 —— "还没评"是合法状态, 不是"中" */
let prEditing = null;
function openPriority(id) {
  const t = byId(id);
  if (!t) return;
  prEditing = id;
  document.getElementById('pr-sub').textContent = t.id + ' ' + titleOf(t);
  const cur = t.priority || '';
  let html = PRIO_ORDER.map(k => {
    const m = PRIO[k];
    return '<button class="pick' + (cur === k ? ' on' : '') + '" onclick="pickPriority(\'' + k + '\')">' +
      '<span class="pi" style="color:' + m.color + '">●</span>' +
      '<span>' + esc(m.label) + '</span></button>';
  }).join('');
  html += '<button class="pick' + (cur === '' ? ' on' : '') + '" onclick="pickPriority(\'\')">' +
    '<span class="pi" style="color:#b0b8c6">○</span><span>未评（清除）</span></button>';
  document.getElementById('pr-opts').innerHTML = html;
  openModal('m-prio');
}
function pickPriority(k) {
  const id = prEditing;
  closeModal('m-prio');
  post('/idea_api/set_field', { id: id, key: 'priority', value: k }).then(d => {
    if (!d.ok) { toast(d.error || '优先级没存上', 'err'); return; }
    const m = PRIO[k];
    toast(id + ' 优先级：' + (m ? m.label : '已清除（未评）'), 'ok');
    loadData().then(() => {});
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ================= 产出 / 标签 ================= */
function toggleDeliv(id, d) {
  const t = byId(id);
  if (!t) return;
  const cur = (t.deliverable || []).slice();
  const i = cur.indexOf(d);
  if (i >= 0) cur.splice(i, 1); else cur.push(d);
  post('/idea_api/set_field', { id: id, key: 'deliverable', value: cur }).then(r => {
    if (!r.ok) { toast(r.error || '产出没存上', 'err'); return; }
    loadData(true, { id: id });
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

let tgEditing = null;
function openTags(id) {
  const t = byId(id);
  if (!t) return;
  tgEditing = id;
  document.getElementById('tg-sub').textContent = t.id + ' ' + titleOf(t);
  document.getElementById('tg-in').value = (t.tags || []).join(', ');
  openModal('m-tags');
  setTimeout(() => document.getElementById('tg-in').focus(), 60);
}
function saveTags() {
  const id = tgEditing;
  const val = document.getElementById('tg-in').value.trim();
  closeModal('m-tags');
  post('/idea_api/set_field', { id: id, key: 'tags', value: val }).then(d => {
    if (!d.ok) { toast(d.error || '标签没存上', 'err'); return; }
    loadData().then(() => {});
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ================= 推进记录 ================= */
function addNote(id) {
  const el = document.getElementById('note-' + id);
  if (!el) return;
  const text = el.value.trim();
  if (!text) { toast('写一句再记', 'err'); return; }
  post('/idea_api/add_note', { id: id, text: text }).then(d => {
    if (!d.ok) { toast(d.error || '没记上', 'err'); return; }
    el.value = '';
    toast('记下了', 'ok');
    loadData().then(() => {});
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ================= 转成任务 ================= */
let pmEditing = null;
function openPromote(id) {
  const t = byId(id);
  if (!t) return;
  pmEditing = id;
  document.getElementById('pm-sub').textContent = t.id + ' ' + titleOf(t);
  // 标题是"要转出成任务时才必须想清的东西"(§3.2): 这里才必填, 预填标题或原文截断
  document.getElementById('pm-name').value = t.title || truncate(t.text.split('\n')[0], 40);

  const ds = (t.deliverable || []).filter(d => DELIV_ORDER.indexOf(d) >= 0);
  const wrap = document.getElementById('pm-deliv-wrap');
  if (ds.length >= 2) {
    // 多个产出时必须由人挑一个: "先发论文还是先申专利"是**策略判断**, 系统不该替他定。
    // 所以这里**不预选** —— 预选等于替他做了那个判断
    wrap.innerHTML = '<label>主产出（任务的产出是单选，必须选一个）</label>' +
      '<select id="pm-deliv"><option value="">请选择…</option>' +
      ds.map(d => '<option value="' + esc(d) + '">' + esc(d) + '</option>').join('') +
      '</select>';
  } else if (ds.length === 1) {
    wrap.innerHTML = '<label>主产出</label><select id="pm-deliv"><option value="' + esc(ds[0]) +
      '">' + esc(ds[0]) + '</option></select>';
  } else {
    wrap.innerHTML = '<div class="mini" style="margin-top:10px">这条还没标可能产出 —— 任务会建出来但不带产出，之后在任务清单里补。</div>';
  }
  document.getElementById('pm-hint').innerHTML =
    '创建任务时会带过去：<b>任务名</b>、<b>产出</b>，以及原文与来源写进创建备注（原始表述不该丢）。<br>' +
    '<b>不带</b>象限与预估工时 —— 留空 = 未归类 / 未估算，那时才该由你来判断。<br>' +
    '灵感的原文与推进记录都<b>不删</b>：想法会演化，原始表述有独立价值。';
  openModal('m-promote');
}
function savePromote() {
  const id = pmEditing;
  const t = byId(id);
  if (!t) return;
  const name = document.getElementById('pm-name').value.trim();
  if (!name) { toast('任务名不能为空', 'err'); return; }
  const sel = document.getElementById('pm-deliv');
  const deliv = sel ? sel.value : '';
  if (sel && !deliv) { toast('请选一个主产出', 'err'); return; }
  closeModal('m-promote');
  post('/idea_api/promote', { id: id, name: name, deliverable: deliv }).then(d => {
    if (!d.ok) {
      // 服务端会明确说"任务已建、状态没回写" —— 那种情况不能重试(会建出第二条),
      // 所以提示里要带上编号
      toast(d.error || '转出失败', 'err');
      loadData().then(() => {});
      return;
    }
    toast('已建任务 No.' + d.no + '，灵感 ' + id + ' → 已转出', 'ok');
    loadData(true, { id: id });
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ================= 解除关联 / 删除 ================= */
function unlinkIdea(id) {
  confirmBox('解除 ' + id + ' 与任务的关联？<br><br>状态会一起退回「设计中」—— ' +
    '否则会留下"标着已转出、却没有对应任务"的悬空条目。灵感本身不动。',
    function () {
      post('/idea_api/unlink', { id: id, status: '设计中' }).then(d => {
        if (!d.ok) { toast(d.error || '没成功', 'err'); return; }
        toast(id + ' 已解除关联，退回设计中', 'ok');
        loadData(true, { id: id });
      }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
    }, '解除关联');
}
function delIdea(id) {
  const t = byId(id);
  confirmBox('<b>删除 ' + esc(id) + '？</b><br><br>' + esc(truncate(titleOf(t || {}), 60)) +
    '<br><br>⚠ 不可恢复。如果只是暂时不做，用「封存」—— 那还会留一句为什么，以后能捞回来。',
    function () {
      post('/idea_api/delete', { id: id }).then(d => {
        if (!d.ok) { toast(d.error || '删除失败', 'err'); return; }
        toast('已删除 ' + id, 'ok');
        loadData().then(() => {});
      }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
    }, '删除');
}

/* ================= 启动 ================= */
loadData().then(ok => {
  if (!ok) {
    toast('读不到接口，显示的是页面内嵌的快照（只读）', 'err');
  }
});
</script>
</body>
</html>
"""


def build_html(ideas):
    """拼装灵感胶囊页。数据内嵌(双击 html 也能只读查看), 有服务时走接口拿计算字段。"""
    data_json = json.dumps(ideas, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")      # 防止 </script> 注入破坏页面
    # 只把两个可能产出的配色带过去。子集共用 DELIVERABLE_META(§2.3) ——
    # 不另立一套颜色, 否则"专利"在灵感页和任务页会是两个颜色
    deliv_meta = {d: DELIVERABLE_META[d] for d in IDEA_DELIVERABLE_ORDER}

    return (TEMPLATE
            .replace("__IDEAS_JSON__", data_json)
            .replace("__DELIV_META__", js(deliv_meta))
            .replace("__DELIV_ORDER__", js(IDEA_DELIVERABLE_ORDER))
            .replace("__STATUS_META__", js(IDEA_STATUS_META))
            .replace("__STATUS_ORDER__", js(IDEA_STATUS_ORDER))
            .replace("__DEFAULT_STATUS__", js(DEFAULT_IDEA_STATUS))
            .replace("__PRIORITY_META__", js(PRIORITY_META))
            .replace("__PRIO_ORDER__", js(PRIORITY_ORDER))
            .replace("__STALE_DAYS__", str(STALE_DAYS)))


def main():
    parser = argparse.ArgumentParser(description="生成灵感胶囊页面")
    parser.add_argument("--open", action="store_true", help="生成后打开浏览器")
    args = parser.parse_args()

    ideas = read_ideas()
    html = build_html(ideas)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    stale = sum(1 for x in ideas if x.get("stale"))
    by_status = {}
    for x in ideas:
        by_status[x["status"]] = by_status.get(x["status"], 0) + 1
    print(f"[完成] 已生成: {OUT_HTML}")
    print(f"       共 {len(ideas)} 条 · " +
          " · ".join(f"{k} {v}" for k, v in by_status.items()) +
          f" · 久置 {stale}")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(OUT_HTML).replace("\\", "/"))


if __name__ == "__main__":
    main()
