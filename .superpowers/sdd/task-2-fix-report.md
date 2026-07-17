# Task 2 corrective-change report

## Scope completed

- Removed the blanket `!important` font-size override from `base.html`.
- Raised every explicit CSS/UI font-size below 22px in `app/static/styles.css` and `app/templates/**/*.html` to `var(--minimum-readable-font-size)`.
- Raised the three font shorthands below 22px to the same minimum variable.
- Preserved headings and metrics already at 22px or larger.
- Made the public invitation status page and all questionnaire page wrappers full width on desktop; their shared `.page` wrapper retains the existing 32px outer margins and 12px mobile side margins.
- Extended the regression suite to reject explicit sub-22px declarations, shorthand font sizes below 22px, the old blanket override, and narrow public/questionnaire page wrappers.

## TDD evidence

Initial required focused run:

```text
PYTHONPATH=. .venv/bin/pytest tests/test_accessible_full_width_layout.py -v
3 failed in 0.03s
```

The failures covered the existing blanket `!important` declaration, multiple sub-22px declarations (including shorthand), and the 700px public questionnaire override. A second focused red run verified the questionnaire wrappers still had their 860px limit before those wrappers were changed.

## Final verification

```text
PYTHONPATH=. .venv/bin/pytest tests/test_accessible_full_width_layout.py -v
3 passed in 0.01s

PYTHONPATH=. .venv/bin/pytest -q
173 passed in 13.55s

git diff --check
exit 0 (no output)
```

## Concerns

No test or whitespace-check concerns remain. Full-width changes apply to outer page wrappers; intentionally compact content elements such as status cards and excerpts retain their local width limits for readable content grouping.
