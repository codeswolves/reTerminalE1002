#!/usr/bin/env python3
"""
HTML 截图工具
=============
使用 Playwright 将生成的 HTML 看板渲染为 800x480 PNG 图片，
供 reTerminal 墨水屏显示。

优先使用系统已安装的 Edge/Chrome，无需额外下载 playwright 浏览器。
若系统无 Edge/Chrome，再回退到 playwright 自带 chromium（需 playwright install）。

用法:
    python render_screenshot.py                    # 截取 output/dashboard/dashboard.html
    python render_screenshot.py --html custom.html # 指定HTML文件

依赖:
    pip install playwright
    # 可选（无系统 Edge/Chrome 时需要）:
    playwright install chromium
"""

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根目录（src/utils/ 的祖父目录）
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_HTML = OUTPUT_DIR / "dashboard" / "dashboard.html"
DEFAULT_PNG = OUTPUT_DIR / "screenshots" / "dashboard.png"

# 浏览器启动顺序：系统 Edge → 系统 Chrome → playwright 自带 chromium
LAUNCH_CHANNELS = [
    {"channel": "msedge", "desc": "系统 Microsoft Edge"},
    {"channel": "chrome", "desc": "系统 Google Chrome"},
    {"channel": None, "desc": "playwright 自带 chromium"},
]


def _launch_browser(p):
    """按顺序尝试启动浏览器，返回 browser 句柄；全部失败则抛出最后一个异常"""
    last_err = None
    for cfg in LAUNCH_CHANNELS:
        try:
            print(f"[INFO] 尝试启动: {cfg['desc']}")
            browser = p.chromium.launch(channel=cfg["channel"]) if cfg["channel"] \
                else p.chromium.launch()
            print(f"[OK] 已启动: {cfg['desc']}")
            return browser
        except Exception as e:
            msg = str(e)
            # 通道不可用通常是 "channel not installed" 类错误，静默跳过
            if "not found" in msg.lower() or "not installed" in msg.lower() \
                or "executable doesn't exist" in msg.lower():
                print(f"[WARN] {cfg['desc']} 不可用，尝试下一个")
                last_err = e
                continue
            # 其他错误直接抛出
            raise
    raise RuntimeError(
        f"所有浏览器启动方式均失败。最后错误: {last_err}\n"
        "请安装系统 Edge/Chrome，或运行: playwright install chromium"
    )


def render_screenshot(html_path, png_path, width=800, height=480):
    """将HTML渲染为PNG截图"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] 未安装 playwright，请执行:")
        print("  pip install playwright")
        print("  # 然后任选其一:")
        print("  #   1) 系统有 Edge/Chrome 即可直接用（推荐）")
        print("  #   2) playwright install chromium")
        sys.exit(1)

    html_path = Path(html_path)
    if not html_path.exists():
        print(f"[ERROR] HTML文件不存在: {html_path}")
        sys.exit(1)

    file_url = html_path.resolve().as_uri()

    print(f"[INFO] HTML: {html_path}")
    print(f"[INFO] 输出: {png_path}")
    print(f"[INFO] 分辨率: {width}x{height}")

    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(file_url, wait_until="networkidle")
        # 等待渲染完成
        page.wait_for_timeout(500)
        page.screenshot(path=str(png_path), full_page=False)
        browser.close()

    print(f"[OK] 截图已保存: {png_path}")
    return png_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTML 看板截图工具")
    parser.add_argument("--html", type=str, default=str(DEFAULT_HTML),
                        help="HTML 文件路径")
    parser.add_argument("--output", type=str, default=str(DEFAULT_PNG),
                        help="PNG 输出路径")
    parser.add_argument("--width", type=int, default=800, help="视口宽度")
    parser.add_argument("--height", type=int, default=480, help="视口高度")
    args = parser.parse_args()

    render_screenshot(args.html, args.output, args.width, args.height)
