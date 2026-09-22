#!/usr/bin/env python3
"""Structural checker for mirrored DUnitX <-> FPCUnit test suites.

WHY THIS EXISTS
----------------
In a dual-compiler project, half of the validation depends on the Delphi IDE
(Delphi Community Edition can't build from the command line), so a defect
that only shows up in the Delphi mirror costs a full IDE round-trip -- or
worse, goes unnoticed while the FPC suite stays green. None of the checks
below need a compiler to run; run this before sending a suite to the IDE.

Adapted and generalized from a project-specific script
(tests/tools/verifica_espelhos.py in github.com/fabianoallex/pascal-amqp-faa),
where it was built to catch defects that had already cost real round-trips:

1. Test code declared AFTER the `initialization` section. In Pascal, a
   `procedure`/`function` there is parsed as a directive, not a declaration
   (dcc32 E2070). A green suite on one compiler is not evidence about the
   other.

2. A new fixture not registered in `initialization`. This is the worst kind:
   no compile error at all -- just a green suite with N fewer tests than it
   should have. A silent false-green.

3. An assertion from the WRONG dialect. Something that generates both
   mirrors from one shared text block left `AssertTrue(msg, cond)` (FPCUnit's
   form) in the DUnitX file. FPC compiled fine, the FPC suite was green, and
   the defect only showed up in dcc32 as "E2003 Undeclared identifier:
   'ASSERTTRUE'". Detection is trivial: the two assertion vocabularies are
   disjoint and known ahead of time.

4. A DUnitX attribute ([Setup], [Test], ...) placed in a `private`/
   `protected` section. Delphi's default RTTI only publishes `public` and
   `published` members -- in a non-visible section the attribute compiles
   and is simply never found. If it's a [Setup], the fixture runs with every
   field nil; if it's a [Test], it silently disappears from the suite.
   FPCUnit can't warn about this either way: the visibility that matters
   there is `published`, and the base fixture doesn't need it at all.

5. RTL calls that only exist on ONE of the two compilers, written into the
   mirror of the other (`GetTempDir` in a DUnitX file; `SysUtils.DeleteFile`
   qualified without the `System.` prefix Delphi requires). The root cause
   is always the same: a generator that writes both mirrors from one shared
   text block. That's fine -- good, even -- for the test body, which is
   meant to stay identical; it's not fine for anything that touches the RTL,
   which is not dialect-neutral. The identifier list below is deliberately
   short: only entries that have actually cost a round-trip.

This is NOT a Pascal parser: it's deliberately simple pattern matching over
the type section and the registration block. It exists for exactly the
defect classes above and doesn't try to be more than that.

USAGE
-----
    python verify_test_mirrors.py [--root PATH] [--dirs tests] \\
        [--mirror-subdir fpc] [--ignore-glob /lib/,/backup/,__recovery]

Exits 1 if it finds a real divergence, 0 if clean -- safe to wire into a
pre-commit hook or a CI step.

Convention this script assumes: for every test file `X/Name.pas` (DUnitX),
its FPCUnit mirror lives at `X/<mirror-subdir>/Name.pas` (default
`X/fpc/Name.pas`). If your project uses a different mirror layout, pass
`--mirror-subdir` or adapt the `mirrored_pairs()` function.

Dropped from the original: a project-specific check that verified every unit
under `src/server` was listed in every consuming `.dpr`/`.dproj` and in a
specific `.lpk` package. That check hardcoded a submodule path and a package
filename particular to one project's architecture. See
`references/test-mirror-verification.md` for how to write an equivalent
check for your own project if you have a similar optional sub-package -- as
a function you append to the `CHECKS` list at the bottom of this file,
matching the signature every other check uses.
"""

import argparse
import io
import os
import re
import sys

DEFAULT_IGNORE = ('/lib/', '\\lib\\', '/backup/', '\\backup\\', '__recovery')

# There is deliberately NO exception list here. An early version of this
# check compared every `procedure` in the type section and required every
# class to be registered -- it flagged 7 divergences, all 7 false positives
# (helper methods that only exist on one side, auxiliary classes that aren't
# fixtures at all). An exception list would have hidden the false positives
# without fixing the heuristic, and every new similarly-named test would
# have tripped it again. The exact discriminators exist in both dialects and
# are used below instead:
#   DUnitX : a fixture is a class with [TestFixture]; a test is a method
#            with [Test].
#   FPCUnit: a fixture is a class(TTestCase); a test is a method in the
#            `published` section.
# With those, a private/protected helper or an unrelated class simply never
# enters the count.


