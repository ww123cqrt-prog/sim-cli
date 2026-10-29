"""Remote Lumapi Adapter — HTTP-based lumapi proxy for remote Lumerical execution.

Translates local lumapi API calls into HTTP requests to a remote
Lumerical Agent Server, enabling Mac/Linux agents to use Windows-hosted
Lumerical FDTD transparently.

Architecture:
    Mac (lumerical-for-agent) --> RemoteLumapi --> HTTP --> Windows (lumerical-agent-server) --> lumapi

Usage:
    from sim_plugin_lumerical.remote_lumapi import RemoteLumapi

    # Create FDTD instance (connects to remote)
    fdtd = RemoteLumapi(host="100.65.228.190", port=7601)

    # Use like local lumapi
    fdtd.newproject()
    fdtd.addfdtd()
    fdtd.addrect()
    fdtd.set("x", 0)
    fdtd.run()
    T = fdtd.getresult("monitor", "T")
    fdtd.close()
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600  # 10 minutes for long simulations


class RemoteLumapi:
    """HTTP-based proxy for lumapi.FDTD.

    Translates lumapi method calls into HTTP requests to a remote
    Lumerical Agent Server. Each method call is converted to a Python
    code string and sent to the server's /eval endpoint.

    The server executes the code in a live lumapi session and returns
    the result (with proper numpy array serialization).
    """

    def __init__(
        self,
        host: str = "100.65.228.190",
        port: int = 7601,
        timeout: float = DEFAULT_TIMEOUT,
        hide: bool = True,
    ):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.hide = hide
        self._client: httpx.Client | None = None
        self._session_id: str | None = None
        self._connected = False

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _eval(self, code: str) -> Any:
        """Send Python code to remote server for execution.

        Args:
            code: Python code string to execute on the remote FDTD instance.
                  The code has access to a variable `fdtd` which is the lumapi.FDTD instance.

        Returns:
            The result of the last expression, or None.
        """
        client = self._ensure_client()
        url = f"{self.base_url}/eval"
        payload = {"code": code}
        if self._session_id:
            payload["session_id"] = self._session_id

        log.debug("Remote eval: %s", code[:200])
        try:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                error = data.get("error", "Unknown error")
                log.error("Remote eval failed: %s", error)
                raise RuntimeError(f"Remote eval failed: {error}")
            return data.get("data", {}).get("result")
        except httpx.HTTPStatusError as e:
            log.error("HTTP error %s: %s", e.response.status_code, e.response.text)
            raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.ConnectError as e:
            log.error("Connection error: %s", e)
            raise RuntimeError(f"Cannot connect to {self.base_url}: {e}")

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def FDTD(self, hide: bool = True) -> RemoteLumapi:
        """Create a remote FDTD session (connects to server).

        This mimics the local `lumapi.FDTD(hide=True)` call.
        Actually creates a session on the remote server.
        """
        client = self._ensure_client()
        url = f"{self.base_url}/connect"
        try:
            resp = client.post(url, json={
                "solver": "lumerical-fdtd",
                "mode": "session",
                "ui_mode": "hidden" if hide else "shown",
            })
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                self._session_id = data["data"]["session_id"]
                self._connected = True
                log.info("Connected to remote Lumerical: session=%s", self._session_id)
            else:
                raise RuntimeError(f"Connect failed: {data.get('error', 'unknown')}")
        except httpx.ConnectError as e:
            raise RuntimeError(f"Cannot connect to {self.base_url}: {e}")
        return self

    def close(self) -> None:
        """Close the remote session."""
        if self._session_id and self._connected:
            try:
                client = self._ensure_client()
                client.post(f"{self.base_url}/disconnect",
                           json={"session_id": self._session_id})
            except Exception:
                pass
            finally:
                self._session_id = None
                self._connected = False
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> RemoteLumapi:
        return self.FDTD(hide=self.hide)

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── Project Management ───────────────────────────────────────────────────

    def newproject(self) -> None:
        """Create a new empty project."""
        self._eval("newproject()")

    def load(self, path: str) -> None:
        """Load a project file (.fsp).

        Note: path must be valid on the REMOTE machine.
        """
        safe_path = path.replace("\\", "/").replace('"', '\\"')
        self._eval(f'load("{safe_path}")')

    def save(self, path: str | None = None) -> None:
        """Save the current project.

        Args:
            path: Save path on the remote machine. If None, saves to current path.
        """
        if path:
            safe_path = path.replace("\\", "/").replace('"', '\\"')
            self._eval(f'save("{safe_path}")')
        else:
            self._eval("save()")

    def switchtolayout(self) -> None:
        """Switch to layout mode."""
        self._eval("switchtolayout()")

    # ── Object Manipulation ──────────────────────────────────────────────────

    def addfdtd(self) -> None:
        """Add an FDTD solver region."""
        self._eval("addfdtd()")

    def addrect(self) -> None:
        """Add a rectangle geometry object."""
        self._eval("addrect()")

    def addcircle(self) -> None:
        """Add a circle geometry object."""
        self._eval("addcircle()")

    def addpoly(self) -> None:
        """Add a polygon geometry object."""
        self._eval("addpoly()")

    def addring(self) -> None:
        """Add a ring geometry object."""
        self._eval("addring()")

    def addsphere(self) -> None:
        """Add a sphere geometry object."""
        self._eval("addsphere()")

    def addtriangle(self) -> None:
        """Add a triangle geometry object."""
        self._eval("addtriangle()")

    def addplane(self) -> None:
        """Add a plane wave source."""
        self._eval("addplane()")

    def addgaussian(self) -> None:
        """Add a Gaussian beam source."""
        self._eval("addgaussian()")

    def addtdfsf(self) -> None:
        """Add a TFSF source."""
        self._eval("addtdfsf()")

    def addpower(self) -> None:
        """Add a power monitor."""
        self._eval("addpower()")

    def addprofile(self) -> None:
        """Add a profile monitor."""
        self._eval("addprofile()")

    def addtime(self) -> None:
        """Add a time monitor."""
        self._eval("addtime()")

    def addmesh(self) -> None:
        """Add a mesh override region."""
        self._eval("addmesh()")

    def delete(self, name: str) -> None:
        """Delete a named object."""
        safe_name = name.replace('"', '\\"')
        self._eval(f'delete("{safe_name}")')

    def deleteall(self) -> None:
        """Delete all objects."""
        self._eval("deleteall()")

    # ── Property Access ──────────────────────────────────────────────────────

    def set(self, property: str, value: Any) -> None:
        """Set property of the currently selected object.

        Args:
            property: Property name (e.g., "x", "y", "material")
            value: Property value
        """
        safe_prop = property.replace('"', '\\"')
        if isinstance(value, str):
            safe_val = value.replace('"', '\\"')
            self._eval(f'set("{safe_prop}", "{safe_val}")')
        else:
            self._eval(f'set("{safe_prop}", {value})')

    def setnamed(self, name: str, property: str, value: Any) -> None:
        """Set property of a named object.

        Args:
            name: Object name
            property: Property name
            value: Property value
        """
        safe_name = name.replace('"', '\\"')
        safe_prop = property.replace('"', '\\"')
        if isinstance(value, str):
            safe_val = value.replace('"', '\\"')
            self._eval(f'setnamed("{safe_name}", "{safe_prop}", "{safe_val}")')
        else:
            self._eval(f'setnamed("{safe_name}", "{safe_prop}", {value})')

    def getnamed(self, name: str, property: str) -> Any:
        """Get property of a named object.

        Args:
            name: Object name
            property: Property name

        Returns:
            Property value
        """
        safe_name = name.replace('"', '\\"')
        safe_prop = property.replace('"', '\\"')
        return self._eval(f'getnamed("{safe_name}", "{safe_prop}")')

    def getobjectlist(self) -> list[str]:
        """Get list of all objects in the project."""
        return self._eval("getobjectlist()")

    def select(self, name: str) -> None:
        """Select an object by name."""
        safe_name = name.replace('"', '\\"')
        self._eval(f'select("{safe_name}")')

    # ── Simulation Control ───────────────────────────────────────────────────

    def run(self) -> None:
        """Run the simulation."""
        self._eval("run()")

    def stop(self) -> None:
        """Stop the simulation."""
        self._eval("stop()")

    def simulationdiverged(self) -> bool:
        """Check if the simulation diverged."""
        result = self._eval("simulationdiverged()")
        return bool(result) if result is not None else False

    # ── Result Retrieval ─────────────────────────────────────────────────────

    def getresult(self, monitor: str, attribute: str | None = None) -> Any:
        """Get result data from a monitor.

        Args:
            monitor: Monitor name
            attribute: Optional attribute name (e.g., "T", "E", "H").
                      If None, returns all available results.

        Returns:
            Result data (numpy array converted to nested list via JSON)
        """
        safe_monitor = monitor.replace('"', '\\"')
        if attribute:
            safe_attr = attribute.replace('"', '\\"')
            return self._eval(f'getresult("{safe_monitor}", "{safe_attr}")')
        else:
            return self._eval(f'getresult("{safe_monitor}")')

    def getdata(self, monitor: str, attribute: str) -> Any:
        """Get data from a monitor.

        Args:
            monitor: Monitor name
            attribute: Attribute name (e.g., "x", "y", "z", "f", "E")

        Returns:
            Requested data
        """
        safe_monitor = monitor.replace('"', '\\"')
        safe_attr = attribute.replace('"', '\\"')
        return self._eval(f'getdata("{safe_monitor}", "{safe_attr}")')

    def getvalue(self, monitor: str, attribute: str) -> Any:
        """Get value from a monitor (alias for getdata)."""
        return self.getdata(monitor, attribute)

    # ── Utility ──────────────────────────────────────────────────────────────

    def eval(self, code: str) -> Any:
        """Execute arbitrary LSF code on the remote server.

        This is the escape hatch for any lumapi call not covered
        by the convenience methods above.

        Args:
            code: LSF code string to execute

        Returns:
            Result of the code execution
        """
        return self._eval(code)

    def redraw(self, state: int = 1) -> None:
        """Enable/disable GUI redraw (no-op in headless mode)."""
        self._eval(f"redraw({state})")

    def redrawoff(self) -> None:
        """Disable GUI redraw."""
        self._eval("redraw(0)")

    def redrawon(self) -> None:
        """Enable GUI redraw."""
        self._eval("redraw(1)")
