program p17_instance_type;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TFoo = class(TStringList) end;
var Ctx: TRttiContext; T: TRttiInstanceType; O: TObject;
begin
  try
    Ctx := TRttiContext.Create;
    T := Ctx.GetType(TFoo).AsInstance;
    Say('Name', T.Name);
    Say('DeclaringUnitName', T.DeclaringUnitName);
    Say('MetaclassType', T.MetaclassType.ClassName);
    Say('BaseType', T.BaseType.Name);
    Say('IsInstance', BoolToStr(Ctx.GetType(TFoo).IsInstance, True));
    O := T.MetaclassType.Create; Say('MetaclassType.Create', O.ClassName); O.Free;
    Say('TypeKind(Integer)', KindName(Ctx.GetType(TypeInfo(Integer)).TypeKind));
    Say('IsOrdinal(Integer)', BoolToStr(Ctx.GetType(TypeInfo(Integer)).IsOrdinal, True));
    Say('IsManaged(string)', BoolToStr(Ctx.GetType(TypeInfo(string)).IsManaged, True));
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
