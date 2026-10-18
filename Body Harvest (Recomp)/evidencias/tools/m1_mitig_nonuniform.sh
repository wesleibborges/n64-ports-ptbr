#!/bin/bash
# M1 - Teste de mitigacao da extensao espuria GL_NV_gpu_shader5
#
# Causa (fonte: contrib/spirv-cross/spirv_glsl.cpp:571):
#   case CapabilityShaderNonUniformEXT:
#       if (!options.vulkan_semantics) require_extension_internal("GL_NV_gpu_shader5");
#       else require_extension_internal("GL_EXT_nonuniform_qualifier");
#
# O SPIR-V do RasterPS* traz CapabilityShaderNonUniformEXT (DXC marca indexacao nao-uniforme
# de arrays de descriptor). Em GLSL nao-Vulkan o spirv-cross exige GL_NV_gpu_shader5.
# Porem NAO ha uso real de `nonuniformEXT` no codigo emitido (grep = 0), pois bindless nao
# sera usado no backend GLES. Mitigacao: remover a linha de #extension.
set -u
B=/root/bhrecomp/m1_layout_matrix2
OUT=/root/bhrecomp/m1_mitig
rm -rf "$OUT"; mkdir -p "$OUT"
: > "$OUT/mitig.tsv"

for f in "$B"/RasterPS*.hlsl.spv.gl.frag; do
  [ -e "$f" ] || continue
  n=$(basename "$f")
  sed '/#extension GL_NV_gpu_shader5 : require/d' "$f" > "$OUT/$n"
  a=99
  if glslangValidator -S frag "$f" > "$OUT/$n.antes.log" 2>&1; then a=0; else a=2; fi
  b=99
  if glslangValidator -S frag "$OUT/$n" > "$OUT/$n.depois.log" 2>&1; then b=0; else b=2; fi
  printf '%s\tantes=%s\tdepois=%s\n' "$n" "$a" "$b" >> "$OUT/mitig.tsv"
done

echo '=== RESULTADO MITIGACAO (RasterPS*) ==='
cat "$OUT/mitig.tsv"
echo '--- erros restantes apos mitigacao (se houver) ---'
grep -h 'ERROR' "$OUT"/*.depois.log 2>/dev/null | head -6
echo '--- prova: linhas 1-3 antes vs depois (RasterPSDynamic) ---'
head -3 "$B/RasterPSDynamic.hlsl.spv.gl.frag"
echo '...'
head -3 "$OUT/RasterPSDynamic.hlsl.spv.gl.frag"