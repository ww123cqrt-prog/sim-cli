# Lumerical FDTD/RCWA Driver for sim-cli

sim-cli 增强插件，支持通过 HTTP 远程调用 Lumerical FDTD/RCWA。

## 版本

0.1.0

## 功能

- 远程 HTTP 调用 Lumerical FDTD
- 支持 RCWA 求解器
- 会话管理
- 结果导出

## 架构

```
本地 Mac (sim-cli) --HTTP--> 远程 Windows (lumerical-server:7601) --> Lumerical FDTD
```

## 安装

```bash
cd plugins/sim-plugin-lumerical
pip install -e .
```

## 使用

```bash
# 启动服务器 (远程)
python lumerical_agent_server.py --port 7601 --host 0.0.0.0

# 连接 (本地)
sim --host <ip> --port 7601 connect --solver lumerical-fdtd

# 执行代码
sim --host <ip> --port 7601 --session <id> exec "fdtd.load('project.fsp')"
sim --host <ip> --port 7601 --session <id> exec "fdtd.run()"

# 断开连接
sim --host <ip> --port 7601 --session <id> disconnect
```

## 依赖

- sim-cli-core >= 0.3
- httpx >= 0.24
- fastapi
- uvicorn

## 许可证

Apache-2.0
