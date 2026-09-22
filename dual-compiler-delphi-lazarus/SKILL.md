---
name: dual-compiler-delphi-lazarus
description: Patterns for building and maintaining Object Pascal projects that compile on both Delphi and Lazarus/FPC (dual-compiler), distilled from real open-source projects (pascal-amqp-faa, pascal-dfe-broker, pascal-pipes-faa, pascal-redis-faa, opcb-object-pascal-component-builder). Use this skill whenever the user is starting a new Delphi project that should also run on Lazarus (or vice versa), porting a project from one compiler to the other, debugging a compile error or runtime bug that only happens on one of the two compilers, reviewing or writing `{$IFDEF FPC}` code, choosing between `{$MODE DELPHI}` and `{$mode objfpc}`, setting up compatibility `.inc` files, organizing `.dpr`/`.dproj`/`.lpr`/`.lpi`/`.lpk` project files, writing mirrored DUnitX+FPCUnit tests, scaffolding a new dual-compiler project skeleton, checking whether DUnitX/FPCUnit test mirrors have drifted apart, or setting up CI for the FPC/Linux side. Trigger even if the user doesn't say "dual-compiler" explicitly — phrases like "this also needs to build on Lazarus", "it works on Delphi but not on FPC", "I need this to compile on both", or "why does this test only fail on one compiler" are valid triggers.
---

# Dual-compiler Delphi/Lazarus

Consolidated knowledge from 5 real-world open-source projects that keep a single codebase compiling on both Delphi and Lazarus/FPC. The goal of this skill is to avoid re-discovering, project after project, the same divergences between Delphi's RTL and FPC's RTL — and to give a project structure that is dual-compiler-ready from day one.

Reference projects used as live examples throughout this skill (all public on GitHub, MIT/Apache-licensed by their author):

| Project | Repository | Role |
|---|---|---|
| pascal-amqp-faa | https://github.com/fabianoallex/pascal-amqp-faa | Canonical source of the RTL/threading/socket gotcha table — the sibling projects below explicitly cite this one as their reference |
| pascal-dfe-broker | https://github.com/fabianoallex/pascal-dfe-broker | Best example of structured documentation (`CLAUDE.md` + `CONTRIBUTING.md` + `docs/`) and the only one with real CI (GitHub Actions running the FPC suite) |
| pascal-pipes-faa | https://github.com/fabianoallex/pascal-pipes-faa | Example of a 3rd platform axis (Windows/Linux/Android) and of why `{$IFDEF}` ordering matters |
| pascal-redis-faa | https://github.com/fabianoallex/pascal-redis-faa | Socket-timeout gotchas and encoding issues with binary data |
| opcb-object-pascal-component-builder | https://github.com/fabianoallex/opcb-object-pascal-component-builder | The only one using `{$mode objfpc}` + real generics (`generic`/`specialize`) instead of `{$MODE DELPHI}` without generics |

When you need something concrete (a file name, a code snippet, a folder layout), prefer opening the real file in one of these repos and adapting it, rather than inventing one from scratch — these projects already paid that cost.

## How to approach the task

1. **Figure out where the user is.** A brand-new project? An existing Delphi project that needs Lazarus support added? A test or build that only breaks on one of the two compilers? Each case points to a different section below.
2. **New project or porting**: for a brand-new plain console-app project, the fastest path is `scripts/scaffold_dual_project.py new --name <Name>` (see "Scaffolding a new project" below) — it generates a working skeleton instead of inventing one from scratch. For anything the scaffold doesn't cover (GUI apps, porting an existing single-compiler project), follow "Anatomy of a dual-compiler project" below and skim how `pascal-amqp-faa` or `pascal-dfe-broker` are organized — copy the shape of their `.inc`, `.groupproj`, `.lpg` files as a starting point.
3. **Specific bug/incompatibility**: check `references/rtl-gotchas.md` — there's a good chance the divergent behavior is already cataloged there, with symptom, root cause, and the fix that was used.
4. **Writing or reviewing tests**: see "Mirrored tests" below.
5. Whenever you resolve a new incompatibility (RTL, threading, encoding, sockets) that isn't in `references/rtl-gotchas.md` yet, suggest adding it there — that's how the list grew in the original projects (each one keeps a "gotchas found" section in its `CLAUDE.md` that gets fed over time).

