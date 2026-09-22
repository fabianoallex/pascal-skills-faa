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
root). That round-trip covers the plain console-app case this script
targets; it hasn't been re-verified for every `--with-lpk`/`add` combination
or every Delphi/Lazarus version. Open a freshly generated `.dproj` in Delphi
and `.lpi` in Lazarus once each and confirm they load and build before
relying on the skeleton for real work — especially after changing anything
in the templates.

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

Both subcommands take `--dry-run` (print what would be written, write
nothing) and require `--force` to overwrite an existing file.

`add` looks for `<!-- SCAFFOLD:... -->` anchor comments that `new` leaves in
the `.groupproj`/`.lpg` it generates. If the target group file has them
(i.e. it was itself produced by this script), the new project is inserted
automatically. If it doesn't — the common case, since your project group is
usually a real, hand-authored file like the ones in the 5 reference repos —
`add` **does not modify the file**. It prints the exact XML snippet to
insert and where, matching the "every new `.dpr`/`.dproj` goes into the
`.groupproj`, every new `.lpi` goes into the `.lpg`" rule from the main
`SKILL.md`. This is deliberate: text-editing a hand-authored MSBuild/Lazarus
XML file by pattern-matching is fragile, and a wrong edit is worse than a
manual step.

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
  units) that it doesn't fit this script's templates — see
  `opcb-object-pascal-component-builder` for how that project structures
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
