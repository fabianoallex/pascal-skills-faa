# Running as an unattended background service: Windows Service vs systemd

A project whose job is to run unattended in the background (a broker, a poller, anything with a "do work every N seconds" loop) needs a real answer for "how does the OS supervise this, restart it on crash, and let an operator start/stop/check it" — and that answer is inherently OS-specific in a way most of this skill isn't. `pascal-dfe-broker` is the only reference project that needs this, and its structure is worth copying directly: **keep the core dual-compiler, and make OS-native service hosting a thin, deliberately single-platform wrapper around it.**

## The shape: one shared core, two thin hosts

```
src/DFe.Host.Loop.pas       -- TDFeHostLoop: the tick cadence (default 60s, configurable)
src/DFe.Host.Aplicacao.pas  -- TDFeAplicacao: Iniciar/Executar/Parar over TDFeOrquestrador.ExecutarCiclo
hosts/console/               -- dual-compiler (.dproj AND .lpi) -- foreground, logs to stdout
hosts/servico/                -- Delphi-only (.dproj, no .lpi) -- Windows Service (Vcl.SvcMgr), logs to file + Event Log
```

Both hosts call the exact same `TDFeAplicacao`/`TDFeHostLoop` — same `dfe.ini`, same tick behavior, same `ExecutarCiclo`. Only what differs between "a process an operator starts in a terminal" and "a service the OS starts and supervises" is different: logging destination, and lifecycle (a blocking loop vs. the SCM's start/stop callbacks). This mirrors the `pascal-pipes-faa` Android pattern elsewhere in this skill: when a platform axis needs something structurally different, isolate it in its own thin target instead of forcing one shared unit to cover everything.

## Why the Windows Service host is Delphi-only, on purpose

Straight from that host's own header comment: *"um Serviço Windows é uma noção inerentemente Windows, e o Lazarus não tem um `TService` pronto. Quem usa Lazarus/Windows tem o host console."* (A Windows Service is an inherently Windows notion, and Lazarus has no ready-made `TService`. Lazarus/Windows users have the console host instead.) The service host uses `Vcl.SvcMgr.TService` — VCL, Delphi-only, with a `.dfm` service module — and there's no attempt to make it dual-compiler. If a Lazarus/Windows project genuinely needs OS-native service supervision without writing this wrapper, a generic process-to-service wrapper (e.g. NSSM) around the plain console host is the usual alternative — not verified in any reference project here, but a well-known general-purpose option worth knowing about.

The Linux equivalent doesn't need a separate host at all: the same dual-compiler console host runs under a systemd unit (`hosts/console/systemd/dfe-broker.service`) — systemd supervises a plain foreground process directly, no OS-specific wrapper code required. See `references/native-library-interop.md` for the systemd-specific gotchas (stdout buffering, `Now` returning UTC).

## What a Windows Service wrapper actually has to handle differently

- **`ServiceStart` (the SCM's `OnStart`) must not block.** The SCM expects it to return quickly; a 60-second tick loop can't run inline. `pascal-dfe-broker` starts the loop on a dedicated `TThread` (`TDFeExecutorThread.Execute` calling `TDFeAplicacao.Executar`) and returns immediately, catching and logging any exception that escapes the thread so a crash doesn't vanish silently.
- **`ServiceStop` (`OnStop`) should wait for the in-flight unit of work to finish**, not kill it — a SEFAZ query in progress shouldn't be cut mid-request. The project caps this at a constant (`ESPERA_MAXIMA_PARADA_MS = 60000`) and reports back to the SCM that it's still stopping while waiting, rather than blocking indefinitely.
- **No console — log to a file, and send startup failures to the Windows Event Log specifically.** A service that fails to start has nowhere else an operator would think to look; `pascal-dfe-broker` writes daily log files next to the config **and** reports startup failure to the Event Log, since that's where "why won't the service start" gets checked first (Control Panel → Event Viewer → Windows Logs → Application).
- **The working directory of a Windows service is `C:\Windows\System32`, not the executable's folder.** Every relative path in config (`ArquivoPFX`, `PathSchemas`, `CursorPath`, `DataDir`) has to be resolved relative to the config file's own location — not the process's current directory — and the service should always be launched with an absolute `--config` path.
- **A service does not see the interactively-logged-in user's `PATH` — only the system `PATH`.** Native DLL dependencies (OpenSSL, libxml2 — see `references/native-library-interop.md`) that happen to resolve fine when a developer runs the console host from their own shell can fail under the service purely because of this, even with nothing else different. Fix: copy the required DLLs directly next to the service executable rather than relying on `PATH`, and verify with the same environment-check the console host offers (`--verificar-ambiente`) run from that folder specifically.
- **Don't put secrets in the config file.** Prefer an indirection (`SenhaEnv=NAME` pointing at a *system* environment variable set via `setx NAME "value" /M`, not a per-user one) over a certificate password sitting in plain text in an `.ini` that might get committed or copied around.
- **Auto-restart on crash is the OS's job, configured, not code.** `sc.exe failure <service> reset=<seconds> actions=restart/<ms>/restart/<ms>/...` — with a `reset` window so repeated crashes eventually stop retrying instead of looping forever. This is infrastructure configuration, not something the service's own code needs to implement.

## Installing (the real recipe)

```powershell
$exe = 'C:\dfe\DFeBrokerServico.exe'
$ini = 'C:\dfe\dfe.ini'
sc.exe create DFeBrokerService binPath= "`"$exe`" --config `"$ini`"" start= delayed-auto DisplayName= "pascal-dfe-broker"
sc.exe failure DFeBrokerService reset= 86400 actions= restart/60000/restart/60000/restart/60000
sc.exe start DFeBrokerService
```

An `/install`/`/uninstall` pair built into the executable itself (standard `TService` behavior) is the simpler alternative for a first install, but doesn't configure auto-restart — still needs the `sc.exe failure` step afterward.

## Verify with the console host first, always

Before installing the service, run the console host with the exact same config and confirm a clean environment report (`DFeBrokerConsole.exe --config <ini> --verificar-ambiente`) — the service wrapper adds no behavior of its own beyond lifecycle and logging, so anything wrong at that point is a config/environment problem, not a service-specific one, and is far easier to diagnose with a console in front of you.

## Be honest about what's actually verified

`pascal-dfe-broker`'s own docs are explicit about the boundary of what was actually checked: clean start/stop/restart and Event Log reporting on Windows 11 were verified; stopping with a tick genuinely in progress, running under a dedicated `NT SERVICE\...` account, and anything involving a real certificate against the real SEFAZ were not. Copy that discipline — "the service installs and starts" is not the same claim as "the service has been exercised under real failure conditions," and a skill (or a README) should say which one it's making.
