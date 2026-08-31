#!/usr/bin/env python3
"""
refresh_csv.py — 每日刷新 CSV 进度数据

用法:
    python3 refresh_csv.py                  # 刷新全部 CSV
    python3 refresh_csv.py fitness          # 只刷新指定文件(不带 .csv 后缀)
    python3 refresh_csv.py weight 90.5      # 带值刷新

说明:
    在此编写每天的进度更新逻辑: 读取 data/ 下的 CSV -> 更新进度 -> 写回。
    任务数据已迁移到 task_flows.json，相关操作通过 serve_task_flow.py API 完成。
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# 需要刷新(或可被单独指定刷新)的 CSV 文件
CSV_FILES = [
    "fitness.csv",
    "goals.csv",
    "weight.csv",
    "slogan.csv",
]

# tasks 已迁移到 task_flows.json，不再通过 CSV 管理


# ---------- 通用工具 ----------

def _today_str() -> str:
    """返回今日日期字符串(YYYY/MM/DD 带前导零, 避免表格软件打开时改写格式)。"""
    t = date.today()
    return f"{t.year:04d}/{t.month:02d}/{t.day:02d}"


def _warn_skipped(skipped):
    """提示被跳过的异常行(行号列表)。"""
    if skipped:
        print(f"[警告] 第 {', '.join(map(str, skipped))} 行格式异常(列数不符), 已跳过未更新")


def _clean_csv_dates(path: Path) -> None:
    """清洗表格软件产生的日期污染: 2026.0/8/1 -> 2026/08/01, 并统一为 YYYY/MM/DD。"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except Exception:
        return
    new_text = text.replace(".0/", "/")  # 剥掉表格软件加的 .0
    new_text = re.sub(
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
        lambda m: f"{int(m.group(1)):04d}/{int(m.group(2)):02d}/{int(m.group(3)):02d}",
        new_text,
    )
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"[清洗] {path.name}: 日期已统一为 YYYY/MM/DD 格式")


def _upsert_today_line(path: Path, date_str: str, new_line: str,
                       find_empty: bool = False) -> None:
    """通用逻辑: 若文件已有今日记录则覆盖, 否则追加(或填入空行)。

    find_empty=True 时, 会先尝试填入首个空行, 找不到才追加末尾。
    """
    with open(path, "r", newline="", encoding="utf-8") as f:
        lines = f.readlines()

    # 今天已有记录 -> 覆盖更新
    for i, line in enumerate(lines):
        if line.startswith(date_str + ","):
            old = line.strip()
            lines[i] = new_line
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"[完成] 已更新今日记录: {path} -> {new_line.strip()} (原: {old})")
            return

    # 无今日记录 -> 写入
    if find_empty:
        for i, line in enumerate(lines):
            if line.strip().strip(",").strip() == "":
                lines[i] = new_line
                break
        else:
            lines.append(new_line)
    else:
        lines.append(new_line)

    with open(path, "w", newline="", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"[完成] 已追加: {path} -> {new_line.strip()}")


# ---------- 各 CSV 刷新函数 ----------

def refresh_weight(path: Path, value: str | None) -> None:
    """weight.csv: 今日体重覆盖/追加 (date,weight)。"""
    if value is None:
        print("[提示] weight.csv 需要体重数值, 用法: python3 refresh_csv.py weight 90.5")
        return
    date_str = _today_str()
    _upsert_today_line(path, date_str, f"{date_str},{value}\n")


def refresh_fitness(path: Path, value: str | None) -> None:
    """fitness.csv: 今日打卡覆盖/填入空行 (date,checkin,content,yesterday,today)。"""
    if value is None:
        print("[提示] fitness.csv 需要打卡内容, 用法: python3 refresh_csv.py fitness 跑步一公里")
        return
    date_str = _today_str()
    new_line = f"{date_str},1,{value},1,1\n"
    _upsert_today_line(path, date_str, new_line, find_empty=True)


# tasks 已迁移到 task_flows.json，相关操作通过 serve_task_flow.py API 完成


def refresh_slogan(path: Path, value: str | None) -> None:
    """slogan.csv: 追加一行新口号(防重复)。"""
    if value is None:
        print("[提示] slogan.csv 需要口号内容, 用法: python3 refresh_csv.py slogan 新口号")
        return
    with open(path, "r", newline="", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        if line.strip() == value:
            print(f"[跳过] 已有相同口号, 避免重复记录: {value}")
            return
    with open(path, "a", newline="", encoding="utf-8") as f:
        f.write(f"{value}\n")
    print(f"[完成] 已追加: {path} -> {value}")


def refresh_goals(path: Path, value: str | None) -> None:
    """goals.csv: 所有目标 done 加 1 (只改 done 列)。"""
    _ = value  # goals 不需要外部传值
    with open(path, "r", newline="", encoding="utf-8") as f:
        lines = f.readlines()
    changed = []
    for i, line in enumerate(lines[1:], start=1):
        parts = line.rstrip("\n").split(",")
        if len(parts) >= 3 and parts[2].strip().isdigit():
            parts[2] = str(int(parts[2]) + 1)
            lines[i] = ",".join(parts) + "\n"
            changed.append(parts)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.writelines(lines)
    if changed:
        print(f"[完成] 目标进度已更新: {path}")
        for parts in changed:
            print(f"    {parts[0]}: done {int(parts[2]) - 1} -> {parts[2]} (target {parts[1]})")
    else:
        print(f"[跳过] goals.csv 中没有可更新的 done 行")


# ---------- 路由与入口 ----------

# 注册各 CSV 的处理函数
_REFRESHERS = {
    "weight.csv": refresh_weight,
    "fitness.csv": refresh_fitness,
    "slogan.csv": refresh_slogan,
    "goals.csv": refresh_goals,
}


def refresh_one(csv_name: str, value=None) -> None:
    """根据 csv_name 路由到对应的刷新函数。"""
    path = DATA_DIR / csv_name
    if not path.exists():
        print(f"[跳过] 文件不存在: {path}")
        return

    # 每次刷新前自动清洗日期格式(防表格软件污染)
    _clean_csv_dates(path)

    handler = _REFRESHERS.get(csv_name)
    if handler is None:
        print(f"[跳过] {csv_name} 的刷新逻辑尚未实现 (日期: {date.today()})")
        return

    handler(path, value)


def main() -> None:
    """解析命令行参数并调用 refresh_one。

    支持:
        python3 refresh_csv.py                        # 全部刷新
        python3 refresh_csv.py weight 90.5            # 单文件 + 单值
        python3 refresh_csv.py fitness 跑步5公里       # 单文件 + 打卡内容
        python3 refresh_csv.py fitness weight 跑步     # 多文件 + 单值
    """
    args = sys.argv[1:]
    if not args:
        for name in CSV_FILES:
            refresh_one(name)
        return

    base_names = {f[:-4] for f in CSV_FILES}
    names = []
    extras = []
    for a in args:
        if a.endswith(".csv") or a in base_names:
            names.append(a)
        else:
            extras.append(a)

    value = None
    if len(extras) == 1:
        value = extras[0]
    elif len(extras) > 1:
        value = extras  # 多参数以列表传给处理函数(如 tasks 任务名 100)

    for n in names:
        fname = n if n.endswith(".csv") else n + ".csv"
        refresh_one(fname, value)


if __name__ == "__main__":
    main()
