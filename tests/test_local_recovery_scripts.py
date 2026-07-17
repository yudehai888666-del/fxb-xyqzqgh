import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_scripts_exist_are_executable_and_parse():
    script_names = [
        "bootstrap_latest.sh",
        "check_local.sh",
        "launch_local.command",
        "launch_public.command",
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
        "launch_local.command": "双击启动学业规划本地服务",
        "launch_public.command": "双击启动学业规划临时公网",
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


def test_desktop_launchers_run_recovery_before_starting():
    local_launcher = (ROOT / "scripts" / "launch_local.command").read_text(
        encoding="utf-8"
    )
    public_launcher = (ROOT / "scripts" / "launch_public.command").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "./scripts/bootstrap_latest.sh" in local_launcher
    assert "./scripts/start_local.sh --background" in local_launcher
    assert "open http://127.0.0.1:5050" in local_launcher
    assert "./scripts/bootstrap_latest.sh" in public_launcher
    assert "./scripts/start_public.sh" in public_launcher
    assert "启动学业规划.command" in readme
    assert "启动学业规划-公网.command" in readme


def test_launch_scripts_display_login_credentials():
    expected_scripts = [
        "start_local.sh",
        "start_public.sh",
    ]

    for script_name in expected_scripts:
        script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
        assert "./scripts/show_login_info.sh" in script

    info_script = (ROOT / "scripts" / "show_login_info.sh").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "check-admin" in info_script
    assert "check123456" in info_script
    assert "check-admin" in readme
    assert "check123456" in readme


def test_start_local_prints_login_info_when_server_already_running():
    script = (ROOT / "scripts" / "start_local.sh").read_text(encoding="utf-8")

    already_running_branch = script.split(
        'echo "本地服务已经在运行：${URL}"', maxsplit=1
    )[1].split("exit 0", maxsplit=1)[0]
    assert "./scripts/show_login_info.sh" in already_running_branch


def test_readme_documents_recovery_and_public_start_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "./scripts/bootstrap_latest.sh" in readme
    assert "./scripts/start_local.sh" in readme
    assert "./scripts/start_public.sh" in readme
    assert "临时公网" in readme
    assert "cloudflared" in readme
