#!/bin/bash
# M1 probe8 - Analisador de layout de blocos SPIR-V (layout DX real vs std430/std140).
# Objetivo: identificar EXATAMENTE quais structs (SSBO/UBO) nao sao expressaveis em std430,
# comparando offsets decorados no SPIR-V (layout DX do DXC) com as regras GLSL.
# Somente leitura: nao altera a arvore do RT64.
set -u
REP=/root/bhrecomp/m1_probe8.txt
exec > "$REP" 2>&1

echo "=== ferramentas ==="
command -v spirv-dis && spirv-dis --version
echo
echo "=== blobs SPIR-V do build aarch64 ==="
find /root/bhrecomp/build-aarch64 -name '*.spv' | sort > /root/bhrecomp/m1_probe8_files.txt
wc -l < /root/bhrecomp/m1_probe8_files.txt
echo

python3 - <<'PYEOF'
import subprocess, re, collections, os

files = [l for l in open('/root/bhrecomp/m1_probe8_files.txt').read().split() if l]

re_ty_int   = re.compile(r'^\s*%(\S+) = OpTypeInt (\d+) (\d+)')
re_ty_float = re.compile(r'^\s*%(\S+) = OpTypeFloat (\d+)')
re_ty_vec   = re.compile(r'^\s*%(\S+) = OpTypeVector %(\S+) (\d+)')
re_ty_mat   = re.compile(r'^\s*%(\S+) = OpTypeMatrix %(\S+) (\d+)')
re_ty_arr   = re.compile(r'^\s*%(\S+) = OpTypeArray %(\S+) %(\S+)')
re_ty_rarr  = re.compile(r'^\s*%(\S+) = OpTypeRuntimeArray %(\S+)')
re_ty_str   = re.compile(r'^\s*%(\S+) = OpTypeStruct (.*)$')
re_const    = re.compile(r'^\s*%(\S+) = OpConstant %\S+ (\d+)')
re_dblk     = re.compile(r'^\s*OpDecorate %(\S+) (Block|BufferBlock)\s*$')
re_moff     = re.compile(r'^\s*OpMemberDecorate %(\S+) (\d+) Offset (\d+)')
re_astr     = re.compile(r'^\s*OpDecorate %(\S+) ArrayStride (\d+)')
re_ptr      = re.compile(r'^\s*%(\S+) = OpTypePointer (\w+) %(\S+)')
re_name     = re.compile(r'^\s*OpName %(\S+) "(.*)"')
re_mname    = re.compile(r'^\s*OpMemberName %(\S+) (\d+) "(.*)"')

def ru(x, a):
    if a <= 0: a = 1
    return ((x + a - 1) // a) * a

# Agregado por NOME do struct (ids sao por-arquivo) e modo (std430/std140)
CALC  = collections.defaultdict(lambda: collections.defaultdict(dict))   # nome -> modo -> {idx: offset glsl}
CALCSIZE = collections.defaultdict(dict)                                  # (nome,modo) -> (size, align)
ACT   = collections.defaultdict(lambda: collections.defaultdict(dict))   # nome -> modo -> {idx: offset DX real}
FILES = collections.defaultdict(set)                                      # (nome,modo) -> {arquivos}
MNAME = collections.defaultdict(dict)                                     # nome -> {idx: nome}
REALSTRIDE = collections.defaultdict(set)                                 # nome struct -> strides reais (runtime array)
CALCSTRIDE = collections.defaultdict(dict)                                # (nome,modo) -> stride calc
ALLAY = {}                                                                # nome -> nome completo (type.StructuredBuffer.X)