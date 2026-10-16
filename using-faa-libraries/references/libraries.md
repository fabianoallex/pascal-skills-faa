# Each library: where to read, and what bites

For each library, the doc to read before writing code with it, then the few rules that caused
real trouble. The docs hold the API and the details; read them in the submodule or on GitHub
(`https://github.com/fabianoallex/<repository>`). Versions in parentheses are the first that
have the behavior: check the copy in use.

## pascal-common-faa

**Read:** `README.md` ("Contents"), `docs/gotchas.md`, and `docs/migrating.md` ("Behavior to know
about", which is for users too).

- Optionals: `IOptXxx` (absent or a value), `INullXxx` (null or a value), `IOptNullXxx` (all
  three, a PATCH). The same type goes from the JSON DTO to the database parameter unchanged.
  Choosing one: pascal-db-faa `docs/optionals.md`; pascal-api-infra-faa `docs/guide/dtos-json.md`,
  step 3.
- `SafeWriteln`, `PcPool`, shutdown, `PcProcessorCount`, spans, metrics: `runtime.md` in this
  skill.
- On FPC for Unix, the program needs `cthreads` first: `PascalCommon.ThreadPool` starts threads.

## pascal-jsonmapper-faa

**Read:** `README.md` ("Contract"), `docs/converters.md` for a type of your own, and
`samples/01-basics`.

- **Only `published` properties, under `{$M+}`.** FPC 3.2.2's RTTI doesn't see `public` ones, and
  Delphi ignores them too, to keep both sides equal: a public property is neither read nor
  written.
- **An API sets `UnknownMembers := umError`**: a typo in a member name becomes a 400 with its
  path instead of a silently ignored value. Duplicate members are always refused (0.4.0+).
- **`EJsonInputError` is the client's fault** (400, a message in JSON terms, safe to return;
  0.5.0+). Any other `EJsonMapperError` is a setup error (500, logged). Invalid JSON text is
  `EJsonParseError`.
- **`null` into a scalar keeps the current value, and an absent member changes nothing.** To tell
  absent, null and a value apart (a PATCH), use pascal-common-faa's optionals and its bridge
  (`PascalCommon.JsonMapper.Optionals`).
- **On FPC, name an array type before using it as a generic argument**
  (`TProductArray = TArray<IProduct>`): `Serialize<TArray<IProduct>>` doesn't parse, because `>>`
  reads as `shr`.
