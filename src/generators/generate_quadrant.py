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
    INTERRUPT_META,
    INTERRUPT_ORDER,
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
  /* "已完成 N ▾": 展开/收起已完成的历史卡片(后评估入口在那些卡片上)。
     原来只是"蓝色 + 虚线下划线"的小字, 混在"5 个 · 估时 4h"这行灰字里根本认不出来
     —— 实测用户找了半天。做成胶囊, 与卡片上的「⏱ 工时」同一套视觉, 字号也提到 12px。
     **选择器不收窄到 .quad-meta**: 临时任务面板复用同一个胶囊, 两处折叠交互保持一致 */
  .qdone {
    display: inline-block; font-size: 12px; font-weight: 600; line-height: 17px;
    color: #3b6fb0; background: #e8eef8; border: 1px solid #c8d8ee; border-radius: 8px;
    padding: 1px 8px; cursor: pointer; vertical-align: 1px;
  }
  .qdone:hover { background: #3b6fb0; color: #fff; border-color: #3b6fb0; }
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
  /* 后评估入口。原来只是一行带下划线的小字(约 33px 宽), 加上"已完成"默认收起,
     等于藏了两层 —— 实测用户找不到。改成与流程跟踪页一致的绿色胶囊 */
  .review-btn {
    font-size: 11px; color: #3a7a56; cursor: pointer; flex: none;
    border: 1px solid #a8d8bd; border-radius: 8px; padding: 2px 8px; background: #f3fbf6;
    transition: all .15s;
  }
  .review-btn:hover { background: #2e9e5b; color: #fff; border-color: #2e9e5b; }

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
  /* 预期成果角标。尺寸/圆角/字号刻意与左边的「⏱ 工时」(.est) 保持一致 ——
     原来是小一号(10px、圆角 6、padding 6)且未标记时用虚线边框,
     三个角标并排时它明显"矮一截、虚一档", 看着像没做完的东西 */
  .dlib {
    border: 1px solid; border-radius: 8px; padding: 2px 7px; font-size: 11px;
    background: #fff; cursor: pointer; white-space: nowrap;
  }
  .dlib:hover { background: #f7f9fc; }
  /* 未标记的配色对齐 .est.none(灰底灰框灰字), 靠"灰"表示待填, 而不是靠虚线 */
  .dlib.none { color: #b0b8c6 !important; border-color: #e3e8f0 !important; background: #f5f6f8; }

  /* ---- 临时任务(机动记录)面板 ---- */
  /* 一行一条记录, 不分卡片 —— 它读的是流水账, 卡片那种层级在这里反而碍眼 */
  .tmp-row {
    display: flex; align-items: center; gap: 10px; padding: 8px 2px;
    border-top: 1px solid #f0f3f8; font-size: 12px; cursor: pointer;
  }
  .tmp-row:first-child { border-top: none; }
  .tmp-row:hover { background: #fafbfd; }
  .tmp-row.fin { opacity: .72; }      /* 已完成的淡一档, 与象限里"收起的历史"同一语气 */
  /* 机动来源角标: 颜色来自 meta.INTERRUPT_META(只有 color/hint, 所以底色统一白) */
  .tmp-row .tri {
    flex: none; border: 1px solid; border-radius: 7px; padding: 1px 6px;
    font-size: 11px; background: #fff; white-space: nowrap;
  }
  .tmp-row .tri.none { color: #b0b8c6; border-color: #e3e8f0; background: #f5f6f8; }
  .tmp-row .trn { flex: 1; min-width: 0; color: #2b3444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tmp-row .trm { flex: none; color: #8893a7; white-space: nowrap; }

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

  /* ---- 任务编排弹窗 ---- */
  .arr-bar { display: flex; gap: 12px; align-items: center; margin: 2px 0 6px; }
  .arr-bar #arr-count { flex: 1; }          /* 合计撑满, 把"全选/全不选"挤到右边 */
  /* 候选可能几十条, 给个固定高度可滚动 —— 否则按钮被顶到屏幕外, 得先滚动才能点 */
  .arr-list {
    max-height: 44vh; overflow-y: auto; border: 1px solid #e3e8f0;
    border-radius: 9px; padding: 2px 10px;
  }
  .arr-row {
    display: flex; align-items: center; gap: 9px; padding: 7px 0;
    border-top: 1px solid #f0f3f8; font-size: 12px; cursor: pointer;
  }
  .arr-row:first-child { border-top: none; }
  .arr-row:hover { background: #fafbfd; }
  .arr-row input[type=checkbox] { flex: none; margin: 0; cursor: pointer; }
  .arr-row .arq { flex: none; font-weight: 700; }
  .arr-row .arn {
    flex: 1; min-width: 0; color: #2b3444;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .arr-row .arw { flex: none; color: #8893a7; white-space: nowrap; }
  /* 超预估标红(估时已失效); 未估算用灰, 与待安排区同一套口径 */
  .arr-row .arw.over { color: #d6453d; }
  .arr-row .arw.none { color: #b0b8c6; }
  /* 待安排池里的"临时"角标: 与时段块上那套同色(琥珀), 按 chip 的字号调大一点。
     未完成的临时任务会出现在待安排池里(突发常常一笔排不完), 不标就和普通任务分不清 */
  .wk-chip .wtmp {
    font-size: 10px; font-weight: 700; line-height: 15px; height: 15px; padding: 0 5px;
    border-radius: 5px; background: #fdf4e3; color: #a8801f; flex: none;
  }
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
  /* 三格并排(计划任务里的 开始 / 时长 / 结束) —— 三者互相联动, 排一行才看得出是一组 */
  .modal .three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
  /* (原先这里是一套 .stseg 并排按钮组, 用于"状态"和"机动来源"。)
     已整体换成下拉: 来源有 6 个选项, 平铺会换行且宽度参差, 看着杂乱;
     而弹窗里其余字段本来就是单行输入, 统一成下拉后反而更整齐。
     代价是"一眼看得全"没有了 —— 所以来源下拉里保留了一个**显式的「未标注」项**,
     不做静默默认(默认等于替人归类, 而这类统计的价值全在归因准确)。 */
  /* gap 与内边距都收紧了一档: 时段弹窗那一排有 4 个按钮(完成/删除/取消/保存),
     给宽了在弹窗宽度里就挤不下 */
  .modal-actions { display: flex; gap: 8px; margin-top: 18px; justify-content: flex-end; }
  /* white-space: nowrap 是**必须**的, 不是为了好看: 中文没有词边界, flex 项收缩时
     min-content 宽度只有 1 个字, 于是"删除记录"会被压成"删除 / 记录"两行, 整排按钮看着就散了。
     nowrap 把收缩下限抬到整段文字 —— 宁可整体挤一点, 也不能断在字中间 */
  .modal-actions button {
    padding: 7px 14px; border-radius: 8px; font-size: 13px; cursor: pointer;
    border: 1px solid #d8dee9; background: #fff; color: #3a4456; white-space: nowrap;
  }
  .modal-actions .btn-primary { background: #3b6fb0; color: #fff; border-color: #3b6fb0; }
  .modal-actions .btn-primary:hover { background: #2d5a94; }
  /* 弹窗左下角那组终态动作(✅ 完成 / 🗑️ 删除): 用 .act-left 推到最左, 与右边"取消/保存"分开 ——
     它们都会弹确认框, 挨着保存键容易被误点。
     推到最左的 auto 外边距挂在 .act-left 上, 而不是各个按钮上 —— 两个按钮各带一个 auto 会把空白劈成两半。
     颜色分开语义: 绿 = 这件事做完了, 红 = 把它删掉, 蓝(主按钮) = 只是存下改动 */
  .modal-actions .act-left { margin-right: auto; display: flex; gap: 8px; }
  /* 组内按钮不再各自带 auto(选择器优先级更高, 见上条注释) */
  .modal-actions .act-left .btn-done { margin-right: 0; }
  .modal-actions .btn-done {
    margin-right: auto; color: #2e9e5b; border-color: #a8d8bd; background: #f3fbf6;
  }
  .modal-actions .btn-done:hover { background: #2e9e5b; color: #fff; border-color: #2e9e5b; }
  .modal-actions .btn-del { color: #d6453d; border-color: #eeb4b0; background: #fdf4f3; }
  .modal-actions .btn-del:hover { background: #d6453d; color: #fff; border-color: #d6453d; }

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
    /* 窄屏必须再紧一档: 时段弹窗那排有 4 个按钮, 桌面上的宽度在这里是没有的 */
    .modal-actions { gap: 6px; }
    .modal-actions button { padding: 7px 10px; }
    .modal-actions .act-left { gap: 6px; }
    /* 窄屏三格并排每格只剩 ~100px, 时间输入根本放不下 —— 改成单列 */
    .modal .three { grid-template-columns: 1fr; }
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
        <button class="est" onclick="openArrange()"
                title="选一批本周要做的任务，按优先级顺序自动铺进工作时间（不用一个个拖）">🗓 任务编排</button>
        <button class="est" onclick="openPlanTask()"
                title="录入一条新任务，并直接排进本周一个时段（正式任务，进象限与待安排池）">＋ 新任务</button>
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

  <!-- 临时任务(机动记录)。放在仪表盘**上方**是有意的:
       它解释的是"本周计划外的时间去哪了", 是读懂仪表盘的前提。
       独立成块而不是并进仪表盘 —— 仪表盘衡量的全是计划内工作, 口径不能混(见 renderDash) -->
  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">临时任务<span class="cnt" id="tmp-cnt"></span></div>
      <div class="chips">
        <a class="qdone" id="tmp-more" onclick="toggleDoneTemp()"></a>
        <span class="mini">只记时间，不进象限统计</span>
        <button class="est" onclick="openTempTask()" title="记一笔突发事项，落到本周时间表上">＋ 记一笔</button>
      </div>
    </div>
    <div class="tmp-list" id="tmp-list"></div>
  </div>

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
    <!-- 写自评时把当周机动构成摆在眼前: "这周为什么没做成"最常见的答案就是突发,
         不摆出来就只会凭印象写"这周事多", 而说不清"被什么吃掉了几小时"(§2.9.4) -->
    <div class="mini" id="wrev-buf"></div>
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
      <span class="act-left">
        <button class="btn-done" id="est-done" onclick="saveHoursThenDone()"
                title="保存工时并标记为已完成">✅ 完成</button>
        <button class="btn-del" onclick="delTask()"
                title="删除这个任务及其全部流程节点，不可恢复">🗑️ 删除</button>
      </span>
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
  <!-- 400 而不是 360: 底部那排有 4 个按钮, 360 会把它们挤到换行/折字 -->
  <div class="modal" style="width:400px">
    <h3 id="sl-title">调整时段</h3>
    <div class="sub" id="sl-sub"></div>
    <label>开始时间</label>
    <input type="time" id="sl-from" step="600">
    <label>结束时间</label>
    <input type="time" id="sl-to" step="600">
    <label>这次实际做了多少（分钟）</label>
    <input type="number" id="sl-done" min="0" step="5" placeholder="留空 = 只改时间">
    <div class="mini" id="sl-remain"></div>
    <!-- 只对临时任务显示。它是机动来源**唯一能补标/改标**的地方:
         临时任务默认"已完成", 一旦完成就离开待安排池, 别处再也够不到它 ——
         少了这里, 记的时候漏选一次, 那条时间记录就永远停在"未标注" -->
    <div id="sl-int-wrap" style="display:none">
      <label>被什么打断的</label>
      <select id="sl-interrupt">__INTERRUPT_OPTIONS__</select>
    </div>
    <div class="modal-actions">
      <span class="act-left">
        <button class="btn-done" id="sl-done-btn" onclick="saveSlotThenDone()"
                title="保存这次改动并标记为已完成">✅ 完成</button>
        <!-- 文案在 openSlot 里按范围动态设置(见 delSlotFromModal):
             普通任务 = 删除时段; 临时任务且这是它最后一个时段 = 删除记录 -->
        <button class="btn-del" id="sl-del" onclick="delSlotFromModal()">🗑️ 删除时段</button>
      </span>
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
    <input type="text" id="tmp-name" placeholder="如：临时会议 / 同事来求助 / 报销审批">
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
    <label>预估工时（小时）</label>
    <input type="number" id="tmp-est" min="0" step="0.5" placeholder="留空 = 按 结束−开始 算">
    <label>状态</label>
    <!-- 只有三档(不是完整的 STATUS_ORDER): 记一笔临时任务时用不到"已暂停/已取消" -->
    <select id="tmp-status">
      <option value="已完成">已完成</option>
      <option value="进行中">进行中</option>
      <option value="未开始">未开始</option>
    </select>
    <label>被什么打断的（可不选）</label>
    <!-- "机动时间被什么吃掉了"唯一的数据源。**刻意不预选**: 给个默认等于替人归类,
         而这类统计的全部价值就在归因准确。漏选不拦, 之后点周表上那个块还能补标 -->
    <select id="tmp-interrupt">__INTERRUPT_OPTIONS__</select>
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

<!-- 任务编排: 勾一批任务, 按优先级顺序自动铺进本周的工作时间 -->
<div class="modal-bg hide" id="m-arrange">
  <div class="modal" style="width:580px">
    <h3>任务编排</h3>
    <div class="sub" id="arr-sub"></div>
    <div class="mini" id="arr-hint"></div>
    <div class="arr-bar">
      <!-- 已选合计放左边并撑满, 全选/全不选靠右 -->
      <span class="mini" id="arr-count"></span>
      <a class="wk-edit" onclick="arrangeAll(true)">全选</a>
      <a class="wk-edit" onclick="arrangeAll(false)">全不选</a>
    </div>
    <div class="arr-list" id="arr-list"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-arrange')">取消</button>
      <button class="btn-primary" onclick="runArrange()">一键编排</button>
    </div>
  </div>
</div>

<!-- 录入新任务: 建一条**正式任务**, 并直接排进本周的一个时段。
     与「临时任务」的分工 —— 那个记的是**已经发生的突发**(默认已完成、不进待办池、
     不参与象限统计, 消耗算机动); 这个录的是**计划要做的事**(进象限与待安排池,
     从 0% 开始, 参与统计)。两类事混在一个入口会让"这到底是记录还是计划"说不清 -->
<div class="modal-bg hide" id="m-plan">
  <div class="modal" style="width:440px">
    <h3>录入新任务</h3>
    <div class="sub" id="pl-sub"></div>
    <label>任务名称</label>
    <input type="text" id="pl-name" placeholder="如：完成XX方案初稿">
    <label>四象限（可不选）</label>
    <select id="pl-quad">__QUAD_OPTIONS__</select>
    <label>哪天</label>
    <select id="pl-day" onchange="planPickDay()"></select>
    <!-- 三格联动: 改开始或时长顺推结束, 改结束反推时长 -->
    <div class="three">
      <div>
        <label>开始</label>
        <input type="time" id="pl-from" step="600" oninput="planSync('from')">
      </div>
      <div>
        <label>时长（小时）</label>
        <input type="number" id="pl-len" min="0" step="0.5" oninput="planSync('len')">
      </div>
      <div>
        <label>结束</label>
        <input type="time" id="pl-to" step="600" oninput="planSync('to')">
      </div>
    </div>
    <label>预估工时（小时）</label>
    <input type="number" id="pl-est" min="0" step="0.5" placeholder="留空 = 按本次时长">
    <div class="mini" id="pl-remain"></div>
    <div class="modal-actions">
      <button onclick="closeModal('m-plan')">取消</button>
      <button class="btn-primary" onclick="savePlanTask()">录入并排进时间表</button>
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
const INTERRUPT = __INTERRUPT_META__;
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

/* ---------------- 临时任务(机动记录) ---------------- */
/* 仪表盘上方的一块独立面板。为什么独立、为什么在上方, 见 HTML 处的注释:
   它解释的是"计划外的时间去哪了" —— 是读懂仪表盘的前提, 但口径与仪表盘完全不同。*/

/* 已完成的记录是否展开。与象限里的 showDone 同构, 默认收起的原因也一样:
   面板首先是"当前要看的东西", 历史一直占着位置会把新记录挤下去;
   但也不能彻底藏掉 —— 那样就没地方回看"上周机动被什么吃掉了"。 */
let showDoneTemp = false;

function toggleDoneTemp() {
  showDoneTemp = !showDoneTemp;
  renderTempPanel();
}

/* 一条记录: [来源角标] 名称 …… 日期 · 时长 · 状态 */
function tempRowHtml(t) {
  const iv = INTERRUPT[t.interrupt];
  // 已完成时 actual_h 就是那段时长; 未完成的可能还没记过, 退回估时
  const h = num(t.actual_h) || num(t.estimate_h) || 0;
  const style = iv ? ' style="color:' + iv.color + ';border-color:' + iv.color + '"' : '';
  return '<div class="tmp-row' + (t.finished ? ' fin' : '') + '"' +
    ' onclick="openHours(\'' + esc(t.no) + '\')" title="点击查看 / 修改工时与来源">' +
    '<span class="tri' + (iv ? '' : ' none') + '"' + style + '>' +
      esc(iv ? t.interrupt : '未标注') + '</span>' +
    '<span class="trn">' + esc(t.name) + '</span>' +
    '<span class="trm">' + esc(t.date || '') + (h ? ' · ' + fmtDur(h) : '') +
      (t.status ? ' · ' + esc(t.status) : '') + '</span>' +
    '</div>';
}

function renderTempPanel() {
  const box = document.getElementById('tmp-list');
  if (!box) return;
  const all = state.tasks.filter(t => t.temp);
  // 新到旧; 未完成的排在已完成之前(与象限矩阵同一取向 —— 先看还要处理的)
  const byNew = (a, b) =>
    (parseYmd(b.date || '').getTime() || 0) - (parseYmd(a.date || '').getTime() || 0);
  const open = all.filter(t => !t.finished).sort(byNew);
  const fin = all.filter(t => t.finished).sort(byNew);
  // 合计用 actual_h 优先 —— 它才是"这段时间确实被占掉了"的数字
  const totalH = all.reduce((a, t) => a + (num(t.actual_h) || num(t.estimate_h) || 0), 0);

  document.getElementById('tmp-cnt').textContent =
    all.length ? '（' + all.length + ' 条 · 合计 ' + fmtDur(totalH) + '）' : '';

  const more = document.getElementById('tmp-more');
  if (more) {
    more.textContent = fin.length
      ? (showDoneTemp ? '收起已完成 ▴' : '已完成 ' + fin.length + ' ▾') : '';
    more.title = showDoneTemp ? '收起已完成的记录' : '展开已完成的记录';
    more.style.display = fin.length ? '' : 'none';
  }

  if (!all.length) {
    box.innerHTML = '<div class="quad-empty">还没有临时记录 —— 点右边「＋ 记一笔」，' +
      '或周表工具栏的「＋ 临时任务」</div>';
    return;
  }
  const shown = open.concat(showDoneTemp ? fin : []);
  box.innerHTML = shown.length
    ? shown.map(tempRowHtml).join('')
    : '<div class="quad-empty">' + fin.length + ' 条已完成的记录已收起</div>';
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
  // 带上卡点数(与流程跟踪页一致): 一眼看出这条复盘过没有、记了几条
  const rv = t.finished
    ? `<span class="review-btn" title="复盘: 估时偏差 / 推进空档 / 卡点" onclick="openReview('${esc(t.no)}')">后评估${(t.blockers || []).length ? ' ' + t.blockers.length : ''}</span>`
    : '';
  // 完成入口放在本页, 是为了让"完成任务 → 仪表盘变化"形成闭环 ——
  // 否则要跳到任务清单页去点, 再等这边轮询同步
  const doneBtn = t.finished ? '' :
    `<button class="done-btn" title="标记完成（立即计入仪表盘）" onclick="event.stopPropagation();doneTask('${esc(t.no)}')">✅</button>`;
  // 预期成果角标: 点它就地改 —— 它决定"产出成果"统计, 不该藏在编辑弹窗里
  const dlm = t.deliverable ? DL[t.deliverable] : null;
  const dlBadge = dlm
    ? `<span class="dlib" style="color:${dlm.color};border-color:${dlm.color}" title="预期成果：${esc(t.deliverable)}（点击修改）" onclick="event.stopPropagation();openDeliverable('${esc(t.no)}')">${esc(t.deliverable)}</span>`
    : `<span class="dlib none" title="未标记预期成果（点击设置）" onclick="event.stopPropagation();openDeliverable('${esc(t.no)}')">成果</span>`;
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

/* 已完成任务的展开状态, 按象限各记一份 —— 展开 A 不该把 B/C/D 的历史也一起摊开 */
const showDone = {};

function toggleDone(q) {
  showDone[q] = !showDone[q];
  renderMatrix();
}

function renderMatrix() {
  const html = QUAD_ORDER.map(q => {
    const m = QUAD[q];
    // 已完成的任务**默认收起**(2026-09-21 调整)。原先和未完成的一起铺开, 理由是
    // "后评估要用它的历史" —— 但象限卡片首先是"当前要关注的事", 历史任务一直占着位置,
    // 会把真正要做的挤到下面去。
    // 也不能彻底藏掉: 后评估入口就挂在那些卡片上, 而它的数据正是靠完成后填的,
    // 看不见就等于没人会去填。所以做成可点的开关, 默认收起。
    const list = state.tasks.filter(t => t.quadrant === q);
    const doneN = list.filter(t => t.finished).length;
    const openN = list.length - doneN;
    const showing = !!showDone[q];
    const shown = showing ? list : list.filter(t => !t.finished);
    const h = list.reduce((s, t) => s + (num(t.estimate_h) || 0), 0);
    const body = shown.length
      ? shown.map(cardHtml).join('')
      : `<div class="quad-empty">${q === 'D' ? 'D 类暂时没有任务' : '暂无任务'}${doneN && !showing ? '（' + doneN + ' 个已完成已收起）' : ''}</div>`;
    // 已完成个数仍要标出来: 诊断区的占比只算未完成, 不标两个数字就对不上账
    const dtoggle = doneN
      ? ' · <a class="qdone" onclick="toggleDone(\'' + q + '\')" title="' +
        (showing ? '收起已完成的任务' : '展开已完成的任务（含后评估入口）') + '">' +
        (showing ? '收起已完成 ▴' : '已完成 ' + doneN + ' ▾') + '</a>'
      : '';
    return `
      <div class="quad" data-q="${q}">
        <div class="quad-head">
          <div class="quad-name">
            <span class="qdot" style="background:${m.color}"></span>
            ${q} · ${m.label}
            <span class="act" style="color:${m.color};background:${m.bg}">${m.action}</span>
          </div>
          <div class="quad-meta">${openN} 个${dtoggle}${h > 0 ? ' · 估时 ' + fmt(h) + 'h' : ''}</div>
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
  renderTempPanel();     // 临时任务面板(DOM 上也排在仪表盘之前, 顺序保持一致)
  renderDash();
  renderMatrix();
  renderUnclassified();
  // 周表也在这里重绘; 它末尾会连带重画 wk-foot / 待安排 / 周自评, 所以那三处不在这里重复调。
  //
  // **为什么必须重绘周表**: state.tasks 是异步拉来的(loadData), 而时段块要靠 byNo() 回任务池
  // 取名字 —— 取不到就整块跳过不渲染。init() 里 loadData 与 loadWeekPlan 是**并发**跑的,
  // 谁先返回决定了 renderWeek 拿到的是"生成页面时的快照"还是"最新任务":
  //   快照 → 刚建的临时任务整块看不见; 最新 → 正常。
  // 于是表现为"刷新几次才显示", 极易被误判成网络问题。而底部统计(走 renderWeekFoot)
  // 反而一直是对的 —— 那个"统计对、块没有"的矛盾就是它的指纹。
  renderWeek();
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
  // 措辞必须与实际行为一致: 完成后卡片是**从象限列表里收起**(点「已完成 N ▾」还能展开),
  // 不是消失。之前这里写的"从象限里移出"会让人以为找不到它了 —— 而
  // 后评估入口恰恰就在收起的那批卡片上, 说错这句等于把入口一起藏了
  confirmBox('把 <b>No.' + esc(no) + ' ' + esc(t.name) + '</b> 标记为已完成？<br><br>' +
    '完成后会从象限列表里<b>收起</b>（象限右上角点「已完成 N ▾」可展开，<b>后评估</b>入口在那里），' +
    '并立即计入仪表盘（平均耗时、本周完成、估时偏差）。',
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
  // 临时任务是**时间记录**、不是待办: 它不进估时校准, 也就没必要拦一道问"实际投入多少"
  // (那笔投入就是周表里记的那段时长)。直接进完成确认
  if (!t.temp && num(t.estimate_h) && !num(t.actual_h)) {
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
    // 完成会让卡片从象限列表收起、并计入仪表盘, 不是个该静默发生的动作
    confirmComplete(no, t, null);
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

/* 工时弹窗里的 🗑️ —— 删除**整个任务**(不是"把时段移出时间表")。
   它比完成重得多: 任务、全部流程节点与已记录的工时一起没了, 而且**不可恢复**,
   所以确认框必须写清影响面, 不能只说一句"确认删除?"。

   注意这里**不先保存工时**(与 ✅ 不同): ✅ 要先存是因为任务还在, 那笔改动有意义;
   删除之后任务连同工时一起消失, 存了也立刻没, 所以只弹确认、不做保存。*/
/* 真正执行"删除任务"并跟进本地状态。两处入口共用:
   - 工时弹窗的 🗑️(先弹确认框)
   - 时段弹窗里"删掉临时记录的最后一条"(按钮文案已写明范围, 故不再确认)
   抽出来是为了让两处善后完全一致 —— 少做一步(比如忘了过滤本地 slots)
   就会立刻表现成"块没了、已排工时却没变"(孤儿块仍计入"未归类") */
function postDeleteTask(no) {
  return post('/api/delete_task', { no: String(no) }).then(d => {
    if (!d.ok) { toast(d.error || '删除失败', 'err'); return d; }
    // 服务端把该任务在**所有周**的时段都清掉了(见 purge_task), 本地只持有当前周
    state.plan.slots = state.plan.slots.filter(s => String(s.no) !== String(no));
    loadData();      // 重新拉取: 它要从象限、待安排池、仪表盘一起消失
    return d;
  }).catch(() => {
    toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err');
    return null;
  });
}

function delTask() {
  const no = editing;
  const t = byNo(no);
  if (!t) return;
  // 只算当前查看那一周 —— 只能提示看得见的部分。服务端清的是**所有周**(见 purge_task),
  // 精确总数在删除后的 toast 里给, 免得这里报一个比实际小的数字却说得像全部
  const n = state.plan.slots.filter(s => String(s.no) === String(no)).length;
  closeModal('m-est');
  confirmBox('删除任务 <b>No.' + esc(no) + ' ' + esc(t.name) + '</b>？<br><br>' +
    '任务、它的全部流程节点、以及已记录的工时都会一并删除，<b>不可恢复</b>。' +
    (n ? '<br><br>它本周还有 <b>' + n + '</b> 个时段，会一并从时间表上移除。' : ''),
    function () {
      postDeleteTask(no).then(d => {
        if (d && d.ok) {
          toast('已删除 No.' + no + ' ' + t.name +
            (d.purged ? '，并移除 ' + d.purged + ' 个排期时段' : ''), 'ok');
        }
      });
    }, '删除任务');
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

/* 本周机动消耗**按来源拆分** —— 返回 [{label, h, color}], 按小时降序。

   键为空串表示没标注来源, 单独成一项, **不并进"其他"**: 两者含义不同
   (一个是"没归类", 一个是"归到了其他类")。混起来会让"其他"虚高, 而"其他占比高"
   恰恰是"该扩充枚举"或"该升级成正式任务"的信号, 不能被没标的人稀释掉。

   临时任务没有象限, 所以它不参与下面的 byQ 统计(混进去会让"未归类"虚高)。 */
function tempBreakdown() {
  const acc = {};
  state.plan.slots.forEach(s => {
    const t = byNo(s.no);
    if (!t || !t.temp) return;
    const k = INTERRUPT[t.interrupt] ? t.interrupt : '';
    acc[k] = (acc[k] || 0) + (s.to - s.from);
  });
  return Object.keys(acc)
    .map(k => ({ label: k || '未标注', h: acc[k],
                 color: k ? INTERRUPT[k].color : '#8893a7' }))
    .sort((a, b) => b.h - a.h);
}

/* 本周机动消耗总量。**从拆分结果求和** —— 这样"构成各项之和 = 总数"是结构上成立的,
   而不是两处各算一遍、哪天规则改了一处就对不上账 */
function tempHours() {
  return tempBreakdown().reduce((a, r) => a + r.h, 0);
}

/* 一行式构成文本; 没有任何临时任务时返回空串(调用方据此不显示) */
function tempBreakHtml() {
  return tempBreakdown()
    .map(r => '<b style="color:' + r.color + '">' + esc(r.label) + '</b> ' + fmtDur(r.h))
    .join(' · ');
}

function renderWeekFoot() {
  const slots = state.plan.slots;
  const total = slots.reduce((a, s) => a + (s.to - s.from), 0);
  const budget = weekHours();
  const byQ = {};
  const tempH = tempHours();        // 临时任务单独算, 不参与下面的象限归类
  slots.forEach(s => {
    const t = byNo(s.no);
    if (t && t.temp) return;
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
  // 机动构成 —— "额度用满了"只说明出了问题, "被什么吃掉了"才指向动作(§8)。
  // 只在真有临时任务时占一行: 没记过就别占版面
  if (tempH > 0.001) {
    const brk = tempBreakHtml();
    if (brk) html += '<br><span style="color:#8890a0">构成：' + brk + '</span>';
  }
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
  //
  // pending() 里排除了临时任务(它们不进待归类、不计入象限占比 —— 那是"待办"的口径)。
  // 但**未完成的临时任务要能继续排时间**: 突发的活常常一笔排不完(估 1h、实际要 3h),
  // 排不下就等于"只能停在半路", 而它恰恰是最需要再占时间的。
  // 所以在这里单独并进来, 不动 pending() 本身 —— 它的其他调用方(待归类 / 诊断 / 副标题)
  // 仍然不该看见临时任务。
  const all = pending().concat(state.tasks.filter(t => t.temp && !t.finished));
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
      // 临时任务没有象限角标, 不标一下会和普通任务混在一起分不清
      (t.temp ? '<span class="wtmp">临时</span>' : '') +
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

/* 铺开的内核: 自 hour 起, 在 [lo, hi) 内为 need 小时找位置, 按 0.5h 刻度推进。
   先把它切成一段段**连续的可用区间(run)**, 再逐段取用 —— 所以一次可能产出多段
   (如 6h 从 10:30 开始 → 10:30–11:30 + 13:30–18:30), 而不是只排到第一个障碍就停。
   切 run 而不是逐格拼接, 是为了能先知道每段有多长 —— 判断"值不值得用"要看长度(见 minRun)。
   taken(h) 由调用方提供(它知道自己在哪一天)。
   返回 {segs:[[from,to],...], left: 还差多少小时没排下}。

   minRun: **不足这么长的空档不用**。默认 0 = 不设限(拖拽要的就是"我点哪就排哪")。
   编排会传 1h, 因为程序排出来的碎片没人会照做 —— 典型是午休前剩下的半小时:
   接不上手就该午休了, 排进去只会变成一个永远被跳过的块。
   注意它和 need 取小值: 任务本来只要 0.5h 时, 半小时空档照样能用。 */
function fillSpan(hour, need, lo, hi, taken, minRun) {
  const limit = minRun || 0;
  const usable = h => h >= lo && h < hi && !inBreak(h) && !taken(h);
  const segs = [];
  let left = need;
  for (let x = Math.max(lo, hour); x < hi && left > 0.001; ) {
    if (!usable(x)) { x += 0.5; continue; }
    let end = x;                                 // 量出这一段连续可用区有多长
    while (end < hi && usable(end)) end += 0.5;
    const len = end - x;
    if (len >= Math.min(limit, left) - 1e-9) {   // 太碎的段跳过(除非这次要排的本来就比它短)
      const take = Math.min(len, Math.ceil(left / 0.5 - 1e-9) * 0.5);
      segs.push([x, x + take]);
      left -= take;
    }
    x = end;
  }
  return { segs: segs, left: left };
}

/* 拖拽要铺多少: 补上"本周还没排够"的缺口 —— 已经排过的部分不重复排。
   超预估/已排够时按 1h 铺开, 具体再手动调。
   **不再拦截"本周已排满"** —— 估时只是估计, 人比估时更清楚还要多久;
   而"排满就不让拖"会让"同一件事一周分两次做"(周中 2h + 周末 2h)根本做不到。 */
function dragNeed(t) {
  const r = remainOf(t);
  const left = r > 0.001 ? Math.max(0, r - arrangedHours(t.no)) : 0;
  return left > 0.001 ? left : 1;
}

/* 一键编排给每个任务排多少: **整个剩余工作量**。
   与 dragNeed 的唯一差别就是"不扣本周已排的" —— 编排会把本周非临时时段整体替换掉,
   已排的本来就要作废; 再扣一次会变成"每编一次就少排一点", 越编越少。 */
function arrangeNeed(t) {
  const r = remainOf(t);
  return r > 0.001 ? r : 1;
}

/* 时长向上取整到 0.5h。刻度是半小时, 1.3h 的需求实际会铺成 1.5h ——
   汇总里必须报取整后的值, 否则"已选共 12.3h"和真正排进去的 12.5h 对不上,
   看起来像程序算错了 */
function roundUpHalf(h) { return Math.ceil(h * 2 - 1e-9) / 2; }

/* 拖入时按任务的预估工时铺开 —— 铺开规则见 fillSpan(与"一键编排"共用同一个内核) */
function addSlot(no, day, hour) {
  const t = byNo(no);
  if (!t) return;
  const need = dragNeed(t);
  const busy = state.plan.slots.filter(s => s.day === day).map(s => [s.from, s.to]);
  const r = fillSpan(hour, need, WK.start, WK.end,
                     h => busy.some(x => h >= x[0] && h < x[1]));
  if (!r.segs.length) { toast('这一天已经排满', 'err'); return; }

  const added = Math.round((need - r.left) * 100) / 100;
  const next = state.plan.slots.concat(r.segs.map(s => ({
    no: String(no), day: day, from: s[0], to: s[1]
  })));
  const desc = r.segs.map(s => hm(s[0]) + '–' + hm(s[1])).join('、');
  if (r.left > 0.001) {
    savePlan(next, '已排 ' + desc + '（共 ' + fmt(added) + 'h），当天还差 ' + fmt(r.left) + 'h');
  } else {
    savePlan(next, '已排 ' + WK.names[day - 1] + ' ' + desc + '（' + fmt(added) + 'h）');
  }
}

/* ---------------- 任务编排 ---------------- */
/* 目的: 不用一个个拖。勾一批本周要做的任务, 按顺序把它们铺进本周的工作时间。

   三条规则:

   1) **只铺工作时间窗**(09:00–18:00 去掉午休 = 7h/天)。这个 7h 不是随手定的:
      7 × 5 天 = 35h, 正好等于默认的"每周净可安排"。所以"排不排得下"不必再设一道
      预算闸门 —— 窗口本身就是容量。它同时也把任务挡在 18:00 之前:
      要不要排到晚上该由人决定, 不该由程序替他决定。

   2) **只替换非临时时段**。临时任务是**已经发生的时间记录**, 不是计划 ——
      被"重新编排"抹掉就成了篡改历史。它们占的位置照样算被占, 程序会绕开。

   3) 顺序 = 优先级 → 象限 → 最久未推进 → 编号; 每个任务排多久 = 剩余工作量
      (超预估/未估算按 1h 兜底) —— 与拖拽同一口径(见 arrangeNeed / dragNeed 的区别)。 */

/* 排序用的秩: 取值不在列表里时给个默认值(优先级按"中"、象限排最后),
   免得脏数据被 indexOf 的 -1 顶到队首 */
function rankIn(list, v, dflt) { const i = list.indexOf(v); return i < 0 ? dflt : i; }

/* 最后一次推进的时间(毫秒)。从**最后一个节点**往前找第一个能解析的日期,
   全都解析不了就退回创建日期 —— 数据里确实有"前日"这类相对值, 必须容忍解析失败。
   都取不到返回 0(排最前): 宁可让它先占一段时间, 也不要因为"日期看不懂"就永远轮不到。 */
function lastTouchMs(t) {
  const ns = t.nodes || [];
  for (let i = ns.length - 1; i >= 0; i--) {
    const ms = parseYmd(ns[i].date).getTime();
    if (!isNaN(ms)) return ms;
  }
  const d = parseYmd(t.date).getTime();
  return isNaN(d) ? 0 : d;
}

/* 编排顺序。优先级是主键, 象限次之(A 类救火先), 再按"最久没碰"。
   为什么还要 LRU: 同一批 B 类任务的重要性本来就接近, 真正的风险是**被无限期搁置**;
   只按前两项排的话永远是同样几条被排上, 其余的连队都排不上(§9.5(2) 同一条理由)。 */
function arrangeOrder(a, b) {
  let d = rankIn(PRIO_ORDER, a.priority, 1) - rankIn(PRIO_ORDER, b.priority, 1);
  if (d) return d;
  d = rankIn(QUAD_ORDER, a.quadrant, 9) - rankIn(QUAD_ORDER, b.quadrant, 9);
  if (d) return d;
  d = lastTouchMs(a) - lastTouchMs(b);
  if (d) return d;
  return (Number(a.no) || 0) - (Number(b.no) || 0);
}

/* 默认勾选: **估过时、且还有剩余工作量**的。
   未估算的不默认勾 —— 拿 1h 的兜底值替人做决定, 排出来只会是错的;
   投入已满 / 超预估的也不默认勾(按估时它们不需要时间了), 但人可以手动勾上。 */
function arrangeChecked(t) {
  return !!num(t.estimate_h) && remainOf(t) > 0.001;
}

/* 一行的工时判据与配色, 与待安排区同一套说法(那边叫"投入已满", 这边就该也是) */
function arrangeTag(t) {
  const r = remainOf(t);
  if (!num(t.estimate_h)) return { w: '未估算', cls: ' none' };
  if (r < -0.001) return { w: '超 ' + fmt(-r) + 'h', cls: ' over' };
  if (r <= 0.001) return { w: '投入已满', cls: '' };
  return { w: '需 ' + fmt(r) + 'h', cls: '' };
}

function arrangeRowHtml(t) {
  const q = QUAD[t.quadrant];
  const p = PRIO[t.priority] || PRIO.medium;
  const tag = arrangeTag(t);
  return '<label class="arr-row">' +
    '<input type="checkbox" data-no="' + esc(t.no) + '"' +
      (arrangeChecked(t) ? ' checked' : '') + ' onchange="arrangeSummary()">' +
    // 优先级与象限各一个小角标 —— 列表就是按这两项排的, 标出来才看得出顺序对不对
    '<span class="arq" style="color:' + p.color + '" title="' + esc(p.label) + '">' +
      esc(p.short) + '</span>' +
    '<span class="arq" style="color:' + (q ? q.color : '#8893a7') + '" title="' +
      (q ? esc(q.label + ' · ' + q.action) : '未归类') + '">' + esc(t.quadrant || '—') + '</span>' +
    '<span class="arn" title="' + esc(t.name) + '">' + esc(t.name) + '</span>' +
    '<span class="arw' + tag.cls + '">' + tag.w + '</span>' +
    '</label>';
}

function openArrange() {
  const tasks = pending().slice().sort(arrangeOrder);
  document.getElementById('arr-sub').textContent =
    state.plan.week_start + ' · 净可安排 ' + fmtDur(weekHours()) +
    ' · 可编排时段 ' + hm(WK.workStart) + '–' + hm(WK.workEnd) + '（午休跳过）';

  // 会被替换掉的**非临时**时段数(连孤儿时段也算, 它们本来就该清掉)
  const old = state.plan.slots.filter(s => {
    const t = byNo(s.no);
    return !t || !t.temp;
  }).length;
  let hint = '按 <b>优先级 → 象限 → 最久未推进</b> 的顺序铺开，每个任务排它的' +
    '<b>剩余工作量</b>（超预估 / 未估算按 1h 兜底）。<br>';
  if (old) hint += '<b style="color:#d6453d">⚠ 本周已有的 ' + old + '</b> 个计划时段会被替换掉；';
  hint += '临时任务的记录<b>不受影响</b>，也不会被挤掉。';
  document.getElementById('arr-hint').innerHTML = hint;

  const box = document.getElementById('arr-list');
  box.innerHTML = tasks.length
    ? tasks.map(arrangeRowHtml).join('')
    : '<div class="mini" style="padding:10px 0">没有未完成的任务</div>';
  arrangeSummary();
  openModal('m-arrange');
}

function arrangeSelected() {
  return Array.from(document.querySelectorAll('#arr-list input[type=checkbox]:checked'))
    .map(c => byNo(c.dataset.no)).filter(Boolean);
}

/* 已选合计。**按 roundUpHalf 后的实际铺开量算**, 而不是原始剩余 ——
   否则"已选共 12.3h"会和真正排进去的 12.5h 对不上, 看起来像程序算错了 */
function arrangeSummary() {
  const sel = arrangeSelected();
  const h = sel.reduce((a, t) => a + roundUpHalf(arrangeNeed(t)), 0);
  const cap = weekHours();
  document.getElementById('arr-count').innerHTML =
    '已选 <b>' + sel.length + '</b> 个 · 需要 <b>' + fmtDur(h) + '</b>' +
    (h > cap + 0.001
      ? ' <b style="color:#d6453d">超出净可安排 ' + fmtDur(cap) + '</b>'
      : ' <span style="color:#888f9c">/ 净可安排 ' + fmtDur(cap) + '</span>');
  return sel;
}

function arrangeAll(on) {
  document.querySelectorAll('#arr-list input[type=checkbox]').forEach(c => { c.checked = on; });
  arrangeSummary();
}

/* 把任务逐个铺进本周。返回 {slots, missed, placedH} */
function packTasks(tasks) {
  // 占用表里**只放临时时段**: 非临时时段这次会被整体替换, 不该挡自己的路
  const taken = state.plan.slots
    .filter(s => { const t = byNo(s.no); return !!t && t.temp; })
    .map(s => ({ day: s.day, from: s.from, to: s.to }));
  const days = Math.max(1, Math.round(state.daysW) || 1);
  const out = [], missed = [];
  let placedH = 0;
  tasks.forEach(t => {
    let need = roundUpHalf(arrangeNeed(t));
    // 一天放不下就顺延到第二天(所以 10h 的任务会占满周一再接着周二)
    for (let day = 1; day <= days && need > 0.001; day++) {
      // 传 minRun = 1h: 不足 1 小时的零碎空档不占用(理由见 fillSpan)。
      // 拖拽那条路径不传, 保持"我点哪就排哪" —— 只有自动铺开才该有这种洁癖
      const r = fillSpan(WK.workStart, need, WK.workStart, WK.workEnd,
                         h => taken.some(x => x.day === day && h >= x.from && h < x.to), 1.0);
      r.segs.forEach(s => {
        out.push({ no: String(t.no), day: day, from: s[0], to: s[1] });
        taken.push({ day: day, from: s[0], to: s[1] });
        placedH += (s[1] - s[0]);
      });
      need = r.left;
    }
    if (need > 0.001) missed.push(t.name);      // 一周都放不下, 如实报出来而不是硬塞
  });
  return { slots: out, missed: missed, placedH: Math.round(placedH * 100) / 100 };
}

function runArrange() {
  const sel = arrangeSelected();
  if (!sel.length) { toast('先勾选要编排的任务', 'err'); return; }
  const old = state.plan.slots.filter(s => { const t = byNo(s.no); return !t || !t.temp; }).length;
  closeModal('m-arrange');
  // 有东西要被替换掉时问一句 —— 手工调过的周表是实打实的工作量, 不能一点就没了
  confirmBox('把选中的 <b>' + sel.length + '</b> 个任务铺进 ' + state.plan.week_start + ' 那一周？' +
    (old ? '<br><br>本周已有的 <b>' + old + '</b> 个计划时段会被替换掉' +
           '（临时任务的记录不受影响）。' : ''),
    function () { doArrange(sel); }, '开始编排');
}

function doArrange(sel) {
  // 临时时段原样保留 —— 它们是已发生的时间记录, 不是计划; 编排只在其之外铺开
  const keep = state.plan.slots.filter(s => { const t = byNo(s.no); return !!t && t.temp; });
  const r = packTasks(sel);
  const next = keep.concat(r.slots);
  // 存盘前按 天 → 起 排一下: 顺序不影响渲染, 但文件里读起来顺
  next.sort((a, b) => (a.day - b.day) || (a.from - b.from));
  // 不传 undo: 被替换掉的时段上若记过 done_h, 那笔**投入不退回** ——
  // 时间是真花了的, 换的只是排期。新时段不带 done_h 也正确: 它们代表未来要投入的时间
  let msg = '已编排 ' + sel.length + ' 个任务，共 ' + fmtDur(r.placedH);
  if (r.missed.length) {
    msg += '；' + r.missed.length + ' 个没排下（' + r.missed.slice(0, 3).join('、') +
      (r.missed.length > 3 ? ' 等' : '') + '）';
  }
  savePlan(next, msg);
}

/* ---------------- 录入新任务(建任务 + 排一个时段) ---------------- */
/* 与「临时任务」分成两个入口, 因为记的是**两类不同的事**:
   临时任务录"已经发生的突发" —— 默认已完成、不进待办池、不参与象限统计, 消耗算机动;
   这里录"计划要做的事" —— 进象限与待安排池, 从 0% 开始, 参与统计。
   合成一个入口会让"这到底是在记录还是在计划"说不清, 也会把突发工时算进象限结构。

   时段为什么在这个弹窗里填: 拖拽与任务编排都会**自动**决定位置与时长, 只有这里能
   直接指定"某天 × 某时段"; 而新任务的 no 是**服务端**分配的, 前端拿不到它就没法在
   下一步写时段 —— 所以"建任务 + 排时段"必须是同一个请求(见 serve_task_flow.py)。 */

/* 某天在 [工作开始, 工作结束) 里第一个空闲的半小时刻度。
   只用来给个合理默认值 —— 真重叠了 savePlanTask 里还有硬校验兜着, 所以不必追求完美 */
function planFirstFree(day) {
  const busy = state.plan.slots.filter(s => s.day === day).map(s => [s.from, s.to]);
  for (let h = WK.workStart; h < WK.workEnd; h += 0.5) {
    if (inBreak(h)) continue;
    if (!busy.some(r => h >= r[0] && h < r[1])) return h;
  }
  return WK.workStart;      // 那天排满了就退回起点, 让重叠校验去提示
}

/* 把 [f, t] 按午休切成若干段, 返回 [[from,to], ...]。
   空数组 = 整段都落在午休里 —— 那才是真的没有可排的时间。

   为什么该由程序切、而不是让人拆两段: "午休不排工作"这条规则程序本来就懂 ——
   拖拽会被拒绝、自动铺开会跳过(fillSpan)。手工填起止的地方原先直接拒绝、要求人
   自己算, 等于把程序已经会的算术退给人做; 而人填的"9 点到 5 点"本来就是一句自然的
   话, 不该被逼成两句话。

   **保存与预览共用这一个函数** —— 预览说"排 6h"、实际排进去 6h, 必须来自同一次计算,
   否则又是"两处各算一遍、哪天规则改了只改一处"的老问题。 */
function carveBreak(f, t) {
  const segs = [];
  if (f < WK.brkStart - 1e-9) segs.push([f, Math.min(t, WK.brkStart)]);
  if (t > WK.brkEnd + 1e-9) segs.push([Math.max(f, WK.brkEnd), t]);
  return segs.filter(s => s[1] - s[0] > 1e-9);
}

/* 把切出来的段写成 "09:00–11:30 + 13:30–17:00" */
function segsText(segs) {
  return segs.map(s => hm(s[0]) + '–' + hm(s[1])).join(' + ');
}

/* 默认时长 = 1 小时。新任务没有"剩余工作量"可依据(那是已有任务才有的概念),
   给个常见起点即可 —— 三个框是联动的, 时间填完随时能改 */
function planDefaultLen() { return 1; }

/* 默认选今天(在本周内时), 否则周一 */
function planDefaultDay() {
  const ws = parseYmd(state.plan.week_start || TODAY);
  const now = new Date();
  const today0 = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const idx = Math.floor((today0 - ws.getTime()) / 86400000);
  return (idx >= 0 && idx <= 6) ? String(idx + 1) : '1';
}

function openPlanTask() {
  document.getElementById('pl-name').value = '';
  // 象限与预估工时都**不预填**: 象限是判断(不该替人定), 估时留空另有明确语义(按本次时长)
  setSelectValue('pl-quad', '');
  document.getElementById('pl-est').value = '';
  document.getElementById('pl-len').value = planDefaultLen();

  // 周一到周日带上日期 —— 只写"周三"的话, 翻到历史周时会和真实日期对不上
  const ws = parseYmd(state.plan.week_start || TODAY);
  document.getElementById('pl-day').innerHTML = WK.names.map((n, i) =>
    '<option value="' + (i + 1) + '">' + n + ' ' +
      md(new Date(ws.getTime() + i * 86400000)) + '</option>').join('');
  document.getElementById('pl-day').value = planDefaultDay();

  document.getElementById('pl-sub').textContent =
    state.plan.week_start + ' · 本周已排 ' +
    fmtDur(state.plan.slots.reduce((a, x) => a + (x.to - x.from), 0)) +
    ' / 净可安排 ' + fmtDur(weekHours());
  planPickDay();
  openModal('m-plan');
}

/* 换天: 把开始挪到那天第一个空闲位置, 再顺推结束 */
function planPickDay() {
  const day = parseInt(document.getElementById('pl-day').value, 10) || 1;
  document.getElementById('pl-from').value = hToTime(planFirstFree(day));
  planSync('len');
}

/* 开始 / 时长 / 结束 三者联动: 改开始或时长顺推结束, 改结束反推时长。
   排期时人想的是"两点开始做一小时半"或"一直做到五点半" —— 两种说法都得能直接用 */
function planSync(src) {
  const f = timeToH(document.getElementById('pl-from').value);
  const lenEl = document.getElementById('pl-len');
  if (src === 'to') {                        // 改结束 → 反推时长
    const len = timeToH(document.getElementById('pl-to').value) - f;
    if (isFinite(len) && len > 0.001) lenEl.value = Math.round(len * 100) / 100;
  } else {                                   // 改开始或时长 → 顺推结束
    const len = parseFloat(lenEl.value);
    if (isFinite(f) && isFinite(len) && len > 0.001) {
      document.getElementById('pl-to').value = hToTime(Math.min(WK.end, f + len));
    }
  }
  renderPlanRemain();
}

/* 预览: 本次**实际能排**多少 + 排完本周还剩多少。
   新任务没有历史投入可对照, 所以不摆时段弹窗那套"预计总投入 / 已投入"
   (renderSlotRemain) —— 那是已有任务才有的数字。

   跨午休时这里显示的**不是** 结束−开始, 而是切掉午休后真正排进去的时长, 并且把切出来
   的段一起列出来。必须说清: 人填"9 点到 5 点"、看到"本次 6h"才不会以为自己填错了 ——
   而 6h 恰恰就是这件事的实际工作量。 */
function renderPlanRemain() {
  const el = document.getElementById('pl-remain');
  if (!el) return;
  const f = timeToH(document.getElementById('pl-from').value);
  const tt = timeToH(document.getElementById('pl-to').value);
  const ok = isFinite(f) && isFinite(tt) && tt > f;
  const segs = ok ? carveBreak(f, tt) : [];
  const add = segs.reduce((a, s) => a + (s[1] - s[0]), 0);
  let html = '';
  if (add > 0) {
    const used = state.plan.slots.reduce((a, s) => a + (s.to - s.from), 0);
    const left = weekHours() - used - add;
    html = '本次 ' + fmtDur(add) + ' · 排完本周 ' +
      (left < -0.001 ? '超 <b style="color:#d6453d">' + fmtDur(-left) + '</b>'
        : left > 0.001 ? '还剩 <b>' + fmtDur(left) + '</b>'
        : '<b style="color:#2e9e5b">刚好排满</b>');
    // 只在**真的被切过**时说明(段数可能仍是 1 —— 如 11:00–12:00 会被截到 11:30)。
    // 没跨午休却提一句"已跳过"只会让人以为出了什么事
    if (add < (tt - f) - 1e-9) {
      html += '<br>跨午休，自动排成 <b>' + segsText(segs) + '</b>（' +
        hm(WK.brkStart) + '–' + hm(WK.brkEnd) + ' 不排工作）';
    }
  } else if (ok) {
    html = '<b style="color:#d6453d">整段都落在午休 ' + hm(WK.brkStart) + '–' +
      hm(WK.brkEnd) + ' 里，没有可排的时间</b>';
  }
  el.innerHTML = html;
}

function savePlanTask() {
  const name = document.getElementById('pl-name').value.trim();
  if (!name) { toast('请填写任务名称', 'err'); return; }
  const day = parseInt(document.getElementById('pl-day').value, 10) || 1;
  const r = readTimeRange('pl-from', 'pl-to');
  if (r.err) { toast(r.err, 'err'); return; }

  // 跨午休**不再要求人拆两段**: 按午休切开, 一次排成多段(见 carveBreak)。
  // 返回空数组说明整段都落在午休里 —— 那才是真的没得排
  const segs = carveBreak(r.f, r.t);
  if (!segs.length) {
    toast('这段时间整个落在午休 ' + hm(WK.brkStart) + '–' + hm(WK.brkEnd) +
      ' 里，没有可排的时间', 'err');
    return;
  }

  // **重叠必须先挡住**: 服务端的 clean_slots 只做边界与网格清洗, **不检查重叠**。
  // 两块叠在一起会互相压住看不清, 而且周表底部的"已安排 / 各象限 / 未归类"会重复计数。
  // 拖拽与任务编排不会撞(它们是自动找空位); 只有这里是人手工指定, 所以只有这里要拦。
  // **逐段查**: 只查原始区间的话, 段与段之间的午休空档会漏过去
  let clash = null, clashSeg = null;
  for (const g of segs) {
    clash = state.plan.slots.find(s =>
      s.day === day && g[0] < s.to - 1e-9 && s.from < g[1] - 1e-9);
    if (clash) { clashSeg = g; break; }
  }
  if (clash) {
    const ct = byNo(clash.no);
    toast(hm(clashSeg[0]) + '–' + hm(clashSeg[1]) + ' 和 ' +
      hm(clash.from) + '–' + hm(clash.to) + '（' + (ct ? ct.name : 'No.' + clash.no) +
      '）重叠了', 'err');
    return;
  }

  const estRaw = document.getElementById('pl-est').value.trim();
  const est = estRaw === '' ? null : (num(estRaw) || null);
  const quadrant = selectValue('pl-quad');
  // "哪天"是**周内第几天**, 不是绝对日期 —— 按当前查看那一周推算: 翻到下周录入, 落的就是下周
  const ws = parseYmd(state.plan.week_start || TODAY);
  const sel = fmtYmd(new Date(ws.getTime() + (day - 1) * 86400000));
  closeModal('m-plan');

  // 一次请求写两处(任务 + 时段)。为什么不能分两步: 新任务的 no 由**服务端**分配,
  // 前端拿不到它就没法写时段 —— 详见 serve_task_flow.py 里 /api/add_task 那段注释。
  // 发**切好的段**而不是原始起止: 怎么切由上面那一次计算决定, 服务端只逐段校验(不重推)
  post('/api/add_task', {
    name: name, quadrant: quadrant, estimate_h: est,
    date: sel,
    slots: segs.map(g => ({ from: g[0], to: g[1] }))
  }).then(d => {
    if (!d.ok) { toast(d.error || '录入失败', 'err'); return; }
    toast('已录入 No.' + d.no + '「' + name + '」 并排到 ' + WK.names[day - 1] + ' ' +
      segsText(segs) + (d.hours ? '（' + fmtDur(d.hours) + '）' : ''), 'ok');
    // 服务端一次写了两处, 本地这两份状态都得跟上 ——
    // 只更新 slots 的话, 时段块会因为 byNo() 找不到这条新任务而整块不渲染
    if (d.task && !byNo(d.no)) state.tasks.push(d.task);
    if (state.plan.week_start === d.week_start) {
      state.plan.slots = d.slots;
      renderWeek();
      render();                // 副标题与象限列表也要跟上(新任务可能直接进了某个象限)
    } else {
      loadWeekPlan(d.week_start);   // 录到了别的周 → 直接翻过去看
    }
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
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

/* 时段弹窗里的 🗑️ —— 与时段块右上角的 ✕ 是同一个动作, 只是从弹窗里点更显眼。
   两种范围(文案在 openSlot 里切换, 点之前就看得见):
     普通任务 / 临时任务还有别的时段 → 只移出**这一个时段**
     临时任务且这是最后一个时段      → 连整条记录一起删

   后者为什么要连任务一起删: 临时任务本质就是"一条时间记录", 任务与时段是一起建出来的。
   只删时段会留下一条**没有任何时间记录的 temp 任务** —— 而 temp 不进待办池、完成后
   在四象限页哪里都看不到, 等于凭空多一条幽灵记录(与孤儿时段是同一类毛病, 方向相反)。*/
function delSlotFromModal() {
  const idx = editingSlot;
  const s = state.plan.slots[idx];
  if (!s) return;
  const t = byNo(s.no);
  const back = num(s.done_h) || 0;
  const lastOfTemp = !!(t && t.temp &&
    state.plan.slots.filter(x => String(x.no) === String(s.no)).length <= 1);
  closeModal('m-slot');
  if (lastOfTemp) {
    postDeleteTask(s.no).then(d => {
      if (d && d.ok) toast('已删除临时记录「' + t.name + '」', 'ok');
    });
    return;
  }
  // 与 delSlot 一样: 不二次确认, 但把回退了多少写进提示
  savePlan(state.plan.slots.filter((_, i) => i !== idx),
    back > 0 ? '已移出时间表，并回退 ' + fmtDur(back) + '实际投入' : '已移出时间表',
    undoOf([s]));
}

/* 提交周计划。**先提交、成功后才改本地** ——
   反过来(先改本地再提交)一旦失败就会留下脏状态: 内存里已经改了, 服务端没改,
   而且之后任何一次 renderWeek() 都会拿这份脏数据重绘, UI 与服务端长期不一致。
   调用方传"新值", 由这里负责在成功后落到 state.plan。 */
function savePlan(nextSlots, msg, undo, after) {
  const week = state.plan.week_start;
  return post('/api/week_plan', { week_start: week, slots: nextSlots, undo: undo || [] }).then(d => {
    if (!d.ok) { toast(d.error || '保存失败', 'err'); return; }
    // 同 saveWeekReview: 回调里现取 state.plan, 避免等待期间翻周后写到已脱离的旧对象上
    // (after 也按同一原则, 由调用方在回调里现取, 不要捕获此刻的对象)
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
    if (after) after();    // 落盘成功后的后续动作(如"存完就完成")
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
  // 临时任务留空时会在完成那一步按"结束 − 开始"自动补上投入, 提示里说清楚 ——
  // 否则这是个隐形行为: 用户不知道自己没填的那个数是怎么来的
  document.getElementById('sl-done').placeholder = (t && t.temp)
    ? '留空 = 完成时按 结束−开始 自动填'
    : '留空 = 只改时间';
  // 已完成的就不再给 ✅ 了(重复完成没有意义), 但时段仍可改 —— 时间记错了要能修
  const db = document.getElementById('sl-done-btn');
  if (db) db.style.display = (t && t.finished) ? 'none' : '';
  // 删除按钮的文案跟着**范围**走, 点之前就知道会删掉什么:
  //   普通任务, 或临时任务还有别的时段 → 只移出这一个时段
  //   临时任务且这是最后一个时段      → 连整条记录一起删(见 delSlotFromModal 的理由)
  const del = document.getElementById('sl-del');
  if (del) {
    const last = !!(t && t.temp &&
      state.plan.slots.filter(x => String(x.no) === String(s.no)).length <= 1);
    del.textContent = last ? '🗑️ 删除记录' : '🗑️ 删除时段';
    del.title = last
      ? '删除这条临时记录：任务与它的时段一并移除'
      : '把这段时间从时间表上拿下来（任务本身保留）';
  }
  // 机动来源只有临时任务有。这里也是它**唯一能补标/改标**的地方 —— 临时任务默认
  // "已完成", 完成后就离开待安排池, 别处再也够不到它
  const iw = document.getElementById('sl-int-wrap');
  if (iw) {
    iw.style.display = (t && t.temp) ? '' : 'none';
    setSelectValue('sl-interrupt', (t && INTERRUPT[t.interrupt]) ? t.interrupt : '');
  }
  renderSlotRemain();
  openModal('m-slot');
}

/* 保存时段时把"机动来源"那一栏一并写回(只有临时任务有这一栏)。
   单独发一个请求、而不是塞进 savePlan: interrupt 是**任务级**字段、住在 task_flows.json,
   跟 slots 不在一处 —— 混进周计划请求会把它写到错误的文件上 */
function collectSlotInterrupt() {
  const s = state.plan.slots[editingSlot];
  const t = s ? byNo(s.no) : null;
  if (!t || !t.temp) return;
  const iv = selectValue('sl-interrupt');
  if ((t.interrupt || '') === iv) return;               // 没变就不发请求
  post('/api/set_interrupt', { no: String(t.no), interrupt: iv }).then(d => {
    if (!d.ok) { toast(d.error || '机动来源没保存上', 'err'); return; }
    t.interrupt = d.interrupt || '';
    renderWeekFoot();                                   // 周表底部"构成"那一行立刻跟上
    renderTempPanel();                                  // 面板上的来源角标也要跟上
  }).catch(() => toast('连接服务器失败，请确认已启动 serve_task_flow.py', 'err'));
}

function saveSlot() {
  const idx = editingSlot;
  const s = state.plan.slots[idx];
  if (!s) return;
  const r = readTimeRange('sl-from', 'sl-to');
  if (r.err) { toast(r.err, 'err'); return; }
  const doneMin = parseFloat(document.getElementById('sl-done').value) || 0;
  if (isNaN(doneMin) || doneMin < 0) { toast('实际投入要填 0 或正数', 'err'); return; }
  collectSlotInterrupt();     // 弹窗一关就取不到了, 先收走
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

/* 时段弹窗里的 ✅: 先按"保存"把这次改动落盘(时段起止 + 这次做了多少), 再走完成流程。
   不做成"只完成"的理由和工时弹窗那个 ✅ 一样 —— 用户在这个弹窗里往往刚改过时间或填了投入,
   直接完成会把那笔改动丢掉。
   完成走 confirmComplete: 卡片会从象限列表收起、并计入仪表盘, 不是个该静默发生的动作。
   (临时任务没有象限卡片, 但同样走这里 —— 它之前唯一的完成入口在任务清单页) */
function saveSlotThenDone() {
  const idx = editingSlot;
  const s = state.plan.slots[idx];
  if (!s) return;
  const r = readTimeRange('sl-from', 'sl-to');
  if (r.err) { toast(r.err, 'err'); return; }
  const doneMin = parseFloat(document.getElementById('sl-done').value) || 0;
  if (isNaN(doneMin) || doneMin < 0) { toast('实际投入要填 0 或正数', 'err'); return; }
  const no = s.no;
  const t0 = byNo(no);
  closeModal('m-slot');

  const next = state.plan.slots.map((x, i) =>
    i === idx ? { no: x.no, day: x.day, from: r.f, to: r.t,
                  done_h: Math.round(((num(x.done_h) || 0) + doneMin / 60) * 60) / 60 } : x);
  // 落盘成功后才弹完成确认 —— 反过来的话, 保存失败会留下"确认了完成、但改动没写进去"
  const finish = () => { const t = byNo(no); if (t) confirmComplete(no, t, null); };

  // 没填"这次做了多少"时, 临时任务改用**它占的时段时长**(结束 − 开始)当投入。
  // 理由: 临时任务记的就是"这段时间被这件事占了", 那个时长本身就是它的实际投入 ——
  // 留空的话这条时间记录就没有投入数字, 而"完成"正是唯一能补上的时机。
  // 普通任务不这么做: 时段长度 ≠ 实际做了多久(排了 2h 可能只做了 40 分钟), 不能替人假设。
  let hours = doneMin / 60;
  if (hours <= 0.001 && t0 && t0.temp) hours = Math.round((r.t - r.f) * 60) / 60;
  if (hours <= 0.001) { savePlan(next, null, null, finish); return; }

  post('/api/log_actual', { no: no, hours: hours }).then(d => {
    if (!d.ok) { toast(d.error || '记录实际投入失败', 'err'); return; }
    const t = byNo(no);
    if (t && d.task) { t.actual_h = d.task.actual_h; t.estimate_h = d.task.estimate_h; }
    savePlan(next, null, null, finish);
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

  document.getElementById('tmp-est').value = '';
  setSelectValue('tmp-status', '已完成');   // 默认"已完成" —— 记的时候多半已经发生了
  // 机动来源**不预选**: 给个默认等于替人归类, 而这类统计的全部价值就在归因准确
  setSelectValue('tmp-interrupt', '');
  document.getElementById('tmp-hint').innerHTML =
    '会作为一条<b>临时任务</b>记进 ' + state.plan.week_start + ' 那一周的时间表。<br>' +
    '它不进待办、不参与象限统计 —— 突发占用会在周表下方单独列出。<br>' +
    '标「已完成」的直接计入机动消耗；没做完的等收工时点时段块补一笔。<br>' +
    '选了"被什么打断"，周表下方会按来源拆开显示；漏选不拦，之后点那个时段块能补标。';
  openModal('m-temp');
}

/* 下拉框的赋值 / 取值(状态与两处机动来源共用)。
   统一走这两个函数、而不是各处自己写 getElementById(...).value —— 散在三处的话,
   哪天规则一变(要 trim、要回落空串)就得记得改三处。
   空值统一用 '' 表示"没选", 与 <option value="">未标注</option> 对应 */
function setSelectValue(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v || '';
}
function selectValue(id) {
  const el = document.getElementById(id);
  return (el && el.value) || '';
}

function saveTempTask() {
  const name = document.getElementById('tmp-name').value.trim();
  if (!name) { toast('请填写这件事是什么', 'err'); return; }
  const date = document.getElementById('tmp-date').value.split('-').join('/');
  const r = readTimeRange('tmp-from', 'tmp-to');
  if (r.err) { toast(r.err, 'err'); return; }

  // 预估工时留空就不传, 由服务端按时段时长兜底 —— 这里也判一次是为了不把 NaN 发过去
  const estVal = parseFloat(document.getElementById('tmp-est').value);
  const status = selectValue('tmp-status') || '已完成';
  // 机动来源可以留空(= 未标注), 但传了它就决定这条记录归到构成里的哪一类
  const interrupt = selectValue('tmp-interrupt');
  post('/api/add_temp_task', {
    name: name, date: date, from: r.f, to: r.t,
    status: status,
    interrupt: interrupt,
    estimate_h: isNaN(estVal) ? null : estVal
  }).then(d => {
    if (!d.ok) { toast(d.error || '记录失败', 'err'); return; }
    closeModal('m-temp');
    toast('已记下「' + name + '」' + fmtDur(d.hours) + '（' + status + '）', 'ok');
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
  // 把当周机动构成摆在写自评的地方 —— "这周为什么没做成"最常见的答案就是突发
  // (§2.9.4 的卡点表里本来就有"被打断")。**不额外存快照**: 历史周的 slots 都在,
  // 翻到哪一周都能直接重算, 比"写自评那一刻"的快照更准
  const bufEl = document.getElementById('wrev-buf');
  if (bufEl) {
    const brk = tempBreakHtml();
    bufEl.innerHTML = brk
      ? '本周机动：已用 <b>' + fmtDur(tempHours()) + '</b> / 额度 ' + fmtDur(weekBufferH()) +
        '<br>构成：' + brk
      : '';
  }
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
  // 含「录入新任务」的 pl-from / pl-to —— 它们同样是手填起止的地方。真校验仍在
  // readTimeRange(它按 WK.start/WK.end 判), 这里给的只是浏览器自带的边界提示
  ['sl-from', 'sl-to', 'tmp-from', 'tmp-to', 'pl-from', 'pl-to'].forEach(id => {
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

    # 四象限的 <option>(含空选项 = 未归类)。文案与任务清单页的「添加任务」保持一致 ——
    # 两处都是"给新任务定象限", 说法不同会让人以为字段含义也不同。
    # 默认"未归类"而不是自动判定: 象限是**判断**, 只能由人来定(§2.4 的推导仅作角标提示)
    quad_options = '<option value="">未归类（之后在象限里归）</option>' + "".join(
        '<option value="%s">%s · %s（%s）</option>'
        % (q, q, QUADRANT_META[q]["label"], QUADRANT_META[q]["action"])
        for q in QUADRANT_ORDER
    )

    # 机动来源的 <option> 列表。**同一份注入两处弹窗**(记临时任务 / 时段块补标),
    # 枚举仍只在 meta.py 维护一份(单一来源约定)。
    # 开头是空值选项 —— 来源允许留空(= 未标注), 必须有个能显式表达"没选"的项,
    # 否则只能拿某个真实类别当默认, 那就等于替人归类了
    interrupt_options = '<option value="">未标注</option>' + "".join(
        '<option value="%s" title="%s">%s</option>' % (k, INTERRUPT_META[k]["hint"], k)
        for k in INTERRUPT_ORDER
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
            .replace("__QUAD_OPTIONS__", quad_options)
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
            .replace("__INTERRUPT_META__", js(INTERRUPT_META))
            .replace("__INTERRUPT_OPTIONS__", interrupt_options)
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