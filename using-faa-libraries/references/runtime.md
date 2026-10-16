# Running an application on the `*-faa` libraries

Threads, shutdown, logging, errors and tracing, where the libraries meet inside one process.
Each point says where it was measured; the library docs named hold the details.

## Console and log output: `SafeWriteln` in UTF-8

In a program with threads, or whose standard output is redirected (Docker, systemd, a Windows
service, `> log`), `Writeln` fails in three different ways:

| Symptom | Where | Measured |
|---|---|---|
| Lines cut and mixed, even with every `Writeln` inside one lock | FPC, stdout to a file or pipe | 2,165 of 16,000 lines corrupted, 8 threads (gotcha 8) |
| The last line stays cut (`...,"dur`) until more output comes; lost if the process dies | Delphi on Windows, stdout to a file or pipe | pascal-api-infra-faa's access log, Delphi 12 Win32/Win64 (gotcha 9) |
| Accented letters in the console's code page (`é` as `0x82`, cp850) or ANSI, not UTF-8 | Windows, both compilers | sample 04's log (gotcha 11) |

**Fix:** call `PcSetSafeLogUtf8(True)` at startup (pascal-common-faa 1.10.0+) and write every line
through `SafeWriteln` (`PascalCommon.SafeLog`). It writes the line under a lock and flushes it.
On a file or a pipe it writes UTF-8, and on a console it writes UTF-16 (`WriteConsoleW`) without
changing the console's code page. A plain `Writeln` in the same program keeps the old behavior,
so don't mix them.

Source: pascal-common-faa `docs/gotchas.md`, 8, 9 and 11.

## `PcPool` is shared by the whole process

`PcPool` (`PascalCommon.ThreadPool`) is created in that unit's initialization and shared by every
library in the process:

- amqp's consumer callbacks on a plain channel run on it;
- pipes' `pdmPool` handlers run on it;
- redis's GUI samples use it.

Its ceiling is `max(16, 4 × cores)`, shared by everyone.

- **Work that may block (I/O, user callbacks) can go on `PcPool`. Work that another thread waits
  for synchronously goes on a `TPcThreadPool` of its own.** One library's slow callbacks become
  another's timeouts. Measured in pascal-amqp-faa's migration, with `PcPool` saturated: with the
  broker's queue actors on `PcPool`, `Queue.Declare` waited its full 15 s and the connection
  dropped. On a pool of the broker's own, it took 26 ms.
- **An AMQP consumer that must stop on time uses `CreateChannel(True)`.** A channel's
  `Close`/`Free` waits for its deliveries **from the moment they are queued**, with no deadline,
  on purpose. With `PcPool` busy elsewhere, freeing a channel waited 1.5 s; with
  `CreateChannel(True)` (a thread of its own), 29 ms. Source: pascal-amqp-faa README, "O callback
  de consumer precisa sempre terminar sozinho".
- **Cores: `PcProcessorCount`, never `TThread.ProcessorCount`**, which is always 1 on FPC outside
  Windows (gotcha 7: `nproc` 12, RTL 1). It counts CPUs, not a container's quota. On FPC for macOS
  and the BSDs it is still 1: pass `AMaxWorkers` there.

Source: pascal-common-faa `docs/migrating.md`, "Behavior to know about".

## Shutdown: wait for your own items

Units are finalized before `PascalCommon.ThreadPool`, so `PcPool` is still running your items when
your finalization frees things. And **`TPcThreadPool.Destroy` runs every queued item before
returning**: don't rely on queuing a "stop" item to a pool that is being destroyed.

- **An object whose work runs on `PcPool` waits for its own items before it is freed.**
  - Count each item from the moment it is queued, not from when it starts.
  - Decrement in the work item's **destructor**: it also runs when the pool frees an item without
    running it.
  - In the owner's `Destroy`, poll that atomic counter down to 0, with a deadline. Don't wait on
    an event the item signals: the item's last act would touch an object being freed.

  Measured in pascal-pipes-faa's migration: freed too early, 0 of 15 items ran, 6 blocks leaked.
  See `Pipes.Threading` (`TPipeMailboxDrainWork.Destroy`, `TPipeKeyedDispatcher.Destroy`).
- **A VCL or LCL form (or data module) that queues work waits in `OnCloseQuery`.** `Application`
  frees its forms before any unit finalization, so waiting later is too late. Measured in
  pascal-redis-faa's migration: a stream consumer woke 2.6 s after `FormDestroy`, with exit code
  0, and heaptrc didn't flag it.
  - Each item counts itself on the form from its constructor to its destructor.
  - While waiting, pump `CheckSynchronize(10)`, not `Sleep(10)`.
  - Count the `TThread.Queue` marshals an item posts too: create and count the marshal before the
    item uncounts itself. An item that only posts a marshal still causes a use after free.
  - **On FPC, `PcPool`'s finalization pumps leftover marshals**: `TThread.WaitFor` from the main
    thread runs `CheckSynchronize`, so a marshal left behind runs against the freed form. Measured
    in pascal-dfe-broker (F10): an access violation with a stack through `TPcThreadPool.Destroy`,
    or a heaptrc leak when it didn't run.
  - A work item never reads a control. On LCL, `TEdit.Text` from a worker is a cross-thread
    `SendMessage` to the UI thread, which is the thread waiting for the item.

  Worked examples: `docs/DECISOES.md` §50 and the GUI samples in pascal-redis-faa;
  `exemplos/consumidor/pascal/ConsumidorDFeVcl` in pascal-dfe-broker, with its
  `prova/ProvaFechamento` harness.

