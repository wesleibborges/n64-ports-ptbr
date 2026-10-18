#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spv_block_audit.py -- Auditoria de blocos de interface (UBO/SSBO) em blobs SPIR-V.

Contexto: M1 do plano docs/PLANO_BACKEND_GLES_R36S.md.

O RT64 compila HLSL -> SPIR-V com DXC usando -fvk-use-dx-layout. Para o backend
GLES (R36S / Mali Bifrost G31) precisamos emitir GLSL ES 3.20 via SPIRV-Cross,
que recusa blocos cujo layout nao seja expressavel em std140/std430:

    "Buffer block cannot be expressed as any of std430, std140, scalar,
     even with enhanced layouts."

Este script descobre QUAIS structs (e quais membros exatos) causam a divergencia,
comparando os Offsets decorados no SPIR-V (layout DX real, gerado pelo DXC) com os
offsets que std430/std140 exigiriam. Tambem calcula o padding minimo que tornaria
o layout DX identico ao GLSL, para guiar a correcao dos headers dual HLSL/C++ em
src/shared/.

Uso:
    python3 spv_block_audit.py <dir_com_spv> [mais_dirs...]

Saida: relatorio em stdout (redirecionar p/ arquivo de evidencia).
Somente leitura: nao altera nenhum arquivo do RT64.
"""

import collections
import glob
import os
import re
import subprocess
import sys

# ----------------------------------------------------------------------------
# Padroes do SPIR-V assembly (spirv-dis)
# ----------------------------------------------------------------------------
R_TY_INT    = re.compile(r'^\s*%(\S+) = OpTypeInt (\d+) (\d+)')
R_TY_FLOAT  = re.compile(r'^\s*%(\S+) = OpTypeFloat (\d+)')
R_TY_VEC    = re.compile(r'^\s*%(\S+) = OpTypeVector %(\S+) (\d+)')
R_TY_MAT    = re.compile(r'^\s*%(\S+) = OpTypeMatrix %(\S+) (\d+)')
R_TY_ARR    = re.compile(r'^\s*%(\S+) = OpTypeArray %(\S+) %(\S+)')
R_TY_RARR   = re.compile(r'^\s*%(\S+) = OpTypeRuntimeArray %(\S+)')
R_TY_STR    = re.compile(r'^\s*%(\S+) = OpTypeStruct (.*)$')
R_CONST     = re.compile(r'^\s*%(\S+) = OpConstant %(\S+) (\d+)')
R_DBLK      = re.compile(r'^\s*OpDecorate %(\S+) (Block|BufferBlock)\s*$')
R_MOFF      = re.compile(r'^\s*OpMemberDecorate %(\S+) (\d+) Offset (\d+)')
R_ASTRIDE   = re.compile(r'^\s*OpDecorate %(\S+) ArrayStride (\d+)')
R_NAME      = re.compile(r'^\s*OpName %(\S+) "(.*)"')
R_MNAME     = re.compile(r'^\s*OpMemberName %(\S+) (\d+) "(.*)"')


class Mod:
    """Modelo de tipos extraido de um unico arquivo SPIR-V."""

    def __init__(self):
        self.int_w = {}                                   # id -> largura (32/64)
        self.flt_w = {}                                   # id -> largura
        self.vec = {}                                     # id -> (comp_id, n)
        self.mat = {}                                     # id -> (col_id, ncols)
        self.arr = {}                                     # id -> (elem_id, count)
        self.rarr = {}                                    # id -> elem_id
        self.struct = {}                                  # id -> [member ids]
        self.const = {}                                   # id -> valor inteiro
        self.name = {}                                    # id -> nome
        self.mname = collections.defaultdict(dict)        # id -> {idx: nome}
        self.block = {}                                   # id -> Block|BufferBlock
        self.offset = collections.defaultdict(dict)       # id -> {idx: offset}
        self.stride = {}                                  # id -> ArrayStride


def parse_spv(path):
    """Executa spirv-dis e preenche um Mod. Retorna None em caso de falha."""
    try:
        out = subprocess.run(['spirv-dis', path], capture_output=True,
                             text=True, timeout=60).stdout
    except Exception:
        return None
    if not out:
        return None
    m = Mod()
    for ln in out.splitlines():
        if 'OpTypeStruct' in ln:
            r = R_TY_STR.match(ln)
            if r:
                # spirv-dis emite os ids dos membros com '%' (ex: "%float");
                # todos os mapas de tipo usam ids SEM '%', logo normalizamos aqui.
                m.struct[r.group(1)] = [x.lstrip('%') for x in r.group(2).split()]
                continue
        if 'OpName' in ln and 'OpMemberName' not in ln:
            r = R_NAME.match(ln)
            if r:
                m.name[r.group(1)] = r.group(2)
                continue
        if 'OpMemberName' in ln:
            r = R_MNAME.match(ln)
            if r:
                m.mname[r.group(1)][int(r.group(2))] = r.group(3)
                continue
        if 'OpMemberDecorate' in ln:
            r = R_MOFF.match(ln)
            if r:
                m.offset[r.group(1)][int(r.group(2))] = int(r.group(3))
                continue
        if 'OpDecorate' in ln:
            r = R_DBLK.match(ln)
            if r:
                m.block[r.group(1)] = r.group(2)
                continue
            r = R_ASTRIDE.match(ln)
            if r:
                m.stride[r.group(1)] = int(r.group(2))
                continue
            continue
        if 'OpTypeVector' in ln:
            r = R_TY_VEC.match(ln)
            if r:
                m.vec[r.group(1)] = (r.group(2), int(r.group(3)))
                continue
        if 'OpTypeMatrix' in ln:
            r = R_TY_MAT.match(ln)
            if r:
                m.mat[r.group(1)] = (r.group(2), int(r.group(3)))
                continue
        if 'OpTypeArray' in ln:
            r = R_TY_ARR.match(ln)
            if r:
                m.arr[r.group(1)] = (r.group(2), r.group(3))
                continue
        if 'OpTypeRuntimeArray' in ln:
            r = R_TY_RARR.match(ln)
            if r:
                m.rarr[r.group(1)] = r.group(2)
                continue
        if 'OpConstant' in ln:
            r = R_CONST.match(ln)
            if r:
                # Constantes float podem vir como "0.5"; interessa apenas o valor
                # inteiro (tamanho de array), entao o parse e tolerante.
                try:
                    m.const[r.group(1)] = int(r.group(3))
                except ValueError:
                    try:
                        m.const[r.group(1)] = int(float(r.group(3)))
                    except ValueError:
                        pass
                continue
        if 'OpTypeFloat' in ln:
            r = R_TY_FLOAT.match(ln)
            if r:
                m.flt_w[r.group(1)] = int(r.group(2))
                continue
        if 'OpTypeInt' in ln:
            r = R_TY_INT.match(ln)
            if r:
                m.int_w[r.group(1)] = int(r.group(2))
                continue
    return m


# ----------------------------------------------------------------------------
# Matematica de layout (std430 / std140)
# ----------------------------------------------------------------------------
def round_up(v, a):
    """Arredonda v para o proximo multiplo de a."""
    if a <= 1:
        return v
    return ((v + a - 1) // a) * a


def scalar_desc(m, i):
    """Retorna (bytes, align, nome_hlsl) se i for escalar, senao None."""
    if i in m.int_w:
        w = m.int_w[i]
        return (w // 8, w // 8, 'uint%d' % w)
    if i in m.flt_w:
        w = m.flt_w[i]
        return (w // 8, w // 8, 'float%d' % w)
    return None


def size_align(m, i, std140=False, depth=0):
    """Calcula (size, align) de um tipo SPIR-V segundo std430 (ou std140)."""
    if depth > 8:
        return (0, 1)

    sc = scalar_desc(m, i)
    if sc:
        return (sc[0], sc[1])

    # Vetor: vec2 alinha ao seu tamanho; vec3/vec4 alinham a 4x o escalar
    if i in m.vec:
        e, n = m.vec[i]
        es, ea, _ = scalar_desc(m, e) or (4, 4, '')
        if n <= 2:
            return (n * es, max(n * es, ea))
        return (n * es, 4 * es)

    # Matriz: tratada como array de colunas (vetores)
    if i in m.mat:
        c, ncol = m.mat[i]
        cs, ca = size_align(m, c, std140, depth + 1)
        stride = round_up(ca, 16) if std140 else ca
        return (ncol * stride, stride)

    # Array: stride = tamanho do elemento arredondado ao seu alinhamento
    if i in m.arr:
        e, cnt = m.arr[i]
        es, ea = size_align(m, e, std140, depth + 1)
        stride = round_up(es, ea)
        if std140:
            stride = round_up(stride, 16)
        n = m.const.get(cnt, 0)
        align = round_up(ea, 16) if std140 else ea
        return (stride * n, align)

    # RuntimeArray (SSBO): sem tamanho estatico, stride do elemento
    if i in m.rarr:
        e = m.rarr[i]
        es, ea = size_align(m, e, std140, depth + 1)
        stride = round_up(es, ea)
        if std140:
            stride = round_up(stride, 16)
        return (0, stride)

    # Struct: alinha cada membro e arredonda o total ao maior alinhamento
    if i in m.struct:
        off = 0
        maxa = 1
        for mem in m.struct[i]:
            ms, ma = size_align(m, mem, std140, depth + 1)
            off = round_up(off, ma) + ms
            maxa = max(maxa, ma)
        return (round_up(off, maxa), maxa)

    return (0, 1)


def gl_offsets(m, sid, std140=False):
    """Offsets que std430/std140 exigiriam, na ordem dos membros da struct."""
    offs = {}
    off = 0
    maxa = 1
    for idx, mem in enumerate(m.struct.get(sid, [])):
        ms, ma = size_align(m, mem, std140, depth=1)
        off = round_up(off, ma)
        offs[idx] = off
        off += ms
        maxa = max(maxa, ma)
    return offs, round_up(off, maxa)


def type_name(m, i, depth=0):
    """Nome legivel (estilo HLSL) do tipo, para o relatorio."""
    if depth > 8:
        return '?'
    sc = scalar_desc(m, i)
    if sc:
        return sc[2]
    if i in m.vec:
        e, n = m.vec[i]
        es, ea, nm = scalar_desc(m, e) or (4, 4, 'float32')
        return '%s%d' % (nm.replace('32', '').replace('64', '64'), n)
    if i in m.mat:
        c, ncol = m.mat[i]
        cn = type_name(m, c, depth + 1)
        return 'matrix %sx%d' % (cn, ncol)
    if i in m.arr:
        e, cnt = m.arr[i]
        n = m.const.get(cnt, 0)
        return '%s[%d]' % (type_name(m, e, depth + 1), n)
    if i in m.rarr:
        return '%s[]' % type_name(m, m.rarr[i], depth + 1)
    if i in m.struct:
        return m.name.get(i, 'struct')
    return '?'


# ----------------------------------------------------------------------------
# Analise
# ----------------------------------------------------------------------------
def unwrap_structs(m, i, acc, depth=0):
    """Coleta ids de structs alcancaveis a partir do tipo i."""
    if depth > 8:
        return
    if i in m.struct:
        if i in acc:
            return
        acc.add(i)
        for mem in m.struct[i]:
            unwrap_structs(m, mem, acc, depth + 1)
        return
    if i in m.arr:
        unwrap_structs(m, m.arr[i][0], acc, depth + 1)
        return
    if i in m.rarr:
        unwrap_structs(m, m.rarr[i], acc, depth + 1)
        return
    if i in m.mat:
        unwrap_structs(m, m.mat[i][0], acc, depth + 1)


def struct_label(m, sid):
    """Nome do struct, sintetizado a partir dos membros quando OpName falta."""
    nm = m.name.get(sid)
    if nm:
        return nm
    mems = m.struct.get(sid, [])
    parts = []
    for idx in range(len(mems)):
        mn = m.mname.get(sid, {}).get(idx)
        if mn:
            parts.append('%s:%s' % (mn, type_name(m, mems[idx])))
        if len(parts) >= 3:
            break
    return '{%s}' % ', '.join(parts) if parts else '<anon>'


def analyze(path):
    """Retorna (mod, [registros de blocos]) para um arquivo .spv."""
    m = parse_spv(path)
    if m is None:
        return None, []
    recs = []
    for sid, kind in sorted(m.block.items()):
        if sid not in m.struct:
            continue
        reach = set()                      # bloco + sub-structs alcancaveis
        unwrap_structs(m, sid, reach)
        for sub in sorted(reach):
            if sub not in m.offset or not m.struct.get(sub):
                continue
            act = m.offset[sub]
            o430, sz430 = gl_offsets(m, sub, std140=False)
            o140, sz140 = gl_offsets(m, sub, std140=True)
            bad430 = [i for i in sorted(act) if o430.get(i) != act[i]]
            bad140 = [i for i in sorted(act) if o140.get(i) != act[i]]
            recs.append({
                'file': os.path.basename(path),
                'kind': kind,
                'root': (sub == sid),
                'name': struct_label(m, sub),
                'nmemb': len(m.struct[sub]),
                'act': act, 'o430': o430, 'o140': o140,
                'sz430': sz430, 'sz140': sz140,
                'bad430': bad430, 'bad140': bad140,
                'stride': m.stride.get(sid) if sub == sid else None,
                'mname': m.mname.get(sub, {}),
            })
    return m, recs


# ----------------------------------------------------------------------------
# Layout DX (DXC -fvk-use-dx-layout)
# ----------------------------------------------------------------------------
# O RT64 compila com -fvk-use-dx-layout. O modelo abaixo reproduz esse layout e
# e calibrado (validado) contra os Offsets que o proprio DXC ja gravou nos blobs.
# Diferenca-chave vs std430/std140: vec3 alinha ao escalar (4 B), nao a 16 B.
def dx_align(m, i, depth=0):
    """Alinhamento do tipo i no layout DX."""
    if depth > 8:
        return 4
    sc = scalar_desc(m, i)
    if sc:
        return sc[1]
    if i in m.vec:
        e, n = m.vec[i]
        es = (scalar_desc(m, e) or (4, 4, ''))[0]
        if n == 3:
            return es
        return min(16, n * es)
    if i in m.mat:
        return dx_align(m, m.mat[i][0], depth + 1)
    if i in m.arr:
        return dx_align(m, m.arr[i][0], depth + 1)
    if i in m.rarr:
        return dx_align(m, m.rarr[i], depth + 1)
    if i in m.struct:
        a = 1
        for mem in m.struct[i]:
            a = max(a, dx_align(m, mem, depth + 1))
        return a
    return 4


def dx_size(m, i, depth=0):
    """Tamanho (com padding interno, sem padding final) do tipo i no layout DX."""
    if depth > 8:
        return 0
    sc = scalar_desc(m, i)
    if sc:
        return sc[0]
    if i in m.vec:
        e, n = m.vec[i]
        return n * ((scalar_desc(m, e) or (4, 4, ''))[0])
    if i in m.mat:
        c, ncol = m.mat[i]
        cs = dx_size(m, c, depth + 1)
        ca = max(1, dx_align(m, c, depth + 1))
        return ncol * round_up(cs, ca)
    if i in m.arr:
        e, cnt = m.arr[i]
        es = dx_size(m, e, depth + 1)
        ea = max(1, dx_align(m, e, depth + 1))
        return round_up(es, ea) * m.const.get(cnt, 0)
    if i in m.rarr:
        e = m.rarr[i]
        return round_up(dx_size(m, e, depth + 1), max(1, dx_align(m, e, depth + 1)))
    if i in m.struct:
        off = 0
        a = 1
        for mem in m.struct[i]:
            ma = max(1, dx_align(m, mem, depth + 1))
            off = round_up(off, ma) + dx_size(m, mem, depth + 1)
            a = max(a, ma)
        return round_up(off, a)
    return 0


def dx_offsets(m, sid):
    """Offsets que o layout DX exigiria, na ordem dos membros da struct."""
    offs = {}
    off = 0
    a = 1
    for idx, mem in enumerate(m.struct.get(sid, [])):
        ma = max(1, dx_align(m, mem))
        off = round_up(off, ma)
        offs[idx] = off
        off += dx_size(m, mem)
        a = max(a, ma)
    return offs, round_up(off, a)


# ----------------------------------------------------------------------------
# Planejador de padding (correcao nos headers dual HLSL/C++)
# ----------------------------------------------------------------------------
# Objetivo: tornar o layout DX (usado pelo DXC) identico ao std430, para que o
# SPIRV-Cross consiga emitir GLSL ES. A insercao e feita nos headers
# src/shared/*.h (que sao inclusos por HLSL E por C++), de modo que host e shader
# mudam juntos -- sem risco de descasamento.
#
# Estrategia deterministica:
#   1. Antes de cada membro i cujo offset DX < offset std430, inserir um vetor de
#      escalares (uint) preenchendo exatamente a diferenca (multiplo de 4).
#   2. Ao final, inserir padding de cauda para o tamanho total ser multiplo de 16
#      (16 >= qualquer alinhamento GLSL pratico), o que iguala tambem o
#      ArrayStride do bloco.
#   3. Recalcular e VERIFICAR o resultado; se algo nao convergir, marcar como
#      NAO-CONVERGENTE em vez de mentir sucesso.
GL_MAX_ALIGN = 16


def pad_plan(m, sid):
    """Plano de padding para tornar DX == std430 na struct sid.

    Retorna dict com offsets finais, membros de padding a inserir e verificacao.
    """
    mems = m.struct.get(sid, [])
    if not mems:
        return None
    dxo, dxsz = dx_offsets(m, sid)
    g430o, s430 = gl_offsets(m, sid, std140=False)
    bad = [i for i in sorted(dxo) if dxo.get(i) != g430o.get(i)]

    ins = []            # (antes_do_indice, bytes_de_padding)
    new_dx = {}         # offset final no layout DX (apos padding)
    new_gl = {}         # offset final no std430 (apos padding)
    cursor = 0          # posicao corrente, identica nos dois layouts
    ok = True

    for idx in range(len(mems)):
        want = g430o.get(idx, 0)
        if want < cursor:
            # std430 exige offset anterior ao que ja consumimos: nao ha padding
            # escalar capaz de corrigir (precisaria reordenar membros).
            ok = False
            new_dx[idx] = cursor
            new_gl[idx] = cursor
        elif want > cursor:
            gap = want - cursor
            if gap % 4 != 0:
                ok = False
            ins.append((idx, gap))
            cursor = want
            new_dx[idx] = cursor
            new_gl[idx] = cursor
        else:
            new_dx[idx] = cursor
            new_gl[idx] = cursor
        cursor += dx_size(m, mems[idx])

    # Cauda: tamanho total multiplo de 16 livra o ArrayStride/limite do bloco.
    tail = round_up(cursor, GL_MAX_ALIGN) - cursor
    tail_dx = round_up(cursor + tail, 4)
    tail_gl = round_up(cursor + tail, GL_MAX_ALIGN)
    if tail_dx != tail_gl:
        ok = False

    return {
        'bad': bad,
        'dx': dxo, 'gl430': g430o, 'gl140': gl_offsets(m, sid, std140=True)[0],
        'dx_size': dxsz, 'gl_size': s430,
        'ins': ins, 'tail': tail,
        'final_size': cursor + tail,
        'ok': ok and not bad,
    }


def hlsl_snippet(m, sid, plan):
    """Sugere o trecho HLSL/C++ (com padding) para o header dual."""
    mems = m.struct.get(sid, [])
    pad_ins = dict(plan['ins'])
    out = []
    for idx, mem in enumerate(mems):
        gap = pad_ins.get(idx)
        if gap:
            n = gap // 4
            if n == 1:
                out.append('    uint pad_%d;' % idx)
            else:
                out.append('    uint pad_%d[%d];' % (idx, n))
        nm = m.mname.get(sid, {}).get(idx, 'member%d' % idx)
        out.append('    %s %s;' % (type_name(m, mem), nm))
    if plan['tail']:
        out.append('    uint pad_tail[%d];' % (plan['tail'] // 4))
    return '\n'.join(out)
# ----------------------------------------------------------------------------
# Coleta e agregacao
# ----------------------------------------------------------------------------
def collect(paths):
    """Expande diretorios para a lista de arquivos .spv. Somente .spv."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, '*.spv'))))
        elif os.path.isfile(p) and p.endswith('.spv'):
            files.append(p)
        else:
            sys.stderr.write('AVISO: ignorado (nao e .spv/): %s\n' % p)
    return files


