# Object Pascal code style

Conventions for writing Object Pascal (Delphi and Lazarus/FPC) in the author's projects. They
are style rules, not compatibility rules: each one holds the same on both compilers. Follow them
in any code you write or generate; when editing existing code that does otherwise, follow them in
what you touch and leave the rest unless asked.

## Method chaining (fluent API): `Result := Self;` on the first line

In a method that returns its own instance so calls can be chained (it returns the class itself,
or an interface the class implements), **assign `Result := Self;` as the first statement after
`begin`**, never at the end of the method.

Why: in Java or C#, `return this;` ends the method, so it has to be the last line. In Pascal,
`Result` is an implicit variable and assigning it doesn't stop the method. Left at the end, it is
skipped by any early `Exit` (a validation, a "nothing to do" case): the method then returns
whatever `Result` held — `nil` or garbage for a class, `nil` for an interface — and the next call
in the chain fails with an access violation far from the cause. Assigned first, every way out of
the method returns the instance, and whoever reads the method sees at once that it is chainable.

Do:

```pascal
function TMinhaClasse.DefinirNome(const ANome: string): TMinhaClasse;
begin
  Result := Self; // always the first line

  if ANome = '' then
    Exit; // the chain doesn't break when the method leaves early

  FNome := ANome;
end;
```

Avoid:

```pascal
function TMinhaClasse.DefinirNome(const ANome: string): TMinhaClasse;
begin
  if ANome = '' then
    Exit; // returns an undefined Result: the next call in the chain fails

  FNome := ANome;
  Result := Self; // only reached when nothing exits before it
end;
```

The same holds for an interface return (`function TBuilder.Add(...): IBuilder;`) and for
`try`/`finally` or `try`/`except` blocks: `Result := Self;` comes before the `try`, as the first
statement of the method.

With `Result` assigned first, leave early with a plain `Exit`. Don't scatter `Exit(Self)` instead:
it works on both compilers, but every new exit path has to remember it, which is the problem this
rule removes.

### Change what you return

The principle behind the rule: a fluent method changes the instance it returns. What that means
in code depends on what `Result := Self;` returns:

| Type | What `Result := Self;` returns | Where the changes go |
|---|---|---|
| Class | the object itself | its fields, directly (`FNome := ...`): it is the same object |
| Interface | the object itself, through the interface | its fields, directly: `Result` can't reach them |
| Record | a copy | `Result` (`Result.FValor := ...`): a change to `Self` is lost |

Don't write `Result.FNome := ...` in a class to make it look like the record case: it does the
same thing with more noise, suggests a copy that isn't there, and doesn't compile at all when the
method returns an interface.

### On a `record`: same first line, then change `Result`, never `Self`

A record is a value: `Result := Self;` copies it at that moment, so a field of `Self` changed
afterwards is not in the copy returned and the chain silently loses the change. Keep
`Result := Self;` first and make every change on `Result`:

```pascal
function TConfigurador.DefinirValor(const ATexto: string): TConfigurador;
begin
  Result := Self;

  if ATexto = '' then
    Exit;

  Result.FValor := ATexto; // changes the copy that is returned
end;
```

Avoid changing `Self` and copying it at the end (`FValor := ATexto; Result := Self;`): it needs
`Result := Self;` before every `Exit` again, and in `R.A(...).B(...)` only `A` changes `R` (`B`
runs on the copy `A` returned), so `R` ends up with part of the chain. Writing to a field of
`Self` also triggers the FPC gotcha in `rtl-gotchas.md`, "A method that assigns to a field of
`Self`, called on a `const` record parameter"; writing only to `Result` doesn't.

The consequence: such a method never changes the record it is called on. A call whose result is
dropped (`R.DefinirValor('x');`) does nothing, and neither compiler warns. Always use the result:
`R := R.DefinirValor('x');`, or assign the end of the chain. Don't mix both styles in one record.
