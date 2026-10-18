#!/bin/bash
# M1 probe9 - causa raiz das 10 falhas do SPIRV-Cross (SSBO / buffer block)
# Roda: cd /root/bhrecomp && bash '<este script>'
set -u
SPV=/root/bhrecomp/build-aarch64/src/shaders
GL=/root/bhrecomp/m1_glsles

echo "############################################################"
echo "# 1. LOGS DE FALHA (SPIRV-Cross) - texto completo"
echo "############################################################"
echo "--- fail_xc.txt ---"
cat "$GL/fail_xc.txt" 2>/dev/null
echo
echo "--- fail_glsl.txt ---"
cat "$GL/fail_glsl.txt" 2>/dev/null
echo
echo "--- conteudo de cada .xc.log (falhas) ---"
for f in "$GL"/*.xc.log; do
  [ -e "$f" ] || continue
  if grep -qi 'error\|fail\|Exception\|unsupported' "$f" 2>/dev/null; then
    echo "=== $(basename "$f") ==="
    cat "$f"
    echo
  fi
done

echo "############################################################"
echo "# 2. SSBO (buffer blocks) nos shaders que falham"
echo "############################################################"
for s in RasterPSDynamic RasterPSDynamicSpecConstant RasterVSSpecConstant RSPProcessCS; do
  echo "=================== $s ==================="
  if [ -f "$SPV/$s.hlsl.spv" ]; then
    echo "--- tipos struct / ArrayStride ---"
    spirv-dis "$SPV/$s.hlsl.spv" 2>/dev/null | grep -n -E 'OpTypeStruct|ArrayStride|OpTypeRuntimeArray' | head -30
    echo "--- decoracoes Offset / ArrayStride ---"
    spirv-dis "$SPV/$s.hlsl.spv" 2>/dev/null | grep -n -E 'ArrayStride|OpMemberDecorate %[^ ]+ [0-9]+ Offset' | head -40
    echo "--- variaveis de storage buffer ---"
    spirv-dis "$SPV/$s.hlsl.spv" 2>/dev/null | grep -n -E 'OpVariable %[^ ]+ (StorageBuffer|Uniform)' | head -20
  else
    echo "(sem .spv)"
  fi
  echo
done

echo "############################################################"
echo "# 3. includes / buffers nos HLSL fonte"
echo "############################################################"
echo "--- RasterPS.hlsl ---"
cat /root/bhrecomp/lib/rt64/src/shaders/RasterPS.hlsl 2>/dev/null | head -60
echo
echo "--- RSPProcessCS.hlsl ---"
cat /root/bhrecomp/lib/rt64/src/shaders/RSPProcessCS.hlsl 2>/dev/null | head -60
echo
echo "--- grep StructuredBuffer/RWStructuredBuffer nos shaders que falham ---"
grep -rn -E 'StructuredBuffer|RWStructuredBuffer|ByteAddressBuffer|ConstantBuffer|push_constant' \
  /root/bhrecomp/lib/rt64/src/shaders/RasterPS.hlsl \
  /root/bhrecomp/lib/rt64/src/shaders/RasterVS.hlsl \
  /root/bhrecomp/lib/rt64/src/shaders/RSPProcessCS.hlsl 2>/dev/null

echo "############################################################"
echo "# 4. RasterPS.hlsl: todas as declaracoes de recurso (sem comentario)"
echo "############################################################"
grep -rn -E '^[^/]*\b(Buffer|Texture|Sampler|cbuffer|struct)\b' /root/bhrecomp/lib/rt64/src/shaders/RasterPS.hlsl 2>/dev/null | head -40

echo "FIM_PROBE9"