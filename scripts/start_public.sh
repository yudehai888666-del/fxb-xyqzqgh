#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
开启临时公网访问

用法:
  ./scripts/start_public.sh

说明:
  - 使用独立的认证服务 http://127.0.0.1:5051
  - 优先使用 cloudflared 开启临时公网 tunnel
  - 如果没有 cloudflared，但有 npx，会自动使用 localtunnel
  - 终端里会出现临时公网 https 地址
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="5051"
URL="http://127.0.0.1:${PORT}"

cd "$ROOT_DIR"

if ! curl -fsS "$URL" >/dev/null 2>&1; then
  ./scripts/start_local.sh --background --require-login --port "$PORT"
fi

echo "正在开启临时公网访问..."
echo "本地服务：${URL}"
./scripts/show_login_info.sh

if command -v cloudflared >/dev/null 2>&1; then
  echo "公网地址会在下面的 cloudflared 输出中显示。"
  cloudflared tunnel --url "$URL"
  exit 0
fi

if command -v npx >/dev/null 2>&1; then
  echo "没有找到 cloudflared，改用 npx localtunnel。"
  echo "公网地址会在下面的 localtunnel 输出中显示。"
  npx localtunnel --port "$PORT"
  exit 0
fi

echo "错误：没有找到 cloudflared，也没有找到 npx，无法开启临时公网。" >&2
echo "可选安装方式：" >&2
echo "  brew install cloudflared" >&2
echo "或者安装 Node.js 后使用 npx localtunnel。" >&2
exit 1
