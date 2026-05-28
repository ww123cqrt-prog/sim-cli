# Lumerical FDTD/RCWA Driver for sim-cli

sim-cli 增强插件，支持通过 HTTP 远程调用 Lumerical FDTD/RCWA。

## 版本

1.1.0

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

## 潜在问题与解决方案

### 问题 1: lumapi 无法导入

**现象：** 使用非 Lumerical Python（如 Anaconda）启动服务器时，`import lumapi` 失败。

**原因：** `lumapi` 是 Lumerical 的 Python 绑定，依赖 `interopapi.dll`，而该 DLL 又依赖 Lumerical `bin/` 目录下的 150+ 个 DLL（Qt、VTK、MKL 等）。

**解决方案：** 服务器脚本已内置自动 PATH 设置（v1.1.0+）。启动时会自动将 Lumerical 的 `bin/` 目录添加到 PATH 环境变量。

```python
# 服务器启动时自动执行：
_LUMERICAL_INSTALL = Path(r"C:\Program Files\Ansys Inc\v252\Lumerical")
_LUMERICAL_BIN = _LUMERICAL_INSTALL / "bin"
if _LUMERICAL_BIN.exists():
    os.environ["PATH"] = str(_LUMERICAL_BIN) + ";" + os.environ.get("PATH", "")
```

**验证方法：**
```bash
# 检查服务器日志，应显示：
# [INFO] Added Lumerical bin to PATH: C:\Program Files\Ansys Inc\v252\Lumerical\bin

# 或手动测试：
python -c "import lumapi; print('OK')"
```

### 问题 2: Python 路径配置

**现象：** 服务器无法找到 Lumerical 安装目录。

**解决方案：** 创建 `.pth` 文件让 Anaconda 能找到 lumapi：

```powershell
# 创建 .pth 文件（一次性操作）
Set-Content -Path "C:\Users\11\anaconda3\Lib\site-packages\lumerical.pth" `
  -Value "C:\Program Files\Ansys Inc\v252\Lumerical\api\python" -Encoding UTF8
```

### 问题 3: 版本检测错误

**现象：** v252 被检测为 v241。

**原因：** 早期版本只检查目录名，v252 的目录结构是 `v252/Lumerical/`，父目录名才是版本号。

**解决方案：** 已在 v0.2.0 修复，现在会同时检查目录名和父目录名。

## 许可证

Apache-2.0
