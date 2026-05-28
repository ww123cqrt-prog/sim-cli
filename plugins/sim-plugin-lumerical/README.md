# Lumerical FDTD/RCWA Driver for sim-cli

sim-cli 增强插件，支持通过 HTTP 远程调用 Lumerical FDTD/RCWA。

## 版本

0.2.0

## 功能

- 远程 HTTP 调用 Lumerical FDTD/RCWA
- 会话管理
- 结果导出
- **RemoteLumapi 适配器** — 让本地代码像调用本地 lumapi 一样调用远程 Lumerical

## 架构

```
本地 Mac (sim-cli) --HTTP--> 远程 Windows (lumerical-server:7601) --> Lumerical FDTD

本地 Mac (lumerical-for-agent) --> RemoteLumapi --HTTP--> 远程 Windows --> lumapi
```

## 安装

```bash
cd plugins/sim-plugin-lumerical
pip install -e .
```

## 使用

### 方式 1: sim-cli 命令行

```bash
# 启动服务器 (远程 Windows)
python lumerical_agent_server.py --port 7601 --host 0.0.0.0

# 连接 (本地 Mac)
sim --host <ip> --port 7601 connect --solver lumerical-fdtd

# 执行代码
sim --host <ip> --port 7601 --session <id> exec "fdtd.load('project.fsp')"
sim --host <ip> --port 7601 --session <id> exec "fdtd.run()"

# 断开连接
sim --host <ip> --port 7601 --session <id> disconnect
```

### 方式 2: RemoteLumapi 适配器

让本地 Python 代码（如 lumerical-for-agent）像调用本地 lumapi 一样调用远程 Lumerical：

```python
from sim_plugin_lumerical.remote_lumapi import RemoteLumapi

# 连接到远程 Windows（替代本地 lumapi.FDTD()）
fdtd = RemoteLumapi(host="100.65.228.190", port=7601)

# 用法与本地 lumapi 完全一致
fdtd.newproject()
fdtd.addfdtd()
fdtd.addrect()
fdtd.setnamed("rect", "x", 0)
fdtd.setnamed("rect", "y span", 1e-6)
fdtd.addpower()
fdtd.run()
T = fdtd.getresult("T", "T")
fdtd.save("output.fsp")
fdtd.close()
```

也支持 context manager：
```python
with RemoteLumapi(host="100.65.228.190", port=7601) as fdtd:
    fdtd.addfdtd()
    fdtd.run()
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 服务器健康检查 |
| `/detect/{solver}` | GET | 检测 Lumerical 安装 |
| `/connect` | POST | 创建会话 |
| `/exec` | POST | 执行 LSF 代码片段 |
| `/eval` | POST | 执行 Python 代码（返回结构化结果，支持 numpy） |
| `/run` | POST | 一次性脚本执行 |
| `/disconnect` | POST | 断开会话 |

## 依赖

- fastapi
- uvicorn
- httpx >= 0.24
- lumapi（Windows 端由 Lumerical 自带 Python 提供）

## 许可证

Apache-2.0
