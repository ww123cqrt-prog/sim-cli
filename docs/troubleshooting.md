# Troubleshooting

## `sim` 命令找不到 (Windows)

### 问题

运行 `sim --version` 时报错：
```
sim: The term 'sim' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

### 原因

`sim.exe` 安装在用户级 Scripts 目录：
```
C:\Users\<username>\AppData\Roaming\Python\Python<version>\Scripts\
```

但系统 PATH 中可能只包含系统级 Scripts 目录：
```
C:\Python<version>\Scripts\
```

### 解决方案

**方案 1：使用 `python -m sim`（推荐）**

```bash
python -m sim --version
python -m sim check comsol
python -m sim connect --solver comsol
```

这种方式不依赖 PATH 配置，始终可用。

**方案 2：添加 Scripts 目录到 PATH**

```powershell
# 添加到用户 PATH（永久生效）
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\$env:USERNAME\AppData\Roaming\Python\Python314\Scripts",
    "User"
)

# 重启终端后生效
```

### 验证

```bash
# 方案 1
python -m sim --version

# 方案 2
sim --version
```

## 远程服务器连接问题

### 问题

从另一台电脑连接 sim serve 时超时或拒绝连接。

### 检查清单

1. **防火墙规则**：确保端口已开放
   ```powershell
   New-NetFirewallRule -DisplayName "Sim-COMSOL-7600" -Direction Inbound -LocalPort 7600 -Protocol TCP -Action Allow
   ```

2. **服务器绑定地址**：确保使用 `--host 0.0.0.0`
   ```bash
   python -m sim serve --host 0.0.0.0 --port 7600
   ```

3. **健康检查端点**：
   - COMSOL Server: `GET /ps`
   - Lumerical Server: `GET /health`
   - CMD Server: `GET /health`
   - 所有服务器: `GET /` (返回可用端点列表)
