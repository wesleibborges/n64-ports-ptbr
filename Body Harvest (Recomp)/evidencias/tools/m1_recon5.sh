#!/bin/bash
# M1 recon 5 - fatos exatos para o experimento do fix de padding (layout DX == std430)
# Coleta: ambiente, integridade dos blobs, comando DXC real, headers dual HLSL/C++ a patchear,
# includes dos shaders que falham e o SCHEMA do spirv-cross --reflect (fonte autoritativa).
set -u
D=/root/bhrecomp
OUT=$D/m1_recon5.txt
{
echo "=== DATE: $(date -Is) ==="
echo "=== MOUNT ==="
mountpoint /opt/r36s/rootfs || true
echo "=== BLOBS: $(ls $D/build-aarch64/src/shaders/*.spv 2>/dev/null | wc -l) ==="
echo "=== INTEGRIDADE ==="
md5sum $D/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv
md5sum $D/m1_fix/RasterPSDynamic.dx.spv 2>/dev/null || true
echo "=== TOOLS ==="
for t in spirv-dis spirv-cross glslangValidator python3 ninja; do printf '%-18s -> ' $t; command -v $t || echo MISSING; done
echo "=== DXC BIN ==="
ls -la $D/lib/rt64/src/contrib/dxc/bin/ 2>/dev/null
echo "=== DXC CMD: RasterPSDynamic ==="
cd $D/build-aarch64 && ninja -t commands src/shaders/RasterPSDynamic.hlsl.spv 2>/dev/null | grep -i 'dxc' | tail -1
echo "=== DXC CMD: RSPProcessCS ==="
cd $D/build-aarch64 && ninja -t commands src/shaders/RSPProcessCS.hlsl.spv 2>/dev/null | grep -i 'dxc' | tail -1
echo "=== SHARED HEADERS (dual HLSL/C++) ==="
ls -la $D/lib/rt64/src/shared/
echo "=== RDPParams (completo) ==="
cat $D/lib/rt64/src/shared/rt64_rdp_params.h
echo "=== DEFS: GPUTile / RSPViewport / RSPLight / RSP* ==="
grep -rn 'struct GPUTile\|struct RSPViewport\|struct RSPLight\|struct RSPRay\|struct RSPTexCoord\|struct RDPSmoke' $D/lib/rt64/src/ 2>/dev/null | head -30
echo "=== HLSL RasterPSDynamic (1-30) ==="
sed -n '1,30p' $D/lib/rt64/src/shaders/RasterPSDynamic.hlsl
echo "=== HLSL RSPProcessCS (1-30) ==="
sed -n '1,30p' $D/lib/rt64/src/shaders/RSPProcessCS.hlsl
echo "=== REFLECT RAW: RasterPSDynamic ==="
spirv-cross $D/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv --reflect > $D/m1_reflect_rp.json 2>$D/m1_reflect_rp.err
echo "rc=$? bytes=$(stat -c %s $D/m1_reflect_rp.json 2>/dev/null)"
head -60 $D/m1_reflect_rp.json
echo "=== REFLECT RAW: RSPProcessCS ==="
spirv-cross $D/build-aarch64/src/shaders/RSPProcessCS.hlsl.spv --reflect > $D/m1_reflect_rsp.json 2>$D/m1_reflect_rsp.err
echo "rc=$? bytes=$(stat -c %s $D/m1_reflect_rsp.json 2>/dev/null)"
head -60 $D/m1_reflect_rsp.json
echo "=== FIM ==="
} > $OUT 2>&1
cat $OUT