## Anatomy of a dual-compiler project

### One source tree, no physical split

Across all 5 projects, code lives entirely in `src/*.pas` — there is no `src.delphi/` + `src.fpc/` split. Compiler differences are resolved **inside the same unit**, with `{$IFDEF FPC}` plus a project-specific platform define (see below). This avoids duplicating business logic and keeps a single place to fix bugs.

Only split physically when the difference is too large to fit in a local `{$IFDEF}` — for example, `pascal-pipes-faa` isolates its entire Android backend (`tests/Android/`, `samples/EchoAndroid/`) because the API there is fundamentally different (Delphi RTL `Posix.*` units, no FPC equivalent), not because "splitting by compiler" is tidier.

### The compatibility `.inc` file

Every reference project includes, right after the `unit X;` declaration of every unit, an `{$I <project>.inc}` pointing at its own include file at the root of `src/` (`dfe.inc`, `amqp.inc`, `pipes.inc`, `redis.inc`). That file has two fixed responsibilities:

1. Turn on the right compatibility mode in FPC (see the decision below — `{$MODE DELPHI}` or `objfpc`).
2. Normalize the platform define: Delphi defines `MSWINDOWS`, FPC defines `WINDOWS` — the `.inc` unifies both into a project-specific define (e.g. `DFE_WINDOWS`, `AMQP_WINDOWS`) so the rest of the code never has to check both separately.

General shape (adapt the define name to your project — see `src/amqp.inc` in `pascal-amqp-faa` for the real, commented example):

```pascal
{$IFDEF FPC}
  {$MODE DELPHI}   // or {$mode objfpc} — see "MODE DELPHI vs objfpc" below
  {$H+}
{$ENDIF}
{$IFDEF MSWINDOWS}{$DEFINE MYPROJECT_WINDOWS}{$ENDIF}
{$IFDEF WINDOWS}{$IFNDEF MYPROJECT_WINDOWS}{$DEFINE MYPROJECT_WINDOWS}{$ENDIF}{$ENDIF}
```

If the project has a third platform axis (e.g. Android via Delphi/FMX, like `pascal-pipes-faa`), **the order of the checks matters**: Delphi also defines `POSIX` on Android, so the more specific define (`_ANDROID`) must be tested and set *before* falling through to the generic `_POSIX` check, and the generic `_POSIX` check must explicitly exclude the Android case already handled. See `src/pipes.inc` in `pascal-pipes-faa` for the commented pattern.

### MODE DELPHI vs objfpc — two valid strategies

There are two deliberate choices for FPC's compilation mode, and this skill doesn't treat one as universally correct — it depends on how much the project actually needs generics:

**a) `{$MODE DELPHI}{$H+}`** — used in 4 of the 5 reference projects (the whole `pascal-*-faa` family plus `pascal-dfe-broker`). It's the simpler option: FPC behaves as close to Delphi as possible, and the project deliberately avoids the features where the two RTLs diverge the most:

- No `reference to procedure` / anonymous methods / `TThread.CreateAnonymousThread` → use `procedure ... of object` and dedicated work items instead.
- No `TList<T>`-style generics, `TArray.Sort<T>`, `TStringHelper` → solved with concrete classes and manual routines.
- No direct `System.Threading`/`TTask`, `System.TMonitor`, `TInterlocked`/`AtomicXxx`, `TEncoding.UTF8.*` → project-specific wrappers (see `references/rtl-gotchas.md` for why each one).

This is the recommended default for a new project, especially if it's mostly business/protocol logic (like the 4 projects that use it) — less surface for divergence between compilers, fewer gotchas to catalog.