def sig_of(mod, sid, rec):
    """Assinatura estavel do bloco (para agregar o mesmo struct entre arquivos)."""
    mems = mod.struct.get(sid, [])
    return (rec['name'], rec['kind'], rec['root'],
            tuple(type_name(mod, x) for x in mems),
            tuple(mems), tuple(sorted(rec['act'].items())))


def gather(files):
    """Analisa os arquivos e devolve (per_file, unique, stats)."""
    per_file = []                     # (nome, n_blocos, n_ruins, ruins[])
    unique = collections.OrderedDict()  # sig -> {pavoneado}
    stats = {'files_ok': 0, 'files_err': 0, 'blocks': 0, 'bad': 0, 'bad_root': 0}
    for path in files:
        mod, recs = analyze(path)
        if mod is None:
            stats['files_err'] += 1
            per_file.append((os.path.basename(path), -1, -1, ['<falha ao desmontar>']))
            continue
        stats['files_ok'] += 1
        ruins = []
        for rec in recs:
            stats['blocks'] += 1
            if rec['bad430']:
                stats['bad'] += 1
                if rec['root']:
                    stats['bad_root'] += 1
                    ruins.append(rec)
        per_file.append((os.path.basename(path), len(recs), len(ruins), ruins))
        for rec in ruins:
            sid = None
            for cand, kind in sorted(mod.block.items()):
                if kind == rec['kind'] and struct_label(mod, cand) == rec['name']:
                    sid = cand
                    break
            if sid is None:
                continue
            s = sig_of(mod, sid, rec)
            if s not in unique:
                plan = pad_plan(mod, sid)
                unique[s] = {
                    'mod': mod, 'sid': sid, 'rec': rec, 'plan': plan,
                    'files': [], 'subs': 0,
                }
            unique[s]['files'].append(os.path.basename(path))
    return per_file, unique, stats


