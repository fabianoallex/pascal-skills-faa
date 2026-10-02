program p04_typekinds;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  TMyEnum = (meA, meB); TMySet = set of TMyEnum;
  TMyRec = record A: Integer; S: string; end;
  TIntArr = array of Integer;
  TStatArr = array[0..2] of Integer;
  TMyClass = class end;
  TMyClassRef = class of TMyClass;
  TFn = function(X: Integer): Integer;
procedure K(const N: string; T: PTypeInfo); begin Say(N, KindName(T^.Kind)); end;
begin
  K('Boolean', TypeInfo(Boolean)); K('ByteBool', TypeInfo(ByteBool));
  K('string', TypeInfo(string)); K('AnsiString', TypeInfo(AnsiString));
  K('UnicodeString', TypeInfo(UnicodeString)); K('WideString', TypeInfo(WideString));
  K('ShortString', TypeInfo(ShortString)); K('Char', TypeInfo(Char)); K('AnsiChar', TypeInfo(AnsiChar));
  K('Integer', TypeInfo(Integer)); K('Cardinal', TypeInfo(Cardinal));
  K('Int64', TypeInfo(Int64)); K('UInt64', TypeInfo(UInt64));
  K('Single', TypeInfo(Single)); K('Double', TypeInfo(Double)); K('Extended', TypeInfo(Extended));
  K('Currency', TypeInfo(Currency)); K('Comp', TypeInfo(Comp));
  K('Variant', TypeInfo(Variant));
  K('enum', TypeInfo(TMyEnum)); K('set', TypeInfo(TMySet)); K('record', TypeInfo(TMyRec));
  K('dynarray', TypeInfo(TIntArr)); K('TBytes', TypeInfo(TBytes)); K('static array', TypeInfo(TStatArr));
  K('class', TypeInfo(TMyClass)); K('IInterface', TypeInfo(IInterface));
  K('TNotifyEvent', TypeInfo(TNotifyEvent));
  K('class of', TypeInfo(TMyClassRef)); K('Pointer', TypeInfo(Pointer));
  K('procvar', TypeInfo(TFn));
end.
