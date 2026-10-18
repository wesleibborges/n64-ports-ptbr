#!/bin/bash
# M1 - PoC v3 (receita final): padding explicito nos 6 headers duais => layout DX == std430
#
# Receita derivada empiricamente (evidencias/m1_layout_diff_dx_gl_20261018.md +
# mensagens do spirv-val):
#   (1) todo membro vec3 deve cair em offset multiplo de 16  -> inserir padding antes
#   (2) o TAMANHO da struct deve ser multiplo de 16 (stride de array em std430)
#       -> inserir padding no fim
#   (3) o PROPRIO padding deve ser ESCALAR: um uint3/float3 de padding tambem exige
#       alinhamento 16 em std430 (descoberto empiricamente no PoC v2)
#   (4) membros vec2 exigem alinhamento 8 em std430 (idem, pode exigir escalar extra)
#
# Se val=0 e xc=0 em layout DX, entao UM UNICO conjunto de blobs serve para
# Vulkan/D3D12/Metal E para GLES (sem duplicar blobs nem layouts no C++).
set -u
SRC=/root/bhrecomp/lib/rt64/src
NINJA=/root/bhrecomp/build-aarch64/build.ninja
OUT=/root/bhrecomp/m1_poc_padding3
BK="$OUT/headers_orig"; PAT="$OUT/headers_patched"
rm -rf "$OUT"; mkdir -p "$BK" "$PAT" "$OUT/spv"

HEADERS="rt64_rdp_params.h rt64_gpu_tile.h rt64_rsp_viewport.h rt64_rsp_light.h rt64_rsp_lookat.h rt64_raster_params.h"
for h in $HEADERS; do cp "$SRC/shared/$h" "$BK/$h"; done

# ---------------------------------------------------------------- aplica padding
python3 - <<'PY'
import os
base = '/root/bhrecomp/lib/rt64/src/shared/'

def patch(fname, subs):
    p = os.path.join(base, fname)
    s = open(p, encoding='utf-8').read()
    orig = s
    for old, new in subs:
        if old not in s:
            print('%s: ANCORA NAO ENCONTRADA: %r' % (fname, old[:60]))
            continue
        s = s.replace(old, new, 1)
    if s != orig:
        open(p, 'w', encoding='utf-8', newline='').write(s)
        print('%s: patch aplicado' % fname)
    else:
        print('%s: sem alteracao' % fname)

# RDPParams: +4 antes de keyScale; +12 no fim (stride 132 -> 144)
patch('rt64_rdp_params.h', [
    ('        float3 keyCenter;\n        float3 keyScale;\n        int convertK[6];\n',
     '        float3 keyCenter;\n'
     '        float padding; // M1-GLES: keyScale @16\n'
     '        float3 keyScale;\n'
     '        int convertK[6];\n'
     '        int padding2[3]; // M1-GLES: stride 144 (multiplo de 16)\n'),
])

# GPUTile: +12 antes de textureDimensions como ESCALARES (uint3 de padding exigiria
# alinhamento 16 em std430 e ficaria invalido em offset 36). Resulta em 64 (multiplo de 16).
patch('rt64_gpu_tile.h', [
    ('        uint textureIndex;\n        float3 textureDimensions;\n',
     '        uint textureIndex;\n'
     '        uint padding0; // M1-GLES: textureDimensions @16 (escalares!)\n'
     '        uint padding1;\n'
     '        uint padding2;\n'
     '        float3 textureDimensions;\n'),
])

# RSPViewport: +4 antes de translate; +4 no fim (28 -> 32)
patch('rt64_rsp_viewport.h', [
    ('        float3 scale;\n        float3 translate;\n',
     '        float3 scale;\n'
     '        float padding; // M1-GLES: translate @16\n'
     '        float3 translate;\n'
     '        float padding2; // M1-GLES: stride 32\n'),
])

# RSPLookAt: +4 antes de y; +4 no fim (28 -> 32)
patch('rt64_rsp_lookat.h', [
    ('        float3 x;\n        float3 y;\n',
     '        float3 x;\n'
     '        float padding; // M1-GLES: y @16\n'
     '        float3 y;\n'
     '        float padding2; // M1-GLES: stride 32\n'),
])

# RSPLight: +4 antes de col, +4 antes de colc, +8 no fim (56 -> 64)
patch('rt64_rsp_light.h', [
    ('        float3 posDir;\n        float3 col;\n        float3 colc;\n        uint kc;\n        uint kl;\n        uint kq;\n',
     '        float3 posDir;\n'
     '        float padding0; // M1-GLES\n'
     '        float3 col;\n'
     '        float padding1; // M1-GLES\n'
     '        float3 colc;\n'
     '        uint kc;\n        uint kl;\n        uint kq;\n'
     '        uint padding2; // M1-GLES: stride 64\n'
     '        uint padding3;\n'),
])

