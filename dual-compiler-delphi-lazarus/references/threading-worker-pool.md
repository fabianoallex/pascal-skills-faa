# A worker pool without `TTask.Run`

The RTL gotcha table says "don't use `System.Threading`/`TTask.Run`, use a
project-specific thread pool" — but that instruction alone leaves the actual
shape of "a project-specific thread pool" to invent from scratch each time.
This is the concrete pattern, taken from
[`pascal-skills-threads`](https://github.com/fabianoallex/pascal-skills-threads)
(`MultiDownloader`, built with this skill), which needed N worker threads
consuming a shared list of download jobs.

Three pieces, each a plain class — no generics, no anonymous methods, per
`{$MODE DELPHI}`:

## 1. A lock-protected job queue

All jobs are known upfront, so the queue only needs to hand out "the next
not-yet-taken job" — a single `TCriticalSection` around an index is enough;
no need for `TInterlocked`/`AtomicXxx` (see the RTL gotcha table for why
those are avoided anyway):

```pascal
TDownloadJobQueue = class
private
  FLock: TCriticalSection;
  FJobs: TDownloadJobArray;
  FNextIndex: Integer;
public
  constructor Create(const AJobs: TDownloadJobArray);
  destructor Destroy; override;
  function TryTake(out AJob: TDownloadJob): Boolean;
end;

function TDownloadJobQueue.TryTake(out AJob: TDownloadJob): Boolean;
begin
  FLock.Enter;
  try
    Result := FNextIndex < Length(FJobs);
    if Result then
    begin
      AJob := FJobs[FNextIndex];
      Inc(FNextIndex);
    end;
  finally
    FLock.Leave;
  end;
end;
```

Full file: `src/MultiDownloader.Queue.pas` in the reference project.

## 2. A worker thread that drains the queue

Each worker is a plain `TThread` (created suspended, `FreeOnTerminate :=
False` so the manager can `WaitFor`/`Free` it deterministically) that loops
`TryTake` until the queue is empty:

```pascal
TDownloadWorker = class(TThread)
protected
  procedure Execute; override;
end;

procedure TDownloadWorker.Execute;
begin
  while not Terminated and FQueue.TryTake(FCurrentJob) do
  begin
    // do the work for FCurrentJob, collect the result
  end;
end;
```

Any cross-thread output (progress logging, etc.) goes through a lock, not
`Synchronize`/`Queue` — see the "no message loop in a console app" entry in
`references/rtl-gotchas.md`. Full file: `src/MultiDownloader.Worker.pas`.

## 3. A manager that owns the pool's lifecycle

The one place that creates the queue, starts N workers, waits for all of
them, and collects results — the only piece of this pattern that changes
per-project is the number of workers and what a "job" actually is:

```pascal
class function TDownloadManager.Run(const AJobs: TDownloadJobArray;
  AMaxConcurrent: Integer): TDownloadResultArray;
var
  LQueue: TDownloadJobQueue;
  LWorkers: array of TDownloadWorker;
  I: Integer;
begin
  LQueue := TDownloadJobQueue.Create(AJobs);
  try
    SetLength(LWorkers, AMaxConcurrent);
    for I := 0 to AMaxConcurrent - 1 do
      LWorkers[I] := TDownloadWorker.Create(I + 1, LQueue, ...);

    for I := 0 to AMaxConcurrent - 1 do
      LWorkers[I].Start;

    for I := 0 to AMaxConcurrent - 1 do
      LWorkers[I].WaitFor;   // exactly once per thread — see the WaitFor
                              // idempotency gotcha in rtl-gotchas.md

    for I := 0 to AMaxConcurrent - 1 do
      LWorkers[I].Free;
  finally
    LQueue.Free;
  end;
end;
```

Full file: `src/MultiDownloader.Manager.pas`.

## Why this shape, not something fancier

- **No condition variables / semaphores for "wait until work arrives"**:
  every job is known upfront (a fixed list, not a live producer), so a
  worker can just loop until `TryTake` returns `False` and exit — there's
  nothing to block on. If the project's actual use case is a genuine
  producer/consumer (jobs arriving while workers are already running),
  the queue needs a wait primitive (`TEvent`/`TSimpleEvent` from `SyncObjs`,
  identical on both compilers) instead of `TryTake` returning `False`
  immediately — that's a real variant of this pattern, not covered here
  because the reference project didn't need it.
- **`WaitFor` called exactly once per thread**, never in a loop or from more
  than one place — this is what the `TThread.WaitFor` non-idempotency
  gotcha on FPC/Unix (see `rtl-gotchas.md`) actually requires in practice.
- **Verified under real concurrency, not just read-through**: the reference
  project's test suite spins up 8 real threads competing for 200 queue
  slots and asserts each job was delivered exactly once
  (`TryTake_Concurrency_NoDuplicatesNoLoss` in
  `tests/Unit/MultiDownloader.QueueTests.pas`) — removing the
  `TCriticalSection` made it fail reliably (duplicated/lost jobs), which is
  the actual evidence the lock is doing something, not just present.
