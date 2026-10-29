# Controller workspace migration

The fork integrates upstream sim-cli 0.4.2 with the existing workspace transfer
extensions and platform-aware COMSOL launch paths. Source history from the
previous COMSOL and auxiliary-plugin repositories is retained by merge commits.

Our controlled install consists of the core and `plugins/comsol`,
`plugins/lumerical`, and `plugins/cmd`. Other upstream plugins remain available
as independent packages; their presence does not install their vendor SDKs.

Use `uv sync --locked --group controllers` in a development checkout, then
`python scripts/workspace.py test --package <core|comsol|lumerical|cmd>` in that
environment. Tests run in separate processes. Each package builds separately
with `uv build --no-sources --package <distribution>`.

The plugin index directs modified packages to this fork. For reproducible
installation, pin the reviewed Git commit or use verified wheel artifacts;
do not replace custom packages with same-version public PyPI packages.

The installed runtime stays independent from the development worktree. Keep
existing host-specific executable paths while switching editable sources only
after candidate verification. Snapshot the previous environment and source
commit first; restore both together on rollback. Do not remove a checkout
while an installed editable package still references it.

Private machine caches supply COMSOL/Lumerical executable paths and connection
profiles. Local long computations require an external process owner and
stdout/stderr plus PID/status records. Remote unattended work uses the
existing Windows persistence rules. SSH-created sessions do not provide an
interactive desktop; GUI validation is separate from headless validation.

The auxiliary CMD service keeps its existing authentication, confirmation and
concurrency behavior. Its service deployment is not automatically replaced by
workspace installation. Source consolidation does not bypass these controls.

Release workflows select one distribution and retain reviewed artifact hash
checks. Migration creates no release tags and performs no PyPI publication.
