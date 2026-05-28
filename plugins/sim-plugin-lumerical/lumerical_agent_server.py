#!/usr/bin/env python3
"""Lumerical Agent Server — sim-cli compatible HTTP server for Lumerical simulations.

Fully compatible with the sim-cli HTTP API protocol. Accepts the same
endpoint shapes as sim/server.py so that `sim --host <remote> --port 7601`
can drive Lumerical FDTD/INTERCONNECT sessions transparently.

Architecture:
    Local Mac (sim-cli) --HTTP--> Remote Windows (lumerical-agent-server) --> Lumerical FDTD

Dependencies:
    # Option 1: Use Lumerical's bundled Python (recommended, lumapi included)
    & "C:\Program Files\Ansys Inc\Lumerical\python\python.exe" -m pip install fastapi uvicorn

    # Option 2: System Python
    pip install fastapi uvicorn lumapi

    # lumapi is typically found at:
    #   C:\\Program Files\\Ansys Inc\\Lumerical\\vXXX\\api\\python\\lumapi.py
    # Add it to PYTHONPATH or install via Lumerical's Python.

Usage:
    # Using Lumerical's bundled Python (recommended)
    & "C:\Program Files\Ansys Inc\Lumerical\python\python.exe" lumerical_agent_server.py

    # Or system Python
    python lumerical_agent_server.py --port 7601 --host 0.0.0.0
"""
from __future__ import annotations

import math
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# ── Logging ──────────────────────────────────────────────────────────────────

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("lumerical-agent-server")


# ── Lumerical PATH setup ────────────────────────────────────────────────────
# Add Lumerical's bin directory to PATH so interopapi.dll can find its dependencies.
# This allows using any Python (e.g. Anaconda) to import lumapi.
_LUMERICAL_INSTALL = Path(r"C:\Program Files\Ansys Inc\v252\Lumerical")
_LUMERICAL_BIN = _LUMERICAL_INSTALL / "bin"
if _LUMERICAL_BIN.exists():
    _bin_str = str(_LUMERICAL_BIN)
    if _bin_str not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _bin_str + ";" + os.environ.get("PATH", "")
        log.info("Added Lumerical bin to PATH: %s", _bin_str)


# ── NaN-safe JSON ────────────────────────────────────────────────────────────

