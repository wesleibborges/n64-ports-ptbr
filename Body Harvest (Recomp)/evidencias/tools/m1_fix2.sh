#!/bin/bash
# M1 - Experimento do fix (v2): restaura o blob sobrescrito, testa -fvk-use-gl-layout
# com o DXC ARM64 correto, compara offsets (DX vs GL) e valida GLSL ES 3.20 no glslang.
set -u
DXC=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/arm64/dxc-linux
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/arm64
SRC=/root/bhrecomp/lib/rt64/src/shaders
BLD=/root/bhrecomp/build-aarch64/src/shaders
OUT=/root/bhrecomp/m1_fix
mkdir -p "$OUT"

echo "===== 0. DXC ARM64: suporta -fvk-use-gl-layout? ====="
"$DXC" -help 2>&1 | grep -i -E 'fvk-use-.*layout|use-gl-layout|use-dx-layout' | head -10
echo "DXC_VERSION:"; "$DXC" --version 2>&1 | head -3

echo
echo "===== 1. RESTAURAR RasterPSDynamic.hlsl.spv via NINJA (regeneracao autoritativa) ====="
rm -f "$BLD/RasterPSDynamic.hlsl.spv"
(cd /root/bhrecomp/build-aarch64 && ninja src/shaders/RasterPSDynamic.hlsl.spv 2>&1 | tail -5)
echo "RC_RESTORE=$?"
echo "--- md5 (restaurado vs copia pre-experimento) ---"
md5sum "$BLD/RasterPSDynamic.hlsl.spv" "$OUT/RasterPSDynamic.dx.spv" 2>&1
echo "--- xc no blob restaurado (deve VOLTAR a falhar = DX layout) ---"
spirv-cross "$BLD/RasterPSDynamic.hlsl.spv" --es --version 320 >/dev/null 2>&1
echo "RC_XC_DX=$?"

echo
echo "===== 2. EXPERIMENTO: -fvk-use-gl-layout -> m1_fix/<S>.gl.spv ====="
for S in RasterPSDynamic RSPProcessCS; do
  echo "######## $S ########"
  CMD=$(cd /root/bhrecomp/build-aarch64 && ninja -t commands "src/shaders/$S.hlsl.spv" 2>&1 | tail -1)
  echo "CMD_ORIG: $CMD"
  CMDGL=$(echo "$CMD" | sed 's/-fvk-use-dx-layout/-fvk-use-gl-layout/')
  CMDGL=$(echo "$CMDGL" | sed "s|/Fo [^ ]*|/Fo $OUT/$S.gl.spv|")
  echo "CMDGL: $CMDGL"
  eval "$CMDGL" >"$OUT/$S.dxc2.log" 2>&1
  echo "RC_DXC=$?"
  tail -4 "$OUT/$S.dxc2.log"
  ls -la "$OUT/$S.gl.spv" 2>&1 | tail -1
  echo "--- XC ES 320 (GL layout) ---"
  spirv-cross "$OUT/$S.gl.spv" --es --version 320 >"$OUT/$S.gl2.frag" 2>"$OUT/$S.xc2.log"
  echo "RC_XC=$?"
  head -3 "$OUT/$S.xc2.log"
  echo "--- GLSLANG validate (GL layout) ---"
  glslangValidator -S frag "$OUT/$S.gl2.frag" 2>&1 | tail -6
  echo
done

echo
echo "===== 3. OFFSETS DX vs GL (RDPParams / GPUTile) ====="
for R in RasterPSDynamic RSPProcessCS; do
  echo "######## $R ########"
  echo "--- DX (original) ---"
  spirv-cross "$OUT/$R.dx.spv" --reflect 2>&1 | grep -E 'keyScale|keyCenter|convertK|textureDimensions|array_stride|"offset"|"size"' | head -30
  echo "--- GL (novo) ---"
  spirv-cross "$OUT/$R.gl.spv" --reflect 2>&1 | grep -E 'keyScale|keyCenter|convertK|textureDimensions|array_stride|"offset"|"size"' | head -30
  echo "--- XC ES 320 no DX (deve falhar) ---"
  spirv-cross "$OUT/$R.dx.spv" --es --version 320 >/dev/null 2>"$OUT/$R.xc_dx.log"; echo "RC=$?"; head -2 "$OUT/$R.xc_dx.log"
  echo
done
echo "===== FIM ====="