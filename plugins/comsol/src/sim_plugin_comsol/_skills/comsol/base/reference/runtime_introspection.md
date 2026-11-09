# Runtime introspection

Use live runtime introspection before guessing COMSOL Java API details.
The goal is to make the agent behave like an engineer inspecting the
current model state, not like a script generator hoping a large snippet
works on the first try.

## Client-server login initialization

`No user name and password could be obtained` occurs before model execution.
Compare the actual host, launcher, SDK and authentication state before calling
it a package regression, license failure or model problem. Native Java batch,
MATLAB LiveLink and a Python client need not use the same connection path.

On a Windows COMSOL 6.4 host with no local login record, the plugin's silent
launch failed with both the old and new plugin. Starting an owned local server
with the standard `mph.Server` launcher initialized automatic login; subsequent
unmodified plugin connections worked. This was observed with mph 1.3.1 and
JPype 1.7.0/1.7.1; it is a host initialization result, not a universal SDK fix.

If reproducing that diagnosis, use a new owned server and a free local port,
read the active COMSOL version, and disconnect/close only that server. Verify
the normal entrypoint again after initialization. Keep the initial failure
and the before/after launch records. Do not print login files or ask the user
to paste passwords into chat. If interactive initialization is needed, the
user can enter credentials in the local COMSOL interface.

## Preferred inspect targets

Run these after `uv run sim connect --solver comsol` and after every meaningful
model edit:

```bash
uv run sim inspect session.health
uv run sim inspect comsol.model.identity
uv run sim inspect last.result
uv run sim inspect comsol.model.describe_text
uv run sim inspect comsol.model.describe
uv run sim inspect comsol.node.properties:<tag-or-dot-path>
```

Target meanings:

| Target | Use |
|---|---|
| `session.health` | Check solver process, UI mode, COMSOL version, PIDs, logs, and whether a visible desktop is live. |
| `comsol.model.identity` | Check active/bound model tag, title/label, saved file path or database location, model path, read-only state, and whether the session has enough durable identity to resume. |
| `last.result` | Check the last `uv run sim exec` result, artifacts, probes, diagnostics, and exceptions. |
| `comsol.model.describe_text` | Human-readable summary of components, physics, features, properties, and warnings. |
| `comsol.model.describe` | Structured summary for programmatic comparison. |
| `comsol.node.properties:<tag-or-dot-path>` | Inspect one suspicious node before calling `set(...)` on it. |

Use `:` or `.` inside driver-specific inspect names. Avoid slash-delimited
inspect names because older sim-cli routes may treat slashes as URL path
segments.

## Compatibility rules

COMSOL versions and installed modules vary. Treat inspect output as
best-effort:

- Missing optional fields are not fatal.
- `partial=true` means use the available fields, then fall back to raw
  Java probing for the missing surface.
- `warnings` are debugging clues, not automatic failures.
- A missing inspect target means the plugin is older; use the raw Java
  snippets in `java_api_patterns.md`.
- Do not copy property names from another model until the live node
  reports that they exist.

## When to inspect

Inspect after each layer:

| Layer | Check |
|---|---|
| Identity | Active model tag, bound model tag, model title/label, saved `.mph` or database location, model path, and intended working folder. |
| Geometry | Component, geometry sequence, named selections, domain/boundary counts where available. |
| Materials | Material tags, material selections, key material property groups. |
| Physics | Physics interface tags, feature tags, feature types, non-empty selections. |
| Mesh | Mesh feature tags, build status, mesh statistics or saved artifact probes. |
| Study | Study tags, solver sequence, relevant parameters. |
| Results | Dataset tags, plot group tags, numerical evaluation nodes, exported artifacts. |

## Fallback pattern

If an inspect target is unavailable, run a small `uv run sim exec` snippet that
reads only model state and writes `_result`. Keep it read-only.

```python
def _tags(container):
    try:
        return list(container.tags())
    except Exception as exc:
        return {"error": type(exc).__name__, "message": str(exc)}

summary = {"components": _tags(model.component())}
for comp_tag in summary["components"]:
    comp = model.component(comp_tag)
    summary.setdefault("physics", {})[comp_tag] = _tags(comp.physics())
    summary.setdefault("materials", {})[comp_tag] = _tags(comp.material())
    summary.setdefault("meshes", {})[comp_tag] = _tags(comp.mesh())

_result = summary
```

For one node:

```python
node = model.component("comp1").physics("ht").feature("temp1")
_result = {
    "type": node.getType() if hasattr(node, "getType") else None,
    "properties": list(node.properties()),
}
```

## Interpreting failures

Use `last.result` first. Then inspect the live model and the suspicious
node. Common patterns:

| Symptom | Likely cause | Next check |
|---|---|---|
| Unknown tag | The model uses different auto-generated tags. | List parent `tags()` before accessing the child. |
| Unknown property | Property name differs by feature type or version. | Inspect `properties()` on the live node. |
| Empty selection | Geometry did not create the expected domains/boundaries. | Inspect geometry and named selections. |
| Solver failure | Earlier physics, material, selection, or study setup is inconsistent. | Review model state layer by layer. |
| Missing module | Host does not have the required COMSOL product. | Check `session.health`, docs search results, and choose a capability fallback path. |
