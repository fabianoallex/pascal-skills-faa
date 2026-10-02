program p23_dynarray_rtti_type;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TIntArr = array of Integer;
var Ctx: TRttiContext;
begin
  Ctx := TRttiContext.Create;
  Say('ElementType', (Ctx.GetType(TypeInfo(TIntArr)) as TRttiDynamicArrayType).ElementType.Name);
end.
