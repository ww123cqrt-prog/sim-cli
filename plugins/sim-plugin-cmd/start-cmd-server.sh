#!/bin/bash
# CMD Server 启动脚本（带安全功能）
# 用法: ./start-cmd-server.sh [端口] [用户名] [密码] [超时秒数]

PORT=${1:-7602}
USERNAME=${2:-admin}
PASSWORD=${3:-changeme}
TIMEOUT=${4:-600}

echo "========================================"
echo "  CMD Server 启动"
echo "========================================"
echo "  端口: $PORT"
echo "  用户名: $USERNAME"
echo "  超时: $TIMEOUT 秒"
echo "========================================"
echo ""

# 启动服务器（带认证和超时）
python -m sim serve --port $PORT --host 0.0.0.0 --username $USERNAME --password $PASSWORD --timeout $TIMEOUT --require-confirm
