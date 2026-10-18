#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 (docs/PLANO_BACKEND_GLES_R36S.md) - Auditor de layout GLSL ES via `spirv-cross --reflect`.

OBJETIVO
    Provar, sem simulacao propria de SPIR-V, QUAIS structs dos 56 blobs do RT64
    divergem entre o layout que o DXC emite (`-fvk-use-dx-layout`, usado pelo RT64)
    e o layout std430 que o SPIRV-Cross precisa para emitir GLSL ES.

    Erro observado nos 10 shaders que falham (Raster* + RSPProcessCS):
        "Buffer block cannot be expressed as any of std430, std140, scalar,
         even with enhanced layouts. You can try flattening this block..."

FONTE DE DADOS (autoritativa)
    spirv-cross <blob.spv> --reflect   -> JSON {entryPoints, types{id:{name,members[]}}}
    Funciona ATE nos blobs que falham na conversao (o erro e na emissao, nao na leitura).

SAIDA
    Relatorio texto/markdown em stdout:
      1. structs DIVERGENTES (offsets DX reais vs offsets std430 recalculados + padding proposto)
      2. structs CONFORMES
      3. resumo por arquivo (quais blocos cada shader usa)

USO
    python3 spv_reflect_audit.py <dir-com-spv> [<dir2> ...]
"""
import json
import os
import subprocess
import sys

SPIRV_CROSS = "spirv-cross"

# ---------------------------------------------------------------- tabelas de tipo
SCALAR = {
    "float": (4, 4), "uint": (4, 4), "int": (4, 4), "bool": (4, 4),
    "double": (8, 8), "int8_t": (1, 1), "uint8_t": (1, 1),
    "int16_t": (2, 2), "uint16_t": (2, 2), "int64_t": (8, 8), "uint64_t": (8, 8),
}
VEC = {
    "vec2": (8, 8), "vec3": (12, 16), "vec4": (16, 16),
    "uvec2": (8, 8), "uvec3": (12, 16), "uvec4": (16, 16),
    "ivec2": (8, 8), "ivec3": (12, 16), "ivec4": (16, 16),
    "bvec2": (8, 8), "bvec3": (12, 16), "bvec4": (16, 16),
    "dvec2": (16, 16), "dvec3": (24, 32), "dvec4": (32, 32),
}


def align_up(v, a):
    return ((v + a - 1) // a) * a


def vec_align(rows):
    """Alinhamento (std430) do vetor de N componentes."""
    if rows >= 3:
        return 16
    if rows == 2:
        return 8
    return 4


def base_size_align(tname):
    """(size, align) para tipos base; None se nao for base."""
    if tname in SCALAR:
        return SCALAR[tname]
    if tname in VEC:
        return VEC[tname]
    if tname.startswith("mat") or tname.startswith("dmat"):
        d = "d" if tname.startswith("dmat") else ""
        body = tname[len(d) + 3:]
        if not body:
            rows = cols = int(d and 4 or 4) if d else (int(d) if d else 4)
            rows = cols = 4
        elif "x" in body:
            c, r = body.split("x")
            cols, rows = int(c), int(r)
        else:
            cols = rows = int(body)
        if d:
            # dmat: coluna e um dvec de 'rows' componentes (align 32 p/ rows>=3)
            va = 32 if rows >= 3 else (16 if rows == 2 else 8)
            colstride = align_up(rows * 8, va)
        else:
            va = vec_align(rows)
            colstride = align_up(rows * 4, va)
        return (cols * colstride, va)
    return None


def struct_layout(tid, types, depth=0):
    """Recalcula o layout std430 de uma struct. -> (dict|None)

    dict = {name, size, align, members:[{name,type,offset,align,size,calc_offset}], ok}
    """
    if depth > 12:
        return None
    t = types.get(tid)
    if not t or "members" not in t:
        return None
    calc = 0
    maxalign = 1
    members = []
    ok = True
    for m in t["members"]:
        mt = m.get("type")
        sub = None
        if mt in types:
            sub = struct_layout(mt, types, depth + 1)
            if sub is None:
                continue
            size, al = sub["size"], sub["align"]
            tname = "%s{%s}" % (types[mt].get("name", mt), mt)
        else:
            ba = base_size_align(mt)
            if ba is None:
                # tipo desconhecido (textura/sampler/imagem) -> ignora, marca incompleto
                members.append({"name": m.get("name"), "type": mt,
                                "offset": m.get("offset"), "align": 0, "size": 0,
                                "calc_offset": None, "unknown": True})
                ok = False
                continue
            size, al = ba
            tname = mt
        arr = m.get("array")
        if arr is not None and len(arr) >= 1:
            stride = m.get("array_stride") or size
            # std430: stride deve ser o stride natural do elemento
            nat = align_up(size, al)
            if stride != nat:
                ok = False
            need = align_up(size, al)
            al = max(al, min(al, al))  # alinhamento do elemento
            size = stride * arr[0]
            tname = "%s[%d]" % (tname, arr[0])
            arrinfo = {"stride": stride, "nat_stride": nat}
        else:
            arrinfo = None
        calc = align_up(calc, al)
        members.append({"name": m.get("name"), "type": tname,
                        "offset": m.get("offset"), "align": al, "size": size,
                        "calc_offset": calc, "arr": arrinfo})
        calc += size
        maxalign = max(maxalign, al)
    total = align_up(calc, maxalign)
    return {"name": t.get("name", tid), "id": tid, "size": total, "align": maxalign,
            "members": members, "ok": ok}


def divergent(info):
    """True se algum membro tem offset real != offset std430 (ou stride divergente)."""
    if not info.get("ok"):
        return True
    for m in info["members"]:
        if m.get("unknown"):
            continue
        if m["offset"] != m["calc_offset"]:
            return True
        if m.get("arr") and m["arr"]["stride"] != m["arr"]["nat_stride"]:
            return True
    return False