# ----------------------------------------------------------------------------
# Relatorio
# ----------------------------------------------------------------------------
def hr(title):
    return '\n' + '=' * 78 + '\n== %s\n' % title + '=' * 78


def rep_per_file(out, per_file):
    out.append(hr('1. POR ARQUIVO'))
    out.append('%-44s %8s %8s' % ('arquivo', 'blocos', 'ruins'))
    out.append('-' * 62)
    for name, nb, nr, ruins in per_file:
        if nb < 0:
            out.append('%-44s %8s %8s' % (name, 'ERRO', '-'))
            continue
        flag = ' <<<' if nr else ''
        out.append('%-44s %8d %8d%s' % (name, nb, nr, flag))
        for rec in ruins:
            out.append('      %-9s %-28s bad430=%s' % (
                rec['kind'], rec['name'], rec['bad430']))


def rep_unique(out, unique):
    out.append(hr('2. BLOCOS RAIZ DIVERGENTES (agregados)'))
    out.append('%-30s %-11s %-7s %-18s %s' % (
        'struct', 'kind', 'arquiv', 'bad430', 'plano'))
    out.append('-' * 78)
    for s, info in unique.items():
        rec = info['rec']
        plan = info['plan']
        if s[3] and len(s[3]) > 3:
            nm = '%s(%s)' % (rec['name'], ','.join(s[3])[:26])
        else:
            nm = rec['name']
        if plan is None:
            st = 'SEM-PLANO'
        elif plan['ok']:
            st = 'OK/%d ins' % len(plan['ins'])
        else:
            st = 'NAO-CONVERGE'
        out.append('%-30s %-11s %-7d %-18s %s' % (
            nm[:30], rec['kind'], len(info['files']), str(rec['bad430']), st))


