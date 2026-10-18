#!/usr/bin/env python3
"""M1 - Valida os 58 blobs SPIR-V do RT64 regenerados APOS o padding de layout.

Criterios de aceite do M1 (comparaveis com evidencias/evidence_m1_layout_matrix_20261018.md):
  1. `spirv-val --target-env vulkan1.0`  -> 0 falhas (antes: 13)
  2. `spirv-cross --es --version 320`    -> 0 falhas (antes: 10)
  3. offsets do layout DX dos blobs REAIS == offsets std430 (blobs .gl.spv da matriz)
     -> provado por m1_layout_diff.py sobre os pares montados em OUT/pairs

Falhas esperadas (ortogonais, M1.1): usampler1D (8), noperspective (Im3DVS),
image load-store format (DebugPS) -> aparecem so no glslangValidator.

Uso: python3 m1_validate_blobs.py
"""
import concurrent.futures
import glob
import os
import re
import subprocess
import sys

BUILD = '/root/bhrecomp/build-aarch64'
MATRIX = '/root/bhrecomp/m1_layout_matrix2'
TOOLS = '/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools'
OUT = '/root/bhrecomp/m1_apply_20261018'
PAIRS = os.path.join(OUT, 'pairs')

RE_STAGE = re.compile(r'(CS|VS|PS|GS)(?:MS|2X|4X|8X)?\.hlsl\.spv$')


def stage_ext(spv):
    m = RE_STAGE.search(os.path.basename(spv))
    if not m:
        return 'frag'
    return {'CS': 'comp', 'VS': 'vert', 'GS': 'geom', 'PS': 'frag'}[m.group(1)]


def run(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def validate(spv):
    ext = stage_ext(spv)
    base = os.path.basename(spv)[:-len('.hlsl.spv')]
    outdir = os.path.join(OUT, 'xc')
    os.makedirs(outdir, exist_ok=True)
    outfile = os.path.join(outdir, '%s.%s' % (base, ext))

    rc_val, log_val = run(['spirv-val', '--target-env', 'vulkan1.0', spv])
    rc_xc, log_xc = run(['spirv-cross', '--es', '--version', '320', spv,
                         '--output', outfile])
    rc_gl, log_gl = (99, '(nao executado)')
    if rc_xc == 0 and os.path.exists(outfile) and os.path.getsize(outfile) > 0:
        rc_gl, log_gl = run(['glslangValidator', '-S', ext, outfile])
        with open(os.path.join(outdir, '%s.glslang.log' % base), 'w',
                  encoding='utf-8') as fh:
            fh.write(log_gl)
    return {
        'name': base, 'ext': ext, 'val': rc_val, 'xc': rc_xc, 'glslang': rc_gl,
        'val_msg': log_val.strip()[:200], 'xc_msg': log_xc.strip()[:200],
        'gl_msg': log_gl.strip().splitlines()[-1][:120] if log_gl.strip() else '',
    }


def build_pairs():
    """Monta pares <blob-real>.dx.spv x <blob-std430-da-matriz>.gl.spv.

    Convencao de nomes da matriz (m1_layout_matrix2): <NAME>.hlsl.spv.dx.spv e
    <NAME>.hlsl.spv.gl.spv, onde <NAME>.hlsl.spv e o basename do blob real.
    """
    os.makedirs(PAIRS, exist_ok=True)
    for f in os.listdir(PAIRS):
        os.remove(os.path.join(PAIRS, f))
    n = 0
    missing = []
    for spv in sorted(glob.glob(os.path.join(BUILD, '**', '*.hlsl.spv'),
                                recursive=True)):
        base = os.path.basename(spv)
        dx = os.path.join(PAIRS, base + '.dx.spv')
        gl = os.path.join(PAIRS, base + '.gl.spv')
        os.symlink(spv, dx)
        ref = os.path.join(MATRIX, base + '.gl.spv')
        if os.path.exists(ref):
            os.symlink(ref, gl)
            n += 1
        else:
            missing.append(base)
    if missing:
        print('AVISO: sem referencia std430 na matriz: %s' % ', '.join(missing[:5]))
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    blobs = sorted(glob.glob(os.path.join(BUILD, '**', '*.hlsl.spv'),
                             recursive=True))
    print('blobs encontrados: %d' % len(blobs))
    if len(blobs) != 58:
        print('ATENCAO: esperado 58')
    print()

    res = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(validate, blobs):
            res.append(r)

    print('%-34s %-5s %4s %4s %7s' % ('shader', 'stage', 'val', 'xc', 'glslang'))
    print('-' * 62)
    for r in res:
        print('%-34s %-5s %4d %4d %7d  %s'
              % (r['name'], r['ext'], r['val'], r['xc'], r['glslang'],
                 '' if r['glslang'] == 0 else r['gl_msg']))

    nval = sum(1 for r in res if r['val'] != 0)
    nxc = sum(1 for r in res if r['xc'] != 0)
    ngl = sum(1 for r in res if r['glslang'] != 0)
    print()
    print('RESUMO: spirv-val falhas=%d (antes 13) | spirv-cross falhas=%d (antes 10) '
          '| glslang falhas=%d' % (nval, nxc, ngl))

    # ---- atribuicao de causa das falhas de glslang (agregado) ----
    causes = {}
    for r in res:
        if r['glslang'] == 0:
            continue
        logf = os.path.join(OUT, 'xc', '%s.glslang.log' % r['name'])
        first = '?'
        if os.path.exists(logf):
            for line in open(logf, encoding='utf-8', errors='replace'):
                if 'ERROR' in line and 'compilation errors' not in line:
                    first = line.strip()
                    break
        causes.setdefault(first, []).append(r['name'])
    if causes:
        print()
        print('=== causas das falhas de glslang (ESSL 320) ===')
        for cause, names in sorted(causes.items(), key=lambda kv: -len(kv[1])):
            print('%-3d %s' % (len(names), cause))
            print('     shaders: %s' % ', '.join(names))

    tsv = os.path.join(OUT, 'validacao_blobs.tsv')
    with open(tsv, 'w', encoding='utf-8') as fh:
        fh.write('shader\tstage\tspirv_val\tspirv_cross\tglslang\tglslang_msg\n')
        for r in res:
            fh.write('%s\t%s\t%d\t%d\t%d\t%s\n'
                     % (r['name'], r['ext'], r['val'], r['xc'], r['glslang'],
                        r['gl_msg'].replace('\t', ' ')))
    print('tabela: %s' % tsv)

    npairs = build_pairs()
    print('pares DX(real) x GL(std430) montados: %d' % npairs)
    print()
    print('=== diff de layout: blobs REAIS (DX+padding) vs std430 ===')
    rc, out = run(['python3', os.path.join(TOOLS, 'm1_layout_diff.py'), PAIRS])
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())