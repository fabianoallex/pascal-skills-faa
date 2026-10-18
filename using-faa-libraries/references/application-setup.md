# Setting up an application on the `*-faa` libraries

What an application does once, so the libraries build from the right copy and behave the same on
both compilers. Each point says where it was measured.

## One copy of each library, provided by the application

An application that uses several `*-faa` libraries has **one** copy of each, which it provides
itself: a git submodule (for example under `vendor/` or `external/`) plus a search path on
Delphi, or one registered or preferred `.lpk` on Lazarus.

- **Never point at the copy inside another library's `external/`.** Those submodules exist for
  that library's own tests and CI. Using one means two versions of the same units one `;` apart
  in the search path.
- **Check out submodules without `--recursive`.** A recursive clone brings the libraries'
  private `external/` copies into the application's tree (measured in pascal-common-faa's F9,
  `docs/migrating.md`, step 1). That does no harm until a path points at them.
- **pascal-common-faa is shared by all of them**, so it is the copy that matters most: amqp,
  redis, pipes, db and api-infra all use it, and the application gives them the same one.

Source: pascal-common-faa README, "For library authors: one copy per application"; the same rule
in each library's README (build section).

## Lazarus: name the copy in every project

lazbuild resolves a required package by name. A package registered in the IDE
(`packagefiles.xml`) **wins over** a `DefaultFilename` without `Prefer`, and a `DefaultFilename`
that doesn't exist falls back to the registered one without a word (pascal-common-faa gotcha 2,
measured 2026-10-04: the build log showed the mapper compiled from another checkout).

So each `.lpi` of the application lists the packages it wants, **pascal-common-faa first**,
each with `DefaultFilename` and `Prefer="True"`:

```xml
<Item>
  <PackageName Value="pascal_common_faa"/>
  <DefaultFilename Value="vendor\pascal-common-faa\packages\pascal_common_faa.lpk" Prefer="True"/>
</Item>
```

- **With the JSON bridge** (optionals in DTOs), list `pascaljsonmapper_pkg` before
  `pascal_common_faa_jsonmapper`. The bridge requires the mapper by name only. Leave the mapper
  line out, and lazbuild silently builds against whatever mapper the IDE has (measured in
  pascal-db-faa's pilot, F6).
- **A project that compiles a library from its `src`** instead of its `.lpk` still needs only the
  `pascal_common_faa` package. Don't also put pascal-common-faa's `src` on the path: its units
  were compiled only into the package's `lib` (measured in pascal-dfe-broker, F10).
- **Building a library's `.lpk` alone** fails with "Broken dependency ... pascal_common_faa" until
  `pascal_common_faa.lpk` is registered, and leaves a `packagefiles.xml` in the current folder
  (gotcha 6). Add `/packagefiles.xml` to `.gitignore`.
- **When in doubt, read the build log**: the `-Fu` paths say which copy was compiled.

Package names: `pascal_common_faa`, `pascal_common_faa_jsonmapper`, `pascaljsonmapper_pkg`,
`pascal_db_faa` (+ `pascal_db_faa_sqldb`, `pascal_db_faa_zeos`), `pascal_api_infra_faa`,
`pascal_amqp_faa` (+ `pascal_amqp_faa_server` for the embedded broker), `pascal_redis_faa`,
`pipes_faa`. pascal-api-infra-faa's Horse units (`src/horse`) are **not** in its package (Horse
has no Lazarus package): add `src/horse` and Horse's own `src` to the project's paths.

Source: pascal-common-faa `docs/migrating.md`, steps 3 and 4 (written for library authors; the
project-side rule is the same).

## Delphi: search paths

Each library's `src` and pascal-common-faa's `src`. Also:

- the bridge's `bridges/jsonmapper` and the mapper's `src`, for optionals in JSON;
- pascal-api-infra-faa's `src/horse` and Horse's `src`;
- amqp's `src\server` for the embedded broker.

The libraries use `uses` without unit scope names; the default scope names (`System;Winapi`)
are enough.

## The minimum-version matrix

The application's copy of each library has to satisfy **every** library that uses it, so its
pascal-common-faa is at least the highest minimum below. As of 2026-10-18:

