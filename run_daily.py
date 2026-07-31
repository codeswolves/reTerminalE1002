#!/usr/bin/env python3
"""
每日一键刷新流水线
==================
执行完整流程：读取CSV → 生成HTML → 渲染PNG → 显示到墨水屏

用法:
    python run_daily.py                  # 完整流程，每日随机风格
    python run_daily.py --no-display     # 只生成HTML+PNG，不更新墨水屏
    python run_daily.py --no-screenshot  # 只生成HTML，不截图
    python run_daily.py --style cyberpunk # 指定风格（覆盖随机）

在 reTerminal 上设置每日定时任务:
    crontab -e
    # 每天早上 8:00 自动刷新（随机风格）
    0 8 * * * cd /home/pi/reTerminal && python run_daily.py
"""

import argparse
import random
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"

# 可用主题列表（与 generate_dashboard.py 的 THEMES 保持一致）
AVAILABLE_STYLES = [
    "default", "cyberpunk", "dracula", "fui",
    "light", "macaron", "morandi", "pixel", "tactical",
]


def pick_random_style():
    """随机选择一种主题风格"""
    return random.choice(AVAILABLE_STYLES)


def step_generate(date=None, style=None):
    """步骤1: 生成HTML看板（每日随机风格）"""
    print("=" * 50)
    print("[STEP 1/3] 生成HTML看板")
    print("=" * 50)
    if style is None:
        style = pick_random_style()
    print(f"[INFO] 今日风格: {style}")
    cmd = [sys.executable, str(BASE_DIR / "generate_dashboard.py"),
           "--style", style]
    if date:
        cmd.extend(["--date", date])
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    if result.returncode != 0:
        print("[FAIL] HTML生成失败")
        return False
    return True


def step_screenshot():
    """步骤2: 渲染PNG截图"""
    print()
    print("=" * 50)
    print("[STEP 2/3] 渲染PNG截图 (800x480)")
    print("=" * 50)

    html_path = OUTPUT_DIR / "dashboard.html"
    if not html_path.exists():
        print("[FAIL] HTML文件不存在，请先完成步骤1")
        return False

    cmd = [sys.executable, str(BASE_DIR / "render_screenshot.py")]
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    if result.returncode != 0:
        print("[WARN] PNG截图失败（可能未安装playwright），跳过此步骤")
        print("[INFO] 你可以手动在浏览器中打开 dashboard.html 并截图")
        return False
    return True


def step_display():
    """步骤3: 显示到墨水屏"""
    print()
    print("=" * 50)
    print("[STEP 3/3] 显示到墨水屏")
    print("=" * 50)

    png_path = OUTPUT_DIR / "dashboard.png"
    if not png_path.exists():
        print("[FAIL] PNG文件不存在，请先完成步骤2")
        return False

    cmd = [sys.executable, str(BASE_DIR / "display_on_eink.py"),
           "--image", str(png_path)]
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    if result.returncode != 0:
        print("[WARN] 墨水屏显示失败")
        print("[INFO] 请确保在 reTerminal 设备上运行，并已安装 IT8951 驱动")
        return False
    return True


def run(date=None, do_screenshot=True, do_display=True, style=None):
    """执行完整流水线（style=None 时每日随机选风格）"""
    print("╔══════════════════════════════════════════════════╗")
    print("║   reTerminal E1002 看板 - 每日刷新流水线         ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    if style is None:
        style = pick_random_style()
    print(f"[INFO] 今日使用风格: {style}")
    print()

    steps = [
        ("生成HTML", lambda: step_generate(date, style)),
        ("渲染截图", lambda: step_screenshot()) if do_screenshot else (None, None),
        ("墨水屏显示", lambda: step_display()) if do_display else (None, None),
    ]

    success_count = 0
    fail_count = 0

    for name, action in steps:
        if action is None:
            continue
        if action():
            success_count += 1
        else:
            fail_count += 1

    print()
    print("=" * 50)
    print(f"[完成] 成功 {success_count} 步, 失败 {fail_count} 步")
    print(f"[输出] {OUTPUT_DIR}")

    return fail_count == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="reTerminal 每日看板刷新流水线"
    )
    parser.add_argument("--date", type=str, default=None,
                        help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--style", type=str, default=None,
                        choices=AVAILABLE_STYLES,
                        help="指定主题风格（默认每日随机）")
    parser.add_argument("--no-screenshot", action="store_true",
                        help="跳过PNG截图步骤")
    parser.add_argument("--no-display", action="store_true",
                        help="跳过墨水屏显示步骤")
    args = parser.parse_args()

    success = run(
        date=args.date,
        do_screenshot=not args.no_screenshot,
        do_display=not args.no_display,
        style=args.style,
    )
    sys.exit(0 if success else 1)
