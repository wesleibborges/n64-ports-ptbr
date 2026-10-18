#!/bin/bash
# Diagnostico 2: verificar existencia real do driver Vulkan (panvk) e do driver GLES
OUT="$(dirname "$0")/diag_results"
mkdir -p "$OUT"
F="$OUT/diag2.txt"
: > "$F"

log(){ echo "===== $* =====" >> "$F"; "$@" >> "$F" 2>&1; echo >> "$F"; }

log uname -a
log ls /usr/lib/aarch64-linux-gnu/libvulkan*
log ls /usr/lib/aarch64-linux-gnu/libMesaVulkan*
log ls /usr/lib/aarch64-linux-gnu/libvk_*
log cat /usr/share/vulkan/icd.d/panfrost_icd.json
log cat /usr/share/vulkan/icd.d/lvp_icd.json
log ls /usr/lib/aarch64-linux-gnu/dri/ | grep -Ei 'panfrost|lima|rockchip|swrast'
log ls /usr/lib/aarch64-linux-gnu/gl4es 2>/dev/null
log find / -maxdepth 3 -name 'libvulkan*' 2>/dev/null
log find / -maxdepth 4 -name 'libGLSLstand*' -o -maxdepth 4 -name 'libgl4es*' 2>/dev/null
log lsmod
log ls /dev/mali* 2>/dev/null
log dmesg 2>/dev/null | grep -Ei 'mali|panfrost|lima|gpu' | tail -n 30
log ls /sys/kernel/debug 2>/dev/null | head -5
log which gl4es eglinfo kmscube weston 2>/dev/null
log dpkg -l 2>/dev/null | grep -Ei 'mesa|vulkan|mali|gl4es|glshim' | head -30
echo "DIAG2-DONE" >> "$F"
