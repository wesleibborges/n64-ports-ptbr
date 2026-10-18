#!/usr/bin/env python3
"""Compara layouts SPIR-V DX vs GL (offsets reais via spirv-dis) e deriva o padding necessario.

Motivacao: queremos UM unico conjunto de blobs que sirva tanto para Vulkan/D3D12/Metal
(que hoje usam `-fvk-use-dx-layout`) quanto para conversao a GLSL ES (que exige std430).
Se tornarmos o layout DX identico ao std430 inserindo padding explicito nos headers
HLSL/C++ duais, o MESMO .spv serve para todos os backends -- sem duplicar blobs nem
duplicar layouts no C++ host.

Este script mede, de forma autoritativa (offsets reais decorados no SPIR-V), o que
divergir entre o layout DX (atual) e o layout GL (std430) e sugere o padding.

Uso: m1_layout_diff.py <dir_com_pares_dx_gl> [filtro_nome]
"""
import glob
import os
import re
import subprocess
import sys

RE_MEMNAME = re.compile(r'OpMemberName\s+(%\S+)\s+(\d+)\s+"(.*)"')
RE_MEMDEC = re.compile(r'OpMemberDecorate\s+(%\S+)\s+(\d+)\s+Offset\s+(\d+)')
RE_OPNAME = re.compile(r'OpName\s+(%\S+)\s+"(.*)"')
RE_STRUCT = re.compile(r'(%\S+)\s*=\s*OpTypeStruct\s*(.*)$')
RE_TYPE = re.compile(r'(%\S+)\s*=\s*OpType(\w+)\s*(.*)$')
RE_STRIDE = re.compile(r'OpDecorate\s+(%\S+)\s+ArrayStride\s+(\d+)')


def strip(i):
    return i.lstrip('%')


def parse(path):
    txt = subprocess.run(['spirv-dis', path], capture_output=True, text=True).stdout
    names, memnames, offsets, structs, types, strides = {}, {}, {}, {}, {}, {}
    for line in txt.splitlines():
        line = line.strip()
        m = RE_MEMNAME.search(line)
        if m:
            memnames.setdefault(strip(m.group(1)), {})[int(m.group(2))] = m.group(3)
            continue
        m = RE_MEMDEC.search(line)
        if m:
            offsets.setdefault(strip(m.group(1)), {})[int(m.group(2))] = int(m.group(3))
            continue
        m = RE_STRIDE.search(line)
        if m:
            strides[strip(m.group(1))] = int(m.group(2))
            continue
        m = RE_STRUCT.search(line)
        if m:
            structs[strip(m.group(1))] = [strip(x) for x in m.group(2).split()]
            continue
        m = RE_OPNAME.search(line)
        if m:
            names[strip(m.group(1))] = m.group(2)
            continue
        m = RE_TYPE.search(line)
        if m:
            types[strip(m.group(1))] = (m.group(2), m.group(3).strip())

    out = {}
    for sid, offs in offsets.items():
        sname = names.get(sid, sid)
        tid = structs.get(sid, [])
        mems = []
        for idx in sorted(offs):
            if idx < len(tid):
                tname, targs = types.get(tid[idx], ('?', ''))
            else:
                tname, targs = '?', ''
            mems.append({'i': idx, 'name': memnames.get(sid, {}).get(idx, '?'),
                         'off': offs[idx], 'type': tname, 'args': targs})
        out[sname] = {'mems': mems, 'stride': strides.get(sid)}
    return out


def is_vec3(m):
    return m['type'] == 'Vector' and m['args'].split()[-1:] == ['3']


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else '/root/bhrecomp/m1_layout_matrix2'
    filt = sys.argv[2] if len(sys.argv) > 2 else None

    pairs = []
    for dx in sorted(glob.glob(os.path.join(d, '*.dx.spv'))):
        gl = dx[:-len('.dx.spv')] + '.gl.spv'
        if os.path.exists(gl):
            pairs.append((os.path.basename(dx)[:-len('.dx.spv')], dx, gl))

    print('# Diff de layout DX vs GL — %d pares de blobs\n' % len(pairs))

    # struct_name -> signature_dx -> {offsets, info}
    seen = {}
    for name, dx, gl in pairs:
        if filt and filt not in name:
            continue
        sx, sg = parse(dx), parse(gl)
        for sname in sx:
            if sname not in sg or not sx[sname]['mems']:
                continue
            mx, mg = sx[sname]['mems'], sg[sname]['mems']
            ox = [m['off'] for m in mx]
            og = [m['off'] for m in mg]
            if ox == og and sx[sname]['stride'] == sg[sname]['stride']:
                continue  # identico, nao precisa padding
            key = (sname, tuple(ox))
            rec = seen.setdefault(key, {'struct': sname, 'dx': mx, 'gl': mg,
                                        'stride_dx': sx[sname]['stride'],
                                        'stride_gl': sg[sname]['stride'],
                                        'shaders': []})
            rec['shaders'].append(name)

    if not seen:
        print('Nenhuma divergencia de layout encontrada.')
        return

    print('## Structs com layout divergente (precisam de padding explicito)\n')
    total = 0
    for key, rec in sorted(seen.items()):
        total += 1
        print('### %s  (stride DX=%s GL=%s) — em %d shader(s)\n'
              % (rec['struct'], rec['stride_dx'], rec['stride_gl'], len(rec['shaders'])))
        print('| idx | membro | off DX | off GL | tipo | acao |')
        print('|---|---|---|---|---|---|')
        for a, b in zip(rec['dx'], rec['gl']):
            acao = ''
            if a['off'] != b['off']:
                delta = b['off'] - a['off']
                if is_vec3(a) and a['off'] % 16 != 0:
                    acao = 'inserir %d byte(s) de padding antes (vec3 precisa alinhar a 16)' % delta
                else:
                    acao = 'deslocado em %+d (consequencia do padding anterior)' % delta
            print('| %d | %s | %d | %d | %s %s | %s |'
                  % (a['i'], a['name'], a['off'], b['off'], a['type'], a['args'], acao))
        print('')

    # consolidado por struct (independente da assinatura)
    bystruct = {}
    for key, rec in seen.items():
        bystruct.setdefault(rec['struct'], set()).update(rec['shaders'])
    print('## Lista consolidada de headers a ajustar (%d structs)\n' % len(bystruct))
    for s in sorted(bystruct):
        n = len(bystruct[s])
        print('- `%s` — afeta %d shader(s)' % (s, n))


if __name__ == '__main__':
    main()