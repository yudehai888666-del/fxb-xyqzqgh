# 可访问性与全宽布局最终修复报告

## 修复范围

- 将 `questionnaires.disclaimer_template` 生成的免责声明页面改为全宽外层布局：桌面两侧各 32px、移动端两侧各 12px。
- 将该生成页面的正文提升至 24px，一级标题提升至 42px，二级标题提升至 30px，并移除所有低于 22px 的可见字号。
- 将文件档案的可见范围选择框、规划详情的可见范围选择框和老师记录的语音输入按钮提升至最小 60px 高度。
- 移除重规划页面 `.rp-page` 的 960px 外层宽度限制。
- 移除登录页 420px 宽度限制，改为桌面 32px、移动端 12px 外边距内的全宽登录界面。

## 测试先行记录

先在 `tests/test_accessible_full_width_layout.py` 新增回归测试，再运行：

```sh
PYTHONPATH=. .venv/bin/pytest -q tests/test_accessible_full_width_layout.py
```

新增测试在修复前的结果为 `3 failed, 3 passed`：

- 生成免责声明使用了 14px 正文、20px 标题、800px 最大宽度等不符合要求的样式。
- 三个可见控件的最小高度分别为 36px、38px、42px。
- 重规划页面仍限制为 960px 宽度。

修复后，同一聚焦测试结果为 `6 passed`。

## 最终验证

```sh
PYTHONPATH=. .venv/bin/pytest -q tests/test_accessible_full_width_layout.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

结果：聚焦测试 `6 passed`；完整测试集 `176 passed`；`git diff --check` 无输出且退出成功。

## 注意事项

- 免责声明页面仍保留 A4 打印媒体规则；打印时由浏览器的页面边距控制纸张留白，屏幕阅读则使用全宽布局。
- 登录页已按要求扩展为全宽；在超宽显示器上，表单区域会占用可用宽度，不再是居中的窄卡片。
