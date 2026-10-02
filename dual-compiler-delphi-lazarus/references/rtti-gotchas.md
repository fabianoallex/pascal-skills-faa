# RTTI gotcha catalog: Delphi vs FPC

How far RTTI code can be shared between Delphi and FPC, measured rather than recalled. Each claim below comes from a probe program compiled and run on both sides: one small `.dpr` per feature, a single source with `{$IFDEF FPC}` only where unavoidable, so a compile failure on one side can't hide the others' results. The probes, the scripts that run them, and the raw reference outputs are in `scripts/rtti-probes/` — re-run them to check a different compiler version.

**Verified on:** FPC 3.2.2 (Lazarus 4.0) Win64, `{$MODE DELPHI}` · Delphi 12 CE (CompilerVersion 36) Win32 **and** Win64. Delphi Win32 and Win64 produced identical results (only the inherited-`TObject` method count and pointer addresses differed), so every divergence here is compiler-driven, not platform-driven. **Not tested:** FPC trunk (3.3.1), which has extended RTTI and attributes merged — re-verify before relying on anything below for a trunk-based build.

## TL;DR — the portable subset on FPC 3.2.2

What genuinely works the same on both sides:

- **Classic `TypInfo` on `published` properties** (`{$M+}` / `TPersistent`): `GetPropList`, `GetPropInfo`, `Get/SetStrProp`, `Get/SetOrdProp`, `Get/SetEnumProp`, `Get/SetSetProp`, `Get/SetInt64Prop`, `Get/SetFloatProp`, `GetEnumName`/`GetEnumValue`, `IsPublishedProp`.
- **`TRttiContext.GetType` + `GetProperties`/`GetProperty` + `GetValue`/`SetValue`** — but only for `published` properties (see below).
- **Interface method RTTI under `{$M+}`**: method names, parameter names/types, return type, **`TRttiMethod.Invoke` through an interface `TValue`** (native on Win64, no libffi needed), and **`TVirtualInterface`** (handler `Args` includes `Self` on both: 3 args for `Add(A, B)`).
- **`TValue` core**: implicit from Integer/string/Boolean, `TValue.From<T>`, `TValue.Make`, `ExtractRawData`, `IsType<T>`, `Empty`/`IsEmpty`, `IsArray`/`GetArrayLength`/`GetArrayElement`; `AsInteger`/`AsString` raise `EInvalidCast` on the wrong kind on both.
- **`TRttiInstanceType`**: `Name`, `DeclaringUnitName`, `MetaclassType`, `BaseType`, `IsInstance`, `IsManaged`, `TypeKind`; `GetTypeData(...)^.UnitName` / `ClassType`.

Design rule that falls out of this: **everything RTTI must see is `published`, or lives on a `{$M+}` interface.** Field-, attribute- and class-method-driven designs (Delphi 2010+ style) are Delphi-only on FPC 3.2.2.

## Divergences that break compilation

