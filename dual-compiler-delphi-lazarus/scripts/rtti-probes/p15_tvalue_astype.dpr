program p15_tvalue_astype;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
var V: TValue; I: Integer; S: string;
begin
  V := 5; I := V.AsType<Integer>; Say('AsType<Integer>', IntToStr(I));
  Say('TryAsType<string>', BoolToStr(V.TryAsType<string>(S), True));
end.
