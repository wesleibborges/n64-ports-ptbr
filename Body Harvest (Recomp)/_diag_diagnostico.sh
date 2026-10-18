#!/bin/bash
# Diagnostico Vulkan/GL no dispositivo (R36S/dArkOS ou ArkOS)
# Nao abre janela. Apenas coleta informacoes e grava em arquivos na pasta do port.

directory="${0%/*}"
OUT="$directory/diag_results"

rm -rf "$OUT"
mkdir -p "$OUT"

log() {
    echo "===== $1 =====" >> "$OUT/diag.txt" 2>&1
    "$@" >> "$OUT/diag.txt" 2>&1
    echo "" >> "$OUT/diag.txt"
}

echo "# Diagnostico $(date)" > "$OUT/diag.txt"

log uname -a
log cat /etc/os-release
log ls /usr/lib/aarch64-linux-gnu/ | grep -Ei 'vulkan|panvk|gallium'
log ls /usr/share/vulkan/icd.d/ 2>/dev/null
log vulkaninfo --summary 2>&1
log vulkaninfo 2>&1
log glxinfo 2>&1
log glxinfo -B 2>&1
log es2_info 2>&1
log ls /usr/lib/libGLES* 2>/dev/null
log ls /usr/lib/aarch64-linux-gnu/libGLES* 2>/dev/null
log ls /usr/lib/aarch64-linux-gnu/dri/ 2>/dev/null
log ls /sys/class/graphics/fb0/ 2>/dev/null
log cat /sys/kernel/debug/mali0/version 2>/dev/null

echo "DIAG-DONE" >> "$OUT/diag.txt"
