#!/usr/bin/env python3
"""CMD Server 启动脚本（带安全功能）

用法:
    # 基本启动（无认证）
    python cmd_server.py --port 7602

    # 带认证
    python cmd_server.py --port 7602 --username admin --password mypass

    # 带超时（600秒 = 10分钟）
    python cmd_server.py --port 7602 --timeout 600

    # 带确认机制
    python cmd_server.py --port 7602 --require-confirm

    # 完整示例
    python cmd_server.py --port 7602 --username admin --password mypass --timeout 600 --require-confirm
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sim_plugin_cmd import CmdDriver


def main():
    parser = argparse.ArgumentParser(
        description="CMD Server with security features",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7602, help="Port (default: 7602)")
    parser.add_argument("--username", default=None, help="Username for authentication")
    parser.add_argument("--password", default=None, help="Password for authentication")
    parser.add_argument("--timeout", type=int, default=0, help="Inactivity timeout in seconds (0 = no timeout)")
    parser.add_argument("--require-confirm", action="store_true", help="Require confirmation before executing commands")
    args = parser.parse_args()

    # Import uvicorn here to avoid import errors
    try:
        import uvicorn
        from fastapi import FastAPI, Header, HTTPException, Request, Body
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
    except ImportError:
        print("Error: fastapi and uvicorn are required.")
        print("Install with: pip install fastapi uvicorn")
        sys.exit(1)

    # Create driver with security options
    driver = CmdDriver(
        username=args.username,
        password=args.password,
        require_confirm=args.require_confirm,
        timeout=args.timeout,
    )

    # Create FastAPI app
    app = FastAPI(title="cmd-server", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Session management
    def _select_session(session_id: str = None):
        if session_id:
            state = driver._sessions.get(session_id)
            if state is None:
                raise HTTPException(404, f"unknown session_id: {session_id}")
            return state
        if len(driver._sessions) == 1:
            return next(iter(driver._sessions.values()))
        if not driver._sessions:
            raise HTTPException(400, "no active sessions — POST /connect first")
        raise HTTPException(400, f"{len(driver._sessions)} sessions live; specify session_id")

    # Endpoints
    @app.get("/health")
    def health():
        return {
            "ok": True,
            "data": {
                "status": "healthy",
                "solver": "cmd",
                "active_sessions": len(driver._sessions),
                "require_confirm": driver._require_confirm,
                "timeout": driver._timeout,
            },
        }

    @app.get("/detect/{solver}")
    def detect_solver(solver: str):
        if solver != "cmd":
            raise HTTPException(404, f"unknown solver: {solver}")
        installs = driver.detect_installed()
        return {
            "ok": True,
            "data": {
                "solver": solver,
                "installs": [i.to_dict() for i in installs],
                "resolutions": [{"install": i.to_dict(), "profile": None} for i in installs],
                "compatibility": None,
            },
        }

    @app.post("/connect")
    def connect(
        solver: str = Body(default="cmd"),
        mode: str = Body(default="session"),
        username: Optional[str] = Body(default=None),
        password: Optional[str] = Body(default=None),
    ):
        # Check authentication
        if driver._username or driver._password:
            if not username or not password:
                raise HTTPException(401, "Authentication required. Provide username and password.")
            if not driver.authenticate(username, password):
                raise HTTPException(401, "Invalid credentials.")
        result = driver.launch()
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "Failed to create session"))
        return result

    @app.post("/exec")
    def exec_command(
        code: str = Body(...),
        label: str = Body(default="cli-snippet"),
        session_id: Optional[str] = Body(default=None),
        x_sim_session: Optional[str] = Header(default=None),
    ):
        sid = session_id or x_sim_session
        state = _select_session(sid)
        result = driver._exec_impl(state, code, label)
        return {"ok": result.get("ok", False), "data": result}

    @app.post("/confirm")
    def confirm_session(
        session_id: str = Body(..., embed=True),
    ):
        result = driver.confirm_session(session_id)
        if not result.get("ok"):
            raise HTTPException(400, result.get("error", "Failed to confirm session"))
        return result

    @app.post("/disconnect")
    def disconnect(x_sim_session: Optional[str] = Header(default=None)):
        state = _select_session(x_sim_session)
        result = driver.disconnect(state.session_id)
        return result

    @app.get("/ps")
    def ps():
        sessions = []
        for sid, state in driver._sessions.items():
            sessions.append({
                "session_id": state.session_id,
                "solver": "cmd",
                "shell": state.shell,
                "cwd": state.cwd,
                "connected_at": state.connected_at,
                "last_activity": state.last_activity,
                "run_count": state.run_count,
                "confirmed": state.confirmed,
            })
        return {
            "sessions": sessions,
            "default_session": sessions[0]["session_id"] if len(sessions) == 1 else None,
            "server_pid": os.getpid(),
        }

    @app.post("/shutdown")
    def shutdown(request: Request):
        client_host = request.client.host if request.client else None
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(403, f"/shutdown is localhost-only (request from {client_host})")
        def _exit_after_flush():
            time.sleep(0.1)
            os._exit(0)
        threading.Thread(target=_exit_after_flush, daemon=True).start()
        return {"ok": True, "data": {"shutting_down": True}}

    # Print startup info
    print(f"[cmd-server] Starting on {args.host}:{args.port}")
    if args.username:
        print(f"[cmd-server] Authentication: username={args.username}")
    if args.timeout > 0:
        print(f"[cmd-server] Timeout: {args.timeout}s")
    if args.require_confirm:
        print(f"[cmd-server] Confirmation required: yes")
    print(f"[cmd-server] Endpoints:")
    print(f"  GET  /health           - Health check")
    print(f"  GET  /detect/cmd       - Detect CMD")
    print(f"  POST /connect          - Create session (requires auth)")
    print(f"  POST /exec             - Execute command")
    print(f"  POST /confirm          - Confirm session")
    print(f"  POST /disconnect       - Disconnect session")
    print(f"  GET  /ps               - List sessions")
    print(f"  POST /shutdown         - Shutdown server")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
