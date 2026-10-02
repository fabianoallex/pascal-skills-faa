program p18_enum_explicit_values;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TE = (eA = 1, eB = 5);
begin
  Say('TypeInfo(TE).Kind', KindName(PTypeInfo(TypeInfo(TE))^.Kind));
  Say('GetEnumName(TE,5)', GetEnumName(TypeInfo(TE), 5));
end.
