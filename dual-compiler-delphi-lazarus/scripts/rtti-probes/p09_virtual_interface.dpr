program p09_virtual_interface;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  IFoo = interface
    ['{6E7D1B6A-2C1F-4C64-9F4C-1D7F7B2E3A11}']
    function Add(A, B: Integer): Integer;
  end;
  {$M-}
  THandler = class
    procedure DoInvoke(Method: TRttiMethod; const Args: TArray<TValue>; out Result: TValue);
  end;
procedure THandler.DoInvoke(Method: TRttiMethod; const Args: TArray<TValue>; out Result: TValue);
begin
  Say('handler.Method', Method.Name);
  Say('handler.Length(Args)', IntToStr(Length(Args)));
  Result := Args[High(Args) - 1].AsInteger + Args[High(Args)].AsInteger;
end;
var H: THandler; VI: IInterface; F: IFoo;
begin
  try
    H := THandler.Create;
    VI := TVirtualInterface.Create(TypeInfo(IFoo), H.DoInvoke);
    if Supports(VI, IFoo, F) then Say('F.Add(2,3)', IntToStr(F.Add(2, 3)))
    else Say('Supports', 'False');
    F := nil; VI := nil; H.Free;
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
