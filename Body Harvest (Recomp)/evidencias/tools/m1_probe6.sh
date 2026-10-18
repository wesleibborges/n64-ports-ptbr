#!/bin/bash
# M1 probe6 - layout DX vs GL: causa raiz do erro do SPIRV-Cross e fix candidato.
# Nao altera nada no RT64; gera artefatos em /root/bhrecomp/m1_layout.
set -u
REP=/root/bhrecomp/m1_probe6.txt
exec > "$REP" 2>&1

SRC=/root/bhrecomp/lib/rt64/src
SH=/root/bhrecomp/build-aarch64/src/shaders
DX=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/x64
WORK=/root/bhrecomp/m1_layout
mkdir -p "$WORK"

echo "############ 0. qual spirv-cross esta no PATH ############"
file /usr/bin/spirv-cross
ls -la /usr/bin/spirv-cross* 2>&1
if head -1 /usr/bin/spirv-cross 2>/dev/null | grep -q '#!'; then
  echo '--- e um WRAPPER script ---'; cat /usr/bin/spirv-cross
fi

echo
echo "############ 1. disassembly do spv DX-layout (bloco problematico) ############"
spirv-dis "$SH/RasterVSSpecConstant.hlsl.spv" > "$WORK/rvss.dx.spvasm" 2>&1
wc -l "$WORK/rvss.dx.spvasm"
echo '--- tipos/structs/arrays ---'
grep -n -E 'OpTypeStruct|OpTypeArray|OpTypeRuntimeArray|OpTypeMatrix|OpTypeVector|OpTypeFloat|OpTypeInt ' "$WORK/rvss.dx.spvasm" | sed 's/^ *//' | head -60
echo '--- nomes dos membros ---'
grep -n -E 'OpMemberName|OpName %' "$WORK/rvss.dx.spvasm" | sed 's/^ *//' | head -80
echo '--- todos os OpMemberDecorate (offsets) ---'
grep -n 'OpMemberDecorate' "$WORK/rvss.dx.spvasm" | sed 's/^ *//'
echo '--- decorations de bloco ---'
grep -n -E 'OpDecorate.*(Block|BufferBlock|NonWritable|Binding|DescriptorSet)' "$WORK/rvss.dx.spvasm" | sed 's/^ *//'

echo
echo "############ 2. desktop GLSL (nao-ES) no spv DX-layout ############"
for v in 430 450 460; do
  echo -n "--version $v (desktop): "
  spirv-cross --version "$v" "$SH/RasterVSSpecConstant.hlsl.spv" --output "/tmp/d$v.glsl" 2>&1 | head -2
  echo ""
done

echo
echo "############ 3. regeneracao com -fvk-use-gl-layout (resto identico ao ninja) ############"
gen() { # gen <outname> <extra defines...>
  local OUT="$1"; shift
  echo "--- $OUT : defines=[$*] ---"
  "$DX" -spirv -fspv-target-env=vulkan1.0 -fvk-use-gl-layout -I"$SRC" -E VSMain -T vs_6_3 -fvk-invert-y "$@" "$SRC/src/shaders/RasterVS.hlsl" /Fo "$WORK/$OUT.spv" 2>&1 | head -6
  if [ -f "$WORK/$OUT.spv" ]; then
    echo "    spv gerado: $(stat -c %s "$WORK/$OUT.spv") bytes"
  else
    echo "    FALHOU: sem spv"
  fi
}
gen rvss_gl -D SPEC_CONSTANT_RENDER_PARAMS

echo
echo "############ 4. diff de offsets DX vs GL (o dado critico) ############"
spirv-dis "$WORK/rvss_gl.spv" > "$WORK/rvss.gl.spvasm" 2>&1
wc -l "$WORK/rvss.gl.spvasm"
echo '--- OpMemberDecorate: < = DX layout | > = GL layout ---'
diff <(grep 'OpMemberDecorate' "$WORK/rvss.dx.spvasm" | sed 's/^ *//' | sort) \
     <(grep 'OpMemberDecorate' "$WORK/rvss.gl.spvasm" | sed 's/^ *//' | sort)
echo "--- fim do diff ---"
echo '--- tamanhos/stride das structs que envolvem runtime arrays ---'
echo 'DX:'; grep -n -E 'OpDecorate %_(runtimearr|ptr_Uniform_type_StructuredBuffer)' "$WORK/rvss.dx.spvasm" | sed 's/^ *//' | head -20
echo 'GL:'; grep -n -E 'OpDecorate %_(runtimearr|ptr_Uniform_type_StructuredBuffer)' "$WORK/rvss.gl.spvasm" | sed 's/^ *//' | head -20

echo
echo "############ 5. spirv-cross ES 320 no spv GL-layout ############"
spirv-cross --version 320 --es "$WORK/rvss_gl.spv" --output "$WORK/rvss_gl.vert.glsl" 2>&1 | head -3
echo "arquivo de saida:"; ls -la "$WORK/rvss_gl.vert.glsl" 2>&1
if [ -f "$WORK/rvss_gl.vert.glsl" ]; then
  echo '--- cabecalho do GLSL ES gerado ---'; head -20 "$WORK/rvss_gl.vert.glsl"
fi

echo
echo "############ 6. outras opcoes de layout no DXC vendorizado ############"
"$DX" -help 2>&1 | grep -n -i 'scalar-layout\|dx-layout\|gl-layout\|legacy-buffer-matrix' | head