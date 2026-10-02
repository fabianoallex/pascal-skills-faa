program p13_record_fields;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TR = record A: Integer; B: string; end;
var Ctx: TRttiContext; F: TRttiField; S: string; R: TR;
begin
  Ctx := TRttiContext.Create;
  S := '';
  for F in Ctx.GetType(TypeInfo(TR)).GetFields do S := S + F.Name + ':' + F.FieldType.Name + ' ';
  Say('TR.GetFields', Trim(S));
  Ctx.GetType(TypeInfo(TR)).GetField('B').SetValue(@R, 'xyz');
  Say('R.B after SetValue', R.B);
end.
