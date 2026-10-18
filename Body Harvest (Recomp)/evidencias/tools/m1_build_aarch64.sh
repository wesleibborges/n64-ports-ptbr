#!/bin/bash
# M1 - rebuild aarch64 EM FATIAS.
#
# Motivo: o runner de comandos tem timeout de ~30s e processos em background sao
# encerrados junto com a sessao. Invocando ninja sob `timeout`, o progresso e
# preservado (mtime dos objetos + .ninja_log) e cada invocacao continua de onde a
# anterior parou. Repita ate o log mostrar a conclusao ("no work to do") ou o
# binario ser religado.
#
# Uso: bash m1_build_aarch64.sh [segundos=25]
set -u
DUR=${1:-25}
OUT=/root/bhrecomp/m1_apply_20261018
LOG=$OUT/ninja_build.log
mkdir -p "$OUT"

timeout "$DUR" ninja -C /root/bhrecomp/build-aarch64 BodyHarvestRecompiled >> "$LOG" 2>&1
RC=$?

echo "ninja exit=$RC (124 = fatia encerrada pelo timeout, esperado)"
echo "--- ultimas linhas do log ---"
tail -n 5 "$LOG"
echo "--- progresso ---"
echo "blobs .hlsl.spv regenerados: $(find /root/bhrecomp/build-aarch64 -name '*.hlsl.spv' | wc -l)/58"
echo "linhas de erro no log: $(grep -c 'FAILED\|error:' "$LOG")"