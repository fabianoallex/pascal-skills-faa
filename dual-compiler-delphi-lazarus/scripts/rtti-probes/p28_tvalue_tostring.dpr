program p28_tvalue_tostring;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  TMyEnum = (meA, meB); TMySet = set of TMyEnum;
  TR = record A: Integer; end;
  TIntArr = array of Integer;
var V: TValue; D: Double; St: TMySet; R: TR; A: TIntArr; O: TObject;
begin
  try
    D := 1.5; V := TValue.From<Double>(D); Say('Double.ToString', V.ToString); Say('Double.AsExtended', FloatToStr(V.AsExtended));
    St := [meB]; V := TValue.From<TMySet>(St); Say('Set.ToString', V.ToString);
    R.A := 1; V := TValue.From<TR>(R); Say('Record.ToString', V.ToString);
    SetLength(A, 2); V := TValue.From<TIntArr>(A); Say('DynArray.ToString', V.ToString);
    O := TObject.Create; V := O; Say('Object.ToString', V.ToString); O.Free;
    V := TValue.From<TMyEnum>(meB); Say('From<Enum>.ToString', V.ToString);
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