- **`Currency` is exact on FPC only from 0.6.0.** Before that, on Win64, `123456789012345.6789`
  came back as `...6768` (measured over HTTP, pascal-api-infra-faa's `POST /prices`).
- Register mappings at startup, then use the mapper from any thread. Class-typed properties are
  never created: reading fills the instance the property already holds.

## pascal-db-faa

**Read:** `docs/README.md` (the guides, in order: getting started, SQL by key, optionals,
migrations, the mock, errors, the pool, adapters). Then the sample closest to the task
(`samples/01-mock-repository` to `06-json`). `docs/gotchas.md` has 49 numbered items, many per
driver: search it for the database and adapter in use before blaming the library.

- **Hold reference-counted objects in interface variables**: the mock as `IDBFactory` (never
  `Free` it; `docs/testing-with-the-mock.md`, "Lifetime"), and `IDatabaseConfig` likewise.
  Mixing a class variable with the interface frees the object early.
- **`Rollback; raise;`** in a transaction's `except`. Without the `raise`, the client gets a
  success for undone work. Without the `Rollback`, the transaction stays open on a pooled
  connection. Source: pascal-api-infra-faa `docs/guide/database.md`, Pitfalls.
- **Behavior differs per adapter** (`docs/adapters.md`, "Adapter-specific behavior you may
  notice"):
  - Firebird through Zeos or FireDAC fails at once on a locked row; set `LockTimeoutMs` (gotcha 32).
  - A batch is Array DML on FireDAC and one `ExecSql` per row elsewhere (gotcha 44).
  - MySQL and MariaDB report rows *changed*, not *matched* (gotcha 46).
- **SQLite needs settings for real use**:
  - a busy timeout (gotcha 24);
  - `PRAGMA foreign_keys` (45);
  - a pooled connection after migrations says "schema has changed" (21);
  - a `sqlite3.dll` without column metadata fails (23);
  - FireDAC needs three settings changed (25).

  See also pascal-api-infra-faa `docs/guide/database.md`, "SQLite".
- **The database client library**:
  - the first load in a process wins (gotcha 11);
  - on Windows, a library loaded by full path doesn't find its own dependencies (14);
  - the default names on Linux don't match the runtime packages (27);
  - on Delphi, `ExtractFilePath('C:/libs/x.dll')` is `'C:'` (43).

  See `docs/adapters.md`, "Client libraries".
- **The pool**: size it to the database, not to the threads. A wait that runs out raises
  `EPoolTimeoutException` (capacity, not an outage: that is `EDatabaseUnavailableException`).
  pascal-api-infra-faa answers both with 503. To wait longer, raise `PoolWaitMaxAttemps` instead
  of looping around the acquire (`docs/errors.md`, "Pool timeouts"; `docs/pool.md`).
- **The mock runs no SQL**: tags, wrong parameter names and SQL errors pass unnoticed there. The
  integration tests on a real database cover those (`docs/testing-with-the-mock.md`, "What the
  mock doesn't do").

## pascal-api-infra-faa

**Read:** `docs/guide/README.md` (the index, one guide per topic, each with "Pitfalls"). Start
from `docs/guide/getting-started.md` and copy the closest sample. The `docs/*-design.md` files
are decision records, for why, not for how.

- **JSON out through `TJsonSend.Send`, never `Res.Send(string)`.** On Delphi, accented text
  arrived broken (4 of 65 HTTP checks, Delphi 12 Win32/Win64). The unit tests can't see it.
- **Configure every middleware once, before `Listen`.** On FPC a Horse callback is a plain
  procedure, so each middleware keeps one configuration per process.
- **`TLoggerMiddleware` first** (`runtime.md`: a middleware's exception on FPC).
- **A route that doesn't exist runs the global middlewares twice** (Horse 3.3.12). The library's
  middlewares count it once. A middleware of your own with side effects would run twice
  (`getting-started.md`, Pitfalls).
- **Horse 3.3.3 or later on FPC for Windows**: 3.3.2 doesn't compile there.
- **The client's address is `TClientAddress.Resolve(AReq)`**, with `TClientAddress.ProxyHops`
  set to the proxies in front. Never `AReq.RemoteAddr` (empty with the console provider) or
  `ClientIp` (the address the client wrote). Guides: `observability.md`, step 3;
  `rate-limiting.md`, step 3.
- **Query parameters through `ParseQueryInt`/`ParseQueryStr`**, never `TryStrToInt`. That one
  accepted `$3`, `0x3` and ` 3`, and on FPC wrapped `99999999999` to 1215752191 (`dtos-json.md`,
  step 7).
- **Text length for validation: `PaCharCount`**, not `Length`, which counts bytes on FPC and
  UTF-16 units on Delphi (`openapi.md`, step 5).
- **Multi-tenancy**: every repository query goes through `TTenantFilter.Prepare`. An unbound
  `:TENANT_ID` is a silent 404 on SQLdb/SQLite. The tenant comes only from the token's claim
  (`multitenancy.md`).
- **Metrics**: the route template as the label, a description on every metric
  (`observability.md`, step 7).
- **MCP**: the endpoint registers after every documented route, and the Horse provider must be
  threaded: tool calls come back to the API over HTTP (`mcp.md`).
- **Testing with curl from Git Bash on Windows**: curl.exe gets its arguments in the ANSI code
  page. Put a non-ASCII body or `\u` escapes in a file
  (`printf '{"name":"Macei\303\263"}' > body.json`, then `--data-binary @body.json`). On
  2026-10-15 a test that typed them looked like a mapper bug that wasn't there.
- Cache, queue or IPC inside an API (one client per process, spans, a server that is down):
  `docs/guide/messaging.md`, built from `samples/04-messaging`. Which sibling library for which
  need: `docs/related-libraries.md`.

## pascal-amqp-faa

**Read:** `README.md` (in Portuguese). In particular: "Uso rápido", "Reconexão automática",
"Exceção no callback de consumer", "O callback de consumer precisa sempre terminar sozinho",
"Erros e exceções", "Concorrência e ordenação de mensagens" and "Limitações conhecidas". Samples:
`samples/Retaguarda` (consumer, `--dedicado`), `RetryDlqVcl`, `PublicadorConfiavelVcl`.

- **Ordering is opt-in, and consumer errors go to `OnConsumerError`**: `runtime.md`.
- **`AutoReconnect := True`, and log `OnReconnectError`.** With unlimited attempts, a
  reconnection that never succeeds shows nowhere else. In tests, wait for `OnReconnect`, not
  `IsOpen` (true before the topology is replayed). Unconfirmed deliveries come back after a
  reconnection, so handlers must be idempotent (at-least-once).
- **A queue named by the server (`QueueName = ''`) breaks the replay** after a reconnection.
  Generate the name in the client (`'reply-' + GUID`, exclusive, auto-delete), or use Direct
  Reply-to.
- **A publisher confirm's failure is not an exception**: `WaitForConfirm` returns `False`, or
  `OnConfirm` gets `AAck = False`. A 202 after a plain publish doesn't mean the broker has the
  message. Resending after a reconnection is opt-in (`RepublishUnconfirmedOnReconnect`).
- **The consumer callback must finish on its own**: `Close`/`Free` wait for it with no deadline.
  Don't `Free` the connection from `OnDisconnect`/`OnReconnect`.
- **No transactions (`tx.*`), on purpose**: use publisher confirms.
- **The embedded broker** is a separate package (`pascal_amqp_faa_server`, `src\server`).
  Durability is opt-in (`DataDir`). On a developer machine, port 5672 may already be taken by an
  installed broker or Docker (seen in pascal-dfe-broker): use another one.
- **TLS with OpenSSL** needs the `AMQP_OPENSSL` define and `libssl`/`libcrypto` at run time. On
  Linux with OpenSSL 3, see the `dual-compiler-delphi-lazarus` skill,
  `references/native-library-interop.md`.

## pascal-redis-faa

**Read:** `README.md` (in Portuguese): "Uso", "Pool de conexões", "Timeouts", "Comandos
bloqueantes", "Transações", "Pub/Sub", "Streams e consumer groups". GUI samples: `CacheAsideVcl`,
`LockDistribuidoVcl`, `FilaTarefasVcl` (each also shows the shutdown pattern of `runtime.md`).

- **One `TRedisClient` for the process**, created at startup. Never a `TRedisConnection` shared
  by request threads: one connection runs one command at a time (`messaging.md`, step 2).
- **Using the pool directly: `Release` in a `finally`**, always. At the ceiling, `Acquire` waits
  and then raises `ERedisPoolExhausted`.
- **A timeout or I/O error invalidates the connection, and the command in flight is never
  retried** (`INCR`, `LPUSH` aren't idempotent): the caller decides. A server error
  (`ERedisReplyError`, with `Code`) leaves the connection usable.
- **Blocking commands (`BLPOP`, `XREAD BLOCK`) go through the facade**, which uses a separate pool
  with a longer read timeout. A deadline of 0 waits forever: only in a dedicated thread.
- **Pub/Sub keeps nothing.** `Publish` returning 0 means nobody got it. For messages that must
  survive, use Streams with a consumer group.
- **`MULTI` undoes nothing.** To read, decide and write, use `WATCH` + `TryCommit` in a loop.
- **Binary-safe by contract**: `TBytes` goes as is, and `string` overloads go as UTF-8.
- **A fallback that catches `ERedisException` hides bugs**: catch only the connection's failures
  (not measured; `messaging.md`, step 6). Log keys, not values: Redis values are often tokens.

## pascal-pipes-faa

**Read:** `README.md` (in Portuguese): "Transporte", "Garantias de threading", "Instalação", "API
(resumo)". Talking to another language: `docs/INTEROP.en.md`. The repository is
`pascal-pipes-faa` (formerly `pascal-named-pipes-faa`).

- **Pick the transport by reach**: `ptLocal` (Named Pipe on Windows, Unix socket on Linux; same
  machine), `ptTcp` (network), `ptTls` (untrusted network, optional mTLS). Android (Delphi) has
  no `ptLocal`.
- **Handler exceptions go to `OnError`** (0.2.0+), and the connection stays open: `runtime.md`.
- **Order in `pdmPool` holds only per `AGroupKey`** of `SendBytes`/`SendText`.
- **`ptTls` with OpenSSL** (`-dPIPES_OPENSSL`, the only backend on Linux): missing libraries
  don't stop the build or the start. They show as `EPipeTls` on the first TLS connection.
- **A client that connects and dies before the server accepts it is invisible** (no event).
- A JSON DTO over a pipe: pascal-api-infra-faa `docs/guide/dtos-json.md`, step 10.
