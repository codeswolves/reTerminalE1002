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
    os.path.join(BASE_DIR, "output", "project", "project_index.html"),
    os.path.join(BASE_DIR, "output", "project", "project_tree.html"),
]

# 最小 DOM mock: 只要够页面 init() 跑完即可
MOCK = """
const __els = {};
// 每个 id 独立一个对象(这样才能按 id 检查渲染结果), 但方法共用一份。
// 方法要够全: 返回一个"什么都接得住"的假元素, 否则页面调用 appendChild 之类
// 会直接抛错, 让人误以为页面有 bug, 其实是 mock 不全。
globalThis.__fakeEl = {
  addEventListener(){}, removeEventListener(){},
  classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
  style: {}, dataset: {}, textContent: '', innerHTML: '', value: '', className: '',
  setAttribute(){}, removeAttribute(){}, getAttribute(){ return null; },
  appendChild(){}, removeChild(){}, insertBefore(){}, replaceChild(){},
  cloneNode(){ return globalThis.__fakeEl; },
  querySelector(){ return globalThis.__fakeEl; }, querySelectorAll(){ return []; },
  closest(){ return globalThis.__fakeEl; }, focus(){}, click(){},
  scrollIntoView(){}, getBoundingClientRect(){ return { top:0,left:0,width:0,height:0 }; }
};
function __el(id) {
  if (!__els[id]) __els[id] = Object.assign({}, globalThis.__fakeEl, { id: id });
  return __els[id];
}
globalThis.__els = __els;
globalThis.document = {
  getElementById: __el,
  querySelector(){ return globalThis.__fakeEl; },
  querySelectorAll(){ return []; },
  createElement(){ return Object.assign({}, globalThis.__fakeEl); },
  addEventListener(){},
  body: globalThis.__fakeEl,
  documentElement: globalThis.__fakeEl
};
globalThis.window = globalThis;
// 页面用 location.search 读 URL 参数(如 ?project=xxx), 没有它会直接抛 ReferenceError
globalThis.location = { search: '', href: 'http://localhost/', pathname: '/', hash: '' };
globalThis.fetch = () => Promise.reject(new Error('no network'));
globalThis.alert = () => {};
globalThis.confirm = () => false;
// 定时器必须禁掉: 页面里的 setInterval(轮询) 会让 node 进程无法退出, 脚本挂在 30s 超时
globalThis.setInterval = () => 0;
globalThis.clearInterval = () => {};
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = () => {};
globalThis.document.hidden = false;
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
