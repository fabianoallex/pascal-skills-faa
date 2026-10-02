program p27_string_kind_by_mode;
{$IFDEF FPC}{$MODE DELPHIUNICODE}{$ENDIF}
{$APPTYPE CONSOLE}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  TP = class
  private FName: string;
  published property Name: string read FName write FName;
  end;
  {$M-}
var V: TValue;
begin
  Say('TypeInfo(string).Kind', KindName(PTypeInfo(TypeInfo(string))^.Kind));
  Say('published string prop kind', KindName(GetPropInfo(TP, 'Name')^.PropType{$IFNDEF FPC}^{$ENDIF}^.Kind));
  V := 'x'; Say('TValue := literal .Kind', KindName(V.Kind));
  Say('SizeOf(Char)', IntToStr(SizeOf(Char)));
end.
