program p19_rtti_directive;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$RTTI EXPLICIT METHODS([vcPrivate..vcPublished]) PROPERTIES([vcPrivate..vcPublished]) FIELDS([vcPrivate..vcPublished])}
  TC = class
  private procedure PrivM;
  public procedure PubM;
  end;
procedure TC.PrivM; begin end;
procedure TC.PubM; begin end;
var Ctx: TRttiContext; M: TRttiMethod; S: string;
begin
  Ctx := TRttiContext.Create; S := '';
  for M in Ctx.GetType(TC).GetDeclaredMethods do S := S + M.Name + ':' + VisName(M.Visibility) + ' ';
  Say('GetDeclaredMethods', '[' + Trim(S) + ']');
end.
