# Repository patterns: normalize, validate, bind the optionals (no `if HasValue`)

How a repository on pascal-common-faa, pascal-db-faa and pascal-api-infra-faa writes INSERTs,
PATCHes and filtered lists so that an optional member is never opened with an `if`. Proven in
pascal-agenda-faa's four repositories (services, professionals, customers, users; 2026-10-19,
323 HTTP checks unchanged, `if` 83 -> 54, `HasValue` 59 -> 37), then moved to the libraries'
validation (pascal-common-faa 1.21.0, pascal-api-infra-faa 0.20.0; 333 checks), and in
pascal-api-infra-faa's sample 02. Each library's own doc has the details: pascal-db-faa `docs/optionals.md` (optionals
as parameters, partial updates), pascal-common-faa's README (normalizers, `Map`, validators),
pascal-api-infra-faa `docs/guide/dtos-json.md`, `errors.md` and `database.md`.

## The three states, and who handles each

| A member that... | is | `Map`/`Normalize` | `TPcValidation.Check` | `OptXxx` parameter | its SQL block |
|---|---|---|---|---|---|
| didn't come | Undefined | not called, stays Undefined | not checked | not bound | removed (`ProcessTag(.., False)`) |
| came as `null` (`IOptNullXxx`) | Null | not called, stays Null | not checked | binds NULL | kept |
| came with a value | From(X) | called: the normalized value | checked | binds the value | kept |

## 0. The document's limits, at the edge

What `TApiSchema.Describe` declares (`MinLength`, `MaxLength`, `Enum`, `Minimum`, `Maximum`) is
enforced when the handler reads the DTO: `THorseBody.Read<I>(AReq)` for a body,
`THorseQueryParams.Read<I>(AReq)` for the query string (pascal-api-infra-faa 0.20.0). A limit is
written once, in the `Describe`; the repository never repeats it. The edge checks the value **as
it came** (before any normalizer: `" rn"` is 3 characters for a `MaxLength(2)`) and answers
before the repository, so a request that breaks a limit and a rule hears of the limit only.
`Pattern` is documented, not enforced: write the format as an application rule.

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

## 2. Validate apart: the application's rules through `TPcValidation`

The rules the document can't say live in a factory that inherits pascal-common-faa's
`TPcStringValidators` (`Required`, `MinLength`, `MaxLength`, `OneOf`, `FromFunc`, `All`), the
partner of `TNorm`; numbers use `TPcIntegerValidators` (`MultipleOf`, `Range`...) and
`TPcCurrencyValidators` (`MaxDecimals`) directly:

```pascal
TValid = class(TPcStringValidators)
public
  class function DisplayName: IPcStringValidator; static;   // Required: something besides blanks
  class function Email: IPcStringValidator; static;         // FromFunc(CheckEmail)
  class function Phone: IPcStringValidator; static;         // FromFunc(CheckPhone)
end;

LName := TOptionals.Normalize(APatch.Name, TNorm.DisplayName);
LCheck := TPcValidation.Create;                 // a record: no try/finally
LCheck.Check('name', LName, TValid.DisplayName);              // string, IOpt, INull, IOptNull
LCheck.Check('durationMinutes', APatch.DurationMinutes, TPcIntegerValidators.MultipleOf(5));
LCheck.Check('price', APatch.Price, TPcCurrencyValidators.MaxDecimals(2));
CheckProfessional(APatch.ProfessionalId, LCheck);  // a rule with context: Fail inside
LCheck.RaiseIfAny;       // EPcValidationError: one 400 listing every failing field
```

- One `Check` per member whatever its shape; the "absent or null: not checked" rule is the
  library's, so the application writes each rule once (pascal-agenda-faa had three overloads per
  rule before).
- A rule that needs the database or another member is a method or a plain `if` that calls
  `LCheck.Fail(AField, ACode, AMessage)`, taking the collector as `var`. Check `LCheck.IsValid`
  before a cross-member rule that needs both members valid (`HasFailed(AField)` asks about one).
- Field names are the JSON names; the codes are the library's (`required`, `too_short`,
  `out_of_range` for a `Minimum`+`Maximum` pair, `not_multiple`, `too_many_decimals`...) or the
  application's (`invalid_email`). The 400: `{"error": <first message>, "code":
  "invalid_fields", "fields": [{field, code, message}]}`. A single business refusal (`own_account`)
  stays an `EValidationException` with its code.
- Validate **after** normalizing (the rule sees what will be stored) and before the transaction.

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
... // TPcValidation, step 2
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

- A conversion to another type: `Map` keeps the type, so an `IOptCurrency` price stored as an
  `Int64` of cents is `if LPrice.HasValue then Params.Int64s[...] := CentsOf(LPrice.Value)`.
- A business decision across members (the owner can't demote or deactivate themselves).
