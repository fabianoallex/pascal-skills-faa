procedure Say(const K, V: string); begin WriteLn(K, '=', V); end;
function KindName(K: TTypeKind): string; begin Result := GetEnumName(TypeInfo(TTypeKind), Ord(K)); end;
function VisName(V: TMemberVisibility): string; begin Result := GetEnumName(TypeInfo(TMemberVisibility), Ord(V)); end;
