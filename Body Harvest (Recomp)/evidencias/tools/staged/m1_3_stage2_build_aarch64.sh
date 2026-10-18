#!/bin/bash
# M1.3 estagio 2 -- PASSO 2: reconfigura e builda o alvo aarch64 (desacoplado da sessao).
#
# Prova (a) do plano: `spirv-cross-c` linkado no binario aarch64.
#   - reconfigura (novo add_subdirectory): log limpo em reconfigure.log
#   - builda: log em aarch64_build.log
# Acompanhar: tail -f /root/bhrecomp/m1_3_gles/stage2/aarch64_build.log
set -u

SRC=/root/bhrecomp
BUILD=/root/bhrecomp/build-aarch64
STAGE=/root/bhrecomp/m1_3_gles/stage2
mkdir -p "$STAGE"

cd "$SRC"
setsid nohup bash -c '
set -uo pipefail
STAGE=/root/bhrecomp/m1_3_gles/stage2
BUILD=/root/bhrecomp/build-aarch64

echo "=== reconfigure $(date -Is) ==="
cmake -S /root/bhrecomp -B "$BUILD" -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE=/root/bhrecomp/Toolchain-aarch64.cmake \
      -DCMAKE_BUILD_TYPE=Release \
      -DNFD_PORTAL=OFF \
      -DRT64_GLSL_ES_SHADERS=ON \
      > "$STAGE/reconfigure.log" 2>&1
echo "reconfigure rc=$?"

echo "=== build $(date -Is) ==="
ninja -C "$BUILD" BodyHarvestRecompiled > "$STAGE/aarch64_build.log" 2>&1
echo "ninja rc=$?"

echo "=== link final ==="
ls -l "$BUILD/BodyHarvestRecompiled" 2>/dev/null
echo "=== simbolos GLSLES ==="
/usr/bin/aarch64-linux-gnu-nm --defined-only "$BUILD/BodyHarvestRecompiled" 2>/dev/null | grep -c "BlobGLSLES"
echo "=== simbolos spirv-cross no binario ==="
/usr/bin/aarch64-linux-gnu-nm --defined-only "$BUILD/BodyHarvestRecompiled" 2>/dev/null | grep -c "spvc_"
echo "=== fim $(date -Is) ==="
' > "$STAGE/aarch64_driver.log" 2>&1 < /dev/null &

echo "lancado (setsid) — PID=$!"
echo "logs: $STAGE/reconfigure.log, $STAGE/aarch64_build.log, $STAGE/aarch64_driver.log"