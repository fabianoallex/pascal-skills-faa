program p12_attributes_field_method;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  TagAttribute = class(TCustomAttribute)
    FTag: string;
    constructor Create(const ATag: string);
  end;
  TC = class
  public
    [Tag('field')] FX: Integer;
    [Tag('meth')] procedure M;
  end;
constructor TagAttribute.Create(const ATag: string); begin FTag := ATag; end;
procedure TC.M; begin end;
var Ctx: TRttiContext; T: TRttiType;
begin
  Ctx := TRttiContext.Create;
  T := Ctx.GetType(TC);
  Say('field attr', TagAttribute(T.GetField('FX').GetAttributes[0]).FTag);
  Say('method attr', TagAttribute(T.GetMethod('M').GetAttributes[0]).FTag);
end.
