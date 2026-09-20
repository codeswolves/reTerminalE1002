"""
week_plan.py
每周时间安排的数据层: 读写 data/week_plan.json。

用途:
    给四象限页面的"每周时间安排"卡片提供数据。把任务摆到具体的
    周几 + 小时段上(工作时间 9:00-18:00), 用于可视化时间落在哪儿。

结构(按周存储):
    {
      "weeks": {
        "2026/09/14": [                                  # 该周周一
          {"no": "37", "day": 1, "from": 9, "to": 11}    # day: 1=周一 .. 7=周日
        ],
        "2026/09/21": []
      },
      "reviews": {
        "2026/09/14": {                                  # 该周的自我评述
          "text": "本周...",
          "at": "2026/09/18 22:40",
          "plan_h": 11.0,     # 写自评时: 本周已排工时
          "slot_n": 2,        # 写自评时: 本周已排时段数
          "done_n": 3,        # 写自评时: 本周已完成的任务数
          "done_h": 17.5      # 写自评时: 这些任务的净投入合计
        }
      },
      "buffers": {
        "2026/09/21": 8       # 该周的机动额度(小时); 只存偏离默认值(WEEK_BUFFER_H)的周
      }
    }

约定:
    - 一个任务可以在一周内出现多次(多个时段)
    - from / to 是小时(24 进制), 只允许落在 [DAY_START, DAY_END]
    - 到新的一周自动切到空白的新周, 不需要手动清空; 旧周数据保留, 可翻回查看
    - 文件缺失或损坏时按空计划处理, 不抛异常(否则会打挂整个接口)
    - 兼容早期单周格式 {"week_start", "slots"}, 读到后自动升级
    - **weeks / reviews / buffers 必须一起读写**: 三者同一个文件, 只写其中一个会静默抹掉其它两个
    - 时段可以指向**临时(突发)任务**(task_flows.json 里 temp: true): 它只做时间记录,
      不进待办池也不参与象限统计, 其占用由页面在周表底部单独列出
    - 机动额度**按周**存(buffers), 不按天: 突发不可能每天恰好 1h(见 meta.WEEK_BUFFER_H)

设计文档: docs/design/time-quadrant-design.md §9.6 (与日排程 slots 结构对齐)
"""

import json
import math
import os
import re
import threading
from datetime import date, timedelta

# 机动额度的默认值来自 meta(单一来源约定)。与 meta.py 同目录,
# 调用方(服务端 / 生成器)都已把 generators 加进 sys.path。
from meta import WEEK_BUFFER_H

# weeks 与 reviews 同存一个文件, 而服务端是多线程(每请求一线程),
# 两个端点各自"读整个文件 → 改自己的字段 → 整文件写回"。
# 交错时后写者会用"自己读到的旧值"覆盖掉先写者刚落盘的字段 ——
# 这正是 generate_quadrant.py 里"必须顺序提交"那条注释要防的事, 在服务端补一把锁。
_FILE_LOCK = threading.Lock()

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
    """空的一周。与 read_week_plan 的返回结构保持一致(含 review)。"""
    return {"week_start": week_start or week_start_of(), "slots": [], "review": None}


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


def norm_week(week_start=None):
    """规范化为该周的周一; 非法或缺失时返回本周周一。"""
    d = parse_date(str(week_start or "").strip())
    return week_start_of(d) if d else week_start_of()


def shift_week(week_start, delta_weeks):
    """周偏移(用于页面上的上一周/下一周导航)。"""
    d = parse_date(norm_week(week_start))
    return week_start_of(d + timedelta(weeks=delta_weeks))


# 只接受这四个键: 客户端多传的字段一律丢弃, 免得文件里长出无人认识的字段
SNAP_KEYS = ("plan_h", "slot_n", "done_n", "done_h")


def _num(v):
    """宽松转成非负有限数字; 不合法返回 None。

    读与写都走这里, 口径才一致 —— 否则会出现"写入接受字符串 '12'、读取却丢弃"的怪事。
    拒绝 NaN/Inf: json.dump 默认会把它们写成非法的 JSON token, 前端 JSON.parse 直接抛错。
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 0:
        return None
    return round(f, 2)


def _clean_review(raw):
    """清洗一条周自评; 没有正文时返回 None(视为未填写)。

    plan_* 是"写自评时排了多少", done_* 是"写自评时已做完了多少" ——
    两组都是快照, 可选。之所以要存, 是因为自评是主观判断,
    以后回看时若没有当时的数字, 就只能拿今天的排期去解释当时的结论。
    """
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("text") or "").strip()
    if not text:
        return None
    out = {"text": text, "at": str(raw.get("at") or "").strip()}
    for k in SNAP_KEYS:
        v = _num(raw.get(k))
        if v is not None:
            out[k] = v
    return out


def _read_raw():
    """读取整个文件, 返回 {"weeks": {...}, "reviews": {...}, "buffers": {...}}。

    三个字段必须一起读 —— 它们共用同一个文件, 分开写会互相覆盖(见 _write_raw)。
    """
    empty = {"weeks": {}, "reviews": {}, "buffers": {}}
    if not os.path.exists(WEEK_PLAN_JSON):
        return empty
    try:
        with open(WEEK_PLAN_JSON, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (ValueError, OSError):
        return empty
    if not isinstance(raw, dict):
        return empty

    weeks = raw.get("weeks")
    weeks = {str(k): clean_slots(v) for k, v in weeks.items()} if isinstance(weeks, dict) else {}
    if not weeks:
        # 旧格式迁移: {"week_start": "...", "slots": [...]} —— 读到即升级, 不丢数据
        old_week = str(raw.get("week_start") or "").strip()
        if old_week:
            weeks = {old_week: clean_slots(raw.get("slots"))}

    reviews = raw.get("reviews")
    if isinstance(reviews, dict):
        reviews = {str(k): _clean_review(v) for k, v in reviews.items()}
        reviews = {k: v for k, v in reviews.items() if v}
    else:
        reviews = {}

    # 机动额度: 只存"偏离默认值"的周, 读进来也只保留合法数字
    buffers = raw.get("buffers")
    if isinstance(buffers, dict):
        buffers = {str(k): _num(v) for k, v in buffers.items()}
        buffers = {k: v for k, v in buffers.items() if v is not None}
    else:
        buffers = {}
    return {"weeks": weeks, "reviews": reviews, "buffers": buffers}


def _write_raw(data):
    """写回整个文件。

    **必须把 reviews 与 buffers 一并写回** —— 排期 / 自评 / 机动额度在同一个文件里,
    只写其中一个会在用户改其它两项时把它们静默抹掉。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(WEEK_PLAN_JSON, "w", encoding="utf-8") as f:
        # allow_nan=False: 宁可抛异常, 也不要写出 NaN 这种非法 JSON ——
        # 那会让前端 JSON.parse 失败, 表现为"读取周计划失败", 排查半天找不到原因
        json.dump({"weeks": data.get("weeks") or {},
                   "reviews": data.get("reviews") or {},
                   "buffers": data.get("buffers") or {}}, f,
                  ensure_ascii=False, indent=2, allow_nan=False)


