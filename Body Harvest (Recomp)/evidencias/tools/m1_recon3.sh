#!/bin/bash
# M1 recon v3 - consolidated state dump (Body Harvest Recomp / R36S GLES backend)
# Date: 2026-10-17  |  Author: weslei.brasil@e-core.com
set -u
OUT=/root/bhrecomp/m1_recon3.txt
: > "$OUT"
exec >> "$OUT" 2>&1

echo "### DATE: $(date -Is)"
echo
echo "### ENV"
mountpoint /opt/r36s/rootfs || true
losetup -a 2>/dev/null | head -3
echo "spv build-aarch64/src/shaders: $(ls /root/bhrecomp/build-aarch64/src/shaders/*.spv 2>/dev/null | wc -l)"
echo "spv build-aarch64/shaders:    $(ls /root/bhrecomp/build-aarch64/shaders/*.spv 2>/dev/null | wc -l)"
echo "files m1_glsles:              $(ls /root/bhrecomp/m1_glsles 2>/dev/null | wc -l)"
echo
echo "### BLOB INTEGRITY (RasterPSDynamic, sobrescrito e restaurado)"
ls -la --time-style=+%Y-%m-%d_%H:%M:%S /root/bhrecomp/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv 2>&1
md5sum /root/bhrecomp/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv 2>&1
md5sum /root/bhrecomp/m1_fix/RasterPSDynamic.dx.spv 2>&1
echo
echo "### FAIL LISTS"
echo "--- fail_xc.txt ---"
cat /root/bhrecomp/m1_glsles/fail_xc.txt 2>&1
echo "--- fail_glsl.txt ---"
cat /root/bhrecomp/m1_glsles/fail_glsl.txt 2>&1
echo
echo "### DXC RULE (build.ninja)"
grep -n -A22 '^rule .*dxc' /root/bhrecomp/build-aarch64/build.ninja 2>&1 | head -46
echo
echo "### FAILING SHADER BUILD STATEMENTS"
while read -r n; do
  [ -z "$n" ] && continue
  echo "--- $n ---"
  grep -n -A9 "build src/shaders/$n.hlsl.spv" /root/bhrecomp/build-aarch64/build.ninja 2>&1 | head -16
done < /root/bhrecomp/m1_glsles/fail_xc.txt
echo
echo "### SHARED HEADERS (dual HLSL/C++): membros vector"
grep -rn 'float3\|uint3\|int3\|float2\|uint2\|int2' /root/bhrecomp/lib/rt64/src/shared/*.h 2>&1
echo
echo "### SHARED HEADERS (list)"
ls -la /root/bhrecomp/lib/rt64/src/shared/ 2>&1
echo
echo "### STRUCT LOCATIONS"
grep -rn 'GPUTile\|RSPViewport\|RSPLight\|RDPParams' /root/bhrecomp/lib/rt64/src --include='*.h' 2>&1 | head -50
echo
echo "### HLSL SOURCES USING THEM"
grep -rln 'RDPParams\|GPUTile\|RSPViewport\|RSPLight' /root/bhrecomp/lib/rt64/src/shaders/ 2>&1
echo "### DONE"