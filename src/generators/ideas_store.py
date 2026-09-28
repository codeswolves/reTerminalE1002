"""
ideas_store.py
灵感胶囊的数据层: 读写 data/ideas.json。

用途:
    给灵感胶囊页(ideas.html)提供数据。灵感**不是任务**: 它回答的是"这个想法可能是什么",
    而不是"这件事该怎么做完", 所以单独一个文件、单独一套口径 —— 理由见设计文档 §1.2 / §7.2。

结构:
    {
      "meta": {"updated": "2026/09/28"},
      "ideas": [
        {
          "id": "I007",                        # 稳定标识, I + 三位递增
          "text": "开完规划会路上想到的: ...",   # 记下时的原话(必填)
          "title": "用图神经网络做承载网流量预测",  # 一句话标题(可选)
          "deliverable": ["论文", "专利"],       # 可能产出, 多选, 可留空
          "status": "设计中",                    # 种子 / 设计中 / 已转出 / 封存
          "tags": ["承载网", "GNN"],             # 自由文本, 只服务检索
          "source": "P02 项目评审会上提到的问题",  # 从哪来的
          "created": "2026/09/20",
          "notes": [{"date": "2026/09/22", "text": "查了下, ..."}],
          "linked_task": "12",                  # 已转出时指向任务清单里的任务号
          "priority": "high",                   # 可选。**缺失 = 未评**(不是"中")
          "why": "数据拿不到"                    # 封存原因(§2.5)
        }
      ]
    }

约定:
    - 必填只有 `text` 与 `status`。捕获时的摩擦每多一个字段, 就多一批想法根本没被记下来,
      而"没记下来"是查不出来的(§2.2) —— 所以其余字段一律可缺, 之后在卡片上补
    - `id` 是稳定标识, 页面与接口都用它。**不用数组下标**: 删一条就会让所有引用错位
    - `deliverable` 是 meta.DELIVERABLE_ORDER 的**子集**(IDEA_DELIVERABLE_ORDER),
      与任务那边是同一批字符串 —— 转成任务时零映射(§2.3)
    - `status = 已转出` **只能由 promote 进入**, 不能手点(§2.4); 且它与 `linked_task` 必须同时成立
    - `priority` **可选**: 缺失 = "还没评", 是个合法状态, 不是"中优先级"。它不进捕获框(§3.1),
      只在卡片上就地设。**优先级不参与排序** —— 本页没有"按价值排序"(§4.3)
    - 写入时守住取值域、**读时不丢数据**: 子集外/未知的值照常读出来并显示(配色走灰兜底),
      藏起来比显示出来更危险。两条合起来才是 §2.3 那条边界
    - 文件缺失或损坏时按"没有灵感"处理, 不抛异常(否则会打挂整个接口)
    - 时间戳一律本地日期 `YYYY/MM/DD`(§7.5); "距上次推进多少天"这类**计算字段读时现算**,
      不落盘 —— 落盘隔天就过期, 而页面没有定时刷新

设计文档: docs/design/inspiration-capsule-design.md §2 (数据模型) / §7 (已知坑与约定)
"""

import json
import os
import re
import threading
from datetime import date

from meta import (
    DEFAULT_IDEA_STATUS,
    IDEA_DELIVERABLE_ORDER,
    IDEA_STATUS_ORDER,
    is_idea_status,
    is_priority,
)

# 灵感与任务一样: 服务端是多线程(每请求一线程), 而每个端点都是"读整个 JSON → 改一个字段
# → 整文件写回"。交错时后写者会拿自己读到的旧值覆盖先写者刚落盘的字段 —— 与 week_plan
# 补 `_FILE_LOCK` 是同一件事、同一条理由。
_FILE_LOCK = threading.Lock()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
IDEAS_JSON = os.path.join(DATA_DIR, "ideas.json")

# 接口可以改的字段(**白名单**)。
# 为什么是白名单: id / created / notes / linked_task 这几个各有各的流转规则
# (id 由服务端分配、created 不可变、notes 走 add_note、linked_task 只能由
# promote / 解除关联成对修改)。用黑名单的话, 漏掉一个就是一条静默的脏数据通道。
#
# `status` 在白名单里, 但它**不接受 `已转出`** —— 那个状态只能由 promote 进入(§2.4),
# 手点会造出"标着已转出、却没有对应任务"的悬空状态, 而那种状态在页面上看不出来。
EDITABLE_KEYS = ("text", "title", "deliverable", "tags", "source", "status", "priority", "why")

