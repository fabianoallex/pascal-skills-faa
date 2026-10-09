# Ready-made dual-compiler libraries (the `*-faa` family)

Before writing infrastructure in a new Delphi + Lazarus/FPC project — JSON, database access, an
HTTP API layer, hashing, threading, messaging — check this table. Each library below already
compiles and passes its tests on both compilers (FPC 3.2.2 and Delphi 12; see each README for
the exact targets verified), and paid the dual-compiler cost this skill catalogs. Reusing one is
cheaper than re-deriving it, and two copies of the same thing in two libraries drift apart.

All are public on GitHub under MIT, by the same author, `{$MODE DELPHI}`. A consumer takes each
one as its **own** git submodule (one copy per application, even when several libraries depend on
it), never through another library's `external/` folder.

## By need

| Need | Library | Where | Notes |
|---|---|---|---|
| Optional/nullable values (`IOptXxx`, `INullXxx`, `IOptNullXxx`) | pascal-common-faa | `PascalCommon.Optionals` | the shared types: a DTO from JSON goes to the DB layer as is |
| Atomics, monotonic time (`TInterlocked`/`TStopwatch` don't exist on FPC) | pascal-common-faa | `PascalCommon.Threading` (`PcAtomic*`, `PcTickMs/Us`) | |
| Thread pool, lock + condition variable | pascal-common-faa | `PascalCommon.ThreadPool` (`TPcThreadPool`, `TPcMonitor`) | see also `threading-worker-pool.md` |
| Replaceable clocks and sleep, for tests | pascal-common-faa | `PascalCommon.SystemContext` (`TClock`, `TTicker`, `TSleep`) | |
| Thread-safe fixed-size cache | pascal-common-faa | `PascalCommon.ClockCache` | |
| Console output from several threads | pascal-common-faa | `PascalCommon.SafeLog` (`SafeWriteln`) | |
| JSON ⇄ objects/DTOs, JSON DOM, exact float text | pascal-jsonmapper-faa | `PascalJsonMapper.Mapper`, `PascalJsonMapper.Json` | maps **published** properties only (FPC's RTTI); optionals through pascal-common-faa's bridge |
| Database access: contracts, pool, transactions, migrations, tagged SQL, paging, batches, mock | pascal-db-faa | `PascalDb.*` | adapters: SQLdb (FPC), FireDAC (Delphi), Zeos (both); Firebird, PostgreSQL, SQLite, MySQL/MariaDB, SQL Server |
| REST API on Horse: error handler, CORS, request log, Bearer/JWT auth, rate limit | pascal-api-infra-faa | `src/horse/PascalApi.Horse.Middlewares` | one configuration per middleware per process (Horse's FPC callbacks are plain procedures); request log with the W3C trace id as `X-Request-Id`, `traceparent` for the handler, text or JSON lines (0.8.0+); HTTP server metrics on `/metrics` (Prometheus) and `/health/live`/`ready` (0.9.0+, `PascalApi.Horse.Observability`); spans to an OpenTelemetry collector over OTLP/HTTP (0.10.0+, `PascalApi.Tracing` — unstable until it moves to pascal-common-faa — and `PascalApi.Otlp`) |
| JWT HS256, SHA-256, HMAC-SHA256, Base64url (FPC 3.2.2 has no SHA-256) | pascal-api-infra-faa | `PascalApi.Jwt`, `PascalApi.Crypto` | only `SysUtils`: candidate to move to pascal-common-faa when a second library needs it |
| Paging/ordering from the query string, `.env` config, file logging, rate-limit window, DTO bases | pascal-api-infra-faa | `PascalApi.Pagination`, `.OrderBy`, `.Config`, `.FileLog`, `.RateLimitState`, `.Dto` | |
| OpenAPI 3.0.3 / Swagger UI from the route declarations and DTO types (no attributes) | pascal-api-infra-faa (0.3.0+) | `PascalApi.OpenApi`, `src/horse/PascalApi.Horse.OpenApi` (`TRouteDoc`) | metadata in code (`TApiSchema.Describe`): FPC 3.2.2 has no custom attributes; Bearer/JWT scheme from the auth middleware (0.7.0+) |
| MCP server (protocol 2026-07-28): the documented routes as tools for AI clients | pascal-api-infra-faa (0.5.0+) | `PascalApi.Mcp`, `src/horse/PascalApi.Horse.Mcp` (`TMcpEndpoint`) | tool calls go back through the API over HTTP (all middlewares apply); checked with the official Python SDK |
| UTF-8 bytes to string that refuses to corrupt text on a non-UTF-8 code page | pascal-common-faa (1.4.0+) | `PascalCommon.Utf8` (`PcTryUtf8BytesToString`) | moved there from pascal-db-faa and pascal-api-infra-faa, which keep wrappers |
| W3C Trace Context: trace/span ids, `traceparent`/`tracestate` parse and format | pascal-common-faa (1.5.0+) | `PascalCommon.TraceContext` (`PcNewTraceId`, `PcTryParseTraceParent`...) | ids from the OS random source; the base of pascal-api-infra-faa's observability (metrics and spans come later) |
| Metrics: counter, gauge, histogram, registry, Prometheus `/metrics` text | pascal-common-faa (1.6.0+) | `PascalCommon.Metrics` (`PcMetrics`, `PcPrometheusText`) | OpenTelemetry names converted to Prometheus ones; lock-free recording on a series |
| Spans (OpenTelemetry-style): tracer, current span per thread, sampling, batch processor | pascal-common-faa (1.7.0+) | `PascalCommon.Tracing` (`TPcTracing`, `IPcSpan`, `IPcSpanExporter`) | the OTLP/HTTP exporter is pascal-api-infra-faa's `PascalApi.Otlp`; a library instruments with `StartSpan` and needs no exporter |
| String to UTF-8 bytes, MD5 hex, UTF-8-safe prefix | pascal-api-infra-faa | `PascalApi.Text` | |
| AMQP 0-9-1 client and an embeddable broker (no RabbitMQ needed) | pascal-amqp-faa | `AMQP.*` | |
| Redis client (RESP2/RESP3, pool, pipelining, Pub/Sub, Streams, TLS) | pascal-redis-faa | `Redis.*` | |
| Local IPC / TCP / TLS messaging with one API (Named Pipe on Windows, Unix socket on Linux) | pascal-pipes-faa (was pascal-named-pipes-faa) | `Pipes.*` | Android (Delphi) too, without the local transport |
| Windows Service vs systemd hosting, NFe/SEFAZ distribution, OpenSSL/libxml2 on Linux | pascal-dfe-broker | an application, not a library | see `background-service-hosting.md`, `native-library-interop.md` |

## Repositories

| Library | Repository |
|---|---|
| pascal-common-faa | https://github.com/fabianoallex/pascal-common-faa |
| pascal-jsonmapper-faa | https://github.com/fabianoallex/pascal-jsonmapper-faa |
| pascal-db-faa | https://github.com/fabianoallex/pascal-db-faa |
| pascal-api-infra-faa | https://github.com/fabianoallex/pascal-api-infra-faa |
| pascal-amqp-faa | https://github.com/fabianoallex/pascal-amqp-faa |
| pascal-redis-faa | https://github.com/fabianoallex/pascal-redis-faa |
| pascal-pipes-faa | https://github.com/fabianoallex/pascal-pipes-faa |
| pascal-dfe-broker | https://github.com/fabianoallex/pascal-dfe-broker |

## Keeping this table right

- Add a row when a library gains something another project could need; the library's README
  "Contents" table is the source.
- When a second library needs a piece that lives in a specific one (as the UTF-8 decoder did),
  that piece moves to pascal-common-faa, whose rule is "what at least two libraries need";
  pascal-common-faa's `docs/plan.md` keeps the list of such candidates.
- State versions in the libraries' READMEs, not here: this table says where to look, not what is
  current.
