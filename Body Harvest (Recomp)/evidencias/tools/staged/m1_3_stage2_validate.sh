#!/bin/bash
# M1.3 estagio 2 -- passos 4 e 5: executar o aceite host-side e validar o ESSL 3.20.
#
# (roda em foreground; deve terminar em poucos segundos apos o binario existir)
set -u

STAGE=/root/bhrecomp/m1_3_gles/stage2
OUT=$STAGE/out
BIN=$STAGE/host/build/m1_3_stage2_host

mkdir -p "$OUT"
rm -f "$OUT"/*.essl "$OUT"/*.glslang.log

echo "=== aceite host-side (codigo de producao: respv::Optimizer + RT64::convertSPIRVToGLSLES) ==="
"$BIN" "$OUT"
echo "host_test rc=$?"
echo

echo "=== validacao ESSL 3.20 (glslangValidator) ==="
shopt -s nullglob
pass=0
fail=0
for f in "$OUT"/*.essl; do
    name=$(basename "$f" .essl)
    case "$name" in
        *VS*|FullScreenVS*) stage=vert ;;
        *) stage=frag ;;
    esac
    size=$(stat -c%s "$f")
    if glslangValidator -S "$stage" "$f" > "$OUT/$name.glslang.log" 2>&1; then
        printf '  OK    %-28s %-4s %8s B\n' "$name" "$stage" "$size"
        pass=$((pass + 1))
    else
        printf '  FAIL  %-28s %-4s %8s B\n' "$name" "$stage" "$size"
        tail -n 5 "$OUT/$name.glslang.log"
        fail=$((fail + 1))
    fi
done
echo "glslangValidator: pass=$pass fail=$fail"
echo

echo "=== invariantes textuais do sanitizador (por shader) ==="
for f in "$OUT"/*.essl; do
    name=$(basename "$f" .essl)
    version=$(head -n 1 "$f")
    highp=$(grep -c 'precision highp float;' "$f")
    nopersp=$(grep -c 'noperspective' "$f")
    mediump=$(grep -c 'precision mediump float;' "$f")
    nvgpu=$(grep -c 'GL_NV_gpu_shader5' "$f")
    printf '  %-28s ver=%-16s highp=%s nopersp=%s mediump=%s nvgpu=%s\n' \
        "$name" "$version" "$highp" "$nopersp" "$mediump" "$nvgpu"
done
echo

exit $((fail > 0))