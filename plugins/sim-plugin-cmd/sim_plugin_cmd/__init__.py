"""CMD/Shell command execution driver for sim-cli.

Allows executing shell commands on remote machines via sim-cli.
Designed for personal use on trusted networks.

Security Features:
- Token-based authentication (connect once, get token, use token for all requests)
- Password hashed with SHA-256, compared with hmac.compare_digest
- Remote confirmation (once per session)
- Auto-exit timeout (no activity for N seconds)

Usage:
    sim --host <remote-ip> --port 7602 connect --solver cmd
    sim --host <remote-ip> --port 7602 --session <id> exec "dir"
    sim --host <remote-ip> --port 7602 --session <id> disconnect
"""
from __future__ import annotations

import hashlib
import hmac
import os
import platform
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from sim.driver import SolverInstall


@dataclass
class SessionState:
    """Session state for CMD driver."""
    session_id: str
    auth_token: str  # Token for subsequent requests
    shell: str = "cmd"  # cmd, powershell, bash
    cwd: str = ""
    env: dict = field(default_factory=dict)
    connected_at: float = 0
    last_activity: float = 0
    run_count: int = 0
    confirmed: bool = False  # Whether user has confirmed this session
    pending_approval: bool = False  # Waiting for human approval
    approval_event: threading.Event = field(default_factory=threading.Event, repr=False)
    approval_result: bool = False  # Human's decision
    client_info: str = ""  # Client IP/port for display
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    timeout: int = 0  # Per-session idle timeout (0 = use server default)


