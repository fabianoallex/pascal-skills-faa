"""Writes a Windows .res file embedding arbitrary files as RCDATA resources,
without brcc32, windres or a C preprocessor — on any OS.

Why this exists: both Delphi and FPC link a 32-bit .res with {$R file.res}
and read it back with FindResource/TResourceStream, on every platform FPC
targets. What is NOT portable is producing it from a .rc: Delphi has brcc32;
FPC on Windows calls the windres that ships with Lazarus; FPC on Linux fails
with 'resource compiler "windres" not found', and installing the MinGW
binutils alone still fails because windres preprocesses the .rc with
x86_64-w64-mingw32-gcc. Writing the .res directly sidesteps all of that.

Verified (FPC 3.2.2 / Lazarus 4.0 / Delphi 12 CE): the output is
byte-for-byte what windres produces for the equivalent .rc
('NAME RCDATA "file"'), links and loads on Delphi, FPC/Windows and
FPC/Linux, preserves the bytes exactly (UTF-8 included), and FindResource
matches names case-insensitively. Real use: pascal-db-faa's
tools/build_sql_res.py (a tree-of-.sql variant of this script).

Usage:
    python build_rcdata_res.py OUT.res NAME=FILE [NAME=FILE ...]
    python build_rcdata_res.py OUT.res NAME=FILE ... --check   (exit 1 if OUT.res
                                                               is missing or stale)
Resource names are upper-cased (Windows stores string names that way).
"""
import struct
import sys
from pathlib import Path

RT_RCDATA = 10
MEMORY_FLAGS = 0x1030   # MOVEABLE | PURE | DISCARDABLE — what windres/brcc32 emit
LANGUAGE = 0x0409       # en-US, windres' default

# A 32-bit .res starts with an empty 32-byte entry (the format signature).
RES_SIGNATURE = struct.pack('<IIHHHHIHHII', 0, 32, 0xFFFF, 0, 0xFFFF, 0, 0, 0, 0, 0, 0)


def pad4(data):
    return data + b'\0' * (-len(data) % 4)


def res_entry(name, data):
    header = struct.pack('<HH', 0xFFFF, RT_RCDATA) + (name + '\0').encode('utf-16-le')
    header = pad4(header) + struct.pack('<IHHII', 0, MEMORY_FLAGS, LANGUAGE, 0, 0)
    return pad4(struct.pack('<II', len(data), 8 + len(header)) + header + data)


def build(pairs):
    entries = {}
    for pair in pairs:
        name, sep, path = pair.partition('=')
        if not sep or not name or not path:
            raise SystemExit(f'build_rcdata_res: expected NAME=FILE, got {pair!r}')
        name = name.upper()
        if name in entries:
            raise SystemExit(f'build_rcdata_res: duplicate resource name {name}')
        entries[name] = Path(path).read_bytes()
    return RES_SIGNATURE + b''.join(res_entry(n, entries[n]) for n in sorted(entries)), len(entries)


def main():
    args = [a for a in sys.argv[1:] if a != '--check']
    check = '--check' in sys.argv
    if len(args) < 2:
        raise SystemExit(__doc__)
    out = Path(args[0])
    data, count = build(args[1:])
    current = out.read_bytes() if out.exists() else None
    if check:
        if current != data:
            print(f'{out} is {"missing" if current is None else "out of date"}')
            sys.exit(1)
        print(f'{out} is up to date ({count} resources)')
    elif current != data:
        out.write_bytes(data)
        print(f'{out}: written ({count} resources)')
    else:
        print(f'{out}: unchanged ({count} resources)')


if __name__ == '__main__':
    main()
