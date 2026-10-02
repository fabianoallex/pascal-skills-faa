program p11_attributes_class_prop;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  TagAttribute = class(TCustomAttribute)
    FTag: string;
    constructor Create(const ATag: string);
  end;
  {$M+}
  [Tag('cls')]
  TC = class
  private FX, FY: Integer;
  public
    [Tag('pub')] property Y: Integer read FY write FY;
  published
    [Tag('prop')] property X: Integer read FX write FX;
  end;
  {$M-}
constructor TagAttribute.Create(const ATag: string); begin FTag := ATag; end;
function Tags(const A: TArray<TCustomAttribute>): string;
var I: Integer;
begin
  Result := '';
  for I := 0 to High(A) do
    if A[I] is TagAttribute then Result := Result + TagAttribute(A[I]).FTag + ' ';
  Result := '[' + Trim(Result) + ']';
end;
var Ctx: TRttiContext; T: TRttiType; P: TRttiProperty;
begin
  try
    Ctx := TRttiContext.Create;
    T := Ctx.GetType(TC);
    Say('class attrs', Tags(T.GetAttributes));
    Say('published prop attrs', Tags(T.GetProperty('X').GetAttributes));
    P := T.GetProperty('Y');
    if P = nil then Say('public prop', 'nil') else Say('public prop attrs', Tags(P.GetAttributes));
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
