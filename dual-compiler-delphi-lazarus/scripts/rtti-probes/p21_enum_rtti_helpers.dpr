program p21_enum_rtti_helpers;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TMyEnum = (meA, meB, meC);
begin
  Say('GetName<T>', TRttiEnumerationType.GetName<TMyEnum>(meB));
  Say('GetValue<T>', IntToStr(Ord(TRttiEnumerationType.GetValue<TMyEnum>('meC'))));
end.
