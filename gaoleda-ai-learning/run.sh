#!/usr/bin/env bash
# ============================================================
#  学习AI with William Gao —— 一键启动（macOS / Linux / WSL / 云端容器）
# ============================================================
set -e
cd "$(dirname "$0")"

echo "[1/4] 检查 Python…"
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "  未找到 Python，请先安装 Python 3.10+"
  exit 1
fi
"$PY" --version

if [ ! -d ".venv" ]; then
  echo "[2/4] 创建虚拟环境 .venv …"
  "$PY" -m venv .venv
else
  echo "[2/4] 虚拟环境已存在"
fi

echo "[3/4] 安装依赖…"
./.venv/bin/python -m pip install --upgrade pip -q
./.venv/bin/python -m pip install -r requirements.txt -q

echo "[4/4] 启动服务（默认 http://localhost:8501，Ctrl+C 停止）…"
exec ./.venv/bin/python app.py
