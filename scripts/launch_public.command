#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
双击启动学业规划临时公网

用法:
  双击桌面上的“启动学业规划-公网.command”
  或在终端运行：./scripts/launch_public.command

流程:
  - 从 Git 仓库恢复 main 最新版
  - 启动本地服务
  - 开启临时公网地址
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== 学业规划：临时公网启动 ==="
./scripts/bootstrap_latest.sh
./scripts/start_public.sh
