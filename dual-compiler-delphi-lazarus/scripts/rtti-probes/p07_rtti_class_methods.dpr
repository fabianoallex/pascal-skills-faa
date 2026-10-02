program p07_rtti_class_methods;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  TC = class
  private procedure PrivM;
  protected procedure ProtM;
  public function Add(A, B: Integer): Integer;
  published procedure PublM;
  end;
  {$M-}
procedure TC.PrivM; begin end;
procedure TC.ProtM; begin end;
function TC.Add(A, B: Integer): Integer; begin Result := A + B; end;
procedure TC.PublM; begin end;
var Ctx: TRttiContext; M: TRttiMethod; S: string; O: TC;
begin
  try
    Ctx := TRttiContext.Create;
    S := '';
    for M in Ctx.GetType(TC).GetDeclaredMethods do S := S + M.Name + ':' + VisName(M.Visibility) + ' ';
    Say('TC.GetDeclaredMethods', '[' + Trim(S) + ']');
    Say('TC.GetMethods.count(incl. inherited)', IntToStr(Length(Ctx.GetType(TC).GetMethods)));
    M := Ctx.GetType(TC).GetMethod('Add');
    if M = nil then Say('GetMethod(Add)', 'nil')
    else begin
      O := TC.Create;
      Say('Add.ToString', M.ToString);
      Say('Invoke Add(2,3)', M.Invoke(O, [2, 3]).ToString);
      O.Free;
    end;
    Say('MethodAddress(PublM)<>nil', BoolToStr(TC.MethodAddress('PublM') <> nil, True));
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
