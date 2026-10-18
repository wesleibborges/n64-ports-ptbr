#!/bin/bash
# M3 (pre-validacao no device) -- monta o pacote de sondas GLES para o cartao SD.
#
# Junta os binarios aarch64 gerados por m3_build_gles_probe.sh + o runner + o README,
# gera o tar.gz e imprime a auditoria do pacote (md5, listagem, conferencia de que
# NENHUM libEGL.so* entrou no pacote -- ver a trava do stub em gles_egl_stub.c).
#
# Uso:  bash m3_package_gles_probe.sh
# Vars: OUT_DIR (build), PKG_DIR (destino no projeto)
set -u

PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"
TOOLS="$PROJ/evidencias/tools"
OUT="${OUT_DIR:-/root/bhrecomp/m3_gles_probe}"
PKG="${PKG_DIR:-$PROJ/evidencias/gles_device_probe_pkg}"
TARBALL="$PROJ/evidencias/gles_device_probe_pkg.tar.gz"

echo "=== M3 | empacotamento das sondas GLES ==="
echo "data_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "build=$OUT"
echo "pkg=$PKG"
echo

rm -rf "$PKG"
mkdir -p "$PKG" || exit 1

echo "--- [1] copiando binarios ---"
for binary in gles_device_probe_aarch64 gles_smoke_aarch64; do
    if [ -f "$OUT/$binary" ]; then
        cp "$OUT/$binary" "$PKG/"
        chmod 755 "$PKG/$binary"
        echo "ok  $binary ($(stat -c%s "$OUT/$binary") bytes)"
    else
        echo "AUSENTE  $binary  -- rode m3_build_gles_probe.sh antes"
        exit 1
    fi
done

echo
echo "--- [2] copiando runner e README ---"
cp "$TOOLS/m3_run_gles_probe.sh" "$PKG/run_gles_probe.sh"
cp "$TOOLS/m3_pkg_README.txt" "$PKG/README.txt"
chmod 755 "$PKG/run_gles_probe.sh"
echo "ok  run_gles_probe.sh"
echo "ok  README.txt"

echo
echo "--- [2b] copiando os casos de ESSL de PRODUCAO (secao [9c] da sonda) ---"
CASES="$PROJ/evidencias/m3_gles_probe/shader_cases"
if [ -d "$CASES" ]; then
    mkdir -p "$PKG/shader_cases"
    cp "$CASES"/*.essl "$PKG/shader_cases/"
    echo "ok  $(ls "$PKG/shader_cases" | wc -l | tr -d ' ') arquivos .essl ($(du -sh "$PKG/shader_cases" | cut -f1))"
    echo "    pares VS+PS (o runner os passa por PROBE_SHADER_DIR):"
    for frag in "$PKG/shader_cases"/*.frag.essl; do
        base=$(basename "$frag" .frag.essl)
        if [ -f "$PKG/shader_cases/$base.vert.essl" ]; then par="par ok"; else par="SEM VS"; fi
        printf '      %-22s %s\n' "$base" "$par"
    done
else
    echo "AVISO: $CASES ausente -- rode m3_make_shader_cases.sh (a secao [9c] fica sem casos)"
fi

echo
echo "--- [3] conferencia CRITICA: nenhum libEGL.so* no pacote ---"
if find "$PKG" -name 'libEGL*' -o -name 'libGLES*' -o -name 'libgbm*' | grep -q .; then
    echo "FALHA: encontrado libEGL/libGLES/libgbm no pacote. O device tem de usar as SUAS."
    find "$PKG" -name 'libEGL*' -o -name 'libGLES*' -o -name 'libgbm*'
    exit 1
fi
echo "ok  nenhuma lib de sistema no pacote (o device resolve libEGL.so.1 -> blob Mali)"

echo
echo "--- [4] arquitetura dos binarios ---"
for binary in "$PKG"/*; do
    [ -f "$binary" ] || continue
    case "$binary" in
        *.sh|*.txt) continue ;;
    esac
    printf '%-32s %s\n' "$(basename "$binary")" "$(file -b "$binary" | cut -d, -f1-3)"
done

echo
echo "--- [5] conteudo + md5 ---"
( cd "$PKG" && ls -la && echo && find . -maxdepth 1 -type f | sort | xargs md5sum )
echo
echo "--- [5b] casos de shader (secao [9c]) + md5 ---"
( cd "$PKG/shader_cases" 2>/dev/null && find . -type f | sort | xargs md5sum )

echo
echo "--- [6] sintaxe do runner ---"
bash -n "$PKG/run_gles_probe.sh" && echo "bash -n run_gles_probe.sh OK"
sh -n "$PKG/run_gles_probe.sh" 2>/dev/null && echo "sh -n run_gles_probe.sh OK"

echo
echo "--- [7] tar.gz ---"
( cd "$PROJ/evidencias" && tar czf "$TARBALL" "$(basename "$PKG")" )
echo "tarball=$TARBALL"
ls -la "$TARBALL"
md5sum "$TARBALL"
echo "conteudo:"
tar tzf "$TARBALL"

echo
echo "=== fim ==="