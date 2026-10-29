"""HTTP client for communicating with remote Lumerical Agent Server."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5 minutes


class LumericalClient:
    """HTTP client for remote Lumerical Agent Server communication.

    Connects to a Windows machine running lumerical-agent-server on a
    specified port (default 7601) and sends requests to execute Lumerical
    FDTD/RCWA simulations.

    Architecture:
        Local Mac (sim-cli) --HTTP--> Remote Windows (lumerical-agent-server)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int = 7601,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.host = host or os.environ.get("LUMERICAL_HOST")
        self.port = port
        authority = f"[{self.host}]" if self.host and ":" in self.host and not self.host.startswith("[") else self.host
        self.base_url = f"http://{authority}:{port}"
        self.timeout = timeout
        self._client: httpx.Client | None = None
        self.session_id: str | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if not self.host:
            raise ValueError("Lumerical host is required; pass driver_options.host or LUMERICAL_HOST")
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def health(self) -> dict[str, Any]:
        """Check if the remote server is healthy."""
        return self.get("/health")

    def detect(self, solver: str = "lumerical-fdtd") -> dict[str, Any]:
        """Detect Lumerical installation on remote machine."""
        return self.get(f"/detect/{solver}")

    def get(self, path: str) -> dict[str, Any]:
        """Send GET request to the remote server."""
        url = f"{self.base_url}{path}"
        log.debug("GET %s", url)
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            log.error("HTTP error %s: %s", e.response.status_code, e.response.text)
            return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except httpx.ConnectError as e:
            log.error("Connection error: %s", e)
            return {"ok": False, "error": f"Cannot connect to {self.base_url}: {e}"}
        except Exception as e:
            log.error("Request error: %s", e)
            return {"ok": False, "error": str(e)}

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send POST request to the remote server."""
        url = f"{self.base_url}{path}"
        log.debug("POST %s %s", url, json)
        try:
            headers = {"X-Sim-Session": self.session_id} if self.session_id else {}
            response = self.client.post(url, json=json or {}, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            log.error("HTTP error %s: %s", e.response.status_code, e.response.text)
            return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except httpx.ConnectError as e:
            log.error("Connection error: %s", e)
            return {"ok": False, "error": f"Cannot connect to {self.base_url}: {e}"}
        except Exception as e:
            log.error("Request error: %s", e)
            return {"ok": False, "error": str(e)}
