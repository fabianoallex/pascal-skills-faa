# Native library interop on Linux: OpenSSL, libxml2, and the FPU

FPC on Linux talks to native C libraries (OpenSSL, libxml2) far more directly than Delphi on Windows typically does, and that surfaces a cluster of gotchas that never show up on Windows — "it compiles and passes on Windows" is not evidence about Linux here. Everything below is from
[`pascal-dfe-broker`](https://github.com/fabianoallex/pascal-dfe-broker)'s `docs/linux.md` (a Brazilian fiscal-document broker that signs and validates XML against native OpenSSL/libxml2 on Debian 12) and
[`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)'s `CLAUDE.md` (its own OpenSSL TLS backend, used cross-platform).

## OpenSSL 3.0's default provider isn't active by default

On Debian 12 / Ubuntu 22.04 (OpenSSL 3.0), `OSSL_PROVIDER_available('default')` returns `0` in the process, and **every** PKCS12 operation fails as a result: `PKCS12_parse` returns 0 with an opaque `digital envelope routines::unsupported / key gen error / mac generation error`. The practical symptom: loading a client certificate (`.pfx`/`.p12` — exactly what a Brazilian NFe A1 digital certificate is) fails with a generic "couldn't read certificate information" error, even though the same file loads fine via the `openssl` CLI and nothing about the `.pfx` itself is wrong (verified across MAC SHA1/SHA256 and 3DES/AES variants — none of that was the cause). Neither does calling `OPENSSL_init_crypto` with cipher/digest flags fix it. **The only fix that worked: explicitly call `OSSL_PROVIDER_load(nil, 'default')`** before any PKCS12 operation. Windows doesn't need this (OpenSSL 3.2/3.5 there already ships with the provider active) — it's Linux-distro-specific, which is exactly the kind of thing "works on Windows" hides.

`pascal-dfe-broker` centralizes this in one place (`DFe.Ambiente.ACBr`, the environment checker called before using the client) and activates the provider whenever the detected OpenSSL version is ≥ 3.0. If a project loads certificates on Linux at all, this needs to happen exactly once, early, not per-call.

## FPC leaves FPU exceptions enabled; native C libraries trip them

FPC does not mask floating-point exceptions by default, and native C libraries (libxml2, OpenSSL) perform floating-point operations that trigger them. The concrete symptom in `pascal-dfe-broker`: simply *initializing* libxml2 crashed the process with `EInvalidOp: Invalid floating point operation` — nothing to do with the project's own arithmetic. Fix: mask FPU exceptions for the current thread before calling into the native library (`DFe.Ambiente.ACBr.PrepararParaBibliotecasNativas` in that project), called from the client's constructor, before every operation, and from the environment checker. **The mask is per-thread** — a multithreaded host must call this in every thread that touches the native-library-backed client, not just once at startup.

## Dynamic loading with a soname fallback list, not a hard link-time dependency

Both `pascal-dfe-broker` and `pascal-amqp-faa`/`pascal-redis-faa` avoid linking against a specific OpenSSL `.so` version at compile time — they load it dynamically at first use, trying a list of sonames in order (`libssl.so.3` → `libssl.so.1.1`, and the matching Windows DLL names like `libssl-3-x64.dll`). This is what lets the same binary run across OpenSSL 1.1.1 and 3.x without a recompile, and it's why `pascal-dfe-broker`'s integration executable "links only against libc" — libssl and libxml2 are resolved at runtime, not at link time. If a project needs OpenSSL on Linux, prefer this pattern (a small list of known sonames, tried in order, with a clear error if none load) over a hard compile-time link.

`pascal-amqp-faa`'s OpenSSL TLS backend (`AMQP.Transport.OpenSSL`, opt-in via `-dAMQP_OPENSSL`, alongside a Windows-only SChannel backend in `AMQP.Transport.Tls` that needs no extra define) adds one more real detail worth knowing if a project layers TLS over its own socket abstraction: the SSL engine talks to a **pair of in-memory BIOs**, never `SSL_set_fd` directly. That preserves the ability to unblock a reader thread by closing the socket (closing the fd doesn't unblock a blocking OpenSSL read the way it does for a plain socket read) while still allowing the `SSL` object — which doesn't tolerate concurrent read/write — to be protected by a critical section that's never held during actual socket I/O.

## `libxml2.so` (unversioned) has to exist, and only the `-dev` package provides it

On Debian/Ubuntu, the runtime package only installs `libxml2.so.2`; a library that does `dlopen`-style loading by the exact name `libxml2.so` (no version suffix) fails unless the `libxml2-dev` package is installed, or a symlink is created by hand (`ln -s libxml2.so.2 libxml2.so`). `pascal-dfe-broker` confirmed the exact failure mode: without the link, the client refuses to start with `EDFeAmbienteIndisponivel` naming the missing file and the fix. If a project's Linux deployment doc doesn't call this out explicitly, whoever provisions the box will hit it once and have no idea why a valid runtime install "doesn't work."

## `Now` returns UTC on FPC 3.2.2 on Linux, regardless of the system timezone

Measured across four different `TZ`/`/etc/localtime` settings (UTC, `America/Sao_Paulo`, `America/Manaus`, `America/Noronha`) in Debian 12 under Docker: FPC 3.2.2's `Now` always returned UTC on Linux, ignoring the configured system timezone entirely. `pascal-dfe-broker` hit this formatting a timestamp (`dhEvento`) that Brazilian fiscal rules require in a specific fixed offset (`-03:00`) — the broker had been trusting `Now` to already reflect local time and was silently emitting `+00:00`, outside the set of offsets Brazilian tax authorities accept. Fix: don't rely on `Now` for "local time" on Linux in FPC 3.2.2 — compute the target offset explicitly instead of trusting the system/libc timezone database to be reflected in it.

## stdout is buffered when it isn't a terminal — logs arrive late, or are lost on a crash

Running a console host under systemd (stdout captured by the journal, not a TTY), FPC buffers output — log lines show up in `journalctl` late, and any lines still in the buffer at the moment of a crash or kill are lost entirely. `pascal-dfe-broker`'s console host now calls `Flush` after every log line to make this non-issue. Worth checking for any dual-compiler service meant to run headless under systemd (or any non-interactive supervisor) on Linux.

## Related: networking behavior that also only shows up on Linux

Not native-library interop, but discovered through the same "Windows hides it" pattern: Nagle's algorithm/`TCP_NODELAY` costs real per-request latency on Linux in a way a Windows-loopback test run won't reveal. See the "Sockets / timeout" section of `references/rtl-gotchas.md`.