**b) `{$mode objfpc}{$H+}{$LONGSTRINGS ON}{$MODESWITCH TYPEHELPERS}{$MODESWITCH ADVANCEDRECORDS}`** — used in `opcb-object-pascal-component-builder`, which needs real generics (`TList<T>`, generic interfaces) for its public builder API. In this mode, **every generic type declaration** needs the `{$IFDEF FPC}generic{$ENDIF}` prefix, and **every specialized use** needs `{$IFDEF FPC}specialize{$ENDIF}` in front — Delphi doesn't use these keywords, FPC in `objfpc` mode requires them. Real example (`src/OPCB.pas`, lines 56 and 59 in `opcb-object-pascal-component-builder`):

```pascal
{$IFDEF FPC}generic{$ENDIF} TSetupProcObj<TBuild> = procedure(AObj: TBuild) of object;
TObjectSetupProcObj = {$IFDEF FPC}specialize{$ENDIF} TSetupProcObj<TObject>;
```

Pick this option when the project's API genuinely benefits from generics (e.g. a generic component/builder library) — but be aware every generic type in the codebase pays the double-`{$IFDEF}` cost. It's not the default; it's the option for when generics are worth it.

In both cases, `{$H+}` (long strings) is mandatory — without it FPC defaults to `ShortString`, incompatible with Delphi.

### Project files and groups

- `.dpr`/`.dproj` (Delphi) and `.lpr`/`.lpi` (Lazarus) point at the same `src/` via search path — neither compiles its own copy of the code. A plain console app doesn't strictly need a separate `.lpr`, though: `pascal-amqp-faa/samples/Retaguarda` compiles the exact same `.dpr` on both compilers, with the `.lpi` pointing straight at it — see "Scaffolding a new project" below. A `.lpr` earns its keep when the two compilers genuinely need different entry-point logic, like a DUnitX/FPCUnit test runner branching between a GUI and a console runner.
- None of the reference projects use a `.dpk` (Delphi package) for library code — Delphi resolves it via a direct search path. Lazarus, on the other hand, typically uses an `.lpk` (`packages/<name>.lpk`) because Lazarus's package mechanism requires it for other projects to depend on it.
- Each project keeps a **Delphi project group at the root** (`<Name>.groupproj`) and, in most cases, an **equivalent Lazarus group** (`<Name>.lpg`). Simple but important rule: **every new `.dpr`/`.dproj` goes into the `.groupproj`, every new `.lpi` goes into the `.lpg`** — forgetting this is the most common way a new project "disappears" from the aggregate build.
- If a sub-target only exists for one compiler (e.g. an Android project in Delphi with no FPC equivalent), it only goes into that compiler's group, and ideally **outside** the aggregate "build everything" target — so people without that platform's SDK don't break the overall build (`pascal-pipes-faa` does this with its Android targets).

### Scaffolding a new project

`scripts/scaffold_dual_project.py new --name MyProject` generates a working skeleton — `.inc`, a starter unit, `.dpr`/`.dproj`, `.lpi`, and root `.groupproj`/`.lpg` — for a plain console-app project, derived from real IDE-built files rather than invented from scratch. `add` inserts one more project into an existing group, falling back to printing manual instructions rather than risking a fragile text-edit if the group file wasn't itself generated by this script. See `references/project-scaffolding.md` for usage, the `--with-lpk` option, v1 scope (console apps only, no dotted names), and the manual recipe if you'd rather copy and rename fields by hand. A generated skeleton has been confirmed end-to-end: `DemoApp.dproj` opens in Delphi with no "repair project" prompt and `DemoApp.lpi` opens in Lazarus, both build and run the console app correctly. Still open a freshly generated `.dproj`/`.lpi` once in each IDE before relying on it — that round-trip has only been verified for the plain console-app case this script targets, not every possible project shape.

### Naming

Delphi rejects a test project with the same name as a unit it references. `pascal-redis-faa` hit this: the integration-test unit is named `Redis.IntegrationTests`, so the test *program* had to be named `Redis.IntegrationSuite` instead of `Redis.IntegrationTests`. When creating a new test executable, check that the `.dpr`/`.lpr` name doesn't collide with any unit in the project.

### Encoding and accented characters — decide and document, don't assume

