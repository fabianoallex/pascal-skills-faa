# RTL gotcha catalog: Delphi vs FPC

Each item below is a real case, found in one of the reference projects, with the observed symptom, the root cause, and the fix that was used. When investigating a behavior that diverges between Delphi and FPC, check the closest matching category here first — there's a good chance it's already been cataloged.

If you find a new gotcha that isn't listed here, it's worth adding it in this same format (symptom → root cause → fix), and also to the `CLAUDE.md` of the project where it was found — that's how these lists grew in the original projects.

## Threading / interop

- **`IInterface` calling convention depends on platform in FPC**: `stdcall` on Windows, `cdecl` on Unix. A COM-like interface that assumes a fixed `stdcall` breaks silently (or fails to compile) on FPC's Unix side. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`TThread.WaitFor` is not idempotent on FPC/Unix**: calling `WaitFor` more than once triggers a second, unconditional `pthread_join`, which can hang or behave differently from Delphi (where calling it again is safe). Guard with a "have I already waited for this thread" flag if the code may call `WaitFor` more than once. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **Delphi's default RTTI only publishes `public`/`published` methods**: a test method (e.g. DUnitX's `[Test]`) declared in a `private` section compiles without error but is never discovered/run, with no warning from the framework. Symptom: "the test disappeared", a lower test count than expected. Always check `public`/`published` visibility on methods decorated with test attributes. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`Halt` leaks managed local variables**: `Halt` doesn't normally run pending `finally`/destructor cleanup on the stack, so local strings/interfaces/dynamic arrays can leak. If the process needs to exit early cleanly, prefer signaling and letting normal flow wind down, or free things manually before `Halt`. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`SIGPIPE` kills the process on Linux without `MSG_NOSIGNAL`**: writing to a socket whose peer already closed the connection raises `SIGPIPE`, which by default kills the whole process on Linux (unlike the more commonly-seen "silent" behavior on Windows). Use `MSG_NOSIGNAL` on the send call, or explicitly ignore `SIGPIPE` at the process level. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)

## Sockets / timeout

- **Delphi's `TSocket.ReceiveTimeout`/`SendTimeout` only take effect if assigned while the socket is already connected**: Delphi's implementation pushes the timeout onto the real socket inside `CreateSocket`, at a point where the handle may still be invalid — assigning the timeout before connecting has no effect. Symptom: "FPC honors the timeout correctly, but Delphi waits for the entire command (or hangs) even with a timeout configured." Fix by re-assigning the timeout *after* the socket is connected. — [`pascal-redis-faa`](https://github.com/fabianoallex/pascal-redis-faa)

## Files / operating system

- **`SysUtils.RenameFile` does not overwrite an existing destination on Windows** — neither on Delphi nor on FPC. If the use case needs to overwrite, call `MoveFileEx` with the `MOVEFILE_REPLACE_EXISTING` flag directly, behind `{$IFDEF <YOUR_DEFINE>_WINDOWS}`. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker), unit `src/DFe.CursorStore.Arquivo.pas`
- **`MOVEFILE_WRITE_THROUGH` doesn't exist in FPC 3.2.2's `Windows` unit** — only `MOVEFILE_REPLACE_EXISTING` is available there. If the actual use case needs write-through semantics, declare the constant manually (the Windows API's numeric value is stable) instead of assuming it's in the standard unit. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)

## Config / parsing

- **Delphi's `TCustomIniFile.ReadBool` doesn't understand `"true"`/`"false"` as text** — Delphi's implementation delegates to `StrToIntDef`, so it only recognizes `"0"`/`"1"` (and numeric variants). FPC understands `"true"`/`"false"` as text. This is a real bug that passed 52 green tests on FPC before showing up only when running on Delphi — a good reminder that "it passed on FPC" isn't enough (see the mirrored-tests section in the main SKILL.md). Fix: write a project-specific boolean-parsing function that accepts both formats, instead of relying on `ReadBool`. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker), see `DFe.Config.LerBooleano` in `src/DFe.Config.pas`

## Memory / interfaces