def _hash_password(password: str) -> str:
    """Hash password with SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


class CmdDriver:
    """sim-cli driver for executing shell commands.

    Security features:
    - Token-based authentication
    - Password hashing
    - Remote confirmation (once per session)
    - Auto-exit timeout
    """

    name = "cmd"
    supports_session = True

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        require_confirm: bool = False,
        timeout: int = 0,  # 0 = no timeout
    ):
        self._sessions: dict[str, SessionState] = {}
        self._sessions_lock = threading.Lock()
        self._username = username
        self._password_hash = _hash_password(password) if password else None
        self._require_confirm = require_confirm
        self._timeout = timeout
        self._last_activity = time.time()
        self._shutdown_event = threading.Event()
        self._auth_tokens: dict[str, str] = {}  # token -> session_id

        # Start timeout monitor if configured
        if timeout > 0:
            self._timeout_thread = threading.Thread(
                target=self._timeout_monitor,
                daemon=True,
            )
            self._timeout_thread.start()

    def _timeout_monitor(self):
        """Monitor for inactivity and shutdown if timeout exceeded."""
        while not self._shutdown_event.is_set():
            time.sleep(10)  # Check every 10 seconds

            with self._sessions_lock:
                if self._sessions:
                    # Check each session
                    expired = []
                    for sid, state in self._sessions.items():
                        # Use per-session timeout if set, otherwise server default
                        session_timeout = state.timeout if state.timeout > 0 else self._timeout
                        if session_timeout > 0 and time.time() - state.last_activity > session_timeout:
                            expired.append(sid)

                    # Remove expired sessions
                    for sid in expired:
                        state = self._sessions.pop(sid)
                        self._auth_tokens.pop(state.auth_token, None)
                        print(f"[cmd-server] Session {sid} expired due to inactivity")

                # If no sessions and timeout exceeded, shutdown
                if not self._sessions and self._timeout > 0 and time.time() - self._last_activity > self._timeout:
                    print(f"[cmd-server] No activity for {self._timeout}s, shutting down...")
                    self._shutdown_event.set()
                    os._exit(0)

    def authenticate(self, username: str, password: str) -> bool:
        """Verify credentials using constant-time comparison."""
        if self._username is None and self._password_hash is None:
            return True  # No auth configured
        password_hash = _hash_password(password)
        username_ok = hmac.compare_digest(username or "", self._username or "")
        password_ok = hmac.compare_digest(password_hash, self._password_hash or "")
        return username_ok and password_ok

    def verify_token(self, token: str) -> Optional[str]:
        """Verify auth token and return session_id if valid."""
        with self._sessions_lock:
            return self._auth_tokens.get(token)

    def detect_installed(self) -> list[SolverInstall]:
        """CMD is always available."""
        shell = "cmd" if platform.system() == "Windows" else "bash"
        return [SolverInstall(
            name="cmd",
            version=platform.version(),
            path=shell,
            source="system",
            extra={"platform": platform.system()},
        )]

    def connect(self, **kwargs) -> dict:
        """Create a new CMD session."""
        return self.launch(**kwargs)

    def launch(self, shell: str = "cmd", cwd: str = None, timeout: int = None, **kwargs) -> dict:
        """Launch a CMD session.

        Args:
            shell: Shell type (cmd, powershell, bash)
            cwd: Working directory
            timeout: Per-session idle timeout in seconds (None = use server default)
        """
        sid = f"cmd-{uuid.uuid4().hex[:12]}"
        token = uuid.uuid4().hex  # Auth token for subsequent requests

        # Determine default shell based on platform
        if shell == "cmd" and platform.system() != "Windows":
            shell = "bash"

        if cwd is None:
            cwd = os.getcwd()

        now = time.time()
        state = SessionState(
            session_id=sid,
            auth_token=token,
            shell=shell,
            cwd=cwd,
            connected_at=now,
            last_activity=now,
            confirmed=not self._require_confirm,  # Auto-confirm if not required
            timeout=timeout or 0,
        )

        with self._sessions_lock:
            self._sessions[sid] = state
            self._auth_tokens[token] = sid
            self._last_activity = now

        return {
            "ok": True,
            "data": {
                "session_id": sid,
                "auth_token": token,  # Client must use this for subsequent requests
                "solver": "cmd",
                "mode": "session",
                "shell": shell,
                "cwd": cwd,
                "connected_at": state.connected_at,
                "run_count": 0,
                "profile": None,
                "requires_confirm": self._require_confirm and not state.confirmed,
                "timeout": state.timeout if state.timeout > 0 else self._timeout,
            },
        }

    def confirm_session(self, session_id: str, auth_token: str, client_info: str = "", timeout: int = 180) -> dict:
        """Request human approval for a session. Blocks until approved/denied or timeout."""
        # Verify token
        token_sid = self.verify_token(auth_token)
        if token_sid != session_id:
            return {"ok": False, "error": "Invalid auth token"}

        with self._sessions_lock:
            state = self._sessions.get(session_id)
            if state is None:
                return {"ok": False, "error": f"Session not found: {session_id}"}

            if state.confirmed:
                return {
                    "ok": True,
                    "data": {
                        "session_id": session_id,
                        "confirmed": True,
                        "message": "Session already confirmed.",
                    },
                }

            state.pending_approval = True
            state.client_info = client_info

        # Print approval request to terminal
        print("\n" + "=" * 60)
        print(f"[APPROVAL REQUIRED] Remote connection request")
        print(f"  Session ID: {session_id}")
        print(f"  Client:     {client_info}")
        print(f"  Shell:      {state.shell}")
        print(f"  Timeout:    {timeout}s")
        print(f"  Time:       {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Wait for human input with timeout
        import sys
        import msvcrt

        deadline = time.time() + timeout
        print(f"  Approve this connection? (y/n) [{timeout}s timeout]: ", end="", flush=True)

        answer = ""
        while time.time() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ('\r', '\n'):
                    print()  # newline
                    answer = answer.strip().lower()
                    break
                elif ch == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                elif ch == '\b':  # backspace
                    if answer:
                        answer = answer[:-1]
                        print('\b \b', end='', flush=True)
                else:
                    answer += ch
                    print(ch, end='', flush=True)
            else:
                time.sleep(0.05)  # 50ms polling

        if answer in ('y', 'yes'):
            with self._sessions_lock:
                state.confirmed = True
                state.pending_approval = False
                state.last_activity = time.time()
            state.approval_event.set()
            print(f"  [APPROVED] Session {session_id}\n")
            return {
                "ok": True,
                "data": {
                    "session_id": session_id,
                    "confirmed": True,
                    "message": "Session approved by human operator.",
                },
            }
        elif answer in ('n', 'no'):
            with self._sessions_lock:
                state.pending_approval = False
            state.approval_event.set()
            print(f"  [DENIED] Session {session_id}\n")
            return {
                "ok": False,
                "error": "Connection denied by human operator.",
            }
        else:
            # Timeout or invalid input
            with self._sessions_lock:
                state.pending_approval = False
            state.approval_event.set()
            print(f"\n  [DENIED] Session {session_id} (timeout or invalid input)\n")
            return {
                "ok": False,
                "error": f"Approval timed out after {timeout}s.",
            }

        # Timeout or interrupt
        with self._sessions_lock:
            state.pending_approval = False
        state.approval_event.set()
        print(f"\n  [DENIED] Session {session_id} (timeout {timeout}s)\n")
        return {
            "ok": False,
            "error": f"Approval timed out after {timeout}s.",
        }

    def run(self, code: str, label: str = "", auth_token: str = "") -> dict:
        """Execute a shell command (called by sim-server)."""
        # Verify token and get session
        session_id = self.verify_token(auth_token)
        if not session_id:
            return {"ok": False, "error": "Invalid or missing auth token"}

        with self._sessions_lock:
            state = self._sessions.get(session_id)
            if state is None:
                return {"ok": False, "error": f"Session not found: {session_id}"}

        return self._exec_impl(state, code, label)

    def exec(self, session_id: str, code: str, label: str = "", auth_token: str = "") -> dict:
        """Execute a shell command (direct call)."""
        # Verify token
        token_sid = self.verify_token(auth_token)
        if token_sid != session_id:
            return {"ok": False, "error": "Invalid auth token"}

        with self._sessions_lock:
            state = self._sessions.get(session_id)
            if state is None:
                return {"ok": False, "error": f"Session not found: {session_id}"}

        return self._exec_impl(state, code, label)

    def _exec_impl(self, state: SessionState, code: str, label: str = "") -> dict:
        """Internal implementation for executing shell commands."""
        # Check if session is confirmed
        if not state.confirmed:
            return {
                "ok": False,
                "error": "Session not confirmed. Call /confirm first.",
                "requires_confirm": True,
                "session_id": state.session_id,
            }

        with state.lock:
            start = time.monotonic()

            try:
                # Determine shell command
                if state.shell == "powershell":
                    cmd = ["powershell", "-Command", code]
                elif state.shell == "bash":
                    cmd = ["bash", "-c", code]
                else:  # cmd
                    cmd = ["cmd", "/c", code]

                # Use CREATE_NO_WINDOW on Windows to prevent start command
                # from hijacking the parent's console/pipe
                creationflags = 0
                if platform.system() == "Windows":
                    creationflags = subprocess.CREATE_NO_WINDOW

                # Execute command
                result = subprocess.run(
                    cmd,
                    cwd=state.cwd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    shell=False,
                    creationflags=creationflags,
                )

                duration = time.monotonic() - start
                state.run_count += 1
                state.last_activity = time.time()
                self._last_activity = time.time()

                return {
                    "ok": result.returncode == 0,
                    "session_id": state.session_id,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "duration_s": round(duration, 3),
                    "label": label,
                    "started_at": time.time(),
                }

            except subprocess.TimeoutExpired:
                return {
                    "ok": False,
                    "error": "Command timed out after 300 seconds",
                }
            except Exception as e:
                return {
                    "ok": False,
                    "error": str(e),
                }

    def disconnect(self, session_id: str, auth_token: str = "") -> dict:
        """Disconnect a CMD session."""
        # Verify token if provided
        if auth_token:
            token_sid = self.verify_token(auth_token)
            if token_sid != session_id:
                return {"ok": False, "error": "Invalid auth token"}

        with self._sessions_lock:
            state = self._sessions.pop(session_id, None)
            if state:
                self._auth_tokens.pop(state.auth_token, None)

        if state is None:
            return {"ok": False, "error": f"Session not found: {session_id}"}

        return {
            "ok": True,
            "data": {
                "session_id": session_id,
                "disconnected": True,
            },
        }

    def inspect(self, session_id: str, name: str, auth_token: str = "") -> dict:
        """Query session state."""
        # Verify token
        if auth_token:
            token_sid = self.verify_token(auth_token)
            if token_sid != session_id:
                return {"ok": False, "error": "Invalid auth token"}

        with self._sessions_lock:
            state = self._sessions.get(session_id)
            if state is None:
                return {"ok": False, "error": f"Session not found: {session_id}"}

        if name == "session.summary":
            return {
                "ok": True,
                "data": {
                    "session_id": state.session_id,
                    "solver": "cmd",
                    "shell": state.shell,
                    "connected_at": state.connected_at,
                    "last_activity": state.last_activity,
                    "run_count": state.run_count,
                    "confirmed": state.confirmed,
                    "connected": True,
                },
            }

        return {"ok": False, "error": f"Unknown inspect target: {name}"}


# Plugin metadata
plugin_info = {
    "name": "cmd",
    "summary": "CMD/Shell command execution plugin with security features.",
    "homepage": "https://github.com/cq/sim-plugins",
    "license_class": "apache-2.0",
    "solver_name": "cmd",
}

# Export for plugin discovery
skills_dir = None  # No skills directory for cmd plugin
__all__ = ["CmdDriver", "skills_dir", "plugin_info"]
