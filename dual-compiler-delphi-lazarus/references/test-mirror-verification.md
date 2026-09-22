# Verifying DUnitX/FPCUnit test mirrors

`scripts/verify_test_mirrors.py` is a generalized version of a script born in
[`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
(`tests/tools/verifica_espelhos.py`), where every check was added after a
real defect cost a full round-trip through the Delphi IDE (Delphi Community
Edition can't build from the command line, so a defect visible only in the
Delphi mirror is expensive to catch any other way).

It's pure pattern matching over the type section and the registration block
— not a Pascal parser — and needs no compiler to run. Use it before sending
a mirrored test suite to the IDE, or wire it into a pre-commit hook or a CI
step (see `assets/github-actions-fpc-linux.yml`); exit code is `0` clean,
`1` on any divergence.

## Usage

```
python scripts/verify_test_mirrors.py [--root PATH] [--dirs tests] \
    [--mirror-subdir fpc] [--ignore-glob /lib/,/backup/,__recovery]
```

- `--root` — project root to scan from. Defaults to the current directory;
  pass this explicitly in CI or when invoking from outside the project.
- `--dirs` — comma-separated directories to scan, relative to `--root`.
  Defaults to `tests`. Add more (e.g. `tests,samples`) if example/demo code
  outside `tests/` should also be linted for check 1.
- `--mirror-subdir` — the subfolder name that holds the FPCUnit mirror of a
  DUnitX file one level up. Defaults to `fpc`, matching the convention used
  in the `pascal-*-faa` family (`tests/Unit/Name.pas` +
  `tests/Unit/fpc/Name.pas`). If your project mirrors tests some other way
  (e.g. `tests/Delphi/` + `tests/Lazarus/`, like
  [`opcb-object-pascal-component-builder`](https://github.com/fabianoallex/opcb-object-pascal-component-builder)),
  this script's pairing convention won't match your layout — adapt
  `mirrored_pairs()` rather than trying to force it through a flag.
- `--ignore-glob` — comma-separated substrings; any path containing one is
  skipped (build-artifact folders, mainly).

## What each check does

1. **Code after `initialization`.** In Pascal, a `procedure`/`function`
   declared after a unit's `initialization` section is parsed as a
   directive, not a real declaration (Delphi's dcc32 rejects it with
   E2070). Scans `.pas`/`.dpr`/`.lpr` under `--dirs`.
2. **Mirror parity.** For every DUnitX file with an FPCUnit mirror, parses
   declared test methods on each side (`[Test] procedure X;` for DUnitX;
   `published` methods of a `TTestCase` descendant for FPCUnit), diffs the
   two sets, and separately checks that every fixture *with* declared tests
   is actually registered (`TDUnitX.RegisterTestFixture(X)` vs
   `RegisterTest(X)`). This catches the worst case: a green suite with fewer
   tests than it should have, with no compile error at all.
3. **Assertion dialect.** FPCUnit's loose `AssertEquals`/`AssertTrue`/...
   and DUnitX's `Assert.*` are disjoint vocabularies. A wrong-dialect
   assertion in a mirror file only fails on the *other* compiler — exactly
   the kind of thing that slips through when one generator writes both
   mirrors from a shared text block.
4. **DUnitX attribute visibility.** `[Setup]`/`[Test]`/etc. placed in a
   `private`/`protected`/`strict private`/`strict protected` section
   compiles fine but is invisible to Delphi's default RTTI (only
   `public`/`published` members are published) — the fixture or test
   silently never runs.
5. **RTL dialect.** A short, deliberately non-exhaustive list of RTL
   identifiers exclusive to one compiler (`GetTempDir`,
   `GetLastOSError` = FPC-only; `TPath`,
   `ReportMemoryLeaksOnShutdown`, `RaiseLastOSError` = Delphi-only), plus a
   `SysUtils.` vs `System.SysUtils.` qualifier check. Kept short on purpose
   — every entry here has actually cost a round-trip; a speculative list
   would just produce false positives. For the full catalog of Delphi/FPC
   RTL divergences, see `references/rtl-gotchas.md` in this skill.

## What was intentionally dropped

The original script had a sixth check: every unit under `src/server` had to
be listed in every consuming `.dpr`/`.dproj` *and* in a specific `.lpk`
package. That check hardcoded a submodule path (`src/server`) and a package
filename (`pascal_amqp_faa_server.lpk`) specific to that one project's
architecture — a sub-package compiled both as a standalone unit list and as
an FPC package. It doesn't generalize cleanly, so it isn't shipped here.

If your project has a similar optional sub-package with the same "unit
missing from one consumer compiles fine on FPC via search path, but produces
divergent `.ppu`/runtime access violations once an interface is involved"
failure mode, write an equivalent check yourself and append it to the
`CHECKS` list at the bottom of `verify_test_mirrors.py`:

```python
def check_my_subpackage_units(cfg):
    """Return a list of (rel_path, message) tuples, same as every other check."""
    ...

CHECKS.append(('my subpackage units', check_my_subpackage_units))
```

Every check function receives the parsed `cfg` (an `argparse.Namespace`
with `root`, `dirs`, `mirror_subdir`, `ignore`) and returns a list of
`(rel_path, message)` tuples — matching this signature is all `main()`
needs to pick it up.
