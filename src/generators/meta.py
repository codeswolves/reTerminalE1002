"""
meta.py
分类 / 优先级 / 状态 / 节点类型 的统一定义, 供各生成器与 HTTP 服务共享。

改动这里即可全局生效。此前同一份清单在 4 个文件里各维护一份, 曾因为
generate_task_flow.py 的 CATEGORY_ORDER 缺 "管理", 导致该分类的任务
在流程页静默消失(项目页却正常显示)。
"""

import json

# ---------------------------------------------------------------------------
# 任务/项目分类
# ---------------------------------------------------------------------------
# 展示顺序。数据里出现但未列在这里的分类不会被丢弃: order_categories() 会把
# 它们追加到末尾, 各页面也都有"按实际数据动态收集"的兜底。
CATEGORY_ORDER = ["科研", "工程", "标准", "专利", "个人", "管理"]

CATEGORY_ICON = {
    "科研": "🔬", "工程": "🔧", "标准": "📐",
    "专利": "💡", "个人": "👤", "管理": "📋",
}

CATEGORY_COLOR = {
    "工程": "#3b6fb0", "标准": "#7c6bc4", "科研": "#2e9e5b",
    "专利": "#d29922", "个人": "#5a6577", "管理": "#d6453d",
}

DEFAULT_CATEGORY = "个人"
CATEGORY_FALLBACK_ICON = "📁"
CATEGORY_FALLBACK_COLOR = "#5a6577"


def order_categories(cats):
    """按预设顺序排列分类; 未预设的追加到末尾(按名称排序)。"""
    known = [c for c in CATEGORY_ORDER if c in cats]
    unknown = sorted(c for c in cats if c not in CATEGORY_ORDER)
    return known + unknown


def collect_categories(items, key="category"):
    """从数据里收集实际出现的分类(已排序), 用于不依赖白名单渲染。"""
    cats = {(it.get(key) or "").strip() for it in items}
    cats.discard("")
    return order_categories(cats)


# ---------------------------------------------------------------------------
# 优先级
# ---------------------------------------------------------------------------
PRIORITY_ORDER = ["high", "medium", "low"]

PRIORITY_META = {
    "high": {"label": "高优先级", "short": "高", "color": "#d6453d", "bg": "#fdeceb"},
    "medium": {"label": "中优先级", "short": "中", "color": "#3b6fb0", "bg": "#e8eef8"},
    "low": {"label": "低优先级", "short": "低", "color": "#2e9e5b", "bg": "#e7f4ec"},
}

DEFAULT_PRIORITY = "medium"


def priority_meta(key):
    """取优先级的展示信息; 未知或缺失时回退到默认优先级。"""
    return PRIORITY_META.get(str(key or "").strip().lower(), PRIORITY_META[DEFAULT_PRIORITY])


# ---------------------------------------------------------------------------
# 任务状态
# ---------------------------------------------------------------------------
STATUS_ORDER = ["未开始", "进行中", "已完成", "已暂停", "已取消"]

STATUS_META = {
    "未开始": {"icon": "○", "color": "#8893a7"},
    "进行中": {"icon": "⏳", "color": "#d29922"},
    "已完成": {"icon": "✅", "color": "#2e9e5b"},
    "已暂停": {"icon": "⏸️", "color": "#7c6bc4"},
    "已取消": {"icon": "❌", "color": "#999999"},
}


# ---------------------------------------------------------------------------
# 项目节点类型
# ---------------------------------------------------------------------------
# project 是根节点专属, 不允许在页面上新建; end 为项目结束节点
KIND_META = {
    "project": {"label": "项目", "color": "#3b6fb0"},
    "milestone": {"label": "里程碑", "color": "#d29922"},
    "task": {"label": "任务", "color": "#7c6bc4"},
    "deliverable": {"label": "交付物", "color": "#2e9e5b"},
    "end": {"label": "结束节点", "color": "#d6453d"},
}

# 页面上可选的节点类型(不含根节点专属的 project)
KIND_CHOICES = ["milestone", "task", "deliverable", "end"]

DEFAULT_KIND = "milestone"


