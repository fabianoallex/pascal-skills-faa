# Repository patterns: normalize, validate, bind the optionals (no `if HasValue`)

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
| came with a value | From(X) | called: the normalized value | binds the value | kept |

## 1. Normalize with the application's factory, inside the optionals

The application's normalizers live in one factory that inherits pascal-common-faa's
`TPcStringNormalizers`, as pascal-api-infra-faa's sample 02 and its guide "DTOs and JSON" do:

```pascal
TNorm = class(TPcStringNormalizers)        // Trim, Lower, FoldForSearch, FromFunc, Chain inherited
public
  class function DisplayName: IPcStringNormalizer; static;   // Chain([Trim, CollapseSpaces])
  class function Email: IPcStringNormalizer; static;         // Chain([Trim, Lower])
  class function Phone: IPcStringNormalizer; static;         // FromFunc(PhoneOf)
end;

LName := TOptionals.Normalize(APatch.Name, TNorm.DisplayName);   // absent stays absent
LEmail := TOptionals.Normalize(APatch.Email, TNorm.Email);        // null stays null
LName := TNorm.DisplayName.Apply(AService.Name);                 // a required, plain value
```

- **A normalizer never refuses.** What can't be made right comes out as it went in (a phone with
  letters) and the validation refuses it next; a normalizer that cut a name at 100 characters
  would hide the client's mistake instead of answering 400.
- Business rules (a phone, a CEP, a CPF) belong in the application's factory, not in the library
  (`PascalCommon.Normalizers`' header).
- A transformation that needs context (a password hash and its iterations) is a class implementing
  `IPcStringNormalizer`, taken the same way: `TOptionals.Normalize(APatch.Password,
  THashPassword.Create(FIterations))`. `Normalize`'s parameter isn't `const` on purpose: the new
  object gets its reference and is freed with the call.
- **FPC ambiguity:** `TOptNullString.Undefined`/`Null`/`From(...)` answer the class, which fits
  every overload of `Normalize` (and of the validators below): pass a typed variable.

## 2. Validate apart: checks that change nothing, one overload per shape

```pascal
procedure ValidateEmail(const AEmail: string); overload;          // required: always checked
procedure ValidateEmail(const AEmail: IOptString); overload;      // checked when it came
procedure ValidateEmail(const AEmail: IOptNullString); overload;  // when it came with a value

procedure ValidateEmail(const AEmail: IOptNullString);
begin
  if AEmail.HasValue and not AEmail.IsNull then
    ValidateEmail(AEmail.Value);
end;

LEmail := TOptionals.Normalize(APatch.Email, TNorm.Email);
ValidateEmail(LEmail);                 // a 400 touches nothing: before the transaction
ValidateDuration(APatch.DurationMinutes);
```

- The `if HasValue` lives inside the rule, once; the repository calls every rule the same way.
- A check that needs the database (the professional exists in this tenant) is a method of the
  repository, with the same overloads.
- An alternative when a check can also normalize: write it as `function(const AValue: T): T` that
  raises, and take it with `Map` (`APatch.Email.Map(CheckEmail)`); `Map` calls it only when the
  member came. pascal-agenda-faa used that first, then chose the split above, which keeps the
  library guide's shape and makes each step testable alone.

## 3. The optional is bound as it is, next to its tag

```sql
UPDATE SERVICES SET UPDATED_AT = :UPDATED_AT
  [NAME {], NAME = :NAME, NAME_KEY = :NAME_KEY [} NAME]
  [DURATION {], DURATION_MINUTES = :DURATION_MINUTES [} DURATION]
  [ACTIVE {], ACTIVE = :ACTIVE [} ACTIVE]
WHERE ID = :ID AND ${TENANT}
```

```pascal
LName := TOptionals.Normalize(APatch.Name, TNorm.DisplayName);
ValidateName(LName);
ValidateDuration(APatch.DurationMinutes);
TTenantFilter.Prepare(LQuery, FScope, FScope.Factory.SqlLoader['SERVICE.UPDATE']
  .ProcessTag('NAME', LName.HasValue)
  .ProcessTag('DURATION', APatch.DurationMinutes.HasValue)
  .ProcessTag('ACTIVE', APatch.Active.HasValue));
LQuery.Params.OptStrings['NAME'] := LName;
LQuery.Params.OptStrings['NAME_KEY'] := TOptionals.Normalize(LName, TNorm.FoldForSearch);  // derived, same state
LQuery.Params.OptIntegers['DURATION_MINUTES'] := APatch.DurationMinutes;
LQuery.Params.OptBooleans['ACTIVE'] := APatch.Active;
```

- **The tag and the parameter go together, on the same `HasValue`.** A tag nobody processes loses
  only its markers and keeps its content: the `:PARAM` stays in the SQL, and an Undefined optional
  binds nothing (SQLdb: `Parameter "X" not found`; another driver may bind NULL silently).
- Normalize and validate **before** the transaction: a 400 touches nothing.
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

- Inside a validation rule, once per shape of member (that is the rule).
- A conversion to another type: `Map` keeps the type, so an `IOptCurrency` price stored as an
  `Int64` of cents is `if LPrice.HasValue then Params.Int64s[...] := CentsOf(LPrice.Value)`.
- A business decision across members (the owner can't demote or deactivate themselves).
