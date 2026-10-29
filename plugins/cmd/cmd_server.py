#!/usr/bin/env python3
"""CMD Server with token-based authentication.

Security features:
- Token-based auth: connect once, get token, use token for all subsequent requests
- Password hashed with SHA-256, compared with hmac.compare_digest
- All sensitive endpoints require valid auth token
- Remote confirmation (once per session)
- Auto-exit timeout

Usage:
    python cmd_server.py --port 7602 --username admin --password mypassword
    python cmd_server.py --port 7602 --username admin --password mypassword --timeout 600 --require-confirm
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sim_plugin_cmd import CmdDriver


def main():
    parser = argparse.ArgumentParser(
        description="CMD Server with token-based authentication",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7602, help="Port (default: 7602)")
    parser.add_argument("--username", default=None, help="Username for authentication")
    parser.add_argument("--password", default=None, help="Password for authentication")
    parser.add_argument("--timeout", type=int, default=0, help="Inactivity timeout in seconds (0 = no timeout)")
    parser.add_argument("--require-confirm", action="store_true", help="Require confirmation before executing commands")
    args = parser.parse_args()

    # Security warnings
    if not args.username or not args.password:
        print("WARNING: No username/password set. Anyone can connect!")
        print("  Add --username <user> --password <pass> for security.")
    if args.timeout == 0:
        print("WARNING: No timeout set. Session never auto-disconnects!")
        print("  Add --timeout 600 for 10-minute inactivity timeout.")
    if not args.require_confirm:
        print("WARNING: No confirmation required. Commands execute immediately!")
        print("  Add --require-confirm for human approval before execution.")

    # Import uvicorn here to avoid import errors
    try:
        import uvicorn
        from fastapi import FastAPI, Header, HTTPException, Request, Body, Depends
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
        from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
    app = FastAPI(title="cmd-server", version="1.2.0")

    # CORS - restrict to same origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security scheme for token auth
    security = HTTPBearer(auto_error=False)

    # ── Auth dependency ──────────────────────────────────────────────────────

    async def get_auth_token(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        x_auth_token: Optional[str] = Header(default=None, alias="X-Auth-Token"),
    ) -> str:
        """Extract auth token from Bearer header or X-Auth-Token header."""
        if credentials and credentials.credentials:
            return credentials.credentials
        if x_auth_token:
            return x_auth_token
        raise HTTPException(401, "Missing authentication. Provide Bearer token or X-Auth-Token header.")

    async def get_optional_auth_token(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        x_auth_token: Optional[str] = Header(default=None, alias="X-Auth-Token"),
    ) -> Optional[str]:
        """Extract auth token if provided, otherwise None."""
        if credentials and credentials.credentials:
            return credentials.credentials
        return x_auth_token

    # ── Public endpoints (no auth required) ──────────────────────────────────

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

    # ── Authenticated endpoints ──────────────────────────────────────────────

    @app.post("/connect")
    def connect(
        solver: str = Body(default="cmd"),
        mode: str = Body(default="session"),
        username: Optional[str] = Body(default=None),
        password: Optional[str] = Body(default=None),
        timeout: Optional[int] = Body(default=None),
    ):
        """Create a new session. Returns auth_token for subsequent requests.

        Args:
            timeout: Per-session idle timeout in seconds (None = use server default)
        """
        # Check authentication if configured
        if driver._username or driver._password_hash:
            if not username or not password:
                raise HTTPException(401, "Authentication required. Provide username and password.")
            if not driver.authenticate(username, password):
                raise HTTPException(401, "Invalid credentials.")
        result = driver.launch(timeout=timeout)
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "Failed to create session"))
        return result

    @app.post("/exec")
    def exec_command(
        code: str = Body(...),
        label: str = Body(default="cli-snippet"),
        session_id: Optional[str] = Body(default=None),
        x_sim_session: Optional[str] = Header(default=None),
        auth_token: str = Depends(get_auth_token),
    ):
        """Execute a command. Requires valid auth token."""
        sid = session_id or x_sim_session
        if not sid:
            raise HTTPException(400, "Missing session_id")

        result = driver.exec(sid, code, label, auth_token=auth_token)
        if not result.get("ok") and "Invalid auth token" in result.get("error", ""):
            raise HTTPException(401, result["error"])
        return {"ok": result.get("ok", False), "data": result}

    @app.post("/confirm")
    def confirm_session(
        session_id: str = Body(..., embed=True),
        auth_token: str = Depends(get_auth_token),
        request: Request = None,
    ):
        """Request human approval. Blocks until operator approves/denies in terminal."""
        client_host = request.client.host if request and request.client else "unknown"
        client_port = request.client.port if request and request.client else 0
        client_info = f"{client_host}:{client_port}"
        result = driver.confirm_session(session_id, auth_token, client_info=client_info)
        if not result.get("ok"):
            if "Invalid auth token" in result.get("error", ""):
                raise HTTPException(401, result["error"])
            raise HTTPException(400, result.get("error", "Failed to confirm session"))
        return result

    @app.post("/disconnect")
    def disconnect(
        x_sim_session: Optional[str] = Header(default=None),
        x_auth_token: Optional[str] = Header(default=None, alias="X-Auth-Token"),
        auth_token: Optional[str] = Depends(get_optional_auth_token),
    ):
        """Disconnect a session."""
        token = auth_token or x_auth_token or ""
        state = driver._sessions.get(x_sim_session)
        if not state:
            raise HTTPException(400, "no active sessions — POST /connect first")
        result = driver.disconnect(state.session_id, auth_token=token)
        return result

    @app.get("/ps")
    def ps(auth_token: str = Depends(get_auth_token)):
        """List active sessions. Requires valid auth token."""
        # Verify token is valid for any session
        session_id = driver.verify_token(auth_token)
        if not session_id:
            raise HTTPException(401, "Invalid auth token")

        sessions = []
        for sid, state in driver._sessions.items():
            sessions.append({
                "session_id": state.session_id,
                "solver": "cmd",
                "shell": state.shell,
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
        """Shutdown the server (localhost only)."""
        client_host = request.client.host if request.client else None
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(403, f"/shutdown is localhost-only (request from {client_host})")
        def _exit_after_flush():
            time.sleep(0.1)
            os._exit(0)
        threading.Thread(target=_exit_after_flush, daemon=True).start()
        return {"ok": True, "data": {"shutting_down": True}}

    # ── Startup info ─────────────────────────────────────────────────────────

    print(f"[cmd-server] Starting on {args.host}:{args.port}")
    if args.username:
        print(f"[cmd-server] Authentication: username={args.username}")
    if args.timeout > 0:
        print(f"[cmd-server] Timeout: {args.timeout}s")
    if args.require_confirm:
        print(f"[cmd-server] Confirmation required: yes")
    print(f"[cmd-server] Endpoints:")
    print(f"  GET  /health           - Health check (public)")
    print(f"  GET  /detect/cmd       - Detect CMD (public)")
    print(f"  POST /connect          - Create session (returns auth_token)")
    print(f"  POST /exec             - Execute command (requires auth_token)")
    print(f"  POST /confirm          - Confirm session (requires auth_token)")
    print(f"  POST /disconnect       - Disconnect session (requires auth_token)")
    print(f"  GET  /ps               - List sessions (requires auth_token)")
    print(f"  POST /shutdown         - Shutdown server (localhost only)")
    print(f"")
    print(f"[cmd-server] Auth flow:")
    print(f"  1. POST /connect with username/password -> get auth_token")
    print(f"  2. Use auth_token in X-Auth-Token header for all subsequent requests")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
