#!/bin/bash
# M1 - Pipeline de shaders GLSL ES para o backend GLES do RT64 (R36S / Mali-G31)
# Objetivo: provar que TODOS os blobs SPIR-V que o RT64 ja gera para aarch64
# podem ser convertidos para GLSL ES 3.20 (SPIRV-Cross) e compilados (glslangValidator).
# Nao altera o CMake: usa os .spv ja produzidos em build-aarch64.
set -u

BUILD=/root/bhrecomp/build-aarch64
OUT=/root/bhrecomp/m1_glsles
rm -rf "$OUT"
mkdir -p "$OUT"

echo "=== ferramentas ==="
spirv-cross --help 2>&1 | head -2
glslangValidator --version 2>&1 | head -3

total=0; xc_ok=0; xc_fail=0; gl_ok=0; gl_fail=0
: > "$OUT/fail_xc.txt"
: > "$OUT/fail_glsl.txt"

while IFS= read -r spv; do
    total=$((total + 1))
    base=$(basename "$spv")
    case "$base" in
        *VS*) stage=vert ;;
        *PS*) stage=frag ;;
        *CS*) stage=comp ;;
        *GS*) stage=geom ;;
        *)    stage=vert ;;
    esac

    glsl="$OUT/$base.$stage.glsl"
    if spirv-cross --version 320 --es "$spv" --output "$glsl" > "$OUT/$base.xc.log" 2>&1; then
        xc_ok=$((xc_ok + 1))
    else
        xc_fail=$((xc_fail + 1))
        echo "$base" >> "$OUT/fail_xc.txt"
        continue
    fi

    if glslangValidator -S "$stage" "$glsl" > "$OUT/$base.glslang.log" 2>&1; then
        gl_ok=$((gl_ok + 1))
    else
        gl_fail=$((gl_fail + 1))
        echo "$base" >> "$OUT/fail_glsl.txt"
    fi
done < <(find "$BUILD" -name '*.spv' | sort)

echo "=== RESULTADO M1 (GLSL ES 3.20) ==="
echo "blobs SPIR-V encontrados : $total"
echo "spirv-cross OK           : $xc_ok"
echo "spirv-cross FALHOU       : $xc_fail"
echo "glslangValidator OK      : $gl_ok"
echo "glslangValidator FALHOU  : $gl_fail"
echo "--- falhas spirv-cross (arquivo) ---"
cat "$OUT/fail_xc.txt"
echo "--- falhas glslang (arquivo) ---"
cat "$OUT/fail_glsl.txt"