# ----------------------------------------------------------------------------
# Verificacao do plano por simulacao
# ----------------------------------------------------------------------------
# Nao basta "inserir padding e esperar o melhor": construimos o struct COM o
# padding, no mesmo modelo de tipos, e recalculamos os DOIS layouts. Se os
# offsets coincidirem membro a membro e os tamanhos finais tambem, o plano
# converge. Se nao, dizemos exatamente por que -- e ha um caso que padding de
# membro NAO corrige: ArrayStride/alinhamento interno de array ou matriz
# (ex.: vec3[3] e 36 B no DX e 48 B no std430), que exigiria mudar o tipo.
_SYN = [0]


def _pad_member(m, nbytes):
    """Cria um membro de padding de nbytes (uint ou uint[N])."""
    m.int_w['@u32'] = 32
    if nbytes == 4:
        return '@u32'
    _SYN[0] += 1
    cid = '@c%d' % _SYN[0]
    aid = '@pa%d' % _SYN[0]
    m.arr[aid] = ('@u32', cid)
    m.const[cid] = nbytes // 4
    return aid


def sub_struct_of(m, i):
    """Struct diretamente alcancado por i (proprio, elemento de array etc.)."""
    for tab, pick in ((m.struct, lambda x: x),):
        if i in tab:
            return i
    if i in m.arr and m.arr[i][0] in m.struct:
        return m.arr[i][0]
    if i in m.mat and m.mat[i][0] in m.struct:
        return m.mat[i][0]
    if i in m.rarr and m.rarr[i] in m.struct:
        return m.rarr[i]
    return None


