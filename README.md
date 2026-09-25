# Pascal Skills FAA

Reusable [Claude Code](https://docs.claude.com/en/docs/claude-code) skills for Object Pascal work — starting with everything needed to build and maintain Delphi/Lazarus **dual-compiler** projects.

## How this skill approaches things

A skill is instructions and context Claude loads when a task matches — not a black box, and not a rulebook to obey blindly. Three things this one deliberately does because of that:

- **Nothing is a black box.** Every claim links to real, inspectable code in one of the reference repos below, and the reasoning is written down, not just the instruction — you can check the "why" yourself before trusting it, and Claude can point you at the exact line it's acting on.
- **Trade-offs are stated, not hidden behind a single answer.** Where more than one approach is genuinely valid — `{$MODE DELPHI}` vs `{$mode objfpc}`, relying on `.dfm`/`.lfm` vs building UI in code — the skill lays out both with their real cost, instead of picking a winner for you. Your project's context decides which one fits.
- **It's meant to be adapted, not followed as-is.** The skill separates what's a universal dual-compiler pattern from what's one project's own choice (see its "What NOT to generalize" section) specifically so you know what to keep and what to fork and change for your own project.

## What the skill does

The flagship skill, `dual-compiler-delphi-lazarus`, hands Claude everything it needs to work on a Pascal codebase that has to compile on both Delphi and Lazarus/FPC:

- **How to lay out a new dual-compiler project** — one shared `src/` tree, the `.inc` compatibility-file pattern, `{$MODE DELPHI}` vs `{$mode objfpc}`, `.dpr`/`.dproj`/`.lpr`/`.lpi`/`.lpk` project files, encoding, line endings.
- **What actually breaks between the two RTLs** — a catalog of real Delphi/FPC divergences (threading, sockets, encoding, memory, types...), each with the symptom, the root cause, and the fix that was used, so Claude isn't guessing.
- **How to keep both compilers honestly tested** — the mirrored DUnitX (Delphi) + FPCUnit (FPC) pattern, why both matter for memory-leak detection, and the sharp edges around Delphi Community Edition not building from the command line.
- **Scaffolding and verification tooling** — `scripts/scaffold_dual_project.py` generates the skeleton of a new dual-compiler project (`.inc`, starter unit, `.dpr`/`.dproj` + `.lpi`, project groups); `scripts/verify_test_mirrors.py` statically checks that DUnitX/FPCUnit test mirrors stay in sync; `scripts/build_rcdata_res.py` writes a `.res` with embedded files on any OS (no `brcc32`/`windres`, which Linux FPC can't use for `.rc` files); `assets/github-actions-fpc-linux.yml` is a copyable CI starting point for the FPC/Linux side.
- **`.dfm`/`.lfm` form-file drift** — the harshest source of real friction in dual-compiler VCL/LCL projects, and what to do about it. See [below](#a-known-hard-problem-dfmlfm-forms).
- **Native library interop on Linux** — OpenSSL 3.0's default provider not being active by default (breaks certificate/PKCS12 loading on Debian 12/Ubuntu 22.04), FPU exceptions native C libraries trip that FPC leaves unmasked, and a handful of other Linux-only gotchas around OpenSSL/libxml2 that never show up testing on Windows.
- **Running unattended as a background service** — keeping one shared, testable core and wrapping it in two thin, deliberately single-platform hosts: a dual-compiler console host under systemd on Linux, and a Delphi-only `TService` Windows Service, plus the real gotchas specific to the Windows Service wrapper (can't block in `OnStart`, working directory is `System32`, doesn't see the interactive user's `PATH`).

It triggers automatically whenever the conversation touches this territory — starting a new dual-compiler project, or debugging something that only fails on one side — without needing to say "use the skill" explicitly.

## What's here

| Skill | What it covers |
|---|---|
| [`dual-compiler-delphi-lazarus`](dual-compiler-delphi-lazarus/SKILL.md) | Everything described above, plus full reference docs in [`references/`](dual-compiler-delphi-lazarus/references/) and runnable tooling in [`scripts/`](dual-compiler-delphi-lazarus/scripts/) and [`assets/`](dual-compiler-delphi-lazarus/assets/) |

More skills will land here as they get extracted from ongoing work — refactoring patterns, packaging/build tooling, component-library conventions, etc.

## A known hard problem: `.dfm`/`.lfm` forms

If your project has VCL/LCL forms, read this before anything else — it causes more real friction than any RTL divergence the skill documents. Delphi's `.dfm` and Lazarus's `.lfm` are two **independently hand-maintained** files behind the same form, and both IDEs **silently rewrite the entire file** when a form is opened and saved in their designer — not just what a developer changed. Confirmed by diffing real pairs: Lazarus stamps a per-form DPI value into the `.lfm`, and reopening a form on a different-scale display rewrites *every coordinate in the file* to match, with nothing about the layout actually changing; `Anchors` sets get canonically reordered by each serializer; accented text gets re-encoded. None of that is a bug to fix — it's just what happens when a file is round-tripped through a design-time tool that owns its own serialization rules.

**Recommendation**: don't hand-edit a `.dfm`/`.lfm` expecting the change to survive, don't review a designer-save diff line by line (open the form visually instead), and — where the project can afford it — prefer building UI in `.pas` code instead of relying on the form designer at all. [`opcb-object-pascal-component-builder`](https://github.com/fabianoallex/opcb-object-pascal-component-builder) exists specifically for this: it builds VCL/LCL/FMX components fluently in code, with real examples that ship no `.dfm`/`.lfm` at all and compile unmodified on both compilers. See `dual-compiler-delphi-lazarus/references/forms-dfm-lfm.md` for the full catalog and the evidence behind each claim.

## Why this repo exists

Two reasons, one practical and one not.

**Practical**: I maintain several Object Pascal projects that compile on both Delphi and Lazarus/FPC (see [Reference projects](#reference-projects) below). Every time I start a new one, or hit a bug that only shows up on one of the two compilers, I end up re-explaining the same rules and pointing at the same example code. This repo turns that knowledge into a skill I can point Claude at for any project, instead of re-deriving it from scratch each time.

**Promotional**: Lazarus is a solid, actively maturing tool — but it's still underused relative to how far it's come, especially in Brazil, which has one of the largest Delphi communities in the world and comparatively little Lazarus adoption. A big part of the reason, in my experience, is friction: teams don't add Lazarus support to an existing Delphi codebase because keeping the two in sync feels risky and poorly documented, so it never gets tried. This repo is a small attempt to lower that barrier — writing down, concretely, what actually breaks between the two compilers and how real, working projects handle it, so "let's also support Lazarus" is a less intimidating call to make.

## Reference projects

The `dual-compiler-delphi-lazarus` skill isn't theoretical — it's distilled from and links back to 5 real, working dual-compiler projects:

- [pascal-amqp-faa](https://github.com/fabianoallex/pascal-amqp-faa) — AMQP 0-9-1 client + embeddable broker
- [pascal-dfe-broker](https://github.com/fabianoallex/pascal-dfe-broker) — Brazilian electronic invoice (NFe) broker
- [pascal-pipes-faa](https://github.com/fabianoallex/pascal-pipes-faa) — named pipes / Unix domain sockets, including an Android backend
- [pascal-redis-faa](https://github.com/fabianoallex/pascal-redis-faa) — Redis client
- [opcb-object-pascal-component-builder](https://github.com/fabianoallex/opcb-object-pascal-component-builder) — fluent component builder for VCL/FMX/LCL

When the skill references a pattern or a gotcha, it links to the actual file in one of these repos rather than duplicating the code — so the example stays live instead of drifting out of date.

## Testing the skill on fresh scenarios

Besides the 5 reference projects the skill is distilled from, it's also exercised end-to-end by giving an agent a real task and collecting feedback afterward on what the skill actually helped with versus what was missing — two different ways so far: **blind** (a fresh session, pointed only at this repo's GitHub URL, with no mention it's a test) and **open acceptance runs** (the prompt explicitly names and links the skill, closer to how most users will actually invoke it). Both are useful; blind runs catch gaps the model can't paper over by "trying to be helpful to a known test," open runs are cheaper to repeat as a regression check after a skill change.

| Project | Task given | What came out of it |
|---|---|---|
| [`pascal-skills-threads`](https://github.com/fabianoallex/pascal-skills-threads) | Blind. "Build an app that downloads several files at once using threads, compiling on both Delphi and Lazarus." | A working dual-compiler console app (10/10 unit tests passing on both compilers, confirmed build+run on Delphi 11 and FPC 3.2.2). The honest feedback afterward (see [`SKILL-FEEDBACK.md`](https://github.com/fabianoallex/pascal-skills-threads/blob/main/SKILL-FEEDBACK.md) in that repo) surfaced 3 real documentation gaps, since fixed here: no coverage of `TThread.Synchronize`/`.Queue` silently doing nothing in a console app with no message loop, no worked example of a worker pool beyond "don't use `TTask.Run`" (see `references/threading-worker-pool.md`), and no guidance on choosing a dual-compiler HTTP client (Indy isn't enabled by default in Lazarus, `fphttpclient` is FPC-only). |
| [`pascal-snake`](https://github.com/fabianoallex/pascal-snake) | Open. "I want to create a Delphi/Lazarus project implementing a snake game. I want you to use this skill: [pascal-skills-faa]." | A working VCL/LCL game (Delphi 12 CE + Lazarus 4.0, 20/20 tests on both sides, 0 leaks). The only reference project with a real GUI (VCL/LCL forms, not console), which is exactly why it surfaced findings none of the console-only projects could: an `.dpr`/`.lpr` `.res` collision, a double-DPI-scaling bug specific to code-built (`CreateNew`) forms at non-100% display scaling, and confirmation that accented UI text renders correctly on both sides. See [`SKILL_FEEDBACK.md`](https://github.com/fabianoallex/pascal-snake/blob/main/SKILL_FEEDBACK.md) in that repo — most of it was applied in a prior commit here, but that same file also records a later scope note (GUI/VCL-LCL isn't the skill's intended focus) that hasn't been acted on yet; treat the GUI-specific content currently in the skill as unresolved on that point. |

More scenarios will be added here as they're tried.

**A caveat on how to read this table**: the "what came out of it" feedback is self-reported by the same agent session that did the task, asked afterward what it would or wouldn't have known *without* the skill. That's an introspective judgment about a counterfactual, not a measured one — once a session has read the skill, it's genuinely hard (for a model, same as for a person) to cleanly separate "I already knew this" from "I just learned this." Some of the claims above hold up under scrutiny (e.g. the HTTP-client gap and the FPCUnit `RequiredPackages` gap both describe actual exploration/trial-and-error, not just a hunch), while others are weaker — the `Synchronize`/message-loop point, for instance, is general Delphi threading knowledge the same session caught and avoided on its own before it became a real mistake, which is a smaller gap than "cost me" framing suggests. Treat this table as a useful source of candidate documentation gaps, not as proof the skill changed the outcome. The rigorous version of this test — running the same task twice, once with the skill available and once without, and comparing the two actual results — hasn't been done yet; that's the next real step if the goal is to *measure* the skill's effect rather than collect plausible-sounding feedback about it.

## Versions tested

Everything here was verified against one specific toolchain, not "Delphi" and "Lazarus" as abstractions:

| | Version |
|---|---|
| Delphi | 12, **Community Edition**, Windows |
| Free Pascal (FPC) | 3.2.2 |
| Lazarus/LCL | 2.2.6 |

Older Delphi versions in particular may diverge from what's documented here — none of it has been checked against them, and some of the RTL/generics/anonymous-method gotchas are exactly the kind of thing that could differ by version. If you hit a divergence on a different version (an older Delphi release, an FPC 3.3.x/trunk build, a newer Lazarus), that's genuinely useful, not noise — see [Contributing](#contributing) below.

## Using the skill

Drop (or symlink) the skill folder into a project's `.claude/skills/` directory, or into your personal `~/.claude/skills/`, and Claude Code will pick it up automatically whenever the conversation touches dual-compiler Delphi/Lazarus work — starting a new dual-compiler project or debugging a compiler-specific bug. Porting an existing single-compiler codebase is deliberately not a goal: every project has its own particulars, so the skill's gotcha catalog can help there, but it makes no promise about it.

## Contributing

Found a Delphi/FPC divergence that isn't in `references/rtl-gotchas.md` yet? PRs and issues are welcome — the format is symptom → root cause → fix, with a link to where it was found. That's exactly how the list grew inside the original projects, and how it'll keep growing here.

This especially includes **version-specific findings**: something that behaves differently on a Delphi version other than 12 CE, or on an FPC/Lazarus version other than 3.2.2/2.2.6 (see [Versions tested](#versions-tested) above). One author on one machine can't catch that kind of divergence alone — say which version it applies to, and it'll get noted as such rather than presented as universal.
