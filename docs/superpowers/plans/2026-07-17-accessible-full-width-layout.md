# 近视友好全宽布局 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让全站界面使用至少 22px 的可读文字，并在桌面端使用接近全屏的内容宽度。

**Architecture:** 共享样式表定义字号、行高、控件尺寸和页面宽度；基础模板在局部页面样式之后加载一个最低字号保护规则，确保模板内部的历史小字号不会覆盖近视友好标准。业务逻辑和模板内容保持不变。

**Tech Stack:** Flask、Jinja2、CSS、pytest。

## Global Constraints

- 普通界面文字最低为 22px，正文默认为 24px。
- 桌面端 `.page` 使用 `calc(100% - 64px)`，不得保留 1120px 最大宽度。
- 输入框、选择框与按钮最小高度为 60px；页面标题为 42px、卡片标题为 30px。
- 手机端仍适配窄屏，并使用 12px 页面边距。

---

### Task 1: 锁定可读性与全宽布局的回归测试

**Files:**
- Create: `tests/test_accessible_full_width_layout.py`
- Consumes: `app/static/styles.css` 与 `app/templates/base.html`。
- Produces: 对最低字号、控件高度、桌面全宽布局及最终覆盖规则的静态回归保护。

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_global_styles_provide_nearsighted_readability_and_full_width_layout():
    styles = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    base_template = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert "--minimum-readable-font-size: 22px" in styles
    assert "font-size: 24px;" in styles
    assert "min-height: 60px;" in styles
    assert "width: calc(100% - 64px);" in styles
    assert "max-width: none;" in styles
    assert "font-size: max(1em, var(--minimum-readable-font-size)) !important;" in base_template
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_accessible_full_width_layout.py -v`

Expected: FAIL because the readable-font CSS variable, full-width rule and final template protection do not yet exist.

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_accessible_full_width_layout.py
git commit -m "test: define accessible full-width layout"
```

### Task 2: 实现共享的近视友好字号与全宽页面规则

**Files:**
- Modify: `app/static/styles.css`
- Modify: `app/templates/base.html`
- Test: `tests/test_accessible_full_width_layout.py`

**Interfaces:**
- Consumes: `--minimum-readable-font-size` from `:root`.
- Produces: 全站 CSS 字号下限及 `.page` 的响应式全宽布局。

- [ ] **Step 1: Write the minimal implementation**

```css
:root {
  --minimum-readable-font-size: 22px;
}

body {
  font-size: 24px;
  line-height: 1.65;
}

.page {
  width: calc(100% - 64px);
  max-width: none;
}

input,
select,
textarea,
.button {
  min-height: 60px;
}
```

Add this final rule after the base template's page content so page-specific style blocks cannot reintroduce unreadably small text:

```html
<style>
  body :where(p, li, dt, dd, label, input, select, textarea, button, th, td, a, span, small, summary, legend) {
    font-size: max(1em, var(--minimum-readable-font-size)) !important;
  }
</style>
```

- [ ] **Step 2: Run the focused test to verify it passes**

Run: `.venv/bin/pytest tests/test_accessible_full_width_layout.py -v`

Expected: PASS.

- [ ] **Step 3: Run the complete regression suite**

Run: `.venv/bin/pytest -q`

Expected: all tests pass.

- [ ] **Step 4: Commit the implementation**

```bash
git add app/static/styles.css app/templates/base.html tests/test_accessible_full_width_layout.py docs/superpowers/specs/2026-07-17-accessible-font-size-design.md docs/superpowers/plans/2026-07-17-accessible-full-width-layout.md
git commit -m "feat: enlarge fonts and use full-width layout"
```

### Task 3: 发布已验证的改动

**Files:**
- No source changes.

**Interfaces:**
- Consumes: `main` 上已经通过测试的提交。
- Produces: GitHub `origin/main` 上可供启动脚本恢复的版本。

- [ ] **Step 1: Confirm the workspace and commit history**

Run: `git status --short && git log -1 --oneline`

Expected: 没有未提交的源代码改动，最新提交为易读字号功能。

- [ ] **Step 2: Push the verified commit**

Run: `git push origin main`

Expected: 输出显示 `main -> main`。