def _sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize an object for JSON serialization.

    Handles: NaN/Inf floats, numpy arrays, nested dicts/lists.
    """
    # numpy array → nested list
    if hasattr(obj, "tolist"):
        return obj.tolist()
    # numpy scalar → Python scalar
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


class _NaNSafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(_sanitize_for_json(content))


# ── Lumerical discovery helpers ──────────────────────────────────────────────

def find_lumerical_install() -> Path | None:
    """Find the Lumerical installation directory."""
    candidates = [
        Path(r"C:\Program Files\Ansys Inc\v252\Lumerical"),
        Path(r"C:\Program Files\Ansys Inc\Lumerical"),
        Path(r"C:\Program Files\Lumerical"),
        Path(r"D:\Program Files\Ansys Inc\Lumerical"),
        Path(r"D:\Program Files\Lumerical"),
        Path(r"D:\Program Files\Lumerical\v241"),
    ]
    for base_path in candidates:
        if base_path.exists():
            # Check if directory name itself is a version (e.g., v241)
            if base_path.name.startswith("v") and base_path.name[1:].isdigit():
                return base_path
            # Check parent directory name (e.g., ...\v252\Lumerical)
            if base_path.parent.name.startswith("v") and base_path.parent.name[1:].isdigit():
                return base_path
            # Look for version subdirectories
            version_dirs = [
                d for d in base_path.iterdir()
                if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
            ]
            if version_dirs:
                return sorted(version_dirs, reverse=True)[0]
    return None


def find_python_path(install_path: Path) -> Path | None:
    """Find the Python executable bundled with Lumerical."""
    candidates = [
        install_path / "python" / "python.exe",
        install_path / "python-3.13.1" / "python.exe",
        install_path / "python-3.12" / "python.exe",
        install_path / "python-3.11" / "python.exe",
        install_path / "python-3.10" / "python.exe",
    ]
    for item in install_path.iterdir():
        if item.is_dir() and item.name.startswith("python-"):
            python_exe = item / "python.exe"
            if python_exe.exists():
                candidates.insert(0, python_exe)
    for python_path in candidates:
        if python_path.exists():
            return python_path
    return None


def _import_lumapi():
    """Import lumapi; log a hint if it fails."""
    try:
        import lumapi
        return lumapi
    except ImportError:
        install = find_lumerical_install()
        if install:
            py = find_python_path(install)
            if py:
                log.warning("lumapi not found in current Python. Use Lumerical's Python: %s", py)
        raise


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="lumerical-agent-server",
    version="1.1.0",
    default_response_class=_NaNSafeJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ───────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    solver: str = "lumerical-fdtd"
    mode: str = "solver"
    ui_mode: str = "no_gui"
    processors: int = 1
    workspace: str | None = None
    driver_options: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    script: str
    solver: str = "lumerical-fdtd"


# ── Session state ────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    session_id: str
    solver: str
    mode: str | None = None
    ui_mode: str | None = None
    processors: int = 1
    workspace: str | None = None
    driver_options: dict = field(default_factory=dict)
    connected_at: float | None = None
    run_count: int = 0
    runs: list[dict] = field(default_factory=list)
    fdtd: Any = field(default=None, repr=False)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


_sessions: dict[str, SessionState] = {}
_sessions_lock = threading.Lock()


def _select_session(header_val: str | None) -> SessionState:
    with _sessions_lock:
        if header_val:
            s = _sessions.get(header_val)
            if s is None:
                raise HTTPException(404, f"unknown session_id: {header_val}")
            return s
        if len(_sessions) == 1:
            return next(iter(_sessions.values()))
        if not _sessions:
            raise HTTPException(400, "no active sessions — POST /connect first")
        raise HTTPException(
            400,
            f"{len(_sessions)} sessions live; set X-Sim-Session header or use `sim --session <id>`",
        )


def _register_session(state: SessionState) -> None:
    with _sessions_lock:
        _sessions[state.session_id] = state


def _drop_session(session_id: str) -> SessionState | None:
    with _sessions_lock:
        return _sessions.pop(session_id, None)


def _list_sessions() -> list[SessionState]:
    with _sessions_lock:
        return list(_sessions.values())


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/version")
def version():
    return {"version": app.version}


@app.get("/health")
def health():
    install = find_lumerical_install()
    return {
        "ok": True,
        "data": {
            "status": "healthy",
            "solver": "lumerical-fdtd",
            "installed": install is not None,
            "install_path": str(install) if install else None,
            "active_sessions": len(_sessions),
        },
    }


@app.get("/detect/{solver}")
def detect_solver(solver: str):
    """Detect Lumerical installations on this host.

    Returns the same shape as sim/server.py /detect/{solver}.
    """
    if not solver.startswith("lumerical"):
        raise HTTPException(404, f"unknown solver: {solver}")

    install = find_lumerical_install()
    installs: list[dict] = []
    resolutions: list[dict] = []

    if install:
        # Extract version from directory name or parent directory name
        if install.name.startswith("v") and install.name[1:].isdigit():
            version = install.name[1:]
        elif install.parent.name.startswith("v") and install.parent.name[1:].isdigit():
            version = install.parent.name[1:]
        else:
            version = install.name
        python_path = find_python_path(install)
        inst_dict = {
            "name": solver,
            "version": version,
            "path": str(install),
            "source": "filesystem-scan",
            "extra": {
                "has_python": python_path is not None,
                "python_path": str(python_path) if python_path else None,
            },
        }
        installs.append(inst_dict)
        resolutions.append({"install": inst_dict, "profile": None})

    return {
        "ok": True,
        "data": {
            "solver": solver,
            "installs": installs,
            "resolutions": resolutions,
            "compatibility": None,
        },
    }


@app.post("/connect")
def connect(req: ConnectRequest):
    """Open a Lumerical session. Returns the same shape as sim/server.py /connect."""
    if not req.solver.startswith("lumerical"):
        raise HTTPException(400, f"unsupported solver: {req.solver}")

    # Check for existing session on the same solver
    with _sessions_lock:
        for s in _sessions.values():
            if s.solver == req.solver:
                raise HTTPException(
                    400,
                    f"a {req.solver} session is already live (id={s.session_id}); "
                    "two concurrent sessions on the same driver aren't supported yet",
                )

    # Validate lumapi is importable and create FDTD instance
    try:
        lumapi = _import_lumapi()
        fdtd = lumapi.FDTD()
    except ImportError as e:
        raise HTTPException(500, f"lumapi not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"failed to create FDTD instance: {e}")

    sid = f"s-{uuid.uuid4().hex[:8]}"
    state = SessionState(
        session_id=sid,
        solver=req.solver,
        mode=req.mode,
        ui_mode=req.ui_mode,
        processors=req.processors,
        workspace=req.workspace,
        driver_options=req.driver_options,
        connected_at=time.time(),
        run_count=0,
        runs=[],
        fdtd=fdtd,
    )
    _register_session(state)

    return {
        "ok": True,
        "data": {
            "session_id": state.session_id,
            "solver": req.solver,
            "mode": state.mode,
            "ui_mode": state.ui_mode,
            "workspace": state.workspace,
            "driver_options": state.driver_options,
            "connected_at": state.connected_at,
            "run_count": 0,
            "profile": None,
            "skills": [],
            "tools": [],
            "tool_refs": [],
            "launch_options": {},
        },
    }


@app.post("/exec")
def exec_snippet(
    req: dict[str, Any],
    x_sim_session: str | None = Header(default=None, alias="X-Sim-Session"),
):
    """Execute a code snippet in a live Lumerical session."""
    code = req.get("code", "")
    label = req.get("label", "snippet")

    state = _select_session(x_sim_session)
    with state.lock:
        start = time.monotonic()
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        errors: list[str] = []
        ok = True

        if state.fdtd is None:
            stderr_parts.append("no active FDTD instance — POST /connect first")
            errors.append("no active FDTD instance")
            ok = False
        else:
            try:
                result_val = state.fdtd.eval(code)
                if result_val is not None:
                    stdout_parts.append(str(result_val))
            except Exception as e:
                stderr_parts.append(str(e))
                errors.append(str(e))
                ok = False

        duration = time.monotonic() - start
        stdout = "\n".join(stdout_parts).strip()
        stderr = "\n".join(stderr_parts).strip()

        result = {
            "ok": ok,
            "session_id": state.session_id,
            "label": label,
            "stdout": stdout,
            "stderr": stderr,
            "errors": errors,
            "duration_s": round(duration, 3),
            "started_at": time.time(),
        }
        state.runs.append(result)
        state.run_count += 1

    return {"ok": ok, "data": result}


@app.post("/eval")
def eval_python(
    req: dict[str, Any],
    x_sim_session: str | None = Header(default=None, alias="X-Sim-Session"),
):
    """Execute Python code with access to the fdtd object.

    Unlike /exec which runs LSF code via fdtd.eval(), /eval runs
    Python code where `fdtd` is available as a local variable.
    Results are properly serialized (numpy arrays → nested lists).

    Used by RemoteLumapi adapter to call lumapi methods like:
        fdtd.getresult("monitor", "T")
        fdtd.addrect()
        fdtd.setnamed("::model::", "x", 0)
    """
    code = req.get("code", "")
    session_id = req.get("session_id")
    state = _select_session(session_id or x_sim_session)

    with state.lock:
        start = time.monotonic()
        ok = True
        result_val = None
        error = None

        if state.fdtd is None:
            ok = False
            error = "no active FDTD instance — POST /connect first"
        else:
            try:
                exec_globals = {"fdtd": state.fdtd, "__builtins__": __builtins__}
                result_val = eval(code, exec_globals)
                if result_val is not None:
                    try:
                        result_val = _sanitize_for_json(result_val)
                    except Exception:
                        result_val = None
            except SyntaxError:
                try:
                    exec_locals: dict[str, Any] = {"fdtd": state.fdtd}
                    exec(code, {"__builtins__": __builtins__}, exec_locals)
                    if "result" in exec_locals:
                        result_val = exec_locals["result"]
                        try:
                            result_val = _sanitize_for_json(result_val)
                        except Exception:
                            result_val = None
                except Exception as e:
                    ok = False
                    error = str(e)
            except Exception as e:
                ok = False
                error = str(e)

        duration = time.monotonic() - start

    return {
        "ok": ok,
        "data": {
            "result": result_val,
            "session_id": state.session_id,
            "duration_s": round(duration, 3),
            "error": error,
        },
    }


@app.post("/run")
def run_script(req: RunRequest):
    """One-shot script execution — no session required.

    Compatible with sim/server.py /run endpoint shape.
    """
    script_path = Path(req.script)
    if not script_path.is_file():
        raise HTTPException(400, f"script not found: {req.script}")

    if not req.solver.startswith("lumerical"):
        raise HTTPException(400, f"unsupported solver: {req.solver}")

    start = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    errors: list[str] = []
    artifacts: list[dict] = []
    fdtd = None

    try:
        lumapi = _import_lumapi()
        fdtd = lumapi.FDTD()

        suffix = script_path.suffix.lower()

        if suffix == ".fsp":
            # Binary project file — load directly
            fdtd.load(str(script_path))
            stdout_parts.append(f"[lumerical] loaded project: {script_path.name}")
        else:
            # Text script (.lsf, .py, etc.) — read and eval
            script_content = script_path.read_text(encoding="utf-8")
            try:
                fdtd.eval(script_content)
            except Exception as e:
                stderr_parts.append(str(e))
                errors.append(f"[lumapi] {e}")

        # Export common outputs using Lumerical script commands
        workdir = str(script_path.parent)
        try:
            spectrum_file = os.path.join(workdir, "spectrum.csv").replace("\\", "/")
            # Use Lumerical script to export transmission data
            fdtd.eval(f'T = getresult("monitor", "T"); csvwrite("{spectrum_file}", T);')
            if os.path.exists(spectrum_file):
                artifacts.append({
                    "path": spectrum_file,
                    "kind": "exported",
                    "size": os.path.getsize(spectrum_file),
                })
        except Exception:
            pass
    except ImportError as e:
        stderr_parts.append(f"lumapi import failed: {e}")
        errors.append(f"lumapi import failed: {e}")
    except Exception as e:
        stderr_parts.append(str(e))
        errors.append(str(e))
    finally:
        if fdtd is not None:
            try:
                fdtd.close()
            except Exception:
                pass

    duration = time.monotonic() - start
    stdout = "\n".join(stdout_parts).strip()
    stderr = "\n".join(stderr_parts).strip()
    exit_code = 0 if not errors else 1

    return {
        "ok": exit_code == 0,
        "data": {
            "exit_code": exit_code,
            "ok": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "errors": errors,
            "duration_s": round(duration, 3),
            "script": str(script_path),
            "solver": req.solver,
            "timestamp": timestamp,
            "diagnostics": [],
            "artifacts": artifacts,
            "workspace_delta": [],
            "parsed": {},
        },
    }


@app.get("/inspect/{name}")
def inspect(
    name: str,
    x_sim_session: str | None = Header(default=None, alias="X-Sim-Session"),
):
    state = _select_session(x_sim_session)

    if name == "session.summary":
        return {
            "ok": True,
            "data": {
                "session_id": state.session_id,
                "solver": state.solver,
                "mode": state.mode,
                "ui_mode": state.ui_mode,
                "workspace": state.workspace,
                "driver_options": state.driver_options,
                "connected_at": state.connected_at,
                "run_count": state.run_count,
                "profile": None,
                "connected": True,
            },
        }
    if name == "last.result":
        if not state.runs:
            return {"ok": True, "data": {"has_last_run": False}}
        last = state.runs[-1]
        return {
            "ok": True,
            "data": {
                "has_last_run": True,
                **{k: v for k, v in last.items() if k != "code"},
            },
        }
    raise HTTPException(404, f"unknown inspect target: {name}")


@app.get("/ps")
def ps():
    """List all active sessions."""
    sessions = _list_sessions()
    rows = [
        {
            "session_id": s.session_id,
            "solver": s.solver,
            "mode": s.mode,
            "ui_mode": s.ui_mode,
            "processors": s.processors,
            "workspace": s.workspace,
            "driver_options": s.driver_options,
            "connected_at": s.connected_at,
            "run_count": s.run_count,
            "profile": None,
        }
        for s in sessions
    ]
    default = sessions[0].session_id if len(sessions) == 1 else None
    return {
        "sessions": rows,
        "default_session": default,
        "server_pid": os.getpid(),
    }


def _teardown_session(session_id: str) -> str | None:
    state = _drop_session(session_id)
    if state is None:
        return None
    if state.fdtd is not None:
        try:
            state.fdtd.close()
        except Exception as e:
            log.warning("error closing FDTD for session %s: %s", session_id, e)
        finally:
            state.fdtd = None
    return state.session_id


def _teardown_all() -> list[str]:
    with _sessions_lock:
        ids = list(_sessions.keys())
    return [sid for sid in (_teardown_session(i) for i in ids) if sid]


@app.post("/disconnect")
def disconnect(
    x_sim_session: str | None = Header(default=None, alias="X-Sim-Session"),
):
    state = _select_session(x_sim_session)
    sid = _teardown_session(state.session_id)
    return {"ok": True, "data": {"session_id": sid, "disconnected": True}}


@app.post("/shutdown")
def shutdown(request: Request):
    client_host = request.client.host if request.client else None
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(
            403,
            f"/shutdown is localhost-only (request from {client_host})",
        )
    disconnected_ids = _teardown_all()

    def _exit_after_flush():
        time.sleep(0.1)
        os._exit(0)

    threading.Thread(target=_exit_after_flush, daemon=True).start()
    return {
        "ok": True,
        "data": {
            "shutting_down": True,
            "disconnected_sessions": disconnected_ids,
        },
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Lumerical Agent Server — sim-cli compatible HTTP server",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7601, help="Port (default: 7601)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload (dev mode)")
    args = parser.parse_args()

    install = find_lumerical_install()
    if install:
        log.info("Found Lumerical installation: %s", install)
    else:
        log.warning("Lumerical not found — server will start but operations may fail.")

    log.info("Starting Lumerical Agent Server on %s:%d", args.host, args.port)
    log.info("Endpoints:")
    log.info("  GET  /version          — Server version")
    log.info("  GET  /health           — Health check")
    log.info("  GET  /detect/{solver}  — Detect Lumerical installation")
    log.info("  POST /connect          — Open a solver session")
    log.info("  POST /exec             — Execute code in live session")
    log.info("  POST /run              — One-shot script execution")
    log.info("  GET  /inspect/{name}   — Query session state")
    log.info("  GET  /ps               — List active sessions")
    log.info("  POST /disconnect       — Tear down a session")
    log.info("  POST /shutdown         — Stop the server")

    try:
        import uvicorn
    except ImportError:
        log.error("uvicorn is required. Install with: pip install uvicorn fastapi")
        sys.exit(1)

    uvicorn.run(
        "lumerical_agent_server:app",
        host=args.host,
        port=args.port,
        log_level="info",
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
