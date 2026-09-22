# Pascal Skills FAA

Reusable [Claude Code](https://docs.claude.com/en/docs/claude-code) skills for Object Pascal work — starting with everything needed to build and maintain Delphi/Lazarus **dual-compiler** projects.

## Why this repo exists

Two reasons, one practical and one not.

**Practical**: I maintain several Object Pascal projects that compile on both Delphi and Lazarus/FPC (see [Reference projects](#reference-projects) below). Every time I start a new one, or hit a bug that only shows up on one of the two compilers, I end up re-explaining the same rules and pointing at the same example code. This repo turns that knowledge into a skill I can point Claude at for any project, instead of re-deriving it from scratch each time.

**Promotional**: Lazarus is a solid, actively maturing tool — but it's still underused relative to how far it's come, especially in Brazil, which has one of the largest Delphi communities in the world and comparatively little Lazarus adoption. A big part of the reason, in my experience, is friction: teams don't add Lazarus support to an existing Delphi codebase because keeping the two in sync feels risky and poorly documented, so it never gets tried. This repo is a small attempt to lower that barrier — writing down, concretely, what actually breaks between the two compilers and how real, working projects handle it, so "let's also support Lazarus" is a less intimidating call to make.

## What's here

| Skill | What it covers |
|---|---|
| [`dual-compiler-delphi-lazarus`](dual-compiler-delphi-lazarus/SKILL.md) | Project layout for a single codebase that compiles on both compilers, the `.inc` compatibility-file pattern, `{$MODE DELPHI}` vs `{$mode objfpc}`, a catalog of RTL divergences between Delphi and FPC (with real symptom → root cause → fix), and mirrored DUnitX/FPCUnit testing |

More skills will land here as they get extracted from ongoing work — refactoring patterns, packaging/build tooling, component-library conventions, etc.

## Reference projects

The `dual-compiler-delphi-lazarus` skill isn't theoretical — it's distilled from and links back to 5 real, working dual-compiler projects:

- [pascal-amqp-faa](https://github.com/fabianoallex/pascal-amqp-faa) — AMQP 0-9-1 client + embeddable broker
- [pascal-dfe-broker](https://github.com/fabianoallex/pascal-dfe-broker) — Brazilian electronic invoice (NFe) broker
- [pascal-pipes-faa](https://github.com/fabianoallex/pascal-pipes-faa) — named pipes / Unix domain sockets, including an Android backend
- [pascal-redis-faa](https://github.com/fabianoallex/pascal-redis-faa) — Redis client
- [opcb-object-pascal-component-builder](https://github.com/fabianoallex/opcb-object-pascal-component-builder) — fluent component builder for VCL/FMX/LCL

When the skill references a pattern or a gotcha, it links to the actual file in one of these repos rather than duplicating the code — so the example stays live instead of drifting out of date.

## Using the skill

Drop (or symlink) the skill folder into a project's `.claude/skills/` directory, or into your personal `~/.claude/skills/`, and Claude Code will pick it up automatically whenever the conversation touches dual-compiler Delphi/Lazarus work — starting a new dual-compiler project, porting an existing one, or debugging a compiler-specific bug.

## Contributing

Found a Delphi/FPC divergence that isn't in `references/rtl-gotchas.md` yet? PRs and issues are welcome — the format is symptom → root cause → fix, with a link to where it was found. That's exactly how the list grew inside the original projects, and how it'll keep growing here.
