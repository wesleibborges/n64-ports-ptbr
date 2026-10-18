#!/bin/bash
# M1.2 - Corrige o `prefix` do pacote SD2 do sysroot aarch64 para cross-build.
#
# Sintoma (pre-existente, exposto pela reconfiguracao do M1.2):
#   CMake Generate step failed:
#     Imported target "SDL2::SDL2" includes non-existent path "/usr/include/SDL2"
#
# Causa: /root/sysroot64/usr/lib/aarch64-linux-gnu/cmake/SDL2/sdl2-config.cmake
# declara `set(prefix "/usr")` (o path DO DEVICE). O CMake valida
# INTERFACE_INCLUDE_DIRECTORIES de imported targets em tempo de generate e falha
# porque /usr/include/SDL2 nao existe no host.
#
# Correcao: reescrever `prefix` para o path do sysroot NO HOST, de forma
# idempotente e com backup (nao altera o device nem a lib linkada).
#
# Uso: bash m1_2_fix_sysroot_sdl2_prefix.sh
set -u

CFG=/root/sysroot64/usr/lib/aarch64-linux-gnu/cmake/SDL2/sdl2-config.cmake
OUT=/root/bhrecomp/m1_2_gles
mkdir -p "$OUT"

echo "=== 1) Prova RAW do problema ==="
sed -n '1,10p' "$CFG"
ls -d /usr/include/SDL2 2>&1 || echo "OK: /usr/include/SDL2 NAO existe no host"
ls -d /root/sysroot64/usr/include/SDL2

echo
echo "=== 2) Backup ==="
if [ ! -f "$OUT/sdl2-config.cmake.orig" ]; then
    cp -p "$CFG" "$OUT/sdl2-config.cmake.orig"
    echo "backup criado: $OUT/sdl2-config.cmake.orig"
else
    echo "backup ja existia (preservado)"
fi
md5sum "$OUT/sdl2-config.cmake.orig"

echo
echo "=== 3) Aplicando prefix do sysroot (idempotente) ==="
sed -i 's|^set(prefix "/usr") *$|set(prefix "/root/sysroot64/usr")|' "$CFG"
grep -n 'set(prefix' "$CFG"
grep -n 'set(SDL2_INCLUDE_DIRS\|set(SDL2_LIBDIR' "$CFG"
md5sum "$CFG"

echo
echo "=== 4) RESTAURANDO os DOIS include dirs (chave: <SDL2/...>) ==="
# O codigo do port (recompui/ui_state.cpp, rt64) faz `#include <SDL2/SDL_video.h>`,
# que so resolve com `-I<sysroot>/usr/include`. O codigo do RT64/plume faz
# `#include <SDL.h>`, que so resolve com `-I<sysroot>/usr/include/SDL2`.
# O pacote jammy (autotools) exporta APENAS o segundo; a config upstream do SDL2
# exporta os DOIS. Prova de que o build M1 usava os dois (log de 2026-10-18):
#   -I/root/sysroot64/usr/include  E  -I/root/sysroot64/usr/include/SDL2
# Sem o primeiro, `ui_state.cpp` falha com "SDL2/SDL_video.h: No such file".
sed -i 's|^set(SDL2_INCLUDE_DIRS "\${includedir}/SDL2") *$|set(SDL2_INCLUDE_DIRS "${includedir}/SDL2" "${includedir}")|' "$CFG"
grep -n 'set(SDL2_INCLUDE_DIRS' "$CFG"
md5sum "$CFG"