program p25_reference_to_typeinfo;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TRefFn = reference to function(X: Integer): Integer;
begin
  Say('reference to.Kind', KindName(PTypeInfo(TypeInfo(TRefFn))^.Kind));
end.
