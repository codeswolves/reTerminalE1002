#!/usr/bin/env python3
"""
reTerminal E1002 墨水屏显示工具
===============================
将生成的 PNG 图片显示到 reTerminal 的墨水屏上。

用法:
    python display_on_eink.py                          # 显示 output/screenshots/dashboard.png
    python display_on_eink.py --image custom.png       # 指定图片
    python display_on_eink.py --clear                  # 清屏

硬件:
    Seeed Studio reTerminal (CM4) + E1002 5" E-Ink Display
    驱动芯片: IT8951
    分辨率: 800x480

依赖 (reTerminal 上):
    pip install Pillow
    # IT8951 驱动通常预装在 reTerminal 系统中
"""

import argparse
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根目录（src/utils/ 的祖父目录）
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_IMAGE = OUTPUT_DIR / "screenshots" / "dashboard.png"


def display_via_it8951(image_path):
    """
    通过 IT8951 驱动显示图片到墨水屏。
    适用于 Seeed Studio reTerminal E1002。
    """
    try:
        from PIL import Image
    except ImportError:
        print("[ERROR] 未安装 Pillow，请执行: pip install Pillow")
        sys.exit(1)

    # ---- 方法1: 使用 IT8951 Python 库 ----
    try:
        from IT8951 import EPD
        from IT8951.display import AutoEPDDisplay
        from IT8951.constants import (Rotate, VCOM, DisplayModes,
                                       Waveform, set_img_enable)

        vcom = VCOM.VCOM_2780
        rotate = Rotate.ROTATE_0

        print("[INFO] 使用 IT8951 驱动显示...")
        display = AutoEPDDisplay(
            vcom=vcom,
            spi_hz=24000000,
            rotate=rotate,
            spi_cs=0,
            spi_bus=0,
        )

        img = Image.open(image_path).convert("L")
        img = img.resize((display.width, display.height), Image.LANCZOS)

        # A2 模式：快速刷新，适合文字/图表
        display.frame_buf.paste(img)
        display.draw_full(DisplayModes.A2)
        print(f"[OK] 图片已显示到墨水屏: {image_path}")
        return True

    except ImportError:
        print("[WARN] IT8951 库未安装，尝试备用方案...")

    # ---- 方法2: 直接写入 framebuffer (备用方案) ----
    try:
        img = Image.open(image_path).convert("1")  # 二值化
        img = img.resize((800, 480), Image.LANCZOS)

        fb_paths = ["/dev/fb0", "/dev/fb1"]
        fb_path = None
        for p in fb_paths:
            if Path(p).exists():
                fb_path = p
                break

        if fb_path is None:
            print("[ERROR] 未找到 framebuffer 设备 (/dev/fb0, /dev/fb1)")
            print("[INFO] 请确保在 reTerminal 设备上运行，并已加载 IT8951 驱动")
            return False

        fb = open(fb_path, "wb")
        fb.write(img.tobytes())
        fb.close()
        print(f"[OK] 图片已写入 framebuffer ({fb_path}): {image_path}")
        return True

    except PermissionError:
        print("[ERROR] 权限不足，请使用 sudo 运行 或 将用户加入 video 组:")
        print("  sudo usermod -a -G video $USER")
        print("  然后重新登录")
        return False
    except Exception as e:
        print(f"[ERROR] framebuffer 写入失败: {e}")
        return False


def display_via_simple(image_path):
    """
    简易版显示：将图片转换为 bmp 并写入 framebuffer。
    适用于已正确配置 IT8951 framebuffer 的系统。
    参考：https://wiki.seeedstudio.com/reTerminal/
    """
    try:
        from PIL import Image
    except ImportError:
        print("[ERROR] 未安装 Pillow")
        sys.exit(1)

    img = Image.open(image_path).convert("1")
    img = img.resize((800, 480), Image.LANCZOS)

    # 保存为 BMP（framebuffer 兼容格式）
    bmp_path = OUTPUT_DIR / "screenshots" / "dashboard.bmp"
    img.save(bmp_path)

    fb_path = "/dev/fb0"
    if Path(fb_path).exists():
        with open(bmp_path, "rb") as src, open(fb_path, "wb") as dst:
            src.seek(54)  # 跳过 BMP 文件头（54 字节），只写入像素数据
            dst.write(src.read())
        print(f"[OK] BMP写入framebuffer: {image_path}")
        return True
    else:
        print(f"[ERROR] {fb_path} 不存在")
        return False


def clear_screen():
    """清屏（全白）"""
    try:
        from PIL import Image
        img = Image.new("1", (800, 480), 1)  # 全白
        fb_path = "/dev/fb0"
        if Path(fb_path).exists():
            with open(fb_path, "wb") as fb:
                fb.write(img.tobytes())
            print("[OK] 屏幕已清除")
            return True
        else:
            print(f"[ERROR] {fb_path} 不存在")
            return False
    except Exception as e:
        print(f"[ERROR] 清屏失败: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="reTerminal E1002 墨水屏显示工具")
    parser.add_argument("--image", type=str, default=str(DEFAULT_IMAGE),
                        help=f"PNG 图片路径 (默认: {DEFAULT_IMAGE})")
    parser.add_argument("--clear", action="store_true", help="清屏（全白）")
    parser.add_argument("--simple", action="store_true",
                        help="使用简易 framebuffer 模式")
    args = parser.parse_args()

    if args.clear:
        clear_screen()
        sys.exit(0)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[ERROR] 图片不存在: {image_path}")
        print("[INFO] 请先运行 generate_dashboard.py 和 render_screenshot.py")
        sys.exit(1)

    if args.simple:
        success = display_via_simple(image_path)
    else:
        success = display_via_it8951(image_path)

    sys.exit(0 if success else 1)