def read_file(path):
    with io.open(path, encoding='utf-8-sig', errors='replace') as f:
        return f.read()


def iter_pascal_files(root, dirs, ignore_patterns):
    for d in dirs:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for folder, _, names in os.walk(base):
            for name in names:
                if not name.lower().endswith(('.pas', '.dpr', '.lpr')):
                    continue
                path = os.path.join(folder, name)
                if any(pattern in path for pattern in ignore_patterns):
                    continue
                yield path


def rel_path(path, root):
    return os.path.relpath(path, root).replace('\\', '/')


def lint_code_after_initialization(cfg):
    """[1] Executable code declared after `initialization`."""
    findings = []
    for path in iter_pascal_files(cfg.root, cfg.dirs, cfg.ignore):
        text = read_file(path)
        m = re.search(r'^initialization\s*$', text, re.M)
        if not m:
            continue
        after = text[m.end():]
        for d in re.finditer(r'^(procedure|function)\s+(\w+)', after, re.M):
            findings.append((rel_path(path, cfg.root),
                              '%s declared after initialization' % d.group(2)))
            break  # one hit per file is enough to flag it
    return findings


def mirrored_pairs(cfg):
    """Match `X/<mirror-subdir>/Name.pas` (FPC) with `X/Name.pas` (DUnitX)."""
    for path in iter_pascal_files(cfg.root, cfg.dirs, cfg.ignore):
        folder, name = os.path.split(path)
        if os.path.basename(folder).lower() != cfg.mirror_subdir.lower():
            continue
        if not name.lower().endswith('.pas'):
            continue
        dunitx_path = os.path.join(os.path.dirname(folder), name)
        if os.path.exists(dunitx_path):
            yield dunitx_path, path


def class_blocks(decl):
    """Yield (name, parent, text_before, body) for each `TXxx = class...end;`.

    The body runs to the first line that is just `end;` -- good enough for a
    consistently-formatted codebase, and avoids needing a real Pascal
    parser. `text_before` carries any attributes preceding the class, which
    is where DUnitX's `[TestFixture]` appears. `parent` is empty for
    `= class` with no explicit ancestor.
    """
    for m in re.finditer(r'^[ \t]*(T\w+)\s*=\s*class\b[ \t]*(?:\(\s*(\w+))?',
                         decl, re.M):
        name = m.group(1)
        parent = m.group(2) or ''
        before = decl[max(0, m.start() - 120):m.start()]
        rest = decl[m.end():]
        end = re.search(r'^[ \t]*end;\s*$', rest, re.M)
        body = rest[:end.start()] if end else rest
        yield name, parent, before, body


def published_tests(body):
    """Methods in the `published` section (FPCUnit's fixture vocabulary)."""
    names = set()
    parts = re.split(r'^[ \t]*(private|protected|public|published)\b',
                      body, flags=re.M)
    section = None
    for part in parts:
        if part in ('private', 'protected', 'public', 'published'):
            section = part
            continue
        if section == 'published':
            names.update(re.findall(r'procedure\s+(\w+)\s*;', part))
    return names


