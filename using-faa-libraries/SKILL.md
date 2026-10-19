---
name: using-faa-libraries
description: Building an application on the *-faa Object Pascal libraries (pascal-common-faa, pascal-jsonmapper-faa, pascal-db-faa, pascal-api-infra-faa, pascal-amqp-faa, pascal-redis-faa, pascal-pipes-faa) on Delphi and/or Lazarus/FPC. Use when adding one of them to a project (git submodule, search path, .lpk, lazbuild), when a build says "needs pascal-common-faa 1.x or later" or compiles against the wrong copy of a package; when writing a Horse REST API with PascalApi.* middlewares, DTOs mapped with TJsonMapper, database access with PascalDb.* (factory, pool, mock, migrations), messaging with AMQP.*/Redis.*/Pipes.*; for PcPool, SafeWriteln, TPcTracing, metrics; and for shutdown hangs, lost consumer exceptions, out-of-order messages or garbled accents in an application that uses them.
---

# Using the `*-faa` libraries

The `*-faa` libraries are MIT, dual-compiler (Delphi 12 and FPC 3.2.2), by one author, and meant
to be combined in one application. Each one documents its own API well: **this skill doesn't
repeat that.** It holds what no single library's documentation can:

- the rules that hold for an application using **several** of them,
- where to read before doing each kind of thing, and
- what each library's maintainers measured that a user still has to know.

Which library covers which need, unit by unit, is the index in the `dual-compiler-delphi-lazarus`
skill: `references/faa-libraries.md` (same plugin; on GitHub,
https://github.com/fabianoallex/pascal-skills-faa/blob/main/dual-compiler-delphi-lazarus/references/faa-libraries.md).
Check it before writing infrastructure an existing library already has.

## How to approach the task

1. **Setting up a project, or a build error about versions, packages or units not found** →
   `references/application-setup.md`: one copy of each library, the Lazarus package rule, the
   minimum-version matrix, what every FPC program does at startup.
2. **Threads, shutdown, logging, tracing, errors from callbacks** → `references/runtime.md`. Read
   it before writing a consumer, a background worker or a VCL/LCL form that queues work: the
   libraries share one thread pool per process.
3. **Using one library** → `references/libraries.md`: for each library, the doc to read first and
   the few rules that bite. Then read that doc (a guide, a README section) on GitHub or in the
   submodule. Don't write from memory: the APIs changed in 0.x versions, and the docs say since
   which version each behavior holds.
4. **An API on Horse**: start from pascal-api-infra-faa's guides (`docs/guide/README.md` is the
   index) and its samples (`samples/01-api` uses every middleware, `samples/02-db` adds the
   database, `samples/03-tenants` multi-tenancy, `samples/04-messaging` Redis + AMQP + pipes).
   Copy the sample closest to the task instead of assembling the program from the reference.
5. **A repository: INSERT, PATCH, filtered lists** → `references/repository-patterns.md`:
   normalize with the application's `TNorm` factory inside the optionals, validate apart (one
   overload per shape of member), bind the optional as it is next to its `ProcessTag`; no
   `if HasValue` in the repository. Proven in pascal-agenda-faa's repositories.
6. **Something that looks like a library bug**: check the library's CHANGELOG for the version in
   use first. Several "bugs" were fixed behavior (a consumer exception lost before amqp 0.4.0, a
   duplicate JSON member accepted before jsonmapper 0.4.0, a `Currency` off by a few units on FPC
   before jsonmapper 0.6.0). If it is still there in the latest version, say so with the
   reproduction: the libraries' gotcha lists grew that way.

## The rules that hold across the family

These come from real failures, each measured in the source cited in the reference files.

- **One copy of each library per application**, provided by the application (submodule + search
  path or package). Never the copy inside another library's `external/`, and `git submodule
  update --init` without `--recursive`.
- **On Lazarus, name the copy**: every project lists `pascal_common_faa` first, with
  `DefaultFilename` and `Prefer="True"`. Without `Prefer`, lazbuild silently builds against the
  copy registered in the IDE.
- **The application's pascal-common-faa meets the highest minimum** of the libraries it uses (the
  matrix is in `references/application-setup.md`). An older copy stops the build with a readable
  `$MESSAGE FATAL`; pascal-jsonmapper-faa has no such check.
- **Every FPC program**: `SetMultiByteConversionCodePage(CP_UTF8)` at startup; on Unix,
  `cthreads` and `cwstring` first in the `uses`.
- **Log through `SafeWriteln` with `PcSetSafeLogUtf8(True)`**, never `Writeln`, in a program with
  threads or a redirected stdout (Docker, systemd, a service): lines come out cut, mixed or in
  the wrong code page otherwise.
- **`PcPool` belongs to the whole process.** Work that blocks may go there; work another thread
  waits for synchronously goes on a pool of its own. An object or a form with items on it waits
  for them before it is freed.
- **Every receiver handles its own errors**: `OnConsumerError` on an AMQP channel, `OnError` on a
  pipe server or client. Messages are processed in parallel unless the code asks for order
  (`CreateChannel(True)` or `Qos(1)`).
- **JSON goes out as UTF-8 bytes with its content type**: `TJsonSend.Send` in a Horse handler,
  bytes with `application/json` on a queue or a pipe.

## Keeping this skill right

- Add only what came from real friction, with the measurement kept apart from the explanation,
  and say what wasn't measured. A rule here points to the library doc that holds the details.
- When a library's doc gains a section that covers a point here, replace the point with a link.
- **Update the version matrix in `references/application-setup.md` with every release** of a
  library that changes a minimum: it is the only place where the minimums of all libraries sit
  together.
