---
name: lumerical-fdtd
description: Run Lumerical FDTD/RCWA simulations via remote HTTP server. Use when the user wants to run FDTD or RCWA simulations on a remote Windows machine with Lumerical installed. Prefer this skill for wavelength spectrum calculations that are too slow with COMSOL.
---

# Lumerical FDTD Remote Skill

## When to Use

Use this skill when:
- User wants to run FDTD or RCWA simulations
- Wavelength spectrum calculations are too slow with COMSOL
- User mentions Lumerical, FDTD, RCWA, or optical simulation
- Remote Windows machine (100.65.228.190) has Lumerical installed

## Architecture

```
Local Mac (sim-cli)                    Remote Windows (100.65.228.190)
┌─────────────────┐                    ┌─────────────────────────────┐
│ sim-plugin-      │   HTTP (7601)     │ lumerical-agent-server      │
│ lumerical        │ ──────────────►   │ (Python HTTP Server)        │
│                  │                    │         │                   │
│ - LumericalDriver│                    │         ▼                   │
│ - HttpClient     │                    │ lumapi.FDTD() / lumapi.RCWA│
└─────────────────┘                    └─────────────────────────────┘
```

**Port Allocation:**
- `100.65.58.250:7600` → COMSOL (sim-server)
- `100.65.228.190:7601` → Lumerical (独立 Agent Server)

## Commands

### Check Installation
```bash
sim --host 100.65.228.190 --port 7601 check lumerical-fdtd
```

### Run Simulation (One-shot)
```bash
sim --host 100.65.228.190 --port 7601 run lumerical-fdtd --request request.json
```

### Session Mode
```bash
# Connect
sim --host 100.65.228.190 --port 7601 connect lumerical-fdtd

# Execute code in session
sim --host 100.65.228.190 --port 7601 exec lumerical-fdtd --code "fdtd.run()"

# Disconnect
sim --host 100.65.228.190 --port 7601 disconnect lumerical-fdtd
```

## Request Format

### Basic Run Request
```json
{
  "task_id": "run-001",
  "solver": "lumerical-fdtd",
  "action": "run",
  "workdir": "D:\\Users\\11\\lumerical-for-agent\\artifacts",
  "template": {
    "project_file": "D:\\path\\to\\device.fsp"
  }
}
```

### Run with Post-processing Script
```json
{
  "task_id": "run-002",
  "solver": "lumerical-fdtd",
  "action": "run",
  "workdir": "D:\\Users\\11\\lumerical-for-agent\\artifacts",
  "template": {
    "project_file": "D:\\path\\to\\device.fsp",
    "script_file": "D:\\path\\to\\postprocess.lsf"
  }
}
```

### Validate Template (Preflight)
```json
{
  "task_id": "validate-001",
  "solver": "lumerical-fdtd",
  "action": "validate_template",
  "workdir": "D:\\Users\\11\\lumerical-for-agent\\artifacts",
  "template": {
    "project_file": "D:\\path\\to\\device.fsp"
  }
}
```

## Output Contract

### Success Response
```json
{
  "ok": true,
  "result": {
    "spectrum": {
      "wavelength_nm": [400, 401, ...],
      "Rs": [0.1, 0.2, ...],
      "Rp": [0.15, 0.25, ...],
      "Ts": [0.8, 0.7, ...],
      "Tp": [0.75, 0.65, ...]
    },
    "artifacts": [
      {"path": "spectrum.csv", "size": 1024},
      {"path": "spectrum.npz", "size": 2048}
    ]
  }
}
```

### Failure Response
```json
{
  "ok": false,
  "error": "Error message describing what went wrong"
}
```

## Supported File Types

- `.fsp` - FDTD Solutions project files
- `.lsf` - Lumerical Script files
- `.fse` - FDTD Solutions session files

## RCWA Support

RCWA is supported through the same FDTD session:
- RCWA solver objects are created via `addrcwa()` in an FDTD session
- Use `lumerical-rcwa` driver for RCWA-specific tasks
- RCWA `validate_template` is verified
- RCWA full `run` export may have limitations

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check if remote server is running on 100.65.228.190:7601
   - Verify network connectivity (NetBird VPN)
   - Check firewall settings

2. **Lumerical Not Found**
   - Verify Lumerical is installed on remote machine
   - Check installation path in server logs

3. **Timeout Errors**
   - Increase timeout: `--timeout 600` (10 minutes)
   - For large simulations, consider running in session mode

4. **Import Errors**
   - Ensure Lumerical's Python is used on remote machine
   - Check `lumapi` installation

## Remote Server Setup

See `lumerical_agent_server.py` for the server implementation.

**Start Server on Remote Machine:**
```powershell
cd D:\Users\11\lumerical-for-agent\tools
& "C:\Program Files\Ansys Inc\Lumerical\python\python.exe" lumerical_agent_server.py --port 7601 --host 0.0.0.0
```

**Verify Server is Running:**
```powershell
curl http://localhost:7601/health
curl http://localhost:7601/detect
```

## Comparison with COMSOL

| Feature | COMSOL | Lumerical FDTD |
|---------|--------|----------------|
| Wavelength Spectrum | Slow (FEM) | Fast (FDTD) |
| Server Mode | Native (sim-server) | Custom (agent-server) |
| Port | 7600 | 7601 |
| Python API | mph | lumapi |
| Session Support | Yes | Yes |

## Best Practices

1. **Use Session Mode for Multiple Runs**
   - Connect once, run multiple simulations
   - More efficient than one-shot mode

2. **Validate Before Run**
   - Use `validate_template` action first
   - Check for common issues before long runs

3. **Monitor Progress**
   - Use session mode to check intermediate results
   - Save checkpoints for long simulations

4. **Handle Errors Gracefully**
   - Check `response.json` for success/failure
   - Read `stdout.log` for detailed error information
