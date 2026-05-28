# 安装指南

本文档介绍如何安装 sim-plugins 中的插件。

## 前置条件

```bash
# 检查 Python 版本 (需要 3.10+)
python --version

# 检查 sim-cli 是否已安装
sim --version

# 如果未安装，执行:
pip install sim-cli-core
```

## 安装插件

### 1. 安装 Lumerical 插件

```bash
cd plugins/sim-plugin-lumerical
pip install -e .

# 验证
sim check lumerical-fdtd
sim plugin list | grep lumerical
```

### 2. 安装 CMD 插件

```bash
cd plugins/sim-plugin-cmd
pip install -e .

# 验证
sim check cmd
sim plugin list | grep cmd
```

## 启动服务

### Lumerical Server

```bash
# 在远程 Windows 机器上
cd plugins/sim-plugin-lumerical
python lumerical_agent_server.py --port 7601 --host 0.0.0.0
```

### CMD Server

```bash
# 在远程 Windows 机器上 (带安全功能)
cd plugins/sim-plugin-cmd
python cmd_server.py --port 7602 --host 0.0.0.0 \
  --username admin \
  --password <你的密码> \
  --timeout 600 \
  --require-confirm
```

## 配置防火墙

```powershell
# Windows PowerShell (管理员)
netsh advfirewall firewall add rule name="Lumerical Server (7601)" dir=in action=allow protocol=TCP localport=7601
netsh advfirewall firewall add rule name="CMD Server (7602)" dir=in action=allow protocol=TCP localport=7602
```

## 验证连接

```bash
# 测试 Lumerical
sim --host <remote-ip> --port 7601 check lumerical-fdtd

# 测试 CMD
curl http://<remote-ip>:7602/health
```

## 卸载插件

```bash
pip uninstall sim-plugin-lumerical
pip uninstall sim-plugin-cmd
```
