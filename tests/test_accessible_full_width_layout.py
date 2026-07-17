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


def test_generated_disclaimer_uses_readable_type_and_full_width_outer_layout():
    route_source = (ROOT / "app" / "routes" / "questionnaires.py").read_text(
        encoding="utf-8"
    )
    stylesheet = route_source.split('html = f"""', 1)[1].split('"""', 1)[0]

    assert "font-size: 24px;" in stylesheet
    assert "width: calc(100% - 64px);" in stylesheet
    assert "max-width: none;" in stylesheet
    assert "padding: 32px 0;" in stylesheet
    assert "font-size: 42px;" in stylesheet
    assert "h2 {{ font-size: 30px;" in stylesheet
    assert "@media (max-width: 700px)" in stylesheet
    assert "width: calc(100% - 24px);" in stylesheet

    undersized = []
    for match in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", stylesheet):
        if float(match.group(1)) < 22:
            undersized.append(match.group(0))
    for match in re.finditer(r"font\s*:\s*(?:[^;{}]*?\s)?(\d+(?:\.\d+)?)px\s*/", stylesheet):
        if float(match.group(1)) < 22:
            undersized.append(match.group(0))

    assert not undersized, "\n".join(undersized)


def test_visible_controls_never_shrink_below_60px():
    css_sources = [ROOT / "app" / "static" / "styles.css"]
    css_sources.extend((ROOT / "app" / "templates").rglob("*.html"))
    undersized_controls = []

    for source in css_sources:
        contents = source.read_text(encoding="utf-8")
        for rule in re.finditer(r"(?P<selector>[^{}]+)\{(?P<rules>[^{}]*)\}", contents):
            if not re.search(r"(?:input|select|textarea|button)", rule.group("selector")):
                continue
            for height in re.finditer(
                r"min-height\s*:\s*(\d+(?:\.\d+)?)px", rule.group("rules")
            ):
                if float(height.group(1)) < 60:
                    undersized_controls.append(
                        f"{source.relative_to(ROOT)}: {rule.group('selector').strip()} "
                        f"({height.group(0)})"
                    )

    assert not undersized_controls, "\n".join(undersized_controls)


def test_replanning_and_login_outer_layouts_use_available_width():
    replanning = (ROOT / "app" / "templates" / "replanning" / "new.html").read_text(
        encoding="utf-8"
    )
    replanning_page = re.search(r"\.rp-page\s*\{(?P<rules>[^}]*)\}", replanning)
    assert replanning_page is not None
    assert "width: 100%;" in replanning_page.group("rules")
    assert "max-width: none;" in replanning_page.group("rules")
    assert not re.search(r"max-width\s*:\s*\d", replanning_page.group("rules"))

    login = (ROOT / "app" / "templates" / "auth" / "login.html").read_text(
        encoding="utf-8"
    )
    assert ".login-page{min-height:100vh;display:grid;place-items:center;padding:32px}" in login
    assert ".login-card{width:100%;max-width:none;" in login
    assert "420px" not in login
    assert "@media(max-width:700px){.login-page{padding:12px}" in login
