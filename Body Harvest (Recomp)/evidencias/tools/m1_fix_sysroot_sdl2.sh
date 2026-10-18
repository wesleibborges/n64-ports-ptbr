#!/bin/bash
# M1 - Corrige o MISMATCH do sysroot aarch64: headers SDL2 2.0.20 (jammy) x
# biblioteca SDL2 2.30 (libSDL2-2.0.so.0.3000.3, vinda do aRkOS).
#
# Sintoma: `plume_vulkan.cpp` usa SDL_GetWindowSizeInPixels (SDL 2.26+) e o build
# aarch64 falha com "'SDL_GetWindowSizeInPixels' was not declared in this scope".
# NAO tem relacao com o padding de layout do M1: e um bloqueio pre-existente do
# ambiente, exposto porque o `.ninja_log` perdeu o registro do objeto do plume
# ("command line not found in log") e o ninja passou a recompila-lo.
#
# Correcao: acrescentar ao header do sysroot a declaracao da API que a BIBLIOTECA
# REALMENTE PRESENTE exporta (a lib e 2.30, os headers e que sao 2.0.20).
#
# Uso: bash m1_fix_sysroot_sdl2.sh
set -u

INC=/root/sysroot64/usr/include/SDL2/SDL_video.h
OUT=/root/bhrecomp/m1_apply_20261018
mkdir -p "$OUT"

echo "=== 1) Prova RAW do mismatch ==="
echo "--- SDL_version.h (headers instalados) ---"
grep -E 'SDL_MAJOR_VERSION|SDL_MINOR_VERSION|SDL_PATCHLEVEL' /root/sysroot64/usr/include/SDL2/SDL_version.h
echo "--- lib efetivamente linkada ---"
ls -l /root/sysroot64/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0
echo "--- simbolo exportado pela lib (prova de que e 2.26+) ---"
nm -D --defined-only /root/sysroot64/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0 | grep GetWindowSizeInPixels

echo
echo "=== 2) Backup do header original ==="
if [ ! -f "$OUT/SDL_video.h.orig" ]; then
    cp -p "$INC" "$OUT/SDL_video.h.orig"
    echo "backup criado: $OUT/SDL_video.h.orig"
else
    echo "backup ja existia (preservado): $OUT/SDL_video.h.orig"
fi
md5sum "$OUT/SDL_video.h.orig"

echo
echo "=== 3) Inserindo declaracao (idempotente, dentro do bloco extern \"C\") ==="
python3 - "$INC" <<'PY'
import io
import re
import sys

p = sys.argv[1]
s = io.open(p, encoding='utf-8', newline='').read()

if 'SDL_GetWindowSizeInPixels' in s:
    print('ja presente: nada a fazer')
    sys.exit(0)

pat = re.compile(r'extern DECLSPEC void SDLCALL SDL_GetWindowSize\([^;]*\);', re.S)
m = pat.search(s)
if not m:
    print('ANCORA NAO ENCONTRADA (SDL_GetWindowSize)')
    sys.exit(1)

decl = '''

/* --- M1 FIX (2026-10-18) ---------------------------------------------------
 * Este sysroot aarch64 possui a biblioteca libSDL2-2.0.so.0.3000.3 (SDL 2.30,
 * vinda do aRkOS), mas os headers instalados sao do jammy (SDL 2.0.20), que nao
 * declaram as APIs introduzidas a partir da 2.26. A declaracao abaixo foi
 * acrescentada para casar com a biblioteca REALMENTE presente e linkada
 * (comprovado via: nm -D --defined-only .../libSDL2-2.0.so.0 | grep
 * GetWindowSizeInPixels -> 1 resultado). Nao altera runtime: o binario do port
 * ja importava este simbolo do SDL2 do dispositivo.
 * ------------------------------------------------------------------------- */
extern DECLSPEC void SDLCALL SDL_GetWindowSizeInPixels(SDL_Window * window,
                                                       int *w, int *h);'''

