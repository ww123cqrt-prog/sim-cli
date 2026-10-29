# Lumerical FDTD / RCWA controller

This SDK-free package exposes `lumerical-fdtd` and `lumerical-rcwa` through
sim-cli. It connects to the existing Lumerical Agent Server; the vendor API
and license stay on the solver host.

Install the repository's `controllers` dependency group. The core runtime
host and Lumerical backend host are separate settings. When using the local
core runtime, select the backend with:

```sh
sim connect --solver lumerical-fdtd --ui-mode no_gui --driver-option host=<solver-host> --driver-option port=7601
sim exec 'x=1;'
sim disconnect
```

Use the absolute sim executable recorded by the selected machine's local
configuration. `LUMERICAL_HOST` can supply the backend host for checks and
one-shot operations. There is no machine address embedded in the package.
`sim --host ...` selects a remote **core runtime**, not the nested backend.

Session execution forwards Lumerical script to `/exec` with the owned backend
session selector. It does not silently choose another session.

For one-shot operations, the backend must be able to read the script path.
Use a local JSON request file containing `{"script":"<remote-script-path>"}`
and run it with `sim run request.json --solver lumerical-fdtd` (or
`lumerical-rcwa`). A local `.lsf` path is useful only if the backend sees the
same shared path. This package does not implicitly upload local projects.

The returned `RunResult` retains backend failures and artifact metadata.
A successful transport or model load does not certify a completed simulation.
The existing backend `/run` loads a project or evaluates a script; actual
solving must be specified by the supplied script and checked from its outputs.

The optional Agent Server remains at `lumerical_agent_server.py`. Existing
service deployment stays separate from package installation. Select its
installation with `LUMERICAL_ROOT`; no GUI sessions use `hide=True`. Do not
start or replace a shared service as a side effect of installing this package.
