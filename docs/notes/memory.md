# 项目约定记忆

## 健身打卡日历图例位置

- 页面元素：`output/dashboard.html` 中"今天、已打卡"图例（`.cal-legend`）
- 当前参数：`margin-top: 4px`
- **约定**：用户说"上移'今天、已打卡'图例"时，直接**缩小** `margin-top: 4px` 这个值；用户说"下移"时，**增大**该值。

## 健身打卡日历头部间距

- `.cal-header` 的 `margin-bottom`：当前 `2px`
- `.cal-grid.wk` 的 `margin-bottom`：当前 `2px`
- 这两处控制"健身打卡"标题行与星期行（一 二 三…）之间的间距；用户说"调整标题和星期行间距"时改这两个值。

## 通用注意

- 修改以上样式后，需同步到生成脚本 `src/generate_dashboard.py` 中对应的样式，避免重新生成页面时被覆盖。
