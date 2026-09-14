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
# 模板注入辅助
# ---------------------------------------------------------------------------
def js(obj):
    """序列化为可安全嵌入 <script> 的 JSON(转义 </ 防止提前闭合脚本标签)。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
