program p02_proptype_fpc_style;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  TP = class
  private FCount: Integer;
  published property Count: Integer read FCount write FCount;
  end;
var TI: PTypeInfo;
begin
  TI := GetPropInfo(TP, 'Count')^.PropType;
  Say('PropType.Name', string(TI^.Name));
end.