# RasterParams: +12 depois de renderIndex (uint3 padding vai de @4 para @16) e
# +4 depois de uint3 padding para screenScale (vec2) cair em 32 (exige alinhamento 8).
patch('rt64_raster_params.h', [
    ('        uint renderIndex;\n        uint3 padding;\n',
     '        uint renderIndex;\n'
     '        uint padding0; // M1-GLES: padding (uint3) @16\n'
     '        uint padding1;\n'
     '        uint padding2;\n'
     '        uint3 padding;\n'
     '        uint padding3; // M1-GLES: screenScale (vec2) @32\n'),
])
PY
for h in $HEADERS; do cp "$SRC/shared/$h" "$PAT/$h"; done

# ---------------------------------------------------------------- compila com LAYOUT DX
SHADERS="RasterPSDynamic RasterPSDynamicMS RasterPSSpecConstant RasterPSSpecConstantMS RasterPSSpecConstantFlat RasterPSSpecConstantFlatMS RasterVSDynamic RasterVSSpecConstant RasterVSSpecConstantFlat RSPProcessCS ComposePS TextureCopyPS"
printf 'shader\tstage\tdxc\tval\txc\tglslang\n' > "$OUT/poc.tsv"
for NAME in $SHADERS; do
  CMD=$(grep -m1 "/Fo .*/${NAME}\.hlsl\.spv$" "$NINJA" | sed 's/^ *COMMAND = //' | sed 's/\\//g')
  if [ -z "$CMD" ]; then echo "$NAME: comando ausente" >&2; continue; fi
  C=$(printf '%s' "$CMD" | sed "s#/Fo [^ ]*#/Fo $OUT/spv/$NAME.hlsl.spv#")
  rm -f "$OUT/spv/$NAME.hlsl.spv"
  eval "$C" > "$OUT/$NAME.dxc.log" 2>&1; RCD=$?
  spv="$OUT/spv/$NAME.hlsl.spv"
  if [ ! -s "$spv" ]; then printf '%s\t-\t%s\t-\t-\t-\n' "$NAME" "$RCD" >> "$OUT/poc.tsv"; continue; fi
  case "$NAME" in *CS*) EXT=comp ;; *VS*) EXT=vert ;; *) EXT=frag ;; esac
  spirv-val --target-env vulkan1.0 "$spv" > "$OUT/$NAME.val.log" 2>&1; RCV=$?
  spirv-cross --es --version 320 "$spv" --output "$OUT/$NAME.$EXT" > "$OUT/$NAME.xc.log" 2>&1; RCX=$?
  RCG=99
  if [ "$RCX" = 0 ] && [ -s "$OUT/$NAME.$EXT" ]; then
    glslangValidator -S "$EXT" "$OUT/$NAME.$EXT" > "$OUT/$NAME.glslang.log" 2>&1; RCG=$?
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$NAME" "$EXT" "$RCD" "$RCV" "$RCX" "$RCG" >> "$OUT/poc.tsv"
done

echo '=== RESULTADO: layout DX + padding explicito ==='
cat "$OUT/poc.tsv"
echo
echo '=== offsets verificados (DX+padding devem IGUALAR o GL) ==='
for s in RDPParams GPUTile RSPViewport RSPLight RSPLookAt; do
  echo "--- $s (RSPProcessCS/RasterVSDynamic) ---"
  python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/spv_layout_dump.py" "$OUT/spv/RSPProcessCS.hlsl.spv" "$s" 2>/dev/null | grep -E 'struct |off='
  python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/spv_layout_dump.py" "$OUT/spv/RasterVSDynamic.hlsl.spv" "$s" 2>/dev/null | grep -E 'struct |off='
done
echo '--- RasterParams (push constant, via RasterPSDynamic) ---'
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/spv_layout_dump.py" "$OUT/spv/RasterPSDynamic.hlsl.spv" RasterParams | grep -E 'struct |off='
echo
echo '=== erros remanescentes de spirv-val (deve estar vazio) ==='
grep -h 'error' "$OUT"/*.val.log 2>/dev/null | head -6
echo '=== erros remanescentes de spirv-cross (deve estar vazio) ==='
grep -h 'exception' "$OUT"/*.xc.log 2>/dev/null | head -4
echo '=== erros remanescentes de glslang ==='
grep -h 'ERROR' "$OUT"/*.glslang.log 2>/dev/null | sort -u | head -6

for h in $HEADERS; do cp "$BK/$h" "$SRC/shared/$h"; done
echo
echo "headers originais restaurados (patch em $PAT)"
echo "resultados: $OUT/poc.tsv"