#!/bin/bash
# M1 - CORRECAO DE RAIZ do mismatch SDL2 do sysroot aarch64.
#
# Problema: o sysroot tem a BIBLIOTECA SDL 2.30.3 (libSDL2-2.0.so.0.3000.3, vinda
# do aRkOS) mas os HEADERS do jammy (SDL 2.0.20). O codigo do port e do RT64 usa
# APIs 2.24+/2.26+ (SDL_GetWindowSizeInPixels, SDL_JoystickPath,
# SDL_GetJoystickGUIDInfo, SDL_HINT_WINDOWS_DPI_AWARENESS, ...), que os headers
# 2.0.20 nao declaram -> falhas de compilacao em cascata.
#
# Correcao: instalar no sysroot os headers PUBLICOS do SDL 2.30.3 - que existem
# localmente em /root/SDL2-2.30.3/include/ (mesma versao da lib) - preservando o
# SDL_config.h / SDL_revision.h do Debian, cuja indirecao
# (#include <SDL2/_real_SDL_config.h>) ja funciona no build atual.
#
# Uso: bash m1_fix_sysroot_sdl2_headers.sh
set -u

SRCINC=/root/sysroot64/usr/include/SDL2
SRC230=/root/SDL2-2.30.3/include
LIB=/root/sysroot64/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0
OUT=/root/bhrecomp/m1_apply_20261018
BK="$OUT/sysroot_SDL2_include_orig"
mkdir -p "$OUT"

echo "=== 1) Prova RAW do mismatch (headers x lib) ==="
echo "--- headers atualmente instalados ---"
grep -E 'SDL_MAJOR_VERSION|SDL_MINOR_VERSION|SDL_PATCHLEVEL' "$SRCINC/SDL_version.h"
echo "--- biblioteca efetivamente linkada (SONAME real) ---"
readlink -f "$LIB"
echo "--- headers reais disponiveis localmente (fonte da correcao) ---"
grep -E 'SDL_MAJOR_VERSION|SDL_MINOR_VERSION|SDL_PATCHLEVEL' "$SRC230/SDL_version.h"

echo
echo "=== 2) Backup COMPLETO do include/SDL2 atual ==="
if [ ! -d "$BK" ]; then
    mkdir -p "$BK"
    cp -a "$SRCINC/." "$BK/"
    echo "backup criado: $BK ($(ls "$BK" | wc -l) arquivos)"
else
    echo "backup ja existia (preservado): $BK ($(ls "$BK" | wc -l) arquivos)"
fi
md5sum "$BK/SDL_version.h" "$BK/SDL_config.h" 2>/dev/null

echo
echo "=== 3) Instalando os headers publicos do SDL 2.30.3 ==="
cp -a "$SRC230"/*.h "$SRCINC/"
echo "copiados: $(ls "$SRC230"/*.h | wc -l) headers"

echo
echo "=== 4) Preservando o SDL_config.h (indirecao Debian que ja funciona) ==="
if [ -f "$BK/SDL_config.h" ]; then
    cp -p "$BK/SDL_config.h" "$SRCINC/SDL_config.h"
    echo "SDL_config.h restaurado do backup (Debian -> <SDL2/_real_SDL_config.h>)"
fi
[ -f "$BK/SDL_revision.h" ] && cp -p "$BK/SDL_revision.h" "$SRCINC/SDL_revision.h"

echo
echo "=== 5) Verificacao ==="
echo "--- versao dos headers agora ---"
grep -E 'SDL_MAJOR_VERSION|SDL_MINOR_VERSION|SDL_PATCHLEVEL' "$SRCINC/SDL_version.h" | head -3
echo "--- APIs que faltavam (todas devem aparecer) ---"
grep -l 'SDL_GetWindowSizeInPixels' "$SRCINC/SDL_video.h"
grep -c 'SDL_JoystickPath' "$SRCINC/SDL_joystick.h"
grep -c 'SDL_GetJoystickGUIDInfo' "$SRCINC/SDL_joystick.h"
grep -c 'SDL_HINT_WINDOWS_DPI_AWARENESS' "$SRCINC/SDL_hints.h"
echo "--- total de arquivos no include/SDL2 ---"
ls "$SRCINC" | wc -l