# "久置"判定(§4.2): `设计中` 且超过这么多天没有新增推进记录 -> 进页顶的久置区。
# 21 天 = 三周: 短于这个数, "还没动"是常态; 长于它, 才真是被放下了
STALE_DAYS = 21

_ID_RE = re.compile(r"^I(\d+)$")


def _today():
    return date.today().strftime("%Y/%m/%d")


def parse_date(s):
    """解析 YYYY/MM/DD; 非法或日期不存在时返回 None(与 week_plan.parse_date 同一处理)。"""
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})$", (s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 读 / 写 原始结构
# ---------------------------------------------------------------------------
def _read_raw():
    """读原始结构(不含计算字段)。文件缺失/损坏时返回空结构, 不抛异常。"""
    empty = {"meta": {}, "ideas": []}
    if not os.path.exists(IDEAS_JSON):
        return empty
    try:
        with open(IDEAS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    ideas = data.get("ideas")
    return {
        "meta": data.get("meta") if isinstance(data.get("meta"), dict) else {},
        "ideas": ideas if isinstance(ideas, list) else [],
    }


def _write_raw(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(IDEAS_JSON, "w", encoding="utf-8") as f:
        # allow_nan=False: 写出 NaN 会让前端 JSON.parse 直接失败, 整页白屏。
        # 而 NaN 很容易从一个除零的统计里悄悄产生 —— 宁可在服务端当场报错
        json.dump(
            {"meta": data.get("meta") or {}, "ideas": data.get("ideas") or []},
            f, ensure_ascii=False, indent=2, allow_nan=False,
        )


def _stamp(data):
    data.setdefault("meta", {})["updated"] = _today()
    return data


# ---------------------------------------------------------------------------
# 字段归一
# ---------------------------------------------------------------------------
def _clean_tags(raw):
    """标签归一 -> 去空白、去重、保序。允许传列表, 也允许传 "a, b c" 这样的字符串
    (卡片上是一行自由文本输入, 不该逼用户写 JSON)。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,，;；\s]+", raw)
    elif isinstance(raw, (list, tuple)):
        parts = []
        for x in raw:
            parts.extend(re.split(r"[,，;；\s]+", str(x)))
    else:
        return []
    out = []
    for p in parts:
        p = p.strip().lstrip("#").strip()
        if p and p not in out:
            out.append(p)
    return out


def _clean_deliverable(raw, write=False):
    """possible deliverable 归一 -> 去重、去空白、按枚举顺序排。

    **读路径不丢数据**(§2.3): 子集外的值照原样保留, 页面上显示并单独成一组 ——
    老数据、手改过的 JSON 都可能带别的值, 藏起来比显示出来更危险。
    **写路径守住取值域**: 子集外的值直接抛错, 让人当场知道, 而不是静默丢弃。
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [raw]
    elif isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        return []
    seen, unknown = [], []
    for p in parts:
        p = str(p).strip()
        if not p or p in seen:
            continue
        if p in IDEA_DELIVERABLE_ORDER:
            seen.append(p)
        elif write:
            raise ValueError(f"可能的产出只能是 {' / '.join(IDEA_DELIVERABLE_ORDER)}")
        else:
            unknown.append(p)
    order = {v: i for i, v in enumerate(IDEA_DELIVERABLE_ORDER)}
    known = sorted(seen, key=lambda v: order[v])
    return known + unknown


def _clean_idea(raw):
    """把一条灵感清洗成页面能渲染的形状。返回 None 表示这条根本不是对象, 跳过。

    **只修类型, 不改语义**: 认不出的 status / deliverable / priority 一律原样留着,
    交给页面用兜底样式显示。这个函数不是"校验器", 是读路径的兜底, 与 clean_slots 同一取向。

    id 缺失时留空, 由调用方补(补号要知道"已用过的最大号", 那是调用方才知道的事;
    按位置补会撞上真实存在的号, 于是两条灵感共用一个 id, 而页面与接口都靠 id 找人)。
    """
    if not isinstance(raw, dict):
        return None
    it = dict(raw)
    it["id"] = str(it.get("id") or "").strip()

    it["text"] = str(it.get("text") or "")
    if it.get("title") is not None:
        it["title"] = str(it.get("title") or "").strip()
    if it.get("source") is not None:
        it["source"] = str(it.get("source") or "").strip()
    if it.get("why") is not None:
        it["why"] = str(it.get("why") or "").strip()
    it["deliverable"] = _clean_deliverable(it.get("deliverable"))
    it["tags"] = _clean_tags(it.get("tags"))
    it["status"] = str(it.get("status") or "").strip() or DEFAULT_IDEA_STATUS
    if it.get("linked_task") is not None:
        it["linked_task"] = str(it.get("linked_task") or "").strip()

    # 优先级: 只认合法值。认不出的**不冒充成"中"** —— 页面上按"未评"(灰)显示,
    # 因为"我不知道它是什么"和"它就是中优先级"是两件不同的事
    pri = str(it.get("priority") or "").strip().lower()
    if is_priority(pri):
        it["priority"] = pri
    else:
        it.pop("priority", None)

    raw_notes = it.get("notes")
    notes = []
    if isinstance(raw_notes, list):
        for n in raw_notes:
            if isinstance(n, dict) and str(n.get("text") or "").strip():
                notes.append({"date": str(n.get("date") or "").strip(),
                              "text": str(n.get("text") or "").strip()})
    it["notes"] = notes
    if not str(it.get("created") or "").strip():
        it["created"] = _today()
    else:
        it["created"] = str(it["created"]).strip()
    return it


# ---------------------------------------------------------------------------
# 读(含计算字段)
# ---------------------------------------------------------------------------
def read_ideas(with_task_check=True):
    """读全部灵感, 附上**计算字段**(不落盘, §7.5):

        note_n              推进记录条数
        age_days            距 created 多少天
        idle_days           距上次推进多少天(最后一条 notes 的日期, 没有就按 created)
        stale               是否进"久置"区: status == 设计中 且 idle_days > STALE_DAYS
        linked_task_missing linked_task 指向的任务已不存在(§7.6)

    按 created 倒序返回(新的在前, §5.3 的组内顺序)。
    """
    today = date.today()
    raw_list = _read_raw()["ideas"]

    # 缺 id 的老数据(手改过 JSON、早期版本)要能读出来, 补号从**已用过的最大号**往后发:
    # 按位置补会撞上真实存在的号 —— 两条灵感共用一个 id 是页面与接口都查不出来的错
    nxt = 0
    for x in raw_list:
        m = _ID_RE.match(str(x.get("id", ""))) if isinstance(x, dict) else None
        if m:
            nxt = max(nxt, int(m.group(1)))

    out = []
    for raw in raw_list:
        it = _clean_idea(raw)
        if it is None:
            continue
        if not it["id"]:
            nxt += 1
            it["id"] = "I%03d" % nxt
        created = parse_date(it["created"])
        last = created
        for n in it["notes"]:
            d = parse_date(n["date"])
            if d and (last is None or d > last):
                last = d
        it["note_n"] = len(it["notes"])
        it["age_days"] = (today - created).days if created else None
        it["idle_days"] = (today - last).days if last else None
        it["stale"] = bool(it["status"] == "设计中" and it["idle_days"] is not None
                           and it["idle_days"] > STALE_DAYS)
        out.append(it)

    if with_task_check:
        # 只读的交叉核对(§7.6)。**只读** task_flows.json, 不碰它 ——
        # 灵感的数据仍然只属于本页面(§7.2 / §7.3), 这里只是拿任务号对一下有没有悬空
        nos = _task_nos()
        for it in out:
            lt = it.get("linked_task") or ""
            # 任务清单读不到时**不报悬空**: "不知道"不等于"已删除", 误报会让人白跑一趟
            it["linked_task_missing"] = bool(lt and nos is not None and lt not in nos)

    out.sort(key=lambda x: (parse_date(x["created"]) or date.min), reverse=True)
    return out


def _task_nos():
    """任务号集合; 读不到返回 None(与"读到了但是空的"区分开)。"""
    try:
        from generate_task_flow import read_tasks_raw  # 延迟导入: 避免模块级循环依赖
        return {str(t.get("no", "")) for t in read_tasks_raw()}
    except Exception:  # noqa: BLE001 — 交叉核对失败不该打挂灵感页
        return None


def count_by_status(ideas=None):
    """状态计数, 用于页头那行 `共 N 条 · 种子 6 · 设计中 11 · ...`。"""
    ideas = read_ideas(with_task_check=False) if ideas is None else ideas
    cnt = {k: 0 for k in IDEA_STATUS_ORDER}
    for it in ideas:
        cnt[it["status"]] = cnt.get(it["status"], 0) + 1
    return cnt


# ---------------------------------------------------------------------------
# 写
# ---------------------------------------------------------------------------
def next_id(ideas):
    """下一个 id: I + 三位递增。按**已用过的最大值**而不是条数 —— 删过条目之后,
    用条数会撞上仍被引用的旧 id。"""
    mx = 0
    for it in ideas:
        m = _ID_RE.match(str(it.get("id", "")))
        if m:
            mx = max(mx, int(m.group(1)))
    return "I%03d" % (mx + 1)


def add_idea(text, deliverable=None, tags=None):
    """新增一条。服务端分配 id, 其余留空 —— 捕获时只要求一段话(§3.1)。

    **刻意不收 priority**: 优先级不进捕获框。捕获时每多一个决定, 就多一批想法
    根本没被记下来, 而"没记下来"是查不出来的(§2.2)。它只在卡片上就地设。

    返回 (ok, res_or_err): ok 时 res = {"id": ..., "idea": {...}}(idea 为刚落盘的那条)。
    """
    text = str(text or "").strip()
    if not text:
        return False, "灵感内容不能为空"
    try:
        deliv = _clean_deliverable(deliverable, write=True)
    except ValueError as exc:
        return False, str(exc)
    tags_clean = _clean_tags(tags)

    with _FILE_LOCK:
        data = _read_raw()
        idea = {"id": next_id(data["ideas"]), "text": text,
                "status": DEFAULT_IDEA_STATUS, "created": _today()}
        if deliv:
            idea["deliverable"] = deliv
        if tags_clean:
            idea["tags"] = tags_clean
        data["ideas"].append(idea)
        _write_raw(_stamp(data))
    return True, {"id": idea["id"], "idea": idea}


def set_idea_field(idea_id, key, value):
    """改一个字段。value 为 None / 空串 = **删除该字段**(与 set_task_field 同一约定)。

    取值域在这里守住(§2.3): `deliverable` 只接受子集内的值; `priority` 只接受
    合法值(空 = 回到"未评"); `status` 只接受枚举内且**不接受 `已转出`** ——
    那个状态只能由 promote 进入(§2.4), 手点会把"已转出但没任务"这种悬空状态造出来。
    """
    target = str(idea_id or "").strip()
    if not target:
        return False, "缺少灵感编号"
    key = str(key or "").strip()
    if key not in EDITABLE_KEYS:
        return False, f"这个字段不能这样改: {key}"

    with _FILE_LOCK:
        data = _read_raw()
        it = None
        for cand in data["ideas"]:
            if str(cand.get("id", "")).strip() == target:
                it = cand
                break
        if it is None:
            return False, f"灵感 {target} 不存在"

        if key == "text":
            text = str(value or "").strip()
            if not text:
                return False, "灵感内容不能为空"
            it["text"] = text
        elif key == "deliverable":
            try:
                deliv = _clean_deliverable(value, write=True)
            except ValueError as exc:
                return False, str(exc)
            if deliv:
                it["deliverable"] = deliv
            else:
                # 空 = 未定(合法状态, §2.3), 但字段本身不该留一个空壳
                it.pop("deliverable", None)
        elif key == "tags":
            tags_clean = _clean_tags(value)
            if tags_clean:
                it["tags"] = tags_clean
            else:
                it.pop("tags", None)
        elif key == "priority":
            pri = str(value or "").strip().lower()
            if not pri:
                it.pop("priority", None)          # 回到"未评"
            elif not is_priority(pri):
                return False, f"非法优先级: {pri}"
            else:
                it["priority"] = pri
        elif key == "status":
            st = str(value or "").strip()
            if st == "已转出":
                return False, "「已转出」只能通过「转成任务」进入"
            if not is_idea_status(st):
                return False, f"非法状态: {st}"
            it["status"] = st
        else:                                       # text 之外的普通文本字段
            val = str(value or "").strip()
            if val:
                it[key] = val
            else:
                it.pop(key, None)

        _write_raw(_stamp(data))
    return True, {"id": target}


def add_idea_note(idea_id, text):
    """追加一条推进记录 {date, text}。日期用本地日期(§7.5)。

    它与"状态"是两件事: 状态说这件事走到哪了, 推进记录说"后来又
    想通了什么"。加记录**不改状态** —— §2.4 明确"系统不自动升级状态"。
    """
    target = str(idea_id or "").strip()
    text = str(text or "").strip()
    if not target:
        return False, "缺少灵感编号"
    if not text:
        return False, "推进记录不能为空"

    with _FILE_LOCK:
        data = _read_raw()
        it = None
        for cand in data["ideas"]:
            if str(cand.get("id", "")).strip() == target:
                it = cand
                break
        if it is None:
            return False, f"灵感 {target} 不存在"
        notes = it.get("notes")
        if not isinstance(notes, list):
            notes = []
        notes.append({"date": _today(), "text": text})
        it["notes"] = notes
        _write_raw(_stamp(data))
    return True, {"id": target, "note_n": len(notes)}


def mark_promoted(idea_id, task_no):
    """转成任务成功后回写: status = 已转出, linked_task = 任务号。

    **由服务端在任务创建成功之后调用**(§7.1 的顺序要求), 本函数只碰 ideas.json ——
    跨文件那一步在接口层, 因为两个文件各有各的锁, 本来就做不到事务。
    两者在同一把锁里一起写: §2.4 那条"已转出与 linked_task 必须同时成立"才不会破。
    """
    target = str(idea_id or "").strip()
    task_no = str(task_no or "").strip()
    if not target or not task_no:
        return False, "缺少灵感编号或任务号"

    with _FILE_LOCK:
        data = _read_raw()
        it = None
        for cand in data["ideas"]:
            if str(cand.get("id", "")).strip() == target:
                it = cand
                break
        if it is None:
            return False, f"灵感 {target} 不存在"
        it["status"] = "已转出"
        it["linked_task"] = task_no
        _write_raw(_stamp(data))
    return True, {"id": target, "linked_task": task_no}


def unlink_idea(idea_id, status="设计中"):
    """解除与任务的关联: 清掉 linked_task, **并把状态一起退回**(默认"设计中")。

    为什么连状态一起退: §2.4 要求"已转出 ⇒ linked_task 存在"。只清关联不改状态,
    就正好造出那个悬空状态 —— 而它在页面上看不出来(§7.1 要防的是同一类问题)。
    这一步是**用户明确点的**, 不是系统自动做的: 任务被删时系统什么都不动(§7.6)。
    """
    target = str(idea_id or "").strip()
    st = str(status or "").strip() or "设计中"
    if st == "已转出" or not is_idea_status(st):
        return False, f"退回的状态不合法: {st}"

    with _FILE_LOCK:
        data = _read_raw()
        it = None
        for cand in data["ideas"]:
            if str(cand.get("id", "")).strip() == target:
                it = cand
                break
        if it is None:
            return False, f"灵感 {target} 不存在"
        it.pop("linked_task", None)
        it["status"] = st
        _write_raw(_stamp(data))
    return True, {"id": target, "status": st}


def delete_idea(idea_id):
    """删除一条。**不可恢复**, 与删除任务同一处理(§5.4)。"""
    target = str(idea_id or "").strip()
    if not target:
        return False, "缺少灵感编号"
    with _FILE_LOCK:
        data = _read_raw()
        keep = [x for x in data["ideas"]
                if str(x.get("id", "")).strip() != target]
        if len(keep) == len(data["ideas"]):
            return False, f"灵感 {target} 不存在"
        data["ideas"] = keep
        _write_raw(_stamp(data))
    return True, {"id": target}


def ensure_store():
    """确保文件存在(首次运行)。已存在则不动它。"""
    if os.path.exists(IDEAS_JSON):
        return False
    with _FILE_LOCK:
        _write_raw(_stamp({"meta": {}, "ideas": []}))
    return True