def analyze(path):
    """Return (declared tests, fixtures WITH tests, registered fixtures).

    Uses each dialect's exact discriminators (see the module-level comment
    above): a private/protected helper or an unrelated class never enters
    the count.

    "Fixture with tests" is the right unit to require registration for: a
    shared BASE fixture that other fixtures descend from is a fixture but
    declares no test of its own and doesn't need to be registered. Requiring
    registration for it would be a false positive; not requiring it for
    fixtures that DO have tests would let the silent-failure defect this
    script exists to catch slip through again.
    """
    text = read_file(path)
    i = text.find('implementation')
    decl = text[:i] if i > 0 else text

    is_dunitx = '[TestFixture]' in decl or 'DUnitX.TestFramework' in text
    classes = list(class_blocks(decl))

    # An FPCUnit fixture can descend from another fixture, not only directly
    # from TTestCase. Resolve by fixed-point closure; without it, every
    # derived fixture disappears from the analysis and the whole file looks
    # like it has no tests at all.
    is_fixture = {}
    for name, parent, before, _body in classes:
        if is_dunitx:
            is_fixture[name] = '[TestFixture]' in before
        else:
            is_fixture[name] = (parent == 'TTestCase')
    if not is_dunitx:
        changed = True
        while changed:
            changed = False
            for name, parent, _b, _c in classes:
                if not is_fixture.get(name) and is_fixture.get(parent):
                    is_fixture[name] = True
                    changed = True

    tests = set()
    fixtures_with_tests = set()
    for name, _parent, _before, body in classes:
        if not is_fixture.get(name):
            continue
        if is_dunitx:
            mine = set(re.findall(r'\[Test\]\s*procedure\s+(\w+)\s*;', body))
        else:
            mine = published_tests(body)
        tests.update(mine)
        if mine:
            fixtures_with_tests.add(name)

    # The FORM of the call matters, not just the fixture name: in DUnitX,
    # registration is a class method and needs the `TDUnitX.` prefix --
    # a bare `RegisterTestFixture(X)` doesn't compile (E2003, undeclared
    # identifier). An earlier version of this check matched either form and
    # so reported a fixture as registered in a file that didn't even
    # compile -- a false negative, found only when dcc32 rejected the file.
    if is_dunitx:
        pattern = r'TDUnitX\s*\.\s*RegisterTestFixture\s*\(\s*(\w+)\s*\)'
    else:
        pattern = r'\bRegisterTest\s*\(\s*(\w+)\s*\)'
    registered = set(re.findall(pattern, text))
    return tests, fixtures_with_tests, registered


def check_mirror_parity(cfg):
    """[2] Declared-test parity and fixture-registration parity."""
    problems = []
    for dunitx_path, fpc_path in mirrored_pairs(cfg):
        td, fd, rd = analyze(dunitx_path)
        tf, ff, rf = analyze(fpc_path)

        only_delphi = td - tf
        only_fpc = tf - td
        if only_delphi:
            problems.append((rel_path(dunitx_path, cfg.root),
                              'test only exists in DELPHI: ' + ', '.join(sorted(only_delphi))))
        if only_fpc:
            problems.append((rel_path(fpc_path, cfg.root),
                              'test only exists in FPC: ' + ', '.join(sorted(only_fpc))))

        # A fixture declared but not registered means tests that never run,
        # with no compile error at all -- the silent-failure defect.
        for path, fixtures, registered in ((dunitx_path, fd, rd), (fpc_path, ff, rf)):
            missing = fixtures - registered
            if missing:
                problems.append((rel_path(path, cfg.root),
                                  'fixture NOT REGISTERED: ' + ', '.join(sorted(missing))))
    return problems


# Assertion vocabularies are disjoint by design: FPCUnit exposes loose
# methods inherited from TAssert, DUnitX only the `Assert` object. A call
# from the wrong set doesn't compile -- but only on the OTHER compiler,
# which is exactly what goes unnoticed when one generator writes both files.
FPCUNIT_ASSERTIONS = (
    'AssertEquals', 'AssertTrue', 'AssertFalse', 'AssertNull', 'AssertNotNull',
    'AssertSame', 'AssertNotSame', 'AssertException', 'AssertEqualsString',
)

# `Assert.` matches all of DUnitX (AreEqual, IsTrue, WillRaise, Pass,
# Fail...) without needing to list every method.
RE_ASSERT_DUNITX = re.compile(r'(?<![\w.])Assert\s*\.\s*[A-Za-z]')


