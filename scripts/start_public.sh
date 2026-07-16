#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
开启临时公网访问

用法:
  ./scripts/start_public.sh

说明:
  - 会先确认本地服务运行在 http://127.0.0.1:5050
  - 然后使用 cloudflared 开启临时公网 tunnel
  - 终端里会出现 https://*.trycloudflare.com 临时访问地址
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="5050"
URL="http://127.0.0.1:${PORT}"

cd "$ROOT_DIR"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "错误：没有找到 cloudflared，无法开启临时公网。" >&2
  echo "macOS 可执行：" >&2
  echo "  brew install cloudflared" >&2
  echo "安装后重新执行：" >&2
  echo "  ./scripts/start_public.sh" >&2
  exit 1
fi

if ! curl -fsS "$URL" >/dev/null 2>&1; then
  ./scripts/start_local.sh --background
fi

echo "正在开启临时公网访问..."
echo "本地服务：${URL}"
echo "公网地址会在下面的 cloudflared 输出中显示。"
cloudflared tunnel --url "$URL"