def _inner_stride(m, i):
    """(stride_dx, stride_gl) do elemento/coluna, ou None se nao for agregado."""
    if i in m.arr:
        e = m.arr[i][0]
    elif i in m.rarr:
        e = m.rarr[i]
    elif i in m.mat:
        e = m.mat[i][0]
    else:
        return None
    ds = round_up(dx_size(m, e), max(1, dx_align(m, e)))
    gs, ga = size_align(m, e)
    return (ds, round_up(gs, max(1, ga)))


def verify_block(m, sid):
    """Simula o padding no struct sid e verifica convergencia DX == std430.

    Retorna dict com: converged, reasons, membros (tabela) e tamanhos finais.
    Muta o modelo (cria ids sinteticos '@P'); chamar uma vez por modulo.
    """
    mems = m.struct.get(sid, [])
    g430o, sz430 = gl_offsets(m, sid, std140=False)
    reasons = []

    # 1) Bottom-up: substituir sub-structs pelas versoes ja "padronizadas".
    resolved = []
    for mem in mems:
        sub = sub_struct_of(m, mem)
        if sub is not None and sub != sid:
            nsub, extra = build_padded(m, sub)
            reasons.extend('sub#%s: %s' % (struct_label(m, sub), r) for r in extra)
            resolved.append(nsub)
        else:
            resolved.append(mem)

    # 2) Estrategia: avancar pelos tamanhos std430 e inserir padding escalar
    #    sempre que o cursor ficar atras do offset exigido pelo std430.
    _SYN[0] += 1
    newid = '@P%d' % _SYN[0]
    members = []
    track = []                    # (indice_original, indice_no_novo, pad_antes)
    cursor = 0
    for pos, mem in enumerate(resolved):
        gs, ga = size_align(m, mem)
        want = round_up(cursor, max(1, ga))
        pad = want - cursor
        if pad > 0:
            members.append(_pad_member(m, pad))
        track.append((pos, len(members), pad))
        members.append(mem)
        cursor = want + gs
    m.struct[newid] = members

    # 3) Verificacao real: recalcular os dois layouts no struct COM padding.
    ndx, _ = dx_offsets(m, newid)
    ngl, nsz = gl_offsets(m, newid, std140=False)
    for i in range(len(members)):
        if ndx.get(i) != ngl.get(i):
            reasons.append('offset@%d dx=%s gl=%s' % (i, ndx.get(i), ngl.get(i)))
    if len(ndx) != len(ngl):
        reasons.append('contagem de membros divergente')
    tail = nsz - cursor
    if nsz != cursor:
        tail = nsz - cursor

    # 4) Stride interno: padding de membro NAO corrige array/matriz.
    for pos, _ni, _pad in track:
        st = _inner_stride(m, resolved[pos])
        if st and st[0] != st[1]:
            reasons.append('%s: stride interno dx=%d gl=%d (nao corrigivel '
                           'por padding)' % (type_name(m, resolved[pos]),
                                             st[0], st[1]))

    return {
        'converged': not reasons,
        'reasons': reasons,
        'members': members,
        'track': track,
        'ndx': ndx, 'ngl': ngl,
        'final_size_gl': nsz,
        'newid': newid,
        'g430': g430o, 'sz430': sz430,
    }


