---
name: lumerical-fdtd
description: Drive an explicitly configured Lumerical FDTD or RCWA backend through the sim-cli Lumerical plugin, with bounded operations and retained result evidence.
---

# Lumerical FDTD and RCWA

Before new modeling, solving, or substantive revision, consult the shared
prior-experience index bundled with the core. Its installed location is
`importlib.resources.files("sim").joinpath("_skills/sim-cli/references/prior-experience.md")`.
Read current case/research reviews and retained failure lessons; official
rebuilds and independent research have separate identities and evidence limits.

Resolve the requested solver host from the operator's private configuration.
Use remote-windows-workstation for Windows identity and cached installation
paths. Never substitute another machine's address or SDK path.

The core runtime and backend Agent Server are separate hops. Supply the
backend via `driver_options.host` / `port`, or `LUMERICAL_HOST` for checks and
one-shot commands. `sim --host` selects the core runtime. Use the operator's
verified absolute sim/Python paths and preserve long-task durability rules.

Connect with the selected `lumerical-fdtd` or `lumerical-rcwa` driver. Execute
bounded Lumerical script in the owned session, inspect outputs, and disconnect.
The driver owns only the session ID returned for its connection. Do not close
or replace unrelated sessions or restart an existing service.

For one-shot commands, a JSON request can name a remote-readable `script`.
Files are not uploaded implicitly. Match the selected solver and verify all
physical inputs and acceptance criteria before a real solve.

Success requires result evidence appropriate to the task: an API connection,
a saved project, and a converged solve are separate claims. Keep stdout,
stderr, exit status, artifacts and any unverified steps distinct. Do not infer
RCWA numerical correctness from FDTD connection success.
