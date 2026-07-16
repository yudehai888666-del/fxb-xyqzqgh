#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
双击启动学业规划本地服务

用法:
  双击桌面上的“启动学业规划.command”
  或在终端运行：./scripts/launch_local.command

流程:
  - 从 Git 仓库恢复 main 最新版
  - 后台启动本地服务
  - 自动打开 http://127.0.0.1:5050
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== 学业规划：本地启动 ==="
./scripts/bootstrap_latest.sh
./scripts/start_local.sh --background

echo "正在打开浏览器..."
open http://127.0.0.1:5050

echo
echo "已发起启动。如果页面没有自动打开，请访问："
echo "http://127.0.0.1:5050"
echo
echo "可以关闭这个终端窗口；服务日志在 logs/local-server.log"
read -r -p "按回车关闭窗口..." _
