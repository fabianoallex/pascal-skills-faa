---
name: dual-compiler-delphi-lazarus
description: Patterns for building and maintaining Object Pascal projects that compile on both Delphi and Lazarus/FPC (dual-compiler), distilled from real open-source projects (pascal-amqp-faa, pascal-dfe-broker, pascal-pipes-faa, pascal-redis-faa, opcb-object-pascal-component-builder). Use this skill whenever the user is starting a new Delphi project that should also run on Lazarus (or vice versa), debugging a compile error or runtime bug that only happens on one of the two compilers, reviewing or writing `{$IFDEF FPC}` code, choosing between `{$MODE DELPHI}` and `{$mode objfpc}`, setting up compatibility `.inc` files, organizing `.dpr`/`.dproj`/`.lpr`/`.lpi`/`.lpk` project files, writing mirrored DUnitX+FPCUnit tests, scaffolding a new dual-compiler project skeleton, checking whether DUnitX/FPCUnit test mirrors have drifted apart, setting up CI for the FPC/Linux side, dealing with `.dfm`/`.lfm` form-file drift (noisy diffs after opening a form in the designer, DPI/coordinate mismatches between the two files, or deciding whether to build UI in code instead of relying on the form designer), debugging OpenSSL/libxml2/certificate loading problems on Linux (a `.pfx`/PKCS12 certificate rejected on Debian/Ubuntu, `EInvalidOp` crashes from native libraries, or anything under FPC that only breaks when deployed to Linux), or wiring up unattended background-service hosting (a Windows Service via `TService`, a systemd unit, or deciding how much of that hosting layer should even try to be dual-compiler). Trigger even if the user doesn't say "dual-compiler" explicitly — phrases like "this also needs to build on Lazarus", "it works on Delphi but not on FPC", "I need this to compile on both", or "why does this test only fail on one compiler" are valid triggers.
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
2. **New project**: for a brand-new plain console-app project, the fastest path is `scripts/scaffold_dual_project.py new --name <Name>` (see "Scaffolding a new project" below) — it generates a working skeleton instead of inventing one from scratch. For anything the scaffold doesn't cover (e.g. GUI apps), follow "Anatomy of a dual-compiler project" below and skim how `pascal-amqp-faa` or `pascal-dfe-broker` are organized — copy the shape of their `.inc`, `.groupproj`, `.lpg` files as a starting point. This skill is designed for projects that are dual-compiler from the start; porting an existing single-compiler codebase is not a goal — every such project has its own particulars. The RTL gotcha table and the `.inc` pattern still apply, but treat them as reference material, not as a porting recipe.
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

`objfpc` mode has one more divergence worth knowing if the project assigns event handlers or takes method pointers: **it requires an explicit `@` to turn a named method into a procedural value**, where `{$MODE DELPHI}` (and Delphi itself) infers it. Confirmed in `opcb-object-pascal-component-builder`'s own Lazarus example code: `TButton.OnClick := @ButtonSearchClick;` (`examples/Builders/Lazarus/book-search/unit1.pas`). Code written assuming Delphi's implicit form (`OnClick := ButtonSearchClick;`) compiles under `{$MODE DELPHI}` but fails under `objfpc` — another reason `{$MODE DELPHI}` is the simpler default, and something to fix immediately if a shared unit is deliberately written in `objfpc` mode.

In both cases, `{$H+}` (long strings) is mandatory — without it FPC defaults to `ShortString`, incompatible with Delphi.

### Project files and groups

