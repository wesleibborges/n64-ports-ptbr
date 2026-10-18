#!/bin/bash
# M1 - Experimento do fix: recomputar o SPIR-V com -fvk-use-gl-layout e testar
# a conversao para GLSL ES 3.20 (SPIRV-Cross) + medir a mudanca de offsets.
set -u
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/x64
OUT=/root/bhrecomp/m1_fix
mkdir -p "$OUT"
cd /root/bhrecomp/build-aarch64 || exit 1

echo "===== A. COMANDOS DXC (ninja -t commands) ====="
echo "--- RasterPSDynamic ---"
ninja -t commands src/shaders/RasterPSDynamic.hlsl.spv 2>&1 | tail -1
echo "--- RSPProcessCS ---"
ninja -t commands src/shaders/RSPProcessCS.hlsl.spv 2>&1 | tail -1

echo
echo "===== B. EXPERIMENTO: -fvk-use-gl-layout ====="
for S in RasterPSDynamic RSPProcessCS; do
  echo "######## $S ########"
  cp -f "src/shaders/$S.hlsl.spv" "$OUT/$S.dx.spv" 2>/dev/null
  CMD=$(ninja -t commands "src/shaders/$S.hlsl.spv" 2>&1 | tail -1)
  CMDGL=$(echo "$CMD" | sed 's/-fvk-use-dx-layout/-fvk-use-gl-layout/')
  CMDGL=$(echo "$CMDGL" | sed -E "s|-Fo[ ]?[^ ]+\\.obj|-Fo $OUT/$S.gl.spv.obj|")
  echo "CMDGL: $CMDGL"
  eval "$CMDGL" >"$OUT/$S.dxc.log" 2>&1
  echo "RC_DXC=$?"
  tail -3 "$OUT/$S.dxc.log"
  ls -la "$OUT/$S.gl.spv.obj" 2>&1 | tail -1
  echo "--- XC ES 320 no blob GL-layout ---"
  spirv-cross "$OUT/$S.gl.spv.obj" --es --version 320 >"$OUT/$S.gl.frag" 2>"$OUT/$S.xc.log"
  echo "RC_XC=$?"
  head -3 "$OUT/$S.xc.log"
  echo "--- OFFSETS: DX (original) ---"
  spirv-cross "$OUT/$S.dx.spv" --reflect 2>&1 | grep -E '"name"|keyScale|keyCenter|convertK|textureDimensions|"offset"|array_stride|"size"' | head -24
  echo "--- OFFSETS: GL layout (novo) ---"
  spirv-cross "$OUT/$S.gl.spv.obj" --reflect 2>&1 | grep -E '"name"|keyScale|keyCenter|convertK|textureDimensions|"offset"|array_stride|"size"' | head -24
  echo
done