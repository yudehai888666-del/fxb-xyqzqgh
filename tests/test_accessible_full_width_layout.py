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
