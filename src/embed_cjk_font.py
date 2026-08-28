#!/usr/bin/env python3
"""
embed_cjk_font.py
=================
把中文字体以「子集 woff2 + base64」形式嵌入 HTML，彻底解决设备端
（如 reTerminal 墨水屏/SenseCraft 终端）缺少中文字体导致中文显示为
「方框+问号」的问题。

原理：
  1. 扫描 HTML 中实际出现的中文字符（页面有多少字就嵌入多少，子集体积很小）
  2. 用 fontTools 对系统中文字体做子集化，输出 woff2
  3. 把 woff2 base64 编码后以 @font-face 嵌入 <style>，并让字体排到 font-family 最前面
  4. 设备渲染时优先使用内嵌字体，不再依赖设备系统字体

用法:
    python embed_cjk_font.py output/dashboard.html           # 原地嵌入
    python embed_cjk_font.py --out out.html in.html           # 输出到新文件
    python embed_cjk_font.py --font <字体文件> in.html         # 指定字体

依赖:
    pip install fonttools brotli

说明: 脚本可被其他生成脚本 import（见 embed_font_file），例如在生成 HTML
      后自动调用，保证每次重新生成页面都带内嵌字体。
"""

import argparse
import base64
import io
import os
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection

FONT_NAME = "EInkCJK"

# 中文字体候选（按优先级查找）
CANDIDATE_FONTS = [
    os.environ.get("CJK_FONT_FILE", ""),
    "assets/fonts/NotoSansSC-Regular.ttf",
    "assets/fonts/msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]

# 用于识别中文字体族的关键词（选对 ttc 中的正确子字体）
CJK_FAMILY_KEYS = (
    "yahei", "ya hei", "微软雅黑",
    "noto sans cjk sc", "source han sans sc", "思源黑体",
    "simhei", "黑体",
    "simsun", "宋体",
    "wenquanyi", "文泉驿",
    "pingfang",
)

# 收集页面上出现的中文相关字符（汉字 + CJK 标点 + 全角符号）
CJK_RE = re.compile(
    r"[\u2E80-\u9FFF"      # CJK 部首 + 汉字
    r"\uF900-\uFAFF"       # CJK 兼容汉字
    r"\uFE30-\uFE4F"       # 中文竖排标点
    r"\uFF00-\uFFEF"       # 全角字符（含全角数字/字母/标点）
    r"\u3000-\u303F"       # CJK 标点（。、，；：！？等）
    r"\u2018-\u201F"       # 引号 ' ' " "
    r"\u2026"              # 省略号 …
    r"\u00B7"              # 间隔号 ·
    r"\u2013\u2014]"       # 短破折号 – 长破折号 —
)


def find_font():
    """按优先级查找可用的中文字体文件。"""
    for path in CANDIDATE_FONTS:
        if path and Path(path).is_file():
            return path
    raise FileNotFoundError(
        "未找到中文字体，请指定 --font <字体文件> 或设置环境变量 CJK_FONT_FILE"
    )


def pick_font_number(font_path):
    """对 .ttc 字体集合，返回包含中文字体族的那一档（如 msyh.ttc 中的微软雅黑）。

    返回 (font_number, family_name)。
    """
    with open(font_path, "rb") as f:
        if f.read(4) != b"ttcf":
            return 0, ""
    try:
        coll = TTCollection(font_path)
        for i, font in enumerate(coll.fonts):
            name = (font["name"].getDebugName(1) or "").lower()
            if any(k in name for k in CJK_FAMILY_KEYS):
                return i, name
        return 0, (coll.fonts[0]["name"].getDebugName(1) or "")
    except Exception:
        return 0, ""


def collect_chars(html):
    """提取 HTML 中出现的中文字符集合。

    去掉 <script> / <style> 块，避免把 JS/CSS 里的关键字误收进字体子集。
    """
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.I)
    chars = set(CJK_RE.findall(cleaned))
    # 补充常见中文标点（即使页面暂时没用到，也保留，避免日后加字漏字）
    chars.update("·，。、；：！？（）《》〈〉【】〔〕“”‘’…—～·")
    return "".join(sorted(chars))


def build_subset_woff2(font_path, text, font_number=0):
    """子集化字体为 woff2 字节流。"""
    options = subset.Options()
    options.font_number = font_number
    options.flavor = "woff2"
    options.text = text
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.recalc_bounds = True
    font = subset.load_font(font_path, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def embed_font(html, font_path, font_number=0, font_name=FONT_NAME):
    """把字体子集 base64 嵌入 HTML，返回新 HTML 字符串。"""
    text = collect_chars(html)
    if not text:
        return html
    woff2 = build_subset_woff2(font_path, text, font_number)
    b64 = base64.b64encode(woff2).decode("ascii")

    css = (
        f'@font-face{{font-family:"{font_name}";'
        f'src:url(data:font/woff2;base64,{b64}) format("woff2");'
        f"font-weight:normal;font-style:normal;font-display:swap;}}"
    )
    # 插入到第一个 <style> 标签的内容开头
    style_idx = html.find("<style")
    if style_idx == -1:
        raise ValueError("HTML 中没有 <style> 标签，无法嵌入字体")
    insert_at = html.find(">", style_idx) + 1
    html = html[:insert_at] + "\n" + css + html[insert_at:]

    # 把自定义字体放到第一个 font-family（body）的最前面
    html = re.sub(
        r"font-family:\s*(-apple-system)",
        f'font-family:"{font_name}", \\1',
        html,
        count=1,
    )
    return html


def embed_font_file(html_path, out_path=None, font_path=None):
    """对文件执行嵌入（原地或输出到新文件）。"""
    html_path = Path(html_path)
    html = html_path.read_text(encoding="utf-8")
    fp = Path(font_path) if font_path else Path(find_font())
    font_number, family = pick_font_number(str(fp))
    out_html = embed_font(html, str(fp), font_number)
    target = Path(out_path) if out_path else html_path
    target.write_text(out_html, encoding="utf-8")
    print(
        f"[OK] 内嵌字体 {fp.name}({family or '?'}) {len(html)//1024}KB -> "
        f"{len(out_html)//1024}KB | {target}"
    )
    return str(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="把中文字体子集嵌入 HTML")
    parser.add_argument("html", help="要处理的 HTML 文件")
    parser.add_argument("--out", help="输出文件（默认原地覆盖）")
    parser.add_argument("--font", help="指定中文字体文件（默认自动查找）")
    args = parser.parse_args()
    try:
        embed_font_file(args.html, args.out, args.font)
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
