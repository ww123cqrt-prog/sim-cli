"""Build the wheel and assert that bundled skill files ship."""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_wheel_contains_skills(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist"
    out_dir.mkdir()

    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"build failed: {proc.stderr[-2000:]}"

    wheels = list(out_dir.glob("sim_plugin_comsol-*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"

    with zipfile.ZipFile(wheels[0]) as zf:
        names = set(zf.namelist())

    required = {
        "sim_plugin_comsol/__init__.py",
        "sim_plugin_comsol/driver.py",
        "sim_plugin_comsol/desktop_attach/__init__.py",
        "sim_plugin_comsol/desktop_attach/cli.py",
        "sim_plugin_comsol/_skills/comsol/SKILL.md",
        "sim_plugin_comsol/_skills/comsol/doc-search/README.md",
        "sim_plugin_comsol/_skills/comsol/doc-search/src/sim_comsol_doc/cli.py",
        "sim_plugin_comsol/_skills/comsol/base/reference/java_api_patterns.md",
        "sim_plugin_comsol/_skills/comsol/base/reference/bloch_mode_following.md",
        "sim_plugin_comsol/_skills/comsol/base/reference/runtime_introspection.md",
        "sim_plugin_comsol/_skills/comsol/base/workflows/model_review_loop.md",
        "sim_plugin_comsol/_skills/comsol/base/workflows/debug_failed_exec.md",
        "sim_plugin_comsol/_skills/comsol/base/workflows/bloch_mode_following/README.md",
        "sim_plugin_comsol/_skills/comsol/base/workflows/bloch_mode_following/BuildBlochModeFollowingBase.java",
        "sim_plugin_comsol/_skills/comsol/base/workflows/bloch_mode_following/VerifyBlochModeFollowingBase.java",
        "sim_plugin_comsol/_skills/comsol/base/workflows/bloch_mode_following/VerifyBlochModeFollowingGammaSolve.java",
        "sim_plugin_comsol/_skills/comsol/base/workflows/bloch_mode_following/COMSOL64_3D_Bloch_ModeFollowing_Base.mph",
        "sim_plugin_comsol/_skills/comsol/base/workflows/bloch_mode_following/receipt.json",
    }
    missing = required - names
    assert not missing, f"missing from wheel: {missing}"
