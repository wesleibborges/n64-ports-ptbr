#!/bin/bash
# M1 - PoC DECISIVO: padding explicito nos headers duais torna o layout DX == std430
#
# Hipotese (opcao b, a recomendada):
#   Inserindo padding explicito nos headers HLSL/C++ duais (src/shared/*.h), o layout
#   gerado por `-fvk-use-dx-layout` passa a coincidir com o layout std430 (o que o
#   SPIRV-Cross exige para GLSL ES). Assim UM UNICO conjunto de blobs serve para
#   Vulkan/D3D12/Metal E para GLES, sem duplicar blobs nem duplicar layouts no C++.
#
# Medicao previa (evidencias/m1_layout_diff_dx_gl_20261018.md):
#   RDPParams : keyScale  92 (DX) vs 96 (GL)  -> inserir 4 bytes antes
#   GPUTile   : textureDimensions 36 (DX) vs 48 (GL) -> inserir 12 bytes antes
#
# Nao altera o CMake nem os blobs reais: compila para $OUT e restaura os headers no fim.
set -u
SRC=/root/bhrecomp/lib/rt64/src
BUILDNINJA=/root/bhrecomp/build-aarch64/build.ninja
OUT=/root/bhrecomp/m1_poc_padding
BK="$OUT/headers_orig"
PAT="$OUT/headers_patched"
rm -rf "$OUT"; mkdir -p "$BK" "$PAT" "$OUT/spv"
DXC=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/arm64/dxc-linux
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/arm64

cp "$SRC/shared/rt64_rdp_params.h" "$BK/"
cp "$SRC/shared/rt64_gpu_tile.h" "$BK/"

# ---------------------------------------------------------------- aplica padding
python3 - <<'PY'
rdp = '/root/bhrecomp/lib/rt64/src/shared/rt64_rdp_params.h'
s = open(rdp, encoding='utf-8').read()
if 'float padding;' not in s:
    s = s.replace('        float3 keyCenter;\n        float3 keyScale;',
                  '        float3 keyCenter;\n'
                  '        float padding; // M1-GLES: alinha keyScale a 16 (DX == std430)\n'
                  '        float3 keyScale;')
    open(rdp, 'w', encoding='utf-8', newline='').write(s)
    print('RDPParams: padding aplicado')
else:
    print('RDPParams: padding ja presente')

tile = '/root/bhrecomp/lib/rt64/src/shared/rt64_gpu_tile.h'
t = open(tile, encoding='utf-8').read()
if 'uint3 padding;' not in t:
    t = t.replace('        uint textureIndex;\n        float3 textureDimensions;',
                  '        uint textureIndex;\n'
                  '        uint3 padding; // M1-GLES: alinha textureDimensions a 16\n'
                  '        float3 textureDimensions;')
    open(tile, 'w', encoding='utf-8', newline='').write(t)
    print('GPUTile: padding aplicado')
else:
    print('GPUTile: padding ja presente')
PY
cp "$SRC/shared/rt64_rdp_params.h" "$PAT/"
cp "$SRC/shared/rt64_gpu_tile.h" "$PAT/"

# ---------------------------------------------------------------- compila com LAYOUT DX
echo '=== compilando com LAYOUT DX (comando identico ao do ninja) ==='
printf 'shader\tdxc\tval\txc\tglslang\n' > "$OUT/poc.tsv"
for NAME in RasterPSDynamic RasterPSDynamicMS RasterPSSpecConstant RasterVSDynamic RasterVSSpecConstant RSPProcessCS; do
  CMD=$(grep -m1 "/Fo .*/${NAME}\.hlsl\.spv$" "$BUILDNINJA" | sed 's/^ *COMMAND = //' | sed 's/\\//g')
  if [ -z "$CMD" ]; then echo "$NAME: comando nao encontrado" >&2; continue; fi
  C=$(printf '%s' "$CMD" | sed "s#/Fo [^ ]*#/Fo $OUT/spv/$NAME.hlsl.spv#")
  rm -f "$OUT/spv/$NAME.hlsl.spv"
  eval "$C" > "$OUT/$NAME.dxc.log" 2>&1
  RCD=$?
  spv="$OUT/spv/$NAME.hlsl.spv"
  if [ ! -s "$spv" ]; then printf '%s\t%s\t-\t-\t-\n' "$NAME" "$RCD" >> "$OUT/poc.tsv"; continue; fi

  case "$NAME" in *CS*) EXT=comp ;; *VS*) EXT=vert ;; *) EXT=frag ;; esac
  spirv-val --target-env vulkan1.0 "$spv" > "$OUT/$NAME.val.log" 2>&1; RCV=$?
  spirv-cross --es --version 320 "$spv" --output "$OUT/$NAME.$EXT" > "$OUT/$NAME.xc.log" 2>&1; RCX=$?
  RCG=99
  if [ "$RCX" = 0 ] && [ -s "$OUT/$NAME.$EXT" ]; then
    glslangValidator -S "$EXT" "$OUT/$NAME.$EXT" > "$OUT/$NAME.glslang.log" 2>&1; RCG=$?
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$NAME" "$RCD" "$RCV" "$RCX" "$RCG" >> "$OUT/poc.tsv"
done

echo '=== RESULTADO (layout DX + padding) ==='
cat "$OUT/poc.tsv"
echo
echo '=== offsets apos padding (devem ser keyScale@96 e textureDimensions@48) ==='
for NAME in RasterPSDynamic RasterVSDynamic; do
  [ -s "$OUT/spv/$NAME.hlsl.spv" ] || continue
  python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/spv_layout_dump.py" \
      "$OUT/spv/$NAME.hlsl.spv" RDPParams | grep -E 'struct |keyScale|convertK|ArrayStride'
  python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/spv_layout_dump.py" \
      "$OUT/spv/$NAME.hlsl.spv" GPUTile | grep -E 'struct |textureIndex|textureDimensions|flags'
done
echo
echo '=== log de conversao (xc) - deve estar VAZIO para RasterPS* se o padding resolveu ==='
head -4 "$OUT/RasterPSDynamic.xc.log" 2>/dev/null
echo
echo '=== erro restante de glslang (se houver) ==='
grep -h 'ERROR' "$OUT"/*.glslang.log 2>/dev/null | head -4

# ---------------------------------------------------------------- restaura headers
cp "$BK/rt64_rdp_params.h" "$SRC/shared/"
cp "$BK/rt64_gpu_tile.h" "$SRC/shared/"
echo
echo "headers originais restaurados (patch preservado em $PAT)"
echo "resultados: $OUT/poc.tsv"