- `.dpr`/`.dproj` (Delphi) and `.lpr`/`.lpi` (Lazarus) point at the same `src/` via search path — neither compiles its own copy of the code. A plain console app doesn't strictly need a separate `.lpr`, though: `pascal-amqp-faa/samples/Retaguarda` compiles the exact same `.dpr` on both compilers, with the `.lpi` pointing straight at it — see "Scaffolding a new project" below. A `.lpr` earns its keep when the two compilers genuinely need different entry-point logic, like a DUnitX/FPCUnit test runner branching between a GUI and a console runner.
- None of the reference projects use a `.dpk` (Delphi package) for library code — Delphi resolves it via a direct search path. Lazarus, on the other hand, typically uses an `.lpk` (`packages/<name>.lpk`) because Lazarus's package mechanism requires it for other projects to depend on it.
- Each project keeps a **Delphi project group at the root** (`<Name>.groupproj`) and, in most cases, an **equivalent Lazarus group** (`<Name>.lpg`). Simple but important rule: **every new `.dpr`/`.dproj` goes into the `.groupproj`, every new `.lpi` goes into the `.lpg`** — forgetting this is the most common way a new project "disappears" from the aggregate build.
- If a sub-target only exists for one compiler (e.g. an Android project in Delphi with no FPC equivalent), it only goes into that compiler's group, and ideally **outside** the aggregate "build everything" target — so people without that platform's SDK don't break the overall build (`pascal-pipes-faa` does this with its Android targets).
- **If a `.dpr` and a `.lpr` live in the same folder with the same program name, they collide on `.res`.** `{$R *.res}` in both resolves to the exact same `<program>.res`, and each IDE freely regenerates it on build (Delphi writes its own MAINICON/version info, Lazarus regenerates from the `.lpi`'s manifest/icon settings) — so building one compiler silently overwrites the other's resource file. `opcb-object-pascal-component-builder`'s `no-dfm` example avoids this by giving the two program files different names (`DelphiProject.dpr` / `LazarusProject.lpr`) without ever saying why. If you need that naming split, give the Lazarus side a distinct program name and set `<Target><Filename Value="..."/></Target>` in its `.lpi` to whatever the shared executable name should actually be — the program name and the output filename don't have to match. A single shared `.dpr` (see "Scaffolding" below) doesn't hit this at all, since there's only one program file to begin with; the collision is specific to the two-programs-one-folder case, e.g. adding a `.lpr` for a test runner's GUI/console split next to a `.dpr` that would otherwise share its name.

### Scaffolding a new project

`scripts/scaffold_dual_project.py new --name MyProject` generates a working skeleton — `.inc`, a starter unit, `.dpr`/`.dproj`, `.lpi`, and root `.groupproj`/`.lpg` — for a plain console-app project, derived from real IDE-built files rather than invented from scratch. `add` generates one more starter project and inserts it into an existing group; `register` does the group-file wiring alone, for a `.dproj`/`.lpi` pair you already built by hand (e.g. a mirrored test runner or a hand-converted GUI project — see `references/project-scaffolding.md`'s conversion checklist) instead of generating a throwaway starter you'd just delete. Both fall back to printing manual instructions rather than risking a fragile text-edit if the group file wasn't itself generated by this script. See `references/project-scaffolding.md` for usage, the `--with-lpk` option, v1 scope (console apps only, no dotted names), and the manual recipe if you'd rather copy and rename fields by hand. The plain console template has been confirmed end-to-end: `DemoApp.dproj` opens in Delphi with no "repair project" prompt and `DemoApp.lpi` opens in Lazarus, both build and run the console app correctly — and a separate real session used it as the base for a VCL/LCL game, confirming `add`'s output was accepted by Delphi 12 CE unmodified (`git status` showed no diff to the generated `.dproj`/`.groupproj` after opening and building). Still open a freshly generated or hand-modified `.dproj`/`.lpi` once in each IDE before relying on it, especially after any hand-edit.

### Naming

Delphi rejects a test project with the same name as a unit it references. `pascal-redis-faa` hit this: the integration-test unit is named `Redis.IntegrationTests`, so the test *program* had to be named `Redis.IntegrationSuite` instead of `Redis.IntegrationTests`. When creating a new test executable, check that the `.dpr`/`.lpr` name doesn't collide with any unit in the project.

### Encoding and accented characters — decide and document, don't assume

Source without a BOM is read as ANSI by Delphi; FPC's Windows console is usually cp850. The reference projects made different, deliberate calls:

- `pascal-dfe-broker` requires 100% ASCII source (avoids mojibake from accents in BOM-less files).
- `pascal-amqp-faa`/`pascal-pipes-faa`/`pascal-redis-faa` keep a UTF-8 BOM, but `pascal-redis-faa` reverted specific error messages back to ASCII because they showed up as garbage on the FPC console in cp850.
- For a **GUI** app specifically: accented literals in a UTF-8-with-BOM `.pas` under `{$MODE DELPHI}` render correctly on both sides — confirmed with Delphi 12 and Lazarus 4.0 ([`pascal-snake`](https://github.com/fabianoallex/pascal-snake)'s UI strings, `começar`/`Espaço`/`sólidas`/`Você`, displayed correctly on both VCL and LCL). The cp850-console mojibake problem above is a console-specific failure mode; it doesn't apply to a form's on-screen text.

There's no universal answer here — the skill recommends **deciding this explicitly at project start and documenting the rule** (e.g. in the project's `CLAUDE.md` or `CONTRIBUTING.md`), rather than letting each developer/IDE normalize it however it likes. See also the `TEncoding.UTF8.GetString` gotcha in `references/rtl-gotchas.md` — it's the more dangerous case, because it isn't just cosmetic: it can crash callbacks in production when the data is binary.

If the project's answer is "UTF-8 with BOM," know that **which file types actually get a BOM is inconsistent, and it's Delphi's doing, not Lazarus's**. Inspecting real files across the reference repos: Delphi stamps a BOM on every file type it creates through its own tooling — `.pas`, `.dpr`/`.lpr` (yes, even the Lazarus-compiled program file gets one, if a Delphi-family tool ever touched it), `.dproj`, `.groupproj`. Lazarus's own XML-based files (`.lpi`, `.lpg`, `.lpk`) never have one — they declare `encoding="UTF-8"` in the XML prologue instead, which is the standard (and sufficient) way to mark encoding for XML. `.inc` files have no BOM in any reference project, consistently — they're typically hand-authored outside the IDE's "New File" flow rather than generated by it. `.dfm`/`.lfm` have no BOM either. A generated or hand-written `.pas` file without a BOM is read as ANSI by Delphi the first time it's opened — harmless while the content is pure ASCII, wrong the moment anyone adds an accented character. `scripts/scaffold_dual_project.py` matches this pattern exactly (BOM on `.pas`/`.dpr`/`.dproj`/`.groupproj`, none on `.inc`/`.lpi`/`.lpg`/`.lpk`) so a generated project looks like what the IDE itself would have produced.

### Line endings

`pascal-redis-faa` explicitly documents LF-only (working tree and repository) — both FPC and Delphi 12+ read LF without issue, and it avoids giant diffs from `core.autocrlf` fighting between environments. Worth adopting as a default in any new project in this family.

### Building with lazbuild

- The first time an `.lpk` is referenced by another project, run `lazbuild --add-package-link <package>.lpk` — without it Lazarus won't find the package.
- `lazbuild` can reuse an old compiled `.ppu` from a package and mask a change. Force a clean rebuild with `lazbuild -B -r`.
- A variant `-B` doesn't fix: **a stale `.ppu` left in the project's own output folder after the project switched from compiling the sources directly (search path) to depending on a package.** With the sources no longer on the project's search path, FPC found the old `.ppu` there and used it (observed: "Wrong number of parameters specified for call to Create" against a constructor that had since changed, with `lazbuild -B`). Deleting the project's `lib/` folder fixed it. Do that whenever a project's unit resolution changes like this. — `pascal-db-faa` (not yet public)

## Forms: `.dfm`/`.lfm` — the hardest part of dual-compiler compatibility

If the project has any VCL/LCL forms, this is worth reading before the RTL gotcha table below — in practice it causes more friction than most RTL divergences combined. `Name.dfm` (Delphi) and `Name.lfm` (Lazarus) are two **independently hand-maintained** files next to `Name.pas`, loaded via `{$IFDEF FPC}{$R *.lfm}{$ELSE}{$R *.dfm}{$ENDIF}`, with no build-time conversion keeping them in sync — whatever a form looks like in one designer, someone recreates by hand in the other.

Confirmed by diffing 10 real `.dfm`/`.lfm` pairs in `pascal-amqp-faa`'s `samples/*Vcl` projects: **both IDEs silently rewrite the entire file** when a form is opened and saved in their designer, not just the parts a developer touched. The single biggest offender is DPI: Lazarus stamps a `DesignTimePPI` value into the `.lfm`, and reopening a form on a different-scale display rewrites *every* coordinate in the file to match (a 125%-scaled session turns a 450×500 form into 562×625 — the same 1.25 ratio shows up on every control) — with nothing about the layout actually changing. `Anchors` sets also get canonically reordered by each serializer, and accented text gets re-encoded (Delphi's `\#227` escape vs. Lazarus's raw UTF-8) — more guaranteed diff noise unrelated to real edits. Don't hand-edit either file expecting the change to survive, and review a designer-save diff by opening the form visually rather than reading the text diff. See `references/forms-dfm-lfm.md` for the full property-by-property catalog and the confirmed evidence for each claim.

**The strategy that sidesteps this entirely: build the UI in `.pas` instead of relying on `.dfm`/`.lfm` at all**, when the project can afford to. `opcb-object-pascal-component-builder` exists specifically for this — its own docs state building components in code "avoids common issues with `.dfm` or `.lfm` files in Git repositories." The mechanism is a form constructor calling `inherited CreateNew(AOwner)` instead of `Create` (skipping resource-stream loading entirely) and adding controls via a fluent builder API; `examples/Builders/VCL-Lazarus/no-dfm/` in that repo is a real form with no `.dfm`/`.lfm` at all, compiling unmodified on both compilers. This doesn't require going all-or-nothing — a hybrid is fine: static chrome in a normal `.lfm`, only the genuinely dynamic part built in code (see `references/forms-dfm-lfm.md` for that example). When the designer is still clearly faster for a static layout, that's a reasonable call — just budget for the friction above rather than being surprised by it.

## Native library interop on Linux: OpenSSL, libxml2, the FPU

If the project talks to OpenSSL or libxml2 directly (certificate/PKCS12 handling, XML signing, TLS) and needs to run on Linux, budget for a cluster of gotchas that never show up on Windows — "it compiles and passes on Windows" is not evidence about Linux here. The sharpest one: **OpenSSL 3.0's default provider isn't active by default on Debian 12/Ubuntu 22.04**, so every PKCS12 operation fails with an opaque error — loading a client certificate (`.pfx`, e.g. a Brazilian NFe A1 certificate) gets rejected even though the file is valid, and the fix is one explicit `OSSL_PROVIDER_load(nil, 'default')` call before first use. FPC also leaves FPU exceptions enabled, and native C libraries trip them — libxml2 initialization alone can crash the process with `EInvalidOp` unless FPU exceptions are masked per-thread. See `references/native-library-interop.md` for these plus the dynamic-loading-with-soname-fallback pattern, the `libxml2.so` unversioned-symlink requirement, `Now` returning UTC regardless of system timezone on FPC 3.2.2/Linux, and stdout buffering under systemd losing log lines.

## Running as a background service: Windows Service vs systemd

If the project needs to run unattended in the background (a broker, a poller, anything supervised by the OS rather than started by hand), this is another axis that's inherently single-platform, like the Android backend in `pascal-pipes-faa` — don't try to dual-compile it. The pattern from `pascal-dfe-broker`: keep one shared, testable core (`TDFeAplicacao`/`TDFeHostLoop`, a plain tick loop) and wrap it in two **thin** hosts — a dual-compiler console host (`.dproj` AND `.lpi`) that's the actual production host on Linux under systemd, and a **Delphi-only** Windows Service host (`Vcl.SvcMgr.TService`) for Windows, on purpose: *"a Windows Service is an inherently Windows notion, and Lazarus has no ready-made `TService`."* The service wrapper has real, specific gotchas of its own — it can't block in `OnStart`, its working directory is `C:\Windows\System32` (every relative config path breaks unless resolved against the config file's own location), and it doesn't see the interactively-logged-in user's `PATH` (native DLLs like OpenSSL/libxml2 have to sit next to the executable). See `references/background-service-hosting.md` for the full pattern, the installation recipe, and what was and wasn't actually verified.

## RTL gotcha table: "forbidden on FPC / use instead"

This table is nearly identical across `pascal-amqp-faa`, `pascal-pipes-faa`, and `pascal-redis-faa` — the latter two inherited/copied it from `pascal-amqp-faa`, which is the canonical source. Use it as a checklist when writing new code under `{$MODE DELPHI}`:

| Forbidden / risky on FPC 3.2 | Use instead | Why |
|---|---|---|
| `reference to procedure` / anonymous methods / `TThread.CreateAnonymousThread` | `procedure ... of object`; dedicated work items | FPC's closure support diverges from Delphi's enough to cause subtle capture bugs |
| `System.Threading` (`TTask.Run`) | A project-specific thread pool (see `references/threading-worker-pool.md` for a concrete lock-protected-queue-plus-workers example) | `System.Threading` has no direct FPC equivalent |
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

This table covers the most common cases. For gotchas cataloged with a real symptom + root cause + fix (threading/interop, networking/HTTP client choice, sockets/timeout, files/OS, config parsing, memory/leaks, types, evaluation order, 3-axis UI framework selection), see **`references/rtl-gotchas.md`** — it includes the real cases from `pascal-dfe-broker`, `pascal-pipes-faa`, and `pascal-redis-faa` with links to the exact files where each one was found.

## Mirrored tests: DUnitX (Delphi) + FPCUnit (FPC)

The pattern across all 5 projects: every new pure unit gets **two test mirrors** — same test name, same assertion — one running on DUnitX (Delphi) and one on FPCUnit (FPC). Folder layout varies a bit between projects (`tests/Unit/` + `tests/Unit/fpc/` in the `pascal-*-faa` family; `tests/Delphi/` + `tests/Lazarus/` in `opcb-object-pascal-component-builder`), but the rule is the same: **both mirrors must exist and stay in sync**.

Key points:

- **The acceptance criterion for any change is compiling AND passing tests on both compilers** — none of these projects accept "it passed on FPC only" or "it passed on Delphi only" as sufficient.
- **Memory-leak detection comes from both sides, and each side catches different bug classes**: heaptrc enabled on the FPC suites (criterion: 0 leaks) and `ReportMemoryLeaksOnShutdown`/FastMM on the Delphi side (also 0 leaks). `opcb-object-pascal-component-builder` documents this explicitly — Delphi-side FastMM caught leaks that FPC's heaptrc didn't. Don't disable either one thinking it's redundant.
- **Delphi's default RTTI only publishes `public`/`published` methods** — a test attribute (`[Test]`) placed on a `private` method compiles fine but never runs, with no warning. If a test "disappears" silently, check the method's visibility first.
- **No `Sleep` and no real wall-clock in tests.** A test that sleeps or reads the system clock to synchronize with asynchronous behavior is slow and flaky across compilers — timing characteristics differ between Delphi and FPC threads. Inject a fake/controllable time source (a clock abstraction the test can advance manually) and drive async completion through explicit signals instead of `Sleep`. **One exception: tests that are *about* contention.** A fake `Sleep` that returns instantly turns a bounded wait-and-retry loop into a tight spin, and the test starts depending on the OS scheduler instead. Observed in `pascal-db-faa`'s pool concurrency test (20 threads, 5 connections, 2000 retries): it failed in 2 of 6 runs in a Linux container, still in 1 of 20 with the fake `Sleep` calling `TThread.Yield`, and passed 20 of 20 with real 1 ms waits. (That the waiting thread burns its retries before the connection holders get scheduled is the explanation consistent with those numbers, not something that was instrumented.) For contention tests, use real short waits with a generous budget.
- **The FPC-side test runner can be both a GUI and a console tool from the same binary** — useful so a developer can run one manually while CI or an AI agent runs the other, with no extra project or file needed. `pascal-amqp-faa`/`pascal-redis-faa`/`pascal-named-pipes-faa` all use the same trick in their FPCUnit `.lpr`: `Interfaces, Forms, GuiTestRunner` are only pulled into the `uses` clause `{$IFDEF MSWINDOWS}`, and at runtime `if (running on Windows) and (ParamCount = 0) then` launch the GUI tree-runner (green/red bar, useful for a human debugging one failing test) `else` run the console runner (`--all --format=plain`, useful for CI or an agent to parse). Off Windows it's always console — the GUI units aren't even compiled in. Off Windows, also put `cwstring` next to `cthreads` in that `{$IFDEF UNIX}` block, and call `SetMultiByteConversionCodePage(CP_UTF8)` before running the tests on the console path — see the two FPC entries in `references/rtl-gotchas.md` "Encoding" for what goes wrong without them (both measured). There's no DUnitX-side equivalent in these repos: the Delphi test executable is plain console only, so a human running it manually just sees the console output too.
- **A thin compat adapter can make mirrored test bodies byte-identical, not just similarly-written.** `pascal-redis-faa` and, independently, a project built with this skill ([`pascal-snake`](https://github.com/fabianoallex/pascal-snake)) both use the same trick: a small class (`Redis.DUnitXCompat`/`Snake.DUnitXCompat`) that exposes FPCUnit's assertion names (`AssertEquals`, `AssertTrue`, `AssertFalse`) implemented on top of DUnitX's `Assert.AreEqual`/`Assert.IsTrue`/`Assert.IsFalse`. With it in the DUnitX-side test unit, the test *bodies* can be copy-pasted verbatim between the two mirrors — only the fixture declaration differs (`[TestFixture]`/`[Test]` vs `class(TTestCase)`/`published`). That turns "keep two hand-written bodies in sync" into "keep one body, pasted twice," which is a meaningfully easier thing to get right and to verify (`scripts/verify_test_mirrors.py`'s assertion-dialect check will flag it if a body drifts to native DUnitX/FPCUnit calls instead). Two things to get right in the adapter's overload set:
  - **String equality: pass `ignoreCase = False` explicitly.** DUnitX's `Assert.AreEqual(string, string)` without the `ignoreCase` argument uses `fIgnoreCaseDefault`, which is initialized to `true` (confirmed in Delphi 12's `source\DUnitX\DUnitX.Assert.pas`, line 1355; changeable via `Assert.IgnoreCaseDefault`) — so a string assertion silently passes on a case difference on the Delphi side only, while FPCUnit's `AssertEquals` is case-sensitive. `Redis.DUnitXCompat` already passes `False`; `pascal-db-faa`'s `PascalDb.DUnitXCompat` does the same.
  - **Floating point: mirror FPCUnit's overloads exactly, including what it *doesn't* have.** FPCUnit 3.2.2's `TAssert` has no `AssertEquals(Double, Double)` without a delta — and FPC resolves such a call to the `Currency` overload **without any warning**, comparing at 4 decimal places. Found in `pascal-db-faa` (not yet public): a `TDateTime` round-trip test passed on FPC at `Currency` precision while the original DUnitX test compared full `Double`s. If the Delphi adapter adds a delta-less `Double` overload for convenience, the same test body compiles on both sides but compares differently on each. Don't offer it; always pass an explicit delta (`AssertEquals(E, A, 0)` for exact). DUnitX *does* have a native `AreEqual(Currency, Currency)` — use it for the `Currency` overload rather than a tolerance-based call, which is ambiguous between DUnitX's `Double` and `Extended` tolerance overloads.
- **Release shared resources in `TearDown`, not only at unit finalization.** Observed in an FPCUnit integration suite: a unit-level singleton (a database connection factory) was released and the test database dropped in that unit's `finalization`, but every fixture also kept a reference to the factory in a field. The drop failed silently (pooled connections were still open), and the leftover database broke the next run. Setting the fixture field to `nil` in `TearDown` fixed it. The explanation consistent with that — not instrumented — is that the test framework frees its fixture objects only after the units they use have been finalized, so anything a fixture still references outlives the unit that owns it. — `pascal-db-faa` (not yet public), `tests/Integration/PascalDb.ContractTests.pas`
- **An FPCUnit test project with no `.lpk` of its own needs `FPCUnitTestRunner` and `FCL` added to `RequiredPackages` in its `.lpi`.** `fpc.cfg` doesn't pull in `fcl-fpcunit` by default, so `uses fpcunit, testregistry, ...` fails to resolve until those two packages are declared — there's no compiler error pointing at this specifically, just unresolved units. Confirmed in [`pascal-skills-threads`](https://github.com/fabianoallex/pascal-skills-threads), where this cost real trial-and-error before finding the fix by inspecting the installed Lazarus's `components/fpcunit/*.lpk`. `scripts/scaffold_dual_project.py register` doesn't set this for you (it only wires the `.lpi` into the project group) — add it by hand to the `.lpi`'s `RequiredPackages` when hand-building a test-runner project.
- **A ready-to-use verification script, not just an idea**: `scripts/verify_test_mirrors.py` (generalized from a prototype in `pascal-amqp-faa`) statically scans both suites and flags divergences — a test with no mirror, a fixture declared but never registered, an assertion or RTL call from the wrong dialect, a test attribute outside a `public`/`published` section — without compiling anything. See `references/test-mirror-verification.md` for what each check does and how to extend it. Not mandatory for every project, but worth adopting once mirrors are large enough that keeping them in sync by hand starts silently failing.

### CI: keep the YAML thin

Delphi Community Edition can't build from the command line. This means Delphi-side validation is usually manual, through the IDE — and automated CI (where it exists, like in `pascal-dfe-broker`) typically only covers the FPC/Linux side. Don't assume "CI is green" covers the Delphi side; that still depends on someone running the suite in the IDE.

The reverse also holds: **a suite that is green on Windows can hide bugs that only Linux shows — run it on Linux early**, even before there is CI (a Docker image with FPC is enough). In `pascal-db-faa`'s first Linux run, three latent problems appeared at once, all invisible on the author's pt-BR Windows machine: the `cwstring` issue, a flaky concurrency test (both above), and seven tests building dates with `StrToDateTime('28/12/2025 ...')`, which depends on the machine's date format (not a dual-compiler issue — any Windows with a different locale would fail too — but only the Linux run surfaced it). — `pascal-db-faa` (not yet public), `tools/test_fpc_docker.sh`

`pascal-dfe-broker`'s real workflow has 3 jobs, but every one of them does the same thing: checkout, optionally initialize a git submodule, then run exactly one shell script. There are zero inline `apt-get`/FPC-install commands in the YAML itself — all Docker/FPC provisioning and test orchestration lives in versioned shell scripts under `tools/docker/`, the same scripts a developer runs locally. That's the reusable pattern, not the literal 3-job shape (which is specific to that project having a companion simulator image and a systemd unit): **keep the workflow file minimal, and put provisioning + orchestration in a script, not inline YAML.**

`assets/github-actions-fpc-linux.yml` is a copyable single-job starting point following this pattern, paired with `assets/ci-test.sh.example` (a stub showing FPC install → `lazbuild -B -r` → run the compiled FPCUnit binaries → call `scripts/verify_test_mirrors.py`) — copy the `.example` in, edit it for your project, and add more jobs the same way as the project grows.

## What NOT to generalize from these projects

Not everything that shows up across the 5 projects is a universal dual-compiler convention — some of it is just the author's portfolio-organization choices:

- **Reusing whole units across sibling repositories** (e.g. `AMQP.Threading.pas` copied and renamed to `Redis.Threading.pas`/`Pipes.Threading.pas`, with no build dependency between repositories) is a portfolio pattern, not a compatibility technique. It only makes sense when several small, independent projects share the same infrastructure base (threading, transport) and the author prefers copying over coupling repositories.
- **Android/FMX support** is only relevant if the project genuinely targets mobile via Delphi — don't add that platform axis "just in case."
- A dual-language README with a sync rule is a documentation convention of the author's, not a technical dual-compiler requirement.
