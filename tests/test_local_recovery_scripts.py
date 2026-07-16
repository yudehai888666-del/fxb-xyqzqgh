import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_scripts_exist_are_executable_and_parse():
    script_names = [
        "bootstrap_latest.sh",
        "check_local.sh",
        "start_local.sh",
        "start_public.sh",
    ]

    for script_name in script_names:
        script_path = ROOT / "scripts" / script_name
        assert script_path.exists(), f"{script_name} should exist"
        mode = script_path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{script_name} should be executable"
        subprocess.run(["bash", "-n", str(script_path)], check=True)


def test_recovery_scripts_explain_their_purpose_in_chinese_help():
    expected_help = {
        "bootstrap_latest.sh": "从 Git 仓库恢复最新代码",
        "check_local.sh": "检查当前版本是否可以启动",
        "start_local.sh": "启动本地服务",
        "start_public.sh": "开启临时公网访问",
    }

    for script_name, expected_text in expected_help.items():
        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / script_name), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert expected_text in result.stdout


def test_public_start_supports_cloudflared_and_localtunnel_fallback():
    script = (ROOT / "scripts" / "start_public.sh").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "cloudflared tunnel --url" in script
    assert "npx localtunnel" in script
    assert "localtunnel" in readme


def test_readme_documents_recovery_and_public_start_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "./scripts/bootstrap_latest.sh" in readme
    assert "./scripts/start_local.sh" in readme
    assert "./scripts/start_public.sh" in readme
    assert "临时公网" in readme
    assert "cloudflared" in readme
