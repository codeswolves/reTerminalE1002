"""
generate_dashboard.py
生成 reTerminal 用的 800x480 仪表盘 HTML。
结构完全对齐 E:/WorkBuddy/design/dashboard.html 模板。
支持多主题换肤 (--style)。
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, date

# ----------------------------------------------------------------------------
# 路径
# ----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(OUT_DIR, "dashboard.html")

# ----------------------------------------------------------------------------
# 主题：default 完全对齐模板配色
# ----------------------------------------------------------------------------
THEMES = {
    "default": {
        "page_bg": "#0f1115", "dash_bg": "#1a1d23", "dash_border": "#2d323d",
        "topbar_bg": "#21252e", "topbar_border": "#2d323d",
        "date_color": "#cbd5e1", "slogan_color": "#f3f4f6", "weather_color": "#9ca3af",
        "panel_bg": "#21252e", "panel_border": "#2d323d",
        "panel_title_color": "#f3f4f6", "panel_title_size": "14px",
        "ring1_color": "#60a5fa", "ring2_color": "#f87171", "ring3_color": "#4ade80",
        "ring_track": "#2d323d", "ring_text": "#ffffff",
        "legend_name": "#cbd5e1",
        "task_name_color": "#cbd5e1", "task_val_color": "#f3f4f6",
        "bar_bg": "#2d323d",
        # 三个任务的昨天/今天色（实色 + 半透明）
        "task_colors": [
            ("#60a5fa", "rgba(96,165,250,0.35)"),
            ("#f87171", "rgba(248,113,113,0.35)"),
            ("#4ade80", "rgba(74,222,128,0.35)"),
        ],
        "task_legend_lbl": "#cbd5e1", "task_legend_dim": "#9ca3af",
        "cal_head_color": "#6b7280",
        "cell_bg": "#2a2f3a", "cell_color": "#9ca3af",
        "cell_done_bg": "rgba(74, 222, 128, 0.18)", "cell_done_color": "#4ade80",
        "cell_today_bg": "#fbbf24", "cell_today_color": "#1a1d23",
        "cal_date_color": "#9ca3af", "cal_legend_color": "#9ca3af",
    },
    "cyberpunk": {
        "page_bg": "#0a0014", "dash_bg": "#1a0033", "dash_border": "#ff2ec4",
        "topbar_bg": "#2a0a4a", "topbar_border": "#ff2ec4",
        "date_color": "#00f0ff", "slogan_color": "#ff2ec4", "weather_color": "#00f0ff",
        "panel_bg": "#2a0a4a", "panel_border": "#ff2ec4",
        "panel_title_color": "#00f0ff", "panel_title_size": "14px",
        "ring1_color": "#00f0ff", "ring2_color": "#ff2ec4", "ring3_color": "#ffe600",
        "ring_track": "#3a1060", "ring_text": "#00f0ff",
        "legend_name": "#ff8df0",
        "task_name_color": "#00f0ff", "task_val_color": "#ffe600",
        "bar_bg": "#3a1060",
        "task_colors": [
            ("#00f0ff", "rgba(0,240,255,0.35)"),
            ("#ff2ec4", "rgba(255,46,196,0.35)"),
            ("#ffe600", "rgba(255,230,0,0.35)"),
        ],
        "task_legend_lbl": "#00f0ff", "task_legend_dim": "#ff2ec4",
        "cal_head_color": "#ff2ec4",
        "cell_bg": "#3a1060", "cell_color": "#00f0ff",
        "cell_done_bg": "rgba(0,240,255,0.18)", "cell_done_color": "#00f0ff",
        "cell_today_bg": "#ffe600", "cell_today_color": "#1a0033",
        "cal_date_color": "#ff2ec4", "cal_legend_color": "#ff2ec4",
    },
    "dracula": {
        "page_bg": "#21222c", "dash_bg": "#282a36", "dash_border": "#44475a",
        "topbar_bg": "#343746", "topbar_border": "#44475a",
        "date_color": "#f8f8f2", "slogan_color": "#bd93f9", "weather_color": "#6272a4",
        "panel_bg": "#343746", "panel_border": "#44475a",
        "panel_title_color": "#f8f8f2", "panel_title_size": "14px",
        "ring1_color": "#bd93f9", "ring2_color": "#ff79c6", "ring3_color": "#50fa7b",
        "ring_track": "#44475a", "ring_text": "#f8f8f2",
        "legend_name": "#f8f8f2",
        "task_name_color": "#f8f8f2", "task_val_color": "#bd93f9",
        "bar_bg": "#44475a",
        "task_colors": [
            ("#bd93f9", "rgba(189,147,249,0.35)"),
            ("#ff79c6", "rgba(255,121,198,0.35)"),
            ("#50fa7b", "rgba(80,250,123,0.35)"),
        ],
        "task_legend_lbl": "#f8f8f2", "task_legend_dim": "#6272a4",
        "cal_head_color": "#6272a4",
        "cell_bg": "#44475a", "cell_color": "#f8f8f2",
        "cell_done_bg": "rgba(80,250,123,0.18)", "cell_done_color": "#50fa7b",
        "cell_today_bg": "#ffb86c", "cell_today_color": "#282a36",
        "cal_date_color": "#6272a4", "cal_legend_color": "#6272a4",
    },
    "fui": {
        "page_bg": "#010409", "dash_bg": "#0d1117", "dash_border": "#1f6feb",
        "topbar_bg": "#161b22", "topbar_border": "#1f6feb",
        "date_color": "#58a6ff", "slogan_color": "#8b949e", "weather_color": "#8b949e",
        "panel_bg": "#161b22", "panel_border": "#1f6feb",
        "panel_title_color": "#e6edf3", "panel_title_size": "14px",
        "ring1_color": "#58a6ff", "ring2_color": "#f85149", "ring3_color": "#3fb950",
        "ring_track": "#21262d", "ring_text": "#e6edf3",
        "legend_name": "#8b949e",
        "task_name_color": "#e6edf3", "task_val_color": "#58a6ff",
        "bar_bg": "#21262d",
        "task_colors": [
            ("#58a6ff", "rgba(88,166,255,0.35)"),
            ("#f85149", "rgba(248,81,73,0.35)"),
            ("#3fb950", "rgba(63,185,80,0.35)"),
        ],
        "task_legend_lbl": "#e6edf3", "task_legend_dim": "#8b949e",
        "cal_head_color": "#8b949e",
        "cell_bg": "#21262d", "cell_color": "#e6edf3",
        "cell_done_bg": "rgba(63,185,80,0.18)", "cell_done_color": "#3fb950",
        "cell_today_bg": "#d29922", "cell_today_color": "#0d1117",
        "cal_date_color": "#8b949e", "cal_legend_color": "#8b949e",
    },
    "light": {
        "page_bg": "#f5f6f8", "dash_bg": "#ffffff", "dash_border": "#d0d6e0",
        "topbar_bg": "#f0f2f7", "topbar_border": "#d0d6e0",
        "date_color": "#5a6577", "slogan_color": "#1f2733", "weather_color": "#8893a7",
        "panel_bg": "#f0f2f7", "panel_border": "#d0d6e0",
        "panel_title_color": "#1f2733", "panel_title_size": "14px",
        "ring1_color": "#3b6fb0", "ring2_color": "#d6453d", "ring3_color": "#2e9e5b",
        "ring_track": "#d0d6e0", "ring_text": "#1f2733",
        "legend_name": "#5a6577",
        "task_name_color": "#3a4456", "task_val_color": "#1f2733",
        "bar_bg": "#e3e8f0",
        "task_colors": [
            ("#3b6fb0", "rgba(59,111,176,0.35)"),
            ("#d6453d", "rgba(214,69,61,0.35)"),
            ("#2e9e5b", "rgba(46,158,91,0.35)"),
        ],
        "task_legend_lbl": "#3a4456", "task_legend_dim": "#8893a7",
        "cal_head_color": "#8893a7",
        "cell_bg": "#e3e8f0", "cell_color": "#3a4456",
        "cell_done_bg": "rgba(46,158,91,0.18)", "cell_done_color": "#2e9e5b",
        "cell_today_bg": "#d29922", "cell_today_color": "#ffffff",
        "cal_date_color": "#8893a7", "cal_legend_color": "#8893a7",
    },
    "macaron": {
        "page_bg": "#fff5f7", "dash_bg": "#fff0f5", "dash_border": "#ffc2d4",
        "topbar_bg": "#ffe9f0", "topbar_border": "#ffc2d4",
        "date_color": "#7a4a5e", "slogan_color": "#c98aa0", "weather_color": "#c98aa0",
        "panel_bg": "#fff0f5", "panel_border": "#ffc2d4",
        "panel_title_color": "#7a4a5e", "panel_title_size": "14px",
        "ring1_color": "#ffb3c6", "ring2_color": "#ffd6a5", "ring3_color": "#a0e7a0",
        "ring_track": "#ffe1ea", "ring_text": "#7a4a5e",
        "legend_name": "#9a6075",
        "task_name_color": "#7a4a5e", "task_val_color": "#c98aa0",
        "bar_bg": "#ffe1ea",
        "task_colors": [
            ("#ffb3c6", "rgba(255,179,198,0.35)"),
            ("#ffd6a5", "rgba(255,214,165,0.35)"),
            ("#a0e7a0", "rgba(160,231,160,0.35)"),
        ],
        "task_legend_lbl": "#7a4a5e", "task_legend_dim": "#c98aa0",
        "cal_head_color": "#c98aa0",
        "cell_bg": "#ffe1ea", "cell_color": "#7a4a5e",
        "cell_done_bg": "rgba(160,231,160,0.25)", "cell_done_color": "#5fbf5f",
        "cell_today_bg": "#ffd6a5", "cell_today_color": "#7a4a5e",
        "cal_date_color": "#c98aa0", "cal_legend_color": "#c98aa0",
    },
    "morandi": {
        "page_bg": "#e8e4df", "dash_bg": "#dedad3", "dash_border": "#c4bdb4",
        "topbar_bg": "#dcd8d2", "topbar_border": "#c4bdb4",
        "date_color": "#5c564e", "slogan_color": "#8a8377", "weather_color": "#9a9388",
        "panel_bg": "#dedad3", "panel_border": "#c4bdb4",
        "panel_title_color": "#5c564e", "panel_title_size": "14px",
        "ring1_color": "#a3b1a1", "ring2_color": "#b09294", "ring3_color": "#c2b0a3",
        "ring_track": "#c4bdb4", "ring_text": "#5c564e",
        "legend_name": "#6f675c",
        "task_name_color": "#5c564e", "task_val_color": "#8a8377",
        "bar_bg": "#cfc9c0",
        "task_colors": [
            ("#a3b1a1", "rgba(163,177,161,0.35)"),
            ("#b09294", "rgba(176,146,148,0.35)"),
            ("#c2b0a3", "rgba(194,176,163,0.35)"),
        ],
        "task_legend_lbl": "#5c564e", "task_legend_dim": "#9a9388",
        "cal_head_color": "#9a9388",
        "cell_bg": "#cfc9c0", "cell_color": "#5c564e",
        "cell_done_bg": "rgba(163,177,161,0.25)", "cell_done_color": "#7e9b7c",
        "cell_today_bg": "#d6a85e", "cell_today_color": "#5c564e",
        "cal_date_color": "#9a9388", "cal_legend_color": "#9a9388",
    },
    "pixel": {
        "page_bg": "#1a1a2e", "dash_bg": "#2d2d44", "dash_border": "#ffd93d",
        "topbar_bg": "#3d3d5c", "topbar_border": "#ffd93d",
        "date_color": "#ffd93d", "slogan_color": "#6bcb77", "weather_color": "#6bcb77",
        "panel_bg": "#3d3d5c", "panel_border": "#ffd93d",
        "panel_title_color": "#ffd93d", "panel_title_size": "14px",
        "ring1_color": "#ff6b6b", "ring2_color": "#4d96ff", "ring3_color": "#6bcb77",
        "ring_track": "#4a4a6a", "ring_text": "#ffd93d",
        "legend_name": "#a8e6cf",
        "task_name_color": "#ffd93d", "task_val_color": "#6bcb77",
        "bar_bg": "#4a4a6a",
        "task_colors": [
            ("#ff6b6b", "rgba(255,107,107,0.35)"),
            ("#4d96ff", "rgba(77,150,255,0.35)"),
            ("#6bcb77", "rgba(107,203,119,0.35)"),
        ],
        "task_legend_lbl": "#ffd93d", "task_legend_dim": "#6bcb77",
        "cal_head_color": "#6bcb77",
        "cell_bg": "#4a4a6a", "cell_color": "#ffd93d",
        "cell_done_bg": "rgba(107,203,119,0.25)", "cell_done_color": "#6bcb77",
        "cell_today_bg": "#ff6b6b", "cell_today_color": "#2d2d44",
        "cal_date_color": "#6bcb77", "cal_legend_color": "#6bcb77",
    },
    "tactical": {
        "page_bg": "#080a08", "dash_bg": "#0c0f0c", "dash_border": "#3a5a3a",
        "topbar_bg": "#142014", "topbar_border": "#3a5a3a",
        "date_color": "#9bbf7a", "slogan_color": "#6a8a5a", "weather_color": "#6a8a5a",
        "panel_bg": "#142014", "panel_border": "#3a5a3a",
        "panel_title_color": "#cfe8c0", "panel_title_size": "14px",
        "ring1_color": "#7faf5f", "ring2_color": "#c75a5a", "ring3_color": "#c7a35a",
        "ring_track": "#1c2a1c", "ring_text": "#cfe8c0",
        "legend_name": "#a8c890",
        "task_name_color": "#cfe8c0", "task_val_color": "#9bbf7a",
        "bar_bg": "#1c2a1c",
        "task_colors": [
            ("#7faf5f", "rgba(127,175,95,0.35)"),
            ("#c75a5a", "rgba(199,90,90,0.35)"),
            ("#c7a35a", "rgba(199,163,90,0.35)"),
        ],
        "task_legend_lbl": "#cfe8c0", "task_legend_dim": "#6a8a5a",
        "cal_head_color": "#6a8a5a",
        "cell_bg": "#1c2a1c", "cell_color": "#cfe8c0",
        "cell_done_bg": "rgba(127,175,95,0.25)", "cell_done_color": "#7faf5f",
        "cell_today_bg": "#c7a35a", "cell_today_color": "#0c0f0c",
        "cal_date_color": "#6a8a5a", "cal_legend_color": "#6a8a5a",
    },
}
DEFAULT_STYLE = "light"


# ----------------------------------------------------------------------------
# 天气
# ----------------------------------------------------------------------------

# 简化 SVG 图标（16x16, viewBox 0 0 16 16）
SVG_ICONS = {
    "sun": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="4" fill="#fbbf24"/><g stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round"><line x1="8" y1="0.5" x2="8" y2="2.5"/><line x1="8" y1="13.5" x2="8" y2="15.5"/><line x1="0.5" y1="8" x2="2.5" y2="8"/><line x1="13.5" y1="8" x2="15.5" y2="8"/><line x1="2.5" y1="2.5" x2="3.9" y2="3.9"/><line x1="12.1" y1="12.1" x2="13.5" y2="13.5"/><line x1="13.5" y1="2.5" x2="12.1" y2="3.9"/><line x1="3.9" y1="12.1" x2="2.5" y2="13.5"/></g></svg>',
    "cloud-sun": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="5" cy="5" r="2.5" fill="#fbbf24"/><path d="M5 11 a3 3 0 1 1 5.5 -1.5 h0.5 a2 2 0 1 1 0 4 H5 a2.5 2.5 0 0 1 0 -2.5z" fill="#9ca3af"/></svg>',
    "cloud": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 11 a3 3 0 1 1 5.5 -1.5 h0.5 a2 2 0 1 1 0 4 H5 a2.5 2.5 0 0 1 0 -2.5z" fill="#9ca3af"/></svg>',
    "cloud-rain": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 8 a3 3 0 1 1 5.5 -1.5 h0.5 a2 2 0 1 1 0 4 H4 a2.5 2.5 0 0 1 0 -2.5z" fill="#9ca3af"/><g stroke="#60a5fa" stroke-width="1.2" stroke-linecap="round"><line x1="6" y1="12" x2="5.5" y2="14.5"/><line x1="9" y1="12" x2="8.5" y2="14.5"/><line x1="12" y1="12" x2="11.5" y2="14.5"/></g></svg>',
    "fog": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><g stroke="#9ca3af" stroke-width="1.3" stroke-linecap="round"><line x1="2" y1="5" x2="14" y2="5"/><line x1="3" y1="8" x2="13" y2="8"/><line x1="2" y1="11" x2="14" y2="11"/></g></svg>',
    "snow": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 7 a3 3 0 1 1 5.5 -1.5 h0.5 a2 2 0 1 1 0 4 H4 a2.5 2.5 0 0 1 0 -2.5z" fill="#dbe4f0"/><g stroke="#dbe4f0" stroke-width="1" stroke-linecap="round"><line x1="6" y1="12" x2="6" y2="14.5"/><line x1="9" y1="12" x2="9" y2="14.5"/><line x1="12" y1="12" x2="12" y2="14.5"/></g></svg>',
    "cloud-bolt": '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 7 a3 3 0 1 1 5.5 -1.5 h0.5 a2 2 0 1 1 0 4 H4 a2.5 2.5 0 0 1 0 -2.5z" fill="#6b7280"/><path d="M8 9 L6 13 L8 13 L7 15.5 L11 11 L9 11 L10 9 Z" fill="#fbbf24"/></svg>',
}


# WMO 天气代码 -> (中文描述, 图标key)
WMO_CODE_MAP = {
    0: ("晴", "sun"), 1: ("晴", "cloud-sun"), 2: ("少云", "cloud-sun"), 3: ("多云", "cloud"),
    45: ("雾", "fog"), 48: ("雾凇", "fog"),
    51: ("毛毛雨", "cloud-rain"), 53: ("毛毛雨", "cloud-rain"), 55: ("毛毛雨", "cloud-rain"),
    56: ("冻毛毛雨", "cloud-rain"), 57: ("冻毛毛雨", "cloud-rain"),
    61: ("小雨", "cloud-rain"), 63: ("中雨", "cloud-rain"), 65: ("大雨", "cloud-rain"),
    66: ("冻雨", "cloud-rain"), 67: ("冻雨", "cloud-rain"),
    71: ("小雪", "snow"), 73: ("中雪", "snow"), 75: ("大雪", "snow"), 77: ("雪粒", "snow"),
    80: ("阵雨", "cloud-rain"), 81: ("阵雨", "cloud-rain"), 82: ("强阵雨", "cloud-rain"),
    85: ("阵雪", "snow"), 86: ("强阵雪", "snow"),
    95: ("雷阵雨", "cloud-bolt"), 96: ("雷阵雨伴冰雹", "cloud-bolt"), 99: ("雷阵雨伴冰雹", "cloud-bolt"),
}

# 北京固定经纬度
BEIJING_LAT, BEIJING_LON = 39.9042, 116.4074


def fetch_weather(city="Beijing"):
    """固定查询北京天气（open-meteo，无需 API key，纯气象数据）。"""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={BEIJING_LAT}&longitude={BEIJING_LON}"
            f"&current=temperature_2m,weather_code"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = data["current"]
        temp = round(float(cur["temperature_2m"]))
        code = int(cur["weather_code"])
        zh, icon_key = WMO_CODE_MAP.get(code, ("未知", "cloud"))
        icon = SVG_ICONS.get(icon_key, SVG_ICONS["cloud"])
        return {"text": f"北京 {temp}°C {zh}", "icon": icon}
    except Exception:
        return {"text": "北京 --°C 未知", "icon": SVG_ICONS["cloud"]}


# ----------------------------------------------------------------------------
# 数据读取
# ----------------------------------------------------------------------------
def read_csv_dicts(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _norm_date(s):
    """日期归一化: 兼容 2026/8/2、2026-08-01 等格式 -> 2026-08-02"""
    s = (s or "").strip().replace("/", "-")
    parts = s.split("-")
    if len(parts) == 3:
        try:
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        except ValueError:
            pass
    return s


def get_weight_info(target_date):
    rows = read_csv_dicts(os.path.join(DATA_DIR, "weight.csv"))
    if not rows:
        return {"percent": 0, "label": "减重40斤"}
    rows.sort(key=lambda r: _norm_date(r.get("date")))
    start = float(rows[0]["weight"])
    current = float(rows[-1]["weight"])
    target_loss = 40.0  # 减重 40 斤 = 20kg
    done_loss = (start - current) * 2  # kg -> 斤
    percent = max(0, min(100, int(done_loss / target_loss * 100))) if target_loss > 0 else 0
    return {"percent": percent, "label": "减重40斤"}


def get_goals_info():
    rows = read_csv_dicts(os.path.join(DATA_DIR, "goals.csv"))
    g = {r["goal"]: r for r in rows}
    out = {}
    for key, label in (("paper", "论文3篇"), ("patent", "专利3篇")):
        if key in g:
            t = int(g[key]["target"]); d = int(g[key]["done"])
            out[key] = {"target": t, "done": d, "label": label,
                        "percent": max(0, min(100, int(d / t * 100))) if t else 0}
        else:
            out[key] = {"target": 0, "done": 0, "label": label, "percent": 0}
    return out


def get_fitness_info(target_date):
    rows = read_csv_dicts(os.path.join(DATA_DIR, "fitness.csv"))
    row = next((r for r in rows if _norm_date(r.get("date")) == target_date), None)
    if not row:
        rows.sort(key=lambda r: _norm_date(r.get("date")))
        row = rows[-1] if rows else {"checkin": "0", "content": "", "yesterday": "0", "today": "0"}
    return {
        "checkin": row.get("checkin", "0") == "1",
        "content": row.get("content", ""),
        "yesterday": float(row.get("yesterday", "0") or 0),
        "today": float(row.get("today", "0") or 0),
        "date": row.get("date", target_date),
    }


def get_tasks_info(target_date):
    rows = read_csv_dicts(os.path.join(DATA_DIR, "tasks.csv"))
    # 过滤空行
    rows = [r for r in rows if (r.get("task_name") or "").strip()]
    # 统计全年完成数量（所有日期，today progress 为 100% 的任务）
    completed_count = 0
    for r in rows:
        try:
            if int(float(r.get("today progress") or 0)) == 100:
                completed_count += 1
        except (ValueError, TypeError):
            pass
    if not rows:
        return {"tasks": [], "completed_count": 0}
    # 按任务编号去重，保留最新日期记录
    task_map = {}
    for r in rows:
        no = r.get("No.", "").strip()
        d = _norm_date(r.get("date"))
        if no not in task_map or d > task_map[no][1]:
            try:
                yp = int(float(r.get("yesterday progress") or 0))
            except (ValueError, TypeError):
                yp = 0
            try:
                tp = int(float(r.get("today progress") or 0))
            except (ValueError, TypeError):
                tp = 0
            task_map[no] = (r, d, yp, tp)
    tasks = []
    for r, _, yp, tp in task_map.values():
        if (r.get("finished") or "").strip().lower() == "yes":
            continue
        tasks.append({"name": r.get("task_name", ""), "progress": tp,
                      "yesterday_progress": yp, "today_progress": tp,
                      "priority": r.get("priority", "medium")})
    return {"tasks": tasks, "completed_count": completed_count}


def get_slogan_info():
    """读取 data/slogan.csv 中的口号。

    约定：slogan.csv 为历史记录格式，最新口号追加在文件末尾，
    本函数取最后一个非空行作为当前口号，
    文件缺失或内容为空时回退默认口号。
    """
    default_slogan = "日日精进 · 知行合一"
    rows = read_csv_dicts(os.path.join(DATA_DIR, "slogan.csv"))
    last_text = ""
    for r in rows:
        text = (r.get("slogan") or "").strip()
        if text:
            last_text = text
    return last_text or default_slogan


# ----------------------------------------------------------------------------
# 三环同心仪表盘（单个 SVG，对齐模板结构）
# ----------------------------------------------------------------------------
def build_gauge_svg(weight_info, goals, theme):
    import math
    # 三环：r=92/58/24, stroke-width=20, rotate(-120 105 105)
    rings = [
        (92, weight_info["percent"], theme["ring1_color"]),
        (58, goals["paper"]["percent"], theme["ring2_color"]),
        (24, goals["patent"]["percent"], theme["ring3_color"]),
    ]
    track = theme["ring_track"]
    # 百分比文字 y 坐标（贴在环顶部起笔处）
    text_y = [13, 47, 81]

    circles = ""
    for i, (r, pct, color) in enumerate(rings):
        circ = 2 * math.pi * r
        dash = circ * pct / 100.0
        circles += f'<circle cx="105" cy="105" r="{r}" fill="none" stroke="{track}" stroke-width="20"/>'
        circles += f'<circle cx="105" cy="105" r="{r}" fill="none" stroke="{color}" stroke-width="20" stroke-linecap="round" stroke-dasharray="{dash:.2f} {circ:.2f}"/>'

    texts = ""
    for i, (r, pct, color) in enumerate(rings):
        texts += f'<text x="105" y="{text_y[i]}" text-anchor="middle" dominant-baseline="middle" fill="{theme["ring_text"]}" font-size="14" font-weight="700">{pct}%</text>'

    return f'''<svg viewBox="0 0 210 210" width="300" height="300" role="img" aria-label="三环进度仪表盘">
            <title>2026年目标三环进度</title>
            <g transform="rotate(-120 105 105)">
              {circles}
            </g>
            {texts}
          </svg>'''


def build_legend(weight_info, goals, theme):
    rows = [
        (theme["ring1_color"], weight_info["label"], weight_info["percent"]),
        (theme["ring2_color"], goals["paper"]["label"], goals["paper"]["percent"]),
        (theme["ring3_color"], goals["patent"]["label"], goals["patent"]["percent"]),
    ]
    items = ""
    for color, name, pct in rows:
        items += f'<div class="legend-row"><span class="dot" style="background:{color}"></span><span class="lg-name">{name}</span><span class="lg-pct" style="color:{color}">{pct}%</span></div>'
    return f'<div class="legend">{items}</div>'


# ----------------------------------------------------------------------------
# 任务面板（双段进度条，对齐模板结构）
# ----------------------------------------------------------------------------
def build_tasks_panel(tasks_info, theme):
    """模板结构：每个 task 一个 .task > .task-head(名称+总%) + .bar(seg昨天+seg今天)"""
    # 全年完成计数
    completed_count = tasks_info.get("completed_count", 0)
    # 按优先级排序后取前3条：high > medium > low
    prio_order = {"high": 0, "medium": 1, "low": 2}
    tasks = sorted(tasks_info["tasks"], key=lambda t: prio_order.get(t.get("priority", "medium"), 1))
    tasks = tasks[:3]
    task_html = ""
    for i, task in enumerate(tasks):
        solid, half = theme["task_colors"][i % len(theme["task_colors"])]
        total = task["progress"]
        y_seg = task["yesterday_progress"]
        t_seg = max(0, task["today_progress"] - task["yesterday_progress"])
        task_html += f'''<div class="task">
          <div class="task-head"><span style="color:{theme["task_name_color"]}">{task["name"]}</span><span class="task-val" style="color:{theme["task_val_color"]}">{total}%</span></div>
          <div class="bar">
            <div class="seg" style="width:{y_seg:.0f}%;background:{solid}"></div>
            <div class="seg" style="width:{t_seg:.0f}%;background:{half}"></div>
          </div>
        </div>'''

    # 底部图例：昨天完成 + 今天推进
    sws_y = "".join(f'<i class="sw" style="background:{c[0]}"></i>' for c in theme["task_colors"])
    sws_t = "".join(f'<i class="sw" style="background:{c[1]}"></i>' for c in theme["task_colors"])
    legend = f'''<div class="task-legend">
        <span class="lbl" style="color:{theme["task_legend_lbl"]}">昨天完成</span>
        <span class="sws">{sws_y}</span>
        <span class="lbl" style="color:{theme["task_legend_lbl"]}">今天推进</span>
        <span class="sws">{sws_t}</span>
      </div>'''

    return f'''<div class="panel tasks-panel">
        <div class="panel-title" style="color:{theme["panel_title_color"]}">每日任务<span class="task-done-count">累计完成  {completed_count}</span></div>
        {task_html}
        {legend}
      </div>'''


# ----------------------------------------------------------------------------
# 月历打卡（对齐模板结构）
# ----------------------------------------------------------------------------
def build_calendar(fitness_rows, target_date, theme):
    d = datetime.strptime(target_date, "%Y-%m-%d").date()
    year, month = d.year, d.month
    first = date(year, month, 1)
    start_weekday = first.weekday()  # 周一为0（Python date.weekday() 即周一=0..周日=6）
    if month == 12:
        ndays = (date(year + 1, 1, 1) - first).days
    else:
        ndays = (date(year, month + 1, 1) - first).days
    checked = {_norm_date(r["date"]): r.get("checkin", "0") == "1" for r in fitness_rows}
    # 累计打卡天数：初始值 + 截止今天（含）的打卡次数
    INITIAL_CHECKIN = 8
    month_checkins = sum(1 for dd, ok in checked.items() if ok and dd <= target_date)
    total_checkins = INITIAL_CHECKIN + month_checkins


    head = "".join(f'<span>{"一二三四五六日"[i]}</span>' for i in range(7))
    cells = ['<span class="cell empty"></span>' for _ in range(start_weekday)]
    for day in range(1, ndays + 1):
        dd = date(year, month, day).isoformat()
        if dd == target_date:
            cells.append(f'<span class="cell today" style="background:{theme["cell_today_bg"]};color:{theme["cell_today_color"]}">{day}</span>')
        elif checked.get(dd):
            cells.append(f'<span class="cell done" style="background:{theme["cell_done_bg"]};color:{theme["cell_done_color"]}">{day}</span>')
        else:
            cells.append(f'<span class="cell" style="background:{theme["cell_bg"]};color:{theme["cell_color"]}">{day}</span>')

    return f'''<div class="panel calendar-panel">
        <div class="cal-header">
          <span class="panel-title" style="margin:0;color:{theme["panel_title_color"]}">健身打卡</span>
          <span class="cal-stats">
            <span class="cal-stats-label">累计打卡</span>
            <span class="cal-stats-num" style="color:{theme["panel_title_color"]}">{total_checkins}</span>
            <span class="cal-stats-label">天</span>
          </span>
          <span class="cal-date">{year} 年 {month:02d} 月</span>
        </div>
        <div class="cal-grid wk">{head}</div>
        <div class="cal-grid">{"".join(cells)}</div>
        <div class="cal-legend">
          <span style="color:{theme["cal_legend_color"]}"><i class="sw" style="background:{theme["cell_today_bg"]}"></i>今天</span>
          <span style="color:{theme["cal_legend_color"]}"><i class="sw" style="background:{theme["cell_done_bg"]}"></i>已打卡</span>
        </div>
      </div>'''


# ----------------------------------------------------------------------------
# HTML 拼装
# ----------------------------------------------------------------------------
def build_html(weight_info, goals, fitness_info, tasks_info, fitness_rows,
               target_date, weather_info, style=DEFAULT_STYLE, slogan=None):
    theme = THEMES.get(style, THEMES[DEFAULT_STYLE])
    if slogan is None:
        slogan = get_slogan_info()
    d = datetime.strptime(target_date, "%Y-%m-%d")
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    date_str = f"{d.year}年{d.month}月{d.day}日 {weekdays[d.weekday()]}"
    weather = weather_info or {"text": "北京 --°C 未知", "icon": SVG_ICONS["cloud"]}

    css = f'''
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: {theme['page_bg']};
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    color: #e5e7eb;
  }}
  .dash {{
    width: 800px;
    height: 480px;
    background: {theme['dash_bg']};
    border: 1px solid {theme['dash_border']};
    border-radius: 14px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
  }}
  .topbar {{
    flex: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 16px;
    background: {theme['topbar_bg']};
    border: 1px solid {theme['topbar_border']};
    border-radius: 10px;
  }}
  .tb-date {{ font-size: 16px; color: {theme['date_color']}; }}
  .tb-slogan {{ font-size: 18px; font-weight: 600; color: {theme['slogan_color']}; letter-spacing: 1px; }}
  .tb-weather {{ display: flex; align-items: center; gap: 8px; font-size: 16px; color: {theme['weather_color']}; }}
  .content {{
    flex: 1;
    min-height: 0;
    display: flex;
    gap: 16px;
  }}
  .col-left {{ width: 340px; display: flex; flex-direction: column; }}
  .col-right {{ flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }}

  .panel {{
    background: {theme['panel_bg']};
    border: 1px solid {theme['panel_border']};
    border-radius: 10px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }}
  .panel-title {{
    font-size: {theme['panel_title_size']};
    font-weight: 600;
    color: {theme['panel_title_color']};
    margin-bottom: 3px;
    letter-spacing: 0.5px;
    flex: none;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  /* gauge */
  .gauge-panel {{ align-items: center; }}
  /*调整3个圈的位置，10px上移，4px下移*/
  .gauge-wrap {{ margin: 10px 0 4px; }} 
  /*2026年目标的图例位置调整，gap: 6px(行间距) 14px(三个图例之间的距离);*/
  .legend {{ width: 100%; display: flex; flex-direction: row; flex-wrap: wrap; justify-content: flex-start; gap: 6px 14px; margin-top: 8px; }}
  .legend-row {{
    display: flex;
    align-items: center;
    font-size: 12px;
    line-height: 1.2;
  }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; flex: none; }}
  .lg-name {{ color: {theme['legend_name']}; flex: none; }}
  .lg-pct {{ font-weight: 700; font-size: 14px; margin-left: 4px; }}

  /* tasks */
  .tasks-panel {{ flex: none; }}
  .task-done-count {{
    font-size: 11px;
    font-weight: 600;
    color: {theme['task_val_color']};
    background: {theme['bar_bg']};
    border-radius: 10px;
    padding: 1px 8px;
    line-height: 1.6;
    flex: none;
  }}
  .task {{ margin-bottom: 5px; }}
  .task:last-child {{ margin-bottom: 0; }}
  /*每日任务的字体在这里调整*/
  .task-head {{
    display: flex;
    justify-content: space-between;
    font-size: 14px;
    margin-bottom: 4px;
  }}
  .task-val {{ font-weight: 600; }}
  .bar {{
    display: flex;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
    background: {theme['bar_bg']};
  }}
  .seg {{ height: 100%; }}
  .task-legend {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 6px 16px;
    margin-top: 8px;
    font-size: 14px;
    color: {theme['task_legend_dim']};
  }}
  .task-legend .lbl {{ color: {theme['task_legend_lbl']}; }}
  .task-legend .sws {{ display: flex; gap: 5px; }}
  .task-legend span {{ display: flex; align-items: center; gap: 4px; }}
  .sw {{ width: 10px; height: 10px; border-radius: 2px; flex: none; }}

  /* calendar */
  .calendar-panel {{ flex: 1; }}
  .cal-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; }}
  .cal-date {{ font-size: 14px; color: {theme['cal_head_color']}; }}
  .cal-stats {{
    display: inline-flex;
    align-items: baseline;
    gap: 5px;
    margin-left: 8px;
  }}
  .cal-stats-num {{
    font-size: 14px;
    font-weight: 700;
    line-height: 1;
  }}
  .cal-stats-label {{
    font-size: 12px;
    color: {theme['cal_head_color']};
  }}
  .cal-grid {{
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
  }}
  /*日历的字体*/
  .cal-grid.wk {{ margin-bottom: 1px; }}
  .wk span {{
    text-align: center;
    font-size: 14px;
    color: {theme['cal_head_color']};
  }}
  .cell {{
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    line-height: 1;
    border-radius: 4px;
  }}
  .cell.empty {{ background: transparent; }}
  /*日历下面图例的字体*/
  .cal-legend {{
    display: flex;
    justify-content: center;
    gap: 14px;
    margin-top: -1px;
    font-size: 14px;
  }}
  .cal-legend span {{ display: flex; align-items: center; gap: 5px; }}
  '''

    gauge = build_gauge_svg(weight_info, goals, theme)
    legend = build_legend(weight_info, goals, theme)
    tasks_html = build_tasks_panel(tasks_info, theme)
    cal_html = build_calendar(fitness_rows, target_date, theme)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>个人仪表盘 800x480</title>
<style>{css}</style>
</head>
<body>
  <div class="dash">
    <div class="topbar">
      <div class="tb-date" id="tbDate">{date_str}</div>
      <div class="tb-slogan">{slogan}</div>
      <div class="tb-weather">
        {weather['icon']}
        <span>{weather['text']}</span>
      </div>
    </div>
    <div class="content">
    <div class="col-left">
      <div class="panel gauge-panel" style="flex:1;">
        <div class="panel-title" style="font-size:19px;">2026年目标</div>
        <div class="gauge-wrap">
          {gauge}
        </div>
        {legend}
      </div>
    </div>
    <div class="col-right">
      {tasks_html}
      {cal_html}
    </div>
    </div>
  </div>
  <script>
    (function(){{
      var d = new Date();
      var wk = ['周日','周一','周二','周三','周四','周五','周六'];
      var s = d.getFullYear()+'年'+(d.getMonth()+1)+'月'+d.getDate()+'日 '+wk[d.getDay()];
      var el = document.getElementById('tbDate');
      if(el) el.textContent = s;
    }})();
  </script>
</body>
</html>'''
    return html


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def generate(target_date=None, open_browser=False, style=DEFAULT_STYLE, out_file=None):
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    weight_info = get_weight_info(target_date)
    goals = get_goals_info()
    fitness_info = get_fitness_info(target_date)
    tasks_info = get_tasks_info(target_date)
    fitness_rows = read_csv_dicts(os.path.join(DATA_DIR, "fitness.csv"))
    weather_info = fetch_weather("Beijing")
    slogan = get_slogan_info()
    html = build_html(weight_info, goals, fitness_info, tasks_info, fitness_rows,
                      target_date, weather_info, style, slogan)
    target_path = out_file or OUT_HTML
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] 生成 {target_path} (style={style}, date={target_date})")
    if open_browser:
        import webbrowser
        webbrowser.open("file://" + os.path.abspath(target_path))
    return target_path


def generate_all(target_date=None):
    """循环生成所有主题到独立文件：dashboard_<style>.html"""
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    paths = []
    for style in THEMES:
        p = os.path.join(OUT_DIR, f"dashboard_{style}.html")
        generate(target_date, False, style, p)
        paths.append(p)
    # 同时生成默认名 dashboard.html
    default_path = generate(target_date, False, DEFAULT_STYLE)
    paths.append(default_path)
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 reTerminal 仪表盘")
    parser.add_argument("--date", type=str, default=None, help="目标日期 YYYY-MM-DD")
    parser.add_argument("--open", action="store_true", help="生成后打开浏览器")
    parser.add_argument("--style", type=str, default=DEFAULT_STYLE,
                        choices=list(THEMES.keys()), help="主题风格")
    parser.add_argument("--all", action="store_true", help="循环生成所有主题到独立文件")
    args = parser.parse_args()
    if args.all:
        generate_all(args.date)
    else:
        generate(args.date, args.open, args.style)
