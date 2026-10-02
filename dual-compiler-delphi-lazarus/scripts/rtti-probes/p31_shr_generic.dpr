program p31_shr_generic;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
var A: TArray<TValue>; V: TValue;
begin
  V := TValue.From<TArray<TValue>>(A);
  Say('Kind', KindName(V.Kind));
end.
