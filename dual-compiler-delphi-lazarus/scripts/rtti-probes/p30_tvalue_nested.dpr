program p30_tvalue_nested;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TValArr = TArray<TValue>;
var A: TValArr; V, E: TValue; O: TObject;
begin
  try
    O := TObject.Create;
    SetLength(A, 2); A[0] := O; A[1] := 7;
    V := TValue.From<TValArr>(A);
    E := V.GetArrayElement(0);
    Say('elem0.Kind', KindName(E.Kind));
    Say('elem0.IsObject', BoolToStr(E.IsObject, True));
    Say('elem0 is TValue-in-TValue', BoolToStr((E.Kind = tkRecord) and (E.TypeInfo = TypeInfo(TValue)), True));
    Say('TypeInfo(TArray<TValue>) = TypeInfo(TValArr)', BoolToStr(TypeInfo(TArray<TValue>) = TypeInfo(TValArr), True));
    O.Free;
  except on Ex: Exception do Say('EXCEPTION', Ex.ClassName + ': ' + Ex.Message); end;
end.