Source without a BOM is read as ANSI by Delphi; FPC's Windows console is usually cp850. The reference projects made different, deliberate calls:

- `pascal-dfe-broker` requires 100% ASCII source (avoids mojibake from accents in BOM-less files).
- `pascal-amqp-faa`/`pascal-pipes-faa`/`pascal-redis-faa` keep a UTF-8 BOM, but `pascal-redis-faa` reverted specific error messages back to ASCII because they showed up as garbage on the FPC console in cp850.

There's no universal answer here — the skill recommends **deciding this explicitly at project start and documenting the rule** (e.g. in the project's `CLAUDE.md` or `CONTRIBUTING.md`), rather than letting each developer/IDE normalize it however it likes. See also the `TEncoding.UTF8.GetString` gotcha in `references/rtl-gotchas.md` — it's the more dangerous case, because it isn't just cosmetic: it can crash callbacks in production when the data is binary.

### Line endings

`pascal-redis-faa` explicitly documents LF-only (working tree and repository) — both FPC and Delphi 12+ read LF without issue, and it avoids giant diffs from `core.autocrlf` fighting between environments. Worth adopting as a default in any new project in this family.

### Building with lazbuild

- The first time an `.lpk` is referenced by another project, run `lazbuild --add-package-link <package>.lpk` — without it Lazarus won't find the package.
- `lazbuild` can reuse an old compiled `.ppu` from a package and mask a change. Force a clean rebuild with `lazbuild -B -r`.

## RTL gotcha table: "forbidden on FPC / use instead"

This table is nearly identical across `pascal-amqp-faa`, `pascal-pipes-faa`, and `pascal-redis-faa` — the latter two inherited/copied it from `pascal-amqp-faa`, which is the canonical source. Use it as a checklist when writing new code under `{$MODE DELPHI}`:

| Forbidden / risky on FPC 3.2 | Use instead | Why |
|---|---|---|
| `reference to procedure` / anonymous methods / `TThread.CreateAnonymousThread` | `procedure ... of object`; dedicated work items | FPC's closure support diverges from Delphi's enough to cause subtle capture bugs |
| `System.Threading` (`TTask.Run`) | A project-specific thread pool | `System.Threading` has no direct FPC equivalent |
| `System.TMonitor` | A project-specific monitor class | Same reason — not a portable API |
| `TInterlocked.*` / `AtomicXxx` | Project-specific atomic wrappers | Atomic primitive names/behavior diverge |
| `TThread.GetTickCount64` | A project-specific tick wrapper | Availability/precision diverges between compilers |
| `GetLastOSError` | A project-specific OS-error wrapper | Same reason |
| `System.Net.Socket` directly | A project-specific socket wrapper | Delphi's high-level socket API has no FPC equivalent |
| `TEncoding.UTF8.GetBytes/GetString` | A project-specific UTF-8 encode/decode | Delphi raises on invalid UTF-8 bytes; FPC doesn't — dangerous with binary data (see the Redis case below) |
| Namespaced `uses System.SysUtils` | Short name + unit scope names | FPC doesn't use unit scope names by default |
| Inline `var` (declared mid-code) | Declare in the routine's `var` block | FPC's inline-var support is more limited |
| `TStringHelper` | Manual routines | Not every FPC version/mode implements the same helpers |
| `TArray.Sort<T>` | Manual sorting | Avoids depending on RTL generics when the project already avoids generics (see "MODE DELPHI vs objfpc") |

This table covers the most common cases. For gotchas cataloged with a real symptom + root cause + fix (threading/interop, sockets/timeout, files/OS, config parsing, memory/leaks, types, evaluation order, 3-axis UI framework selection), see **`references/rtl-gotchas.md`** — it includes the real cases from `pascal-dfe-broker`, `pascal-pipes-faa`, and `pascal-redis-faa` with links to the exact files where each one was found.

## Mirrored tests: DUnitX (Delphi) + FPCUnit (FPC)

