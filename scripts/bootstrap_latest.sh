#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
从 Git 仓库恢复最新代码

用法:
  ./scripts/bootstrap_latest.sh [branch]

默认行为:
  - 使用当前项目的 origin 远端
  - 默认拉取 main 分支
  - 本地有未提交改动时会停止，避免覆盖开发现场
  - 只允许 fast-forward 更新，避免自动制造合并提交
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

BRANCH="${1:-main}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "错误：当前目录不是 Git 仓库：$ROOT_DIR" >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "错误：没有找到 origin 远端，请先配置 Git 仓库地址。" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  echo "已停止：当前目录有未提交或未跟踪改动。" >&2
  echo "请先提交、暂存或移走这些改动，再重新执行：" >&2
  echo "  ./scripts/bootstrap_latest.sh ${BRANCH}" >&2
  exit 1
fi

echo "正在从 Git 仓库获取最新信息..."
git fetch origin "$BRANCH"

if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" "origin/${BRANCH}"
fi

echo "正在更新 ${BRANCH} 到 origin/${BRANCH} 的最新版本..."
git pull --ff-only origin "$BRANCH"

echo "已恢复到 Git 仓库保存的最新 ${BRANCH}。"
echo "下一步可以执行："
echo "  ./scripts/start_local.sh"