def strip_comments_and_strings(text):
    """Replace comments and string literals with spaces, keeping newlines.

    Without this, the assertion-dialect check flags PROSE: a comment
    explaining the difference between FPCUnit's AssertException and
    DUnitX's Assert.WillRaise -- naming the other dialect while documenting
    why it doesn't apply -- is exactly the kind of thing a real test file
    should say. Preserving line breaks keeps the reported line numbers
    pointing at the real file.
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "'":  # string literal
            j = i + 1
            while j < n and text[j] != "'":
                j += 1
            out.append(' ' * (min(j, n - 1) - i + 1))
            i = j + 1
        elif c == '/' and text[i:i + 2] == '//':
            j = text.find('\n', i)
            if j < 0:
                j = n
            out.append(' ' * (j - i))
            i = j
        elif c == '{':  # block comment (and compiler directives)
            j = text.find('}', i)
            if j < 0:
                j = n - 1
            out.append(''.join(ch if ch == '\n' else ' ' for ch in text[i:j + 1]))
            i = j + 1
        elif text[i:i + 2] == '(*':
            j = text.find('*)', i)
            j = n - 2 if j < 0 else j
            out.append(''.join(ch if ch == '\n' else ' ' for ch in text[i:j + 2]))
            i = j + 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def find_calls(body, names):
    """Occurrences of `names` called as a function, e.g. `Name(...)`."""
    found = []
    for name in names:
        for m in re.finditer(r'(?<![\w.])' + name + r'\s*\(', body, re.IGNORECASE):
            found.append((name, body.count('\n', 0, m.start()) + 1))
    return found


def check_assertion_dialect(cfg):
    """[3] An assertion from the wrong dialect -- caught only by the OTHER compiler.

    Doesn't try to understand the code: looks for one dialect's assertion
    names inside a file belonging to the other. `TAssert.AssertTrue(...)`
    qualified is legitimate on both sides and is excluded from the match.
    """
    problems = []
    for dunitx_path, fpc_path in mirrored_pairs(cfg):
        body = strip_comments_and_strings(read_file(dunitx_path))
        for name, line in find_calls(body, FPCUNIT_ASSERTIONS):
            problems.append((rel_path(dunitx_path, cfg.root),
                              'line %d: FPCUnit assertion (%s) in a DUnitX file -- use Assert.*'
                              % (line, name)))
        body = strip_comments_and_strings(read_file(fpc_path))
        for m in RE_ASSERT_DUNITX.finditer(body):
            line = body.count('\n', 0, m.start()) + 1
            problems.append((rel_path(fpc_path, cfg.root),
                              'line %d: DUnitX assertion (Assert.*) in an FPCUnit file' % line))
    return problems


# Sections where a DUnitX attribute is invisible to the default RTTI.
NO_RTTI_SECTIONS = ('private', 'protected', 'strict private', 'strict protected')

RE_SECTION = re.compile(r'^\s*(strict\s+private|strict\s+protected|private|'
                        r'protected|public|published)\s*$', re.IGNORECASE)
RE_DUNITX_ATTRIBUTE = re.compile(
    r'\[\s*(Setup|TearDown|SetupFixture|TearDownFixture|Test|TestCase)\b',
    re.IGNORECASE)


def check_attribute_visibility(cfg):
    """[4] A DUnitX attribute in a section the default RTTI doesn't publish.

    Deliberately simple heuristic, and sufficient: scans line by line,
    tracking the last visibility section seen. Starts at `public` because
    that's the default for a Delphi class with no explicit specifier.
    """
    problems = []
    for dunitx_path, _fpc_path in mirrored_pairs(cfg):
        body = strip_comments_and_strings(read_file(dunitx_path))
        section = 'public'
        for n, line in enumerate(body.splitlines(), 1):
            m = RE_SECTION.match(line)
            if m:
                section = ' '.join(m.group(1).lower().split())
                continue
            if RE_DUNITX_ATTRIBUTE.search(line) and section in NO_RTTI_SECTIONS:
                problems.append((rel_path(dunitx_path, cfg.root),
                                  'line %d: DUnitX attribute in a %s section -- '
                                  'the default RTTI can\'t see it, it will never run'
                                  % (n, section)))
    return problems


# RTL identifiers that only exist on one side. Deliberately SHORT: every
# entry here has cost a real round-trip through the IDE; a speculative list
# would only produce false positives. See references/rtl-gotchas.md in this
# skill for the full set of Delphi/FPC divergences, which doesn't fit a
# simple heuristic.
FPC_ONLY = (
    'GetTempDir',       # on Delphi: TPath.GetTempPath (System.IOUtils)
    'GetLastOSError',   # on Delphi: a project-specific wrapper (RaiseLastOSError RAISES)
)
DELPHI_ONLY = (
    'TPath',                         # System.IOUtils doesn't serve FPC 3.2
    'ReportMemoryLeaksOnShutdown',   # doesn't exist on FPC
    'RaiseLastOSError',
)

# On Delphi the unit is System.SysUtils: qualifying as `SysUtils.Xxx` doesn't
# compile (E2003). On FPC it's the opposite -- `System.SysUtils.` doesn't
# exist.
RE_QUALIFIER_SHORT = re.compile(r'(?<![\w.])SysUtils\s*\.\s*[A-Za-z]')
RE_QUALIFIER_LONG = re.compile(r'(?<![\w.])System\s*\.\s*SysUtils\s*\.')


def find_identifiers(body, names):
    """Occurrences of `names` used as an identifier, with or without parens.

    Different from find_calls on purpose: `GetTempDir` and `TPath` show up
    WITHOUT parentheses right after them too (e.g.
    `IncludeTrailingPathDelimiter(GetTempDir)`, `TPath.GetTempPath`), and
    requiring a `(` would let both slip through -- which is exactly what
    happened with an earlier version of this check.
    """
    found = []
    for name in names:
        pattern = r'(?<![\w.])' + name + r'(?![\w])'
        for m in re.finditer(pattern, body, re.IGNORECASE):
            found.append((name, body.count('\n', 0, m.start()) + 1))
    return found


def check_rtl_dialect(cfg):
    """[5] RTL from one compiler's dialect written into the other's mirror."""
    problems = []
    for dunitx_path, fpc_path in mirrored_pairs(cfg):
        body = strip_comments_and_strings(read_file(dunitx_path))
        for name, line in find_identifiers(body, FPC_ONLY):
            problems.append((rel_path(dunitx_path, cfg.root),
                              'line %d: %s only exists on FPC' % (line, name)))
        for m in RE_QUALIFIER_SHORT.finditer(body):
            problems.append((rel_path(dunitx_path, cfg.root),
                              'line %d: SysUtils. qualifier -- on Delphi the unit is System.SysUtils'
                              % (body.count('\n', 0, m.start()) + 1)))
        body = strip_comments_and_strings(read_file(fpc_path))
        for name, line in find_identifiers(body, DELPHI_ONLY):
            problems.append((rel_path(fpc_path, cfg.root),
                              'line %d: %s only exists on Delphi' % (line, name)))
        for m in RE_QUALIFIER_LONG.finditer(body):
            problems.append((rel_path(fpc_path, cfg.root),
                              'line %d: System.SysUtils. qualifier -- on FPC the unit is SysUtils'
                              % (body.count('\n', 0, m.start()) + 1)))
    return problems


# Each check takes the parsed config and returns a list of (rel_path, msg)
# tuples. To add a project-specific check (e.g. a sub-package unit-list
# parity check like the one dropped from the original script -- see the
# module docstring), append a function with this same signature here.
CHECKS = [
    ('code after initialization', lint_code_after_initialization),
    ('mirror parity (declared tests + registration)', check_mirror_parity),
    ('assertion dialect', check_assertion_dialect),
    ('DUnitX attribute visibility', check_attribute_visibility),
    ('RTL dialect', check_rtl_dialect),
]


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0] if __doc__ else '')
    p.add_argument('--root', default=os.getcwd(),
                    help='Project root to scan from (default: current directory)')
    p.add_argument('--dirs', default='tests',
                    help='Comma-separated directories to scan, relative to --root '
                         '(default: tests)')
    p.add_argument('--mirror-subdir', default='fpc',
                    help='Name of the subfolder that holds the FPCUnit mirror of a '
                         'DUnitX file one level up (default: fpc)')
    p.add_argument('--ignore-glob', default=','.join(DEFAULT_IGNORE),
                    help='Comma-separated substrings; any path containing one is skipped')
    args = p.parse_args(argv)
    args.root = os.path.abspath(args.root)
    args.dirs = [d.strip() for d in args.dirs.split(',') if d.strip()]
    args.ignore = [s for s in args.ignore_glob.split(',') if s]
    return args


def main(argv=None):
    cfg = parse_args(argv if argv is not None else sys.argv[1:])
    failed = False

    for n, (label, check) in enumerate(CHECKS, 1):
        print('[%d] %s' % (n, label))
        problems = check(cfg)
        if problems:
            failed = True
            for path, msg in problems:
                print('    FAIL  %s: %s' % (path, msg))
        else:
            print('    ok')

    if failed:
        print('\nDIVERGENCES FOUND')
        return 1
    print('\nclean')
    return 0


if __name__ == '__main__':
    sys.exit(main())
