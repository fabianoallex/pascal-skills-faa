#!/usr/bin/env python3
"""Scaffold the skeleton of a new Delphi/Lazarus dual-compiler project.

WHY THIS EXISTS
----------------
The dual-compiler-delphi-lazarus skill documents that most of a dual-compiler
project's boilerplate -- the `.inc` compatibility file, `.dpr`/`.dproj`,
`.lpi`, `.groupproj`, `.lpg` -- is 80-100% identical from one project to the
next, with only a handful of fields (a project name, a fresh GUID, a search
path) actually varying. This script generates that skeleton instead of
copying it by hand from a reference project and renaming fields.

Every template here is derived from real, IDE-built files in
https://github.com/fabianoallex/pascal-amqp-faa (its `samples/Retaguarda`
target specifically, the simplest plain-console-app example in that repo) --
not invented from scratch. The only generated content is name substitution,
a freshly minted GUID, and search-path depth.

IMPORTANT: generated `.dproj`/`.lpi` files are validated as well-formed XML
before this script exits successfully, but well-formed XML is a floor, not
proof the IDE will accept them. Open the generated `.dproj` in Delphi and
`.lpi` in Lazarus once each and confirm they load without a "repair
project" prompt and build a runnable binary before relying on this
skeleton for real work.

USAGE
-----
New project, at the root of a fresh repo:
    python scaffold_dual_project.py new --name MyProject

Add one more project (e.g. a second sample or tool) to an existing group:
    python scaffold_dual_project.py add --name MyTool \\
        --groupproj MyProject.groupproj --lpg MyProject.lpg \\
        --inc src/myproject.inc

Both subcommands support --dry-run (print what would be written, write
nothing) and refuse to overwrite an existing file unless --force is given.

V1 SCOPE: a single shared `.dpr` console-app skeleton, following the real
pattern found in `samples/Retaguarda` -- Delphi and FPC compile the SAME
`.dpr` (no separate `.lpr`), because a plain console program doesn't need
the GUI/console dual-mode branching that a DUnitX/FPCUnit test runner does.
See references/project-scaffolding.md if you need a test-runner-shaped
target instead (that one does need a separate `.lpr` -- copy the pattern
from `tests/Unit/` in any of the reference repos).
"""

import argparse
import os
import re
import sys
import uuid
import xml.dom.minidom as minidom
from pathlib import Path

IDE_VERIFICATION_NOTICE = (
    "Generated files are unverified against a real IDE. Open {name}.dproj in "
    "Delphi and {name}.lpi in Lazarus once each and confirm they load and "
    "build before relying on this skeleton."
)

GROUPPROJ_ANCHOR = "<!-- SCAFFOLD:PROJECTS -->"
GROUPPROJ_TARGET_ANCHOR = "<!-- SCAFFOLD:TARGETS -->"
LPG_ANCHOR = "<!-- SCAFFOLD:TARGETS -->"

# Matches <Target Name="Build"> ... <CallTarget Targets="A;B"/> ... </Target>
# (and the Clean/Make equivalents) so a new project name can be appended to
# the Targets attribute -- growing the attribute value, not the XML tree, is
# the only correct way to add to this list.
RE_AGGREGATE_TARGET = re.compile(
    r'(<Target Name="%s">\s*<CallTarget Targets=")([^"]*)("\s*/>)'
)


def new_guid():
    return "{%s}" % str(uuid.uuid4()).upper()


def to_win_path(rel):
    """Windows-style backslash path, matching how these project files store paths."""
    return str(rel).replace("/", "\\")


# ---------------------------------------------------------------------------
# Templates. Each is a plain string with __TOKEN__ placeholders replaced by
# simple .replace() calls -- not string.Template/format, because Pascal
# source and these XML files are full of literal `{` `}` `$` characters that
# would collide with a templating mini-language.
# ---------------------------------------------------------------------------

INC_TEMPLATE = """{$IFDEF FPC}
  {$MODE DELPHI}
  {$H+}
{$ENDIF}
{$IFDEF MSWINDOWS}{$DEFINE __DEFINE___WINDOWS}{$ENDIF}
{$IFDEF WINDOWS}{$IFNDEF __DEFINE___WINDOWS}{$DEFINE __DEFINE___WINDOWS}{$ENDIF}{$ENDIF}
"""

