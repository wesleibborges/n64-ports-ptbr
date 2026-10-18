#!/bin/bash
# M1 - rebuild aarch64 DESACOPLADO da sessao (setsid + nohup + stdin de /dev/null).
#
# Se o runner encerrar a sessao, o processo sobrevive (nova sessao via setsid),
# permitindo que o build corra entre chamadas. Verifique com:
#   ps aux | grep '[n]inja'
# e acompanhe com: tail -f /root/bhrecomp/m1_apply_20261018/ninja_build.log
set -u
OUT=/root/bhrecomp/m1_apply_20261018
mkdir -p "$OUT"

cd /root/bhrecomp
setsid nohup ninja -C build-aarch64 BodyHarvestRecompiled >> "$OUT/ninja_build.log" 2>&1 < /dev/null &
echo "lancado (setsid) — PID=$!"