"""
week_plan.py
每周时间安排的数据层: 读写 data/week_plan.json。

用途:
    给四象限页面的"每周时间安排"卡片提供数据。把任务摆到具体的
    周几 + 小时段上(工作时间 9:00-18:00), 用于可视化时间落在哪儿。

结构:
    {
      "week_start": "2026/09/14",                      # 该周周一
      "slots": [
        {"no": "37", "day": 1, "from": 9, "to": 11}    # day: 1=周一 .. 7=周日
      ]
    }

约定:
    - 一个任务可以在一周内出现多次(多个时段)
    - from / to 是小时(24 进制), 只允许落在 [DAY_START, DAY_END]
    - 文件缺失或损坏时按空计划处理, 不抛异常(否则会打挂整个接口)

设计文档: docs/design/time-quadrant-design.md §9.6 (与日排程 slots 结构对齐)
"""

import json
import os
import re
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
WEEK_PLAN_JSON = os.path.join(DATA_DIR, "week_plan.json")

# 工作时间窗: 08:30 - 22:30; 页面以 1 小时为间隔设行(共 14 行), 边界都落在 .5 上。
# 用浮点小时表示: 8.5 = 08:30, 22.5 = 22:30
DAY_START = 8.5
DAY_END = 22.5
HOURS_PER_DAY = DAY_END - DAY_START

# 午休时段: 一般不安排工作。页面上拖拽会被拒绝, 自动铺开也会跳过(把上午和下午自然切开)
BREAK_START = 11.5   # 11:30
BREAK_END = 13.5     # 13:30

# 工作时间: 09:00 - 18:00。其余时段在时间轴上标为"下班时间"(灰底),
# 只做视觉区分 —— 不禁止安排(临时的晚间工作也需要落位)
WORK_START = 9.0
WORK_END = 18.0

DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def parse_date(s):
    """解析 YYYY/MM/DD; 非法或日期不存在时返回 None。"""
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})$", (s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def week_start_of(d=None):
    """返回 d 所在周的周一(YYYY/MM/DD 字符串)。"""
    d = d or date.today()
    return (d - timedelta(days=d.weekday())).strftime("%Y/%m/%d")


def empty_plan(week_start=None):
    return {"week_start": week_start or week_start_of(), "slots": []}


def snap_half(h):
    """把小时对齐到 0.5(半小时), 避免出现 9.3 这种无法在时间表上对齐的值。"""
    return round(h * 2) / 2


def clean_slots(raw):
    """清洗 slots: 丢弃非法项, 对齐到半小时, 并把时间范围夹到工作时间窗内。"""
    out = []
    if not isinstance(raw, list):
        return out
    for s in raw:
        if not isinstance(s, dict):
            continue
        no = str(s.get("no") or "").strip()
        if not no:
            continue
        try:
            day = int(s.get("day"))
            h_from = float(s.get("from"))
            h_to = float(s.get("to"))
        except (TypeError, ValueError):
            continue
        if not 1 <= day <= 7:
            continue
        h_from = snap_half(max(DAY_START, min(DAY_END - 0.5, h_from)))
        h_to = snap_half(max(h_from + 0.5, min(DAY_END, h_to)))
        out.append({"no": no, "day": day, "from": h_from, "to": h_to})
    return out


def read_week_plan():
    """读取周计划; 文件缺失或损坏时返回空计划。"""
    if not os.path.exists(WEEK_PLAN_JSON):
        return empty_plan()
    try:
        with open(WEEK_PLAN_JSON, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (ValueError, OSError):
        return empty_plan()
    if not isinstance(raw, dict):
        return empty_plan()
    week_start = str(raw.get("week_start") or "").strip() or week_start_of()
    return {"week_start": week_start, "slots": clean_slots(raw.get("slots"))}


def write_week_plan(plan):
    """写入周计划(会先清洗 slots)。"""
    data = {
        "week_start": str(plan.get("week_start") or "").strip() or week_start_of(),
        "slots": clean_slots(plan.get("slots")),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(WEEK_PLAN_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data
