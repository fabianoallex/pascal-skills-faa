program p20_generic_class;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  TBox<T> = class
  private FValue: T;
  published property Value: T read FValue write FValue;
  end;
  {$M-}
  TIntBox = TBox<Integer>;
var Ctx: TRttiContext; Ty: TRttiType; B: TIntBox;
begin
  try
    Ctx := TRttiContext.Create;
    Ty := Ctx.GetType(TIntBox);
    Say('Name', Ty.Name);
    Say('prop Value type', Ty.GetProperty('Value').PropertyType.Name);
    B := TIntBox.Create; Ty.GetProperty('Value').SetValue(B, 11);
    Say('Value after SetValue', IntToStr(B.Value)); B.Free;
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
