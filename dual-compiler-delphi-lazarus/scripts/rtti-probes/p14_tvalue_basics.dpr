program p14_tvalue_basics;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type TR = record A: Integer; B: string; end;
var V: TValue; I: Integer; S: string; R, R2: TR;
begin
  try
    V := 5; Say('implicit Integer.Kind', KindName(V.Kind)); Say('AsInteger', IntToStr(V.AsInteger));
    V := 'abc'; Say('implicit string.Kind', KindName(V.Kind)); Say('AsString', V.AsString);
    I := 42; V := TValue.From<Integer>(I); Say('From<Integer>.ToString', V.ToString);
    S := 'gen'; V := TValue.From<string>(S); Say('From<string>.AsString', V.AsString);
    R.A := 7; R.B := 'rec'; V := TValue.From<TR>(R); Say('From<TR>.Kind', KindName(V.Kind));
    V.ExtractRawData(@R2); Say('ExtractRawData.B', R2.B);
    Say('IsType<TR>', BoolToStr(V.IsType<TR>, True));
    V := TValue.Empty; Say('Empty.IsEmpty', BoolToStr(V.IsEmpty, True));
    V := True; Say('implicit Boolean.Kind', KindName(V.Kind));
    try V := 'abc'; Say('string.AsInteger', IntToStr(V.AsInteger));
    except on E: Exception do Say('string.AsInteger raises', E.ClassName); end;
    try V := 5; Say('Integer.AsString', V.AsString);
    except on E: Exception do Say('Integer.AsString raises', E.ClassName); end;
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
