#!/usr/bin/env python3
"""M1 - Compara os offsets dos blobs REAIS (layout DX + padding) contra os blobs
std430 (`.gl.spv`) da matriz de referencia.

Por que nao comparar index-a-index: o padding adicionou MEMBROS NOVOS
(`padding0/1/2...`), que nao existem nos blobs de referencia. Portanto a
comparacao correta e pela INTERSECCAO de nomes de membros: se todo membro
significativo cai no MESMO offset do std430, o layout DX+padding == std430.

Criterio de aceite do M1: 0 divergencias.

Uso: python3 m1_offset_compare.py
"""
import glob
import os
import re
import subprocess
import sys

BUILD = '/root/bhrecomp/build-aarch64'
MATRIX = '/root/bhrecomp/m1_layout_matrix2'

RE_MEMNAME = re.compile(r'OpMemberName\s+(%\S+)\s+(\d+)\s+"(.*)"')
RE_MEMDEC = re.compile(r'OpMemberDecorate\s+(%\S+)\s+(\d+)\s+Offset\s+(\d+)')
RE_OPNAME = re.compile(r'OpName\s+(%\S+)\s+"(.*)"')


def parse(path):
    txt = subprocess.run(['spirv-dis', path], capture_output=True, text=True).stdout
    names, memnames, offsets = {}, {}, {}
    for line in txt.splitlines():
        line = line.strip()
        m = RE_MEMNAME.search(line)
        if m:
            memnames.setdefault(m.group(1).lstrip('%'), {})[int(m.group(2))] = m.group(3)
            continue
        m = RE_MEMDEC.search(line)
        if m:
            offsets.setdefault(m.group(1).lstrip('%'), {})[int(m.group(2))] = int(m.group(3))
            continue
        m = RE_OPNAME.search(line)
        if m:
            names[m.group(1).lstrip('%')] = m.group(2)
    out = {}
    for sid, offs in offsets.items():
        sname = names.get(sid, sid)
        mem = {}
        for idx, off in offs.items():
            nm = memnames.get(sid, {}).get(idx)
            if nm is not None:
                mem[nm] = off
        if mem:
            out[sname] = mem
    return out


def main():
    blobs = sorted(glob.glob(os.path.join(BUILD, '**', '*.hlsl.spv'), recursive=True))
    checked = 0
    failed = []
    for spv in blobs:
        base = os.path.basename(spv)
        ref = os.path.join(MATRIX, base + '.gl.spv')
        if not os.path.exists(ref):
            continue
        dx_s = parse(spv)
        gl_s = parse(ref)
        for sname, dxm in dx_s.items():
            # casa structs cujo nome pode ter prefixo (ex.: type.ConstantBuffer.RasterParams)
            gl_name = None
            for cand in gl_s:
                if cand == sname or cand.endswith(sname.split('.')[-1]) \
                        or sname.endswith(cand.split('.')[-1]):
                    gl_name = cand
                    break
            if gl_name is None:
                continue
            glm = gl_s[gl_name]
            common = [k for k in dxm if k in glm]
            if not common:
                continue
            checked += 1
            diffs = [k for k in common if dxm[k] != glm[k]]
            tag = 'OK' if not diffs else 'DIVERGE'
            print('%-34s %-40s %s' % (base.replace('.hlsl.spv', ''), sname, tag))
            for k in sorted(common):
                mark = '' if dxm[k] == glm[k] else '  <-- DIFF'
                print('    %-14s DX+pad=%-4d std430=%-4d%s'
                      % (k, dxm[k], glm[k], mark))
            if diffs:
                failed.append((base, sname, diffs))
    print()
    print('structs comparados: %d | divergentes: %d' % (checked, len(failed)))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())