"""Build and independently install the four controller distributions."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

PACKAGES = ('sim-cli-core', 'sim-plugin-comsol', 'sim-plugin-lumerical', 'sim-plugin-cmd')
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='sim-wheel-check-') as scratch:
        work = Path(scratch)
        output = args.output.resolve() if args.output else work/'dist'
        wheels = []
        for name in PACKAGES:
            destination = output/name
            subprocess.run(['uv', 'build', '--no-sources', '--package', name,
                            '--out-dir', str(destination)], cwd=ROOT, check=True)
            matches = list(destination.glob('*.whl'))
            if len(matches) != 1:
                raise RuntimeError(f'Expected exactly one wheel for {name}')
            wheels.append(matches[0])
        constraints = work/'constraints.txt'
        subprocess.run(['uv','export','--locked','--group','controllers','--no-hashes',
                        '--no-emit-workspace','--output-file',str(constraints)],cwd=ROOT,check=True,
                       stdout=subprocess.DEVNULL)
        for profile in ('core','controllers'):
            environment = work/profile
            subprocess.run(['uv','venv','--python',sys.executable,str(environment)],check=True)
            python = environment/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
            selected = wheels[:1] if profile=='core' else wheels
            subprocess.run(['uv','pip','install','--python',str(python),'--constraint',str(constraints),
                            *map(str,selected)],check=True)
            check = r'''
import json,sys,tempfile,subprocess
from importlib import metadata
from pathlib import Path
import sim
profile=sys.argv[1]
entries={p.name:p for p in metadata.entry_points(group='sim.drivers')}
if profile=='core':
    assert not entries, entries
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'tiny.inp'
        path.write_text('*Heading\nsynthetic\n*Node\n1,0,0,0\n')
        binary=Path(sys.executable).with_name('sim.exe' if sys.platform=='win32' else 'sim')
        result=subprocess.run([str(binary),'--json','scan',str(path)],capture_output=True,text=True,check=True)
        assert json.loads(result.stdout)['ok']
else:
    for name in ('comsol','lumerical-fdtd','lumerical-rcwa','cmd'):
        assert callable(entries[name].load())
    import sim_plugin_comsol,sim_plugin_lumerical,sim_plugin_cmd
    assert (sim_plugin_comsol.skills_dir/'comsol/SKILL.md').is_file()
    assert (sim_plugin_lumerical.skills_dir/'lumerical-fdtd/SKILL.md').is_file()
for name in ('sim-cli-core',) if profile=='core' else ('sim-cli-core','sim-plugin-comsol','sim-plugin-lumerical','sim-plugin-cmd'):
    data=json.loads(metadata.distribution(name).read_text('direct_url.json'))
    assert not data.get('dir_info',{}).get('editable'),name
assert Path(sim.__file__).is_relative_to(Path(sys.prefix)),sim.__file__
print(profile+' wheel installation PASS')
'''
            subprocess.run([str(python),'-c',check,profile],cwd=work,check=True)


if __name__ == '__main__':
    main()
