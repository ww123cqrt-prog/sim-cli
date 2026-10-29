# Prior simulation experience

Use this lookup before a new model, solve, or substantive revision, including
solver-native execution outside `sim`. Search by physical objective, device,
boundary/source type, output quantity, and the actual error when relevant.
Read a matching method and its source case before reusing their recipe. Record
the sources, applicable conditions, unresolved limits, or a negative search.
An unavailable library is a lookup limitation, not evidence of no prior work.

## Find the current host's library

Obsidian's own configuration identifies local vaults on both macOS and Windows;
do not carry a Mac path onto Windows. Run this read-only snippet with the
host's configured Python, without creating or syncing an environment:

```python
import json, os, sys
from pathlib import Path

if sys.platform == "darwin":
    config = Path.home() / "Library/Application Support/obsidian/obsidian.json"
elif sys.platform == "win32":
    config = Path(os.environ["APPDATA"]) / "obsidian/obsidian.json"
else:
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "obsidian/obsidian.json"
if config.is_file():
    for item in json.loads(config.read_text(encoding="utf-8-sig")).get("vaults", {}).values():
        root = Path(item["path"])
        if any((root / part).is_dir() for part in ("COMSOL", "Lumerical/FDTD")):
            print(root)
```

If multiple libraries match, choose by the requested case and verify the
relevant files. A configured path is not proof that cloud files are readable
or current. If configuration is absent, use an already configured operator
location; report the lookup gap rather than scanning unrelated disks.

## Search within the selected vault

Paths below are relative to the vault. Use available text search, such as
`rg -n -i -- "Bloch|Floquet|mode following" <relevant-directory>`, or the host's
native file/text search. Start with methods and registration, then read the
matching complete case and current review. Do not ingest every note by default.

| Experience | Lookup sources |
|---|---|
| COMSOL official learning | `COMSOL/学习总览.md`, `COMSOL/方法总结/`, `COMSOL/案例笔记/` |
| Lumerical official learning | `Lumerical/FDTD/方法总结/案例登记.json`, `Lumerical/FDTD/案例笔记/`, `Lumerical/FDTD/方法总结/` |
| Independent research / paper reproduction | `Lumerical/FDTD/研究复盘/index.md` and its R-series source notes; the operator's project index |
| Lumerical command reference | `Lumerical/LumericalScrpitCommand.md`, `Lumerical/LumericalScriptCommamd/`; these are command docs, not learned cases |
| Existing project-specific experience | The active solver skill's project references and retained failure/method records |

The directory named `FDTD` also includes MODE, RCWA, STACK, INTERCONNECT and
coupled workflows. Check actual solver and completed scope; do not label the
entire library as pure FDTD. The registry/current case and referenced review
take precedence over superseded batch progress or withdrawn acceptance.

Also check the operator-installed reference at
`Path.home() / ".agents/skills/sim-cli/references/operator-experience.md"`
(or the operator's configured skill root), even when reading this file from
the installed core package. Read it if present and resolve its links relative
to its own directory. It links private project families and retained records
unavailable in the public package. Host-specific
record IDs are namespaced by source: two records named `sp_001` are not
automatically the same experience. Preserve originals and treat copied records
as dated snapshots. Host profiles and private model/data paths stay outside
the public repository.

## Reuse and count correctly

- COMSOL learning units use stable `case_id` values; exclude `redirect: true`
  / `并入主案例` geometry attachments from independent-case counts.
- Lumerical official units use the registry's stable case IDs and numbers.
  Aliases, 2D/3D attachments, sweeps, repairs, and from-empty reconstructions of
  an official example remain within that official case.
- Independent research uses normalized DOI or stable project identity. Count
  stages and parameter variants within the same project once. Distinguish
  registered research from unregistered project-family leads and tool probes.
- Learning acceptance, complete workflow execution, numerical convergence,
  file availability, and historical versus current evidence are separate facts.
  Check `learning_status`, `accepted_scope` / `numerical_status`, COMSOL's
  document/model/result/review fields, and any later correction.

Read original model/PDF/raw-data paths on their owning host. A synced note does
not establish that its linked large artifacts are present locally. Remote
Windows access follows `remote-windows-workstation` and its private host cache;
preserve the current host's executable paths and durable launch rules. Looking
up history does not authorize new learning jobs, reruns, or note edits.
