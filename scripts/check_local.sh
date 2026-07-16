#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
检查当前版本是否可以启动

用法:
  ./scripts/check_local.sh

检查内容:
  - Python 和 Git 是否可用
  - 关键项目文件是否存在
  - 虚拟环境和依赖文件是否存在
  - 5050 端口是否已经被占用
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="5050"
FAILED=0

cd "$ROOT_DIR"

ok() {
  echo "OK：$1"
}

warn() {
  echo "提示：$1"
}

fail() {
  echo "错误：$1" >&2
  FAILED=1
}

command -v git >/dev/null 2>&1 && ok "Git 可用" || fail "Git 不可用"
command -v python3 >/dev/null 2>&1 && ok "python3 可用" || fail "python3 不可用"

[[ -f "run.py" ]] && ok "启动入口 run.py 存在" || fail "缺少 run.py"
[[ -f "requirements.txt" ]] && ok "依赖文件 requirements.txt 存在" || fail "缺少 requirements.txt"
[[ -f "app/schema.sql" ]] && ok "数据库结构 app/schema.sql 存在" || fail "缺少 app/schema.sql"

if [[ -d ".venv" ]]; then
  ok "虚拟环境 .venv 已存在"
else
  warn "虚拟环境 .venv 不存在，start_local.sh 会自动创建"
fi

if [[ -f "instance/academic_planning.sqlite3" ]]; then
  ok "本地数据库已存在"
else
  warn "本地数据库不存在，应用启动时会自动初始化空数据库"
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  warn "端口 ${PORT} 已被占用；如果这是本项目服务，可以直接打开 http://127.0.0.1:${PORT}"
else
  ok "端口 ${PORT} 可用"
fi

if [[ "$FAILED" -eq 1 ]]; then
  echo "检查未通过，请先处理上面的错误。" >&2
  exit 1
fi

echo "检查完成：当前版本具备启动条件。"