STARTER_UNIT_TEMPLATE = """unit __NAME__.Core;

{$I __INC_NAME__.inc}

interface

type
  T__NAME__ = class
  public
    function Greeting: string;
  end;

implementation

function T__NAME__.Greeting: string;
begin
  Result := '__NAME__ is alive.';
end;

end.
"""

# Single .dpr shared by Delphi and FPC -- matches the real pattern in
# pascal-amqp-faa/samples/Retaguarda (a plain console app needs no
# GUI/console branching, so it needs no separate .lpr).
DPR_TEMPLATE = """program __NAME__;

{$IFDEF FPC}
  {$MODE DELPHI}
  {$H+}
{$ELSE}
  {$APPTYPE CONSOLE}
{$ENDIF}

uses
  {$IFDEF FPC}
    {$IFDEF UNIX}
  cthreads,
    {$ENDIF}
  {$ENDIF}
  SysUtils,
  __NAME__.Core;

var
  LGreeter: T__NAME__;
begin
  LGreeter := T__NAME__.Create;
  try
    Writeln(LGreeter.Greeting);
  finally
    LGreeter.Free;
  end;
end.
"""

# Derived from pascal-amqp-faa/samples/Retaguarda/Retaguarda.dproj -- a
# plain console app has no per-unit DCCReference list at all (everything
# resolves via DCC_UnitSearchPath), which is what makes this template short.
DPROJ_TEMPLATE = """<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
    <PropertyGroup>
        <ProjectGuid>__GUID__</ProjectGuid>
        <ProjectVersion>20.1</ProjectVersion>
        <FrameworkType>None</FrameworkType>
        <Base>True</Base>
        <Config Condition="'$(Config)'==''">Debug</Config>
        <Platform Condition="'$(Platform)'==''">Win32</Platform>
        <TargetedPlatforms>3</TargetedPlatforms>
        <AppType>Console</AppType>
        <MainSource>__NAME__.dpr</MainSource>
        <ProjectName Condition="'$(ProjectName)'==''">__NAME__</ProjectName>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Config)'=='Base' or '$(Base)'!=''">
        <Base>true</Base>
    </PropertyGroup>
    <PropertyGroup Condition="('$(Platform)'=='Win32' and '$(Base)'=='true') or '$(Base_Win32)'!=''">
        <Base_Win32>true</Base_Win32>
        <CfgParent>Base</CfgParent>
        <Base>true</Base>
    </PropertyGroup>
    <PropertyGroup Condition="('$(Platform)'=='Win64' and '$(Base)'=='true') or '$(Base_Win64)'!=''">
        <Base_Win64>true</Base_Win64>
        <CfgParent>Base</CfgParent>
        <Base>true</Base>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Config)'=='Debug' or '$(Cfg_1)'!=''">
        <Cfg_1>true</Cfg_1>
        <CfgParent>Base</CfgParent>
        <Base>true</Base>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Config)'=='Release' or '$(Cfg_2)'!=''">
        <Cfg_2>true</Cfg_2>
        <CfgParent>Base</CfgParent>
        <Base>true</Base>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Base)'!=''">
        <DCC_DcuOutput>.\\$(Platform)\\$(Config)</DCC_DcuOutput>
        <DCC_ExeOutput>.\\$(Platform)\\$(Config)</DCC_ExeOutput>
        <DCC_Namespace>System;Xml;Data;Datasnap;Web;Soap;$(DCC_Namespace)</DCC_Namespace>
        <DCC_UnitSearchPath>__SRC_REL__;$(DCC_UnitSearchPath)</DCC_UnitSearchPath>
        <SanitizedProjectName>__NAME__</SanitizedProjectName>
        <UsingDelphiRTL>true</UsingDelphiRTL>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Base_Win32)'!=''">
        <DCC_Namespace>Winapi;System.Win;Data.Win;Datasnap.Win;Web.Win;Soap.Win;Xml.Win;$(DCC_Namespace)</DCC_Namespace>
        <BT_BuildType>Debug</BT_BuildType>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Base_Win64)'!=''">
        <DCC_Namespace>Winapi;System.Win;Data.Win;Datasnap.Win;Web.Win;Soap.Win;Xml.Win;$(DCC_Namespace)</DCC_Namespace>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Cfg_1)'!=''">
        <DCC_Define>DEBUG;$(DCC_Define)</DCC_Define>
        <DCC_DebugDCUs>true</DCC_DebugDCUs>
        <DCC_Optimize>false</DCC_Optimize>
        <DCC_GenerateStackFrames>true</DCC_GenerateStackFrames>
        <DCC_DebugInfoInExe>true</DCC_DebugInfoInExe>
        <DCC_IntegerOverflowCheck>true</DCC_IntegerOverflowCheck>
        <DCC_RangeChecking>true</DCC_RangeChecking>
    </PropertyGroup>
    <PropertyGroup Condition="'$(Cfg_2)'!=''">
        <DCC_LocalDebugSymbols>false</DCC_LocalDebugSymbols>
        <DCC_Define>RELEASE;$(DCC_Define)</DCC_Define>
        <DCC_SymbolReferenceInfo>0</DCC_SymbolReferenceInfo>
        <DCC_DebugInformation>0</DCC_DebugInformation>
    </PropertyGroup>
    <ItemGroup>
        <DelphiCompile Include="$(MainSource)">
            <MainSource>MainSource</MainSource>
        </DelphiCompile>
        <BuildConfiguration Include="Base">
            <Key>Base</Key>
        </BuildConfiguration>
        <BuildConfiguration Include="Debug">
            <Key>Cfg_1</Key>
            <CfgParent>Base</CfgParent>
        </BuildConfiguration>
        <BuildConfiguration Include="Release">
            <Key>Cfg_2</Key>
            <CfgParent>Base</CfgParent>
        </BuildConfiguration>
    </ItemGroup>
    <ProjectExtensions>
        <Borland.Personality>Delphi.Personality.12</Borland.Personality>
        <Borland.ProjectType>Application</Borland.ProjectType>
        <BorlandProject>
            <Delphi.Personality>
                <Source>
                    <Source Name="MainSource">__NAME__.dpr</Source>
                </Source>
            </Delphi.Personality>
            <Platforms>
                <Platform value="Win32">True</Platform>
                <Platform value="Win64">True</Platform>
            </Platforms>
        </BorlandProject>
        <ProjectFileVersion>12</ProjectFileVersion>
    </ProjectExtensions>
    <Import Project="$(BDS)\\Bin\\CodeGear.Delphi.Targets" Condition="Exists('$(BDS)\\Bin\\CodeGear.Delphi.Targets')"/>
    <Import Project="$(APPDATA)\\Embarcadero\\$(BDSAPPDATABASEDIR)\\$(PRODUCTVERSION)\\UserTools.proj" Condition="Exists('$(APPDATA)\\Embarcadero\\$(BDSAPPDATABASEDIR)\\$(PRODUCTVERSION)\\UserTools.proj')"/>
</Project>
"""

