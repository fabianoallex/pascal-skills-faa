"""Compile and run every RTTI probe (p*.dpr) from the command line, one program per
feature, and print each probe's compile result and output side by side.

Usage:
    python run_probes.py              # all probes, FPC only
    python run_probes.py p08 p09      # only probes whose name contains p08 or p09
    COMPILERS=fpc,delphi python run_probes.py

Delphi is off by default: Delphi Community Edition refuses command-line builds
("This version of the product does not support command line compiling"). With CE,
use gen_delphi.py and run the generated project in the IDE instead. With a paid
edition, add `delphi` to COMPILERS.

Compiler paths come from the FPC / DCC environment variables, falling back to the
Lazarus 4.0 and Delphi 12 default install locations. Both are built for Win64.
"""
import glob, os, re, subprocess, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
DCC = os.environ.get('DCC', r'C:\Program Files (x86)\Embarcadero\Studio\23.0\bin\dcc64.exe')
FPC = os.environ.get('FPC', r'C:\lazarus4.0\fpc\3.2.2\bin\x86_64-win64\fpc.exe')
COMPILERS = os.environ.get('COMPILERS', 'fpc').split(',')


def build(compiler, src, out):
    os.makedirs(out, exist_ok=True)
    if compiler == 'delphi':
        cmd = [DCC, '-Q', '-B', '-E' + out, '-NU' + out, '-NSSystem;Winapi', src]
        err_re = re.compile(r'(Error|Fatal)', re.I)
    else:
        cmd = [FPC, '-B', '-FE' + out, '-FU' + out, src]
        err_re = re.compile(r'(Error:|Fatal:)')
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, errors='replace')
    text = p.stdout + p.stderr
    errs = [l.strip() for l in text.splitlines() if err_re.search(l) and 'Compilation aborted' not in l]
    # The "Unit Rtti is experimental" warning fires on every FPC probe -- noise.
    warns = [l.strip() for l in text.splitlines() if 'Warning' in l and 'experimental' not in l]
    return p.returncode == 0, errs[:3], warns[:3]


def run(exe):
    try:
        p = subprocess.run([exe], capture_output=True, text=True, timeout=20, errors='replace')
        out = p.stdout.strip()
        if p.returncode != 0:
            out += '\n<exit code %d> %s' % (p.returncode, p.stderr.strip()[:300])
        return out
    except subprocess.TimeoutExpired:
        return '<timeout>'


results = {}
for src in sorted(glob.glob(os.path.join(HERE, 'p*.dpr'))):
    name = os.path.splitext(os.path.basename(src))[0]
    if len(sys.argv) > 1 and not any(a in name for a in sys.argv[1:]):
        continue
    r = {}
    for c in COMPILERS:
        out = os.path.join(HERE, 'out', c)
        ok, errs, warns = build(c, os.path.basename(src), out)
        r[c] = {'compiled': ok, 'errors': errs, 'warnings': warns,
                'output': run(os.path.join(out, name + '.exe')) if ok else ''}
    results[name] = r
    print('=' * 70)
    print(name)
    for c in COMPILERS:
        x = r[c]
        print('  [%s] %s' % (c, 'COMPILED' if x['compiled'] else 'COMPILE FAILED'))
        for e in x['errors']:
            print('      ! ' + e)
        for w in x['warnings']:
            print('      ~ ' + w)
        for line in x['output'].splitlines():
            print('      ' + line)

with open(os.path.join(HERE, 'out', 'results.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