- **An object constructed inline as an interface-typed argument, in a call that raises an exception, leaks one block on FPC 3.2.2** (caught via heaptrc): writing something like `Foo.Bar(TMyObject.Create)` where `Bar` raises before the interface takes ownership of the object can leave the temporary object unfreed on this FPC version. Fix: assign the object to a local variable (of the interface type) before passing it into the call, instead of constructing it inline. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)

## Types

- **`Length()` of a dynamic array is `NativeInt` on Delphi Win64** (but `Integer`/`LongInt` on other compiler/platform combinations). Comparisons or generic calls that explicitly assume `Integer` (e.g. `Assert.AreEqual(n, Length(x))` where `n: Integer`) may fail to compile on Win64. Fix with an explicit cast: `Assert.AreEqual(n, Integer(Length(x)))`. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)

## Encoding

- **Delphi's `TEncoding.UTF8.GetString` raises on byte sequences that aren't valid UTF-8; FPC doesn't.** This is harmless if the data is always text, but dangerous when the data may be binary — for example, arbitrary values stored in Redis, which have no guarantee of being valid UTF-8 text. On Delphi, a binary value received in a pub/sub callback could silently crash the application (an unhandled exception inside the callback), while FPC processed it normally. Fix: use a tolerant, project-specific encoder (e.g. based on `TMBCSEncoding`) instead of `TEncoding.UTF8` directly whenever the data isn't guaranteed to be text. — [`pascal-redis-faa`](https://github.com/fabianoallex/pascal-redis-faa)
- See also, in the main SKILL.md, the "Encoding and accented characters" section about the source-file encoding policy (ASCII vs UTF-8-with-BOM) itself — that's a distinct problem: it's about the `.pas` file, not about runtime data.

## Evaluation order

- **Function-argument evaluation order is not guaranteed left-to-right** (not on Delphi, not on FPC — but this tends to surprise people who assume "like C"). A real bug appeared when building a logging call that had a side effect (e.g. incrementing a counter or consuming a value) in the middle of the argument list — the observed order differed from what the code visually suggested. Avoid relying on side effects inside argument lists; if a side effect needs to happen before a call, put it on its own line. — [`pascal-redis-faa`](https://github.com/fabianoallex/pascal-redis-faa)

## UI / cross-platform (3 axes: compiler × OS × framework)

- **Selecting a UI framework (VCL/FMX/LCL) via nested `{$IFDEF}`**, when a single compiler (Delphi) can target more than one framework:

  ```pascal
  uses
    {$IFDEF FPC}Controls, ExtCtrls, Menus,
    {$ELSE}
      {$IFDEF FRAMEWORK_FMX}
      FMX.Controls, FMX.StdCtrls, ...
      {$ELSE}
      Vcl.Controls, Vcl.StdCtrls, ...
      {$ENDIF}
    {$ENDIF}
    Classes, SysUtils, ...;
  ```

  `FRAMEWORK_FMX` is a project define (`.dproj`) chosen manually per build — not something the compiler sets on its own. — [`opcb-object-pascal-component-builder`](https://github.com/fabianoallex/opcb-object-pascal-component-builder), `src/OPCB.pas`

- **In builds targeting 3 platforms (Windows/Linux/Android), the order of platform `{$IFDEF}`s matters**: Delphi also defines `POSIX` when compiling for Android, so testing `POSIX` before `ANDROID` would misclassify an Android build as "generic Unix." The rule used: test and define the more specific case (`_ANDROID`) first, and make the generic case (`_POSIX`) explicitly exclude the case already handled. See also the equivalent note in "The compatibility `.inc` file" in the main SKILL.md. — [`pascal-pipes-faa`](https://github.com/fabianoallex/pascal-pipes-faa), `src/pipes.inc`
- Practical consequence of the Android axis: Android's `addrinfo` (bionic libc) has its fields in a different order than glibc's (`ai_canonname` before `ai_addr`) — a generic `addrinfo` struct written with Linux/glibc in mind reads the wrong fields on Android. The Android backend uses the Delphi RTL's `Posix.NetDB` instead of a generic struct for this reason.
