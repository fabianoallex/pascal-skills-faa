# RTL gotcha catalog: Delphi vs FPC

Each item below is a real case, found in one of the reference projects, with the observed symptom, the root cause, and the fix that was used. When investigating a behavior that diverges between Delphi and FPC, check the closest matching category here first — there's a good chance it's already been cataloged.

If you find a new gotcha that isn't listed here, it's worth adding it in this same format (symptom → root cause → fix), and also to the `CLAUDE.md` of the project where it was found — that's how these lists grew in the original projects.

## Threading / interop

- **`IInterface` calling convention depends on platform in FPC**: `stdcall` on Windows, `cdecl` on Unix. A COM-like interface that assumes a fixed `stdcall` breaks silently (or fails to compile) on FPC's Unix side. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`TThread.WaitFor` is not idempotent on FPC/Unix**: calling `WaitFor` more than once triggers a second, unconditional `pthread_join`, which can hang or behave differently from Delphi (where calling it again is safe). Guard with a "have I already waited for this thread" flag if the code may call `WaitFor` more than once. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **Delphi's default RTTI only publishes `public`/`published` methods**: a test method (e.g. DUnitX's `[Test]`) declared in a `private` section compiles without error but is never discovered/run, with no warning from the framework. Symptom: "the test disappeared", a lower test count than expected. Always check `public`/`published` visibility on methods decorated with test attributes. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`Halt` leaks managed local variables**: `Halt` doesn't normally run pending `finally`/destructor cleanup on the stack, so local strings/interfaces/dynamic arrays can leak. If the process needs to exit early cleanly, prefer signaling and letting normal flow wind down, or free things manually before `Halt`. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`SIGPIPE` kills the process on Linux without `MSG_NOSIGNAL`**: writing to a socket whose peer already closed the connection raises `SIGPIPE`, which by default kills the whole process on Linux (unlike the more commonly-seen "silent" behavior on Windows). Use `MSG_NOSIGNAL` on the send call, or explicitly ignore `SIGPIPE` at the process level. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)
- **`TThread.Synchronize`/`.Queue` have nothing to run on in a plain console app**: both marshal the call onto the main thread via the VCL/LCL message queue, which is only pumped by `Application.ProcessMessages`/`Application.Run` or a manual `CheckSynchronize` loop. A console app (no `Forms`/`Application` unit) has neither, so a worker thread calling `Synchronize`/`Queue` can block indefinitely or the call may simply never run — with no error raised. This is easy to reach for by instinct (e.g. to log from a worker thread) and it isn't obviously wrong until it hangs. Fix: don't route console-app cross-thread work through `Synchronize`/`Queue` at all — protect the shared resource (e.g. console output) with a `TCriticalSection` and access it directly from the worker thread instead. — [`pascal-skills-threads`](https://github.com/fabianoallex/pascal-skills-threads), `src/MultiDownloader.SyncConsole.pas`
- **There's no ready-made replacement for `TTask.Run`/a worker pool** — the RTL gotcha table says "use dedicated work items" but that's an instruction, not a pattern. See `references/threading-worker-pool.md` for a concrete lock-protected-queue-plus-`TThread`-workers example instead of re-deriving it per project.

## Networking / HTTP client

- **No dual-compiler HTTP client is a clean fit for every case — pick one and document the trade-off.** Indy (`TIdHTTP`) ships with Delphi but is **not enabled by default in a clean Lazarus install** (its Lazarus package has to be installed first). `TFPHTTPClient` (`fphttpclient`) is FPC-only, no Delphi equivalent. Binding directly to `wininet.dll` (`external 'wininet.dll'`) compiles and runs unmodified on both compilers with zero extra packages — Windows handles HTTPS via Schannel/the system certificate store — but restricts the project to Windows only. There's no universal answer; decide and document it the same way as the encoding decision below. — [`pascal-skills-threads`](https://github.com/fabianoallex/pascal-skills-threads), `src/MultiDownloader.Http.pas`

## Sockets / timeout

- **Delphi's `TSocket.ReceiveTimeout`/`SendTimeout` only take effect if assigned while the socket is already connected**: Delphi's implementation pushes the timeout onto the real socket inside `CreateSocket`, at a point where the handle may still be invalid — assigning the timeout before connecting has no effect. Symptom: "FPC honors the timeout correctly, but Delphi waits for the entire command (or hangs) even with a timeout configured." Fix by re-assigning the timeout *after* the socket is connected. — [`pascal-redis-faa`](https://github.com/fabianoallex/pascal-redis-faa)
- **Without `TCP_NODELAY`, Nagle's algorithm plus delayed ACK costs ~40ms per round-trip on Linux (up to 200ms on Windows outside loopback) for a small-frame request/response protocol — and testing over Windows loopback hides it completely.** A 457-test server suite dropped from 12m59s to 50s on Linux/Docker after setting `TCP_NODELAY` on every socket at connect and accept. Don't trust a fast Windows-loopback run to represent Linux or real-network behavior for latency-sensitive request/response protocols. — [`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)

## Files / operating system

- **`SysUtils.RenameFile` does not overwrite an existing destination on Windows** — neither on Delphi nor on FPC. If the use case needs to overwrite, call `MoveFileEx` with the `MOVEFILE_REPLACE_EXISTING` flag directly, behind `{$IFDEF <YOUR_DEFINE>_WINDOWS}`. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker), unit `src/DFe.CursorStore.Arquivo.pas`
- **`MOVEFILE_WRITE_THROUGH` doesn't exist in FPC 3.2.2's `Windows` unit** — only `MOVEFILE_REPLACE_EXISTING` is available there. If the actual use case needs write-through semantics, declare the constant manually (the Windows API's numeric value is stable) instead of assuming it's in the standard unit. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)

## Config / parsing

- **Delphi's `TCustomIniFile.ReadBool` doesn't understand `"true"`/`"false"` as text** — Delphi's implementation delegates to `StrToIntDef`, so it only recognizes `"0"`/`"1"` (and numeric variants). FPC understands `"true"`/`"false"` as text. This is a real bug that passed 52 green tests on FPC before showing up only when running on Delphi — a good reminder that "it passed on FPC" isn't enough (see the mirrored-tests section in the main SKILL.md). Fix: write a project-specific boolean-parsing function that accepts both formats, instead of relying on `ReadBool`. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker), see `DFe.Config.LerBooleano` in `src/DFe.Config.pas`

## Memory / interfaces

- **An object constructed inline as an interface-typed argument, in a call that raises an exception, leaks one block on FPC 3.2.2** (caught via heaptrc): writing something like `Foo.Bar(TMyObject.Create)` where `Bar` raises before the interface takes ownership of the object can leave the temporary object unfreed on this FPC version. Fix: assign the object to a local variable (of the interface type) before passing it into the call, instead of constructing it inline. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)

## Generics / RTL collections

- **`TDictionary<K,V>.Create(AComparer)` with `AComparer = nil` crashes on FPC 3.2.2, but not on Delphi.** Symptom: `EAccessViolation` in `FindBucketIndex` (`generics.dictionaries.inc`) on the first `Add`/`TryGetValue` — in `pascal-db-faa` this single cause took down 30 of 158 tests at once, all through a cache class that forwarded an optional comparer parameter (`const AComparer: IEqualityComparer<K> = nil`) straight into the dictionary constructor. Root cause: Delphi's `TDictionary` replaces a `nil` comparer with `TEqualityComparer<K>.Default`; FPC's `rtl-generics` stores the `nil` as-is and later calls `GetHashCode` on it. Fix: never forward a possibly-`nil` comparer — `if Assigned(AComparer) then FMap := TMap.Create(AComparer) else FMap := TMap.Create;`. Worth grepping for in any code that wraps a generic collection and exposes an optional comparer. — `pascal-db-faa` (not yet public), `src/PascalDb.ClockCache.pas`
- **`IEqualityComparer<T>` has a different signature, and `TEqualityComparer<T>.Construct` takes different callable types.** FPC's `rtl-generics` declares `Equals(constref ALeft, ARight: T): Boolean` and `GetHashCode(constref AValue: T): UInt32`; Delphi uses `const` and an `Integer` hash. `Construct` accepts `reference to function` closures on Delphi, but on FPC 3.2.2 only a plain function pointer or an `of object` method (no anonymous functions in the stable compiler) — so the idiomatic Delphi `TEqualityComparer<TKey>.Construct(function(const L, R: TKey): Boolean begin ... end, ...)` doesn't compile on FPC. Fix: a **named** standalone function passed to `Construct` compiles on both (Delphi accepts a named function where it expects `reference to`), with the parameter modifier and hash type under `{$IFDEF FPC}`: `function KeyHash({$IFDEF FPC}constref{$ELSE}const{$ENDIF} V: TKey): {$IFDEF FPC}UInt32{$ELSE}Integer{$ENDIF};`. `BobJenkinsHash` exists in both RTLs with the same signature. — `pascal-db-faa` (not yet public), `src/PascalDb.Optionals.pas` (`SingleKeyEquals`/`SingleKeyHash`)
- **Generics themselves are not the problem under `{$MODE DELPHI}` on FPC 3.2.2.** Generic interfaces with GUIDs (`IOptional<T> = interface ['{...}']`), classes inheriting from a specialized generic (`TOptNullString = class(TOptionalNullable<string>, ...)`), generic methods with interface constraints resolving `TypeInfo(I)`'s GUID, and `Generics.Collections` all compiled and behaved identically in `pascal-db-faa` without `generic`/`specialize` keywords. The divergences were in the *collection library's* behavior (the two items above), not in the language feature — so a project that uses generics doesn't have to switch to `{$mode objfpc}`, but should test collection edge cases (nil comparers, custom comparers) on both sides.

## Types

- **`Length()` of a dynamic array is `NativeInt` on Delphi Win64** (but `Integer`/`LongInt` on other compiler/platform combinations). Comparisons or generic calls that explicitly assume `Integer` (e.g. `Assert.AreEqual(n, Length(x))` where `n: Integer`) may fail to compile on Win64. Fix with an explicit cast: `Assert.AreEqual(n, Integer(Length(x)))`. — [`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)
- **`TGuid.Empty` doesn't exist on FPC 3.2.2** — it comes from Delphi's `TGuidHelper` record helper. Symptom: `identifier idents no member "Empty"`. Fix: a typed constant, which works on both: `const EMPTY_GUID: TGUID = '{00000000-0000-0000-0000-000000000000}';`. — `pascal-db-faa` (not yet public), `src/PascalDb.Optionals.pas`

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

## Resource files

- **A `.dpr` and a `.lpr` with the same program name, in the same folder, silently overwrite each other's `.res`.** `{$R *.res}` in each resolves to the identical `<program>.res` file, and both IDEs freely regenerate it on their own build (Delphi writes MAINICON/version info; Lazarus regenerates from the `.lpi`'s manifest/icon settings) — so building one compiler clobbers the resource the other one just wrote, with no warning from either side. Symptom: an icon, manifest, or version-info change made in one IDE "disappears" after building in the other. Fix: give the two program files different names (e.g. `MyApp.dpr` / `MyAppLCL.lpr`) and, if the executable name needs to stay identical, set `<Target><Filename Value="MyApp"/></Target>` in the Lazarus side's `.lpi` — the program name and the output filename don't have to match. — [`opcb-object-pascal-component-builder`](https://github.com/fabianoallex/opcb-object-pascal-component-builder) dodges this with its `no-dfm` example's `DelphiProject.dpr`/`LazarusProject.lpr` naming, though without documenting why; confirmed as a real, hit-in-practice collision building [`pascal-snake`](https://github.com/fabianoallex/pascal-snake) with this skill.
- **Loading an embedded `RCDATA` resource: `FindResource`/`TResourceStream` are portable, but `RT_RCDATA` isn't where Delphi code expects it.** On Delphi it comes from `Winapi.Windows`; on FPC 3.2.2 it's declared in the `system` unit only for non-Windows targets (`rtl/inc/resh.inc`), and on Windows it lives in FPC's own `Windows` unit — so code that drops `Winapi.Windows` for FPC gets `Identifier not found "RT_RCDATA"` on Windows. Fix: a local constant with the same value on every platform, `SQL_RESOURCE_TYPE = {$IFDEF FPC}PChar(10){$ELSE}RT_RCDATA{$ENDIF};` (`MAKEINTRESOURCE(10)`), with `Winapi.Windows` only under `{$IFNDEF FPC}`. This covers *reading* the resource; *producing* it differs too (`brcc32` is Delphi-only; FPC uses `fpcres`/`windres`), which is a build-pipeline decision, not an RTL one. — `pascal-db-faa` (not yet public), `src/PascalDb.SqlLoader.pas`
