#!/bin/bash
# M1.3 estagio 2 -- PASSO 3: build + execucao do aceite host-side (x86_64).
#
# Prova (c) do plano: blob GLES -> respv::Optimizer::run -> spirv-cross -> ESSL 3.20,
# usando o CODIGO DE PRODUCAO (lib/rt64/src/render/rt64_glsl_es.cpp) sobre os blobs REAIS.
# Log: /root/bhrecomp/m1_3_gles/stage2/host_run.log
set -u

STAGE=/root/bhrecomp/m1_3_gles/stage2
HOST=$STAGE/host
mkdir -p "$HOST" "$STAGE/out"
cp -f "$STAGE/staged/CMakeLists.host.txt" "$HOST/CMakeLists.txt"
cp -f "$STAGE/staged/m1_3_stage2_host.cpp" "$HOST/m1_3_stage2_host.cpp"

setsid nohup bash -c '
set -uo pipefail
STAGE=/root/bhrecomp/m1_3_gles/stage2
HOST=$STAGE/host

echo "=== cmake configure $(date -Is) ==="
cmake -S "$HOST" -B "$HOST/build" -G Ninja -DCMAKE_BUILD_TYPE=Release
echo "configure rc=$?"

echo "=== cmake build $(date -Is) ==="
cmake --build "$HOST/build" --target m1_3_stage2_host
echo "build rc=$?"

echo
echo "=== execucao do aceite host-side $(date -Is) ==="
"$HOST/build/m1_3_stage2_host" "$STAGE/out"
echo "host_test rc=$?"

echo
echo "=== validacao ESSL 3.20 (glslangValidator) ==="
shopt -s nullglob
pass=0
fail=0
for f in "$STAGE"/out/*.essl; do
    name=$(basename "$f" .essl)
    case "$name" in
        *VS*|FullScreenVS) stage=vert ;;
        *) stage=frag ;;
    esac
    if glslangValidator -S "$stage" "$f" > "$STAGE/out/$name.glslang.log" 2>&1; then
        echo "  $name ($stage) : OK"
        pass=$((pass + 1))
    else
        echo "  $name ($stage) : FAIL"
        tail -n 3 "$STAGE/out/$name.glslang.log"
        fail=$((fail + 1))
    fi
done
echo "glslangValidator: pass=$pass fail=$fail"

echo
echo "=== tamanhos ==="
for f in "$STAGE"/out/*.essl; do
    printf "  %-40s %8s B\\n" "$(basename "$f")" "$(stat -c%s "$f")"
done
echo "=== fim $(date -Is) ==="
' > "$STAGE/host_run.log" 2>&1 < /dev/null &

echo "lancado (setsid) — PID=$!"
echo "log: $STAGE/host_run.log"