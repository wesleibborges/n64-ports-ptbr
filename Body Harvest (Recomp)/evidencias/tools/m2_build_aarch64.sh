#!/bin/bash
# M2-GLES -- rebuild aarch64 EM FATIAS.
#
# Motivo (mesmo do m1_build_aarch64.sh): o runner de comandos tem timeout de ~30s
# e processos em background morrem com a sessao. Invocando ninja sob `timeout` o
# progresso e' preservado (mtime dos objetos + .ninja_log) e cada invocacao
# continua de onde a anterior parou. Repita ate' o log dizer "no work to do".
#
# Uso: bash m2_build_aarch64.sh <on|off> [segundos=25]
#   on  -> build com o gate RT64_GLES_BACKEND (plume_gles dentro do binario)
#   off -> build sem o gate (mede a nao-regressao dos outros backends)
set -u
GATE=${1:-on}
DUR=${2:-25}
OUT=/root/bhrecomp/m2_gles_gate_20261018
LOG=$OUT/ninja_build_${GATE}.log
mkdir -p "$OUT"

timeout "$DUR" ninja -C /root/bhrecomp/build-aarch64 BodyHarvestRecompiled >> "$LOG" 2>&1
RC=$?

echo "gate=${GATE} ninja exit=${RC} (124 = fatia encerrada pelo timeout, esperado)"
echo "--- ultimas linhas do log ---"
tail -n 4 "$LOG"
echo "--- progresso ---"
echo "objetos plume_gles*: $(find /root/bhrecomp/build-aarch64 -name 'plume_gles*.o' 2>/dev/null | wc -l)"
echo "erros no log: $(grep -c 'FAILED\|error:' "$LOG" 2>/dev/null)"