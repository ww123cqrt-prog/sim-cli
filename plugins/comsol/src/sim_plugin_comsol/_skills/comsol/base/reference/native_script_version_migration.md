# Native Java / MATLAB M-file version migration

Use when a target COMSOL version cannot open a newer `.mph`, and the task is to rebuild that model in the target version. Prefer native source export before manually reconstructing the whole model. This is source-level reconstruction, not binary MPH downgrading; cross-version API compatibility still needs a test.

## Export from the source version

Open the original with the version that can read it, preserve the original, and compact the history in memory before exporting:

```java
Model model = ModelUtil.load("Source", "C:/case/original.mph");
model.resetHist();
model.save("C:/case/NativeModel.java", "java");
model.save("C:/case/NativeModel.m", "m");
```

These are alternative native source formats. Export only the format the task needs. The original solved fields and exact generated mesh are not transported as existing numerical data by these commands; the target executes the definitions, regenerates its mesh and recomputes the requested studies. Keep the original model and numeric references for comparison.

Do not use a `.java`/`.m` suffix on `comsolbatch -outputfile` as a substitute for source export: a binary MPH can acquire that suffix. Verify readable source. Read the generated execution calls (`run`, `runAll`, `runNoGen`, parameter sweeps) and external file dependencies before running it. Export-only authorization does not authorize every study contained in the exported script.

## Execute in the target version

**Java** needs the target COMSOL runtime and its compiler, without MATLAB:

```powershell
& "$comsolBin/comsolcompile.exe" NativeModel.java
& "$comsolBin/comsolbatch.exe" -inputfile NativeModel.class -batchlog replay.log -nosave
```

Inspect generated `main`/`run` methods: explicitly save the returned model under the target workspace. For a long replay, place a save checkpoint immediately after its authorized study, before optional plotting setup. Keep the raw export and a diff of the execution copy. See [Java batch patterns](java_batch_patterns.md) for a full wrapper.

**MATLAB M-file** also needs MATLAB and LiveLink for MATLAB. A new owned server can be launched using the native 6.3 wrapper:

```matlab
function replay_m(comsolRoot, workdir)
addpath(fullfile(comsolRoot,'mli'));
[port,pid] = mphstartcomsolmphserver('comsolpath',comsolRoot, ...
    'hide','on','silent','on');
mphstart(port);
import com.comsol.model.util.*
cleanup = onCleanup(@() ModelUtil.disconnect);
model = NativeModel;
model.save(fullfile(workdir,'rebuilt.mph'));
end
```

Use `matlab -batch` for a headless scripted run. Match the primary function name to its `.m` filename in the execution copy; the tested native export began with `function out = model` even when saved under another filename. Own-server PID/port and actual MATLAB/COMSOL versions belong in the run receipt. Disconnect owned sessions gracefully; do not terminate unrelated servers or solver jobs. Honor the user's selected machine and saved resource policy rather than adding an arbitrary `-np`.

Choose Java when the task only needs COMSOL replay and MATLAB would add an unnecessary dependency. M-files are useful when the task already uses MATLAB analysis or LiveLink. They call the same COMSOL engine; agreement between these routes is not independent physical-solver validation.

## Compatibility and acceptance

- Preserve raw exports and first errors. Test the target compiler/runtime, not just the filename or model-file existence.
- Distinguish a path/lifecycle change, an optional visualization-property change, and a physics/solver-definition change. Do not silently remove unsupported physics to make the script finish.
- Record external CAD/table/function dependencies and transfer the required files with the script. A source export is not always self-contained.
- After replay, save and reopen in a fresh native process. Compare actual parameters, final geometry/material mapping, boundary conditions, mesh/study identity and the relevant numerical outputs. Rebuilt meshes need not be element-for-element identical.
- For a stored eigenmode, match complex components on common physical coordinates and record the mode family. Magnitude pictures or equal mode numbers alone do not prove identity. Use the case's declared metric/tolerance; do not turn one case's 0.98 identity gate into a universal migration threshold.
- If postprocessing fails after a successful save, reopen that saved state and repeat only the extraction.

## Observed compatibility limits

Native Java and MATLAB M-file replay were both exercised from COMSOL 6.4.0.293
to 6.3.0.290, including target save and fresh native readback. This is a tested
source-reconstruction route, not a guarantee that every model or physics API
is backward compatible. Detailed solver cases and numerical acceptance
records remain in the operator's private experience library.

- A 6.4 image-export property, `highprecisioncolor`, was unsupported in 6.3.
  The execution copies omitted that optional plot property and kept the raw
  exports and exact diffs. Physics and solver definitions were unchanged.
- A native `Table` with a 10,000-row buffer truncated a requested 65,536-row
  field export. Set that table's capacity before filling it, and verify the
  actual exported row count and shape. Reopen an already saved solution for
  extraction rather than repeating its solve:

  ```java
  model.result().table("fieldTable").set("tablebuffersize", expectedRows);
  model.result().table("fieldTable").setTableData(fieldRows);
  ```

- The observed MATLAB client was R2023b; COMSOL 6.3 officially lists R2024a
  and R2024b. A successful local R2023b replay does not establish official
  support or general compatibility. Prefer documented pairings for a new
  deployment.

Primary references: [COMSOL model save types](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_general.47.16.html),
[mphstartcomsolmphserver](https://doc.comsol.com/6.3/doc/com.comsol.help.llmatlab/llmatlab_ug_ref.9.68.html),
[Table buffer capacity](https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_results.52.160.html),
[COMSOL 6.3 MATLAB requirements](https://www.comsol.com/system-requirements/63/module).
