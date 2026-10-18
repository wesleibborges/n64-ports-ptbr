#!/usr/bin/env python3
"""Analisa o results.tsv da matriz de layout DX vs GL (M1) e emite relatorio markdown.

Uso: m1_matrix_analyze.py [results.tsv]

Colunas: shader, stage, dxc_dx, val_dx, xc_dx, glsl_dx, dxc_gl, val_gl, xc_gl, glsl_gl
 - dxc_*  : return code do DXC
 - val_*  : return code do spirv-val (0 = SPIR-V Vulkan valido); 'NA' se ausente
 - xc_*   : return code do SPIRV-Cross (--es --version 320)
 - glsl_* : return code do glslangValidator; 99 = nao executado (xc falhou antes)

Tolerante ao separador: aceita TAB real ou a sequencia literal \\t.
"""
import sys

COLS = ['shader', 'stage', 'dxc_dx', 'val_dx', 'xc_dx', 'glsl_dx',
        'dxc_gl', 'val_gl', 'xc_gl', 'glsl_gl']


def load(path):
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('shader'):
                continue
            parts = line.replace('\\t', '\t').split('\t')
            if len(parts) < len(COLS):
                continue
            rows.append(dict(zip(COLS, parts)))
    return rows


def rc(v):
    """Normaliza return code: 'NA' (nao aplicavel) -> None."""
    return None if v == 'NA' else int(v)


def failing(rows, key):
    """Shaders cujo retorno != 0 (ignora NA e 99=nao-executado)."""
    out = []
    for r in rows:
        v = rc(r[key])
        if v is None or v == 99:
            continue
        if v != 0:
            out.append((r['shader'], r['stage'], v))
    return out


def not_run(rows, key):
    return [r['shader'] for r in rows if r[key] == '99']


def table(title, items):
    print('\n### %s (%d)\n' % (title, len(items)))
    if not items:
        print('_nenhum_')
        return
    print('| shader | stage | rc |')
    print('|---|---|---|')
    for name, stage, v in items:
        print('| %s | %s | %s |' % (name, stage, v))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/root/bhrecomp/m1_layout_matrix2/results.tsv'
    rows = load(path)
    n = len(rows)
    print('## Matriz de layout DX vs GL — %d shaders\n' % n)
    print('Fonte: `%s`\n' % path)

    dxv = failing(rows, 'val_dx')
    glv = failing(rows, 'val_gl')
    dxx = failing(rows, 'xc_dx')
    glx = failing(rows, 'xc_gl')
    dxg = failing(rows, 'glsl_dx')
    glg = failing(rows, 'glsl_gl')

    print('| metrica | DX layout (atual) | GL layout (candidato) |')
    print('|---|---|---|')
    print('| DXC falhou | %d | %d |' % (
        len(failing(rows, 'dxc_dx')), len(failing(rows, 'dxc_gl'))))
    print('| spirv-val falhou (SPIR-V invalido) | %d | %d |' % (len(dxv), len(glv)))
    print('| SPIRV-Cross falhou (>=ES 320) | %d | %d |' % (len(dxx), len(glx)))
    print('| glslangValidator falhou | %d | %d |' % (len(dxg), len(glg)))

    table('spirv-val FALHOU com layout DX (SPIR-V Vulkan invalido)', dxv)
    table('SPIRV-Cross FALHOU com layout DX', dxx)
    table('SPIRV-Cross FALHOU com layout GL', glx)
    table('glslangValidator FALHOU com layout DX', dxg)
    table('glslangValidator FALHOU com layout GL', glg)

    # falhas independentes do layout (falham em ambos)
    both = sorted(set(r[0] for r in glg) & set(r[0] for r in dxg))
    print('\n### glslang FALHA em AMBOS os layouts (independente de layout) (%d)\n' % len(both))
    for s in both:
        print('- %s' % s)

    # DX-only glslang fails (resolvidos pela troca de layout)
    dxonly = sorted(set(r[0] for r in dxg) - set(both))
    print('\n### glslang falhava so em DX e passou em GL (resolvido pelo layout) (%d)\n' % len(dxonly))
    for s in dxonly:
        print('- %s' % s)

    print('\n### Nao executados (99) com GL (xc nao produziu GLSL): checar\n')
    print('val_dx  : %s' % not_run(rows, 'val_dx'))
    print('val_gl  : %s' % not_run(rows, 'val_gl'))


if __name__ == '__main__':
    main()