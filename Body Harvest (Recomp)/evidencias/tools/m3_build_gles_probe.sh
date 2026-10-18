#!/bin/bash
# M3 (pré-validação no device) -- build aarch64 dos artefatos de sonda GLES do R36S.
#
# Produz, para o Mali-G31 do R36S, DOIS binários aarch64 independentes do port:
#   1) gles_device_probe_aarch64  -- sonda EGL/GLES dlopen-only (não linka EGL nem GLES)
#   2) gles_smoke_aarch64         -- o smoke do M2 (15/15 no host) rodando no driver REAL
#
# O item 2 precisa de um `libEGL.so.1` só para o LINK, porque o blob Mali do device não tem
# SONAME e tem .dynsym malformado (ver gles_egl_stub.c). O stub fica em $OUT/stub e NÃO é
# publicado -- ver m3_package_gles_probe.sh.
#
# Uso:  bash m3_build_gles_probe.sh
# Vars: PLUME_DIR, STAGED_DIR, OUT_DIR
set -u

PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"
TOOLS="$PROJ/evidencias/tools"
PLUME="${PLUME_DIR:-/root/bhrecomp/lib/rt64/src/contrib/plume}"
STAGED="${STAGED_DIR:-/root/bhrecomp/m2_gles/staged}"
OUT="${OUT_DIR:-/root/bhrecomp/m3_gles_probe}"

CC=aarch64-linux-gnu-gcc
CXX=aarch64-linux-gnu-g++

mkdir -p "$OUT/stub" || exit 1
cd "$OUT" || exit 1

echo "=== M3 | build aarch64 dos artefatos de sonda GLES ==="
echo "data_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "proj=$PROJ"
echo "plume=$PLUME"
echo "staged=$STAGED"
echo "out=$OUT"
echo

echo "--- [0] ferramentas ---"
"$CC" --version | head -1
"$CXX" --version | head -1
echo

echo "--- [1] stub de link-time (libEGL.so.1, SONAME correto) ---"
"$CC" -shared -fPIC -Wl,-soname,libEGL.so.1 -O2 -Wall -Wextra \
    -o "$OUT/stub/libEGL.so.1" "$TOOLS/gles_egl_stub.c"
echo "stub rc=$?"
readelf -d "$OUT/stub/libEGL.so.1" | grep -iE 'SONAME'
md5sum "$OUT/stub/libEGL.so.1"
echo

echo "--- [2] gles_device_probe (dlopen-only: sem EGL/GLES no link) ---"
"$CXX" -std=c++17 -O2 -Wall -Wextra \
    -o "$OUT/gles_device_probe_aarch64" "$TOOLS/gles_device_probe.cpp" -ldl
echo "probe rc=$?"
echo

echo "--- [3] gles_smoke aarch64 (backend plume_gles + smoke do M2) ---"
SMOKE_SRC=""
for candidate in "$STAGED/gles_smoke.cpp" "$PLUME/gles_smoke.cpp"; do
    [ -f "$candidate" ] && SMOKE_SRC="$candidate" && break
done
if [ -z "$SMOKE_SRC" ]; then
    echo "gles_smoke.cpp AUSENTE (procurei em $STAGED e $PLUME)"
    smoke_rc=1
else
    echo "smoke_src=$SMOKE_SRC"
    # O stub e' passado por CAMINHO (nao por -lEGL): `-lEGL` acharia a libEGL.so do proprio
    # toolchain cross (GLVND, com __glDispatch* indefinidos -- medido). O linker registra o
    # SONAME do stub (libEGL.so.1) em DT_NEEDED, que no device resolve para o blob Mali.
    "$CXX" -std=c++17 -O2 -Wall -Wextra -I"$PLUME" -I"$(dirname "$SMOKE_SRC")" \
        -o "$OUT/gles_smoke_aarch64" \
        "$SMOKE_SRC" "$PLUME/plume_gles.cpp" "$PLUME/plume_gles_gl.cpp" \
        "$OUT/stub/libEGL.so.1" -ldl
    smoke_rc=$?
    echo "smoke rc=$smoke_rc"
fi
echo

echo "--- [4] auditoria dos binarios ---"
for binary in gles_device_probe_aarch64 gles_smoke_aarch64; do
    if [ -f "$OUT/$binary" ]; then
        printf '%-30s %s\n' "$binary" "$(md5sum "$OUT/$binary" | cut -d' ' -f1)"
        printf '%-30s %s bytes\n' "" "$(stat -c%s "$OUT/$binary")"
        file "$OUT/$binary" | sed 's/^/    /'
        echo "    DT_NEEDED:"
        readelf -d "$OUT/$binary" | grep -i needed | sed 's/^/      /'
        echo "    DT_RPATH/RUNPATH (deve estar vazio):"
        readelf -d "$OUT/$binary" | grep -iE 'rpath|runpath' | sed 's/^/      /'
        echo "    GLES/EGL NO link (deve estar vazio para o probe):"
        readelf -d "$OUT/$binary" | grep -iE 'libEGL|libGLES' | sed 's/^/      /'
    else
        printf '%-30s AUSENTE\n' "$binary"
    fi
    echo
done

echo "--- [5] sanity sob QEMU contra a rootfs do device ---"
echo "(esperado: teto do fluxo ok, falha de display por AUSENCIA DE GPU -- nao por codigo)"
for binary in gles_device_probe_aarch64 gles_smoke_aarch64; do
    if [ -f "$OUT/$binary" ]; then
        echo "### $binary"
        timeout 120 qemu-aarch64-static -L /opt/r36s/rootfs "$OUT/$binary" --short 2>&1 | tail -20
        echo "qemu exit=$?"
        echo
    fi
done

echo "=== fim ==="