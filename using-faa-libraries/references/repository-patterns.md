# Repository patterns: optionals, checks and SQL tags without `if HasValue`

How a repository on pascal-common-faa, pascal-db-faa and pascal-api-infra-faa writes INSERTs,
PATCHes and filtered lists so that an optional member is never opened with an `if`. Proven in
pascal-agenda-faa's four repositories (services, professionals, customers, users; 2026-10-19,
323 HTTP checks unchanged, `if` 83 -> 54, `HasValue` 59 -> 37) and in pascal-api-infra-faa's
sample 02. Each library's own doc has the details: pascal-db-faa `docs/optionals.md` (optionals
as parameters, partial updates), pascal-common-faa's README (normalizers, `Map`), pascal-api-infra-faa
`docs/guide/dtos-json.md` and `database.md`.

## The three states, and who handles each

| A member that... | is | `Map`/`Normalize` | `OptXxx` parameter | its SQL block |
|---|---|---|---|---|
| didn't come | Undefined | not called, stays Undefined | not bound | removed (`ProcessTag(.., False)`) |
| came as `null` (`IOptNullXxx`) | Null | not called, stays Null | binds NULL | kept |
| came with a value | From(X) | called: the rule's result, or its exception | binds the value | kept |

## 1. A check is a function from the value to the value to store

```pascal
// The shape of TPcStringFunc: normalizes, and raises a 400 for a bad value.
function CheckEmail(const AEmail: string): string;
begin
  Result := NormalizeEmail(AEmail);
  if Result = '' then
    raise EValidationException.Create('"email" is not an email address.');
end;

function CheckDuration(const AMinutes: Integer): Integer;   // TPcIntegerFunc
begin
  if (AMinutes < 5) or (AMinutes > 480) or (AMinutes mod 5 <> 0) then
    raise EValidationException.Create('"durationMinutes" must be a multiple of 5 from 5 to 480.');
  Result := AMinutes;
end;
```

- A required member calls it directly: `LName := CheckName(AService.Name)`.
- An optional member goes through `Map`: `LEmail := APatch.Email.Map(CheckEmail)`. No `if`: absent
  stays absent, `null` stays `null`, a value is checked.
- **The signature must match exactly**, `const` included: `function(const AValue: string): string`
  (also `Integer`, `Int64`, `Currency`...). It is a plain function pointer, not a method (FPC 3.2.2
  has no closures, and `of object` would refuse a Delphi caller's plain function): write the
  checks as unit-level functions.
- `Map` is for checks (it may raise); `Normalize` with a factory normalizer (`TNorm.CityName`) is
  for pure transformations. pascal-api-infra-faa's sample 02 keeps limits out of normalizers so a
  normalizer never hides a client's mistake; a check that raises doesn't hide it.

## 2. A rule that needs context is a normalizer object

When the rule needs more than the value (a hash's iterations, the tenant's scope to look a row
up), write an `IPcStringNormalizer` that carries it, and take it with `Normalize`:

```pascal
type
  TExistingProfessional = class(TInterfacedObject, IPcStringNormalizer)
  private
    FScope: TTenantDataScope;
  public
    constructor Create(const AScope: TTenantDataScope);
    function Apply(const AValue: string): string;   // the id, or a 400
  end;

LProfessional := APatch.ProfessionalId.Normalize(TExistingProfessional.Create(FScope));
LHash := APatch.Password.Normalize(THashPassword.Create(FIterations));
```

`Normalize`'s parameter isn't `const` on purpose: the new object gets its reference and is freed
with the call.

## 3. The optional is bound as it is, next to its tag

```sql
UPDATE SERVICES SET UPDATED_AT = :UPDATED_AT
  [NAME {], NAME = :NAME, NAME_KEY = :NAME_KEY [} NAME]
  [DURATION {], DURATION_MINUTES = :DURATION_MINUTES [} DURATION]
  [ACTIVE {], ACTIVE = :ACTIVE [} ACTIVE]
WHERE ID = :ID AND ${TENANT}
```

```pascal
LName := APatch.Name.Map(CheckName);
LDuration := APatch.DurationMinutes.Map(CheckDuration);
TTenantFilter.Prepare(LQuery, FScope, FScope.Factory.SqlLoader['SERVICE.UPDATE']
  .ProcessTag('NAME', LName.HasValue)
  .ProcessTag('DURATION', LDuration.HasValue)
  .ProcessTag('ACTIVE', APatch.Active.HasValue));
LQuery.Params.OptStrings['NAME'] := LName;
LQuery.Params.OptStrings['NAME_KEY'] := LName.Map(PcFoldForSearch);  // derived, same state
LQuery.Params.OptIntegers['DURATION_MINUTES'] := LDuration;
LQuery.Params.OptBooleans['ACTIVE'] := APatch.Active;
```

- **The tag and the parameter go together, on the same `HasValue`.** A tag nobody processes loses
  only its markers and keeps its content: the `:PARAM` stays in the SQL, and an Undefined optional
  binds nothing (SQLdb: `Parameter "X" not found`; another driver may bind NULL silently).
- Check through `Map` **before** the transaction: a 400 touches nothing.
- The same for an INSERT with optional columns: `[EMAIL {] EMAIL, [} EMAIL]` in the column list
  and `[EMAIL {] :EMAIL, [} EMAIL]` in the values; absent, the database writes its default (NULL).
- `IOptNullXxx` for a PATCH member that may be cleared (`OptNullStrings`: Null writes NULL);
  `IOptXxx` for one that can't be null.
- `Booleans`/`OptBooleans` into an integer column work on every engine the contract suite runs
  (pascal-db-faa `Params_EveryType_RoundTrip`).

## 4. Defaults and merges

- A default: `AService.BufferMinutes.ValueOr(0)`; the stored value under a PATCH:
  `LName.ValueOr(LResult.Strings['NAME'])`.
- A nullable member over a stored nullable value (absent -> stored, null -> null, value -> value)
  has no one-call form yet: a three-line helper (`if APatch.HasValue then Result := APatch as
  INullString else Result := AStored`).
- Read the row and write it whole only when a derived column depends on several members (a search
  key over name, email and phone); otherwise prefer the tagged partial UPDATE.

## 5. Filtered lists

Search and filters are the same pair, tag plus value, in both statements of a page; since
pascal-api-infra-faa 0.19.0 `TTenantPagedQuery.Run<T>` (or `TPagedQuery`) runs the count and the
page with one `TQueryArgs`, and `THorseQueryParams.Read<IFind>` fills the Find DTO from the query
string. A literal search: `PdbLikeContains(PcFoldForSearch(AFind.Search.Value))` with
`ESCAPE '!'` (never a backslash: pascal-db-faa gotcha 26).

## Where an `if` stays, on purpose

- Inside the check itself (that is the rule).
- A conversion to another type: `Map` keeps the type, so an `IOptCurrency` price stored as an
  `Int64` of cents is `if LPrice.HasValue then Params.Int64s[...] := CentsOf(LPrice.Value)`.
- A business decision across members (the owner can't demote or deactivate themselves).
