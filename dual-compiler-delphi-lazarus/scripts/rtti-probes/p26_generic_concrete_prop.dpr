program p26_generic_concrete_prop;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  TBox<T> = class
  private FValue: T; FCount: Integer;
  public property Value: T read FValue write FValue;
  published property Count: Integer read FCount write FCount;
  end;
  {$M-}
  TIntBox = TBox<Integer>;
var Ctx: TRttiContext; Ty: TRttiType; Pr: TRttiProperty; S: string;
begin
  try
    Ctx := TRttiContext.Create;
    Ty := Ctx.GetType(TIntBox);
    Say('Name', Ty.Name);
    S := '';
    for Pr in Ty.GetProperties do S := S + Pr.Name + ':' + Pr.PropertyType.Name + ' ';
    Say('GetProperties', '[' + Trim(S) + ']');
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
