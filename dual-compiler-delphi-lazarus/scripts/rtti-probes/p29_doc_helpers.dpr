program p29_doc_helpers;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
function IsStringKind(K: TTypeKind): Boolean;
begin
  Result := K in [{$IFDEF FPC}tkSString, tkAString{$ELSE}tkString{$ENDIF}, tkLString, tkWString, tkUString];
end;
function IsBooleanType(T: PTypeInfo): Boolean;
begin
  Result := T = TypeInfo(Boolean);
end;
type
  {$M+}
  TP = class
  private FFlag: Boolean; FName: string; FN: Integer;
  published
    property Flag: Boolean read FFlag write FFlag;
    property Name: string read FName write FName;
    property N: Integer read FN write FN;
  end;
  {$M-}
function PT(const P: string): PTypeInfo; begin Result := GetPropInfo(TP, P)^.PropType{$IFNDEF FPC}^{$ENDIF}; end;
begin
  Say('IsBooleanType(Flag)', BoolToStr(IsBooleanType(PT('Flag')), True));
  Say('IsBooleanType(N)', BoolToStr(IsBooleanType(PT('N')), True));
  Say('IsStringKind(Name)', BoolToStr(IsStringKind(PT('Name')^.Kind), True));
  Say('IsStringKind(N)', BoolToStr(IsStringKind(PT('N')^.Kind), True));
  Say('IsStringKind(AnsiString)', BoolToStr(IsStringKind(PTypeInfo(TypeInfo(AnsiString))^.Kind), True));
  Say('IsStringKind(ShortString)', BoolToStr(IsStringKind(PTypeInfo(TypeInfo(ShortString))^.Kind), True));
end.
