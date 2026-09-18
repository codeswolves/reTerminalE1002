"""
check_page_js.py
用 node + 最小 DOM mock 真跑一遍页面内嵌的 JS, 捕获运行时错误。

为什么需要它:
    生成器产出的是"语法正确、但可能运行时报错"的页面。例如某个函数定义漏了,
    `node --check` 查不出来(语法没问题), 但浏览器一加载就 ReferenceError,
    整个 <script> 中断 —— 表现是"页面好几块区域全是空白"。
    这个脚本能在交付前把这类问题拦住, 并顺带报告各区域渲染出的内容长度。

用法:
    python src/utils/check_page_js.py                        # 检查默认的 3 个页面
    python src/utils/check_page_js.py output/tasks/quadrant.html
"""

import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PAGES = [
    os.path.join(BASE_DIR, "output", "tasks", "quadrant.html"),
    os.path.join(BASE_DIR, "output", "tasks", "tasks_view.html"),
    os.path.join(BASE_DIR, "output", "tasks", "task_flow.html"),
]

# 最小 DOM mock: 只要够页面 init() 跑完即可
MOCK = """
const __els = {};
function __el(id) {
  if (!__els[id]) __els[id] = {
    innerHTML: '', textContent: '', value: '', className: '',
    classList: { add(){}, remove(){}, contains(){ return false; } },
    addEventListener(){}, querySelectorAll(){ return []; },
    dataset: {}, style: {}
  };
  return __els[id];
}
globalThis.__els = __els;
globalThis.document = {
  getElementById: __el,
  querySelectorAll(){ return []; },
  addEventListener(){}
};
globalThis.window = globalThis;
globalThis.fetch = () => Promise.reject(new Error('no network'));
globalThis.alert = () => {};
globalThis.confirm = () => false;
"""

# 跑完之后报告各区域渲染出的内容长度 —— 全是 0 就说明渲染没发生
CHECK = """
const out = [];
Object.keys(globalThis.__els).forEach(function (id) {
  const el = globalThis.__els[id];
  const s = String(el.innerHTML || el.textContent || '');
  if (s) out.push(id + '=' + s.length);
});
console.log('RENDERED: ' + (out.join(', ') || '(none)'));
"""


def check(path):
    """返回 (True/False/None, 说明)。None 表示跳过(文件缺失或没有 node)。"""
    if not os.path.exists(path):
        return None, "文件不存在"
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not blocks:
        return None, "没有 <script> 块"

    tmp = os.path.join(os.path.dirname(path), "_check_run.js")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(MOCK + "\n".join(blocks) + CHECK)
    try:
        r = subprocess.run(
            ["node", tmp], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
    except FileNotFoundError:
        return None, "未找到 node，跳过"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    if r.returncode != 0:
        err = [ln for ln in (r.stderr or "").strip().splitlines() if ln.strip()]
        return False, "\n".join(err[:8])
    return True, (r.stdout or "").strip()


def main():
    pages = sys.argv[1:] or DEFAULT_PAGES
    failed = 0
    for p in pages:
        ok, msg = check(p)
        name = os.path.relpath(p, BASE_DIR)
        if ok is None:
            print(f"[跳过] {name}: {msg}")
        elif ok:
            print(f"[OK]   {name}: {msg}")
        else:
            failed += 1
            print(f"[FAIL] {name}:\n{msg}")
    if failed:
        print(f"\n[结果] {failed} 个页面存在 JS 运行时错误")
    else:
        print("\n[结果] 全部通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
