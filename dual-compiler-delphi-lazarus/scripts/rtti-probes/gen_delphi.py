"""Generate a single Delphi project that runs every RTTI probe, for Delphi editions
that can't build from the command line (Community Edition).

Each p*.dpr probe becomes a unit exposing `procedure Run;`, and delphi_side/
rtti_delphi.dpr calls them all, writing the combined output to
delphi_results.txt next to this script. Open delphi_side/rtti_delphi.dproj (not
the .dpr) in the IDE, pick Win32 or Win64, and run it once.

The .dproj comes from scaffold_dual_project.py's template on purpose: when the
Delphi 12 CE IDE creates a .dproj for a bare .dpr itself, it lists no Win64
platform at all, and the IDE then offers no way to add one.
"""
import glob, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'delphi_side')
# Left out of the combined project because they fail to compile on Delphi
# (FPC-only syntax, or a restriction both compilers share) or touch API whose
# Delphi signature wasn't known up front -- one failing unit would stop the whole
# build. Compile these standalone .dpr files in the IDE one at a time instead.
SKIP = {'p02_proptype_fpc_style', 'p18_enum_explicit_values', 'p20_generic_class',
        'p24_typedata_unitname'}

sys.path.insert(0, os.path.dirname(HERE))
import scaffold_dual_project as scaffold  # noqa: E402

os.makedirs(OUT, exist_ok=True)
for inc in ('uses.inc', 'util.inc'):
    shutil.copy(os.path.join(HERE, inc), OUT)

names = []
for src in sorted(glob.glob(os.path.join(HERE, 'p*.dpr'))):
    name = os.path.splitext(os.path.basename(src))[0]
    if name in SKIP:
        continue
    lines = open(src, encoding='utf-8').read().splitlines()
    lines = [l for l in lines if '{$I hdr.inc}' not in l and '{$APPTYPE' not in l
             and not l.startswith('{$IFDEF FPC}{$MODE')]
    assert lines[0].startswith('program ')
    lines[0] = 'unit %s;\n\ninterface\n\nprocedure Run;\n\nimplementation\n' % name
    # The program's main block is the last column-0 `begin`; method bodies come before it.
    main_begin = max(i for i, l in enumerate(lines) if l == 'begin')
    lines[main_begin] = 'procedure Run;\nbegin'
    assert lines[-1] == 'end.'
    lines[-1] = 'end;\n\nend.'
    open(os.path.join(OUT, name + '.pas'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    names.append(name)

results_path = os.path.join(HERE, 'delphi_results.txt')
prog = ['program rtti_delphi;', '', '{$APPTYPE CONSOLE}', '', 'uses', '  System.SysUtils,']
prog += ['  %s in \'%s.pas\'%s' % (n, n, ',' if i < len(names) - 1 else ';') for i, n in enumerate(names)]
prog += ['',
         'procedure Probe(const Name: string; P: TProc);',
         'begin',
         "  WriteLn('==== ', Name);",
         "  try P except on E: Exception do WriteLn('UNCAUGHT=', E.ClassName, ': ', E.Message); end;",
         'end;',
         '',
         'begin',
         "  AssignFile(Output, '%s');" % results_path,
         '  Rewrite(Output);',
         "  WriteLn('platform=', {$IFDEF WIN64}'Win64'{$ELSE}'Win32'{$ENDIF}, ' CompilerVersion=', FloatToStr(CompilerVersion));"]
prog += ["  Probe('%s', %s.Run);" % (n, n) for n in names]
prog += ['  CloseFile(Output);', 'end.', '']
open(os.path.join(OUT, 'rtti_delphi.dpr'), 'w', encoding='utf-8').write('\n'.join(prog))

dproj = os.path.join(OUT, 'rtti_delphi.dproj')
if not os.path.exists(dproj):  # keep the GUID stable across regenerations
    open(dproj, 'w', encoding='utf-8').write(scaffold.render(
        scaffold.DPROJ_TEMPLATE, GUID=scaffold.new_guid(), NAME='rtti_delphi', SRC_REL='.'))

print('Generated %d probe units in %s' % (len(names), OUT))
print('Open delphi_side\\rtti_delphi.dproj in the IDE and run it; output goes to %s' % results_path)