# ---------------------------------------------------------------------------
# 时间管理四象限
# ---------------------------------------------------------------------------
# A 重要且紧迫 / B 重要不紧迫 / C 紧迫不重要 / D 不重要不紧迫
# min / max 是目标时间占比(%), 下界之和 = 100% 构成精确可行解, 上界之和 = 120% 不可同时达到。
# 详见 docs/design/time-quadrant-design.md §1.2 / §3.2
QUADRANT_ORDER = ["A", "B", "C", "D"]

QUADRANT_META = {
    "A": {"label": "重要且紧迫", "action": "马上做", "color": "#d6453d", "bg": "#fdeceb",
          "min": 20, "max": 25, "hint": "救火有成本上限, 超过即说明预防不足"},
    "B": {"label": "重要不紧迫", "action": "计划做", "color": "#3b6fb0", "bg": "#e8eef8",
          "min": 65, "max": 80, "hint": "主战场, 长期价值全部来自这里"},
    "C": {"label": "紧迫不重要", "action": "快速做", "color": "#d29922", "bg": "#fef8e8",
          "min": 0, "max": 15, "hint": "单值 15%, 按上限处理"},
    "D": {"label": "不重要不紧迫", "action": "看情况做", "color": "#8893a7", "bg": "#f0f2f5",
          "min": 0, "max": 0, "hint": "不专门安排时间"},
}


def quadrant_meta(key):
    """取象限展示信息; 未标记或取值非法时返回 None(表示未归类)。"""
    return QUADRANT_META.get(str(key or "").strip().upper())


def is_quadrant(key):
    """取值是否是合法象限。"""
    return str(key or "").strip().upper() in QUADRANT_META


# ---------------------------------------------------------------------------
# 每日时间预算 (docs/design/time-quadrant-design.md §1.3)
# ---------------------------------------------------------------------------
# 机动时间在分母之外: 把它算进分母等于预先给"未知"分配了确定的时间
DAY_HOURS = 8            # 每天毛可用时间
DAY_BUFFER_H = 1         # 每天机动预留(应对突发, 不参与象限分配)
DAY_PLAN_H = DAY_HOURS - DAY_BUFFER_H          # 每天净可安排 = 7
PLAN_DAYS_PER_WEEK = 5   # 每周安排天数(默认工作日)
WEEK_PLAN_H = DAY_PLAN_H * PLAN_DAYS_PER_WEEK  # 每周净可安排 = 35


# ---------------------------------------------------------------------------
# 任务卡点类型 (任务后评估用, docs/design/time-quadrant-design.md §2.9.4)
# ---------------------------------------------------------------------------
# 必须归类而非自由文本: 否则既不能统计("最常因为什么卡住")也不能反哺配额调整
BLOCKER_ORDER = ["需求不清", "依赖他人", "技术难点", "返工", "被打断", "精力不足", "外部阻塞", "估算失误"]

BLOCKER_META = {
    "需求不清": {"color": "#d29922", "hint": "目标或验收标准一开始就不明确"},
    "依赖他人": {"color": "#3b6fb0", "hint": "等回复、等评审、等他人产出"},
    "技术难点": {"color": "#7c6bc4", "hint": "确实需要攻关"},
    "返工": {"color": "#d6453d", "hint": "做完了才发现方向错"},
    "被打断": {"color": "#d29922", "hint": "突发事项 / 会议 / 他人请求"},
    "精力不足": {"color": "#5a6577", "hint": "状态差、拖延"},
    "外部阻塞": {"color": "#8893a7", "hint": "设备、数据、权限等"},
    "估算失误": {"color": "#2e9e5b", "hint": "任务本身没问题, 是估时偏了"},
}


def blocker_meta(key):
    """取卡点展示信息; 未知取值回退到灰色, 不丢弃数据。"""
    return BLOCKER_META.get(str(key or "").strip(), {"color": "#8893a7", "hint": ""})


# ---------------------------------------------------------------------------
# 模板注入辅助
# ---------------------------------------------------------------------------
def js(obj):
    """序列化为可安全嵌入 <script> 的 JSON(转义 </ 防止提前闭合脚本标签)。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
