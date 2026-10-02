"""Generate a Delphi project group with one project per RTTI probe, for a
"Build All" in the IDE (Delphi Community Edition can't build from the command line).

Unlike gen_delphi.py, which merges the probes into a single runner, this builds
every probe .dpr exactly as FPC does -- same source, one program each -- so a
probe that fails to compile only fails its own project. The executables land
in Win32/Debug (or Win64/Debug) next to this script, ready to be run and
diffed against the FPC output.

Probes expected to fail on Delphi go last in the group, so if the IDE stops at
the first failing project, everything else has already been built.
"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
GROUP = os.path.join(HERE, 'RttiProbes.groupproj')
# Recorded as compile failures on Delphi 12 in rtti-gotchas.md.
EXPECTED_TO_FAIL = ['p02_proptype_fpc_style', 'p18_enum_explicit_values']

sys.path.insert(0, os.path.dirname(HERE))
import scaffold_dual_project as scaffold  # noqa: E402

names = [os.path.splitext(os.path.basename(p))[0] for p in sorted(glob.glob(os.path.join(HERE, 'p*.dpr')))]
names = [n for n in names if n not in EXPECTED_TO_FAIL] + [n for n in EXPECTED_TO_FAIL if n in names]

for n in names:
    dproj = os.path.join(HERE, n + '.dproj')
    if not os.path.exists(dproj):  # keep GUIDs stable across regenerations
        open(dproj, 'w', encoding='utf-8-sig').write(scaffold.render(
            scaffold.DPROJ_TEMPLATE, GUID=scaffold.new_guid(), NAME=n, SRC_REL='.'))
        scaffold.validate_xml(dproj)

items = ''.join('        <Projects Include="%s.dproj">\n            <Dependencies/>\n        </Projects>\n' % n
                for n in names)
targets = ''.join(
    '    <Target Name="{0}">\n        <MSBuild Projects="{0}.dproj"/>\n    </Target>\n'
    '    <Target Name="{0}:Clean">\n        <MSBuild Projects="{0}.dproj" Targets="Clean"/>\n    </Target>\n'
    '    <Target Name="{0}:Make">\n        <MSBuild Projects="{0}.dproj" Targets="Make"/>\n    </Target>\n'.format(n)
    for n in names)


def call(suffix):
    return ';'.join(n + suffix for n in names)


group = ('<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\n'
         '    <PropertyGroup>\n        <ProjectGuid>%s</ProjectGuid>\n    </PropertyGroup>\n'
         '    <ItemGroup>\n%s    </ItemGroup>\n'
         '    <ProjectExtensions>\n        <Borland.Personality>Default.Personality.12</Borland.Personality>\n'
         '        <Borland.ProjectType/>\n        <BorlandProject>\n'
         '            <Default.Personality/>\n        </BorlandProject>\n    </ProjectExtensions>\n'
         '%s'
         '    <Target Name="Build">\n        <CallTarget Targets="%s"/>\n    </Target>\n'
         '    <Target Name="Clean">\n        <CallTarget Targets="%s"/>\n    </Target>\n'
         '    <Target Name="Make">\n        <CallTarget Targets="%s"/>\n    </Target>\n'
         '    <Import Project="$(BDS)\\Bin\\CodeGear.Group.Targets" '
         'Condition="Exists(\'$(BDS)\\Bin\\CodeGear.Group.Targets\')"/>\n'
         '</Project>\n') % (scaffold.new_guid(), items, targets, call(''), call(':Clean'), call(':Make'))
open(GROUP, 'w', encoding='utf-8-sig').write(group)
scaffold.validate_xml(GROUP)

print('%s (%d projects; expected failures last: %s)' % (GROUP, len(names), ', '.join(EXPECTED_TO_FAIL)))
