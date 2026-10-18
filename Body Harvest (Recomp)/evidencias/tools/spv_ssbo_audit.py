#!/usr/bin/env python3
"""spv_ssbo_audit.py -- auditor de layout de blocos SSBO (BufferBlock) em SPIR-V.

Contexto (M1 do PLANO_BACKEND_GLES_R36S):
  O RT64 compila HLSL->SPIR-V com DXC usando `-fvk-use-dx-layout` (ver
  CMakeLists.txt, variavel DXC_SPV_OPTS). Esse layout (DX) permite `float3`
  desalinhado a 16 (ex.: keyScale@92, ArrayStride 128). O SPIRV-Cross recusa
  esses blocos ao emitir GLSL ES:

    "Buffer block cannot be expressed as any of std430, std140, scalar,
     even with enhanced layouts. You can try flattening this block..."

  A auditoria anterior (spv_block_audit.py) olhava apenas o struct RAIZ do
  bloco. Para um SSBO de `StructuredBuffer<T>` o struct raiz e
  `%type_StructuredBuffer_T = OpTypeStruct %_runtimearr_T` (1 membro @0),
  que trivialmente "bate" com std430 -> falso negativo. A divergencia real
  esta no struct de ELEMENTO (T) do runtime array.

Este script:
  1) Le os offsets REAIS do SPIR-V (layout DX, decorados pelo DXC).
  2) Simula o layout std430 (GLSL ES 3.20).
  3) Compara membro a membro + stride + tamanho, para cada struct de elemento
     alcancavel a partir de um bloco (Block / BufferBlock).
  4) Agrega por struct e mostra quais arquivos .spv sao afetados.

Uso:  python3 spv_ssbo_audit.py <dir1> [dir2 ...]
"""
import glob
import os
import re
import sys
from collections import OrderedDict, defaultdict

# ---------------------------------------------------------------- regexes SPIR-V
RE_STRUCT = re.compile(r'^%(\S+) = OpTypeStruct (.*)$')
RE_VEC = re.compile(r'^%(\S+) = OpTypeVector %(\S+) (\d+)$')
RE_MAT = re.compile(r'^%(\S+) = OpTypeMatrix %(\S+) (\d+)$')
RE_ARR = re.compile(r'^%(\S+) = OpTypeArray %(\S+) %(\S+)$')
RE_RARR = re.compile(r'^%(\S+) = OpTypeRuntimeArray %(\S+)$')
RE_INT = re.compile(r'^%(\S+) = OpTypeInt (\d+) (\d+)$')
RE_FLT = re.compile(r'^%(\S+) = OpTypeFloat (\d+)$')
RE_PTR = re.compile(r'^%(\S+) = OpTypePointer \S+ %(\S+)$')
RE_CONST = re.compile(r'^%(\S+) = OpConstant %(\S+) (\d+)$')
RE_STRIDE = re.compile(r'^OpDecorate %(\S+) ArrayStride (\d+)$')
RE_BLOCK = re.compile(r'^OpDecorate %(\S+) (BufferBlock|Block)$')
RE_MOFF = re.compile(r'^OpMemberDecorate %(\S+) (\d+) Offset (\d+)$')
RE_NAME = re.compile(r'^OpName %(\S+) "(.*)"$')
RE_MNAME = re.compile(r'^OpMemberName %(\S+) (\d+) "(.*)"$')
RE_MSTRIDE = re.compile(r'^OpMemberDecorate %(\S+) (\d+) MatrixStride (\d+)$')
RE_ROWMAJOR = re.compile(r'^OpMemberDecorate %(\S+) (\d+) RowMajor$')


def rid(tok):
    """Remove o '%' de um token de id."""
    return tok[1:] if tok.startswith('%') else tok


class Model(object):
    """Modelo minimo de um modulo SPIR-V (formato de assembly do spirv-dis)."""

    def __init__(self):
        self.structs = {}       # id -> [ids dos membros]
        self.vec = {}           # id -> (id do componente, n)
        self.mat = {}           # id -> (id do vetor coluna, n de colunas)
        self.array = {}         # id -> (id do elemento, id da constante de tamanho)
        self.rarr = {}          # id -> id do elemento
        self.scalar = {}        # id -> (bits, signed) / ou ('float', bits)
        self.ptr = {}           # id -> id do tipo apontado
        self.const = {}         # id -> valor inteiro
        self.names = {}         # id -> nome
        self.stride = {}        # id -> ArrayStride
        self.blocks = OrderedDict()   # id -> 'Block' | 'BufferBlock'
        self.moff = {}          # id -> {indice: offset}

    # -- leitura ------------------------------------------------------------
    def parse(self, path):
        with open(path, 'r', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                m = RE_STRUCT.match(line)
                if m:
                    self.structs[m.group(1)] = [rid(t) for t in m.group(2).split()]
                    continue
                m = RE_VEC.match(line)
                if m:
                    self.vec[m.group(1)] = (m.group(2), int(m.group(3)))
                    continue
                m = RE_MAT.match(line)
                if m:
                    self.mat[m.group(1)] = (m.group(2), int(m.group(3)))
                    continue
                m = RE_ARR.match(line)
                if m:
                    self.array[m.group(1)] = (m.group(2), rid(m.group(3)))
                    continue
                m = RE_RARR.match(line)
                if m:
                    self.rarr[m.group(1)] = m.group(2)
                    continue
                m = RE_INT.match(line)
                if m:
                    self.scalar[m.group(1)] = ('int', int(m.group(2)), m.group(3) == '1')
                    continue
                m = RE_FLT.match(line)
                if m:
                    self.scalar[m.group(1)] = ('float', int(m.group(2)), False)
                    continue
                m = RE_PTR.match(line)
                if m:
                    self.ptr[m.group(1)] = m.group(2)
                    continue
                m = RE_CONST.match(line)
                if m:
                    self.const[m.group(1)] = int(m.group(3))
                    continue
                m = RE_STRIDE.match(line)
                if m:
                    self.stride[m.group(1)] = int(m.group(2))
                    continue
                m = RE_BLOCK.match(line)
                if m:
                    self.blocks[m.group(1)] = m.group(2)
                    continue
                m = RE_MOFF.match(line)
                if m:
                    self.moff.setdefault(m.group(1), {})[int(m.group(2))] = int(m.group(3))
                    continue
                m = RE_NAME.match(line)
                if m:
                    self.names[m.group(1)] = m.group(2)
        return self