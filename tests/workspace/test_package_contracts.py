from importlib import metadata
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('name',['comsol','lumerical-fdtd','lumerical-rcwa','cmd'])
def test_installed_driver_entry_point_loads(name):
    entries=[ep for ep in metadata.entry_points(group='sim.drivers') if ep.name==name]
    if not entries:
        pytest.skip('optional controller package not installed in core-only environment')
    assert callable(entries[0].load())


def test_modified_plugins_resolve_to_our_git_source():
    spec=importlib.util.spec_from_file_location('workspace_index',ROOT/'scripts/workspace.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows={r['solver']:r for r in module.plugin_index()['plugins']}
    for name in ['comsol','lumerical','cmd']:
        assert 'ww123cqrt-prog/sim-cli.git@' in rows[name]['install_spec']
        assert rows[name]['install_spec'].endswith('#subdirectory=plugins/'+name)
