program p24_typedata_unitname;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+} TP = class end; {$M-}
begin
  Say('TypeData.UnitName', string(GetTypeData(TypeInfo(TP))^.UnitName));
  Say('TypeData.ClassType', GetTypeData(TypeInfo(TP))^.ClassType.ClassName);
end.