| Library (latest tag) | needs pascal-common-faa | needs also |
|---|---|---|
| pascal-common-faa (v1.17.0) | — | — |
| pascal-jsonmapper-faa (v0.6.0) | — | — |
| pascal-db-faa (v0.15.0) | 1.8.0 | — |
| pascal-api-infra-faa (v0.16.0) | 1.17.0 | pascal-db-faa 0.15.0, pascal-jsonmapper-faa 0.6.0; pascal-redis-faa 0.2.0 only for `src/redis` (the Redis key store) |
| pascal-amqp-faa (v0.4.1) | 1.8.0 | — |
| pascal-redis-faa (v0.2.0) | 1.8.0 | — |
| pascal-pipes-faa (v0.3.0) | 1.0.0 | — |

pascal-api-infra-faa sets the bar: 0.16.0 needs 1.17.0 (`PascalCommon.Random` and
`PascalCommon.AesGcm` for its JWT signing keys, `PascalCommon.Crypto`, which its `PascalApi.Crypto`
wraps), even if the application never uses them; 0.15.0 needed 1.16.0. Use the
latest pascal-common-faa unless something pins it: within a major version it only adds (strict
semver, its README).

**How a too-old copy shows:** the build stops with the library's own message, for example
`pascal-amqp-faa needs pascal-common-faa 1.8.0 or later`. FPC shows `Fatal: (2022) User defined:
...`, Delphi shows `F1054 ...`. Measured on both compilers (pascal-common-faa `docs/migrating.md`,
step 5).

**Except pascal-jsonmapper-faa**, which has no version constant. Its minimum is only in
pascal-api-infra-faa's `.lpk`, so on Delphi:

- a mapper before 0.5.0 fails on the missing `EJsonInputError`;
- 0.5.0 compiles silently, without 0.6.0's exact `Currency` on FPC.

Check the mapper's version by hand when upgrading pascal-api-infra-faa (its `CLAUDE.md`,
"Dependencies").

To refresh this table, read each library's check:

```
grep -rn "PASCALCOMMON_VERSION <\|PASCALDB_VERSION <" <library>/src
```

## Every FPC program

In `{$MODE DELPHI}` on FPC, `string` is an 8-bit string in the process's code page. So an FPC
program that uses the libraries:

1. **Calls `SetMultiByteConversionCodePage(CP_UTF8)` at startup** (inside `{$IFDEF FPC}`).
   Without it, non-ASCII text outside the code page becomes `?`, and SQL sources refuse to load
   (`ESqlSourceException`) rather than corrupt a statement. LCL applications already run in UTF-8.
2. **On Unix, puts `cthreads` and `cwstring` first in the program's `uses`.** The thread pool and
   the connection pool need `cthreads`. Without `cwstring`, a `Variant` holding a non-ASCII
   `WideString` comes back as invalid UTF-8.
3. **Saves source files that have non-ASCII literals as UTF-8 with a BOM**, so both compilers
   read them as UTF-8.

Delphi needs none of this. Source: pascal-db-faa `docs/adapters.md`, "What a Free Pascal program
must do", with the measurements in its `docs/gotchas.md`. pascal-api-infra-faa's samples
check `Belém` and `São Paulo` over HTTP.

## Checking for leaks in the application's own CI

- **FPC on Linux:** heaptrc's exit report doesn't reach the console. A leaking program prints
  nothing and exits 0 (pascal-common-faa gotcha 5, measured on Debian bookworm). Run with
  `HEAPTRC="log=<file>"` and check the file for `0 unfreed memory blocks`. A check that only
  greps the console passes on a leak. Two consumers (amqp, dfe-broker) had never actually seen
  their Linux leak report until this was found.
- **Check that heaptrc is on at all** (`-gh`, or `UseHeaptrc` in the `.lpi`). pascal-redis-faa's
  test projects never had it.

## A worked application: pascal-dfe-broker

[pascal-dfe-broker](https://github.com/fabianoallex/pascal-dfe-broker) is an application (not a
library) built on pascal-amqp-faa and pascal-common-faa. Copy its setup when starting one:

- the libraries as submodules in `vendor/`;
- the `.lpi` files listing `pascal_common_faa` first with `Prefer="True"`;
- the `.dproj` files with `vendor\pascal-common-faa\src` on the search path;
- the Docker scripts passing `-Fu`/`-Fi` by hand.

Its `CLAUDE.md` records what the migration measured. `.ci/f10-findings.md` holds what it reported
back to the libraries.

Two lessons from its releases:

- **Package a release with `lazbuild --pcp=<a folder of its own>`**, from a clean clone, so the
  build doesn't change which packages the developer's IDE has registered (measured on its v0.2.0
  release).
- **Clone the release tree into a short path.** In a long temporary path, cloning the submodules
  failed with `invalid index-pack output` (same release).
