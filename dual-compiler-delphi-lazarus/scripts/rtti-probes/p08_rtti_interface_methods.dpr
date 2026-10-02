program p08_rtti_interface_methods;
{$I hdr.inc}
uses {$I uses.inc};
{$I util.inc}
type
  {$M+}
  IFoo = interface
    ['{6E7D1B6A-2C1F-4C64-9F4C-1D7F7B2E3A10}']
    function Add(A, B: Integer): Integer;
    function Greet(const Name: string): string;
  end;
  {$M-}
  TFoo = class(TInterfacedObject, IFoo)
    function Add(A, B: Integer): Integer;
    function Greet(const Name: string): string;
  end;
function TFoo.Add(A, B: Integer): Integer; begin Result := A + B; end;
function TFoo.Greet(const Name: string): string; begin Result := 'hi ' + Name; end;
var Ctx: TRttiContext; T: TRttiType; M: TRttiMethod; P: TRttiParameter; S: string; F: IFoo; V: TValue;
begin
  try
    Ctx := TRttiContext.Create;
    T := Ctx.GetType(TypeInfo(IFoo));
    for M in T.GetDeclaredMethods do
    begin
      S := '';
      for P in M.GetParameters do S := S + P.Name + ':' + P.ParamType.Name + ' ';
      Say('method.' + M.Name, 'params[' + Trim(S) + '] returns ' + M.ReturnType.Name);
    end;
    F := TFoo.Create;
    TValue.Make(@F, TypeInfo(IFoo), V);
    Say('Invoke Add(2,3)', T.GetMethod('Add').Invoke(V, [2, 3]).ToString);
    Say('Invoke Greet', T.GetMethod('Greet').Invoke(V, ['bob']).AsString);
  except on E: Exception do Say('EXCEPTION', E.ClassName + ': ' + E.Message); end;
end.