# Derived from pascal-amqp-faa/samples/Retaguarda/Retaguarda.lpi. Points
# `Filename` straight at the shared `.dpr` -- there is no separate `.lpr`.
# The --with-lpk variant swaps OtherUnitFiles for a RequiredPackages entry.
LPI_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<CONFIG>
  <ProjectOptions>
    <Version Value="12"/>
    <PathDelim Value="\\"/>
    <General>
      <Flags>
        <MainUnitHasCreateFormStatements Value="False"/>
        <MainUnitHasTitleStatement Value="False"/>
        <MainUnitHasScaledStatement Value="False"/>
      </Flags>
      <SessionStorage Value="InProjectDir"/>
      <Title Value="__NAME__"/>
      <UseAppBundle Value="False"/>
      <ResourceType Value="res"/>
    </General>
    <BuildModes>
      <Item Name="Default" Default="True"/>
    </BuildModes>
    <PublishOptions>
      <Version Value="2"/>
      <UseFileFilters Value="True"/>
    </PublishOptions>
    <RunParams>
      <FormatVersion Value="2"/>
    </RunParams>
__REQUIRED_PACKAGES__
    <Units>
      <Unit>
        <Filename Value="__NAME__.dpr"/>
        <IsPartOfProject Value="True"/>
      </Unit>
    </Units>
  </ProjectOptions>
  <CompilerOptions>
    <Version Value="11"/>
    <PathDelim Value="\\"/>
    <Target>
      <Filename Value="__NAME__"/>
    </Target>
    <SearchPaths>