def build_padded(m, sid, _depth=0):
    """Versao recursiva: retorna (novo_id, lista_de_motivos)."""
    if _depth > 6:
        return sid, ['recursao profunda demais']
    res = verify_block(m, sid)
    mems = m.struct.get(sid, [])
    # Reaplica sobre o novo id para manter o encadeamento de sub-structs.
    newid = res['newid']
    out = []
    if len(mems) != len(res['members']):
        pass
    for pos, mem in enumerate(mems):
        sub = sub_struct_of(m, mem)
        if sub is not None and sub != sid:
            nsub, extra = build_padded(m, sub, _depth + 1)
            out.extend(extra)
            res['members'][res['track'][pos][1]] = nsub
    m.struct[newid] = res['members']
    return newid, out + res['reasons']


# ----------------------------------------------------------------------------
# Relatorio: verificacao por simulacao + trechos HLSL/C++ propostos
# ----------------------------------------------------------------------------
def rep_verify(out, unique):
    """Simula o padding em cada struct divergente e reporta se converge."""
    out.append(hr('3. VERIFICACAO POR SIMULACAO (padding proposto)'))
    if not unique:
        out.append('Nenhum bloco raiz divergente: nada a corrigir.')
        return
    for s, info in unique.items():
        rec = info['rec']
        plan = info['plan']
        mod = info['mod']
        sid = info['sid']
        out.append('')
        out.append('--- %s  [%s]  %d arquivo(s) ---' % (
            rec['name'], rec['kind'], len(info['files'])))
        out.append('    membros    : %s' % ', '.join(
            '%d:%s' % (i, type_name(mod, x))
            for i, x in enumerate(mod.struct.get(sid, []))))
        out.append('    offsets DX : %s' % rec['act'])
        out.append('    offsets430 : %s' % rec['o430'])
        out.append('    bad430     : %s' % (rec['bad430'] or '-'))
        if plan:
            out.append('    dx_size=%d gl430_size=%d ins=%s tail=%d plano=%s' % (
                plan['dx_size'], plan['gl_size'], plan['ins'], plan['tail'],
                'OK' if plan['ok'] else 'NAO-CONVERGE'))
        else:
            out.append('    plano      : SEM-PLANO')
        res = verify_block(mod, sid)
        info['verify'] = res
        out.append('    simulacao  : %s' % (
            'CONVERGE' if res['converged'] else 'DIVERGE'))
        if res['converged']:
            out.append('      membros finais (%d): %s' % (
                len(res['members']),
                ', '.join(type_name(mod, x) for x in res['members'])))
            out.append('      tamanho final std430/GLSL = %d B' % res['final_size_gl'])
        else:
            for r in res['reasons']:
                out.append('      ! %s' % r)