s = s[:m.end()] + decl + s[m.end():]
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('declaracao inserida apos SDL_GetWindowSize')
PY

echo
echo "=== 4) Verificacao pos-fix (SDL_video.h) ==="
grep -n 'SDL_GetWindowSizeInPixels' "$INC"
md5sum "$INC"

# ---------------------------------------------------------------------------
# 5) MESMA CLASSE DE PROBLEMA: APIs de joystick introduzidas apos a 2.0.20
#    (SDL_JoystickPathForIndex 2.24, SDL_JoystickPath 2.24,
#     SDL_GetJoystickGUIDInfo 2.26) usadas por lib/RecompFrontend/recompinput.
#    Todas as 3 sao exportadas pela lib do sysroot (comprovado por nm abaixo).
# ---------------------------------------------------------------------------
JINC=/root/sysroot64/usr/include/SDL2/SDL_joystick.h

echo
echo "=== 5.1) Prova RAW: a lib exporta as 3 APIs de joystick ==="
nm -D --defined-only /root/sysroot64/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0 | grep -E 'SDL_JoystickPath|SDL_GetJoystickGUIDInfo'

echo
echo "=== 5.2) Backup do SDL_joystick.h original ==="
if [ ! -f "$OUT/SDL_joystick.h.orig" ]; then
    cp -p "$JINC" "$OUT/SDL_joystick.h.orig"
    echo "backup criado: $OUT/SDL_joystick.h.orig"
else
    echo "backup ja existia (preservado): $OUT/SDL_joystick.h.orig"
fi
md5sum "$OUT/SDL_joystick.h.orig"

echo
echo "=== 5.3) Inserindo as 3 declaracoes (idempotente) ==="
python3 - "$JINC" <<'PY'
import io
import re
import sys

p = sys.argv[1]
s = io.open(p, encoding='utf-8', newline='').read()

if 'SDL_JoystickPath' in s:
    print('ja presente: nada a fazer')
    sys.exit(0)

# ancora: declaracao existente tambem na 2.0.20
pat = re.compile(
    r'extern DECLSPEC SDL_JoystickGUID SDLCALL SDL_JoystickGetGUIDFromString\([^;]*\);',
    re.S)
m = pat.search(s)
if not m:
    print('ANCORA NAO ENCONTRADA (SDL_JoystickGetGUIDFromString)')
    sys.exit(1)

decl = '''

/* --- M1 FIX (2026-10-18) ---------------------------------------------------
 * APIs adicionadas ao SDL apos a 2.0.20 (SDL_JoystickPathForIndex e
 * SDL_JoystickPath na 2.24; SDL_GetJoystickGUIDInfo na 2.26). Ausentes nos
 * headers 2.0.20 do sysroot, mas EXPORTADAS pela libSD2 2.30.3 presente
 * (comprovado via nm). Declaracoes transcritas fielmente dos headers reais
 * em /root/SDL2-2.30.3/include/SDL_joystick.h e usadas por
 * lib/RecompFrontend/recompinput (input_events.cpp, profiles.cpp).
 * ------------------------------------------------------------------------- */
extern DECLSPEC const char *SDLCALL SDL_JoystickPathForIndex(int device_index);
extern DECLSPEC const char *SDLCALL SDL_JoystickPath(SDL_Joystick *joystick);
extern DECLSPEC void SDLCALL SDL_GetJoystickGUIDInfo(SDL_JoystickGUID guid,
                                                     Uint16 *vendor,
                                                     Uint16 *product,
                                                     Uint16 *version,
                                                     Uint16 *crc16);'''

s = s[:m.end()] + decl + s[m.end():]
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('3 declaracoes inseridas apos SDL_JoystickGetGUIDFromString')
PY

echo
echo "=== 5.4) Verificacao pos-fix (SDL_joystick.h) ==="
grep -n 'SDL_JoystickPath\\|SDL_GetJoystickGUIDInfo' "$JINC"
md5sum "$JINC"