__SEARCH_PATHS__
      <UnitOutputDirectory Value="lib\\$(TargetCPU)-$(TargetOS)"/>
    </SearchPaths>
    <Parsing>
      <SyntaxOptions>
        <SyntaxMode Value="Delphi"/>
      </SyntaxOptions>
    </Parsing>
    <CodeGeneration>
      <Checks>
        <IOChecks Value="True"/>
      </Checks>
    </CodeGeneration>
    <Linking>
      <Debugging>
        <DebugInfoType Value="dsDwarf3"/>
      </Debugging>
    </Linking>
  </CompilerOptions>
</CONFIG>
"""

LPI_REQUIRED_PACKAGES_WITH_LPK = """    <RequiredPackages>
      <Item>
        <PackageName Value="__PKG_NAME__"/>
      </Item>
    </RequiredPackages>"""

LPI_SEARCH_PATHS_NO_LPK = """      <IncludeFiles Value="__SRC_REL__"/>
      <OtherUnitFiles Value="__SRC_REL__"/>"""

LPI_SEARCH_PATHS_WITH_LPK = ""  # resolution comes entirely from the package

# Derived from pascal-amqp-faa/AMQP.groupproj (structure only -- trimmed to
# one project entry). Carries SCAFFOLD anchors so `add` can find where to
# insert later without doing fragile text-surgery on a hand-authored file.
GROUPPROJ_TEMPLATE = """<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
    <PropertyGroup>
        <ProjectGuid>__GUID__</ProjectGuid>
    </PropertyGroup>
    <ItemGroup>
        <Projects Include="__NAME__.dproj">
            <Dependencies/>
        </Projects>
        <!-- SCAFFOLD:PROJECTS -->
    </ItemGroup>
    <Target Name="__NAME__">
        <MSBuild Projects="__NAME__.dproj"/>
    </Target>
    <Target Name="__NAME__:Clean">
        <MSBuild Projects="__NAME__.dproj" Targets="Clean"/>
    </Target>
    <Target Name="__NAME__:Make">
        <MSBuild Projects="__NAME__.dproj" Targets="Make"/>
    </Target>
    <!-- SCAFFOLD:TARGETS -->
    <Target Name="Build">
        <CallTarget Targets="__NAME__"/>
    </Target>
    <Target Name="Clean">
        <CallTarget Targets="__NAME__:Clean"/>
    </Target>
    <Target Name="Make">
        <CallTarget Targets="__NAME__:Make"/>
    </Target>
    <Import Project="$(BDS)\\Bin\\CodeGear.Group.Targets" Condition="Exists('$(BDS)\\Bin\\CodeGear.Group.Targets')"/>
</Project>
"""

# Derived from pascal-amqp-faa/AMQP.lpg (structure only -- trimmed to one target).
LPG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<CONFIG>
  <ProjectGroup FileVersion="2">
    <Targets>
      <Target FileName="__NAME__.lpi">
        <BuildModes>
          <Mode Name="Default"/>
        </BuildModes>
      </Target>
      <!-- SCAFFOLD:TARGETS -->
    </Targets>
  </ProjectGroup>
</CONFIG>
"""

# Derived from pascal-amqp-faa/packages/pascal_amqp_faa.lpk (opt-in, --with-lpk).
LPK_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<CONFIG>
  <Package Version="5">
    <PathDelim Value="\\"/>
    <Name Value="__PKG_NAME__"/>
    <CompilerOptions>
      <Version Value="11"/>
      <PathDelim Value="\\"/>
      <SearchPaths>
        <IncludeFiles Value="__SRC_REL__"/>
        <OtherUnitFiles Value="__SRC_REL__"/>
        <UnitOutputDirectory Value="lib\\$(TargetCPU)-$(TargetOS)"/>
      </SearchPaths>
    </CompilerOptions>
    <Description Value="__NAME__ shared library units."/>
    <License Value="MIT"/>
    <Version Minor="1"/>
    <Files>
      <Item>
        <Filename Value="__SRC_REL__\\__INC_NAME__.inc"/>
        <Type Value="Include"/>
      </Item>
      <Item>
        <Filename Value="__SRC_REL__\\__NAME__.Core.pas"/>
        <UnitName Value="__NAME__.Core"/>
      </Item>
    </Files>
    <RequiredPkgs>
      <Item>
        <PackageName Value="FCL"/>
      </Item>
    </RequiredPkgs>
    <UsageOptions>
      <UnitPath Value="$(PkgOutDir)"/>
    </UsageOptions>
    <PublishOptions>
      <Version Value="2"/>
      <UseFileFilters Value="True"/>
    </PublishOptions>
  </Package>