# ----------------------------------------------------------------------------
# Relatorio: trechos HLSL/C++ propostos + resumo final
# ----------------------------------------------------------------------------
def rep_padding(out, unique):
    """Trecho de header dual (HLSL/C++) que tornaria DX == std430."""
    out.append(hr('4. PADDING PROPOSTO NOS HEADERS DUAL (src/shared/*.h)'))
    if not unique:
        out.append('Nada a propor.')
        return
    for s, info in unique.items():
        rec = info['rec']
        plan = info['plan']
        mod = info['mod']
        sid = info['sid']
        out.append('')
        out.append('--- %s  [%s]  %d arquivo(s) ---' % (
            rec['name'], rec['kind'], len(info['files'])))
        out.append('    arquivos : %s' % ', '.join(sorted(set(info['files']))))
        if plan is None:
            out.append('    SEM-PLANO (struct vazia ou irresolvivel)')
            continue
        out.append('    dx_size=%d  gl430_size=%d  final=%d  tail=%d' % (
            plan['dx_size'], plan['gl_size'], plan['final_size'], plan['tail']))
        out.append('')
        out.append(hlsl_snippet(mod, sid, plan))
    out.append('')
    out.append('NOTA: o padding muda apenas o layout INTERNO do bloco. Como os')
    out.append('      headers de src/shared/ sao inclusos por HLSL E por C++')
    out.append('      (guard HLSL_CPU), host e shader mudam juntos. Validar com')
    out.append('      static_assert(sizeof(...)) e recompilar os 58 blobs.')


