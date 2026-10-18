#!/bin/bash
# Diagnostico 3: sistema alternativo com kernel 5.x
# Objetivo: confirmar driver kernel panfrost + Vulkan panvk funcional
OUT="$(dirname "$0")/diag_results"
mkdir -p "$OUT"
F="$OUT/diag3.txt"
: > "$F"

log(){ echo "===== $* =====" >> "$F"; "$@" >> "$F" 2>&1; echo >> "$F"; }

log uname -a
log cat /etc/os-release
log ls /dev/panfrost 2>/dev/null
log ls /dev/mali* 2>/dev/null
log dmesg 2>/dev/null | grep -Ei 'panfrost|panthor|mali|gpu' | head -40
log ls /sys/class/devfreq/ 2>/dev/null
log ls /usr/lib/aarch64-linux-gnu/libvulkan* 2>/dev/null
log cat /usr/share/vulkan/icd.d/panfrost_icd.json 2>/dev/null
log which vulkaninfo 2>/dev/null
log vulkaninfo --summary 2>&1 | head -60
log dpkg -l 2>/dev/null | grep -Ei 'mesa-vulkan|libvulkan' | head -10
log ls /usr/lib/aarch64-linux-gnu/dri/ 2>/dev/null | grep -Ei 'panfrost|lima|rockchip'
log glxinfo -B 2>/dev/null
log eglinfo 2>&1 | head -40
echo "DIAG3-DONE" >> "$F"