</CONFIG>
"""


def render(template, **tokens):
    out = template
    for key, value in tokens.items():
        out = out.replace("__%s__" % key, value)
    return out


def validate_xml(path):
    try:
        minidom.parse(str(path))
    except Exception as exc:
        raise SystemExit(
            "Generated file is not well-formed XML, aborting: %s (%s)" % (path, exc)
        )


def write_file(path, content, dry_run, force, validate_as_xml=False):
    path = Path(path)
    if path.exists() and not force:
        raise SystemExit(
            "Refusing to overwrite existing file (pass --force to override): %s" % path
        )
    print(("[dry-run] would write " if dry_run else "writing ") + str(path))
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if validate_as_xml:
        try:
            validate_xml(path)
        except SystemExit:
            path.unlink(missing_ok=True)
            raise


def check_name_collision(project_dir, name):
    """Refuse if `name` collides with an existing unit under src/ (Delphi
    rejects a project with the same name as a unit it references -- see
    the "Naming" section of SKILL.md)."""
    src = Path(project_dir) / "src"
    if not src.is_dir():
        return
    for pas_file in src.rglob("*.pas"):
        unit_name = pas_file.stem
        if unit_name.lower() == name.lower():
            raise SystemExit(
                "Refusing: '%s' collides with an existing unit (%s). Delphi "
                "rejects a project with the same name as a unit it "
                "references -- pick a different project name (e.g. "
                "'%sSuite')." % (name, pas_file, name)
            )


def cmd_new(args):
    project_dir = Path(args.dir).resolve()
    name = args.name
    define_prefix = (args.define_prefix or name).upper()
    inc_name = define_prefix.lower()

    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise SystemExit(
            "Project name must be a valid Pascal identifier "
            "(letters, digits, underscore, not starting with a digit): %r" % name
        )

    check_name_collision(project_dir, name)

    src_dir = project_dir / "src"
    inc_path = src_dir / ("%s.inc" % inc_name)
    unit_path = src_dir / ("%s.Core.pas" % name)
    dpr_path = project_dir / ("%s.dpr" % name)
    dproj_path = project_dir / ("%s.dproj" % name)
    lpi_path = project_dir / ("%s.lpi" % name)
    groupproj_path = project_dir / ("%s.groupproj" % name)
    lpg_path = project_dir / ("%s.lpg" % name)

    write_file(inc_path, render(INC_TEMPLATE, DEFINE=define_prefix), args.dry_run, args.force)
    write_file(unit_path, render(STARTER_UNIT_TEMPLATE, NAME=name, INC_NAME=inc_name),
               args.dry_run, args.force)
    write_file(dpr_path, render(DPR_TEMPLATE, NAME=name), args.dry_run, args.force)

    src_rel = to_win_path(os.path.relpath(src_dir, project_dir))
    write_file(dproj_path,
               render(DPROJ_TEMPLATE, NAME=name, GUID=new_guid(), SRC_REL=src_rel),
               args.dry_run, args.force, validate_as_xml=True)

    if args.with_lpk:
        pkg_name = "%s_pkg" % name.lower()
        required_packages = render(LPI_REQUIRED_PACKAGES_WITH_LPK, PKG_NAME=pkg_name)
        search_paths = LPI_SEARCH_PATHS_WITH_LPK
    else:
        required_packages = ""
        search_paths = render(LPI_SEARCH_PATHS_NO_LPK, SRC_REL=src_rel)

    write_file(lpi_path,
               render(LPI_TEMPLATE, NAME=name,
                      REQUIRED_PACKAGES=required_packages, SEARCH_PATHS=search_paths),
               args.dry_run, args.force, validate_as_xml=True)

    write_file(groupproj_path, render(GROUPPROJ_TEMPLATE, NAME=name, GUID=new_guid()),
               args.dry_run, args.force, validate_as_xml=True)
    write_file(lpg_path, render(LPG_TEMPLATE, NAME=name), args.dry_run, args.force,
               validate_as_xml=True)

    if args.with_lpk:
        pkg_name = "%s_pkg" % name.lower()
        lpk_path = project_dir / "packages" / ("%s.lpk" % pkg_name)
        src_rel_from_pkg = to_win_path(os.path.relpath(src_dir, lpk_path.parent))
        write_file(lpk_path,
                   render(LPK_TEMPLATE, NAME=name, PKG_NAME=pkg_name,
                          SRC_REL=src_rel_from_pkg, INC_NAME=inc_name),
                   args.dry_run, args.force, validate_as_xml=True)

    if not args.dry_run:
        print("\n" + IDE_VERIFICATION_NOTICE.format(name=name))


def insert_before_anchor(text, anchor, insertion):
    if anchor not in text:
        return None
    return text.replace(anchor, insertion + "\n    " + anchor, 1)


def cmd_add(args):
    name = args.name
    # Resolve every incoming path up front and consistently. Mixing a
    # resolved path (which Windows normalizes 8.3 short names like
    # FABIAN~1.ARN into their long form) with an unresolved one in the same
    # os.path.relpath() call produces a bogus, wildly-long ../../.. path,
    # since relpath compares path components as text, not by identity.
    groupproj_path = Path(args.groupproj).resolve()
    lpg_path = Path(args.lpg).resolve()
    inc_path = Path(args.inc).resolve()

    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise SystemExit("Project name must be a valid Pascal identifier: %r" % name)

    target_dir = Path(args.dir).resolve() if args.dir else Path.cwd()
    check_name_collision(groupproj_path.parent, name)

    dpr_path = target_dir / ("%s.dpr" % name)
    dproj_path = target_dir / ("%s.dproj" % name)
    lpi_path = target_dir / ("%s.lpi" % name)

    unit_path = target_dir / ("%s.Core.pas" % name)
    define_prefix = inc_path.stem.upper()
    write_file(unit_path, render(STARTER_UNIT_TEMPLATE, NAME=name, INC_NAME=inc_path.stem),
               args.dry_run, args.force)
    write_file(dpr_path, render(DPR_TEMPLATE, NAME=name), args.dry_run, args.force)

    src_rel = to_win_path(os.path.relpath(inc_path.parent, target_dir))
    write_file(dproj_path,
               render(DPROJ_TEMPLATE, NAME=name, GUID=new_guid(), SRC_REL=src_rel),
               args.dry_run, args.force, validate_as_xml=True)
    write_file(lpi_path,
               render(LPI_TEMPLATE, NAME=name, REQUIRED_PACKAGES="",
                      SEARCH_PATHS=render(LPI_SEARCH_PATHS_NO_LPK, SRC_REL=src_rel)),
               args.dry_run, args.force, validate_as_xml=True)

    dproj_rel = to_win_path(os.path.relpath(dproj_path, groupproj_path.parent))
    lpi_rel = to_win_path(os.path.relpath(lpi_path, lpg_path.parent))

    groupproj_snippet = (
        '        <Projects Include="%s">\n'
        '            <Dependencies/>\n'
        '        </Projects>' % dproj_rel
    )
    target_snippet = (
        '    <Target Name="%s">\n'
        '        <MSBuild Projects="%s"/>\n'
        '    </Target>\n'
        '    <Target Name="%s:Clean">\n'
        '        <MSBuild Projects="%s" Targets="Clean"/>\n'
        '    </Target>\n'
        '    <Target Name="%s:Make">\n'
        '        <MSBuild Projects="%s" Targets="Make"/>\n'
        '    </Target>' % (name, dproj_rel, name, dproj_rel, name, dproj_rel)
    )
    lpg_snippet = (
        '      <Target FileName="%s">\n'
        '        <BuildModes>\n'
        '          <Mode Name="Default"/>\n'
        '        </BuildModes>\n'
        '      </Target>' % lpi_rel
    )

    if groupproj_path.exists():
        text = groupproj_path.read_text(encoding="utf-8")
        new_text = insert_before_anchor(text, GROUPPROJ_ANCHOR, groupproj_snippet)
        new_text = insert_before_anchor(new_text, GROUPPROJ_TARGET_ANCHOR,
                                         target_snippet) if new_text else None
        if new_text:
            for kind, suffix in (("Build", ""), ("Clean", ":Clean"), ("Make", ":Make")):
                pattern = re.compile(RE_AGGREGATE_TARGET.pattern % kind)
                new_text, count = pattern.subn(
                    lambda m: m.group(1) + m.group(2) + (";%s%s" % (name, suffix)) + m.group(3),
                    new_text,
                )
                if count == 0:
                    raise SystemExit(
                        "Found SCAFFOLD anchors but couldn't locate the aggregate "
                        "<Target Name=\"%s\"> block to extend -- not touching %s. "
                        "Insert the project into it by hand." % (kind, groupproj_path)
                    )
            write_file(groupproj_path, new_text, args.dry_run, args.force or True,
                       validate_as_xml=True)
        else:
            print_manual_groupproj_instructions(groupproj_path, groupproj_snippet, target_snippet)
    else:
        print_manual_groupproj_instructions(groupproj_path, groupproj_snippet, target_snippet)

    if lpg_path.exists():
        text = lpg_path.read_text(encoding="utf-8")
        new_text = insert_before_anchor(text, LPG_ANCHOR, lpg_snippet)
        if new_text:
            write_file(lpg_path, new_text, args.dry_run, args.force or True,
                       validate_as_xml=True)
        else:
            print_manual_lpg_instructions(lpg_path, lpg_snippet)
    else:
        print_manual_lpg_instructions(lpg_path, lpg_snippet)

    if not args.dry_run:
        print("\n" + IDE_VERIFICATION_NOTICE.format(name=name))


def print_manual_groupproj_instructions(path, projects_snippet, target_snippet):
    print(
        "\n%s doesn't look like a file this script generated (no SCAFFOLD "
        "anchor comments found), so it was left untouched to avoid a "
        "fragile text edit of a hand-authored file.\n\n"
        "Insert this snippet inside the existing <ItemGroup> that already "
        "lists the other <Projects Include=...> entries:\n\n%s\n\n"
        "And insert these three <Target> blocks anywhere alongside the "
        "other per-project targets, then append the project name (plain, "
        "':Clean', and ':Make' variants) to the three aggregate "
        "<CallTarget Targets=\"...\"> lists (Build/Clean/Make):\n\n%s\n"
        % (path, projects_snippet, target_snippet)
    )


def print_manual_lpg_instructions(path, target_snippet):
    print(
        "\n%s doesn't look like a file this script generated (no SCAFFOLD "
        "anchor comment found), so it was left untouched.\n\n"
        "Insert this snippet inside the existing <Targets> element, "
        "alongside the other <Target FileName=...> entries:\n\n%s\n"
        % (path, target_snippet)
    )


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Scaffold a brand-new dual-compiler project")
    p_new.add_argument("--name", required=True, help="Project name (a valid Pascal identifier)")
    p_new.add_argument("--dir", default=".", help="Directory to create the project in (default: .)")
    p_new.add_argument("--define-prefix",
                        help="Platform-define prefix for the .inc file (default: --name, uppercased)")
    p_new.add_argument("--with-lpk", action="store_true",
                        help="Also scaffold packages/<name>_pkg.lpk, for a project meant to be "
                             "consumed as a reusable Lazarus package by other projects")
    p_new.add_argument("--dry-run", action="store_true", help="Print what would be written, write nothing")
    p_new.add_argument("--force", action="store_true", help="Overwrite existing files")
    p_new.set_defaults(func=cmd_new)

    p_add = sub.add_parser("add", help="Add one more project to an existing group")
    p_add.add_argument("--name", required=True, help="New project's name (a valid Pascal identifier)")
    p_add.add_argument("--dir", help="Directory to create the new project's files in (default: cwd)")
    p_add.add_argument("--groupproj", required=True, help="Path to the existing .groupproj to update")
    p_add.add_argument("--lpg", required=True, help="Path to the existing .lpg to update")
    p_add.add_argument("--inc", required=True,
                        help="Path to the existing project's .inc file (reused, not regenerated)")
    p_add.add_argument("--dry-run", action="store_true", help="Print what would be written, write nothing")
    p_add.add_argument("--force", action="store_true", help="Overwrite existing new-project files")
    p_add.set_defaults(func=cmd_add)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