| Code | Delphi 12 | FPC 3.2.2 | Portable form |
|---|---|---|---|
| `PropInfo^.PropType` | `PPTypeInfo` — needs `^` (without it: E2010 `PTypeInfo` vs `PPTypeInfo`) | `PTypeInfo` — with `^` it's `TTypeInfo`, an error | `PropInfo^.PropType{$IFNDEF FPC}^{$ENDIF}` — neither spelling compiles on both |
| Attributes (`TCustomAttribute`, `[Tag(...)]`) | ✔ on classes, properties (public too), fields, methods | `TCustomAttribute` doesn't exist; `[` is a syntax error | none on 3.2.2 |
| `TRttiType.GetFields` / `TRttiField` (classes **and** records) | ✔ all visibilities by default | doesn't exist | published properties instead of fields |
| `TVirtualMethodInterceptor` | ✔ | doesn't exist | none |
| `TValue.AsType<T>` / `TryAsType<T>` | ✔ | doesn't exist | `AsInteger`/`AsString`/…, or `ExtractRawData` |
| `TRttiContext.FindType` / `GetTypes`, `TRttiType.QualifiedName` | ✔ (see the Delphi-side catch below) | don't exist (`GetTypes` is commented out in the source) | keep your own name → `PTypeInfo` registry |
| `TRttiEnumerationType.GetName<T>` / `GetValue<T>` | ✔ | doesn't exist | `GetEnumName`/`GetEnumValue` from `TypInfo` |
| `TRttiDynamicArrayType` (`ElementType`) | ✔ | doesn't exist | `TValue.GetArrayLength`/`GetArrayElement` work on both |
| `reference to` types (and `TypeInfo` of them) | ✔ (`tkInterface`) | not supported in 3.2.2 | `procedure ... of object` |
| `published property Value: T` in a generic class | ✔ compiles, get/set via RTTI works | "This kind of property cannot be published" | publish only concrete-typed properties — and the `T` one is then invisible to FPC's RTTI anyway |
| `TypeInfo` of an enum with explicit values (`(eA = 1, eB = 5)`) | E2134 "has no type info" | "No type info available" | **same on both** — map such enums by hand |

Delphi-side catch: `QualifiedName` (and therefore `FindType`) raises `ENonPublicType` — *"Type 'TFoo' is not declared in the interface section of a unit"* — for types declared in a unit's `implementation` section or in the `.dpr`. Only interface-section types are findable by name.

## Divergences that compile fine and differ silently

These are the dangerous ones: no compiler error, different runtime answer.

### `TTypeKind` spellings

| Type | Delphi 12 | FPC 3.2.2 |
|---|---|---|
| `string` | `tkUString` | **`tkAString`** under `{$MODE DELPHI}` (`string` = `AnsiString`); `tkUString` under `{$MODE DELPHIUNICODE}` |
| `AnsiString` | `tkLString` | `tkAString` |
| `ShortString` | `tkString` | `tkSString` |
| `Char` | `tkWChar` | `tkChar` (under `{$MODE DELPHI}`) |
| `Boolean`, `ByteBool` | `tkEnumeration` | **`tkBool`** |
| `UInt64` | `tkInt64` | `tkQWord` |
| `Comp` | `tkFloat` | `tkInt64` |
| procedural type (`function(X: Integer): Integer`) | `tkProcedure` | `tkProcVar` |

Same on both: `Integer`/`Cardinal` `tkInteger`, `Int64` `tkInt64`, floats and `Currency` `tkFloat`, `WideString` `tkWString`, `UnicodeString` `tkUString`, `AnsiChar` `tkChar`, `Variant`, enum, set, record, dynarray/`TBytes`, static array, class, `IInterface`, `TNotifyEvent` (`tkMethod`), `class of` (`tkClassRef`), `Pointer` (`tkPointer`).

Consequences: a `case Kind of` written against one compiler silently falls into `else` on the other, and `PropIsType(Obj, 'Flag', tkEnumeration)` on a Boolean property is `True` on Delphi and **`False`** on FPC. Handle both spellings in one place:

```pascal
function IsStringKind(K: TTypeKind): Boolean;
begin
  // FPC declares tkString as an alias of tkSString: listing both is a
  // "duplicate set element" compile error, hence the split.
  Result := K in [{$IFDEF FPC}tkSString, tkAString{$ELSE}tkString{$ENDIF}, tkLString, tkWString, tkUString];
end;

function IsBooleanType(T: PTypeInfo): Boolean;
begin
  Result := T = TypeInfo(Boolean); // compare the PTypeInfo, not the kind
end;
```

### Visibility: what `GetProperties` / `GetMethods` actually return

