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
    CATEGORY_COLOR,
    CATEGORY_FALLBACK_COLOR,
    CATEGORY_FALLBACK_ICON,
    CATEGORY_ICON,
    CATEGORY_ORDER,
    DAY_HOURS,
    DAY_PLAN_H,
    DELIVERABLE_META,
    DELIVERABLE_ORDER,
    PLAN_DAYS_PER_WEEK,
    PRIORITY_META,
    PRIORITY_ORDER,
    QUADRANT_META,
    QUADRANT_ORDER,
    WEEK_BUFFER_H,
    WEEK_GROSS_H,
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
    GRID_MIN,
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
  .diag-legend {
    display: flex; flex-wrap: wrap; align-items: center; gap: 5px 16px;
    padding: 9px 0 8px; font-size: 11px; color: #8893a7;
    border-bottom: 1px solid #f0f3f8;
  }
  .diag-legend .lg {
    display: inline-block; width: 22px; height: 9px; margin-right: 5px;
    vertical-align: -1px; border-radius: 3px;
  }
  .diag-legend .lg-fill { background: #8893a7; border-radius: 5px; }
  /* 与 .qbar .zone 保持同一视觉语言: 斜纹 + 左右边界线 */
  .diag-legend .lg-zone {
    background: repeating-linear-gradient(45deg, rgba(90,101,119,.42) 0 1.5px, transparent 1.5px 4px);
    border-left: 1.5px solid rgba(90,101,119,.55);
    border-right: 1.5px solid rgba(90,101,119,.55);
    border-radius: 0;
  }
  .diag-legend .lg-note { color: #a8b0bd; }

  .diag-row { display: grid; grid-template-columns: max-content 1fr 236px; gap: 12px; align-items: center; padding: 9px 0; border-top: 1px solid #f0f3f8; }
  .diag-row:first-child { border-top: none; }
  .qtag { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .qdot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
  .qtag small { font-weight: 400; color: #8893a7; font-size: 11px; white-space: nowrap; }
  .qbar { position: relative; height: 12px; background: #eef1f6; border-radius: 6px; overflow: hidden; }
  /* 目标区间用斜纹 + 边界线, 而不是实心色块:
     1) 实心块会被读成"第二段进度条"; 2) 它必须盖在进度条之上 ——
     实际值落在区间内时(达标), 实心块会被进度条完全遮住, 恰好最该看到目标的时候看不到。
     颜色固定为中性灰蓝, 不随象限变色 —— "目标"这个概念与象限无关, 各象限不同色会让人
     误以为三条带子含义不同。 */
  .qbar .zone {
    position: absolute; top: 0; bottom: 0; z-index: 2;
    background: repeating-linear-gradient(45deg, rgba(90,101,119,.42) 0 1.5px, transparent 1.5px 4px);
    border-left: 1.5px solid rgba(90,101,119,.55);
    border-right: 1.5px solid rgba(90,101,119,.55);
  }
  .qbar .fill { position: absolute; top: 0; bottom: 0; left: 0; z-index: 1; border-radius: 6px; opacity: .82; transition: width .3s ease; }
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
    position: absolute; left: 3px; right: 3px; border-radius: 7px; padding: 4px 8px 4px 7px;
    font-size: 11px; line-height: 1.35; overflow: hidden; cursor: pointer;
    /* 内容垂直居中: 矮块里上下留白已被压到最小, 靠居中而不是顶部对齐来用满高度 */
    display: flex; flex-direction: column; justify-content: center;
  }
  .wk-slot:hover { box-shadow: 0 1px 6px rgba(0,0,0,.1); }
  .wk-slot .ws-name { font-weight: 600; color: #1f2733; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .wk-slot .ws-time { font-size: 10px; color: #5a6577; }
  .wk-slot .ws-x { position: absolute; right: 4px; top: 2px; color: #b0b8c6; font-size: 11px; }
  .wk-slot .ws-x:hover { color: #d6453d; }
  .wk-slot.done { opacity: .6; }
  /* 临时(突发)任务: 虚线内框 + 角标, 与"计划内"的实心块一眼可分。
     它是记下来的时间, 不是排进去的计划, 视觉上就该有区别 */
  .wk-slot.temp { outline: 1px dashed #c9a961; outline-offset: -4px; }
  .ws-tmp {
    display: inline-block; font-size: 9px; line-height: 14px; height: 14px; padding: 0 4px;
    border-radius: 4px; background: #fdf4e3; color: #a8801f; margin-right: 4px; vertical-align: 1px;
  }
  /* 矮块(半小时): 缩字号、去掉上下留白、右侧给 ✕ 让位 ——
     否则内容高度超过容器, 会被 overflow:hidden 裁成半截字 */
  .wk-slot.sm { padding: 0 16px 0 6px; font-size: 10px; }
  .wk-slot.sm .ws-name { line-height: 1.2; }
  /* 角标跟着收: 14px 高的角标会把名称行撑高, 20px 的块里就不够用了 */
  .wk-slot.sm .ws-tmp {
    font-size: 8px; line-height: 12px; height: 12px; padding: 0 3px; margin-right: 3px;
  }
  .wk-slot.sm .ws-x { font-size: 10px; top: 1px; right: 3px; }
  /* 矮块里虚线内框要贴得更近, 否则会压到文字 */
  .wk-slot.sm.temp { outline-offset: -2px; }
  .wk-foot { font-size: 12px; color: #5a6577; line-height: 1.9; margin-top: 11px; padding-top: 9px; border-top: 1px solid #f0f3f8; }
  .wk-foot b { color: #1f2733; }
  .wk-edit { color: #3b6fb0; cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
  .wk-edit:hover { color: #2d5a94; }
  /* 周自评展示区 */
  .wk-rev { margin-top: 11px; }
  .wk-rev .rev-box {
    background: #fbfcfe; border: 1px solid #e3e8ef; border-left: 3px solid #7c6bc4;
    border-radius: 8px; padding: 10px 13px; font-size: 12px; color: #3c4658;
    line-height: 1.75; white-space: pre-wrap; word-break: break-word;
  }
  .wk-rev .rev-meta { font-size: 11px; color: #a8b0bd; margin-top: 6px; }
  .wk-rev .rev-meta b { color: #7c6bc4; font-weight: 600; }

  .wk-nav {
    border: 1px solid #d8dee9; background: #fff; border-radius: 6px; color: #5a6577;
    width: 24px; height: 22px; font-size: 14px; line-height: 1; padding: 0; cursor: pointer;
  }
  .wk-nav:hover { border-color: #3b6fb0; color: #3b6fb0; }
  .done-btn {
    border: 1px solid #cfe3d6; background: #f0f9f3; border-radius: 6px;
    font-size: 11px; line-height: 1; padding: 3px 6px; cursor: pointer;
  }
  .done-btn:hover { border-color: #2e9e5b; background: #e7f4ec; }
  /* 预期成果角标 */
  .dlib {
    border: 1px solid; border-radius: 6px; padding: 2px 6px; font-size: 10px;
    background: #fff; cursor: pointer; white-space: nowrap;
  }
  .dlib:hover { background: #f7f9fc; }
  .dlib.none { color: #a8b0bd !important; border-color: #dfe4ec !important; border-style: dashed; }

  /* ---- 仪表盘 ---- */
  .dash { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .dash-card { border: 1px solid #e3e8ef; border-radius: 10px; padding: 12px 14px; background: #fff; }
  .dash-card .dc-label { font-size: 12px; color: #8893a7; margin-bottom: 6px; }
  .dash-card .dc-value { font-size: 24px; font-weight: 700; color: #2b3444; line-height: 1.15; }
  .dash-card .dc-value small { font-size: 13px; font-weight: 400; color: #8893a7; margin-left: 3px; }
  .dash-card .dc-value .dc-tag { font-size: 12px; font-weight: 600; margin-left: 5px; }
  .dash-card .dc-sub { font-size: 11px; color: #8893a7; margin-top: 6px; line-height: 1.5; }
  .dash-card .dc-sub b { color: #5a6577; font-weight: 600; }
  .dash-trend { grid-column: 1 / -1; border: 1px solid #e3e8ef; border-radius: 10px; padding: 12px 14px; background: #fff; }
  .dash-bars { display: flex; align-items: flex-end; gap: 6px; height: 62px; margin-top: 14px; }
  .dash-bar { flex: 1; background: #cfd9e6; border-radius: 3px 3px 0 0; min-height: 2px; position: relative; }
  .dash-bar.on { background: #3b6fb0; }
  .dash-bar .db-n { position: absolute; top: -15px; left: 0; right: 0; text-align: center; font-size: 10px; color: #8893a7; }
  .dash-x { display: flex; gap: 6px; margin-top: 5px; }
  /* min-width:0 是必需的: flex 项目默认 min-width:auto, 压不到内容宽度以下,
     12 个日期标签在窄屏会把容器撑破 */
  .dash-x div { flex: 1; min-width: 0; text-align: center; font-size: 10px; color: #a8b0bd; }
  .dash-empty { border: 1px dashed #d8dee9; border-radius: 10px; padding: 16px; text-align: center; color: #8893a7; font-size: 12px; grid-column: 1 / -1; }
  .dist { margin-top: 10px; }
  .dist-row {
    display: grid; grid-template-columns: 100px 1fr 64px 92px 58px;
    align-items: center; gap: 8px; padding: 3px 0; font-size: 12px;
  }
  .dist-row .dir-name { color: #5a6577; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dist-row .dir-bar { height: 14px; background: #f0f2f5; border-radius: 4px; overflow: hidden; }
  .dist-row .dir-bar i { display: block; height: 100%; border-radius: 4px; }
  .dist-row .dir-pct { text-align: right; font-weight: 600; color: #2b3444; }
  .dist-row .dir-plan { text-align: right; color: #8893a7; font-size: 11px; }
  .dist-row .dir-diff { text-align: right; font-size: 11px; }

  .wk-pool-head { display: flex; align-items: center; gap: 8px; margin: 15px 0 8px; }
  .wk-pool { display: flex; flex-wrap: wrap; gap: 8px; }
  /* 待安排区的补充说明: 现在只用来解释「已排够」是什么意思(它们不再被移出池子) */
  #wk-pool-hint { margin-top: 10px; line-height: 1.75; }
  #wk-pool-hint b { color: #5a6577; }
  .wk-chip {
    border: 1px solid #d8dee9; background: #fff; border-radius: 9px; padding: 6px 10px;
    font-size: 12px; cursor: grab; display: flex; align-items: center; gap: 6px; max-width: 100%;
  }
  .wk-chip:hover { border-color: #3b6fb0; }
  .wk-chip.dragging { opacity: .45; }
  /* 本周已排够(按估时算): 淡一点, 与"还缺时间"的区分开。
     它仍然可以拖 —— 估时只是估计, 排满了不代表不用再排 */
  .wk-chip.enough { opacity: .6; }
  .wk-chip .wq { font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 6px; flex: none; }
  .wk-chip .wn { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .wk-chip .wh {
    font-size: 10px; color: #8893a7; flex: none; cursor: pointer;
    border-bottom: 1px dashed #c8cfda; padding-bottom: 1px;
  }
  .wk-chip .wh:hover { color: #3b6fb0; border-bottom-color: #3b6fb0; }

  /* 弹窗 */
  .modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 16px; }
  .modal-bg.hide { display: none; }
  .modal { background: #fff; border-radius: 14px; padding: 22px; width: 520px; max-width: 100%; max-height: 88vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,.14); }
  .modal h3 { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
  .modal .sub { font-size: 12px; color: #8893a7; margin-bottom: 14px; }
  .modal label { display: block; font-size: 12px; color: #5a6577; margin: 12px 0 5px; }
  .modal input[type=text], .modal input[type=number], .modal input[type=date], .modal input[type=time], .modal select, .modal textarea {
    width: 100%; padding: 8px 10px; border: 1px solid #d8dee9; border-radius: 8px;
    font-size: 13px; font-family: inherit; box-sizing: border-box;
  }
  /* 两个并排字段(如 开始/结束): 用 grid 让两列等宽且标签对齐 */
  .modal .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .modal-actions { display: flex; gap: 10px; margin-top: 18px; justify-content: flex-end; }
  .modal-actions button { padding: 7px 18px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid #d8dee9; background: #fff; color: #3a4456; }
  .modal-actions .btn-primary { background: #3b6fb0; color: #fff; border-color: #3b6fb0; }
  .modal-actions .btn-primary:hover { background: #2d5a94; }
  /* 工时弹窗里的 ✅: 用 margin-right:auto 推到最左, 与右边"取消/保存"分开 ——
     它是终态动作(而且会遇到确认框), 挨着保存键容易被误点。
     绿色是为了和蓝色主按钮区分开: 那个是"存下改动", 这个是"这件事做完了" */
  .modal-actions .btn-done {
    margin-right: auto; color: #2e9e5b; border-color: #a8d8bd; background: #f3fbf6;
  }
  .modal-actions .btn-done:hover { background: #2e9e5b; color: #fff; border-color: #2e9e5b; }

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
    /* 仪表盘 4 列在 390px 上每格只剩 ~78px, 数字会被挤到换行 —— 降到 2 列 */
    .dash { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .dash-card { padding: 10px 11px; }
    .dash-card .dc-value { font-size: 20px; }
    /* 分类占比: 小屏藏掉"计划"与"pp 差"两列, 只留名称/条/占比 */
    .dist-row { grid-template-columns: 78px 1fr 50px; }
    .dist-row .dir-plan, .dist-row .dir-diff { display: none; }
    /* 卡片底部左右两组按钮在窄屏会互挤, 改成上下排 */
    .card-foot { flex-direction: column; align-items: stretch; gap: 7px; }
    /* 趋势图: 12 组柱+标签在窄屏很挤, 缩小间距与字号 */
    .dash-bars, .dash-x { gap: 4px; }
    .dash-x div { font-size: 9px; }
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
      <!-- 相对链接: 项目页在 output/project/ 下, 靠服务端的 PROJECT_PAGES 路由转发
           (公网博客是把它们平铺在站点根目录, 所以不能用 ../project/ 这种本地路径) -->
      <a class="nav-link" href="project_index.html">项目管理</a>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">每周时间安排<span class="cnt" id="wk-cnt"></span></div>
      <div class="chips">
        <button class="wk-nav" onclick="shiftWeek(-1)" title="上一周">‹</button>
        <span class="mini" id="wk-range"></span>
        <button class="wk-nav" onclick="shiftWeek(1)" title="下一周">›</button>
        <button class="est" id="wk-back" onclick="shiftWeek(0)">回到本周</button>
        <button class="est" id="wk-rev-btn" onclick="openWeekReview()">📝 自评</button>
        <button class="est" onclick="openTempTask()" title="记录突发的临时事项，直接落到时间表上">＋ 临时任务</button>
        <button class="est" onclick="clearWeek()">清空本周</button>
      </div>
    </div>
    <div class="wk-scroll" id="wkgrid"></div>
    <div class="wk-foot" id="wk-foot"></div>
    <div class="wk-rev" id="wk-rev"></div>
    <div class="wk-pool-head">
      <span class="mini">待安排</span>
      <span class="mini" id="wk-pool-cnt"></span>
    </div>
    <div class="wk-pool" id="wk-pool"></div>
    <div class="mini" id="wk-pool-hint"></div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">时间结构诊断</div>
      <div class="budget">
        每天 <input id="b-day" type="number" min="1" max="16" step="0.5">h
        × <input id="b-days" type="number" min="1" max="7">天
        − 每周机动 <input id="b-wbuf" type="number" min="0" max="40" step="0.5"
                     title="本周留给突发的时间。改这里会记到当前查看的那一周名下，不是全局设置">h =
        <b id="b-week">0</b>h/周
      </div>
    </div>
    <div class="diag-legend">
      <span><i class="lg lg-fill"></i>实际占比</span>
      <span><i class="lg lg-zone"></i>目标区间 —— 该象限应有的占比</span>
      <span class="lg-note">实心条越过带子右边界＝超限，没够到左边界＝不足</span>
    </div>
    <div id="diag"></div>
    <div class="diag-foot" id="diag-foot"></div>
  </div>

  <div class="matrix" id="matrix"></div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">仪表盘<span class="mini" id="dash-stamp"></span></div>
      <div class="chips"><span class="mini">统计口径见每张卡片下方 · 本页操作即时生效</span></div>
    </div>
    <div class="dash" id="dash"></div>
  </div>

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

<!-- 预期成果 -->
<div class="modal-bg hide" id="m-dl">
  <div class="modal" style="width:420px">
    <h3>预期成果</h3>
    <div class="sub" id="dl-sub"></div>
    <label>这个任务要产出什么？（决定"产出成果"统计）</label>
    <select id="dl-sel"></select>
    <div class="mini" id="dl-hint" style="margin-top:8px;line-height:1.7"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-dl')">取消</button>
      <button class="btn-primary" onclick="saveDeliverable()">保存</button>
    </div>
  </div>
</div>

<!-- 本周自评 -->
<div class="modal-bg hide" id="m-wrev">
  <div class="modal" style="width:520px">
    <h3 id="wrev-title">本周自评</h3>
    <div class="sub" id="wrev-sub"></div>
    <label>这一周的情况（用自己的话写，给自己看）</label>
    <textarea id="wrev-text" rows="9" placeholder="可以写：&#10;· 哪些做成了、哪些没做到&#10;· 没做到的卡在哪（被打断 / 估时偏了 / 本来就不该接）&#10;· 下周要调整什么（配额、块粒度，还是直接砍任务）"></textarea>
    <div class="modal-actions">
      <button onclick="closeModal('m-wrev')">取消</button>
      <button class="btn-primary" onclick="saveWeekReview()">保存自评</button>
    </div>
  </div>
</div>

<!-- 估时 / 实际工时 -->
<div class="modal-bg hide" id="m-est">
  <div class="modal" style="width:400px">
    <h3 id="est-title">填写工时</h3>
    <div class="sub" id="est-sub"></div>
    <label>预计总共要投入多少工时（小时，净专注时间，不含等待）</label>
    <input type="number" id="est-h" min="0" step="0.5" placeholder="留空表示未估算">
    <label>累计实际投入（小时，可边做边更新）</label>
    <input type="number" id="act-h" min="0" step="0.5" placeholder="留空表示未记录">
    <div class="modal-actions">
      <button class="btn-done" id="est-done" onclick="saveHoursThenDone()"
              title="保存工时并标记为已完成">✅ 完成</button>
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
    <input type="time" id="sl-from" step="600">
    <label>结束时间</label>
    <input type="time" id="sl-to" step="600">
    <label>这次实际做了多少（分钟）</label>
    <input type="number" id="sl-done" min="0" step="5" placeholder="留空 = 只改时间">
    <div class="mini" id="sl-remain"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-slot')">取消</button>
      <button class="btn-primary" onclick="saveSlot()">保存</button>
    </div>
  </div>
</div>

<!-- 记一笔临时(突发)任务 -->
<div class="modal-bg hide" id="m-temp">
  <div class="modal" style="width:400px">
    <h3>记一笔临时任务</h3>
    <div class="sub" id="tmp-sub"></div>
    <label>这件事是什么</label>
    <input type="text" id="tmp-name" placeholder="如：临时会议 / 线上故障排查 / 同事来求助">
    <label>发生在哪天</label>
    <input type="date" id="tmp-date">
    <div class="two">
      <div>
        <label>开始</label>
        <input type="time" id="tmp-from" step="600">
      </div>
      <div>
        <label>结束</label>
        <input type="time" id="tmp-to" step="600">
      </div>
    </div>
    <div class="mini" id="tmp-hint"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-temp')">取消</button>
      <button class="btn-primary" onclick="saveTempTask()">记到时间表</button>
    </div>
  </div>
</div>

<!-- 本周机动额度 -->
<div class="modal-bg hide" id="m-buf">
  <div class="modal" style="width:400px">
    <h3>本周机动额度</h3>
    <div class="sub" id="buf-sub"></div>
    <label>这一周留给突发的时间（小时）</label>
    <input type="number" id="buf-h" min="0" max="40" step="0.5">
    <div class="mini" id="buf-hint"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-buf')">取消</button>
      <button onclick="resetWeekBuffer()">恢复默认</button>
      <button class="btn-primary" onclick="saveWeekBuffer()">保存</button>
    </div>
  </div>
</div>

<!-- 完成任务（顺带记一笔实际投入） -->
<div class="modal-bg hide" id="m-done">
  <div class="modal" style="width:400px">
    <h3>任务完成</h3>
    <div class="sub" id="dn-sub"></div>
    <label>实际投入了多少工时（小时）</label>
    <input type="number" id="dn-actual" min="0" step="0.5" placeholder="留空 = 不记录">
    <div class="mini" id="dn-hint"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-done')">取消</button>
      <button onclick="saveDone(false)">只标记完成</button>
      <button class="btn-primary" onclick="saveDone(true)">完成并记录</button>
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
const CAT = __CAT_META__;
const CAT_ORDER = __CAT_ORDER__;
const DL = __DELIVERABLE_META__;
const DL_ORDER = __DELIVERABLE_ORDER__;
const BUDGET = __BUDGET__;
const WEEK_META = __WEEK_META__;
const WEEK_PLAN = __WEEK_PLAN__;
const TODAY = "__TODAY__";

let state = {
  tasks: [],
  dayH: BUDGET.day_hours,
  daysW: BUDGET.days_per_week,
  // 机动额度是**周属性**: 挂在 plan 上, 跟着翻周走。
  // 不单独放一个 state.bufH —— 那样会出现"预算栏一个值、周表另一个值"的两份状态
  plan: { week_start: '', slots: [], buffer_h: BUDGET.week_buffer_h }
};
let editingSlot = -1;
let editing = null;   // 当前弹窗对应的任务编号
let doneTarget = null;   // 完成任务弹窗对应的任务编号
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
/* 时长显示: 不足 1 小时就说分钟。
   10 分钟 = 0.1667h, 按"小时 + 1 位小数"会显示成 0.2h(其实是 12 分钟) ——
   而临时突发恰恰常是几十分钟的量级, 这个舍入会让"我明明记了 10 分钟"对不上账 */
function fmtDur(h) {
  const m = Math.round(h * 60);
  return m < 60 ? m + ' 分钟' : fmt(h) + 'h';
}
function byNo(no) { return state.tasks.find(t => String(t.no) === String(no)); }

/* ---------------- 统计 ---------------- */
/* 当前查看那一周的机动额度(小时)。取不到就回落到默认值。 */
function weekBufferH() {
  const v = state.plan ? state.plan.buffer_h : null;
  return (typeof v === 'number' && isFinite(v) && v >= 0) ? v : BUDGET.week_buffer_h;
}

/* 净可安排 = 每天毛可用 × 天数 − 每周机动。
   机动是**整周一个池子**, 不是每天扣 1h —— 这样周三出一次 3h 的事故只是花掉池子的一部分,
   不会立刻被判成"超支"; 反过来没出事的日子也不浪费额度(见 meta.WEEK_BUFFER_H)。 */
function weekHours() {
  return Math.max(0, state.dayH * state.daysW - weekBufferH());
}

/* 只有未完成任务参与统计与归类: 已完成的任务是历史, 混进来会稀释当前的时间结构。
   临时(突发)任务同样排除 —— 它是**时间记录**, 不是待办:
   放进来会让"待归类"堆满琐事, 还会把突发工时算进象限结构。
   机动时间本就在象限分母之外(§1.3), 它的消耗在周表下方单列。 */
function pending() { return state.tasks.filter(t => !t.finished && !t.temp); }

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
  // 阈值一律读 QUAD, 不写字面量 —— 否则改 meta.py 的说法在这里不生效
  const bad = [];
  if (b !== null && b < QUAD.B.min) bad.push('B 类只有 ' + r1(b) + '%，长期价值的投入被挤占');
  if (a !== null && a > QUAD.A.max) bad.push('A 类 ' + r1(a) + '%，救火占比偏高 —— 检查有多少是"拖成的 A"');
  if (c !== null && c > QUAD.C.max) bad.push('C 类 ' + r1(c) + '%，被别人的紧急事项牵着走');
  if (d !== null && d > QUAD.D.max) bad.push('D 类还占 ' + r1(d) + '%，确认一下是否真的还要做');
  if (bad.length) return { warn: true, text: '⚠ ' + bad.join('；') + '。' };
  return {
    warn: false,
    text: '✓ 结构在目标区间内' + (b !== null ? '（B 类 ' + r1(b) + '%）' : '') +
          (a !== null && a < QUAD.A.min ? '。A 类偏低，说明最近没有救火任务，或者还没被识别出来' : '')
  };
}

function renderDiag() {
  const st = stats();
  const wh = weekHours();
  document.getElementById('b-week').textContent = fmt(wh);
  // 机动额度是周属性(翻周会变), 所以在这里回填而不是只在 init 里设一次。
  // 只在值真的不同时才写 —— 否则会打断正在输入的用户
  const bwb = document.getElementById('b-wbuf');
  if (bwb && parseFloat(bwb.value) !== weekBufferH()) bwb.value = weekBufferH();

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
      '百分比 = 各象限估时 ÷ 已估算总工时（任务池工作量结构）<br>' +
      '小时数 = 目标百分比 × 净可安排 ' + fmt(state.dayH * state.daysW - weekBufferH()) +
      'h/周（每周机动 ' + fmt(weekBufferH()) + 'h 在分母之外）';
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
    // C 的下界是 0 但语义是"上限 15%"（原话是单值 15%）, 写成 "≤15%" 才准确
    const target = m.max === 0 ? '目标 0%'
      : (m.min === 0 ? '目标 ≤' + m.max + '%' : '目标 ' + m.min + '–' + m.max + '%');
    const lo = wh * m.min / 100, hi = wh * m.max / 100;
    // 这行是"按周预算换算出的执行参考", 和上面的百分比(占任务池)不是同一个分母 ——
    // 必须带前缀说明, 否则会被读成"同一个占比的另一种写法"
    const hrs = m.max === 0
      ? '目标 0h'
      : '按 ' + fmt(wh) + 'h/周 ≈ ' + (m.min === 0
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
  // 两个数各有各的分母, 必须分开写清楚 ——
  // 从前合成一句"分母 = 净可安排时间"会和"任务池工作量结构"直接打架
  foot.push('基于 <b>' + st.estN + ' / ' + st.allN + '</b> 个未完成且已估算的任务');
  if (st.totalH > 0) {
    foot.push('<b>百分比</b> = 本象限估时 ÷ 已估算总工时 ' + fmt(st.totalH) +
      'h —— 口径是<u>任务池工作量结构</u>，不是本周实际投入');
  }
  if (st.estN / Math.max(1, st.allN) < 0.7) foot.push('⚠ 未估算的任务超过 30%，上面的比例还不可信');
  foot.push('<b>小时数</b> = 目标百分比 × 净可安排 ' + fmt(wh) + 'h/周（' +
    fmt(state.dayH) + 'h/天 × ' + fmt(state.daysW) + ' 天 = ' +
    fmt(state.dayH * state.daysW) + 'h，减每周机动 ' + fmt(weekBufferH()) + 'h）');
  document.getElementById('diag-foot').innerHTML = foot.join('<br>');
}

/* ---------------- 仪表盘 ---------------- */
/* 产出成果现在读任务是 deliverable 字段(预期成果), 不再用 category 推导。
   旧口径的实测问题: 7 项"成果"里 4 项是"开会/搭工具/看完指南/联系某人",
   同时"工程"分类的真实交付物(项目、仿真、小程序)被整类排除。 */

function ymdMs(s) {
  const d = parseYmd(s || '');
  return isNaN(d.getTime()) ? null : d.getTime();
}

/* 毫秒时间戳 -> 所在周的周一(YYYY/MM/DD) */
function weekKeyOf(ms) {
  const d = new Date(ms);
  return fmtYmd(new Date(d.getTime() - ((d.getDay() + 6) % 7) * 86400000));
}

function dashCard(label, value, unit, subs) {
  return '<div class="dash-card"><div class="dc-label">' + label + '</div>' +
    '<div class="dc-value">' + value + (unit ? '<small>' + unit + '</small>' : '') + '</div>' +
    (subs ? '<div class="dc-sub">' + subs + '</div>' : '') + '</div>';
}

function renderDash() {
  const box = document.getElementById('dash');
  // 标出数据新鲜度: 一眼看出页面数据是刚拉的, 还是停留很久了(没有自动同步)
  const stamp = document.getElementById('dash-stamp');
  if (stamp) stamp.textContent = '· 数据更新于 ' + new Date().toLocaleTimeString('zh-CN', { hour12: false });
  // 临时(突发)任务不进仪表盘: 这里衡量的是"计划内工作"的完成情况与投入结构,
  // 把突发琐事混进来会系统性拉低平均耗时(它们多半当天完成), 也会让投入占比失真
  const planTasks = state.tasks.filter(t => !t.temp);
  const done = planTasks.filter(t => t.finished && ymdMs(t.completed_date) !== null);
  if (!done.length) {
    box.innerHTML = '<div class="dash-empty">还没有已完成的任务 —— 完成任务后这里会显示平均耗时、每周产出与估时偏差</div>';
    return;
  }

  // 1. 平均完成时间: 均值容易被少数长任务拉偏, 所以均值与中位数一起给
  const days = done.map(t => t.total_days).filter(d => typeof d === 'number' && d >= 0);
  const sorted = days.slice().sort((a, b) => a - b);
  const avg = days.length ? days.reduce((a, b) => a + b, 0) / days.length : null;
  // 偶数个时取中间两项平均, 否则直接取上中位, 与"中位数"这个名字不符
  const med = !sorted.length ? null
    : (sorted.length % 2 ? sorted[(sorted.length - 1) / 2]
      : Math.round((sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2));
  // "当天完成"的琐事会把均值稀释掉 —— 单独给出，否则这个数字看不出真实分布
  const zeroN = days.filter(d => d === 0).length;
  const multi = days.filter(d => d > 0);
  const multiAvg = multi.length ? multi.reduce((a, b) => a + b, 0) / multi.length : null;
  const card1 = dashCard('平均完成时间',
    avg === null ? '—' : fmt(Math.round(avg * 10) / 10), '天',
    '中位数 <b>' + (med === null ? '—' : med) + '</b> 天 · 当天完成 <b>' + zeroN + '</b> 个<br>' +
    (multiAvg === null ? ''
      : '跨天任务平均 <b>' + fmt(Math.round(multiAvg * 10) / 10) + '</b> 天（' + multi.length + ' 个）· ') +
    '共 ' + days.length + ' 个已完成');

  // 2. 每周完成数: 本周 + 近 12 周趋势
  const byWeek = {};
  done.forEach(t => {
    const k = weekKeyOf(ymdMs(t.completed_date));
    byWeek[k] = (byWeek[k] || 0) + 1;
  });
  const thisW = thisWeekStart();
  const lastW = fmtYmd(new Date(parseYmd(thisW).getTime() - 7 * 86400000));
  const cur = byWeek[thisW] || 0, prev = byWeek[lastW] || 0;
  const diff = cur - prev;
  const arrow = diff > 0 ? '↑ +' + diff : (diff < 0 ? '↓ ' + diff : '持平');
  const arrowCol = diff > 0 ? '#2e9e5b' : (diff < 0 ? '#d6453d' : '#8893a7');
  const card2 = dashCard('本周完成', cur, '个',
    '上周 ' + prev + ' 个 <b style="color:' + arrowCol + '">' + arrow + '</b>');

  // 3. 产出成果: 读 deliverable 字段(预期成果), **不再用 category 推导**。
  //    旧口径把"科研/标准"分类的完成数当成果, 结果把"看完指南""联系某人"也算成成果,
  //    同时把工程类的真实产出(项目/仿真/小程序)全排除 —— 方向相反的两处误差都不可见。
  const marked = done.filter(t => t.deliverable);
  const unmarked = done.length - marked.length;
  const byDl = {};
  marked.forEach(t => byDl[t.deliverable] = (byDl[t.deliverable] || 0) + 1);
  const dlTxt = DL_ORDER.filter(d => byDl[d])
    .map(d => d + ' ' + byDl[d]).join(' · ');
  let card3;
  if (!marked.length) {
    // 老任务还没有这个字段 —— 宁可显示 —, 也不要拿旧口径编一个数出来
    card3 = dashCard('产出成果', '—', '',
      '尚无任务标记预期成果<br>' +
      (unmarked ? '<b style="color:#b7791f">' + unmarked + '</b> 个已完成任务未标记' : ''));
  } else {
    card3 = dashCard('产出成果', marked.length, '项',
      (dlTxt || '—') +
      (unmarked ? '<br><span style="color:#b7791f">另有 ' + unmarked + ' 个已完成任务未标记成果</span>' : '') +
      '<br>口径：已完成且填写了预期成果（与分类无关）');
  }

  // 4. 估时偏差系数: 就是设计文档 §2.8 要的那个数
  // 只统计**已完成**的任务。actual_h 现在可以边做边累加, 而进行中的比值还在变 ——
  // 没做完就计入, 会让"实际 ÷ 预估"偏低, 看起来像"习惯性高估", 方向正好相反。
  // (中途超预估的信号由待安排区的"超预估"标红负责, 不混进这个系数里)
  const pairs = planTasks.filter(t => t.finished && num(t.estimate_h) && num(t.actual_h));
  let card4;
  if (!pairs.length) {
    card4 = dashCard('估时偏差', '—', '',
      '还没有"预估 + 实际"都填的任务<br>完成时补一下实际净投入即可');
  } else {
    const k = pairs.reduce((s, t) => s + num(t.actual_h) / num(t.estimate_h), 0) / pairs.length;
    const kk = Math.round(k * 100) / 100;
    const kc = k > 1.15 ? '#d6453d' : (k < 0.85 ? '#2e9e5b' : '#5a6577');
    const ktxt = k > 1.15 ? '习惯性低估' : (k < 0.85 ? '习惯性高估' : '估算较准');
    card4 = dashCard('估时偏差', '×' + kk, '',
      '实际 ÷ 预估 · <span class="dc-tag" style="color:' + kc + '">' + ktxt + '</span><br>基于 ' +
      pairs.length + ' 条配对（未填实际的不计入）');
  }

  // 趋势: 近 12 周柱状图
  const base = parseYmd(thisW).getTime();
  const weeks = [];
  for (let i = 11; i >= 0; i--) weeks.push(fmtYmd(new Date(base - i * 7 * 86400000)));
  const counts = weeks.map(w => byWeek[w] || 0);
  const maxN = Math.max(1, Math.max.apply(null, counts));
  const bars = weeks.map((w, i) => {
    const h = Math.max(2, Math.round(counts[i] / maxN * 56));
    return '<div class="dash-bar' + (w === thisW ? ' on' : '') + '" style="height:' + h + 'px">' +
      (counts[i] ? '<span class="db-n">' + counts[i] + '</span>' : '') + '</div>';
  }).join('');
  const xs = weeks.map(w => '<div>' + w.slice(5, 7) + '/' + w.slice(8, 10) + '</div>').join('');
  const trend = '<div class="dash-trend"><div class="mini">每周完成任务数（近 12 周 · 蓝色柱为本周）</div>' +
    '<div class="dash-bars">' + bars + '</div><div class="dash-x">' + xs + '</div></div>';

  // 5. 各类任务的时间投入占比: 实际(actual_h, 仅已完成) 对照 计划(estimate_h, 全部已估算)
  //    两者口径不同 —— 混在一起会得出错误结论, 所以拆开算、分别标注
  const actBy = {}, planBy = {};
  let actAll = 0, planAll = 0;
  planTasks.forEach(t => {
    const c = t.category || '其他';
    if (num(t.actual_h)) { actBy[c] = (actBy[c] || 0) + num(t.actual_h); actAll += num(t.actual_h); }
    if (num(t.estimate_h)) { planBy[c] = (planBy[c] || 0) + num(t.estimate_h); planAll += num(t.estimate_h); }
  });
  const cats = Object.keys(actBy).concat(Object.keys(planBy))
    .filter((c, i, arr) => arr.indexOf(c) === i)
    .sort((a, b) => (actBy[b] || 0) - (actBy[a] || 0));
  let dist;
  if (!actAll && !planAll) {
    dist = '<div class="mini">还没有可统计的工时</div>';
  } else {
    dist = '<div class="dist">' + cats.map(c => {
      const m = CAT[c] || { color: '#8893a7', icon: '' };
      const a = actBy[c] || 0, p = planBy[c] || 0;
      const ap = actAll ? a / actAll * 100 : 0;
      const pp = planAll ? p / planAll * 100 : 0;
      const d = (actAll && planAll) ? ap - pp : null;
      // 该分类下没有任何已完成任务时是"无数据", 不是 0% ——
      // 显示成 0% 会读成"这个类别不重要", 而事实是"还没做", 结论正好相反
      const hasAct = actBy[c] !== undefined;
      const hasPlan = planBy[c] !== undefined;
      const ppTxt = hasPlan ? pp.toFixed(1) + '%' : '—';   // 与"无实际"对称: 不拿 0.0% 冒充数据
      const dTxt = !hasAct
        ? '<span style="color:#8893a7">尚无完成</span>'
        : (d === null ? '' :
          '<span style="color:' + (d > 1 ? '#d6453d' : (d < -1 ? '#2e9e5b' : '#8893a7')) + '">' +
          (d > 0 ? '+' : '') + (Math.round(d * 10) / 10) + 'pp</span>');
      return '<div class="dist-row">' +
        '<div class="dir-name">' + m.icon + ' ' + c + '</div>' +
        '<div class="dir-bar"><i style="width:' + (hasAct ? ap.toFixed(1) : 0) +
        '%;background:' + m.color + (hasAct ? '' : ';opacity:.28') + '"></i></div>' +
        '<div class="dir-pct">' + (hasAct ? ap.toFixed(1) + '%' : '—') + '</div>' +
        '<div class="dir-plan">计划 ' + ppTxt + '</div>' +
        '<div class="dir-diff">' + dTxt + '</div></div>';
    }).join('') + '</div>' +
      '<div class="mini" style="margin-top:8px">实际：' + fmt(actAll) + 'h / ' +
      planTasks.filter(t => num(t.actual_h)).length + ' 个任务（actual_h）· 计划：' + fmt(planAll) +
      'h / ' + planTasks.filter(t => num(t.estimate_h)).length +
      ' 个任务（estimate_h）· 两者口径不同，故分别标注</div>';
  }
  const distCard = '<div class="dash-trend"><div class="mini">各类任务的时间投入占比' +
    '（按实际净投入降序 · pp = 相对计划的百分点差）</div>' + dist + '</div>';

  box.innerHTML = card1 + card2 + card3 + card4 + distCard + trend;
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
  // 完成入口放在本页, 是为了让"完成任务 → 仪表盘变化"形成闭环 ——
  // 否则要跳到任务清单页去点, 再等这边轮询同步
  const doneBtn = t.finished ? '' :
    `<button class="done-btn" title="标记完成（立即计入仪表盘）" onclick="event.stopPropagation();doneTask('${esc(t.no)}')">✅</button>`;
  // 预期成果角标: 点它就地改 —— 它决定"产出成果"统计, 不该藏在编辑弹窗里
  const dlm = t.deliverable ? DL[t.deliverable] : null;
  const dlBadge = dlm
    ? `<span class="dlib" style="color:${dlm.color};border-color:${dlm.color}" title="预期成果：${esc(t.deliverable)}（点击修改）" onclick="event.stopPropagation();openDeliverable('${esc(t.no)}')">${esc(t.deliverable)}</span>`
    : `<span class="dlib none" title="未标记预期成果（点击设置）" onclick="event.stopPropagation();openDeliverable('${esc(t.no)}')">成果?</span>`;
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
          ${dlBadge}
          ${hint ? `<span class="hint" title="点击采纳（按优先级与紧迫性推导，仅供参考）" onclick="event.stopPropagation();setQuadrant('${esc(t.no)}','${hint}')">建议 ${hint}</span>` : ''}
        </span>
        <span class="chips">
          ${prog}
          ${rv}
          ${doneBtn}
          <span class="qbtns">${btns}</span>
        </span>
      </div>
    </div>`;
}

function renderMatrix() {
  const html = QUAD_ORDER.map(q => {
    const m = QUAD[q];
    // 这里刻意**含已完成**: 卡片会以"已做完"样式留在矩阵里(后评估要用它的历史)。
    // 但诊断区的占比只算未完成, 两个数字会不同 —— 所以下面标出已完成个数, 让它们能对上账。
    const list = state.tasks.filter(t => t.quadrant === q);
    const doneN = list.filter(t => t.finished).length;
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
          <div class="quad-meta">${list.length} 个${doneN ? '（含已完成 ' + doneN + '）' : ''}${h > 0 ? ' · 估时 ' + fmt(h) + 'h' : ''}</div>
        </div>
        <div class="quad-body">${body}</div>
      </div>`;
  }).join('');
  const el = document.getElementById('matrix');
  el.innerHTML = html;
  // 两个都要绑: innerHTML 重建会连同旧的 dragstart 监听一起丢掉。
  // 漏掉 bindDrag 的后果很隐蔽 —— 首屏能拖(init 里补绑过), 但任何一次 render()
  // 之后就静默失效, 用户只会觉得"拖拽有时候坏"。
  bindDrag(el);
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
          <button class="done-btn" title="标记完成（立即计入仪表盘）" onclick="doneTask('${esc(t.no)}')">✅</button>
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
  renderDash();
  renderMatrix();
  renderUnclassified();
  renderWeekPool();   // 改估时后待安排区的"还差 Xh"要跟着变, 否则得刷新页面才更新
  renderWeekFoot();   // 同理: 改象限后 wk-foot 里的 A/B/C/D 小时拆分要跟着变
  // total 也要排除临时任务, 否则与 pool 的口径对不上
  // ("共 N 个" 含临时任务、"未完成 M 个" 不含, 两个数字互相矛盾)
  const total = state.tasks.filter(t => !t.temp).length;
  const pool = pending();
  const unc = pool.filter(t => !t.quadrant).length;
  // 措辞要准确: 已完成的任务仍出现在象限矩阵里(带"已做完"样式与后评估入口),
  // 只是不计入象限占比与待安排池 —— 说"不参与统计"会与矩阵里的数字对不上
  document.getElementById('subtitle').textContent =
    '共 ' + total + ' 个任务 · 未完成 ' + pool.length + ' 个（已归类 ' +
    (pool.length - unc) + ' · 待归类 ' + unc + '）· 已完成 ' +
    (total - pool.length) + ' 个不计入象限占比与待安排';
}

function post(url, payload) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(r => {
    // 服务端未匹配路由时返回的是 HTML(404 页), 直接 r.json() 会抛异常,
    // 各处 catch 就会统一报"连接服务器失败" —— 把路由/参数问题误导成网络问题。
    const ct = r.headers.get('content-type') || '';
    if (!r.ok || ct.indexOf('json') < 0) {
      throw new Error(r.ok ? '服务端返回了非 JSON 响应' : '服务端返回 HTTP ' + r.status);
    }
    return r.json();
  });
}

/* 真正执行完成动作(不含确认与录入) */
function postComplete(no) {
  post('/api/complete_task', { no: String(no) }).then(d => {
    if (!d.ok) { toast(d.error || '操作失败', 'err'); return; }
    toast('No.' + no + ' 已完成', 'ok');
    loadData();            // 重新拉取: 仪表盘要立刻反映这次完成
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* 带确认的完成。actual 非 null 时先写实际投入再标记完成 ——
   顺序不能反: 反了的话第二步失败就留下"完成了但没有实际投入"的状态, 而任务已经不在待安排里了 */
function confirmComplete(no, t, actual) {
  confirmBox('把 <b>No.' + esc(no) + ' ' + esc(t.name) + '</b> 标记为已完成？<br><br>' +
    '完成后会从象限里移出，并立即计入仪表盘（平均耗时、本周完成、估时偏差）。',
    function () {
      if (actual === null || actual === undefined) { postComplete(no); return; }
      post('/api/set_actual', { no: String(no), actual_h: actual }).then(d => {
        if (!d.ok) { toast(d.error || '记录实际投入失败', 'err'); return; }
        postComplete(no);
      }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
    }, '完成任务');
}

/* 点 ✅ 的入口。
   估过时但没记过实际投入 → 先弹录入框: 任务一完成就从待安排消失, 不在这里顺手问一句,
   actual_h 大概率永远空着 —— 设计文档 §2.8.4 说的"完成时记一个数"就是这一步。
   已经记过的直接走确认, 不打扰。 */
function doneTask(no) {
  const t = byNo(no);
  if (!t) return;
  if (num(t.estimate_h) && !num(t.actual_h)) {
    doneTarget = String(no);
    document.getElementById('dn-sub').textContent = 'No.' + no + ' ' + t.name;
    document.getElementById('dn-actual').value = num(t.estimate_h) || '';
    document.getElementById('dn-hint').innerHTML =
      '预计投入 <b>' + fmtDur(num(t.estimate_h)) + '</b>（已预填，改一下就行）。<br>' +
      '它用于<b>估时校准</b> —— 算出你习惯性低估多少倍。跳过也能完成，只是那个系数会少了这条数据。';
    openModal('m-done');
    return;
  }
  confirmComplete(no, t, null);
}

function saveDone(withActual) {
  const no = doneTarget;
  const t = no ? byNo(no) : null;
  if (!t) { closeModal('m-done'); return; }
  let actual = null;
  if (withActual) {
    actual = parseFloat(document.getElementById('dn-actual').value);
    if (isNaN(actual) || actual < 0) { toast('实际投入要填 0 或正数', 'err'); return; }
  }
  closeModal('m-done');
  confirmComplete(no, t, actual);
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

/* 工时弹窗里的 ✅ —— 比卡片上那个多一层意义:
   这里是"边做边更新实际投入"的地方, 用户可能刚改完值就决定收工,
   所以完成前先把当前填的值存下来, 否则那一改会随弹窗关闭一起丢掉。*/
function saveHoursThenDone() {
  const no = editing;
  const t = byNo(no);
  if (!t) return;
  const est = num(document.getElementById('est-h').value);
  const act = num(document.getElementById('act-h').value);
  closeModal('m-est');

  // 顺序必须串行(同 saveHours): 服务端每个端点都是"读整个 JSON → 改一个字段 → 整文件写回",
  // 并行会互相覆盖。完成放最后 —— 任务一完成就从待安排移出, 前面任何一步失败都必须能停住
  post('/api/set_estimate', { no: String(no), estimate_h: est }).then(r1 => {
    if (!r1.ok) { toast(r1.error || '预估工时保存失败', 'err'); return false; }
    return post('/api/set_actual', { no: String(no), actual_h: act });
  }).then(r2 => {
    if (r2 === false) return;
    if (r2 && !r2.ok) {
      toast('预估工时已保存，但实际投入未保存：' + (r2.error || '未知错误'), 'err');
      loadData();
      return;
    }
    t.estimate_h = est;
    t.actual_h = act;
    // 工时上面刚写过, 这里 actual 传 null 不重复写。确认框仍要弹 ——
    // 完成会从象限移出并计入仪表盘, 不是个该静默发生的动作
    confirmComplete(no, t, null);
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function openHours(no) {
  const t = byNo(no);
  if (!t) return;
  editing = no;
  document.getElementById('est-title').textContent = 'No.' + no + ' 工时';
  document.getElementById('est-sub').textContent = t.name;
  document.getElementById('est-h').value = num(t.estimate_h) || '';
  document.getElementById('act-h').value = num(t.actual_h) || '';
  // 已完成的就不再给 ✅ 了(重复完成没有意义), 但工时仍可查改
  document.getElementById('est-done').style.display = t.finished ? 'none' : '';
  openModal('m-est');
}

function saveHours() {
  const no = editing;
  const t = byNo(no);
  if (!t) return;
  const est = num(document.getElementById('est-h').value);
  const act = num(document.getElementById('act-h').value);
  // 必须顺序提交, 不能用 Promise.all: 服务端是多线程, 两个端点都走
  // "读整个 JSON → 改一个字段 → 整文件写回", 并行时后写者会覆盖先写者的改动。
  // 本项目在 adoptAllHints() 里已写明这条原则, 这里不能例外。
  post('/api/set_estimate', { no: String(no), estimate_h: est }).then(r1 => {
    if (!r1.ok) { toast(r1.error || '预估工时保存失败', 'err'); return null; }
    return post('/api/set_actual', { no: String(no), actual_h: act });
  }).then(r2 => {
    if (r2 === null) return;                       // 前一个已失败, 不再往下走
    if (!r2.ok) {
      // 第一个已落盘、第二个没有 —— 说清楚, 否则用户以为整次保存都失败了
      toast('预估工时已保存，但实际投入未保存：' + (r2.error || '未知错误'), 'err');
      loadData();                                  // 拉回服务端真实状态, 避免本地与服务端不一致
      return;
    }
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
const WK = { start: 0, end: 0, brkStart: 0, brkEnd: 0, workStart: 0, workEnd: 0, names: [], row: 34, gridMin: 10 };

/* 半小时的块在时间轴上只有 17px, 不好点也不好读, 所以给个最小高度 */
const MIN_SLOT_H = 20;
/* 低于这个高度就走紧凑布局(.wk-slot.sm): 只留名称, 不放"临时"角标与时间段 */
const SNUG_H = 30;

/* 临时(突发)任务的配色 —— 与象限色不冲突。
   临时任务多半没有象限, 不加这套颜色就会和"未归类"的灰完全一样 */
const TEMP = { color: '#c9a961', bg: '#fdf9f0' };

/* 该小时是否落在午休时段内 */
function inBreak(h) { return h >= WK.brkStart && h < WK.brkEnd; }

/* 浮点小时 -> "8:30" 这样的显示串。
   先把小时归一到整分钟再拆 —— 用小数部分直接算会出问题: 10 分钟 = 1/6 小时在二进制里
   没有精确表示, 10.9999999 会被算成 mm=60, 显示成 "10:60" */
function hm(h) {
  const t = Math.round(h * 60);
  return Math.floor(t / 60) + ':' + two(t % 60);
}

/* 浮点小时 <-> <input type="time"> 的 "HH:MM" */
function hToTime(h) {
  const t = Math.round(h * 60);
  return two(Math.floor(t / 60)) + ':' + two(t % 60);
}
function timeToH(v) {
  const m = String(v || '').match(/^(\d{1,2}):(\d{2})$/);
  return m ? (+m[1] * 60 + +m[2]) / 60 : NaN;
}
/* 是否落在时间网格上(10 分钟的整数倍)。
   不落网格时**提示并拒绝**, 不静默挪到最近的网格 —— 那会表现为"说保存成功、却排在别的时间" */
function onGrid(h) {
  return Math.abs(Math.round(h * 60) % WK.gridMin) < 1e-6;
}
/* 读并校验一对时间输入框。通过返回 {f, t}, 否则返回 {err} */
function readTimeRange(fromId, toId) {
  const f = timeToH(document.getElementById(fromId).value);
  const t = timeToH(document.getElementById(toId).value);
  if (isNaN(f) || isNaN(t)) return { err: '请填写开始与结束时间' };
  if (!onGrid(f) || !onGrid(t)) return { err: '时间要以 ' + WK.gridMin + ' 分钟为单位' };
  if (f < WK.start - 1e-6 || t > WK.end + 1e-6)
    return { err: '时间要在 ' + hm(WK.start) + ' – ' + hm(WK.end) + ' 之间' };
  if (t - f < WK.gridMin / 60 - 1e-6)
    return { err: '结束时间至少要比开始晚 ' + WK.gridMin + ' 分钟' };
  return { f: f, t: t };
}

/* 按**本地时区**构造日期。不能用 new Date("2026-09-14") —— 那会被当成 UTC 午夜解析,
   在西半球时区会落到本地前一天, 让 getDay() 算出的"周几"整体错位一天。 */
function parseYmd(s) {
  const m = String(s || '').match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(NaN);
}
function two(n) { return (n < 10 ? '0' : '') + n; }
function md(d) { return (d.getMonth() + 1) + '/' + two(d.getDate()); }
function fmtYmd(d) { return d.getFullYear() + '/' + two(d.getMonth() + 1) + '/' + two(d.getDate()); }

/* 本周周一(YYYY/MM/DD) —— getDay(): 0=周日, 故 (getDay()+6)%7 得到 0=周一 */
function thisWeekStart() {
  const t = new Date();
  return fmtYmd(new Date(t.getTime() - ((t.getDay() + 6) % 7) * 86400000));
}

function shiftWeek(delta) {
  if (delta === 0) { loadWeekPlan(''); return; }        // 0 = 回到本周
  const cur = parseYmd(state.plan.week_start || TODAY);
  loadWeekPlan(fmtYmd(new Date(cur.getTime() + delta * 7 * 86400000)));
}

function slotHtml(s, idx) {
  const t = byNo(s.no);
  if (!t) return '';
  const q = QUAD[t.quadrant];
  // 临时任务多半没有象限, 给它琥珀色, 与"未归类"的灰区分开
  const color = q ? q.color : (t.temp ? TEMP.color : '#8893a7');
  const bg = q ? q.bg : (t.temp ? TEMP.bg : '#f0f2f5');
  const top = (s.from - WK.start) * WK.row;
  const h = Math.max(MIN_SLOT_H, (s.to - s.from) * WK.row - 3);
  const snug = h < SNUG_H;      // 半小时的块: 收掉上下留白并缩小角标, 见 .wk-slot.sm
  return '<div class="wk-slot' + (t.finished ? ' done' : '') + (t.temp ? ' temp' : '') +
    (snug ? ' sm' : '') +
    '" style="top:' + top + 'px;height:' + h + 'px;border-left:3px solid ' + color + ';background:' + bg + '"' +
    ' title="' + esc(t.name) + ' · ' + hm(s.from) + '–' + hm(s.to) + '" onclick="openSlot(' + idx + ')">' +
    '<span class="ws-x" onclick="event.stopPropagation();delSlot(' + idx + ')">✕</span>' +
    '<span class="ws-name">' + (t.temp ? '<span class="ws-tmp">临时</span>' : '') +
    esc(t.name) + '</span>' +
    (h > 40 ? '<span class="ws-time">' + hm(s.from) + '–' + hm(s.to) + '</span>' : '') +
    '</div>';
}

function renderWeek() {
  const plan = state.plan;
  const ws = parseYmd(plan.week_start || TODAY);
  const days = [];
  for (let i = 0; i < 7; i++) days.push(new Date(ws.getTime() + i * 86400000));
  const today = new Date();

  const isThisWeek = plan.week_start === thisWeekStart();
  document.getElementById('wk-range').textContent =
    md(days[0]) + ' – ' + md(days[6]) + (isThisWeek ? '（本周）' : '');
  const back = document.getElementById('wk-back');
  if (back) back.style.display = isThisWeek ? 'none' : '';
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
  renderWeekReview();
}

function renderWeekFoot() {
  const slots = state.plan.slots;
  const total = slots.reduce((a, s) => a + (s.to - s.from), 0);
  const budget = weekHours();
  const byQ = {};
  // 临时任务没有象限, 混进 byQ[''] 会让下面"未归类"的小时数虚高 —— 单独计
  let tempH = 0;
  slots.forEach(s => {
    const t = byNo(s.no);
    if (t && t.temp) { tempH += (s.to - s.from); return; }
    const q = (t && t.quadrant) || '';
    byQ[q] = (byQ[q] || 0) + (s.to - s.from);
  });
  const parts = QUAD_ORDER.filter(q => byQ[q])
    .map(q => '<b style="color:' + QUAD[q].color + '">' + q + '</b> ' + fmtDur(byQ[q]));
  let html = '本周已安排 <b>' + fmtDur(total) + '</b>';
  if (budget > 0) {
    html += ' / 净可安排 ' + fmtDur(budget);
    if (total > budget) html += ' <span style="color:#d6453d">⚠ 已超出预算</span>';
  }
  if (parts.length) html += '<br>' + parts.join(' · ');
  const noQuad = byQ[''] ? byQ[''] : 0;
  if (noQuad) html += '<br><span style="color:#8890a0">其中 ' + fmtDur(noQuad) + ' 属于未归类的任务</span>';
  // 机动额度对照 —— "机动时间被什么吃掉了"最直接的答案(§1.3 机动预留 / §8)。
  // 额度和消耗都按**周**比, 不按天: 突发不可能每天恰好 1h, 按天比会把"那天事多"误判成超支
  const bufH = weekBufferH();
  const over = tempH - bufH;
  html += '<br><span style="color:#a8801f">机动：已用 <b>' + fmtDur(tempH) + '</b> / 额度 ' +
    fmtDur(bufH) +
    (over > 0.001
      ? ' <b style="color:#d6453d">⚠ 超支 ' + fmtDur(over) + '（侵占了象限额度）</b>'
      : '<span style="color:#2e9e5b"> 剩 ' + fmtDur(bufH - tempH) + '</span>') +
    '</span> <a class="wk-edit" onclick="openWeekBuffer()">调整额度</a>';
  document.getElementById('wk-foot').innerHTML = html;
}

/* 某任务本周已排的小时数 */
function arrangedHours(no) {
  return state.plan.slots
    .filter(s => String(s.no) === String(no))
    .reduce((a, s) => a + (s.to - s.from), 0);
}

/* 剩余工作量 = 预计总投入 − 累计实际投入。

   **可能为负**(超预估) —— 调用方必须显式处理: 负数意味着"估时已经不够用了",
   而不是"这件事没得做了"。直接当成"没有剩余"隐藏掉, 就又变回"任务凭空消失"。
   未估算的任务按 1h 兜底(与旧行为一致)。 */
function remainOf(t) {
  return (num(t.estimate_h) || 1) - (num(t.actual_h) || 0);
}

function renderWeekPool() {
  // 判据是"任务做完了没有", 而不是"本周排满了没有" ——
  // 估时只是估计: 按估时排满 ≠ 真的够了; 而同一件事一周分两次做(周中 2h + 周末 2h)更常见。
  // 靠"排满就移出池子"来收拢列表, 上面两种情况都会变成"任务不见了", 而人不知道它去了哪,
  // 下次拖不动只会以为坏了。
  // 注意 arrangedHours() 只看**当前查看那一周**: 所以本周排满的任务, 翻到下一周仍是同一条。
  const all = pending();
  const gapOf = t => remainOf(t) - arrangedHours(t.no);
  // "本周已排够"(按估时算)不再移出池子, 只标出来: 让人知道它不缺时间, 但想再排照样能拖
  const full = all.filter(t => remainOf(t) > 0.001 && gapOf(t) <= 0.001);
  document.getElementById('wk-pool-cnt').textContent = '（' + all.length + '）拖进格子即可安排';
  const hint = document.getElementById('wk-pool-hint');
  if (hint) {
    hint.innerHTML = full.length
      ? '标「已排够」的 <b>' + full.length + '</b> 个是按<b>估时</b>算满了 —— ' +
        '估时不准时照样可以再排，拖进去会先按 1h 铺开'
      : '';
  }
  const box = document.getElementById('wk-pool');
  if (!all.length) {
    box.innerHTML = '<span class="mini">没有未完成的任务</span>';
    return;
  }
  box.innerHTML = all.map(t => {
    const q = QUAD[t.quadrant];
    const left = remainOf(t);
    // 剩余**为负**才是超预估。用 <= 0 判定会把"投入刚好等于预估"也算进来,
    // 于是显示成"超 0h" —— 既像 bug(用户实测反馈过), 又把两件不同的事混成了一个说法
    const over = left < -0.001;
    // 投入已达预估(剩余 ≈ 0): 同样不需要再排时间, 但说法必须和"超出"分开
    const met = !over && left <= 0.001 && !!num(t.estimate_h);
    const gap = left - arrangedHours(t.no);
    // 已排够 = 有估时、没超、也没做满, 且本周排的已经够剩余工作量了。它不是"没事做", 只是"不缺时间"
    const enough = !over && !met && !!num(t.estimate_h) && gap <= 0.001;
    const tag = !num(t.estimate_h) ? '未估算'
      : (over ? '超 ' + fmt(-left) + 'h'
              : (met ? '投入已满'
                     : (enough ? '已排够' : '差 ' + fmt(gap) + 'h')));
    // 超预估标红: 它是"估时偏了"最直接的信号, 不该看起来和正常任务一样
    return '<div class="wk-chip' + (enough || met ? ' enough' : '') + '" draggable="true" data-no="' + esc(t.no) + '">' +
      (q ? '<span class="wq" style="color:' + q.color + ';background:' + q.bg + '">' + t.quadrant + '</span>' : '') +
      '<span class="wn">' + esc(t.name) + '</span>' +
      '<span class="wh"' + (over ? ' style="color:#d6453d;border-bottom-color:#d6453d"' : '') +
      ' title="点击修改工时" onclick="event.stopPropagation();openHours(\'' + esc(t.no) + '\')">' + tag + '</span>' +
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
  // 变量名别用 left —— 下面铺开逻辑里那个 left 是"这次还剩多少没排", 含义不同, 重名会直接报错
  const remain = remainOf(t);                            // 剩余工作量(可能为负 = 超预估)
  // 这次铺开多少: 优先补上"还没排够"的缺口; 超预估或本周已排够时按 1h 铺开, 具体再手动调。
  // **不再拦截"本周已排满"** —— 估时只是估计, 人比估时更清楚还要多久;
  // 而"排满就不让拖"会让"同一件事一周分两次做"(周中 2h + 周末 2h)根本做不到
  let need = remain > 0.001 ? Math.max(0, remain - arrangedHours(no)) : 0;
  if (need <= 0.001) need = 1;
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

  const next = state.plan.slots.concat(segs.map(s => ({
    no: String(no), day: day, from: s[0], to: s[1]
  })));
  const desc = segs.map(s => hm(s[0]) + '–' + hm(s[1])).join('、');
  if (left > 0.001) {
    savePlan(next, '已排 ' + desc + '（共 ' + fmt(added) + 'h），当天还差 ' + fmt(left) + 'h');
  } else {
    savePlan(next, '已排 ' + WK.names[day - 1] + ' ' + desc + '（' + fmt(added) + 'h）');
  }
}

/* 把要移出的时段上记过的投入汇总成 [{no, hours}], 交给服务端一次性回退。
   按 no 累加 —— 同一任务占了多个时段时要合并成一笔, 否则会反复读写同一份任务文件,
   中间任何一次失败都更难收拾 */
function undoOf(slots) {
  const acc = {};
  slots.forEach(s => {
    const h = num(s.done_h) || 0;
    if (h > 0) acc[s.no] = (acc[s.no] || 0) + h;
  });
  return Object.keys(acc).map(no => ({ no: no, hours: Math.round(acc[no] * 60) / 60 }));
}

function delSlot(idx) {
  const s = state.plan.slots[idx];
  if (!s) return;
  const back = num(s.done_h) || 0;
  // 直接扣, 不做二次确认 —— 但把回退写进提示: 数字变了得让人知道为什么变。
  // 没记过投入的时段保持原提示, 不弹无关的话
  savePlan(state.plan.slots.filter((_, i) => i !== idx),
    back > 0 ? '已移出时间表，并回退 ' + fmtDur(back) + '实际投入' : '已移出时间表',
    undoOf([s]));
}

/* 提交周计划。**先提交、成功后才改本地** ——
   反过来(先改本地再提交)一旦失败就会留下脏状态: 内存里已经改了, 服务端没改,
   而且之后任何一次 renderWeek() 都会拿这份脏数据重绘, UI 与服务端长期不一致。
   调用方传"新值", 由这里负责在成功后落到 state.plan。 */
function savePlan(nextSlots, msg, undo) {
  const week = state.plan.week_start;
  post('/api/week_plan', { week_start: week, slots: nextSlots, undo: undo || [] }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return; }
    // 同 saveWeekReview: 回调里现取 state.plan, 避免等待期间翻周后写到已脱离的旧对象上
    if (state.plan.week_start !== week) { loadWeekPlan(week); return; }
    // 服务端已把要回退的投入扣掉了(见 undo 参数), 本地任务池得跟上 ——
    // 否则周表底部和弹窗里的"还差多少"仍按旧的 actual_h 算, 与文件里的值不一致
    (d.undone || []).forEach(u => {
      const t = byNo(u.no);
      if (t) t.actual_h = u.actual_h;
    });
    state.plan.slots = Array.isArray(d.slots) ? d.slots : nextSlots;  // 服务端清洗后的结果
    state.plan.review = d.review || null;   // 服务端一并带回(写排期不动自评)
    renderWeek();
    if (msg) toast(msg, 'ok');
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function clearWeek() {
  if (!state.plan.slots.length) { toast('这一周还没有安排', ''); return; }
  const undo = undoOf(state.plan.slots);
  const back = undo.reduce((a, u) => a + u.hours, 0);
  confirmBox('清空 ' + state.plan.week_start + ' 那一周已安排的 ' + state.plan.slots.length +
    ' 个时段？<br><br>任务本身不会被删除，只是从时间表上拿下来。' +
    // 整周一起清的影响面比删一个时段大得多, 这里必须提前说清回退多少 ——
    // 删单个时段可以只在事后提示(toast), 整周清空不能
    (back > 0 ? '<br><br>这些时段里通过周表记过的 <b>' + fmtDur(back) + '</b>实际投入会一并回退' +
      '（在任务清单页直接填的投入不受影响）。' : ''), function () {
    savePlan([], back > 0 ? '已清空本周安排，并回退 ' + fmtDur(back) + '实际投入' : '已清空本周安排', undo);
  }, '清空本周');
}

/* 时间输入改用 <input type="time"> 后, 这里原来那个"把半小时刻度填进下拉框"的
   fillHourOptions() 就没有用了 —— 用户可以直接输入任意 10 分钟刻度的时刻 */

/* 弹窗里的「原估 / 已投入 / 这次做了 / 还剩」实时预览。
   放在弹窗里而不是让人去别的页面翻 —— "这次做了多少"得看着总数才能填准 */
function renderSlotRemain() {
  const el = document.getElementById('sl-remain');
  if (!el) return;
  const s = state.plan.slots[editingSlot];
  const t = s ? byNo(s.no) : null;
  if (!t) { el.innerHTML = ''; return; }
  const total = num(t.estimate_h);
  const used = num(t.actual_h) || 0;
  const add = (parseFloat(document.getElementById('sl-done').value) || 0) / 60;
  let html = '本任务：' + (total ? '预计总投入 ' + fmtDur(total) : '未估算');
  if (used > 0) html += ' · 已投入 ' + fmtDur(used);
  if (add > 0) html += ' · 这次 ' + fmtDur(add);
  if (total) {
    const left = total - used - add;
    // 三种情况分开写: "还剩 0 分钟"和待安排区那个"超 0h"一样, 是个没意义的读数
    html += ' → ' + (left < -0.001 ? '超 <b style="color:#d6453d">' + fmtDur(-left) + '</b>'
      : left > 0.001 ? '还剩 <b>' + fmtDur(left) + '</b>'
      : '<b style="color:#2e9e5b">刚好用完</b>');
  }
  el.innerHTML = html;
}

function openSlot(idx) {
  const s = state.plan.slots[idx];
  if (!s) return;
  const t = byNo(s.no);
  editingSlot = idx;
  document.getElementById('sl-title').textContent = t ? t.name : ('No.' + s.no);
  document.getElementById('sl-sub').textContent =
    WK.names[s.day - 1] + ' · 当前 ' + hm(s.from) + '–' + hm(s.to);
  document.getElementById('sl-from').value = hToTime(s.from);
  document.getElementById('sl-to').value = hToTime(s.to);
  document.getElementById('sl-done').value = '';   // 每次打开都是"记一笔新的", 不保留上次输入
  renderSlotRemain();
  openModal('m-slot');
}

function saveSlot() {
  const idx = editingSlot;
  const s = state.plan.slots[idx];
  if (!s) return;
  const r = readTimeRange('sl-from', 'sl-to');
  if (r.err) { toast(r.err, 'err'); return; }
  const doneMin = parseFloat(document.getElementById('sl-done').value) || 0;
  if (isNaN(doneMin) || doneMin < 0) { toast('实际投入要填 0 或正数', 'err'); return; }
  closeModal('m-slot');

  // 不直接改 s: 交给 savePlan 在提交成功后统一落到 state.plan, 避免失败留下脏状态。
  // done_h 必须跟着走 —— 它是"通过这个时段记了多少投入"的账本, 删时段时靠它回退。
  // 重建对象时漏掉它, 之前在这个时段记的投入就永远退不回来了
  const next = state.plan.slots.map((x, i) =>
    i === idx ? { no: x.no, day: x.day, from: r.f, to: r.t,
                  done_h: Math.round(((num(x.done_h) || 0) + doneMin / 60) * 60) / 60 } : x);
  if (doneMin <= 0) { savePlan(next, '已更新时段'); return; }

  // 顺序有讲究: 先记实际投入(服务端累加), 再存时段。
  // savePlan 成功后要重绘周表, 而"还差 / 超预估"依赖新的 actual_h —— 反过来做会先用旧值画一遍
  post('/api/log_actual', { no: s.no, hours: doneMin / 60 }).then(d => {
    if (!d.ok) { toast(d.error || '记录实际投入失败', 'err'); return; }
    const t = byNo(s.no);
    if (t && d.task) { t.actual_h = d.task.actual_h; t.estimate_h = d.task.estimate_h; }
    savePlan(next, '已记录实际投入 ' + fmtDur(doneMin / 60));
    // 工作量正好填满、任务却还没标完成 → 顺口问一句。
    // **不自动完成**: "投入 = 预估"不等于"做完了"(估 8h、做了 8h 却还差收尾很常见),
    // 而完成会牵动仪表盘(平均耗时、本周完成数、估时偏差)—— 让数字自动触发这些后果, 比不做还危险
    if (t && num(t.estimate_h) && remainOf(t) <= 0.001 && !t.finished) {
      confirmBox('「' + esc(t.name) + '」的工作量已经填满：预计 ' +
        fmtDur(num(t.estimate_h)) + '，累计投入 ' + fmtDur(num(t.actual_h)) + '。<br><br>' +
        '要顺便标记为完成吗？', function () { postComplete(t.no); }, '工作量已填满');
    }
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ---------------- 临时(突发)任务 ---------------- */
/* 它只做**时间记录**: 占掉哪个时段、花了多久, 用来回答"机动时间被什么吃掉了"。
   所以走独立入口, 不进待办池(不参与象限诊断), 也不进仪表盘 —— 见 §1.3 机动预留。 */

function openTempTask() {
  const ws = parseYmd(state.plan.week_start || thisWeekStart());
  const now = new Date();
  // 默认今天; 今天不在当前查看的这一周时(翻到了历史周/下一周), 退回该周周一
  const inWeek = now >= ws && now < new Date(ws.getTime() + 7 * 86400000);
  const d = inWeek ? now : ws;

  const di = document.getElementById('tmp-date');
  // <input type="date"> 只认 YYYY-MM-DD, 而数据统一存 YYYY/MM/DD。
  // min/max 锁在当前查看的这一周 —— 记到别的周会表现为"记完就不见了"
  di.min = fmtYmd(ws).split('/').join('-');
  di.max = fmtYmd(new Date(ws.getTime() + 6 * 86400000)).split('/').join('-');
  di.value = fmtYmd(d).split('/').join('-');
  document.getElementById('tmp-name').value = '';

  // 默认时段: 今天就从"当前 10 分钟刻度"起 1h, 否则 9:00–10:00。
  // 突发多半是刚发生的事, 默认当下比默认上班时间少改两次
  let h0 = WK.workStart;
  if (inWeek && d.toDateString() === now.toDateString()) {
    const cur = now.getHours() +
      Math.floor(now.getMinutes() / WK.gridMin) * WK.gridMin / 60;
    if (cur >= WK.start && cur <= WK.end - 1) h0 = cur;
  }
  if (inBreak(h0)) h0 = WK.brkEnd;            // 落到午休时段就挪到午休之后
  document.getElementById('tmp-from').value = hToTime(h0);
  document.getElementById('tmp-to').value = hToTime(h0 + 1);

  document.getElementById('tmp-hint').innerHTML =
    '会作为一条<b>临时任务</b>记进 ' + state.plan.week_start + ' 那一周的时间表。<br>' +
    '它不进待办、不参与象限统计 —— 突发占用会在周表下方单独列出。';
  openModal('m-temp');
}

function saveTempTask() {
  const name = document.getElementById('tmp-name').value.trim();
  if (!name) { toast('请填写这件事是什么', 'err'); return; }
  const date = document.getElementById('tmp-date').value.split('-').join('/');
  const r = readTimeRange('tmp-from', 'tmp-to');
  if (r.err) { toast(r.err, 'err'); return; }

  post('/api/add_temp_task', { name: name, date: date, from: r.f, to: r.t }).then(d => {
    if (!d.ok) { toast(d.error || '记录失败', 'err'); return; }
    closeModal('m-temp');
    toast('已记下「' + name + '」' + fmtDur(d.hours), 'ok');
    // 服务端一次写了两处(任务 + 时段), 本地这两份状态都得跟上 ——
    // 只更新 slots 的话, 时段块会因为 byNo() 找不到这条新任务而整块不渲染
    if (d.task && !byNo(d.no)) state.tasks.push(d.task);
    if (state.plan.week_start === d.week_start) {
      state.plan.slots = d.slots;
      renderWeek();
      render();                 // 副标题的"共 N 个任务"也要跟着更新
    } else {
      loadWeekPlan(d.week_start);   // 记到了别的周 → 直接翻过去看
    }
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* ---------------- 本周机动额度 ---------------- */
/* 额度按周落盘, 而不是像"每天几小时 / 一周几天"那样只放在内存里 ——
   **调整这个动作本身就是信号**: 如果连着几周都在往上调, 说明 5h 这个基线定低了,
   或者突发已经常态化。不落盘的话, 这个证据每周刷新页面就没了。 */

function openWeekBuffer() {
  document.getElementById('buf-sub').textContent =
    state.plan.week_start + ' 那一周 · 已排 ' + state.plan.slots.length + ' 个时段';
  document.getElementById('buf-h').value = weekBufferH();
  document.getElementById('buf-hint').innerHTML =
    '默认 ' + fmt(BUDGET.week_buffer_h) + 'h。它只影响"净可安排"的换算（从周预算里扣掉），' +
    '不参与象限占比的分母。<br>' +
    '改回默认值等于没调过、不留痕 —— 所以"连着几周都往上调"这件事本身就能一眼看出来。';
  openModal('m-buf');
}

/* hours 不传 = 从弹窗输入框读; 传了 = 预算栏直接改(见 init 里的 change 绑定) */
function saveWeekBuffer(hours) {
  const week = state.plan.week_start;
  const h = (hours === undefined)
    ? parseFloat(document.getElementById('buf-h').value)
    : hours;
  if (isNaN(h) || h < 0) { toast('额度要填 0 或正数', 'err'); return; }
  post('/api/week_buffer', { week_start: week, hours: h }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return; }
    closeModal('m-buf');          // 弹窗没开时调用也无害
    // 等待期间可能翻了周: 只有还停在同一周时才改本地状态,
    // 否则会把额度落到一个已经脱离的 plan 对象上
    if (state.plan.week_start === week) {
      state.plan.buffer_h = d.buffer_h;
      renderDiag();
      renderWeekFoot();
    }
    toast('本周机动额度：' + fmt(d.buffer_h) + 'h', 'ok');
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function resetWeekBuffer() {
  saveWeekBuffer(BUDGET.week_buffer_h);
}

/* week 为空 = 本周(由服务端规范化); 传入具体周一则查看那一周 */
function loadWeekPlan(week) {
  const q = week ? '?week=' + encodeURIComponent(week) : '';
  fetch('/api/week_plan' + q).then(r => r.json()).then(d => {
    // renderDiag 也要跟着: 机动额度是周属性, 预算栏与"净可安排"得随周变
    if (d && d.slots) { state.plan = d; renderWeek(); renderDiag(); }
  }).catch(() => {
    // 不能静默失败: 直接双击打开 html 文件时 fetch 必失败, 表现为"点了没反应"
    toast('读取周计划失败 —— 请确认页面是通过本地服务器打开的', 'err');
  });
}

/* ---------------- 预期成果 ---------------- */
/* 成果类型与任务分类(category)正交: 领域是"科研"不代表产出是"论文",
   反过来"工程"任务也可能产出论文。所以单独一个字段, 单独填。 */
let dlEditing = null;

function openDeliverable(no) {
  const t = byNo(no);
  if (!t) return;
  dlEditing = String(no);
  const sel = document.getElementById('dl-sel');
  if (!sel.options.length) {
    sel.innerHTML = '<option value="">无（事务性任务）</option>' +
      DL_ORDER.map(d => `<option value="${esc(d)}">${esc(d)} —— ${esc((DL[d] || {}).hint || '')}</option>`).join('');
  }
  sel.value = t.deliverable || '';
  document.getElementById('dl-sub').textContent = 'No.' + no + ' ' + t.name;
  document.getElementById('dl-hint').innerHTML =
    '留空表示这是事务性任务、没有可交付物 —— 大部分任务确实如此，不必硬凑。<br>' +
    '这个字段也是<b>天然的完成标准</b>：成果达成了就该收尾，避免任务无限打磨（帕金森定律）。';
  openModal('m-dl');
}

function saveDeliverable() {
  const no = dlEditing;
  const t = byNo(no);
  if (!t) return;
  const val = document.getElementById('dl-sel').value;
  post('/api/set_deliverable', { no: String(no), deliverable: val }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return; }
    t.deliverable = val;
    closeModal('m-dl');
    render();
    toast(val ? 'No.' + no + ' 预期成果：' + val : 'No.' + no + ' 已标记为无成果任务', 'ok');
  }).catch(e => toast(e && e.message ? e.message : '连接服务器失败', 'err'));
}

/* ---------------- 本周自评 ---------------- */
/* 与排期同存 week_plan.json, 但走独立端点: 写自评不碰 slots, 写排期不碰自评 */
function renderWeekReview() {
  const box = document.getElementById('wk-rev');
  const btn = document.getElementById('wk-rev-btn');
  const r = state.plan.review;
  if (btn) btn.textContent = r ? '📝 自评 ✓' : '📝 自评';
  if (!r) { box.innerHTML = ''; return; }
  // 快照一起显示: 以后回看时能知道"当时排了多少", 而不是用今天的数字去解释当时的判断
  const meta = [];
  if (r.at) meta.push('写于 ' + esc(r.at));
  if (typeof r.plan_h === 'number') {
    meta.push('当时已排 ' + fmt(r.plan_h) + 'h / ' + (r.slot_n || 0) + ' 个时段');
  }
  if (typeof r.done_n === 'number') {
    meta.push('本周已完成 ' + r.done_n + ' 个' +
      (r.done_h ? '（净投入 ' + fmt(r.done_h) + 'h）' : ''));
  }
  box.innerHTML = '<div class="rev-box">' + esc(r.text) + '</div>' +
    (meta.length ? '<div class="rev-meta">' + meta.join(' · ') + '</div>' : '');
}

function openWeekReview() {
  const week = state.plan.week_start || thisWeekStart();
  const r = state.plan.review;
  // 标题跟着实际查看的周走 —— 翻到历史周还写"本周自评"会和副标题自相矛盾
  const isThis = week === thisWeekStart();
  document.getElementById('wrev-title').textContent = isThis ? '本周自评' : '周自评（' + week + '）';
  document.getElementById('wrev-sub').textContent =
    week + ' 那一周 · 已排 ' + state.plan.slots.length + ' 个时段' +
    (isThis ? '' : ' · 这是历史周，补写的自评会记在那一周名下');
  document.getElementById('wrev-text').value = r ? r.text : '';
  openModal('m-wrev');
}

function saveWeekReview() {
  const week = state.plan.week_start || thisWeekStart();
  const text = document.getElementById('wrev-text').value.trim();
  const now = new Date();
  const stamp = fmtYmd(now) + ' ' + two(now.getHours()) + ':' + two(now.getMinutes());
  // 两类快照: "排了多少"(计划侧) 与 "做完了多少"(实际侧)。
  // 只存文字的话, 以后回看只能用今天的数字去解释当时的结论, 很容易误判。
  // "本周已完成"的口径与仪表盘一致: completed_date 落在这一周内。
  const ws = parseYmd(week).getTime();
  if (isNaN(ws)) {   // 周不合法时宁可什么都不记 —— 否则 ms >= NaN 恒为假, 会静默记成"完成 0 个"
    toast('这一周的日期不合法，无法记录自评', 'err');
    return;
  }
  const weekDone = state.tasks.filter(t => {
    if (!t.finished || !t.completed_date) return false;
    const ms = parseYmd(t.completed_date).getTime();
    return !isNaN(ms) && ms >= ws && ms < ws + 7 * 86400000;
  });
  post('/api/week_review', {
    week_start: week,
    text: text,
    at: stamp,
    plan_h: state.plan.slots.reduce((s, x) => s + (x.to - x.from), 0),
    slot_n: state.plan.slots.length,
    done_n: weekDone.length,
    done_h: weekDone.reduce((s, t) => s + (num(t.actual_h) || 0), 0)
  }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return; }
    // 不要在回调里用闭包捕获的 plan: 等待期间用户可能翻周, state.plan 已被换成新对象,
    // 这时写回旧对象会表现为"提示保存成功但界面没变"。改成现取, 并校验周是否一致。
    if (state.plan.week_start !== week) { loadWeekPlan(week); return; }
    state.plan.review = d.review || null;
    closeModal('m-wrev');
    renderWeekReview();
    toast(text ? '自评已保存' : '自评已清除', 'ok');
  }).catch(e => toast(e && e.message ? e.message : '连接服务器失败', 'err'));
}

/* ---------------- 后评估 ---------------- */
/* 估时偏差的常见原因。取值必须落在 meta.BLOCKER_ORDER 内 ——
   这里直接存进 blockers 的 type 字段, 写一个枚举外的词(原先写的"想当然")会留下
   没有颜色/含义映射的孤立类型, "最常因为什么卡住"的统计随之失真。
   加了 filter 兜底: 即使以后手滑写错, 也会被丢掉而不是污染数据。 */
const ASK_OPTIONS = ['需求不清', '依赖他人', '返工', '估算失误'].filter(k => BLOCKER[k]);

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
    (q === 'C' ? '注意：C 类有 ' + QUAD.C.max + '% 上限，先想清楚能不能委托。' : '');
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

/* 拉取任务并重绘。只在页面加载、以及本页数据变更后各调用一次 ——
   不做定时轮询: 数据源就是本页操作与偶尔的外部编辑, 没必要让页面空转 */
function loadData() {
  fetch('/api/tasks').then(r => r.json()).then(data => {
    if (!Array.isArray(data) || !data.length) return;
    state.tasks = data;
    render();
  }).catch(() => {
    toast('读取任务失败 —— 请确认页面是通过本地服务器打开的', 'err');
  });
}

function init() {
  state.tasks = TASKS;
  // state.plan 要**先**赋值: 机动额度挂在它上面, 预算栏与周表都依赖它
  state.plan = {
    week_start: (WEEK_PLAN && WEEK_PLAN.week_start) || '',
    slots: (WEEK_PLAN && WEEK_PLAN.slots) || [],
    review: (WEEK_PLAN && WEEK_PLAN.review) || null,
    buffer_h: (WEEK_PLAN && typeof WEEK_PLAN.buffer_h === 'number')
      ? WEEK_PLAN.buffer_h : BUDGET.week_buffer_h
  };
  const bd = document.getElementById('b-day'), bw = document.getElementById('b-days');
  const bb = document.getElementById('b-wbuf');
  bd.value = state.dayH; bw.value = state.daysW; bb.value = weekBufferH();
  // "每天几小时 / 一周几天"是长期参数, 只影响换算、不落盘
  [bd, bw].forEach(el => el.addEventListener('change', () => {
    state.dayH = parseFloat(bd.value) || 0;
    state.daysW = parseFloat(bw.value) || 1;
    renderDiag();
    renderWeekFoot();  // wk-foot 里的"净可安排 Xh"也要跟着变
  }));
  // 机动额度不同: 它是**周属性**, 改了要落盘(理由见 saveWeekBuffer 上方注释)
  bb.addEventListener('change', () => saveWeekBuffer(parseFloat(bb.value)));
  document.querySelectorAll('.modal-bg').forEach(bg => {
    bg.addEventListener('click', e => { if (e.target === bg) bg.classList.add('hide'); });
  });
  WK.start = WEEK_META.start;
  WK.end = WEEK_META.end;
  WK.brkStart = WEEK_META.brkStart;
  WK.brkEnd = WEEK_META.brkEnd;
  WK.workStart = WEEK_META.workStart;
  WK.workEnd = WEEK_META.workEnd;
  WK.names = WEEK_META.names;
  WK.gridMin = WEEK_META.gridMin;
  // 时间输入框的上下界取自 WK(不写死在 HTML 里, 免得两处不一致)
  ['sl-from', 'sl-to', 'tmp-from', 'tmp-to'].forEach(id => {
    const el = document.getElementById(id);
    el.min = hToTime(WK.start);
    el.max = hToTime(WK.end);
  });
  // 填"这次实际做了多少"时实时预览还剩多少
  document.getElementById('sl-done').addEventListener('input', renderSlotRemain);
  render();
  renderWeek();
  // 不在这里 bindDrag(document): 各渲染函数自己负责绑(见 renderMatrix / renderUnclassified),
  // 否则会给人"document 上绑一次就一劳永逸"的错觉 —— innerHTML 重建后其实已经失效
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

    cat_meta = {
        c: {"color": CATEGORY_COLOR.get(c, CATEGORY_FALLBACK_COLOR),
            "icon": CATEGORY_ICON.get(c, CATEGORY_FALLBACK_ICON)}
        for c in CATEGORY_ORDER
    }

    budget = {
        "day_hours": DAY_HOURS,
        "days_per_week": PLAN_DAYS_PER_WEEK,
        # 机动按**周**给(不是每天): 突发事件不可能每天恰好 1h, 日配额是拿刚性尺子量弹性的事
        "week_buffer_h": WEEK_BUFFER_H,
        "week_gross_h": WEEK_GROSS_H,
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
        # 时间网格(分钟): 输入的时间必须落在它的整数倍上, 见 GRID_MIN 的注释
        "gridMin": GRID_MIN,
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
            .replace("__CAT_META__", js(cat_meta))
            .replace("__CAT_ORDER__", js(CATEGORY_ORDER))
            .replace("__DELIVERABLE_META__", js(DELIVERABLE_META))
            .replace("__DELIVERABLE_ORDER__", js(DELIVERABLE_ORDER))
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