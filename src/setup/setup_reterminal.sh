#!/bin/bash
# ============================================================
# reTerminal E1002 看板 - 设备端安装脚本
# 在 reTerminal (Raspberry Pi) 上运行此脚本完成配置
#
# 用法:
#   chmod +x setup_reterminal.sh
#   ./setup_reterminal.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # src/ 目录
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"               # 项目根目录
echo "╔══════════════════════════════════════════════════╗"
echo "║   reTerminal E1002 看板 - 安装配置               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# 1. 安装 Python 依赖
echo "[1/4] 安装 Python 依赖..."
pip3 install --user Pillow playwright 2>/dev/null || pip install --break-system-packages Pillow playwright

# 2. 安装 Chromium (Playwright 截图用) 与中文字体 (设备浏览器渲染中文必需)
echo "[2/4] 安装 Chromium 浏览器与中文字体..."
python3 -m playwright install chromium 2>/dev/null || echo "[WARN] Chromium 安装跳过（可手动安装）"
echo "[INFO] 安装中文字体 (fonts-noto-cjk)..."
sudo apt-get update >/dev/null 2>&1 && sudo apt-get install -y fonts-noto-cjk || echo "[WARN] 中文字体安装失败，SenseCraft 加载页面中文可能显示为方块"

# 3. 创建数据目录
echo "[3/4] 初始化数据目录..."
mkdir -p "${PROJECT_ROOT}/data" "${PROJECT_ROOT}/output"

# 创建示例 CSV（如果不存在）
for f in weight.csv fitness.csv tasks.csv; do
    if [ ! -f "${PROJECT_ROOT}/data/${f}" ]; then
        touch "${PROJECT_ROOT}/data/${f}"
        echo "[INFO] 已创建空文件: data/${f}"
    fi
done

# 4. 设置定时任务
echo "[4/4] 设置每日自动刷新定时任务 (每天 07:00)..."
CRON_JOB="0 7 * * * cd ${PROJECT_ROOT} && python3 src/run_daily.py >> /tmp/dashboard_cron.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "run_daily.py"; then
    echo "[INFO] 定时任务已存在，跳过"
else
    (crontab -l 2>/dev/null; echo "${CRON_JOB}") | crontab -
    echo "[OK] 已添加每日定时任务"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  安装完成！                                      ║"
echo "║                                                  ║"
echo "║  手动运行: python3 src/run_daily.py              ║"
echo "║  查看定时: crontab -l                            ║"
echo "║  日志位置: /tmp/dashboard_cron.log               ║"
echo "║                                                  ║"
echo "║  数据文件:                                       ║"
echo "║    data/weight.csv   - 体重记录                  ║"
echo "║    data/fitness.csv  - 健身打卡                  ║"
echo "║    data/tasks.csv    - 任务进度                  ║"
echo "╚══════════════════════════════════════════════════╝"