| Probe | Delphi 12 | FPC 3.2.2 |
|---|---|---|
| `GetProperties` on a `{$M+}` class with private/protected/public/published props | `PubProp:mvPublic PublProp:mvPublished` | `PublProp:mvPublished` only |
| `GetProperties` on a class **without** `{$M+}` (public prop) | `[X]` | `[]` |
| `GetProperties` on `TStringList` | 25 | **0** (nothing published) |
| `GetDeclaredMethods` on a `{$M+}` class | `Add:mvPublic PublM:mvPublished` | **`[]`** — even published methods |
| `GetMethod('Add')` on a class + `Invoke` | ✔ returns 5 | **`nil`** |
| `{$RTTI EXPLICIT METHODS([vcPrivate..vcPublished]) ...}` | honored — private method appears | ignored with *Warning: Illegal compiler directive "$RTTI"* |

FPC 3.2.2 has no method RTTI for classes at all; `TObject.MethodAddress('PublM')` (classic published-method lookup) still works on both. Delphi's default RTTI does **not** include private/protected methods either — see the DUnitX `[Test]`-in-`private` case in `rtl-gotchas.md`.

### `TValue` behavior

| Probe | Delphi 12 | FPC 3.2.2 |
|---|---|---|
| `V := 'literal'` → `V.Kind` | `tkUString` | `tkAString` — **even under `{$MODE DELPHIUNICODE}`**, because the implicit operator is declared in the `Rtti` unit itself, compiled with `string = AnsiString` |
| `V := True` → `V.Kind` | `tkEnumeration` | `tkBool` |
| `ToString` of Double 1.5 | `1,5` | **`''`** |
| `ToString` of a set / record / dynarray / object | `[meB]` / `(record)` / `(dynamic array [0..1] of Integer)` / `(TObject @ …)` | **`''`** for all |
| `ToString` of Integer / string / Boolean / enum | value | value (same) |

Root cause for `ToString`: FPC 3.2.2's `TValue.ToString` is a `case Kind of` covering only strings, integer kinds, `tkBool`, enums, chars, pointers and interfaces — everything else hits `else result := ''`. Never use `TValue.ToString` for serialization or logging of non-ordinal values on FPC; use `AsExtended` etc. explicitly.

### `TRttiType` metadata

| Probe | Delphi 12 | FPC 3.2.2 |
|---|---|---|
| `GetType(TypeInfo(Integer)).IsOrdinal` | `True` | **`False`** — `TRttiType.GetIsOrdinal` returns `false` and no subclass overrides it in 3.2.2; test `TypeKind` instead |
| `Name` of `TBox<Integer>` | `TBox<System.Integer>` | `TBox$1$crc9F312717` — never match generic types by name |
| `PropertyType.Name` of an `Integer` property | `Integer` | `LongInt` |
| `ParamType.Name` of a `string` parameter | `string` | `AnsiString` |
| `GetPropValue` of a Boolean property (`VarToStr`) | `True` | `1` |

The type-name rows matter for anything that maps by type name (JSON/ORM converters keyed on `'Integer'`, `'string'`): key on `PTypeInfo`/`TTypeKind`, not on `Name`.

## Practical rules for dual-compiler RTTI code

1. **`published` is the contract.** Anything a serializer/binder/ORM must see goes in a `published` section of a `{$M+}` class. Public-only properties exist only on Delphi's side.
2. **No attributes, no fields, no class-method RTTI** while FPC 3.2.2 is a target. If you need metadata, keep it in an explicit registry (class → list of property names/options) built at unit initialization.
3. **Dynamic dispatch goes through `{$M+}` interfaces** (`TRttiMethod.Invoke` on an interface `TValue`, or `TVirtualInterface` for proxies/mocks) — the one piece of extended RTTI that matches on both.
4. **Compare `TTypeKind` sets, not single kinds**, and route all kind checks through one helper (see above).
5. **`{$IFNDEF FPC}^{$ENDIF}` on every `PropType` dereference** — wrap it once in a `PropTypeOf(PropInfo): PTypeInfo` helper.
6. **Don't trust `TValue.ToString`, `IsOrdinal`, or type `Name`** on the FPC side.
7. Under `{$MODE DELPHIUNICODE}` FPC's `string` becomes `tkUString`, but `TValue` implicit conversions still produce `tkAString` — don't mix mode changes into the RTTI story without re-testing.
