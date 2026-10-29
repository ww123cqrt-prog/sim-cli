"""SDK-free Lumerical drivers backed by an explicitly selected Agent Server."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from pathlib import Path

from sim.driver import ConnectionInfo, Diagnostic, LintResult, RunResult, SolverInstall
from .client import LumericalClient


class LumericalDriverError(RuntimeError):
    def __init__(self, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class LumericalFDTDDriver:
    name = "lumerical-fdtd"
    supports_session = True

    def __init__(self, host: str | None = None, port: int = 7601, timeout: float = 300):
        self.client = LumericalClient(host, port, timeout)
        self.host, self.port = self.client.host, port
        self._session_id: str | None = None
        self._connected_at: float | None = None
        self._run_count = 0

    def detect(self, script: Path) -> bool:
        return script.suffix.lower() in {".fsp", ".lsf", ".fse"}

    def lint(self, script: Path) -> LintResult:
        diagnostics = []
        if not script.is_file():
            diagnostics.append(Diagnostic("error", f"File not found: {script}"))
        if script.suffix.lower() not in {".fsp", ".lsf", ".fse", ".json"}:
            diagnostics.append(Diagnostic("warning", f"Unusual file extension: {script.suffix}"))
        return LintResult(not diagnostics, diagnostics)

    def detect_installed(self) -> list[SolverInstall]:
        if not self.host:
            return []
        response = self.client.detect(self.name)
        if not response.get("ok"):
            return []
        return [SolverInstall(name=i.get("name", self.name), version=i.get("version", "unknown"),
                              path=i.get("path", "remote"), source=f"remote:{self.host}:{self.port}",
                              extra=i.get("extra", {}))
                for i in response.get("data", {}).get("installs", [])]

    def launch(self, host: str | None = None, port: int | None = None,
               timeout: float | None = None, **kwargs) -> dict:
        if self._session_id:
            return {"ok": False, "error_code": "RUN_FAILED", "message": "A Lumerical session is already active"}
        selected_host = host or self.host
        selected_port = self.port if port is None else int(port)
        if not selected_host:
            return {"ok": False, "error_code": "RUN_FAILED",
                    "message": "Lumerical host is required; pass driver_options.host or LUMERICAL_HOST"}
        if (selected_host, selected_port) != (self.host, self.port) or timeout is not None:
            self.client.close()
            self.client = LumericalClient(selected_host, selected_port, timeout if timeout is not None else self.client.timeout)
        self.host, self.port = selected_host, selected_port
        health = self.client.health()
        if not health.get("ok"):
            return self._failure(health)
        installs = self.detect_installed()
        if not installs:
            return {"ok": False, "error_code": "SOLVER_NOT_INSTALLED", "message": "Lumerical unavailable on selected backend"}
        payload = {"solver": self.name, **{k: kwargs[k] for k in ("mode", "ui_mode", "processors", "workspace") if k in kwargs}}
        response = self.client.post("/connect", json=payload)
        if not response.get("ok"):
            return self._failure(response)
        data = response.get("data", response)
        sid = data.get("session_id")
        if not isinstance(sid, str) or not sid:
            return {"ok": False, "error_code": "RUN_FAILED", "message": "Backend omitted session_id"}
        self._session_id = self.client.session_id = sid
        self._connected_at = time.time()
        self._run_count = 0
        return {**data, "ok": True, "session_id": sid,
                "launch_options": {"backend_host": self.host, "backend_port": self.port}}

    @staticmethod
    def _failure(response: dict) -> dict:
        data = response.get("data", {})
        message = response.get("message") or response.get("error") or data.get("error") or data.get("stderr") or "; ".join(map(str, data.get("errors") or [])) or "Lumerical backend request failed"
        return {**data, "ok": False, "error_code": "RUN_FAILED", "message": str(message)[:280],
                "stderr": str(data.get("stderr") or message)}

    def connect(self) -> ConnectionInfo:
        result = self.launch()
        return ConnectionInfo(self.name, result.get("solver_version"),
                              "ok" if result.get("ok") else "error", result.get("message", "Connected"))

    def run(self, code: str, label: str = "") -> dict:
        if not self._session_id:
            return {"ok": False, "error_code": "RUN_FAILED", "message": "Connect to Lumerical before executing code"}
        response = self.client.post("/exec", json={"code": code, "label": label})
        self._run_count += 1
        if not response.get("ok"):
            return self._failure(response)
        return {**response.get("data", {}), "ok": True}

    def disconnect(self) -> dict:
        if self._session_id is None:
            self.client.close()
            return {"ok": True, "disconnected": True}
        response = self.client.post("/disconnect")
        already_gone = response.get("http_status") == 404 and "unknown session_id" in str(response.get("error", ""))
        if not response.get("ok") and not already_gone:
            return self._failure(response)
        self._session_id = self.client.session_id = None
        self._connected_at = None
        self.client.close()
        return {"ok": True, "disconnected": True}

    def parse_output(self, stdout: str) -> dict:
        try:
            value = json.loads(stdout)
            return value if isinstance(value, dict) else {"result": value}
        except ValueError:
            return {"raw": stdout}

    def run_file(self, script: Path) -> RunResult:
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            request = json.loads(script.read_text(encoding="utf-8")) if script.suffix.lower() == ".json" else {"script": str(script)}
            if not isinstance(request, dict) or not isinstance(request.get("script"), str):
                raise ValueError("Run request requires a remote script path")
            if request.get("solver", self.name) != self.name:
                raise ValueError("Run request solver does not match selected driver")
            request["solver"] = self.name
            response = self.client.post("/run", json=request)
        except (OSError, ValueError) as exc:
            response = {"ok": False, "error": str(exc)}
        data = response.get("data", {})
        errors = list(data.get("errors") or [])
        success = response.get("ok") is True and not errors and data.get("exit_code") == 0
        if not success and not errors:
            errors.append(str(response.get("error") or data.get("error") or data.get("stderr") or "Remote run failed"))
        return RunResult(exit_code=0 if success else (data.get("exit_code") or 1),
                         stdout=str(data.get("stdout", "")), stderr=str(data.get("stderr", response.get("error", ""))),
                         duration_s=time.monotonic()-start, script=str(script), solver=self.name,
                         timestamp=timestamp, errors=errors, artifacts=data.get("artifacts") or [])


class LumericalRCWADriver(LumericalFDTDDriver):
    """RCWA uses the same backend session with explicit RCWA request identity."""
    name = "lumerical-rcwa"
