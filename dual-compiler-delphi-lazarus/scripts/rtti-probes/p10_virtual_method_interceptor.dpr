program p10_virtual_method_interceptor;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  TC = class
  public function Val: Integer; virtual;
  end;
function TC.Val: Integer; begin Result := 1; end;
var VMI: TVirtualMethodInterceptor; O: TC;
begin
  O := TC.Create;
  VMI := TVirtualMethodInterceptor.Create(TC);
  VMI.OnBefore := procedure(Instance: TObject; Method: TRttiMethod; const Args: TArray<TValue>; out DoInvoke: Boolean; out Result: TValue)
    begin DoInvoke := False; Result := 99; end;
  VMI.Proxify(O);
  Say('O.Val (intercepted)', IntToStr(O.Val));
  VMI.Unproxify(O); O.Free; VMI.Free;
end.
