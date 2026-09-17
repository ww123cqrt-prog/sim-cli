# Bloch parameter sweeps with COMSOL Mode Following

Use this reference when building or reviewing a periodic eigenfrequency model
whose Bloch vector changes along an ordered path. The purpose is to preserve a
clear parameter, boundary, and solver contract. It does not make a mode number
a physical identity and it does not prove mesh/PML convergence.

## 1. Use one ordered scalar path parameter

Keep the reduced Bloch coordinates and the physical Floquet vector separate:

```text
k              ordered dimensionless path coordinate
qx_scan(k)     reduced x coordinate
qy_scan(k)     reduced y coordinate
kBx            2*pi*qx_scan/a
kBy            2*pi*qy_scan/a
```

If manual single-point operation must coexist with the sweep, use an explicit
switch rather than silently changing the meaning of `qx` and `qy`:

```text
qx_active = if(use_k_scan>0.5,qx_scan,qx)
qy_active = if(use_k_scan>0.5,qy_scan,qy)
```

`k` is dimensionless. `kBx,kBy` have physical reciprocal-length units.

For a piecewise high-symmetry path, keep k strictly ordered and include each
joint once. A Gamma-X-M-Gamma parameterization is:

```text
0<=k<=1: (qx,qy)=(0.5*k,0)
1<=k<=2: (qx,qy)=(0.5,0.5*(k-1))
2<=k<=3: (qx,qy)=(0.5*(3-k),0.5*(3-k))
```

## 2. Make source and destination explicit

For a square cell centered at the origin, a stable convention is:

```text
x source: x=-a/2  -> x destination: x=+a/2
y source: y=-a/2  -> y destination: y=+a/2
```

In a `PeriodicCondition`, select the union of source and destination faces,
set the Boolean property `manualDestinationSelection=true`, and populate its
named extra selection `destinationDomains` with the destination faces. Do not
assume that a component Identity pair tag is directly accepted as a physics
boundary selection in a Form Union geometry. Do not keep an otherwise unused
Identity pair merely as an audit record: EWFD's default `dcont1` can consume it
and impose an unintended source/target mesh-mapping constraint. Audit the
source/destination IDs and translation from the `PeriodicCondition` itself.

Always pass the full vector:

```java
feature("pcx").set("kFloquet", new String[]{"kBx", "kBy", "0"});
```

COMSOL documents the source-to-destination Floquet factor as

```text
exp(-i*kF dot (r_dst-r_src))
```

Verify Gamma, X, M and a +/-q pair analytically before solving a long path.
For the source/destination convention above, Gamma gives `(1,1)`, X gives
`(-1,1)`, M gives `(-1,-1)`, and the +/-q phases are complex conjugates.

## 3. Use one parameter-sweep owner

COMSOL 6.4 supports two different, valid parameter-sweep layouts for
eigenmode following. Choose one and record which contract the model uses.

### Visible Study Parametric Sweep

This is the layout used by COMSOL's Wave Optics
`bandgap_photonic_crystal` application and is preferable for a reusable GUI
case model:

```text
Study
  Parametric Sweep (k)
  Eigenfrequency (Mode following = on)

Eigenvalue Solver (modefollowing = on)
  ModeFollowing
```

The Study tree visibly owns the k list. Set `pdistrib=off` on the Parametric
Sweep so the predecessor state is preserved. Set `stopwhennoeigfound=on` on
the Eigenvalue solver when a missing eigensolution must fail closed. This
layout does not also need an `EigenvalueParam` child.

### Eigenfrequency Auxiliary Sweep

If the parameter is configured as an auxiliary sweep inside the
Eigenfrequency study step, the generated solver hierarchy is:

```text
Eigenvalue
  EigenvalueParam
  ModeFollowing
```

Here `EigenvalueParam` owns the ordered parameter list; use `pdistrib=off` and
`peigonerror=stop` there.

Do not combine a Study Parametric Sweep over k with an `EigenvalueParam` sweep
over the same k list. That creates two sweep owners and can repeat or nest the
calculation. Keep a separate manual single-point study if needed.

In either layout, distributing individual k points destroys the
predecessor-state sequence. Skipping a failed point creates a visually complete
path with missing evidence.

Initial Mode Following settings can remain conservative:

```text
detectifcannotfollowpreviousmodes=on
thresholdmodefollowing=0.01
highsenseigdetection=off
followextramodes=off
```

The requested eigenpair count is a candidate-space size, not the number of
physical bands. When a mode cannot be followed, inspect path step, eigensolver
shift, candidate count, degeneracy and PML-localized competitors before enabling
extra-mode following.

## 4. Keep top and bottom PML contracts separate

Disconnected top and bottom PML slabs should be separate PML coordinate-system
nodes with explicit domain selections. Record their physical adjacent media,
normal direction and swept-mesh ownership. A single node that happens to select
both domains is harder to review and can hide an incorrect layer assignment.

Mode Following does not validate the PML. Repeat selected points with another
PML/buffer setup and inspect PML energy localization.

## 5. Build-only and review workflow

For a review MPH:

1. Load an immutable or copied parent.
2. Remove saved solutions/results if the output must be unsolved.
3. Add parameters, explicit Floquet destinations, separate PML nodes, one
   declared sweep owner, and solver attributes.
4. Permit geometry and mesh builds only when needed to make selections real.
5. Never call a study or solver run method.
6. Save under a new path.
7. In a fresh COMSOL process, reload the MPH and verify the saved structure.

The verifier should check solution stores with `isEmpty()`, not only the absence
of plot groups. Also check geometry/mesh counts, boundary selections, complete
Floquet vector, solver hierarchy and parameter ownership. For a GUI case that
claims a Study Parametric Sweep, verify that the Study actually contains a
`Parametric` feature with the expected k range; a solver-only attribute is not
equivalent to a visible Study scan.

`comsolbatch` can report a process exit code of zero even when a Java class
throws and the batch log contains an error. Require an explicit success sentinel
from the Java program and scan the batch log for the COMSOL error block before
accepting the artifact.

A structural reload is necessary but insufficient. Run at least one bounded
Gamma eigensolve without saving the solved state. Record DOFs, elapsed time and
peak memory, and require a solve sentinel after matrix assembly. This regression
specifically detects periodic-map failures that a tree/property audit cannot.

## 6. Evidence boundary after solving

Native Mode Following is an identity aid. After a solve, still check:

- forward/reverse paths at shared q points;
- complex-field overlap for isolated modes;
- projector overlap/principal angles for near-degenerate clusters;
- symmetry at high-symmetry points;
- selected eigenpair residuals;
- PML energy fractions;
- mesh and PML/buffer convergence.

Inside an exact degenerate subspace, component order is basis dependent. Do not
repair a band plot by forcing solution numbers or nearest-frequency sorting.
