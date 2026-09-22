# Scaffolding a new dual-compiler project

`scripts/scaffold_dual_project.py` generates the skeleton of a new
Delphi/Lazarus dual-compiler console project: the `.inc` compatibility file,
a starter unit, `.dpr`/`.dproj`, `.lpi`, and root `.groupproj`/`.lpg` files.
Every template is derived from real, IDE-built files in
[`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
(specifically `samples/Retaguarda`, the simplest plain-console-app target in
that repo) — not invented from scratch. The only content the script
generates is name substitution, a freshly minted project GUID, and the
relative search-path depth.

**Every XML file the script writes is parsed with `xml.dom.minidom`**
immediately after writing — a parse failure deletes the file and aborts
rather than leaving something broken on disk — but well-formed XML is a
floor, not proof Delphi or Lazarus will accept the file.

Confirmed end-to-end (2026-09): a `new --name DemoApp` skeleton opened
cleanly in both real IDEs — no "repair project" prompt in Delphi, no
migration prompt in Lazarus — and both built and ran the console app
correctly (`DemoApp.exe` printed the expected greeting from both the
Delphi `Win32\Debug\` output and the Lazarus/FPC output at the project
root). `add`'s output got the same confirmation separately, in a different
project ([`pascal-snake`](https://github.com/fabianoallex/pascal-snake), Delphi
12 CE + Lazarus 4.0): after opening the group and building both sides,
`git status` showed **no modification** to the generated `.dproj` or
`.groupproj` — Delphi accepted the generated project file completely
unchanged. That covers the plain console-app template `new`/`add` generate;
it hasn't been re-verified for every `--with-lpk` combination or every
Delphi/Lazarus version, and it does NOT cover any hand-edit made afterward
(e.g. converting a console `.dproj` to a VCL app — see the conversion
checklist below, which is explicitly unverified against a real IDE build).
Open a freshly generated or hand-modified `.dproj` in Delphi and `.lpi` in
Lazarus once each and confirm they load and build before relying on the
result for real work — especially after changing anything in the
templates or hand-editing the output.

## A real discovery worth knowing: you often don't need a separate `.lpr`

The skill's "Anatomy of a dual-compiler project" section describes
`.dpr`/`.dproj` (Delphi) and `.lpr`/`.lpi` (Lazarus) as if they're always
two separate program files. For a **plain console app**, that's not
necessary: `pascal-amqp-faa/samples/Retaguarda` compiles the exact same
`Retaguarda.dpr` on both compilers (its `.lpi`'s `<Unit><Filename>` points
straight at the `.dpr`), using `{$IFDEF FPC} ... {$ELSE}{$APPTYPE
CONSOLE}{$ENDIF}` at the top to handle the one thing that differs. This
script follows that pattern: `new` generates one `.dpr` and points both the
`.dproj` and the `.lpi` at it.

A **test runner** genuinely needs a separate `.lpr` — DUnitX/FPCUnit test
runners branch between a GUI tree-runner and a console runner depending on
platform, which is real per-compiler logic, not just an `{$IFDEF}` around a
directive. If you're scaffolding a test-runner-shaped target, copy the
pattern from `tests/Unit/` in any of the 5 reference repos instead of using
this script — see the boilerplate table below for what's project-specific
there.

## Usage

New project, at the root of a fresh repo:

```
python scripts/scaffold_dual_project.py new --name MyProject
```

Add a second project (another sample, a tool) to the group `new` created:

```
python scripts/scaffold_dual_project.py add --name MyTool \
    --dir tools/MyTool \
    --groupproj MyProject.groupproj --lpg MyProject.lpg \
    --inc src/myproject.inc
```

Wire an **already-built** `.dproj`/`.lpi` pair into the groups — e.g. a
mirrored test runner you copied from `tests/Unit/` in a reference repo by
hand, per the note above, or a project you hand-converted using the
conversion checklist below — with no throwaway starter files:

```
python scripts/scaffold_dual_project.py register --name MyTests \
    --dproj tests/Unit/MyTests.dproj --lpi tests/Unit/fpc/MyTestsFpc.lpi \
    --groupproj MyProject.groupproj --lpg MyProject.lpg
```

All three subcommands take `--dry-run` (print what would be written, write
nothing) and require `--force` to overwrite an existing file.

`add` and `register` both look for `<!-- SCAFFOLD:... -->` anchor comments
that `new` leaves in the `.groupproj`/`.lpg` it generates. If the target
group file has them (i.e. it was itself produced by this script), the
project is inserted automatically. If it doesn't — the common case, since
your project group is usually a real, hand-authored file like the ones in
the 5 reference repos — nothing is modified. Instead, the exact XML snippet
to insert and where is printed, matching the "every new `.dpr`/`.dproj`
goes into the `.groupproj`, every new `.lpi` goes into the `.lpg`" rule from
the main `SKILL.md`. This is deliberate: text-editing a hand-authored
MSBuild/Lazarus XML file by pattern-matching is fragile, and a wrong edit is
worse than a manual step.

**Use `register`, not `add`, once you already have a `.dproj`/`.lpi` pair.**
`add` always generates a starter unit and a console `.dpr` first — useful
when you want a new project from scratch, wasted work when you already built
the files by hand (confirmed the hard way while scaffolding `pascal-snake`'s
test runner: the generated starter had to be deleted, and because the
FPC-side `.lpi` lived at a different path/name than the Delphi-side `.dproj`
— `tests/Unit/fpc/MyTestsFpc.lpi` next to `tests/Unit/MyTests.dproj` — `add`
registered the wrong `.lpi` into the `.lpg` and it had to be fixed by hand).
`register` takes the paths you already have and only does the group-file
wiring.

### `--with-lpk`

Add `--with-lpk` to `new` to also scaffold `packages/<name>_pkg.lpk`, for a
project meant to be consumed as a reusable Lazarus package by other
projects (mirroring what `pascal-amqp-faa` and `pascal-dfe-broker` both do).
Without it, the generated `.lpi` resolves the source tree directly via
`OtherUnitFiles`/`IncludeFiles` — no package needed for a project that isn't
itself a dependency of something else.

### v1 scope

- **Console app only.** A GUI-forms project (VCL/LCL/FMX) has enough
  additional per-framework structure (forms, resources, framework-specific
  units) that it doesn't fit this script's templates — see the conversion
  checklist below for converting the generated console skeleton by hand,
  or `opcb-object-pascal-component-builder` for how that project structures
  VCL/FMX/LCL examples instead.
- **Plain identifiers only, no dots.** Some of the reference repos name
  projects like `AMQP.UnitTests` (dotted, unit-scope style). The script
  rejects that for `--name` on purpose: the generated starter unit declares
  a class named `T<Name>`, and a dot isn't a valid character in a Pascal
  identifier. If you want a dotted project name, use the manual recipe
  below instead.
- The naming-collision gotcha from `SKILL.md` ("Naming" section) is
  enforced: `new`/`add` refuse if `--name` collides with an existing unit
  under `src/`.

## Console → VCL/LCL conversion checklist

There's no `--gui` mode yet (see "v1 scope" above) — building a GUI project
today means generating the console skeleton with `new`, then converting it
by hand. This checklist is the concrete set of changes one real conversion
needed, converting a `new`-generated console skeleton into a VCL/LCL game
([`pascal-snake`](https://github.com/fabianoallex/pascal-snake)). It's a
report of what one project needed, not a verified-complete recipe — treat
it as a strong starting point, and re-verify by opening both projects in
their real IDEs, same as everywhere else in this document.

**`.dproj`:**
- `FrameworkType`: `None` → `VCL`
- `AppType`: `Console` → `Application`
- Append to `DCC_Namespace`: `Vcl;Vcl.Imaging;Vcl.Touch;Vcl.Samples;Vcl.Shell`
  (needed for the short-name `uses Forms, Controls, ...` style VCL code
  normally uses)
- Add `Manifest_File`, `AppDPIAwarenessMode=PerMonitorV2`, and
  `AppEnableRuntimeThemes` (DPI-awareness and theming, which a console app
  has no use for)
- Add a `<DCCReference Include="...">` entry per unit. The console template
  emits none, relying entirely on `DCC_UnitSearchPath` — that's enough for
  the compiler, but a GUI project's units are more naturally something the
  IDE's Project Manager should list explicitly (this hasn't been confirmed
  as strictly *required* for compilation, only as what a real hand-converted
  project ended up with)

**`.lpi`:**
- Add `LCL` to `RequiredPackages`
- Add `Scaled` (see `references/forms-dfm-lfm.md`'s DPI-scaling section if
  the form is built via `CreateNew` rather than a `.lfm`)
- Add an `XPManifest` with `DpiAware`
- Add `GraphicApplication` (the Lazarus equivalent of `AppType=Application`)

**Also needed a separate `.lpr`** (rather than reusing the shared console
`.dpr`) — a GUI entry point calls `Application.Initialize`/
`CreateForm`/`Run`, which isn't something Delphi and FPC can share via one
file the way the plain console template does. **Give it a different program
name than the `.dpr`** if they'd otherwise share one — see the `.res`
collision gotcha in `SKILL.md`'s "Project files and groups" and in
`references/rtl-gotchas.md`'s "Resource files" section; keep the built
executable's name the same via `<Target><Filename Value="..."/></Target>`
in the `.lpi`.

**Register, don't `add`, the result.** Once the `.dproj`/`.lpi` exist (converted
or hand-written), use `register` (see Usage above) to wire them into the
groups — `add` would generate a redundant console starter on top of what
you already have.

## Manual recipe (if you'd rather not run the script)

The boilerplate-vs-project-specific split, from reading real files in
`pascal-amqp-faa`:

| File | Boilerplate | Project-specific fields |
|---|---|---|
| `.inc` | ~100% | filename only |
| `.dpr` | ~90% | `program` name, `uses` list |
| `.dproj` | ~85% | `ProjectGuid` (regenerate — never copy, a GUID collision confuses the IDE), `MainSource`/`ProjectName`/`SanitizedProjectName`, `DCC_UnitSearchPath` |
| `.lpi` | ~80% | `Title`, `Target/Filename`, `RequiredPackages` (if using a `.lpk`) or `SearchPaths` (if not), `Units` |
| `.groupproj` | ~95%, mechanical | one `<Projects Include="...">` entry + 3 `<Target>` blocks (`Name`, `Name:Clean`, `Name:Make`) + append to the 3 aggregate `<CallTarget Targets="...">` lists |
| `.lpg` | ~95%, mechanical | one `<Target FileName="...">` block |
| `.lpk` (optional) | ~85% | `Name`, `Description`, one `<Item>` per unit in `<Files>` |

To do it by hand: copy the matching file from `pascal-amqp-faa` (or
`samples/Retaguarda` specifically, for the console-app case) and rename the
fields in the table above. Generate a fresh GUID for `ProjectGuid` — don't
copy one, Delphi gets confused by duplicate GUIDs across projects. Then
apply the same IDE-verification caveat as above: open both projects once in
their real IDEs before relying on them.

**Keep the byte-order mark where Delphi puts one.** Inspecting real files:
`.pas`, `.dpr`/`.lpr`, `.dproj`, and `.groupproj` all carry a UTF-8 BOM in
every reference project — that's Delphi's own file-creation convention, and
it's why `scripts/scaffold_dual_project.py` writes those four file types
with a BOM. `.lpi`/`.lpg`/`.lpk` never have one (they declare
`encoding="UTF-8"` in the XML prologue instead), and neither do `.inc`
files. If you're copying a file by hand with a plain text editor, check
your editor didn't silently strip or add a BOM — a `.pas` file without one
is read as ANSI by Delphi, which only shows up as a bug once someone adds
an accented character.