The pattern across all 5 projects: every new pure unit gets **two test mirrors** — same test name, same assertion — one running on DUnitX (Delphi) and one on FPCUnit (FPC). Folder layout varies a bit between projects (`tests/Unit/` + `tests/Unit/fpc/` in the `pascal-*-faa` family; `tests/Delphi/` + `tests/Lazarus/` in `opcb-object-pascal-component-builder`), but the rule is the same: **both mirrors must exist and stay in sync**.

Key points:

- **The acceptance criterion for any change is compiling AND passing tests on both compilers** — none of these projects accept "it passed on FPC only" or "it passed on Delphi only" as sufficient.
- **Memory-leak detection comes from both sides, and each side catches different bug classes**: heaptrc enabled on the FPC suites (criterion: 0 leaks) and `ReportMemoryLeaksOnShutdown`/FastMM on the Delphi side (also 0 leaks). `opcb-object-pascal-component-builder` documents this explicitly — Delphi-side FastMM caught leaks that FPC's heaptrc didn't. Don't disable either one thinking it's redundant.
- **Delphi's default RTTI only publishes `public`/`published` methods** — a test attribute (`[Test]`) placed on a `private` method compiles fine but never runs, with no warning. If a test "disappears" silently, check the method's visibility first.
- **No `Sleep` and no real wall-clock in tests.** A test that sleeps or reads the system clock to synchronize with asynchronous behavior is slow and flaky across compilers — timing characteristics differ between Delphi and FPC threads. Inject a fake/controllable time source (a clock abstraction the test can advance manually) and drive async completion through explicit signals instead of `Sleep`.
- **A ready-to-use verification script, not just an idea**: `scripts/verify_test_mirrors.py` (generalized from a prototype in `pascal-amqp-faa`) statically scans both suites and flags divergences — a test with no mirror, a fixture declared but never registered, an assertion or RTL call from the wrong dialect, a test attribute outside a `public`/`published` section — without compiling anything. See `references/test-mirror-verification.md` for what each check does and how to extend it. Not mandatory for every project, but worth adopting once mirrors are large enough that keeping them in sync by hand starts silently failing.

### CI: keep the YAML thin

Delphi Community Edition can't build from the command line. This means Delphi-side validation is usually manual, through the IDE — and automated CI (where it exists, like in `pascal-dfe-broker`) typically only covers the FPC/Linux side. Don't assume "CI is green" covers the Delphi side; that still depends on someone running the suite in the IDE.

`pascal-dfe-broker`'s real workflow has 3 jobs, but every one of them does the same thing: checkout, optionally initialize a git submodule, then run exactly one shell script. There are zero inline `apt-get`/FPC-install commands in the YAML itself — all Docker/FPC provisioning and test orchestration lives in versioned shell scripts under `tools/docker/`, the same scripts a developer runs locally. That's the reusable pattern, not the literal 3-job shape (which is specific to that project having a companion simulator image and a systemd unit): **keep the workflow file minimal, and put provisioning + orchestration in a script, not inline YAML.**

`assets/github-actions-fpc-linux.yml` is a copyable single-job starting point following this pattern, paired with `assets/ci-test.sh.example` (a stub showing FPC install → `lazbuild -B -r` → run the compiled FPCUnit binaries → call `scripts/verify_test_mirrors.py`) — copy the `.example` in, edit it for your project, and add more jobs the same way as the project grows.

## What NOT to generalize from these projects

Not everything that shows up across the 5 projects is a universal dual-compiler convention — some of it is just the author's portfolio-organization choices:

- **Reusing whole units across sibling repositories** (e.g. `AMQP.Threading.pas` copied and renamed to `Redis.Threading.pas`/`Pipes.Threading.pas`, with no build dependency between repositories) is a portfolio pattern, not a compatibility technique. It only makes sense when several small, independent projects share the same infrastructure base (threading, transport) and the author prefers copying over coupling repositories.
- **Android/FMX support** is only relevant if the project genuinely targets mobile via Delphi — don't add that platform axis "just in case."
- A dual-language README with a sync rule is a documentation convention of the author's, not a technical dual-compiler requirement.
