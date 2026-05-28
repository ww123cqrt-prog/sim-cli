# CMD/Shell Command Execution Plugin for sim-cli

sim-cli 增强插件，支持安全地执行远程 CMD/Shell 命令。

## 版本

0.1.0

## 功能

- 远程执行 CMD/Shell 命令
- 用户名密码认证
- 远程确认机制 (只需确认一次)
- 超时退出机制
- 支持 CMD、PowerShell、Bash

## 架构

```
本地 Mac (sim-cli) --HTTP--> 远程 Windows (cmd-server:7602) --> CMD/Bash
```

## 安装

```bash
cd plugins/sim-plugin-cmd
pip install -e .
```

## 使用

### 启动服务器 (远程)

```bash
# 基本启动
python cmd_server.py --port 7602 --host 0.0.0.0

# 带安全功能
python cmd_server.py --port 7602 --host 0.0.0.0 \
  --username admin \
  --password mypassword \
  --timeout 600 \
  --require-confirm
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--port` | 监听端口 | 7602 |
| `--host` | 绑定地址 | 0.0.0.0 |
| `--username` | 认证用户名 | 无 |
| `--password` | 认证密码 | 无 |
| `--timeout` | 超时秒数 (0=禁用) | 0 |
| `--require-confirm` | 启用确认机制 | False |

### 连接 (本地)

```bash
# 1. 认证连接
curl -X POST http://<ip>:7602/connect \
  -H "Content-Type: application/json" \
  -d '{"solver": "cmd", "username": "admin", "password": "mypassword"}'

# 2. 确认会话 (只需一次)
curl -X POST http://<ip>:7602/confirm \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<session-id>"}'

# 3. 执行命令
curl -X POST http://<ip>:7602/exec \
  -H "Content-Type: application/json" \
  -d '{"code": "dir", "session_id": "<session-id>"}'

# 4. 断开连接
curl -X POST http://<ip>:7602/disconnect \
  -H "Content-Type: application/json" \
  -H "X-Sim-Session: <session-id>"
```

## 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| GET | /detect/cmd | 检测 CMD |
| POST | /connect | 创建会话 (需认证) |
| POST | /exec | 执行命令 |
| POST | /confirm | 确认会话 |
| POST | /disconnect | 断开会话 |
| GET | /ps | 列出会话 |
| POST | /shutdown | 关闭服务器 |

## 安全功能

### 用户名密码认证

```bash
python cmd_server.py --username admin --password mypassword
```

### 远程确认机制

```bash
python cmd_server.py --require-confirm
```

首次连接后需要调用 `/confirm` 端点确认一次，后续命令无需再次确认。

### 超时退出

```bash
python cmd_server.py --timeout 600  # 10 分钟无活动后自动关闭
```

## 启动脚本

### Windows

```powershell
start-cmd-server.bat 7602 admin mypassword 600
```

### Linux/Mac

```bash
./start-cmd-server.sh 7602 admin mypassword 600
```

## 依赖

- sim-cli-core >= 0.3
- fastapi
- uvicorn

## 许可证

Apache-2.0