def read_weeks():
    """全部周的排期。返回 {week_start: [slots]}。"""
    return _read_raw()["weeks"]


def read_reviews():
    """全部周的自评。返回 {week_start: {text, at, plan_h?, slot_n?, done_n?, done_h?}}。"""
    return _read_raw()["reviews"]


def read_week_plan(week_start=None):
    """读取指定周的计划 + 自评 + 机动额度(默认本周)。

    按周存储 —— 到了新的一周自动显示空白的新周, **不需要手动清空**;
    旧周的安排、自评与机动额度仍留在文件里, 用页面上的"← 上一周"可以翻回去看。

    buffer_h 是该周的机动额度: 没单独设过就回落到默认值(WEEK_BUFFER_H)。
    """
    week = norm_week(week_start)
    data = _read_raw()
    return {"week_start": week, "slots": data["weeks"].get(week, []),
            "review": data["reviews"].get(week),
            "buffer_h": data["buffers"].get(week, WEEK_BUFFER_H)}


def write_week_plan(week_start=None, slots=None):
    """只写入指定周的排期(默认本周), 不动其它周的排期、自评与机动额度。"""
    week = norm_week(week_start)
    # 加锁: 读-改-写必须整体串行, 否则与 write_week_review 并发时互相覆盖
    with _FILE_LOCK:
        data = _read_raw()
        data["weeks"][week] = clean_slots(slots)
        _write_raw(data)
        return {"week_start": week, "slots": data["weeks"][week],
                "review": data["reviews"].get(week),
                "buffer_h": data["buffers"].get(week, WEEK_BUFFER_H)}


def write_week_review(week_start=None, text="", stamp="", snap=None):
    """写入指定周的自评; text 传空表示删除该周自评。

    snap 是"写自评那一刻"的数字快照, 全部可选:
        plan_h / slot_n —— 本周已排的工时与时段数
        done_n / done_h —— 本周已完成的任务数与其净投入合计
    存它们是为了让回顾有依据: 自评是主观结论, 没有当时的数字,
    以后只能用今天的排期去解释, 很容易看不懂或误判。
    """
    week = norm_week(week_start)
    if not isinstance(snap, dict):
        snap = {}                      # 非 dict 会让下面的 .items() 直接抛异常
    text = str(text or "").strip()
    with _FILE_LOCK:
        data = _read_raw()
        if text:
            rec = {"text": text, "at": str(stamp or "").strip()}
            for k in SNAP_KEYS:        # 白名单: 只取这四个键
                v = _num(snap.get(k))
                if v is not None:
                    rec[k] = v
            data["reviews"][week] = rec
        else:
            data["reviews"].pop(week, None)   # 正文为空 = 删除该周自评
        _write_raw(data)
        return {"week_start": week, "review": data["reviews"].get(week)}


def read_week_buffer(week_start=None):
    """指定周的机动额度(小时); 未单独设置过则回落到默认值。"""
    week = norm_week(week_start)
    return _read_raw()["buffers"].get(week, WEEK_BUFFER_H)


def write_week_buffer(week_start=None, hours=None):
    """设置指定周的机动额度。返回 (结果, 错误信息)。

    hours 传 None / 空串(或恰好等于默认值)表示**恢复默认**, 会删掉该周的自定义值 ——
    只存"偏离默认值"的周, 文件里才不会堆一排无意义的 5.0。

    额度为什么要落盘、而不是像页面上另外几个预算参数那样纯前端(不落盘):
    **调整这个动作本身就是信号**。如果连着几周都在往上调, 说明 5h 这个基线定低了
    (或者突发已经常态化)。只放在内存里的话, 这个证据每周刷新页面就没了。
    """
    week = norm_week(week_start)
    raw = str(hours).strip() if hours is not None else ""
    h = None
    if raw != "":
        h = _num(hours)
        if h is None:
            return None, "机动额度要填 0 或正数"
    with _FILE_LOCK:
        data = _read_raw()
        if h is None or abs(h - WEEK_BUFFER_H) < 0.001:
            data["buffers"].pop(week, None)      # 等于默认值 = 不留痕迹
        else:
            data["buffers"][week] = h
        _write_raw(data)
        return {"week_start": week,
                "buffer_h": data["buffers"].get(week, WEEK_BUFFER_H)}, ""
