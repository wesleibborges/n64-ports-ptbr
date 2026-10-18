#!/bin/bash
# M1 - APLICACAO REAL do padding de layout nos 6 headers duais do RT64.
#
# Contexto: o PoC v3 (evidencias/tools/m1_poc_padding2.sh) provou que inserir padding
# explicito nos 6 headers duais faz `-fvk-use-dx-layout` produzir offsets IDENTICOS ao
# std430 => UM unico conjunto de blobs serve Vulkan/D3D12/Metal E GLES/GLSL-ES.
# Este script aplica essa correcao na arvore REAL (lib/rt64/src/shared/).
#
# Etapas:
#   0) backup dos 6 headers originais + md5
#   1) snapshot md5 dos 58 blobs SPIR-V ANTES
#   2) copia os headers corrigidos (validados no PoC) e verifica md5 pos-aplicacao
#   3) prova que cada header real == artefato validado (diff -q)
#   4) INVALIDA os artefatos gerados pelo DXC.
#      NECESSARIO: no lib/rt64/CMakeLists.txt os add_custom_command do DXC declaram
#      apenas `DEPENDS ${FILENAME}` (.hlsl). Os headers inclusos via -I NAO entram nas
#      dependencias do ninja, portanto uma mudanca de header NAO dispara o DXC.
#      (bug latente upstream -> documentado em evidence_m1_padding_applied_20261018.md)
#
# Uso: bash m1_apply_padding.sh
set -u

SRC=/root/bhrecomp/lib/rt64/src
OUT=/root/bhrecomp/m1_apply_20261018
PAT=/root/bhrecomp/m1_poc_padding3/headers_patched
B=/root/bhrecomp/build-aarch64
HEADERS="rt64_gpu_tile.h rt64_raster_params.h rt64_rdp_params.h rt64_rsp_light.h rt64_rsp_lookat.h rt64_rsp_viewport.h"

rm -rf "$OUT"
mkdir -p "$OUT/backup_headers"

echo "=== ETAPA 0: backup dos headers originais ==="
for h in $HEADERS; do cp -p "$SRC/shared/$h" "$OUT/backup_headers/$h"; done
md5sum "$OUT/backup_headers"/*.h | tee "$OUT/md5_headers_backup.txt"

echo
echo "=== ETAPA 1: snapshot md5 dos blobs ANTES ==="
find "$B" -name '*.hlsl.spv' -print0 | sort -z | xargs -0 md5sum > "$OUT/md5_blobs_before.txt"
echo "blobs no snapshot: $(wc -l < "$OUT/md5_blobs_before.txt")"

echo
echo "=== ETAPA 2: aplicando padding na arvore real ==="
FAIL=0
: > "$OUT/md5_headers_applied.txt"
for h in $HEADERS; do
    cp "$PAT/$h" "$SRC/shared/$h"
    A=$(md5sum "$PAT/$h" | cut -d' ' -f1)
    Bx=$(md5sum "$SRC/shared/$h" | cut -d' ' -f1)
    if [ "$A" = "$Bx" ]; then ST=OK; else ST="FAIL"; FAIL=1; fi
    printf '%-24s validado=%s aplicado=%s  %s\n' "$h" "$A" "$Bx" "$ST" \
        | tee -a "$OUT/md5_headers_applied.txt"
done

echo
echo "=== ETAPA 3: prova de identidade real == artefato validado (diff -q) ==="
DIFFFAIL=0
for h in $HEADERS; do
    if diff -q "$PAT/$h" "$SRC/shared/$h" > /dev/null; then
        echo "identico: $h"
    else
        echo "DIVERGENTE: $h"
        DIFFFAIL=1
    fi
done
echo
echo "=== marcadores M1-GLES presentes nos headers reais ==="
grep -c 'M1-GLES' "$SRC/shared/rt64_gpu_tile.h" "$SRC/shared/rt64_raster_params.h" \
    "$SRC/shared/rt64_rdp_params.h" "$SRC/shared/rt64_rsp_light.h" \
    "$SRC/shared/rt64_rsp_lookat.h" "$SRC/shared/rt64_rsp_viewport.h"

echo
echo "=== ETAPA 4: invalidando artefatos gerados pelo DXC ==="
NSPV=$(find "$B" -name '*.hlsl.spv' | wc -l)
find "$B" -name '*.hlsl.spv' -delete
find "$B" -name '*.hlsl.spirv.c' -delete
find "$B" -name '*.hlsl.spirv.h' -delete
find "$B" -name '*.hlsli.rw' -delete
find "$B" -name '*.hlsli.rw.c' -delete
find "$B" -name '*.hlsli.rw.h' -delete
echo "artefatos .hlsl.spv removidos: $NSPV"
echo "artefatos .spirv.c/.spirv.h/.hlsli.rw* removidos"
echo "restantes .spv: $(find "$B" -name '*.spv' | wc -l)"

echo
if [ "$FAIL" = 0 ] && [ "$DIFFFAIL" = 0 ] && [ "$NSPV" = 58 ]; then
    echo "APLICACAO OK (6 headers, 58 blobs invalidados)"
else
    echo "APLICACAO COM PROBLEMA: FAIL=$FAIL DIFFFAIL=$DIFFFAIL NSPV=$NSPV"
fi