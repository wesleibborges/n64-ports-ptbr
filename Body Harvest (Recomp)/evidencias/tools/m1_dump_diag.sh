#!/bin/bash
# M1 diagnostico - dump das contagens reais e dos logs de falha
set -u
OUT=/root/bhrecomp/m1_glsles
REP=/root/bhrecomp/m1_diag.txt
exec > "$REP" 2>&1

echo "=== INVENTARIO $OUT ==="
for ext in vert.glsl frag.glsl comp.glsl xc.log glslang.log spv; do
    n=$(find "$OUT" -maxdepth 1 -name "*.$ext" | wc -l)
    printf '%-12s = %s\n' "$ext" "$n"
done

echo
echo "=== fail_xc.txt (spirv-cross) ==="
cat "$OUT/fail_xc.txt" 2>/dev/null
echo
echo "=== fail_glsl.txt (glslangValidator) ==="
cat "$OUT/fail_glsl.txt" 2>/dev/null

echo
echo "=== LOGS COMPLETOS: falhas spirv-cross ==="
while IFS= read -r b; do
    [ -z "$b" ] && continue
    echo "### $b"
    cat "$OUT/$b.xc.log" 2>/dev/null
    echo
done < "$OUT/fail_xc.txt"

echo
echo "=== LOGS COMPLETOS: falhas glslang ==="
while IFS= read -r b; do
    [ -z "$b" ] && continue
    echo "### $b"
    cat "$OUT/$b.glslang.log" 2>/dev/null
    echo
done < "$OUT/fail_glsl.txt"

echo
echo "=== DXC vendorizado: binarios e opcao gl-layout ==="
DXC=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux
ls -la "$DXC"
"$DXC" --help 2>&1 | grep -i -E 'gl-layout|fvk-use|flatten|spirv' | head -30

echo
echo "=== comportamento quando $OUT ja existe (por que ls variou) ==="
ls -la /root/bhrecomp/ | grep -i m1