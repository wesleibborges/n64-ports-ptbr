#!/bin/bash
# M1 recon4: fatos para o experimento do fix de padding (headers dual HLSL/C++)
set -u
B=/root/bhrecomp
SPV=$B/build-aarch64/src/shaders
OUT=$B/m1_recon4
mkdir -p $OUT
LOG=$OUT/report.txt
: > $LOG

echo "=== 1. INTEGRIDADE / AMBIENTE ===" | tee -a $LOG
date -u +%Y-%m-%dT%H:%M:%SZ | tee -a $LOG
mountpoint /opt/r36s/rootfs 2>&1 | tee -a $LOG
echo "spv total: $(ls $SPV/*.spv 2>/dev/null | wc -l)" | tee -a $LOG
md5sum $SPV/RasterPSDynamic.hlsl.spv 2>&1 | tee -a $LOG
md5sum $B/m1_fix/RasterPSDynamic.dx.spv 2>&1 | tee -a $LOG

echo | tee -a $LOG
echo "=== 2. COMANDO DXC COMPLETO (RasterPSDynamic) ===" | tee -a $LOG
cd $B/build-aarch64
ninja -t commands src/shaders/RasterPSDynamic.hlsl.spv 2>/dev/null | tail -1 >> $LOG 2>&1

echo | tee -a $LOG
echo "=== 3. RULE DXC (build.ninja) ===" | tee -a $LOG
grep -A20 'rule .*dxc' $B/build-aarch64/build.ninja 2>/dev/null | head -50 | tee -a $LOG

echo | tee -a $LOG
echo "=== 4. INCLUDES dos shaders que falham ===" | tee -a $LOG
for f in RasterPSDynamic RasterPS RasterVS RSPProcessCS; do
  if [ -f "$B/lib/rt64/src/shaders/$f.hlsl" ]; then
    echo "--- $f.hlsl ---" | tee -a $LOG
    grep -n '#include' "$B/lib/rt64/src/shaders/$f.hlsl" | tee -a $LOG
  else
    echo "--- $f.hlsl AUSENTE (sera variante gerada) ---" | tee -a $LOG
  fi
done

echo | tee -a $LOG
echo "=== 5. INCLUDES em TODOS os shaders *.hlsl (paths unicos) ===" | tee -a $LOG
grep -rh '#include' $B/lib/rt64/src/shaders/*.hlsl 2>/dev/null | sort -u | tee -a $LOG

echo | tee -a $LOG
echo "=== 6. HLSL FONTE: RasterPS/RasterVS/RSPProcess */ ===" | tee -a $LOG
ls -la $B/lib/rt64/src/shaders/ 2>&1 | head -60 | tee -a $LOG

echo | tee -a $LOG
echo "=== 7. HEADERS shared (dual HLSL/C++) ===" | tee -a $LOG
ls -la $B/lib/rt64/src/shared/ 2>&1 | tee -a $LOG

echo | tee -a $LOG
echo "=== 8. rt64_rdp_params.h (completo) ===" | tee -a $LOG
cat $B/lib/rt64/src/shared/rt64_rdp_params.h 2>&1 | tee -a $LOG

echo | tee -a $LOG
echo "=== 9. rt64_hlsl.h (wrappers interop) ===" | tee -a $LOG
cat $B/lib/rt64/src/shared/rt64_hlsl.h 2>&1 | tee -a $LOG

echo | tee -a $LOG
echo "=== 10. REFLECT: SSBO types (RasterPSDynamic) ===" | tee -a $LOG
spirv-cross $SPV/RasterPSDynamic.hlsl.spv --reflect 2>&1 | tee -a $LOG

echo "RC=0" | tee -a $LOG