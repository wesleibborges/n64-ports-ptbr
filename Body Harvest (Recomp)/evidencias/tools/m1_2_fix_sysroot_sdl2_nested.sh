#!/bin/bash
# M1.2 - SDL2 do sysroot: include dirs SEM sombrear os headers Vulkan vendorizados.
#
# Contexto (dois requisitos conflitantes):
#   1. O port (recompui/ui_state.cpp) faz `#include <SDL2/SDL_video.h>` -> precisa de
#      um path que contenha `SDL2/SDL_video.h`.
#   2. O RT64/plume faz `#include <SDL.h>` -> precisa de `.../include/SDL2` no -I.
#   3. Adicionar `.../include` ao include GLOBAL (via SDL2_INCLUDE_DIRS) faz o
#      `vulkan/vulkan_core.h` DO SYSROOT (jammy, 2022) sombrear o Vulkan-Headers
#      vendorizado do RT64 -> `volk.h` falha:
#        error: 'PFN_vkGetEncodedVideoSessionParametersKHR' does not name a type
#
# Solucao: manter SDL2_INCLUDE_DIRS com o valor padrao do pacote (.../include/SDL2) e
# satisfazer o requisito 1 com um diretorio aninhado `.../include/SDL2/SDL2` contendo
# symlinks para os headers. Assim o -I extra NAO existe e o Vulkan vendorizado vence.
#
# Uso: bash m1_2_fix_sysroot_sdl2_nested.sh
set -u

CFG=/root/sysroot64/usr/lib/aarch64-linux-gnu/cmake/SDL2/sdl2-config.cmake
D=/root/sysroot64/usr/include/SDL2
TMP=/tmp/m1_2_sdl2
mkdir -p "$TMP"

echo "=== 1) Revertendo SDL2_INCLUDE_DIRS para o valor do pacote ==="
sed -i 's|^set(SDL2_INCLUDE_DIRS "\${includedir}/SDL2" "\${includedir}") *$|set(SDL2_INCLUDE_DIRS "${includedir}/SDL2")|' "$CFG"
grep -n 'set(SDL2_INCLUDE_DIRS' "$CFG"

echo
echo "=== 2) Criando o diretorio aninhado SDL2/SDL2 com symlinks ==="
mkdir -p "$D/SDL2"
n=0
for f in "$D"/*.h; do
    b=$(basename "$f")
    ln -sfn "../$b" "$D/SDL2/$b"
    n=$((n + 1))
done
echo "symlinks: $n"
ls "$D/SDL2/SDL_video.h" "$D/SDL2/SDL.h" 2>&1 | head -3

echo
echo "=== 3) Prova RAW: os dois includes resolvem com UM unico -I ==="
printf '#include <SDL2/SDL_video.h>\n#include <SDL.h>\nint main(void) { return 0; }\n' > "$TMP/t.c"
if aarch64-linux-gnu-gcc -I"$D" -c "$TMP/t.c" -o "$TMP/t.o" 2>"$TMP/err.txt"; then
    echo "OK: <SDL2/SDL_video.h> e <SDL.h> resolvem com -I$D"
else
    echo "FALHA:"; cat "$TMP/err.txt"; exit 1
fi

echo
echo "=== 4) Prova RAW: include global NAO deve conter o sysroot ==="
grep -c 'root/sysroot64/usr/include$' "$CFG" || true
md5sum "$CFG"