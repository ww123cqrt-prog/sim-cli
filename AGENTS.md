# Workspace maintenance

Core runtime lives in `src/sim`; each independently published plugin lives in
`plugins/<solver>`. Keep the entry-point interface and plugin `_skills/` paths.
`simparse` is a separate PyPI dependency; do not vendor its implementation.

Use `uv sync --locked --all-packages --group dev`, then
`uv run --no-sync python scripts/workspace.py test`. Tests run in separate
processes per package. Public tests use unit tests and tiny synthetic fixtures.
Solver execution cases and detailed regression data belong in private
`sim-proj/cases/`; do not add them here.

Regenerate `plugin-index.json` with `uv run python scripts/workspace.py index`
after package metadata changes. Check it with `--check`.

Build one package with `uv build --no-sources --package <distribution>`.
Core releases use `v<version>` and `publish.yml`; plugin releases use
`<solver>-v<version>` and `plugin-publish.yml`, each matching package metadata.
Never combine sibling distributions in one publication artifact set.

For this fork's core/COMSOL/Lumerical/CMD work, use the `controllers` group
instead of installing every workspace plugin. Preserve platform-specific
COMSOL paths and existing workspace file-transfer behavior. Keep private host
profiles outside the repository. Existing Mac absolute launcher paths and
long-task process ownership/logging rules remain in the operator's local
skills; remote Windows execution uses remote-windows-workstation and its
per-machine software cache. Do not tie unattended computations to an agent
terminal or replace an existing shared service during package installation.
