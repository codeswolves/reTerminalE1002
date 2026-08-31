# 中文乱码问题记录（2026-08-28）

## 一、问题现象

`output/dashboard.html` 加载到 SenseCraft 的 reTerminal E1002 终端后，页面上的中文全部显示为**「方框 + 问号」**（即 Unicode 缺字字符，tofu / missing glyph）。

- 本地浏览器（Windows）打开同一份 `dashboard.html` 中文显示**正常**。
- 设备端（reTerminal / SenseCraft 内置 WebView 渲染）中文显示**异常**，数字英文正常。

> 核心痛点：E1002 SenseCraft 内置 WebView **没有系统中文字体**。编码 meta 标签只能解决字符解码，**不能解决方块豆腐块**，必须让网页自带字体（WebFont）。

## 二、排查过程

1. **对比历史版本字体配置**

   对比 8/26、8/27、8/28 三个版本的 `dashboard.html`：

   ```bash
   git show bc5c9c8:output/dashboard.html | Select-String "font-family"
   git show 5bbfb8d:output/dashboard.html | Select-String "font-family"
   git show 4c858c5:output/dashboard.html | Select-String "font-family"
   ```

   三个版本的 `font-family` 字体栈**完全一致**，都声明了 `"Microsoft YaHei"`、`"PingFang SC"` 等中文字体。

2. **结论：代码/字体栈没有变化**

   字体栈从 8/26 到 8/28 从未改变，本地浏览器一直正常。因此问题**不是代码变更导致**，而是**设备端渲染环境缺少中文字体**。

## 三、根本原因

`dashboard.html` 中声明的字体（`Microsoft YaHei`、`PingFang SC` 等）都是**桌面系统字体**：

- Windows 自带微软雅黑 → 本地浏览器正常；
- reTerminal 设备系统（Linux 类）**未安装任何中文字体** → 渲染引擎找不到可用的中文字体，回退失败，显示为「方框 + 问号」。

> 注：此前几天显示正常，可能与设备端加载的内容/环境变化有关（例如之前加载的是 Windows 本地截图 PNG，今天改为设备端直接渲染 HTML），排查后确认核心问题始终是**设备缺中文字体**。

## 四、解决方案

### 方案一（已采用，推荐）：HTML 内嵌中文字体子集（base64）

新增工具 `src/embed_cjk_font.py`，把中文字体**以子集 woff2 + base64 形式直接嵌入 HTML**，页面完全自包含，不依赖设备系统字体。

原理：

1. 扫描 HTML 中实际出现的所有中文字符（含 CJK 标点）；
2. 用 fonttools 对本机中文字体（微软雅黑）做**子集化**，只保留页面用到的字符，输出 woff2（体积小，约几十 KB）；
3. 将 woff2 base64 编码后以 `@font-face` 嵌入 `<style>`，并让自定义字体 `EInkCJK` 排到 `font-family` 最前面。

效果：

| 文件 | 内嵌前 | 内嵌后 |
|---|---|---|
| `output/dashboard.html` | 12 KB | 约 88 KB（含 76 KB 字体子集） |

**已集成到生成脚本**：`src/generate_dashboard.py` 每次生成后自动嵌入（可用 `--no-embed` 关闭）。

手动使用方式：

```bash
python src/embed_cjk_font.py output/dashboard.html              # 原地嵌入
python src/embed_cjk_font.py --out out.html in.html             # 输出到新文件
python src/embed_cjk_font.py --font <字体文件> in.html           # 指定字体
```

### 方案二（备用）：在设备上安装中文字体

修改 `src/setup_reterminal.sh`，在 reTerminal 设备上安装 Noto CJK 字体：

```bash
sudo apt update
sudo apt install -y fonts-noto-cjk
```

安装后设备系统自带中文字体，任何页面（包括不内嵌字体的 `tasks_view.html`）都能正常显示。

## 五、硬性约束核对

加载到 E1002 SenseCraft WebView 的 HTML 必须满足：