def rep_summary(out, unique, stats):
    out.append(hr('5. RESUMO'))
    out.append('arquivos .spv lidos   : %d (erros: %d)' % (
        stats['files_ok'], stats['files_err']))
    out.append('blocos de interface   : %d' % stats['blocks'])
    out.append('blocos divergentes    : %d (raiz: %d)' % (
        stats['bad'], stats['bad_root']))
    out.append('structs raiz unicas   : %d' % len(unique))
    okc = sum(1 for i in unique.values()
              if i.get('verify') and i['verify']['converged'])
    out.append('convergem com padding : %d / %d' % (okc, len(unique)))
    nok = sorted({i['rec']['name'] for i in unique.values()
                  if not (i.get('verify') and i['verify']['converged'])})
    if nok:
        out.append('NAO convergem (padding nao basta): %s' % ', '.join(nok))
        out.append('  -> exigem mudanca de TIPO (stride de array/matriz), nao padding.')


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    files = collect(argv[1:])
    if not files:
        sys.stderr.write('Nenhum .spv encontrado.\n')
        return 1
    per_file, unique, stats = gather(files)
    out = ['spv_block_audit.py -- %d arquivo(s) .spv' % len(files)]
    rep_per_file(out, per_file)
    rep_unique(out, unique)
    rep_verify(out, unique)
    rep_padding(out, unique)
    rep_summary(out, unique, stats)
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))