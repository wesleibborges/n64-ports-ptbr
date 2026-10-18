#!/bin/bash
# M1 - Coleta o patch de padding dos headers duais como artefato do projeto.
set -u
SRC=/root/bhrecomp/m1_poc_padding3
DST="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/m1_patches_headers"
mkdir -p "$DST"

cp "$SRC"/headers_patched/*.h "$DST/"

: > "$DST/layout_padding.patch"
for f in $(ls "$SRC/headers_orig"); do
  diff -u "$SRC/headers_orig/$f" "$SRC/headers_patched/$f" >> "$DST/layout_padding.patch"
done

echo '=== artefatos ==='
ls -la "$DST"
echo '=== patch (linhas) ==='
wc -l "$DST/layout_padding.patch"
echo '=== patch (conteudo) ==='
cat "$DST/layout_padding.patch"