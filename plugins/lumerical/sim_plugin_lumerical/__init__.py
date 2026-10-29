"""Lumerical FDTD/RCWA driver plugin for sim-cli.

Distributed as an out-of-tree plugin; discovered by sim-cli via the
``sim.drivers`` entry-point group. Bundled skill files (under ``_skills/``)
are exposed via the ``sim.skills`` entry-point group.

Architecture:
- Local Mac (sim-cli) connects to remote Windows via HTTP
- Remote Windows runs lumerical-agent-server on port 7601
- Server uses lumapi to control Lumerical FDTD/RCWA
"""
from importlib.resources import files

from .driver import LumericalFDTDDriver, LumericalRCWADriver

skills_dir = files(__name__) / "_skills"


plugin_info = {
    "name": "lumerical-fdtd",
    "summary": "Driver plugin for Lumerical FDTD/RCWA via remote HTTP server.",
    "homepage": "https://github.com/ww123cqrt-prog/sim-cli/tree/main/plugins/lumerical",
    "license_class": "commercial",
    "solver_name": "lumerical-fdtd",
}

__all__ = ["LumericalFDTDDriver", "LumericalRCWADriver", "skills_dir", "plugin_info"]
