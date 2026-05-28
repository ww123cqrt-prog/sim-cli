"""Lumerical FDTD/RCWA driver for sim-cli.

Architecture:
- This driver connects to a remote Lumerical Agent Server via HTTP
- The remote server runs on a Windows machine with Lumerical installed
- Communication uses JSON over HTTP on port 7601 (default)

This module is SDK-free: it does NOT import `lumapi` at module load time,
so `sim check lumerical-fdtd` works on a host without Lumerical installed.
All Lumerical operations happen on the remote server.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from sim.driver import ConnectionInfo, Diagnostic, LintResult, SolverInstall

from .client import LumericalClient

log = logging.getLogger(__name__)


class LumericalDriverError(RuntimeError):
    """Lumerical driver failure with machine-readable diagnostics."""

    def __init__(self, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

    def __str__(self) -> str:
        bits = [super().__str__()]
        if code := self.diagnostics.get("code"):
            bits.append(f"code={code}")
        if host := self.diagnostics.get("host"):
            bits.append(f"host={host}")
        if port := self.diagnostics.get("port"):
            bits.append(f"port={port}")
        return " | ".join(bits)


class LumericalFDTDDriver:
    """sim-cli driver for Lumerical FDTD via remote HTTP server.

    This driver connects to a remote Windows machine running
    lumerical-agent-server and executes FDTD simulations via HTTP API.

    Usage:
        sim --host 100.65.228.190 --port 7601 check lumerical-fdtd
        sim --host 100.65.228.190 --port 7601 run lumerical-fdtd --request request.json
    """

    name = "lumerical-fdtd"
    supports_session = True

    def __init__(
        self,
        host: str = "100.65.228.190",
        port: int = 7601,
        timeout: float = 300,
    ):
        self.host = host
        self.port = port
        self.client = LumericalClient(host, port, timeout)
        self._session_id: str | None = None
        self._connected_at: float | None = None
        self._run_count: int = 0

    def detect(self, script: Path) -> bool:
        """Check if this driver can handle the given script."""
        # Check if script is a Lumerical project file
        suffix = script.suffix.lower()
        return suffix in {".fsp", ".lsf", ".fse"}

    def lint(self, script: Path) -> LintResult:
        """Validate a simulation script before execution."""
        diagnostics = []

        # Check file exists
        if not script.exists():
            diagnostics.append(Diagnostic(
                level="error",
                message=f"File not found: {script}",
            ))

        # Check file extension
        suffix = script.suffix.lower()
        if suffix not in {".fsp", ".lsf", ".fse"}:
            diagnostics.append(Diagnostic(
                level="warning",
                message=f"Unusual file extension for Lumerical: {suffix}",
            ))

        return LintResult(
            ok=len(diagnostics) == 0,
            diagnostics=diagnostics,
        )

    def detect_installed(self) -> list[SolverInstall]:
        """Scan remote host for Lumerical installations via HTTP."""
        try:
            response = self.client.detect(self.name)
            if response.get("ok"):
                data = response.get("data", {})
                installs = data.get("installs", [])
                return [SolverInstall(
                    name=inst.get("name", self.name),
                    version=inst.get("version", "unknown"),
                    path=inst.get("path", "remote"),
                    source=f"remote:{self.host}:{self.port}",
                    extra=inst.get("extra", {}),
                ) for inst in installs]
        except Exception as e:
            log.debug("Detection failed: %s", e)
        return []

    def connect(self) -> ConnectionInfo:
        """Connect to remote Lumerical Agent Server."""
        try:
            # Check server health first
            health = self.client.health()
            if not health.get("ok"):
                return ConnectionInfo(
                    solver="lumerical-fdtd",
                    version=None,
                    status="error",
                    message=f"Server not healthy: {health.get('error', 'unknown')}",
                )

            # Detect Lumerical installation
            detect = self.client.detect(self.name)
            if not detect.get("ok"):
                return ConnectionInfo(
                    solver="lumerical-fdtd",
                    version=None,
                    status="error",
                    message=f"Lumerical not found on remote: {detect.get('error', 'unknown')}",
                )

            # Get version from nested response
            data = detect.get("data", {})
            installs = data.get("installs", [])
            version = installs[0].get("version") if installs else None

            # Connect to server
            response = self.client.post("/connect")
            if response.get("ok"):
                self._session_id = response.get("session_id", str(uuid.uuid4()))
                self._connected_at = time.time()
                return ConnectionInfo(
                    solver="lumerical-fdtd",
                    version=version,
                    status="ok",
                    message="Connected to remote Lumerical server",
                )
            else:
                return ConnectionInfo(
                    solver="lumerical-fdtd",
                    version=version,
                    status="error",
                    message=response.get("error", "Connection failed"),
                )
        except Exception as e:
            return ConnectionInfo(
                solver="lumerical-fdtd",
                version=None,
                status="error",
                message=str(e),
            )

    def run(self, code: str, label: str = "") -> dict:
        """Execute a simulation request on the remote server.

        Args:
            code: JSON string containing the simulation request
            label: Optional label for the run

        Returns:
            dict with at least {"ok": bool} and optional result data
        """
        try:
            # Parse the request
            if isinstance(code, str):
                request = json.loads(code)
            else:
                request = code

            # Send to remote server
            response = self.client.post("/run", json=request)
            self._run_count += 1
            return response
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def disconnect(self) -> dict:
        """Disconnect from the remote server."""
        try:
            response = self.client.post("/disconnect")
            self._session_id = None
            self._connected_at = None
            return {"ok": True, "disconnected": True}
        except Exception as e:
            return {"ok": True, "disconnected": True, "error": str(e)}

    def parse_output(self, stdout: str) -> dict:
        """Parse solver output."""
        # Try to parse as JSON
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"raw": stdout}

    def run_file(self, script: Path) -> dict:
        """Run a simulation file on the remote server.

        Args:
            script: Path to the simulation file

        Returns:
            dict with simulation results
        """
        # Build request
        request = {
            "task_id": f"run-{uuid.uuid4().hex[:12]}",
            "solver": "lumerical-fdtd",
            "action": "run",
            "workdir": str(script.parent),
            "template": {
                "project_file": str(script),
            },
        }

        return self.run(json.dumps(request))


class LumericalRCWADriver(LumericalFDTDDriver):
    """sim-cli driver for Lumerical RCWA via remote HTTP server.

    RCWA is accessed through the same FDTD session via addrcwa().
    This driver extends LumericalFDTDDriver with RCWA-specific behavior.
    """

    name = "lumerical-rcwa"

    def detect(self, script: Path) -> bool:
        """Check if this driver can handle RCWA scripts."""
        # RCWA uses the same .fsp files as FDTD
        suffix = script.suffix.lower()
        return suffix in {".fsp", ".lsf"}

    def detect_installed(self) -> list[SolverInstall]:
        """Scan remote host for Lumerical RCWA support."""
        # RCWA is part of FDTD, so same detection
        return super().detect_installed()
