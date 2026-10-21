# Ready-made dual-compiler libraries (the `*-faa` family)

Before writing infrastructure in a new Delphi + Lazarus/FPC project — JSON, database access, an
HTTP API layer, hashing, threading, messaging — check this table. Each library below already
compiles and passes its tests on both compilers (FPC 3.2.2 and Delphi 12; see each README for
the exact targets verified), and paid the dual-compiler cost this skill catalogs. Reusing one is
cheaper than re-deriving it, and two copies of the same thing in two libraries drift apart.

All are public on GitHub under MIT, by the same author, `{$MODE DELPHI}`. A consumer takes each
one as its **own** git submodule (one copy per application, even when several libraries depend on
it), never through another library's `external/` folder.

This table says which library to pick. How to set them up together and use them without the
traps their authors measured (versions, Lazarus packages, the shared thread pool, shutdown,
errors from callbacks) is the `using-faa-libraries` skill, in the same plugin.

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
| REST API on Horse: error handler, CORS, request log, Bearer/JWT auth, rate limit | pascal-api-infra-faa | `src/horse/PascalApi.Horse.Middlewares` | one configuration per middleware per process (Horse's FPC callbacks are plain procedures); request log with the W3C trace id as `X-Request-Id`, `traceparent` for the handler, text or JSON lines (0.8.0+); HTTP server metrics on `/metrics` (Prometheus) and `/health/live`/`ready` (0.9.0+, `PascalApi.Horse.Observability`); spans to an OpenTelemetry collector over OTLP/HTTP (0.10.0+; the exporter is `PascalApi.Otlp`, the spans are pascal-common-faa's `PascalCommon.Tracing` since 0.11.0) |
| SHA-256, HMAC-SHA256, Base64url, constant-time comparison (FPC 3.2.2 has no SHA-256); password hashing with PBKDF2-HMAC-SHA256 (1.18.0+) | pascal-common-faa (1.17.0+) | `PascalCommon.Crypto` (`PcSha256`, `PcHmacSha256`, `PcBase64UrlEncode`, `PcPbkdf2HmacSha256`...) | moved from pascal-api-infra-faa, whose `PascalApi.Crypto` keeps `Pa*` wrappers |
| JWT HS256: sign, verify (alg, signature, exp, nbf), a `kid` in the header | pascal-api-infra-faa | `PascalApi.Jwt` | on `PascalCommon.Crypto`; the signing keys are the next row |
| JWT signing keys that rotate without logging anyone out: named by `kid`, generated and rotated in a database or Redis, one ring per tenant, sealed under a master key | pascal-api-infra-faa (0.15.0+) | `PascalApi.JwtKeys` (`TStaticJwtKeyRing`, `TRotatingJwtKeyRing`, `TSealedJwtKeyStore`), `PascalApi.Tenancy` (`TTenantJwtKeyRing`), `src/redis/PascalApi.Redis.JwtKeys` | opt-in (`TJwtMiddleware.New(secret)` unchanged); rotation happens on a request, no thread; guide with procedures (revoking a leaked key, rotating the master key): its `docs/guide/jwt-keys.md` |
| Paging/ordering from the query string, `.env` config, file logging, rate-limit window, DTO bases | pascal-api-infra-faa | `PascalApi.Pagination`, `.OrderBy`, `.Config`, `.FileLog`, `.RateLimitState`, `.Dto` | |
| OpenAPI 3.0.3 / Swagger UI from the route declarations and DTO types (no attributes) | pascal-api-infra-faa (0.3.0+) | `PascalApi.OpenApi`, `src/horse/PascalApi.Horse.OpenApi` (`TRouteDoc`) | metadata in code (`TApiSchema.Describe`): FPC 3.2.2 has no custom attributes; Bearer/JWT scheme from the auth middleware (0.7.0+); request and response headers (`HeaderParam`, `ResponseHeader`, 0.23.0+) |
| MCP server (protocol 2026-07-28): the documented routes as tools for AI clients | pascal-api-infra-faa (0.5.0+) | `PascalApi.Mcp`, `src/horse/PascalApi.Horse.Mcp` (`TMcpEndpoint`) | tool calls go back through the API over HTTP (all middlewares apply); checked with the official Python SDK |
| Multi-tenant API: tenant from a JWT claim, a database per tenant or a shared one with `TENANT_ID` | pascal-api-infra-faa (0.12.0+) | `PascalApi.Tenancy`, `src/horse/PascalApi.Horse.Tenancy` (`TTenantMiddleware`) | opt-in, database-agnostic; every query through `TTenantFilter.Prepare` (an unbound `:TENANT_ID` is a silent 404 on SQLdb/SQLite); design and decisions in its `docs/multitenancy-design.md`; `samples/03-tenants` |
| UTF-8 bytes to string that refuses to corrupt text on a non-UTF-8 code page | pascal-common-faa (1.4.0+) | `PascalCommon.Utf8` (`PcTryUtf8BytesToString`) | moved there from pascal-db-faa and pascal-api-infra-faa, which keep wrappers |
| W3C Trace Context: trace/span ids, `traceparent`/`tracestate` parse and format | pascal-common-faa (1.5.0+) | `PascalCommon.TraceContext` (`PcNewTraceId`, `PcTryParseTraceParent`...) | ids from the OS random source; the base of pascal-api-infra-faa's observability (metrics and spans come later) |
| Random bytes from the operating system (BCryptGenRandom, `/dev/urandom`) for secrets and ids | pascal-common-faa (1.15.0+) | `PascalCommon.Random` (`PcRandomBytes`, `PcFillRandom`) | never `Random` (a clock-seeded Mersenne twister) nor `CreateGUID` (FPC 3.2.2 falls back to `Random` on some Unix targets) |
| AES-128/192/256-GCM, authenticated encryption with AAD (neither RTL has AES) | pascal-common-faa (1.16.0+) | `PascalCommon.AesGcm` (`PcAesGcmEncrypt`, `PcAesGcmDecrypt`) | pure Pascal, checked against NIST and OpenSSL vectors; the S-box is a table lookup: for secrets at rest, not for decrypting client input at a high rate |
| Metrics: counter, gauge, histogram, registry, Prometheus `/metrics` text | pascal-common-faa (1.6.0+) | `PascalCommon.Metrics` (`PcMetrics`, `PcPrometheusText`) | OpenTelemetry names converted to Prometheus ones; lock-free recording on a series |
| Spans (OpenTelemetry-style): tracer, current span per thread, sampling, batch processor | pascal-common-faa (1.7.0+) | `PascalCommon.Tracing` (`TPcTracing`, `IPcSpan`, `IPcSpanExporter`) | the OTLP/HTTP exporter is pascal-api-infra-faa's `PascalApi.Otlp`; a library instruments with `StartSpan` and needs no exporter |
| String to UTF-8 bytes, MD5 hex, UTF-8-safe prefix | pascal-api-infra-faa | `PascalApi.Text` | |
| Search key: lower case, Latin accents removed, blanks collapsed (store it next to a name; SQLite's `LOWER`/`LIKE` fold ASCII only) | pascal-common-faa (1.20.0+) | `PascalCommon.Text` (`PcFoldForSearch`), `TPcStringNormalizers.FoldForSearch` | a phone, a CEP, a CPF stay in the application's normalizer factory |
| A LIKE pattern that matches what a user typed literally (`%`, `_` escaped) | pascal-db-faa (0.16.0+) | `PascalDb.SqlLoader` (`PdbLikeContains`, `PdbLikePrefix`, `PdbLikeEscape`) | escape `!`, never a backslash: SQLdb's SQLite3/PostgreSQL connectors then lose the parameters after it (its gotcha 26) |
| SQL the same on several databases written once, each database's folder only for what differs | pascal-db-faa (0.17.0+) | `PascalDb.SqlSources` (`TFallbackSqlSource`) | wraps any source: `<SQLDirectory>/<KEY>`, then `COMMON/<KEY>`; outside a `TCompositeSqlSource`, so a database's own script wins |
| A Boolean flag stored in a `SMALLINT`/`INTEGER` column | pascal-db-faa (0.17.0+) | `PascalDb.Interfaces` (`IParams.Flags`/`OptFlags`/`NullFlags`/`OptNullFlags`) | `Booleans` only for a BOOLEAN column: PostgreSQL refuses a Boolean for an integer column (its gotcha 54) |
| An instant in JSON: a zone required on input, `Z` written (a `TDateTime` member takes a text without a zone as is and writes none) | pascal-jsonmapper-faa (0.7.0+) | `TUtcDateTime` (`PascalJsonMapper.Json`), `JsonStrToUtcDateTime`, `JsonUtcDateTimeToStr` | `date-time` in pascal-api-infra-faa's OpenAPI (0.19.0+) |
| Validation: validators per type and a collector of every failing field (neutral, no HTTP) | pascal-common-faa (1.21.0+) | `PascalCommon.Validators` (`TPcStringValidators`..., `TPcValidation`, `EPcValidationError`) | the normalizers' partner; inherit a factory for your rules |
| IANA time zones (neither RTL converts an arbitrary zone): local ⇄ UTC with the daylight-saving gap and overlap resolved, a local day's bounds, zone names validated | pascal-common-faa (1.22.0+) | `PascalCommon.TimeZones` (`PcTimeZones`, `IPcTimeZone`, `TPcLocalDateTime`) | the IANA tzdb embedded (the same answers on every target; never the Windows registry or ICU, measured stale); `TPcDirectoryTzSource` for `/usr/share/zoneinfo`; names case-sensitive; design in its `docs/timezones-design.md` |
| An instant as its zone's clock with the offset, ISO 8601 (`2027-10-31T01:00:00+01:00`) | pascal-common-faa (1.23.0+) | `PascalCommon.TimeZones` (`PcLocalIsoString`, `PcFormatUtcOffset`) | an offset with seconds (local mean time) keeps them, as Python and java.time do |
| The OpenAPI document's limits enforced, and a 400 listing every failing field | pascal-api-infra-faa (0.20.0+) | `TApiSchema.Check`, `TApiInput.FromJson<I>`, `THorseBody.Read<I>` | design: its `docs/validation-design.md` |
| A Find DTO filled from the query string, by the members the OpenAPI document lists | pascal-api-infra-faa (0.19.0+) | `PascalApi.QueryParams` (`TQueryParams`), `THorseQueryParams` in `src/horse/PascalApi.Horse.Middlewares` | a value of the wrong kind is a 400 naming the parameter; a non-optional member missing is a `required` field failure (0.23.0+) |
| Optimistic concurrency over HTTP: the row's version as a strong `ETag`, `If-Match` read as RFC 9110 says, 428/400/412 | pascal-api-infra-faa (0.23.0+) | `PascalApi.Preconditions` (`VersionETag`, `RequireIfMatchSent`, `RequireIfMatch`, `RaisePreconditionFailed`) | no middleware (the check needs the row); the write names the version read (`WHERE VERSION = :VERSION`); guide `docs/guide/concurrency.md` |
| `Idempotency-Key` on a POST: the first answer replayed, 409 while in flight, 422 for another body | pascal-api-infra-faa (0.23.0+) | `PascalApi.Idempotency` (`TIdempotency`, `TDbIdempotencyStore`, `TMemoryIdempotencyStore`), `src/horse/PascalApi.Horse.Idempotency` (`THorseIdempotentRequest`) | the table and its SQL are the application's (in the guide); not a middleware (Horse doesn't expose the response body alike on both compilers) |
| A paged list in one call: the count and the page through the same filters, one transaction | pascal-api-infra-faa (0.19.0+) | `PascalApi.PagedQuery` (`TPagedQuery`, `TTenantPagedQuery`, `TQueryArgs`) | the row reader is a plain function (no closures on FPC) |
| Refresh tokens used once: rotation in a family, a reuse or a race revoking it, logout, revoke a user | pascal-api-infra-faa (0.19.0+) | `PascalApi.RefreshTokens` (`TRefreshTokens`, `TDbRefreshTokenStore`) | the core only: login, passwords and users stay in the application; sample and guide (`docs/guide/refresh-tokens.md`) and a `Rotate` race fix in 0.19.1: use 0.19.1+ |
| AMQP 0-9-1 client and an embeddable broker (no RabbitMQ needed) | pascal-amqp-faa | `AMQP.*` | |
| Redis client (RESP2/RESP3, pool, pipelining, Pub/Sub, Streams, TLS) | pascal-redis-faa | `Redis.*` | |
| A distributed lock on one Redis (`SET NX PX` with a token, release and extend by script) | pascal-redis-faa (0.3.0+) | `Redis.Lock` (`TRedisLock`) | `Acquire` tells busy from unavailable (only connection lost, timeout, pool exhausted); the application decides whether to go on without it; not Redlock |
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
