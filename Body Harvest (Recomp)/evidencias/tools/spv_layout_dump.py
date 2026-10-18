#!/usr/bin/env python3
"""Dump autoritativo de layouts de um .spv via `spirv-dis` (le decoracoes reais).

Corrige o defeito dos auditores anteriores: normaliza ids removendo o '%'
em TODAS as referencias (OpMemberName/OpMemberDecorate/OpTypeStruct), o que
fazia nenhum tipo resolver e zerava offsets/sizes.

Uso: spv_layout_dump.py <arquivo.spv> [filtro_nome]
Imprime, para cada struct com Offset: nome da struct, tamanho (se OpDecorate
ArrayStride/size known) e membros com nome + offset.
"""
import re
import subprocess
import sys

RE_OPNAME = re.compile(r'OpName\s+(%\S+)\s+"(.*)"')
RE_MEMNAME = re.compile(r'OpMemberName\s+(%\S+)\s+(\d+)\s+"(.*)"')
RE_MEMDEC = re.compile(r'OpMemberDecorate\s+(%\S+)\s+(\d+)\s+Offset\s+(\d+)')
RE_MEMDEC_ALL = re.compile(r'OpMemberDecorate\s+(%\S+)\s+(\d+)\s+(\w+)\s*(.*)')
RE_STRIDE = re.compile(r'OpDecorate\s+(%\S+)\s+ArrayStride\s+(\d+)')
# spirv-dis emite tipos como `%id = OpTypeXxx ...` (com '='), nao `OpTypeXxx %id ...`
RE_STRUCT = re.compile(r'(%\S+)\s*=\s*OpTypeStruct\s*(.*)$')
RE_TYPE = re.compile(r'(%\S+)\s*=\s*OpType(\w+)\s*(.*)$')


def strip(i):
    return i.lstrip('%')


def main():
    path = sys.argv[1]
    filt = sys.argv[2] if len(sys.argv) > 2 else None
    txt = subprocess.run(['spirv-dis', path], capture_output=True, text=True).stdout
    names = {}
    memnames = {}
    offsets = {}
    strides = {}
    structs = {}
    types = {}
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
            # regex novo: group(1)=id, group(2)=nome do tipo, group(3)=args
            types[strip(m.group(1))] = (m.group(2), m.group(3).strip())
    print('=== %s ===' % path)
    for sid, offs in offsets.items():
        sname = names.get(sid, sid)
        if filt and filt not in sname:
            continue
        order = sorted(offs)
        print('struct %s (id %%%s)' % (sname, sid))
        if sid in strides:
            print('  ArrayStride %d' % strides[sid])
        for idx in order:
            mem = memnames.get(sid, {}).get(idx, '?')
            tid = structs.get(sid, [])
            tname, targs = '?', ''
            if idx < len(tid):
                tname, targs = types.get(tid[idx], ('?', ''))
            tdesc = ('%s %s' % (tname, targs)).strip()
            flag = ''
            if tname == 'Vector' and targs.split()[-1:] == ['3'] and offs[idx] % 16 != 0:
                flag = '  <-- VEC3 NAO ALINHADO A 16'
            print('  [%2d] %-26s off=%-4d %s%s' % (idx, mem, offs[idx], tdesc, flag))
        print('')


if __name__ == '__main__':
    main()