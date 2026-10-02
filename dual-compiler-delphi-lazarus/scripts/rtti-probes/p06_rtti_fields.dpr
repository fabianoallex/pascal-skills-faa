program p06_rtti_fields;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  TC = class
  private FPriv: Integer;
  protected FProt: string;
  public FPub: Double;
  end;
var Ctx: TRttiContext; F: TRttiField; S: string;
begin
  Ctx := TRttiContext.Create;
  S := '';
  for F in Ctx.GetType(TC).GetFields do S := S + F.Name + ':' + VisName(F.Visibility) + ' ';
  Say('TC.GetFields', Trim(S));
end.
