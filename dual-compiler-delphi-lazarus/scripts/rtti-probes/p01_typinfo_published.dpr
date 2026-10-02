program p01_typinfo_published;
{$I hdr.inc}
uses {$I uses.inc}, {$IFDEF FPC}Variants{$ELSE}System.Variants{$ENDIF};
{$I util.inc}
type
  TMyEnum = (meA, meB, meC);
  TMySet = set of TMyEnum;
  {$M+}
  TP = class
  private
    FName: string; FCount: Integer; FFlag: Boolean; FA: AnsiString; FU: UInt64;
    FE: TMyEnum; FW: WideString; FS: ShortString; FC: Char; FD: Double; FI64: Int64;
    FSet: TMySet; FObj: TObject; FEv: TNotifyEvent; FPub: Integer;
  public
    property PublicOnly: Integer read FPub write FPub;
  published
    property Name: string read FName write FName;
    property Count: Integer read FCount write FCount;
    property Flag: Boolean read FFlag write FFlag;
    property A: AnsiString read FA write FA;
    property U: UInt64 read FU write FU;
    property E: TMyEnum read FE write FE;
    property W: WideString read FW write FW;
    property S: ShortString read FS write FS;
    property C: Char read FC write FC;
    property D: Double read FD write FD;
    property I64: Int64 read FI64 write FI64;
    property SetP: TMySet read FSet write FSet;
    property Obj: TObject read FObj write FObj;
    property Ev: TNotifyEvent read FEv write FEv;
  end;
  {$M-}
var P: TP; L: PPropList; N, i: Integer; PI: PPropInfo; TI: PTypeInfo;
begin
  try
    P := TP.Create;
    N := GetPropList(PTypeInfo(P.ClassInfo), L);
    Say('count', IntToStr(N));
    for i := 0 to N - 1 do
    begin
      PI := L^[i];
      TI := PI^.PropType{$IFNDEF FPC}^{$ENDIF};
      Say('kind.' + string(PI^.Name), KindName(TI^.Kind));
    end;
    FreeMem(L);
    Say('public_prop_visible_to_typinfo', BoolToStr(GetPropInfo(P, 'PublicOnly') <> nil, True));
    SetStrProp(P, 'Name', 'abc'); Say('GetStrProp', GetStrProp(P, 'Name'));
    SetOrdProp(P, 'Count', 42); Say('GetOrdProp', IntToStr(GetOrdProp(P, 'Count')));
    SetEnumProp(P, 'E', 'meC'); Say('GetEnumProp', GetEnumProp(P, 'E'));
    SetSetProp(P, 'SetP', '[meA,meC]'); Say('GetSetProp', GetSetProp(P, 'SetP', True));
    SetPropValue(P, 'Flag', True); Say('GetPropValue.Flag', VarToStr(GetPropValue(P, 'Flag')));
    SetInt64Prop(P, 'I64', 1234567890123); Say('GetInt64Prop', IntToStr(GetInt64Prop(P, 'I64')));
    SetFloatProp(P, 'D', 1.5); Say('GetFloatProp', FloatToStr(GetFloatProp(P, 'D')));
    Say('GetEnumName', GetEnumName(TypeInfo(TMyEnum), 1));
    Say('GetEnumValue', IntToStr(GetEnumValue(TypeInfo(TMyEnum), 'meC')));
    Say('IsPublishedProp', BoolToStr(IsPublishedProp(P, 'Name'), True));
    Say('PropIsType.Flag.tkBool?', BoolToStr(PropIsType(P, 'Flag', tkEnumeration), True));
    P.Free;
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
