#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
启动本地服务

用法:
  ./scripts/start_local.sh
  ./scripts/start_local.sh --background

默认地址:
  http://127.0.0.1:5050

说明:
  - 自动创建 .venv
  - 自动安装 requirements.txt
  - 自动生成本地 secret key
  - 前台模式按 Ctrl+C 停止
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

BACKGROUND=0
if [[ "${1:-}" == "--background" ]]; then
  BACKGROUND=1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="5050"
URL="http://127.0.0.1:${PORT}"

cd "$ROOT_DIR"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "本地服务已经在运行：${URL}"
    exit 0
  fi
  echo "错误：端口 ${PORT} 已被其他程序占用。" >&2
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2 || true
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "正在创建虚拟环境 .venv..."
  python3 -m venv .venv
fi

echo "正在确认 Python 依赖..."
.venv/bin/python -m pip install -r requirements.txt

mkdir -p instance logs

if [[ ! -f "instance/.secret-key" ]]; then
  .venv/bin/python - <<'PY' > instance/.secret-key
import secrets
print(secrets.token_hex(32))
PY
  chmod 600 instance/.secret-key
fi

export ACADEMIC_PLANNING_SECRET_KEY
ACADEMIC_PLANNING_SECRET_KEY="$(cat instance/.secret-key)"

if [[ "$BACKGROUND" -eq 1 ]]; then
  echo "正在后台启动本地服务..."
  nohup .venv/bin/python run.py > logs/local-server.log 2>&1 &
  echo "$!" > logs/local-server.pid

  for _ in $(seq 1 30); do
    if curl -fsS "$URL" >/dev/null 2>&1; then
      echo "本地服务已启动：${URL}"
      echo "日志文件：logs/local-server.log"
      exit 0
    fi
    sleep 1
  done

  echo "错误：服务没有在预期时间内启动，请查看 logs/local-server.log" >&2
  exit 1
fi

echo "本地服务启动中：${URL}"
echo "停止服务：在这个终端按 Ctrl+C"
.venv/bin/python run.py
