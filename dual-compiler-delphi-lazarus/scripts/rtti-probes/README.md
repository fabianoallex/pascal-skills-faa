# RTTI probes

The evidence behind `../../references/rtti-gotchas.md`. Each `pNN_*.dpr` is one small console program testing one RTTI feature, written once for both compilers (`{$IFDEF FPC}` only where unavoidable). One program per feature on purpose: a feature that doesn't compile on one side can't hide the results of the others.

Each probe prints `key=value` lines; a runtime exception prints `EXCEPTION=<class>: <message>`.

## Running

**FPC** (any edition, command line):

```
python run_probes.py            # all probes
python run_probes.py p08 p09    # a subset, by name fragment
```

Set `FPC` to point at another `fpc.exe` (default: Lazarus 4.0's FPC 3.2.2 Win64).

**Delphi Community Edition** can't build from the command line, so:

```
python gen_delphi.py
```

turns every probe into a unit and generates `delphi_side/rtti_delphi.dproj`, which runs them all. Open that `.dproj` (not the `.dpr`) in the IDE, choose Win32 or Win64, and run it once; the output lands in `delphi_results.txt` here. The `.dproj` comes from `scaffold_dual_project.py`'s template because the one the CE IDE creates for a bare `.dpr` has no Win64 platform and can't get one.

A few probes are left out of that project, because one unit that fails to compile would block the whole build (see `SKIP` in `gen_delphi.py`). Compile those standalone `.dpr` files in the IDE.

Alternatively, `python gen_delphi_group.py` generates `RttiProbes.groupproj` with one project per probe, the same `.dpr` files FPC builds, untouched. **Build All** in the IDE; the executables land in `Win32\Debug\` (or `Win64\Debug\`), ready to run and diff. The two probes expected to fail on Delphi (`p02_proptype_fpc_style`, `p18_enum_explicit_values`) are placed last, because the IDE stops Build All at the first project that fails.

With a paid Delphi edition, `COMPILERS=fpc,delphi python run_probes.py` builds both sides with `dcc64` (override with `DCC`).

## Reference runs

`results/` holds the runs `rtti-gotchas.md` is based on:

- `fpc-3.2.2-win64.txt`: `run_probes.py`.
- `delphi-12-ce-win32.txt` / `delphi-12-ce-win64.txt`: the `gen_delphi.py` combined runner.
- `delphi-12-ce-win32-standalone.txt` / `delphi-12-ce-win64-standalone.txt`: every probe built on its own through `RttiProbes.groupproj`. It covers the probes the runner skips (`p20`, `p24`, `p29`) and matches the runner on everything else, apart from object addresses and how `p16`'s uncaught exception is printed. Win32 and Win64 differ only in addresses and in the inherited `TObject` method count (36 vs 39).

Compile failures don't appear in any output file: `p02_proptype_fpc_style` gives E2010 and `p18_enum_explicit_values` gives E2134 on Delphi, as recorded in `rtti-gotchas.md`.

`p30_tvalue_nested` and `p31_shr_generic` were built on Delphi 12 CE Win32 later, standalone; their output is appended to `delphi-12-ce-win32-standalone.txt`. `p30` contradicts `pascal-amqp-faa`'s note: Delphi wraps nested `TValue`s too.

When re-verifying on another version, run the probes and diff the output against these files. Then record the version in `rtti-gotchas.md` rather than overwriting the existing claims.
