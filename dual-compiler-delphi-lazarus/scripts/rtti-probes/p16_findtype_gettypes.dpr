program p16_findtype_gettypes;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TFoo = class end;
var Ctx: TRttiContext; T: TRttiType;
begin
  Ctx := TRttiContext.Create;
  T := Ctx.GetType(TFoo);
  Say('QualifiedName', T.QualifiedName);
  T := Ctx.FindType(T.QualifiedName);
  Say('FindType', BoolToStr(T <> nil, True));
  Say('GetTypes.count>0', BoolToStr(Length(Ctx.GetTypes) > 0, True));
end.
