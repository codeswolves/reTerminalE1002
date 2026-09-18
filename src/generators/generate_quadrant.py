"""
generate_quadrant.py
生成任务时间管理四象限页面 (HTML)。

功能:
    读取 data/task_flows.json, 按"重要性 x 紧迫性"把任务归入四个象限,
    并给出时间结构诊断: 各象限预估工时占比 vs 目标区间
    (A 20-25% / B 65-80% / C <=15% / D 0), 指出偏差方向。

    页面还提供:
    - 拖拽或按钮改象限 (写回 task_flows.json 的 quadrant 字段)
    - 预估工时 estimate_h / 实际净投入 actual_h 录入
    - "待归类"任务的 7 问自检 (推导建议象限)
    - 已完成任务的后评估: 事实层自动生成 + 卡点归类

用法:
    python3 src/generators/generate_quadrant.py            # 生成页面
    python3 src/generators/generate_quadrant.py --open     # 生成后打开浏览器

设计文档: docs/design/time-quadrant-design.md
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import date

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(BASE_DIR, "output", "tasks")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "quadrant.html")

GEN_DIR = os.path.join(BASE_DIR, "src", "generators")
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)
from meta import (  # noqa: E402
    BLOCKER_META,
    BLOCKER_ORDER,
    DAY_BUFFER_H,
    DAY_HOURS,
    DAY_PLAN_H,
    PLAN_DAYS_PER_WEEK,
    PRIORITY_META,
    PRIORITY_ORDER,
    QUADRANT_META,
    QUADRANT_ORDER,
    WEEK_PLAN_H,
    blocker_meta,
    js,
)
from generate_task_flow import read_tasks  # noqa: E402
from week_plan import (  # noqa: E402
    BREAK_END,
    BREAK_START,
    DAY_END,
    DAY_NAMES,
    DAY_START,
    WORK_END,
    WORK_START,
    read_week_plan,
)

TODAY_STR = date.today().strftime("%Y/%m/%d")


def _embed(obj):
    """JSON 嵌入 HTML 时的安全转义(转义 </ 防止提前闭合脚本标签)。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


