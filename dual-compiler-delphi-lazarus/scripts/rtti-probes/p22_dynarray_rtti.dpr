program p22_dynarray_rtti;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TIntArr = array of Integer;
var A: TIntArr; V: TValue;
begin
  try
    SetLength(A, 3); A[2] := 9; V := TValue.From<TIntArr>(A);
    Say('IsArray', BoolToStr(V.IsArray, True));
    Say('GetArrayLength', IntToStr(V.GetArrayLength));
    Say('GetArrayElement(2)', V.GetArrayElement(2).ToString);
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
