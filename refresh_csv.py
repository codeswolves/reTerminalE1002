#!/usr/bin/env python3
"""
refresh_csv.py — 每日刷新 CSV 进度数据

用法:
    python3 refresh_csv.py            # 刷新全部 CSV
    python3 refresh_csv.py fitness    # 只刷新指定文件(不带 .csv 后缀)

说明:
    在此编写每天的进度更新逻辑: 读取 data/ 下的 CSV -> 更新进度 -> 写回。
"""

import csv
import sys
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# 需要刷新(或可被单独指定刷新)的 CSV 文件
CSV_FILES = [
    "fitness.csv",
    "goals.csv",
    "weight.csv",
    "tasks.csv",
    "slogan.csv",
]


def refresh_one(csv_name: str, value: str | None = None) -> None:
    """刷新单个 CSV 文件。在此编写具体更新逻辑。"""
    path = DATA_DIR / csv_name
    if not path.exists():
        print(f"[跳过] 文件不存在: {path}")
        return

    # --- weight.csv: 今日记录覆盖更新, 无记录则追加 (date,weight) ---
    if csv_name == "weight.csv":
        if value is None:
            print(f"[提示] {csv_name} 需要体重数值, 用法: python3 refresh_csv.py weight 90.5")
            return
        today = date.today()
        date_str = f"{today.year}/{today.month}/{today.day}"  # 与现有格式一致, 不带前导零
        with open(path, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
        # 今天已有记录 -> 覆盖更新
        for i, line in enumerate(lines):
            if line.startswith(date_str + ","):
                lines[i] = f"{date_str},{value}\n"
                with open(path, "w", newline="", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"[完成] 已更新今日记录: {path} -> {date_str},{value} (原: {line.strip()})")
                return
        # 无今日记录 -> 追加
        with open(path, "a", newline="", encoding="utf-8") as f:
            f.write(f"{date_str},{value}\n")
        print(f"[完成] 已追加: {path} -> {date_str},{value}")
        return

    # --- fitness.csv: 今日记录覆盖更新, 无记录则填入第一个空行 (date,checkin,content,yesterday,today) ---
    if csv_name == "fitness.csv":
        if value is None:
            print(f"[提示] {csv_name} 需要打卡内容, 用法: python3 refresh_csv.py fitness 跑步一公里")
            return
        today = date.today()
        date_str = f"{today.year}/{today.month}/{today.day}"
        new_row = f"{date_str},1,{value},1,1\n"
        with open(path, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
        # 今天已有记录 -> 覆盖更新 content
        for i, line in enumerate(lines):
            if line.startswith(date_str + ","):
                lines[i] = new_row
                with open(path, "w", newline="", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"[完成] 已更新今日打卡: {path} -> {new_row.strip()} (原: {line.strip()})")
                return
        # 无今日记录 -> 找第一个空行填入, 没有空行则追加到末尾
        for i, line in enumerate(lines):
            if line.strip().strip(",").strip() == "":
                lines[i] = new_row
                break
        else:
            lines.append(new_row)
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[完成] 已打卡: {path} -> {new_row.strip()}")
        return

    # --- tasks.csv: 两种模式 ---
    #   模式1: tasks 3            -> 所有任务 progress +3
    #   模式2: tasks 任务名 100    -> 指定任务 progress 设为 100
    if csv_name == "tasks.csv":
        # 模式2: 按任务名设值
        if isinstance(value, list):
            if len(value) != 2 or not value[1].lstrip("-").isdigit():
                print(f"[提示] {csv_name} 按任务设置用法: python3 refresh_csv.py tasks 任务名 100")
                return
            task_name, new_progress = value[0], str(int(value[1]))
            with open(path, "r", newline="", encoding="utf-8") as f:
                lines = f.readlines()
            found = False
            for i, line in enumerate(lines[1:], start=1):  # 跳过表头
                parts = line.rstrip("\n").split(",")
                if len(parts) >= 3 and parts[1].strip() == task_name:
                    parts[2] = new_progress
                    lines[i] = ",".join(parts) + "\n"
                    found = True
                    break
            if not found:
                print(f"[跳过] 未找到任务: {task_name}")
                return
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"[完成] 已设置进度: {task_name} -> {new_progress}")
            return
        # 模式1: 全部 +x
        if value is None or not value.lstrip("-").isdigit():
            print(f"[提示] {csv_name} 用法: ① python3 refresh_csv.py tasks 3 (全部+x)  ② python3 refresh_csv.py tasks 任务名 100 (指定任务设值)")
            return
        delta = int(value)
        with open(path, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
        changed = []
        for i, line in enumerate(lines[1:], start=1):  # 跳过表头
            parts = line.rstrip("\n").split(",")
            if len(parts) >= 3 and parts[2].strip().isdigit():
                parts[2] = str(int(parts[2]) + delta)
                lines[i] = ",".join(parts) + "\n"
                changed.append(parts)
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.writelines(lines)
        if changed:
            print(f"[完成] 进度已更新: {path} (增量 {delta:+d})")
            for parts in changed:
                print(f"    {parts[1]}: {int(parts[2]) - delta} -> {parts[2]}")
        else:
            print(f"[跳过] {csv_name} 中没有可更新的进度行")
        return

    # --- slogan.csv: 直接追加一行新口号 (单列) ---
    if csv_name == "slogan.csv":
        if value is None:
            print(f"[提示] {csv_name} 需要口号内容, 用法: python3 refresh_csv.py slogan 新口号")
            return
        with open(path, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
        # 防重复: 已有相同口号则跳过
        for line in lines:
            if line.strip() == value:
                print(f"[跳过] 已有相同口号, 避免重复记录: {value}")
                return
        with open(path, "a", newline="", encoding="utf-8") as f:
            f.write(f"{value}\n")
        print(f"[完成] 已追加: {path} -> {value}")
        return

    # --- goals.csv: 所有目标 done 加 1 (只改 done 列, 不动其他字段) ---
    if csv_name == "goals.csv":
        with open(path, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
        changed = []
        for i, line in enumerate(lines[1:], start=1):  # 跳过表头
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
            print(f"[跳过] {csv_name} 中没有可更新的 done 行")
        return

    # --- 其他 CSV: TODO 逻辑 ---
    # 示例框架:
    # with open(path, "r", newline="", encoding="utf-8") as f:
    #     rows = list(csv.DictReader(f))
    # ... 更新 rows ...
    # with open(path, "w", newline="", encoding="utf-8") as f:
    #     writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    #     writer.writeheader()
    #     writer.writerows(rows)
    print(f"[跳过] {csv_name} 的刷新逻辑尚未实现 (日期: {date.today()})")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        for name in CSV_FILES:
            refresh_one(name)
        return
    value = None
    names = []
    extras = []
    base_names = [f[:-4] for f in CSV_FILES]
    for a in args:
        if a.endswith(".csv") or a in base_names:
            names.append(a)
        else:
            extras.append(a)
    if len(extras) == 1:
        value = extras[0]
    elif len(extras) > 1:
        value = extras  # 多参数(如 tasks 任务名 100)以列表传给处理函数
    for n in names:
        refresh_one(n if n.endswith(".csv") else n + ".csv", value)


if __name__ == "__main__":
    main()
