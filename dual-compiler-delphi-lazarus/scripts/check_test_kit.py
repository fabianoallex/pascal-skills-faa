"""Checks a project's copy of the test kit against this skill's canonical one,
or installs it.

The kit is two files every *-faa project used to copy from its neighbour
(eight copies by 2026-10-19, identical but for names):
  - tools/gen_fpc_mirror.py: must be byte-for-byte scripts/gen_fpc_mirror.py;
  - tests/Unit/<Prefix>.DUnitXCompat.pas: from "interface" down, the same as
    assets/DUnitXCompat.pas.template (the unit name and the top comment are
    the project's).

Usage:
  python check_test_kit.py <project>                    report; exit 1 on drift
  python check_test_kit.py <project> --install <Prefix> write both files
      (tools/gen_fpc_mirror.py and tests/Unit/<Prefix>.DUnitXCompat.pas);
      an existing compat unit keeps its own top comment
Comparison ignores line endings and a UTF-8 BOM.
"""
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CANON_GEN = SKILL / 'scripts' / 'gen_fpc_mirror.py'
TEMPLATE = SKILL / 'assets' / 'DUnitXCompat.pas.template'


def read(path):
    return path.read_text(encoding='utf-8-sig').replace('\r\n', '\n')


def body_from_interface(text):
    i = text.find('\ninterface\n')
    return text[i:] if i >= 0 else None


def compat_units(project):
    unit_dir = project / 'tests' / 'Unit'
    return sorted(unit_dir.glob('*.DUnitXCompat.pas')) if unit_dir.is_dir() else []


def check(project):
    problems = []
    gen = project / 'tools' / 'gen_fpc_mirror.py'
    if not gen.exists():
        problems.append('tools/gen_fpc_mirror.py is missing')
    elif read(gen) != read(CANON_GEN):
        problems.append('tools/gen_fpc_mirror.py differs from the skill\'s scripts/gen_fpc_mirror.py')
    units = compat_units(project)
    if not units:
        problems.append('no tests/Unit/<Prefix>.DUnitXCompat.pas')
    want = body_from_interface(read(TEMPLATE))
    for unit in units:
        if body_from_interface(read(unit)) != want:
            problems.append(f'{unit.relative_to(project).as_posix()}: differs from the template '
                            'below "interface"')
    return problems


def install(project, prefix):
    (project / 'tools').mkdir(exist_ok=True)
    (project / 'tools' / 'gen_fpc_mirror.py').write_text(read(CANON_GEN), encoding='utf-8',
                                                         newline='\n')
    unit_dir = project / 'tests' / 'Unit'
    unit_dir.mkdir(parents=True, exist_ok=True)
    target = unit_dir / f'{prefix}.DUnitXCompat.pas'
    template = read(TEMPLATE).replace('{{UNIT}}', f'{prefix}.DUnitXCompat')
    if target.exists():
        # Keep the project's unit line and top comment, take the template's body.
        current = read(target)
        head = current[:current.find('\ninterface\n')]
        template = head + body_from_interface(template)
    # Delphi reads a BOM-less .pas as ANSI: keep the BOM the family uses.
    target.write_text(template, encoding='utf-8-sig', newline='\n')
    print(f'installed tools/gen_fpc_mirror.py and {target.relative_to(project).as_posix()}')


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    project = Path(sys.argv[1]).resolve()
    if len(sys.argv) == 4 and sys.argv[2] == '--install':
        install(project, sys.argv[3])
    problems = check(project)
    for p in problems:
        print('DRIFT:', p)
    if problems:
        sys.exit(1)
    print('test kit: same as the skill\'s')


if __name__ == '__main__':
    main()
