# sim-plugins

sim-cli 增强插件集合，包含 Lumerical FDTD 和 CMD 命令执行功能。

## 插件列表

| 插件 | 版本 | 说明 | 状态 |
|------|------|------|------|
| sim-plugin-lumerical | 0.1.0 | Lumerical FDTD/RCWA 驱动 | ✅ |
| sim-plugin-cmd | 0.1.0 | CMD/Shell 命令执行 | ✅ |

## 架构

```
sim-cli 核心框架
    │
    ├── 官方插件
    │   └── sim-plugin-comsol (GitHub: svd-ai-lab/sim-plugin-comsol)
    │
    └── 本仓库插件 (sim-plugins)
        ├── sim-plugin-lumerical
        │   ├── 远程 HTTP 调用 Lumerical
        │   └── 端口: 7601
        │
        └── sim-plugin-cmd
            ├── 安全的 CMD 命令执行
            ├── 用户名密码认证
            ├── 远程确认机制
            ├── 超时退出
            └── 端口: 7602
```

## 快速安装

```bash
# 克隆仓库
git clone https://github.com/<your-username>/sim-plugins.git
cd sim-plugins

# 安装 Lumerical 插件
cd plugins/sim-plugin-lumerical
pip install -e .

# 安装 CMD 插件
cd ../sim-plugin-cmd
pip install -e .

# 验证安装
sim plugin list
```

## 使用方法

### Lumerical FDTD

```bash
# 启动 Lumerical 服务器 (远程机器)
python lumerical_agent_server.py --port 7601 --host 0.0.0.0

# 连接 (本地)
sim --host <remote-ip> --port 7601 connect --solver lumerical-fdtd
sim --host <remote-ip> --port 7601 --session <id> exec "fdtd.run()"
sim --host <remote-ip> --port 7601 --session <id> disconnect
```

### CMD 命令执行

```bash
# 启动 CMD 服务器 (远程机器，带安全功能)
python cmd_server.py --port 7602 --username admin --password <密码> --timeout 600 --require-confirm

# 连接 (本地)
curl -X POST http://<remote-ip>:7602/connect \
  -H "Content-Type: application/json" \
  -d '{"solver": "cmd", "username": "admin", "password": "<密码>"}'

# 确认会话
curl -X POST http://<remote-ip>:7602/confirm \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<session-id>"}'

# 执行命令
curl -X POST http://<remote-ip>:7602/exec \
  -H "Content-Type: application/json" \
  -d '{"code": "dir", "session_id": "<session-id>"}'
```

## 端口分配

| 端口 | 服务 | 用途 |
|------|------|------|
| 7600 | comsol-server | COMSOL 仿真 (官方插件) |
| 7601 | lumerical-server | Lumerical 仿真 |
| 7602 | cmd-server | CMD 命令执行 |

## 安全功能 (CMD 插件)

- **用户名密码认证**: 连接时需要提供凭据
- **远程确认机制**: 首次连接需确认一次
- **超时退出**: 无活动超时后自动关闭服务器

## 文档

- [安装指南](docs/installation.md)
- [Lumerical 插件文档](plugins/sim-plugin-lumerical/README.md)
- [CMD 插件文档](plugins/sim-plugin-cmd/README.md)

## 依赖

- Python 3.10+
- sim-cli-core >= 0.3
- fastapi (CMD 插件)
- uvicorn (CMD 插件)
- httpx (Lumerical 插件)

## 许可证

Apache-2.0

## 作者

cq

## 相关项目

- [sim-cli](https://github.com/svd-ai-lab/sim-cli) - 统一仿真控制框架
- [sim-plugin-comsol](https://github.com/svd-ai-lab/sim-plugin-comsol) - COMSOL 驱动插件