# ----------------------------------------------------------------------------
# 模板 (普通字符串 + 占位符替换: 不写 f-string, CSS/JS 花括号无需双写)
# ----------------------------------------------------------------------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>时间四象限</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #f5f6f8;
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif;
    color: #1f2733; min-height: 100vh; padding: 28px 20px 48px;
  }
  .wrap { max-width: 1080px; margin: 0 auto; }
  .header { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
  .head-left { display: flex; align-items: center; min-width: 0; flex-wrap: wrap; gap: 10px; }
  .head-title { min-width: 0; }
  .title { font-size: 26px; font-weight: 700; letter-spacing: 1px; }
  .subtitle { font-size: 13px; color: #5a6577; margin-top: 6px; }
  .nav-link {
    background: #fff; color: #3b6fb0; border: 1px solid #c8d8ee; border-radius: 20px;
    padding: 8px 16px; font-size: 13px; font-weight: 600; text-decoration: none;
    transition: all .15s; white-space: nowrap;
  }
  .nav-link:hover { background: #e8eef8; border-color: #3b6fb0; }

  /* 面板 */
  .panel { background: #fff; border: 1px solid #e3e8f0; border-radius: 12px; padding: 16px 18px; margin-bottom: 18px; }
  .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
  .panel-title { font-size: 15px; font-weight: 700; }
  .panel-title .cnt { font-size: 12px; font-weight: 400; color: #8893a7; margin-left: 6px; }

  /* 预算控制 */
  .budget { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #5a6577; flex-wrap: wrap; }
  .budget input {
    width: 46px; padding: 4px 6px; border: 1px solid #d8dee9; border-radius: 6px;
    font-size: 12px; font-family: inherit; text-align: center;
  }
  .budget b { color: #3b6fb0; font-size: 13px; }

  /* 诊断行 */
  .panel-sub { font-size: 12px; color: #5a6577; line-height: 1.8; margin: -4px 0 12px; }
  .panel-sub b { color: #1f2733; }
  .diag-summary { font-size: 13px; line-height: 1.7; padding: 10px 13px; border-radius: 9px; background: #f4fbf6; border: 1px solid #cfe8d9; color: #1f6b3d; margin-bottom: 10px; }
  .diag-summary.warn { background: #fef8e8; border-color: #f3e2b8; color: #8a5d00; }
  .diag-empty { font-size: 12px; color: #8893a7; line-height: 1.8; }
  .diag-demo { font-size: 11px; color: #8893a7; margin-top: 9px; line-height: 2; background: #fafbfd; border-radius: 8px; padding: 9px 12px; }
  .diag-demo i { font-style: normal; color: #d3dae6; }
  .diag-row { display: grid; grid-template-columns: max-content 1fr 236px; gap: 12px; align-items: center; padding: 9px 0; border-top: 1px solid #f0f3f8; }
  .diag-row:first-child { border-top: none; }
  .qtag { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .qdot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
  .qtag small { font-weight: 400; color: #8893a7; font-size: 11px; white-space: nowrap; }
  .qbar { position: relative; height: 12px; background: #eef1f6; border-radius: 6px; overflow: hidden; }
  .qbar .zone { position: absolute; top: 0; bottom: 0; background: #dbe6f5; }
  .qbar .fill { position: absolute; top: 0; bottom: 0; left: 0; border-radius: 6px; opacity: .82; transition: width .3s ease; }
  .qval { font-size: 12px; color: #5a6577; line-height: 1.5; }
  .qval b { font-size: 14px; color: #1f2733; margin-right: 6px; white-space: nowrap; }
  .qval b.over { color: #d6453d; }
  .qval b.low { color: #b7791f; }
  .qval .tgt { color: #8893a7; white-space: nowrap; }
  .qval .hrs { white-space: nowrap; }
  .qval .hrs { color: #3b6fb0; }
  .diag-note { font-size: 12px; color: #b7791f; background: #fef8e8; border-radius: 8px; padding: 4px 10px; margin-top: 4px; display: inline-block; }
  .diag-foot { font-size: 12px; color: #8893a7; margin-top: 12px; padding-top: 10px; border-top: 1px solid #f0f3f8; line-height: 1.6; }

  /* 2x2 矩阵 */
  .matrix { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px; }
  .quad {
    background: #fff; border: 1px solid #e3e8f0; border-radius: 12px; padding: 14px;
    display: flex; flex-direction: column; gap: 10px; min-height: 132px; transition: all .15s;
  }
  .quad.dragover { border-color: #3b6fb0; background: #f8fbff; }
  .quad-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .quad-name { font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 7px; }
  .quad-name .act { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
  .quad-meta { font-size: 11px; color: #8893a7; }
  .quad-body { display: flex; flex-direction: column; gap: 8px; }
  .quad-empty { font-size: 12px; color: #b0b8c6; padding: 14px 2px; text-align: center; }

  /* 任务卡 */
  .card {
    background: #fff; border: 1px solid #e6eaf2; border-radius: 10px; padding: 10px 12px;
    display: flex; flex-direction: column; gap: 7px; cursor: grab; transition: all .15s;
  }
  .card:hover { border-color: #c8d1de; box-shadow: 0 2px 8px rgba(0,0,0,.05); }
  .card.dragging { opacity: .45; }
  .card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .card-no { font-size: 11px; color: #8893a7; margin-bottom: 2px; }
  .card-name { font-size: 13px; font-weight: 600; line-height: 1.4; word-break: break-word; }
  .badge { flex: none; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
  .card-foot { display: flex; align-items: center; justify-content: space-between; gap: 6px; font-size: 11px; color: #8893a7; flex-wrap: wrap; }
  .chips { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .est {
    border: 1px solid #c8d8ee; background: #e8eef8; color: #3b6fb0; border-radius: 8px;
    padding: 2px 7px; font-size: 11px; cursor: pointer; font-weight: 600;
  }
  .est.none { border-color: #e3e8f0; background: #f5f6f8; color: #b0b8c6; font-weight: 400; }
  .est:hover { border-color: #3b6fb0; }
  .hint {
    border: 1px dashed #c8d8ee; color: #3b6fb0; border-radius: 8px;
    padding: 2px 7px; font-size: 11px; cursor: pointer;
  }
  .hint:hover { background: #e8eef8; }
  .qbtns { display: flex; gap: 3px; }
  .qbtn {
    border: 1px solid #d8dee9; background: #fff; color: #5a6577; border-radius: 6px;
    width: 20px; height: 20px; font-size: 11px; cursor: pointer; line-height: 1; padding: 0;
  }
  .qbtn:hover { border-color: #3b6fb0; color: #3b6fb0; }
  .qbtn.on { background: #3b6fb0; border-color: #3b6fb0; color: #fff; }
  .mini { font-size: 11px; color: #8893a7; }
  .mini.done { color: #2e9e5b; }
  .mini.stall { color: #d6453d; }
  .review-btn { font-size: 11px; color: #3b6fb0; cursor: pointer; text-decoration: underline; }

  .hidden { display: none !important; }
  .empty { text-align: center; color: #8893a7; padding: 40px 0; font-size: 13px; }

  /* ---- 每周时间安排 ---- */
  .wk-scroll { overflow-x: auto; padding-bottom: 6px; }
  .wk-table { min-width: 820px; }
  .wk-head { display: flex; gap: 4px; margin-bottom: 4px; }
  .wk-hcell { flex: 1; min-width: 100px; font-size: 11px; text-align: center; padding: 3px 0; font-weight: 600; }
  .wk-hcell:first-child { width: 54px; min-width: 54px; flex: none; }
  .wk-hcell small { display: block; font-weight: 400; font-size: 10px; }
  /* 周一–周五蓝色, 周六周日绿色 */
  .wk-hcell.weekday { color: #3b6fb0; }
  .wk-hcell.weekday small { color: #7ea6d6; }
  .wk-hcell.weekend { color: #2e9e5b; }
  .wk-hcell.weekend small { color: #8fc7a8; }
  /* 今天: 只加下划线标记, 不覆盖上面按星期几定的颜色 */
  .wk-hcell.today { text-decoration: underline; text-underline-offset: 3px; }
  .wk-hcell.today small { font-weight: 700; }
  .wk-body { display: flex; gap: 4px; }
  .wk-hours { width: 54px; min-width: 54px; flex: none; }
  .wk-hr { height: 34px; font-size: 10px; color: #b0b8c6; text-align: right; padding-right: 6px; line-height: 1; }
  .wk-col { flex: 1; min-width: 100px; position: relative; background: #fafbfd; border-radius: 8px; }
  .wk-cell { height: 34px; border-top: 1px solid #f0f3f8; }
  .wk-cell:first-child { border-top: none; }
  .wk-cell.over { background: #e8eef8; }
  /* 非工作时间(下班)底色与工作时间的分界线 —— 只做视觉区分, 不禁止安排。
     这两层必须 pointer-events:none, 否则会吃掉拖拽事件, 导致下班时段拖不进任务 */
  .wk-off { position: absolute; left: 0; right: 0; background: #eef1f6; pointer-events: none; }
  .wk-wline { position: absolute; left: 0; right: 0; border-top: 1px dashed #c8d1de; pointer-events: none; }
  /* 午休时段: 半透明覆盖层, 拖拽会被拒绝, 自动铺开也会跳过 */
  .wk-brk {
    position: absolute; left: 0; right: 0; z-index: 5; pointer-events: none;
    background: rgba(241,244,248,.82);
    border-top: 1px dashed #d8dee9; border-bottom: 1px dashed #d8dee9;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; color: #98a3b5; letter-spacing: 4px;
  }
  .wk-slot {
    position: absolute; left: 3px; right: 3px; border-radius: 7px; padding: 5px 8px 5px 7px;
    font-size: 11px; line-height: 1.35; overflow: hidden; cursor: pointer;
    display: flex; flex-direction: column;
  }
  .wk-slot:hover { box-shadow: 0 1px 6px rgba(0,0,0,.1); }
  .wk-slot .ws-name { font-weight: 600; color: #1f2733; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .wk-slot .ws-time { font-size: 10px; color: #5a6577; }
  .wk-slot .ws-x { position: absolute; right: 4px; top: 2px; color: #b0b8c6; font-size: 11px; }
  .wk-slot .ws-x:hover { color: #d6453d; }
  .wk-slot.done { opacity: .6; }
  .wk-foot { font-size: 12px; color: #5a6577; line-height: 1.9; margin-top: 11px; padding-top: 9px; border-top: 1px solid #f0f3f8; }
  .wk-foot b { color: #1f2733; }
  .wk-pool-head { display: flex; align-items: center; gap: 8px; margin: 15px 0 8px; }
  .wk-pool { display: flex; flex-wrap: wrap; gap: 8px; }
  .wk-chip {
    border: 1px solid #d8dee9; background: #fff; border-radius: 9px; padding: 6px 10px;
    font-size: 12px; cursor: grab; display: flex; align-items: center; gap: 6px; max-width: 100%;
  }
  .wk-chip:hover { border-color: #3b6fb0; }
  .wk-chip.dragging { opacity: .45; }
  .wk-chip .wq { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 6px; flex: none; }
  .wk-chip .wn { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .wk-chip .wh { font-size: 10px; color: #8893a7; flex: none; }

  /* 弹窗 */
  .modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
  .modal-bg.hide { display: none; }
  .modal { background: #fff; border-radius: 14px; padding: 22px; width: 520px; max-width: 100%; max-height: 88vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,.14); }
  .modal h3 { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
  .modal .sub { font-size: 12px; color: #8893a7; margin-bottom: 14px; }
  .modal label { display: block; font-size: 12px; color: #5a6577; margin: 12px 0 5px; }
  .modal input[type=text], .modal input[type=number], .modal select, .modal textarea {
    width: 100%; padding: 8px 10px; border: 1px solid #d8dee9; border-radius: 8px;
    font-size: 13px; font-family: inherit; box-sizing: border-box;
  }
  .modal-actions { display: flex; gap: 10px; margin-top: 18px; justify-content: flex-end; }
  .modal-actions button { padding: 7px 18px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid #d8dee9; background: #fff; color: #3a4456; }
  .modal-actions .btn-primary { background: #3b6fb0; color: #fff; border-color: #3b6fb0; }
  .modal-actions .btn-primary:hover { background: #2d5a94; }

  /* 后评估 */
  .facts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 14px; font-size: 12px; color: #5a6577; }
  .facts div { display: flex; justify-content: space-between; gap: 8px; border-bottom: 1px dashed #eef1f6; padding-bottom: 5px; }
  .facts b { color: #1f2733; }
  .facts b.bad { color: #d6453d; }
  .timeline { position: relative; height: 34px; margin: 14px 0 4px; }
  .tl-axis { position: absolute; left: 0; right: 0; top: 15px; height: 2px; background: #eef1f6; }
  .tl-gap { position: absolute; top: 13px; height: 6px; background: #f0dada; border-radius: 3px; }
  .tl-dot { position: absolute; top: 9px; width: 10px; height: 10px; border-radius: 50%; background: #3b6fb0; border: 2px solid #fff; box-shadow: 0 0 0 1px #c8d8ee; }
  .tl-cap { position: absolute; top: 22px; font-size: 10px; color: #8893a7; transform: translateX(-50%); white-space: nowrap; }
  .ask { background: #fef8e8; border: 1px solid #f3e2b8; border-radius: 10px; padding: 10px 12px; margin-top: 12px; font-size: 12px; color: #8a5d00; line-height: 1.6; }
  .ask .opts { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .ask .opts button { border: 1px solid #d8dee9; background: #fff; border-radius: 14px; padding: 4px 11px; font-size: 12px; cursor: pointer; color: #3a4456; }
  .ask .opts button:hover { border-color: #3b6fb0; color: #3b6fb0; }
  .blockers { margin-top: 12px; }
  .blocker { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 6px 0; border-bottom: 1px dashed #eef1f6; }
  .blocker .bt { font-weight: 600; }
  .blocker .bd { color: #8893a7; }
  .blocker .x { margin-left: auto; cursor: pointer; color: #b0b8c6; }
  .blocker .x:hover { color: #d6453d; }
  .blk-row { display: flex; gap: 8px; align-items: flex-end; margin-top: 10px; }
  .blk-row > div { flex: 1; min-width: 0; }

  /* 7 问自检 */
  .chk { display: flex; align-items: flex-start; gap: 9px; padding: 8px 0; border-bottom: 1px dashed #eef1f6; font-size: 13px; }
  .chk input { margin-top: 3px; flex: none; }
  .chk .dim { font-size: 11px; color: #8893a7; }
  .chk-res { margin-top: 14px; font-size: 13px; background: #f8fbff; border: 1px solid #dbe6f5; border-radius: 10px; padding: 11px 13px; line-height: 1.7; }

  /* toast / confirm */
  #toast {
    position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%) translateY(14px);
    background: rgba(31,39,51,.93); color: #fff; font-size: 13px; padding: 10px 18px;
    border-radius: 10px; opacity: 0; pointer-events: none; transition: all .22s;
    z-index: 2000; max-width: 80vw; line-height: 1.5;
  }
  #toast.on { opacity: 1; transform: translateX(-50%) translateY(0); }
  #toast.ok { background: rgba(46,158,91,.95); }
  #toast.err { background: rgba(214,69,61,.95); }
  #cfm-msg { font-size: 13px; color: #5a6577; line-height: 1.6; }

  /* ---- 移动端适配 (docs/design/mobile-responsive.md) ---- */
  @media (max-width: 640px) {
    body { padding: 18px 14px 40px; }
    .header { flex-direction: column; align-items: stretch; gap: 12px; }
    .title { font-size: 22px; }
    .nav-link { padding: 7px 13px; font-size: 12px; }
    .panel { padding: 13px 14px; }
    .diag-row { grid-template-columns: 1fr; gap: 6px; }
    .matrix { grid-template-columns: 1fr; }
    .facts { grid-template-columns: 1fr; }
    .modal { padding: 17px; }
    .blk-row { flex-direction: column; align-items: stretch; }
  }

  /* 触屏没有 hover: 操作按钮不要藏得太深, 拖拽不可靠, 以按钮路径为主 */
  @media (hover: none) {
    .est, .hint, .qbtn { padding: 4px 8px; }
    .qbtn { width: 24px; height: 24px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="head-left">
      <div class="head-title">
        <div class="title">时间四象限</div>
        <div class="subtitle" id="subtitle"></div>
      </div>
    </div>
    <div class="head-left">
      <a class="nav-link" href="tasks_view.html">← 任务清单</a>
      <a class="nav-link" href="task_flow.html">流程跟踪</a>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">每周时间安排<span class="cnt" id="wk-cnt"></span></div>
      <div class="chips">
        <span class="mini" id="wk-range"></span>
        <button class="est" onclick="clearWeek()">清空本周</button>
      </div>
    </div>
    <div class="wk-scroll" id="wkgrid"></div>
    <div class="wk-foot" id="wk-foot"></div>
    <div class="wk-pool-head">
      <span class="mini">待安排</span>
      <span class="mini" id="wk-pool-cnt"></span>
    </div>
    <div class="wk-pool" id="wk-pool"></div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">时间结构诊断</div>
      <div class="budget">
        每天 <input id="b-day" type="number" min="1" max="16" step="0.5">h
        − 机动 <input id="b-buf" type="number" min="0" max="8" step="0.5">h
        × <input id="b-days" type="number" min="1" max="7">天 =
        <b id="b-week">0</b>h/周
      </div>
    </div>
    <div id="diag"></div>
    <div class="diag-foot" id="diag-foot"></div>
  </div>

  <div class="matrix" id="matrix"></div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">待归类<span class="cnt" id="unc-cnt"></span></div>
      <div class="chips">
        <span class="mini" style="margin-right:8px">拖拽卡片到上方象限，或用卡片上的 A/B/C/D 按钮</span>
        <button class="est" onclick="adoptAllHints()">采纳全部建议</button>
      </div>
    </div>
    <div class="quad-body" id="unclassified"></div>
  </div>
</div>

<!-- 估时 / 实际工时 -->
<div class="modal-bg hide" id="m-est">
  <div class="modal" style="width:400px">
    <h3 id="est-title">填写工时</h3>
    <div class="sub" id="est-sub"></div>
    <label>预估剩余工时（小时，净专注时间，不含等待）</label>
    <input type="number" id="est-h" min="0" step="0.5" placeholder="留空表示未估算">
    <label>实际净投入（小时，任务完成后填）</label>
    <input type="number" id="act-h" min="0" step="0.5" placeholder="留空表示未填写">
    <div class="modal-actions">
      <button onclick="closeModal('m-est')">取消</button>
      <button class="btn-primary" onclick="saveHours()">保存</button>
    </div>
  </div>
</div>

<!-- 后评估 -->
<div class="modal-bg hide" id="m-review">
  <div class="modal">
    <h3 id="rv-title">任务后评估</h3>
    <div class="sub" id="rv-sub"></div>
    <div class="facts" id="rv-facts"></div>
    <div class="timeline" id="rv-timeline"></div>
    <div id="rv-ask"></div>
    <label>卡点记录（归类后可用于统计"最常因为什么卡住"）</label>
    <div class="blockers" id="rv-blockers"></div>
    <div class="blk-row">
      <div>
        <label style="margin-top:0">类型</label>
        <select id="rv-blk-type">__BLOCKER_OPTIONS__</select>
      </div>
      <div>
        <label style="margin-top:0">起（可空）</label>
        <input type="text" id="rv-blk-from" placeholder="2026/08/20">
      </div>
      <div>
        <label style="margin-top:0">止（可空）</label>
        <input type="text" id="rv-blk-to" placeholder="2026/08/26">
      </div>
      <button class="nav-link" style="border-radius:8px;padding:8px 14px" onclick="addBlocker()">添加</button>
    </div>
    <div class="modal-actions">
      <button onclick="closeModal('m-review')">关闭</button>
    </div>
  </div>
</div>

<!-- 7 问自检 -->
<div class="modal-bg hide" id="m-check">
  <div class="modal">
    <h3>接这件事之前，先问自己 7 个问题</h3>
    <div class="sub">勾选"是"。用于判定象限，也用于决定要不要直接拒绝。</div>
    <div id="chk-list"></div>
    <div class="chk-res" id="chk-res"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-check')">关闭</button>
      <button class="btn-primary" id="chk-apply" onclick="applyCheck()">采纳建议并归类</button>
    </div>
  </div>
</div>

<div class="modal-bg hide" id="m-slot">
  <div class="modal" style="width:360px">
    <h3 id="sl-title">调整时段</h3>
    <div class="sub" id="sl-sub"></div>
    <label>开始时间</label>
    <select id="sl-from"></select>
    <label>结束时间</label>
    <select id="sl-to"></select>
    <div class="modal-actions">
      <button onclick="closeModal('m-slot')">取消</button>
      <button class="btn-primary" onclick="saveSlot()">保存</button>
    </div>
  </div>
</div>

<div class="modal-bg hide" id="m-cfm">
  <div class="modal" style="width:380px">
    <h3 id="cfm-title">确认操作</h3>
    <div id="cfm-msg"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-cfm')">取消</button>
      <button class="btn-primary" id="cfm-ok" onclick="cfmOk()">确定</button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
const TASKS = __TASKS_JSON__;
const QUAD = __QUAD_META__;
const QUAD_ORDER = __QUAD_ORDER__;
const PRIO = __PRIORITY_META__;
const PRIO_ORDER = __PRIO_ORDER__;
const BLOCKER = __BLOCKER_META__;
const BUDGET = __BUDGET__;
const WEEK_META = __WEEK_META__;
const WEEK_PLAN = __WEEK_PLAN__;
const TODAY = "__TODAY__";

let state = {
  tasks: [],
  dayH: BUDGET.day_hours,
  bufH: BUDGET.day_buffer_h,
  daysW: BUDGET.days_per_week,
  plan: { week_start: '', slots: [] }
};
let editingSlot = -1;
let editing = null;   // 当前弹窗对应的任务编号
let dragNo = null;

function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function num(v) {
  const n = parseFloat(v);
  return isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : null;
}
function fmt(v) {
  if (v === null || v === undefined) return '—';
  return (Math.round(v * 10) / 10).toString();
}
function byNo(no) { return state.tasks.find(t => String(t.no) === String(no)); }

/* ---------------- 统计 ---------------- */
function weekHours() { return Math.max(0, state.dayH - state.bufH) * state.daysW; }

/* 只有未完成任务参与统计与归类: 已完成的任务是历史, 混进来会稀释当前的时间结构 */
function pending() { return state.tasks.filter(t => !t.finished); }

function stats() {
  const pool = pending();
  const est = pool.filter(t => num(t.estimate_h));
  const totalH = est.reduce((s, t) => s + num(t.estimate_h), 0);
  const byQ = {};
  QUAD_ORDER.forEach(q => {
    const list = est.filter(t => t.quadrant === q);
    const h = list.reduce((s, t) => s + num(t.estimate_h), 0);
    byQ[q] = { h: h, pct: totalH > 0 ? h / totalH * 100 : null, n: list.length };
  });
  return { totalH: totalH, byQ: byQ, estN: est.length, allN: pool.length };
}

/* 偏差解读: 偏离方向本身就是结论 —— 见设计文档 §3.4 */
function diagnose(q, pct) {
  if (pct === null) return '';
  const m = QUAD[q];
  if (q === 'A' && pct > m.max) return '救火占比过高 —— 检查 A 类里有多少其实是"拖成的 A"';
  if (q === 'B' && pct < m.min) return '最危险的信号 —— 长期价值投入不足，优先从 C 类回收时间';
  if (q === 'C' && pct > m.max) return '被别人的紧急事项牵着走 —— 能委托就委托，能拒就拒';
  if (q === 'D' && pct > 0) return '确认一下这些是否真的还要做';
  return '';
}

function r1(v) { return Math.round(v * 10) / 10; }

/* 结论句 —— 见设计文档 §3.4: 单纯摆数字没有价值, 偏离方向本身才是结论 */
function summarize(st) {
  const g = q => st.byQ[q].pct;
  const a = g('A'), b = g('B'), c = g('C'), d = g('D');
  const bad = [];
  if (b !== null && b < 65) bad.push('B 类只有 ' + r1(b) + '%，长期价值的投入被挤占');
  if (a !== null && a > 25) bad.push('A 类 ' + r1(a) + '%，救火占比偏高 —— 检查有多少是"拖成的 A"');
  if (c !== null && c > 15) bad.push('C 类 ' + r1(c) + '%，被别人的紧急事项牵着走');
  if (d !== null && d > 0) bad.push('D 类还占 ' + r1(d) + '%，确认一下是否真的还要做');
  if (bad.length) return { warn: true, text: '⚠ ' + bad.join('；') + '。' };
  return {
    warn: false,
    text: '✓ 结构在目标区间内' + (b !== null ? '（B 类 ' + r1(b) + '%）' : '') +
          (a !== null && a < 20 ? '。A 类偏低，说明最近没有救火任务，或者还没被识别出来' : '')
  };
}

function renderDiag() {
  const st = stats();
  const wh = weekHours();
  document.getElementById('b-week').textContent = fmt(wh);

  // 一个任务都没估算时, 不要摆四行 "—" —— 那样完全看不出这张卡在干什么
  if (st.estN === 0) {
    document.getElementById('diag').innerHTML =
      '<div class="diag-empty">还没有任务填过预估工时，比例暂时算不出来。' +
      '点卡片上的"未估算"填几个数字 —— 填完之后，这里会显示成这样：</div>' +
      '<div class="diag-demo">' +
      'B 重要不紧迫 &nbsp;&nbsp;<i>▓▓▓▓▓▓▓░░░</i>&nbsp; 71% &nbsp; 目标 65–80% &nbsp; ✓ 落在区间内<br>' +
      'C 紧迫不重要 &nbsp;&nbsp;<i>▓▓▓▓░░░░░░</i>&nbsp; 23% &nbsp; 目标 ≤15% &nbsp;&nbsp;&nbsp; ⚠ 超限 —— 被别人的紧急事项牵着走' +
      '</div>';
    document.getElementById('diag-foot').innerHTML =
      '分母 = 净可安排时间 ' + fmt(state.dayH - state.bufH) +
      'h/天（机动 ' + fmt(state.bufH) + 'h 在分母之外）· 口径：任务池工作量结构';
    return;
  }

  const rows = QUAD_ORDER.map(q => {
    const m = QUAD[q];
    const d = st.byQ[q];
    const pct = d.pct === null ? null : Math.round(d.pct * 10) / 10;
    const zoneLeft = m.max > 0 ? m.min : 0;
    const zoneW = m.max > 0 ? Math.max(2, m.max - m.min) : 0;
    const over = pct !== null && pct > m.max;
    const low = pct !== null && q === 'B' && pct < m.min;
    const cls = over ? 'over' : (low ? 'low' : '');
    const target = m.max === 0 ? '目标 0%' : '目标 ' + m.min + '–' + m.max + '%';
    const lo = wh * m.min / 100, hi = wh * m.max / 100;
    const hrs = m.max === 0
      ? '0h'
      : (m.min === 0
        ? '≤' + fmt(hi) + 'h/周 · ≤' + fmt(hi / state.daysW) + 'h/天'
        : fmt(lo) + '–' + fmt(hi) + 'h/周 · ' + fmt(lo / state.daysW) + '–' + fmt(hi / state.daysW) + 'h/天');
    const note = diagnose(q, pct);
    return `
      <div class="diag-row">
        <div class="qtag"><span class="qdot" style="background:${m.color}"></span>${q} · ${m.label}<small>${m.action}</small></div>
        <div class="qbar">
          ${zoneW > 0 ? `<span class="zone" style="left:${zoneLeft}%;width:${zoneW}%"></span>` : ''}
          ${pct !== null ? `<span class="fill" style="width:${Math.min(100, pct)}%;background:${m.color}"></span>` : ''}
        </div>
        <div class="qval">
          <b class="${cls}">${pct === null ? '—' : pct + '%'}</b>
          <span class="tgt">${target}</span>
          <div class="hrs">${hrs}</div>
          ${note ? `<span class="diag-note">${esc(note)}</span>` : ''}
        </div>
      </div>`;
  }).join('');

  document.getElementById('diag').innerHTML = rows;

  // 结论句: 只在超界时才说话是不够的, 正常状态也要明确说"正常", 否则看不出这张卡的作用
  const sum = summarize(st);
  const foot = [];
  foot.push('<div class="diag-summary' + (sum.warn ? ' warn' : '') + '">' + sum.text + '</div>');
  foot.push('基于 <b>' + st.estN + ' / ' + st.allN + '</b> 个未完成且已估算的任务 · 口径：任务池工作量结构（不是本周实际投入）');
  if (st.totalH > 0) foot.push('已估算总工时 ' + fmt(st.totalH) + 'h');
  if (st.estN / Math.max(1, st.allN) < 0.7) foot.push('⚠ 未估算的任务超过 30%，上面的比例还不可信');
  foot.push('分母 = 净可安排时间 ' + fmt(state.dayH - state.bufH) + 'h/天（机动 ' + fmt(state.bufH) + 'h 在分母之外）');
  document.getElementById('diag-foot').innerHTML = foot.join('<br>');
}

/* ---------------- 卡片 ---------------- */
function cardHtml(t) {
  const p = PRIO[t.priority] || PRIO.medium;
  const est = num(t.estimate_h);
  const hint = (t.q_hint && t.q_hint !== t.quadrant) ? t.q_hint : '';
  const btns = QUAD_ORDER.map(q =>
    `<button class="qbtn${t.quadrant === q ? ' on' : ''}" title="归入 ${q}" onclick="event.stopPropagation();setQuadrant('${esc(t.no)}','${t.quadrant === q ? '' : q}')">${q}</button>`
  ).join('');
  const prog = t.finished
    ? '<span class="mini done">✅ 已完成 ' + esc(t.completed_date || '') + '</span>'
    : '<span class="mini' + (t.stalled ? ' stall' : '') + '">' + (t.stalled ? '⚠ 停滞' : '进度 ' + t.today + '%') + '</span>';
  const rv = t.finished
    ? `<span class="review-btn" onclick="openReview('${esc(t.no)}')">后评估</span>`
    : '';
  return `
    <div class="card${t.finished ? ' done' : ''}" draggable="true" data-no="${esc(t.no)}" onclick="openHours('${esc(t.no)}')">
      <div class="card-head">
        <div>
          <div class="card-no">No.${esc(t.no)} · ${esc(t.category)} · ${esc(t.date)}</div>
          <div class="card-name">${esc(t.name)}</div>
        </div>
        <span class="badge" style="color:${p.color};background:${p.bg}">${p.short}</span>
      </div>
      <div class="card-foot">
        <span class="chips">
          <span class="est${est ? '' : ' none'}">${est ? '⏱ ' + fmt(est) + 'h' : '未估算'}</span>
          ${hint ? `<span class="hint" title="点击采纳（按优先级与紧迫性推导，仅供参考）" onclick="event.stopPropagation();setQuadrant('${esc(t.no)}','${hint}')">建议 ${hint}</span>` : ''}
        </span>
        <span class="chips">
          ${prog}
          ${rv}
          <span class="qbtns">${btns}</span>
        </span>
      </div>
    </div>`;
}

function renderMatrix() {
  const html = QUAD_ORDER.map(q => {
    const m = QUAD[q];
    const list = state.tasks.filter(t => t.quadrant === q);
    const h = list.reduce((s, t) => s + (num(t.estimate_h) || 0), 0);
    const body = list.length
      ? list.map(cardHtml).join('')
      : `<div class="quad-empty">${q === 'D' ? 'D 类暂时没有任务' : '暂无任务'}</div>`;
    return `
      <div class="quad" data-q="${q}">
        <div class="quad-head">
          <div class="quad-name">
            <span class="qdot" style="background:${m.color}"></span>
            ${q} · ${m.label}
            <span class="act" style="color:${m.color};background:${m.bg}">${m.action}</span>
          </div>
          <div class="quad-meta">${list.length} 个${h > 0 ? ' · 估时 ' + fmt(h) + 'h' : ''}</div>
        </div>
        <div class="quad-body">${body}</div>
      </div>`;
  }).join('');
  const el = document.getElementById('matrix');
  el.innerHTML = html;
  bindDrop(el);
}

function renderUnclassified() {
  const list = pending().filter(t => !t.quadrant);
  document.getElementById('unc-cnt').textContent = '（' + list.length + '）';
  const box = document.getElementById('unclassified');
  if (!list.length) {
    box.innerHTML = '<div class="quad-empty">全部任务都已归类</div>';
    return;
  }
  box.innerHTML = list.map(t => `
    <div class="card" draggable="true" data-no="${esc(t.no)}">
      <div class="card-head">
        <div>
          <div class="card-no">No.${esc(t.no)} · ${esc(t.category)} · ${esc(t.date)}</div>
          <div class="card-name">${esc(t.name)}</div>
        </div>
        <span class="badge" style="color:${(PRIO[t.priority] || PRIO.medium).color};background:${(PRIO[t.priority] || PRIO.medium).bg}">${(PRIO[t.priority] || PRIO.medium).short}</span>
      </div>
      <div class="card-foot">
        <span class="chips">
          <span class="est${num(t.estimate_h) ? '' : ' none'}" onclick="openHours('${esc(t.no)}')">${num(t.estimate_h) ? '⏱ ' + fmt(num(t.estimate_h)) + 'h' : '未估算'}</span>
          <span class="hint" onclick="openCheck('${esc(t.no)}')">7 问自检</span>
          ${t.q_hint ? `<span class="mini">推导建议 ${t.q_hint}</span>` : ''}
        </span>
        <span class="qbtns">
          ${QUAD_ORDER.map(q => `<button class="qbtn" title="归入 ${q}" onclick="setQuadrant('${esc(t.no)}','${q}')">${q}</button>`).join('')}
        </span>
      </div>
    </div>`).join('');
  bindDrag(box);
}

/* ---------------- 拖拽 ---------------- */
function bindDrag(root) {
  root.querySelectorAll('.card').forEach(c => {
    c.addEventListener('dragstart', e => {
      dragNo = c.dataset.no;
      c.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', dragNo);
    });
    c.addEventListener('dragend', () => { c.classList.remove('dragging'); dragNo = null; });
  });
}
function bindDrop(root) {
  root.querySelectorAll('.quad').forEach(z => {
    z.addEventListener('dragover', e => { e.preventDefault(); z.classList.add('dragover'); });
    z.addEventListener('dragleave', () => z.classList.remove('dragover'));
    z.addEventListener('drop', e => {
      e.preventDefault();
      z.classList.remove('dragover');
      const no = dragNo || e.dataTransfer.getData('text/plain');
      if (no) setQuadrant(no, z.dataset.q);
    });
  });
}

/* ---------------- 交互 ---------------- */
function render() {
  renderDiag();
  renderMatrix();
  renderUnclassified();
  const total = state.tasks.length;
  const pool = pending();
  const unc = pool.filter(t => !t.quadrant).length;
  document.getElementById('subtitle').textContent =
    '共 ' + total + ' 个任务 · 未完成 ' + pool.length + ' 个（已归类 ' +
    (pool.length - unc) + ' · 待归类 ' + unc + '）· 已完成 ' +
    (total - pool.length) + ' 个不参与统计';
}

function post(url, payload) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(r => r.json());
}

function setQuadrant(no, q) {
  const t = byNo(no);
  if (!t) return;
  const prev = t.quadrant;
  post('/api/set_quadrant', { no: String(no), quadrant: q }).then(d => {
    if (!d.ok) { toast(d.error || '操作失败', 'err'); return; }
    t.quadrant = q;
    render();
    toast(q ? 'No.' + no + ' 已归入 ' + q + ' 类' + (t.q_hint && t.q_hint !== q ? '（推导建议是 ' + t.q_hint + '）' : '') : 'No.' + no + ' 已移出象限', 'ok');
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* 一键采纳推导建议。逐条顺序提交 —— 并发写同一个 JSON 会互相覆盖 */
function adoptAllHints() {
  const targets = pending().filter(t => !t.quadrant && t.q_hint);
  if (!targets.length) { toast('当前没有可采纳的建议', ''); return; }
  const dist = {};
  targets.forEach(t => { dist[t.q_hint] = (dist[t.q_hint] || 0) + 1; });
  const desc = Object.keys(dist).map(k => k + ' 类 ' + dist[k] + ' 个').join('、');
  confirmBox(
    '将按推导建议归类 ' + targets.length + ' 个任务（' + desc + '）。<br><br>' +
    '推导依据是优先级与紧迫程度，仅供参考 —— 归类后随时可以用卡片按钮改回来。',
    function () {
      let done = 0, i = 0;
      (function next() {
        if (i >= targets.length) {
          render();
          toast('已按建议归类 ' + done + ' 个任务', 'ok');
          return;
        }
        const t = targets[i++];
        post('/api/set_quadrant', { no: String(t.no), quadrant: t.q_hint }).then(d => {
          if (d.ok) { t.quadrant = t.q_hint; done++; }
          next();
        }).catch(() => {
          render();
          toast('连接服务器失败，已归类 ' + done + ' 个', 'err');
        });
      })();
    },
    '采纳全部建议'
  );
}

function openHours(no) {
  const t = byNo(no);
  if (!t) return;
  editing = no;
  document.getElementById('est-title').textContent = 'No.' + no + ' 工时';
  document.getElementById('est-sub').textContent = t.name;
  document.getElementById('est-h').value = num(t.estimate_h) || '';
  document.getElementById('act-h').value = num(t.actual_h) || '';
  openModal('m-est');
}

function saveHours() {
  const no = editing;
  const t = byNo(no);
  if (!t) return;
  const est = num(document.getElementById('est-h').value);
  const act = num(document.getElementById('act-h').value);
  Promise.all([
    post('/api/set_estimate', { no: String(no), estimate_h: est }),
    post('/api/set_actual', { no: String(no), actual_h: act })
  ]).then(rs => {
    if (!rs[0].ok || !rs[1].ok) { toast((rs[0].error || rs[1].error) || '保存失败', 'err'); return; }
    t.estimate_h = est;
    t.actual_h = act;
    closeModal('m-est');
    render();
    let msg = '已保存';
    if (est && act) {
      const k = act / est;
      if (k > 1.2) msg += '：实际是估算的 ' + (Math.round(k * 100) / 100) + ' 倍';
    }
    toast(msg, 'ok');
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ---------------- 每周时间安排 ---------------- */
const WK = { start: 0, end: 0, brkStart: 0, brkEnd: 0, workStart: 0, workEnd: 0, names: [], row: 34 };

/* 该小时是否落在午休时段内 */
function inBreak(h) { return h >= WK.brkStart && h < WK.brkEnd; }

/* 浮点小时 -> "8:30" 这样的显示串 */
function hm(h) {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  return hh + ':' + (mm < 10 ? '0' : '') + mm;
}

function parseYmd(s) { return new Date(String(s).replace(/\//g, '-')); }
function two(n) { return (n < 10 ? '0' : '') + n; }
function md(d) { return (d.getMonth() + 1) + '/' + two(d.getDate()); }

function slotHtml(s, idx) {
  const t = byNo(s.no);
  if (!t) return '';
  const q = QUAD[t.quadrant];
  const color = q ? q.color : '#8893a7';
  const bg = q ? q.bg : '#f0f2f5';
  const top = (s.from - WK.start) * WK.row;
  const h = Math.max(20, (s.to - s.from) * WK.row - 3);
  return '<div class="wk-slot' + (t.finished ? ' done' : '') +
    '" style="top:' + top + 'px;height:' + h + 'px;border-left:3px solid ' + color + ';background:' + bg + '"' +
    ' title="' + esc(t.name) + ' · ' + hm(s.from) + '–' + hm(s.to) + '" onclick="openSlot(' + idx + ')">' +
    '<span class="ws-x" onclick="event.stopPropagation();delSlot(' + idx + ')">✕</span>' +
    '<span class="ws-name">' + esc(t.name) + '</span>' +
    (h > 40 ? '<span class="ws-time">' + hm(s.from) + '–' + hm(s.to) + '</span>' : '') +
    '</div>';
}

function renderWeek() {
  const plan = state.plan;
  const ws = parseYmd(plan.week_start || TODAY);
  const days = [];
  for (let i = 0; i < 7; i++) days.push(new Date(ws.getTime() + i * 86400000));
  const today = new Date();

  document.getElementById('wk-range').textContent = md(days[0]) + ' – ' + md(days[6]);
  const wcnt = document.getElementById('wk-cnt');
  if (wcnt) wcnt.textContent = plan.slots.length ? '（' + plan.slots.length + ' 个时段）' : '';

  let head = '<div class="wk-hcell"></div>';
  days.forEach((d, i) => {
    const isToday = d.toDateString() === today.toDateString();
    const cls = (i >= 5 ? ' weekend' : ' weekday') + (isToday ? ' today' : '');
    head += '<div class="wk-hcell' + cls + '">' +
      WK.names[i] + '<small>' + md(d) + '</small></div>';
  });

  let hours = '';
  for (let h = WK.start; h < WK.end; h += 1) hours += '<div class="wk-hr">' + hm(h) + '</div>';

  let cols = '';
  for (let day = 1; day <= 7; day++) {
    let cells = '';
    for (let h = WK.start; h < WK.end; h += 1) {
      cells += '<div class="wk-cell' + (inBreak(h) ? ' brk' : '') +
        '" data-day="' + day + '" data-hour="' + h + '"></div>';
    }
    const blocks = plan.slots
      .map((s, idx) => ({ s: s, idx: idx }))
      .filter(o => o.s.day === day)
      .map(o => slotHtml(o.s, o.idx)).join('');
    // 下班时段底色: 按 09:00 / 18:00 精确切, 与"整点半行"的边界无关
    const offs = [[WK.start, WK.workStart], [WK.workEnd, WK.end]]
      .filter(r => r[1] - r[0] > 0.001)
      .map(r => '<div class="wk-off" style="top:' + ((r[0] - WK.start) * WK.row) +
        'px;height:' + ((r[1] - r[0]) * WK.row) + 'px"></div>')
      .join('');
    const wlines = [WK.workStart, WK.workEnd]
      .map(h => '<div class="wk-wline" style="top:' + ((h - WK.start) * WK.row) + 'px"></div>')
      .join('');
    cols += '<div class="wk-col" data-day="' + day + '">' + cells + offs + wlines +
      '<div class="wk-brk" style="top:' + ((WK.brkStart - WK.start) * WK.row) +
      'px;height:' + ((WK.brkEnd - WK.brkStart) * WK.row) + 'px">午休</div>' +
      blocks + '</div>';
  }

  document.getElementById('wkgrid').innerHTML =
    '<div class="wk-table"><div class="wk-head">' + head + '</div>' +
    '<div class="wk-body"><div class="wk-hours">' + hours + '</div>' + cols + '</div></div>';

  bindWeekDrop();
  renderWeekFoot();
  renderWeekPool();
}

function renderWeekFoot() {
  const slots = state.plan.slots;
  const total = slots.reduce((a, s) => a + (s.to - s.from), 0);
  const budget = weekHours();
  const byQ = {};
  slots.forEach(s => {
    const t = byNo(s.no);
    const q = (t && t.quadrant) || '';
    byQ[q] = (byQ[q] || 0) + (s.to - s.from);
  });
  const parts = QUAD_ORDER.filter(q => byQ[q])
    .map(q => '<b style="color:' + QUAD[q].color + '">' + q + '</b> ' + fmt(byQ[q]) + 'h');
  let html = '本周已安排 <b>' + fmt(total) + 'h</b>';
  if (budget > 0) {
    html += ' / 净可安排 ' + fmt(budget) + 'h';
    if (total > budget) html += ' <span style="color:#d6453d">⚠ 已超出预算</span>';
  }
  if (parts.length) html += '<br>' + parts.join(' · ');
  const noQuad = byQ[''] ? byQ[''] : 0;
  if (noQuad) html += '<br><span style="color:#8890a0">其中 ' + fmt(noQuad) + 'h 属于未归类的任务</span>';
  document.getElementById('wk-foot').innerHTML = html;
}

/* 某任务本周已排的小时数 */
function arrangedHours(no) {
  return state.plan.slots
    .filter(s => String(s.no) === String(no))
    .reduce((a, s) => a + (s.to - s.from), 0);
}

function renderWeekPool() {
  // 判据是"排满了没有", 而不是"有没有排过" ——
  // 否则排不完的任务(例如 6h 只放得下 1h)会从待安排里消失, 剩下的工时再也排不了
  const pool = pending().filter(t => {
    const need = num(t.estimate_h) || 1;
    return need - arrangedHours(t.no) > 0.001;
  });
  document.getElementById('wk-pool-cnt').textContent = '（' + pool.length + '）拖进格子即可安排';
  const box = document.getElementById('wk-pool');
  if (!pool.length) {
    box.innerHTML = '<span class="mini">所有未完成任务都已排满</span>';
    return;
  }
  box.innerHTML = pool.map(t => {
    const q = QUAD[t.quadrant];
    const need = num(t.estimate_h) || 1;
    const done = arrangedHours(t.no);
    const tag = done > 0.001
      ? '还差 ' + fmt(need - done) + 'h'
      : (num(t.estimate_h) ? fmt(need) + 'h' : '未估算');
    return '<div class="wk-chip" draggable="true" data-no="' + esc(t.no) + '">' +
      (q ? '<span class="wq" style="color:' + q.color + ';background:' + q.bg + '">' + t.quadrant + '</span>' : '') +
      '<span class="wn">' + esc(t.name) + '</span>' +
      '<span class="wh">' + tag + '</span>' +
      '</div>';
  }).join('');
  box.querySelectorAll('.wk-chip').forEach(c => {
    c.addEventListener('dragstart', e => {
      dragNo = c.dataset.no;
      c.classList.add('dragging');
      e.dataTransfer.setData('text/plain', dragNo);
    });
    c.addEventListener('dragend', () => c.classList.remove('dragging'));
  });
}

function bindWeekDrop() {
  document.querySelectorAll('.wk-cell').forEach(cell => {
    cell.addEventListener('dragover', e => { e.preventDefault(); cell.classList.add('over'); });
    cell.addEventListener('dragleave', () => cell.classList.remove('over'));
    cell.addEventListener('drop', e => {
      e.preventDefault();
      cell.classList.remove('over');
      const no = dragNo || e.dataTransfer.getData('text/plain');
      if (no) addSlot(no, parseInt(cell.dataset.day, 10), parseFloat(cell.dataset.hour));
    });
  });
}

/* 从落点起找该天最近的空闲 1 小时段, 避免与已有安排重叠 */
/* 拖入时按任务的预估工时铺开。
   遇到午休或已占用的时段会"跳过并继续往后排", 因此可能生成多段
   (例如 6h 从 10:30 开始 → 10:30-11:30 + 13:30-18:30), 而不是只排到第一个障碍就停。 */
function addSlot(no, day, hour) {
  const t = byNo(no);
  const total = num(t && t.estimate_h) || 1;
  const need = Math.max(0, total - arrangedHours(no));   // 只接手"还没排够"的部分
  if (need <= 0.001) { toast('这个任务的预估工时已经排满了', ''); return; }
  const busy = state.plan.slots
    .filter(s => s.day === day)
    .map(s => [s.from, s.to]);
  const taken = h => busy.some(r => h >= r[0] && h < r[1]);
  const usable = h => h >= WK.start && h < WK.end && !inBreak(h) && !taken(h);

  let h = hour;                                   // 落点不可用时向后找第一个可用位置
  while (h < WK.end && !usable(h)) h += 0.5;
  if (h >= WK.end) { toast('这一天已经排满', 'err'); return; }

  const segs = [];
  let cur = null, left = need, added = 0;
  for (let x = h; x < WK.end && left > 0.001; x += 0.5) {
    if (usable(x)) {
      if (cur && Math.abs(cur[1] - x) < 0.001) {
        cur[1] = x + 0.5;                         // 与上一段相接则合并
      } else {
        cur = [x, x + 0.5];                       // 断开处开新段
        segs.push(cur);
      }
      left -= 0.5;
      added += 0.5;
    } else {
      cur = null;
    }
  }

  segs.forEach(s => state.plan.slots.push({
    no: String(no), day: day, from: s[0], to: s[1]
  }));
  const desc = segs.map(s => hm(s[0]) + '–' + hm(s[1])).join('、');
  if (left > 0.001) {
    savePlan('已排 ' + desc + '（共 ' + fmt(added) + 'h），当天还差 ' + fmt(left) + 'h');
  } else {
    savePlan('已排 ' + WK.names[day - 1] + ' ' + desc + '（' + fmt(added) + 'h）');
  }
}

function delSlot(idx) {
  state.plan.slots.splice(idx, 1);
  savePlan('已移出时间表');
}

function savePlan(msg) {
  const plan = state.plan;
  post('/api/week_plan', { week_start: plan.week_start, slots: plan.slots }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return; }
    renderWeek();
    if (msg) toast(msg, 'ok');
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function clearWeek() {
  if (!state.plan.slots.length) { toast('本周还没有安排', ''); return; }
  confirmBox('清空本周已安排的 ' + state.plan.slots.length +
    ' 个时段？<br><br>任务本身不会被删除，只是从时间表上拿下来。', function () {
    state.plan.slots = [];
    savePlan('已清空本周安排');
  }, '清空本周');
}

/* 把 8.5 .. 22.5 的半小时刻度填进下拉框(init 里先调用, 否则弹窗是空的) */
function fillHourOptions() {
  const fromEl = document.getElementById('sl-from');
  const toEl = document.getElementById('sl-to');
  const parts = [];
  for (let h = WK.start; h <= WK.end; h += 0.5) {
    parts.push('<option value="' + h + '">' + hm(h) + '</option>');
  }
  fromEl.innerHTML = parts.join('');
  toEl.innerHTML = parts.join('');
}

function openSlot(idx) {
  const s = state.plan.slots[idx];
  if (!s) return;
  const t = byNo(s.no);
  editingSlot = idx;
  document.getElementById('sl-title').textContent = t ? t.name : ('No.' + s.no);
  document.getElementById('sl-sub').textContent =
    WK.names[s.day - 1] + ' · 当前 ' + hm(s.from) + '–' + hm(s.to);
  document.getElementById('sl-from').value = s.from;
  document.getElementById('sl-to').value = s.to;
  openModal('m-slot');
}

function saveSlot() {
  const s = state.plan.slots[editingSlot];
  if (!s) return;
  const f = Math.max(WK.start, Math.min(WK.end - 0.5,
    parseFloat(document.getElementById('sl-from').value) || s.from));
  const t = Math.max(f + 0.5, Math.min(WK.end,
    parseFloat(document.getElementById('sl-to').value) || s.to));
  s.from = f;
  s.to = t;
  closeModal('m-slot');
  savePlan('已更新时段');
}

function loadWeekPlan() {
  fetch('/api/week_plan').then(r => r.json()).then(d => {
    if (d && d.slots) { state.plan = d; renderWeek(); }
  }).catch(() => {});
}

/* ---------------- 后评估 ---------------- */
const ASK_OPTIONS = ['需求不清', '依赖他人', '返工', '想当然'];

function openReview(no) {
  const t = byNo(no);
  if (!t) return;
  editing = no;
  document.getElementById('rv-title').textContent = '后评估 · No.' + no;
  document.getElementById('rv-sub').textContent = t.name;

  const est = num(t.estimate_h), act = num(t.actual_h);
  const k = (est && act) ? act / est : null;
  const facts = [];
  facts.push(['完成日期', esc(t.completed_date || '—')]);
  facts.push(['总历时', t.total_days + ' 天' + (t.plan_days ? '（计划 ' + t.plan_days + ' 天）' : '')]);
  facts.push(['估时 → 实际', (est ? fmt(est) + 'h' : '未估') + ' → ' + (act ? fmt(act) + 'h' : '未填'),
    k !== null && k > 1.2 ? 'bad' : '']);
  facts.push(['最长空档', t.max_gap ? t.max_gap + ' 天（' + esc(t.max_gap_from) + '–' + esc(t.max_gap_to) + '）' : '—']);
  facts.push(['推进次数', (t.nodes || []).length + ' 次']);
  facts.push(['象限', t.quadrant ? t.quadrant + ' · ' + QUAD[t.quadrant].label : '未归类']);
  document.getElementById('rv-facts').innerHTML = facts.map(f =>
    '<div><span>' + f[0] + '</span><b class="' + (f[2] || '') + '">' + f[1] + '</b></div>').join('');

  document.getElementById('rv-timeline').innerHTML = timelineHtml(t);

  // 定向提问: 带日期锚点 + 预填选项, 比空白输入框好答得多 —— 见设计文档 §2.9.3
  const asks = [];
  if (t.max_gap && t.max_gap > 5) {
    asks.push({
      msg: '检测到 ' + esc(t.max_gap_from) + '–' + esc(t.max_gap_to) + ' 有 ' + t.max_gap + ' 天无推进，当时卡在哪？',
      opts: ASK_OPTIONS.concat(['技术难点', '外部阻塞', '精力不足']),
      range: [t.max_gap_from, t.max_gap_to]
    });
  }
  if (k !== null && k > 1.5) {
    asks.push({
      msg: '实际是估算的 ' + (Math.round(k * 100) / 100) + ' 倍，低估的主要原因？',
      opts: ASK_OPTIONS, range: ['', '']
    });
  }
  if (t.delayed) asks.push({ msg: '任务已延期，主要原因？', opts: ['需求不清', '依赖他人', '被打断', '估算失误'], range: ['', ''] });
  document.getElementById('rv-ask').innerHTML = asks.map((a, i) => `
    <div class="ask">
      ${a.msg}
      <div class="opts">
        ${a.opts.map(o => `<button onclick="quickBlocker('${esc(o)}','${esc(a.range[0])}','${esc(a.range[1])}')">${esc(o)}</button>`).join('')}
      </div>
    </div>`).join('');

  renderBlockers(t);
  openModal('m-review');
}

function timelineHtml(t) {
  const nodes = (t.nodes || []).filter(n => /^\d{4}\/\d{1,2}\/\d{1,2}$/.test(n.date));
  if (nodes.length < 2) return '';
  const first = new Date(nodes[0].date.replace(/\//g, '-')).getTime();
  const last = new Date(nodes[nodes.length - 1].date.replace(/\//g, '-')).getTime();
  const span = Math.max(1, (last - first) / 86400000);
  const pos = d => Math.min(99, Math.max(0, (new Date(d.replace(/\//g, '-')).getTime() - first) / 86400000 / span * 100));
  let gaps = '';
  for (let i = 1; i < nodes.length; i++) {
    const a = pos(nodes[i - 1].date), b = pos(nodes[i].date);
    if (b - a > 8) gaps += `<span class="tl-gap" style="left:${a}%;width:${b - a}%"></span>`;
  }
  const dots = nodes.map(n => `<span class="tl-dot" style="left:${pos(n.date)}%"></span>`).join('');
  return `<div class="tl-axis"></div>${gaps}${dots}
    <span class="tl-cap" style="left:0">${esc(nodes[0].date)}</span>
    <span class="tl-cap" style="left:100%">${esc(nodes[nodes.length - 1].date)}</span>`;
}

function renderBlockers(t) {
  const list = t.blockers || [];
  const box = document.getElementById('rv-blockers');
  box.innerHTML = list.length
    ? list.map((b, i) => `
      <div class="blocker">
        <span class="bt" style="color:${(BLOCKER[b.type] || {}).color || '#8893a7'}">${esc(b.type)}</span>
        <span class="bd">${esc(b.from || '')}${b.from && b.to ? '–' : ''}${esc(b.to || '')}${b.note ? ' · ' + esc(b.note) : ''}</span>
        <span class="x" onclick="delBlocker(${i})">✕</span>
      </div>`).join('')
    : '<div class="mini">还没有记录卡点。过程中的卡点最好顺手记在流程节点备注里。</div>';
}

function saveBlockers(t, next) {
  return post('/api/set_blockers', { no: String(t.no), blockers: next }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return false; }
    t.blockers = next;
    renderBlockers(t);
    return true;
  }).catch(() => { toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'); return false; });
}

function quickBlocker(type, from, to) {
  const t = byNo(editing);
  if (!t) return;
  const next = (t.blockers || []).concat([{ type: type, from: from || '', to: to || '', note: '' }]);
  saveBlockers(t, next).then(ok => { if (ok) toast('已记录卡点：' + type, 'ok'); });
}

function addBlocker() {
  const t = byNo(editing);
  if (!t) return;
  const type = document.getElementById('rv-blk-type').value;
  const from = document.getElementById('rv-blk-from').value.trim();
  const to = document.getElementById('rv-blk-to').value.trim();
  const next = (t.blockers || []).concat([{ type: type, from: from, to: to, note: '' }]);
  saveBlockers(t, next).then(ok => {
    if (ok) {
      document.getElementById('rv-blk-from').value = '';
      document.getElementById('rv-blk-to').value = '';
      toast('已添加卡点', 'ok');
    }
  });
}

function delBlocker(i) {
  const t = byNo(editing);
  if (!t) return;
  const next = (t.blockers || []).filter((b, k) => k !== i);
  saveBlockers(t, next);
}

/* ---------------- 7 问自检 (设计文档 §2.5) ---------------- */
const CHECKS = [
  ['这件事能给组织带来价值吗？', '价值 · 组织'],
  ['这件事能给我带来价值吗？', '价值 · 个人（当下）'],
  ['这件事对我的职业规划重要吗？', '价值 · 个人（长期）'],
  ['这件事对我重要吗？', '价值 · 个人（综合）'],
  ['我是唯一可以做这件事的人吗？', '可替代性'],
  ['拒绝他会损害我们的关系吗？', '拒绝成本 · 关系'],
  ['拒绝他会造成不利的影响吗？', '拒绝成本 · 风险']
];

function openCheck(no) {
  const t = byNo(no);
  if (!t) return;
  editing = no;
  document.getElementById('chk-list').innerHTML = CHECKS.map((c, i) => `
    <label class="chk">
      <input type="checkbox" id="chk-${i}">
      <span>${i + 1}. ${c[0]}<div class="dim">${c[1]}</div></span>
    </label>`).join('');
  document.getElementById('chk-list').querySelectorAll('input').forEach(cb => cb.addEventListener('change', calcCheck));
  calcCheck();
  openModal('m-check');
}

function calcCheck() {
  const on = i => document.getElementById('chk-' + i).checked;
  const value = on(0) || on(1) || on(2) || on(3);
  const stuck = on(4) || on(5) || on(6);
  let q = '';
  if (value && stuck) q = 'A';
  else if (value) q = 'B';
  else if (stuck) q = 'C';
  const box = document.getElementById('chk-res');
  if (!q) {
    box.innerHTML = '<b>建议：直接拒绝，不要登记进清单。</b><br>没有价值、也能推掉的事，登记进来就已经占用了认知空间（D 象限的正解是入口拒绝）。';
    document.getElementById('chk-apply').classList.add('hidden');
    return;
  }
  const m = QUAD[q];
  box.innerHTML = '<b>建议归入 ' + q + ' · ' + m.label + '（' + m.action + '）</b><br>' +
    '有价值：' + (value ? '是' : '否') + ' · 难以推卸：' + (stuck ? '是' : '否') + '<br>' +
    (q === 'C' ? '注意：C 类有 15% 上限，先想清楚能不能委托。' : '');
  document.getElementById('chk-apply').classList.remove('hidden');
  document.getElementById('chk-apply').dataset.q = q;
}

function applyCheck() {
  const q = document.getElementById('chk-apply').dataset.q;
  if (!q) return;
  const no = editing;
  closeModal('m-check');
  setQuadrant(no, q);
}

/* ---------------- 弹窗 / 提示 ---------------- */
let cfmCb = null;
function confirmBox(msg, cb, title) {
  document.getElementById('cfm-msg').innerHTML = msg;
  document.getElementById('cfm-title').textContent = title || '确认操作';
  cfmCb = cb;
  openModal('m-cfm');
}
function cfmOk() {
  closeModal('m-cfm');
  const cb = cfmCb;
  cfmCb = null;
  if (cb) cb();
}

function openModal(id) { document.getElementById(id).classList.remove('hide'); }
function closeModal(id) { document.getElementById(id).classList.add('hide'); }

let toastTimer = null;
function toast(msg, type) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'on' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ''; }, 2600);
}

function loadData() {
  fetch('/api/tasks').then(r => r.json()).then(data => {
    if (Array.isArray(data) && data.length) { state.tasks = data; render(); }
  }).catch(() => {});
}

function init() {
  state.tasks = TASKS;
  const bd = document.getElementById('b-day'), bb = document.getElementById('b-buf'), bw = document.getElementById('b-days');
  bd.value = state.dayH; bb.value = state.bufH; bw.value = state.daysW;
  [bd, bb, bw].forEach(el => el.addEventListener('change', () => {
    state.dayH = parseFloat(bd.value) || 0;
    state.bufH = parseFloat(bb.value) || 0;
    state.daysW = parseFloat(bw.value) || 1;
    renderDiag();   // 预算只影响小时换算, 不落盘
  }));
  document.querySelectorAll('.modal-bg').forEach(bg => {
    bg.addEventListener('click', e => { if (e.target === bg) bg.classList.add('hide'); });
  });
  state.plan = {
    week_start: (WEEK_PLAN && WEEK_PLAN.week_start) || '',
    slots: (WEEK_PLAN && WEEK_PLAN.slots) || []
  };
  WK.start = WEEK_META.start;
  WK.end = WEEK_META.end;
  WK.brkStart = WEEK_META.brkStart;
  WK.brkEnd = WEEK_META.brkEnd;
  WK.workStart = WEEK_META.workStart;
  WK.workEnd = WEEK_META.workEnd;
  WK.names = WEEK_META.names;
  fillHourOptions();
  render();
  renderWeek();
  bindDrag(document);
  loadData();
  loadWeekPlan();
}

init();
</script>
</body>
</html>
"""


def build_html(tasks):
    """拼装四象限页面 (数据内嵌, 双击即可看; 有服务器时以 /api/tasks 为准)。"""
    valid = [t for t in tasks if t.get("json_backed")]
    data_json = _embed(valid)

    blocker_options = "".join(
        '<option value="%s">%s</option>' % (b, b) for b in BLOCKER_ORDER
    )

    budget = {
        "day_hours": DAY_HOURS,
        "day_buffer_h": DAY_BUFFER_H,
        "day_plan_h": DAY_PLAN_H,
        "days_per_week": PLAN_DAYS_PER_WEEK,
        "week_plan_h": WEEK_PLAN_H,
    }
    week_meta = {
        "start": DAY_START,
        "end": DAY_END,
        "brkStart": BREAK_START,
        "brkEnd": BREAK_END,
        "workStart": WORK_START,
        "workEnd": WORK_END,
        "names": DAY_NAMES,
    }
    plan = read_week_plan()

    return (TEMPLATE
            .replace("__BLOCKER_OPTIONS__", blocker_options)
            .replace("__TASKS_JSON__", data_json)
            .replace("__QUAD_META__", js(QUADRANT_META))
            .replace("__QUAD_ORDER__", js(QUADRANT_ORDER))
            .replace("__PRIORITY_META__", js(PRIORITY_META))
            .replace("__PRIO_ORDER__", js(PRIORITY_ORDER))
            .replace("__BLOCKER_META__", js(BLOCKER_META))
            .replace("__BUDGET__", js(budget))
            .replace("__WEEK_META__", js(week_meta))
            .replace("__WEEK_PLAN__", js(plan))
            .replace("__TODAY__", TODAY_STR))


def main():
    parser = argparse.ArgumentParser(description="生成时间管理四象限页面")
    parser.add_argument("--open", action="store_true", help="生成后打开浏览器")
    args = parser.parse_args()

    tasks = read_tasks()
    if not tasks:
        print("[错误] task_flows.json 中没有可展示的任务数据")
        sys.exit(1)

    html = build_html(tasks)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    est = [t for t in tasks if t.get("estimate_h")]
    quad = [t for t in tasks if t.get("quadrant")]
    print(f"[完成] 已生成: {OUT_HTML}")
    print(f"       共 {len(tasks)} 个任务, 已归类 {len(quad)}, 已估算工时 {len(est)}")

    if args.open:
        webbrowser.open("file://" + os.path.abspath(OUT_HTML).replace("\\", "/"))


if __name__ == "__main__":
    main()