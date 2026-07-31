#!/usr/bin/env python3
"""
HTML 截图工具
=============
使用 Playwright 将生成的 HTML 看板渲染为 800x480 PNG 图片，
供 reTerminal 墨水屏显示。

用法:
    python render_screenshot.py                    # 截取 output/dashboard.html
    python render_screenshot.py --html custom.html # 指定HTML文件

依赖:
    pip install playwright
    playwright install chromium
"""

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_HTML = OUTPUT_DIR / "dashboard.html"
DEFAULT_PNG = OUTPUT_DIR / "dashboard.png"


def render_screenshot(html_path, png_path, width=800, height=480):
    """将HTML渲染为PNG截图"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] 未安装 playwright，请执行:")
        print("  pip install playwright")
        print("  playwright install chromium")
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
        browser = p.chromium.launch()
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
