# Forms: `.dfm`/`.lfm` mirrors

This is, in practice, one of the hardest parts of keeping a project
dual-compiler — harder than most RTL divergences, because the two files
aren't just different, they're **actively and silently rewritten by each
IDE's form designer** every time a form is opened and saved. Everything
below is confirmed by diffing 10 real `.dfm`/`.lfm` pairs from
[`pascal-amqp-faa`](https://github.com/fabianoallex/pascal-amqp-faa)'s
`samples/*Vcl` projects, not theorized.

## The mechanism

Delphi's `TForm` and Lazarus's LCL `TForm` both load their visual layout
from a resource stream at construction, pulled in via a `{$R}` directive
right after `implementation`:

```pascal
implementation

{$IFDEF FPC}
  {$R *.lfm}
{$ELSE}
  {$R *.dfm}
{$ENDIF}
```

`Name.dfm` (Delphi) and `Name.lfm` (Lazarus) sit side by side next to
`Name.pas`, both under version control, both hand-maintained in the sense
that a developer drags components onto each one *separately* in each IDE's
designer. **They are not derived from one another** — there is no
build-time or tool-assisted conversion keeping them in sync in any of the
reference projects. Whatever one designer's form looks like, someone has to
go recreate by hand in the other.

## The IDEs rewrite these files silently — this is not a hypothesis

Diffing the same form's `.dfm` against its `.lfm` shows patterns that only
make sense as automatic serializer behavior, not deliberate developer
edits:

- **`LCLVersion = '4.4.0.0'`** — identical across all 10 `.lfm` files
  examined, from the same Lazarus install. Nothing a developer would type
  by hand.
- **`TextHeight = 15`** in every `.dfm` — a font-metric cache Delphi's
  designer computes and stamps in, absent from every `.lfm`.
- **`DesignTimePPI` drift moves EVERY coordinate in the file.** 8 of the 10
  pairs examined have `DesignTimePPI = 120` in the `.lfm` with no PPI
  concept at all in the matching `.dfm`; the other 2 (forms that happen to
  have no child controls) have `DesignTimePPI = 96`. 120/96 = 1.25, and
  that's exactly the scale factor observed between every `Left`/`Top`/
  `Width`/`Height`/`Font.Height` value in the affected pairs (e.g. a form's
  `ClientHeight`/`ClientWidth` of 450×500 in the `.dfm` vs. 562×625 in the
  `.lfm`). **The likely story**: the form was opened in the Lazarus
  designer on a monitor running at 125% scaling, and Lazarus rewrote every
  physical coordinate in the file to match — not because the layout
  changed, but because the designer session's DPI did. The 2 unaffected
  forms simply never got reopened on that display. This means a form's
  `.lfm` can drift out of visual sync with its `.dfm` counterpart from
  nothing more than *opening it on a different machine*, with a diff that
  touches every line and tells you nothing about what actually changed.
- **`Anchors` sets get canonically reordered.** Delphi always serializes
  `[akLeft, akTop, akRight, ...]`; Lazarus always serializes `[akTop,
  akLeft, akRight, ...]`. 100% consistent across every anchored control in
  all 10 pairs — a serializer's fixed ordering, not something anyone typed.
- **Accented text gets re-encoded.** The same string appears as Delphi's
  escaped `'Conex\#227o'` in the `.dfm` and as raw UTF-8 `'Conexão'` in the
  `.lfm` — same content, unrelated on-disk representation.

**Practical consequence**: don't hand-edit a `.dfm`/`.lfm` expecting the
change to survive, and don't expect a diff after a designer save to be
small or meaningful — the whole file can get rewritten by a DPI change
alone. Review these diffs by what changed *visually* (open both forms), not
by reading the text diff line by line.

## Property differences, cataloged

Beyond the DPI-driven coordinate drift, these properties are consistently
one-sided (not present, or not meaningful, on the other compiler):

| Property | Only in | Why |
|---|---|---|
| `Font.Charset = DEFAULT_CHARSET` | `.dfm` | No LCL equivalent |
| `TextHeight` | `.dfm` | Delphi designer's font-metric cache |
| `DesignSize = (W, H)` | `.dfm` | VCL-specific anchor-resize reference size |
| `DesignTimePPI` | `.lfm` | LCL's per-form DPI record (see above — the drift trigger) |
| `LCLVersion` | `.lfm` | IDE stamp |
| `ParentBackground = False` (on `TGroupBox`) | `.lfm` | LCL-only property |
| `EchoMode = emPassword` (alongside `PasswordChar`) | `.lfm` | LCL splits this into a separate property; VCL only has `PasswordChar` |
| `ClientHeight`/`ClientWidth` on child containers (not just the form) | `.lfm` | LCL serializes these on nested containers too |

None of this is a defect to "fix" — it's just what each designer considers
worth writing down. Don't try to make the two files property-identical;
they're independently maintained mirrors with genuinely different
serialization rules, not two views of one shared source.

## Runtime `{$IFDEF}` inside a form unit: what's actually needed

Every "big" form examined (those with real child controls) has the same
two-part pattern, and it's narrower than you might expect — it's not about
compensating colors or fonts at runtime:

```pascal
uses
  {$IFDEF FPC}
  LCLIntf, LCLType, LMessages,
  {$ELSE}
  Windows, Messages,
  {$ENDIF}
  ...;
```

and, right after the `{$R}` block:

```pascal
{$IFDEF FPC}
const
  // The LCL doesn't have the Messages unit; LM_VSCROLL has the same value as WM_VSCROLL.
  WM_VSCROLL = LM_VSCROLL;
{$ENDIF}
```

used later for something like `SendMessage(mmoLog.Handle, WM_VSCROLL,
SB_BOTTOM, 0)` (auto-scrolling a log `TMemo`). This is a real, narrow need:
resolving Win32-API-shaped message constants that the LCL names
differently. No color/font/sizing compensation logic was found in any of
the 10 samples — that category of problem lives entirely in the static
`.dfm`/`.lfm` files (the DPI drift above), not in runtime code.

## The strategy that sidesteps all of this: build the UI in `.pas`, skip `.dfm`/`.lfm` entirely

[`opcb-object-pascal-component-builder`](https://github.com/fabianoallex/opcb-object-pascal-component-builder)
exists specifically because of this problem — this isn't an inference, it's
stated directly:

> "One of the main advantages of OPCB is the ability to create components
> directly in code, eliminating the need for `.dfm` (Delphi) or `.lfm`
> (Lazarus) files. This way, all logic and component configuration remain
> centralized in `.pas` units... **Reduced version control conflicts:
> avoids common issues with `.dfm` or `.lfm` files in Git repositories.**"
> — `docs/doc.md`

The mechanism: a form's constructor calls `inherited CreateNew(AOwner)`
instead of the normal inherited `Create`. `CreateNew` is `TCustomForm`'s
constructor variant that skips loading a resource stream entirely, so no
`.dfm`/`.lfm` needs to exist — the Lazarus project's `.lpr` also has
`RequireDerivedFormResource := True` commented out (that directive normally
*forces* every form to have a matching `.lfm`). Controls are then added in
code:

```pascal
constructor TMainForm.Create(AOwner: TComponent);
begin
  // If we called the inherited Create, it would try to load the
  // associated .dfm, which doesn't exist in this case.
  inherited CreateNew(AOwner);
  WindowState := wsMaximized;
  ...
  Creator := TControlCreator.Create;
  try
    Creator.SetOwnerAndParent(Self, Self)
      .Add(TControlBuilder.Create(TButton).WithCaption('Button 1'))
      ...
  finally
    Creator.Free;
  end;
end;
```

`examples/Builders/VCL-Lazarus/no-dfm/UMainForm.pas` in that repo is the
concrete proof: the exact same `.pas` file, no `.dfm`/`.lfm` at all,
compiles and runs unmodified under both Delphi and Lazarus.

**This doesn't require going all-or-nothing.** `examples/Builders/Lazarus/
schema-driven-ui/unit1.lfm` shows a hybrid: static chrome (a toolbar panel,
menu) is still laid out in the normal `.lfm`, and only the part whose shape
is inherently dynamic (schema-driven form fields) is built at runtime via
`TControlCreator` inside that panel. The pattern scales down to "avoid the
designer only for the parts that would otherwise need manual per-compiler
resync," not "rewrite every form as code."

## Recommendation

- **When a form's content is dynamic, or the project can tolerate building
  chrome in code, prefer building it programmatically** (OPCB or a
  hand-rolled equivalent) over relying on two independently-maintained
  designer files. This is the only approach in these reference projects
  that eliminates the DPI-drift and reordering noise entirely, because
  there's only one source file.
- **When using the designer is clearly faster for a static layout, accept
  `.dfm`/`.lfm` but budget for the friction**: don't hand-edit either file
  expecting stability, expect large diffs after any designer save
  (especially across different-DPI machines), and don't review those diffs
  property-by-property as if divergence were a bug — verify visually
  instead.
- **Standardize the DPI/monitor scale used when editing forms**, if
  possible, across whoever touches the Lazarus side — it's the single
  biggest source of noisy, meaningless diffs observed here.