Source: pascal-common-faa `docs/migrating.md`, "Behavior to know about"; pascal-dfe-broker
`.ci/f10-findings.md`, finding 1.

## Every receiver handles its own errors

An exception that escapes a callback the library calls on a pool thread has nowhere to go unless
the application gives it a handler:

- **pascal-amqp-faa (0.4.0+):** an exception in a consumer callback goes to
  `Chan.OnConsumerError`. If the delivery isn't settled yet, the library `Nack`s it without
  requeue: the message goes to the queue's dead-letter exchange, or is **dropped** when there is
  none.
  - Assign the handler and log there (since 0.4.1 it runs inside the message's `process` span,
    so the log carries its trace id).
  - Give the queue a dead-letter exchange where a message must not be lost.
  - Until 0.3.0 the exception was swallowed and the delivery stayed unacknowledged. Measured
    against RabbitMQ 3: 1 callback in 8 s, and with `Qos(1)` the consumer stopped.
- **pascal-pipes-faa (0.2.0+):** an exception from any handler (`OnMessage`, `OnConnected`, ...)
  goes to the same component's `OnError`, on the same thread. The connection stays open: closing
  it is the application's decision (`DisconnectClient(AConnId)`). `OnRequest` is the exception
  to the rule: its exception becomes an error reply. Until 0.1.1 it was lost silently. Decide by
  the exception's class (`EPipeClosed`, `EPipeTimeout`, ...), not its text, which changed to
  English in 0.3.0.
- **pascal-api-infra-faa:** a handler's exception reaches `THorse.OnError` on both compilers. A
  *middleware's* exception never does on FPC: Horse 3.3.12's FPC router re-raises it, and fpWeb
  answered `500 text/html` with the message and stack addresses (measured 2026-10-14).
  `TLoggerMiddleware` catches it and answers through the error handler, so **it must be the first
  middleware** (guide `observability.md`, Pitfalls; `errors.md`, step 5).

Sources: pascal-amqp-faa README, "Exceção no callback de consumer"; pascal-pipes-faa README,
"Garantias de threading"; pascal-api-infra-faa `docs/guide/messaging.md` and `dtos-json.md`,
Pitfalls.

## Order of messages is opt-in

pascal-amqp-faa dispatches each delivery to the pool as an independent item: **two deliveries of
one consumer can finish out of order.** That is by design: parallel by default, ordered by
opt-in.

When order matters, use one of these:

- `Qos(1)` with the `Ack` at the end of processing, which serializes the consumer;
- `CreateChannel(True)`: one thread for the channel, with the network flow unchanged;
- a queue of the application's own.

pascal-pipes-faa in `pdmPool` orders only within an `AGroupKey`.

Measured in a real consumer: pascal-dfe-broker's command source consumed on a plain channel and
kept its order by luck. pascal-common-faa 1.1.3 made the pool grow in a burst, and commands came
out of order. Fixed with `CreateChannel(True)`, and its test caught the mutant 9 times in 10
(`.ci/f10-findings.md`, finding 7). The rule it adopted: **every consumer that depends on order
uses `CreateChannel(True)` or `Qos(1)`.**

Two traps with an application queue: `ADelivery.Properties.Headers` is freed when the callback
returns, so copy what you need first. And `Channel.Close` doesn't know about your queue, so drain
it before closing.

Source: pascal-amqp-faa README, "Concorrência e ordenação de mensagens".

## Tracing and metrics across the libraries

- **Spans are pascal-common-faa's** (`PascalCommon.Tracing`: `TPcTracing`, `IPcSpan`, 1.7.0+).
  Libraries instrument with `StartSpan` and need no exporter. pascal-db-faa's statements,
  pascal-redis-faa's commands and pascal-amqp-faa's publish/process join the same trace.
- **The exporter is pascal-api-infra-faa's** (`PascalApi.Otlp`, OTLP/HTTP). It is checked in CI
  against a real OpenTelemetry Collector.
- **`TPcTracingOptions.FromEnvironment` reads only the process environment.** To honor a `.env`
  file, pass pascal-api-infra-faa's `ReadAppConfig` (`PascalApi.Config`). Source:
  pascal-api-infra-faa `CLAUDE.md`, "Observability".
- **Metrics are pascal-common-faa's** (`PascalCommon.Metrics`, `PcMetrics`), named as OpenTelemetry
  names them and served as Prometheus text.
  - Every metric needs a description: `promtool check metrics` fails on "no help text".
  - Never put a raw path or an id in a label; use the route template.
  - See pascal-api-infra-faa's guide `observability.md`, step 7 and Pitfalls.

Guides: pascal-api-infra-faa `docs/guide/observability.md`; `docs/guide/messaging.md`, step 5
("one trace through Redis and the broker").

## A DTO on a queue or a pipe

The same DTO and mapper as in the HTTP API. Publish **bytes, with `application/json`**:
pascal-amqp-faa's `PublishText` labels the message `text/plain`. Source: pascal-api-infra-faa
`docs/guide/dtos-json.md`, steps 8 to 10.

## Upper and lower case on FPC for Linux

`AnsiUpperCase('são paulo')` gives `'SãO PAULO'` on FPC/Linux when the process has no `LANG`
(the locale "C", common in containers). It gives the right result on Delphi and FPC/Windows.
Measured with the same binary with and without `LANG` (gotcha 10). Use pascal-common-faa's
`TOptionals.Upper`/`Lower` (1.9.0+), or `Character.ToUpper`/`ToLower` on a `UnicodeString` on FPC.
