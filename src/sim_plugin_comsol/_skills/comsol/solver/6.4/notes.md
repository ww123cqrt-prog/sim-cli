# COMSOL 6.4 notes

Latest tested as of 2026 Q1. Drives cleanly via mph 1.2.x. The
plugin-owned block-with-hole smoke workflow in `base/workflows/` runs
unchanged on 6.4.

Record only differences confirmed by live introspection, official docs,
or a reproduced workflow failure. Do not turn this file into a static API
table.

## Confirmed differences

- Mode Following can be driven by either a visible Study `Parametric Sweep`
  plus an Eigenfrequency step, or by an Eigenfrequency auxiliary sweep that
  generates an `EigenvalueParam` attribute. In both cases the Eigenvalue solver
  has `modefollowing=on` and a `ModeFollowing` child. Do not configure both
  sweep owners for the same parameter. COMSOL's Wave Optics
  `bandgap_photonic_crystal` model uses the visible Study Parametric Sweep.
- A physics `PeriodicCondition` exposes manual target control through the
  Boolean property `manualDestinationSelection` and the named extra selection
  `destinationDomains`.

## Workarounds

- A component Identity pair tag created on a Form Union was not accepted as a
  named physics boundary selection in a reproduced Wave Optics build. Use the
  union of source/destination boundaries and set `destinationDomains`
  explicitly. Do not retain an otherwise unused pair as an audit record:
  EWFD's default `dcont1` consumed `pairy` in a reproduced 3D Bloch model and
  failed eigensolver assembly with `src2dst_pairy` / incompatible source and
  destination meshes.
- `comsolbatch` can return exit code zero after a compiled Java class throws.
  Require an explicit success sentinel and inspect the batch log.

## Verification snippets

- Use `base/reference/java_api_patterns.md` to confirm tags and
  properties before applying any version-specific workaround.
- For a model that claims a GUI-visible k scan, reload it and verify the Study
  contains a `Parametric` feature with the expected `pname` and `plistarr`.
  A solver-only `EigenvalueParam` is an auxiliary-sweep contract, not a visible
  Study Parametric Sweep.