| 要求 | dashboard.html 现状 |
|---|---|
| `<!DOCTYPE html>` | 第 1 行 ✅ |
| `<html lang="zh-CN">` | ✅ |
| `<meta charset="UTF-8">` 写在 `<head>` **第一行** | 第 5 行（head 首行内容）✅ |
| 文件保存编码 **UTF-8 无 BOM** | 已验证无 BOM（HEX `3C 21 44`）✅ |
| 必须用**子集化 woff2**，不能用完整字体 | ✅ 内嵌 76KB 子集（完整 Noto-SC woff2 约 700KB，E1002 加载卡顿） |

## 六、方案选型对比：独立 woff2 文件 vs base64 内嵌

旧方案（glyphhanger 生成**独立 woff2 文件** `./subset.woff2`，与 HTML 分开上传）与**base64 内嵌**的对比：

| 维度 | 独立 woff2 文件 | base64 内嵌（本项目） |
|---|---|---|
| 网络差时字体加载 | 下载慢/失败 → 短暂方块 | 字体在 HTML 内，一次请求拿到，**无此风险** |
| Gitee/GitHub raw 风控 | 可能拦截 woff2 请求 → 方块 | 没有独立字体请求，**不会被拦截** |
| 部署文件数 | html + woff2 两个文件，缺一不可 | **单文件自包含** |
| 新增汉字 | 必须手动重跑 glyphhanger | 生成脚本每次**自动重新提取字符集** |
| HTML 体积 | 小（字体另存） | 增大 33%（base64 膨胀，约 76KB，可接受） |

结论：在 E1002 场景下 base64 内嵌**更稳定**，代价是 HTML 体积增加几十 KB，换取完全消除字体加载失败/被拦截的风险。

### 两种子集化工具对比

- **glyphhanger（旧方案）**：

  ```bash
  npm install -g glyphhanger
  glyphhanger ./index.html --subset=./NotoSansSC-Regular.ttf --formats=woff2
  ```

- **本项目 embed_cjk_font.py（fonttools 实现）**：

  ```bash
  python src/embed_cjk_font.py output/dashboard.html
  ```

  效果相同（只保留页面出现过的汉字），且已集成到每日生成流程，无需手动操作。

## 七、部署注意（针对 E1002 SenseCraft）

1. **墨水屏刷新特性**：字体下载/渲染完成后，需要**触发一次屏幕刷新**，否则屏上可能仍显示旧内容/方块。首次加载新页面后务必刷新一次。
2. 避免使用 raw 直链加载资源；本方案为单文件内嵌，天然规避该问题。
3. 网络差时 base64 内嵌的 HTML 一次性加载，比「HTML + 字体双请求」更快出字。

## 八、无法绕开的缺点与兜底

内嵌字体方案仍有以下限制，需提前知晓：

1. 页面**新增汉字时**，必须重新生成子集字体（本项目已由生成脚本自动完成）；
2. 内嵌字体只包含**页面当前用到的字符**，未用到的字不在字体里；
3. 兜底备选：若内嵌方案仍不稳定，可改用 **SVG 内嵌**——把文字转为矢量路径，不依赖任何字体，体积同样很小；或退回 PNG 截图方案（体积大但中文 100% 稳定）。

## 九、相关文件

| 文件 | 说明 |
|---|---|
| `src/embed_cjk_font.py` | 新增，字体子集嵌入工具 |
| `src/generate_dashboard.py` | 集成自动嵌入逻辑（`--no-embed` 可关闭） |
| `src/generate_tasks_view.py` | 不嵌入字体（按需，仅 `dashboard.html` 内嵌） |
| `src/setup_reterminal.sh` | 设备安装 Noto CJK 字体的备用方案 |
| `output/dashboard.html` | 已内嵌字体，设备端中文正常显示 |
| `output/dashboard.png` | 已按最新页面重新截图 |

对应提交：`5cf393c`
