# 表单控件可读高度修复报告

## 修复范围

将以下面向用户填写信息的控件固定高度统一为 60px：

- `questionnaires/parent.html`：`.q-input`
- `questionnaires/materials.html`：`.mat-input`、`.mat-select`
- `replanning/new.html`：`.rp-input`、`.rp-select`

图标和进度展示等装饰性元素未纳入该规则。

## 测试驱动验证

新增 `test_named_form_control_classes_do_not_use_fixed_heights_below_60px`，在修改样式前运行失败，列出了上述五个 `height: 42px` 规则。

修改后验证结果：

- `PYTHONPATH=. .venv/bin/pytest -q tests/test_accessible_full_width_layout.py`：7 passed
- `PYTHONPATH=. .venv/bin/pytest -q`：177 passed
- `git diff --check`：通过，无空白错误
