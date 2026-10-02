program p05_rtti_properties;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  TC = class
  private
    FPriv, FProt, FPub, FPubl: Integer;
    property PrivProp: Integer read FPriv write FPriv;
  protected
    property ProtProp: Integer read FProt write FProt;
  public
    property PubProp: Integer read FPub write FPub;
  published
    property PublProp: Integer read FPubl write FPubl;
  end;
  {$M-}
  TNoM = class
  private FX: Integer;
  public property X: Integer read FX write FX;
  end;
var Ctx: TRttiContext; T: TRttiType; Pr: TRttiProperty; O: TC; S: string;
begin
  try
    Ctx := TRttiContext.Create;
    T := Ctx.GetType(TC); O := TC.Create;
    S := '';
    for Pr in T.GetProperties do S := S + Pr.Name + ':' + VisName(Pr.Visibility) + ' ';
    Say('TC.GetProperties', Trim(S));
    Pr := T.GetProperty('PublProp');
    if Pr <> nil then begin Pr.SetValue(O, 7); Say('PublProp.GetValue', Pr.GetValue(O).ToString); end;
    Pr := T.GetProperty('PubProp');
    if Pr <> nil then begin Pr.SetValue(O, 8); Say('PubProp.GetValue', Pr.GetValue(O).ToString); end
    else Say('PubProp', 'nil');
    Say('PublProp.PropertyType', T.GetProperty('PublProp').PropertyType.Name);
    S := '';
    for Pr in Ctx.GetType(TNoM).GetProperties do S := S + Pr.Name + ' ';
    Say('TNoM(no $M+).GetProperties', '[' + Trim(S) + ']');
    Say('TStringList.GetProperties.count', IntToStr(Length(Ctx.GetType(TStringList).GetProperties)));
    O.Free;
    Ctx.Free;
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
