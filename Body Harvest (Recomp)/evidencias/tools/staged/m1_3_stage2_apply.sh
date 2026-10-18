#!/bin/bash
# M1.3 estagio 2 -- PASSO 1: copia os fontes staged para a arvore e aplica o patch de runtime.
# Roda rapido (sem build). Saida: /root/bhrecomp/m1_3_gles/stage2/apply.log
set -uo pipefail

STAGED_SRC="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/staged"
STAGE="/root/bhrecomp/m1_3_gles/stage2"

mkdir -p "$STAGE/backup" "$STAGE/host" "$STAGE/out" "$STAGE/staged"
cp -f "$STAGED_SRC"/rt64_glsl_es.h \
      "$STAGED_SRC"/rt64_glsl_es.cpp \
      "$STAGED_SRC"/rt64_glsl_es_device.h \
      "$STAGED_SRC"/m1_3_stage2_apply.py \
      "$STAGED_SRC"/m1_3_stage2_host.cpp \
      "$STAGED_SRC"/CMakeLists.host.txt \
      "$STAGE/staged/"

echo "=== md5 ANTES (targets do port) ==="
md5sum /root/bhrecomp/lib/rt64/CMakeLists.txt \
       /root/bhrecomp/lib/rt64/src/render/rt64_shader_library.cpp \
       /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.cpp \
       /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.h \
       /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader_cache.cpp \
  | tee "$STAGE/md5_before.txt"

echo
echo "=== aplicando patch ==="
python3 "$STAGE/staged/m1_3_stage2_apply.py"
RC=$?
echo "patch rc=$RC"

if [ "$RC" -ne 0 ]; then
    echo "!!! PATCH FALHOU -- restaurando backup"
    cp -f "$STAGE/backup/CMakeLists.txt"          /root/bhrecomp/lib/rt64/CMakeLists.txt
    cp -f "$STAGE/backup/rt64_shader_library.cpp" /root/bhrecomp/lib/rt64/src/render/rt64_shader_library.cpp
    cp -f "$STAGE/backup/rt64_raster_shader.cpp"  /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.cpp
    cp -f "$STAGE/backup/rt64_raster_shader.h"    /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.h
    cp -f "$STAGE/backup/rt64_raster_shader_cache.cpp" /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader_cache.cpp
    rm -f /root/bhrecomp/lib/rt64/src/render/rt64_glsl_es.h \
          /root/bhrecomp/lib/rt64/src/render/rt64_glsl_es.cpp \
          /root/bhrecomp/lib/rt64/src/render/rt64_glsl_es_device.h
    echo "backup restaurado"
    exit 1
fi

echo
echo "=== md5 DEPOIS (arvore) ==="
md5sum /root/bhrecomp/lib/rt64/CMakeLists.txt \
       /root/bhrecomp/lib/rt64/src/render/rt64_shader_library.cpp \
       /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.cpp \
       /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.h \
       /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader_cache.cpp \
       /root/bhrecomp/lib/rt64/src/render/rt64_glsl_es.h \
       /root/bhrecomp/lib/rt64/src/render/rt64_glsl_es.cpp \
       /root/bhrecomp/lib/rt64/src/render/rt64_glsl_es_device.h \
  | tee "$STAGE/md5_after.txt"

echo
echo "=== conferencia de contagens ==="
echo -n "createShader(device,  em shader_library : "
grep -c 'createShader(device,' /root/bhrecomp/lib/rt64/src/render/rt64_shader_library.cpp
echo -n "createShader(device,  em raster_shader  : "
grep -c 'createShader(device,' /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.cpp
echo -n "device->createShader( residual          : "
grep -c 'device->createShader(' /root/bhrecomp/lib/rt64/src/render/rt64_shader_library.cpp /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.cpp
echo -n "case RenderShaderFormat::GLSL_ES        : "
grep -c 'RenderShaderFormat::GLSL_ES' /root/bhrecomp/lib/rt64/src/render/rt64_shader_library.cpp /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader.cpp /root/bhrecomp/lib/rt64/src/render/rt64_raster_shader_cache.cpp

echo
echo "PATCH OK"
exit 0