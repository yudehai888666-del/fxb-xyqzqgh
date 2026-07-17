from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_global_styles_provide_nearsighted_readability_and_full_width_layout():
    styles = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")
    base_template = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert "--minimum-readable-font-size: 22px" in styles
    assert "font-size: 24px;" in styles
    assert "min-height: 60px;" in styles
    assert "width: calc(100% - 64px);" in styles
    assert "max-width: none;" in styles
    assert "font-size: max(1em, var(--minimum-readable-font-size)) !important;" not in base_template


def test_every_declared_ui_font_size_is_at_least_the_readable_minimum():
    css_sources = [ROOT / "app" / "static" / "styles.css"]
    css_sources.extend((ROOT / "app" / "templates").rglob("*.html"))
    small_sizes = []

    for source in css_sources:
        contents = source.read_text(encoding="utf-8")
        for match in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", contents):
            if float(match.group(1)) < 22:
                small_sizes.append(f"{source.relative_to(ROOT)}: {match.group(0)}")
        for match in re.finditer(
            r"font\s*:\s*(?:[^;{}]*?\s)?(\d+(?:\.\d+)?)px\s*/", contents
        ):
            if float(match.group(1)) < 22:
                small_sizes.append(f"{source.relative_to(ROOT)}: {match.group(0)}")

    assert not small_sizes, "\n".join(small_sizes)


def test_public_questionnaire_uses_the_same_full_width_layout():
    page_rules = {
        ROOT / "app" / "templates" / "invitations" / "status.html": ".public-questionnaire-page",
        ROOT / "app" / "templates" / "questionnaires" / "student.html": ".q-page",
        ROOT / "app" / "templates" / "questionnaires" / "parent.html": ".q-page",
        ROOT / "app" / "templates" / "questionnaires" / "materials.html": ".mat-page",
    }

    for template, selector in page_rules.items():
        contents = template.read_text(encoding="utf-8")
        page_rule = re.search(
            rf"{re.escape(selector)}\s*\{{(?P<rules>[^}}]*)\}}", contents
        )
        assert page_rule is not None
        assert re.search(r"max-width\s*:\s*none\s*;", page_rule.group("rules"))
        assert not re.search(r"max-width\s*:\s*\d", page_rule.group("rules"))
