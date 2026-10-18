#!/bin/bash
# M1 probe7 - causa raiz (vec3 desalinhado no SSBO RDPParams) e prova do fix por padding explicito.
# Nao altera a arvore do RT64; trabalha em copia isolada (/root/bhrecomp/m1_pad).
set -u
REP=/root/bhrecomp/m1_probe7.txt
exec > "$REP" 2>&1

SRC=/root/bhrecomp/lib/rt64/src
SH=/root/bhrecomp/build-aarch64/src/shaders
DX=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/x64
W=/root/bhrecomp/m1_layout
P=/root/bhrecomp/m1_pad
mkdir -p "$W"

echo "############ 0. conferindo caminhos (bug do probe6) ############"
ls -la "$SRC/shaders/RasterVS.hlsl"
echo "antes era usado: \$SRC/src/shaders -> path duplicado"

echo
echo "############ 1. RasterVSSpecConstant com -fvk-use-gl-layout (path corrigido) ############"
"$DX" -spirv -fspv-target-env=vulkan1.0 -fvk-use-gl-layout -I"$SRC" -E VSMain -T vs_6_3 \
  -fvk-invert-y -D SPEC_CONSTANT_RENDER_PARAMS "$SRC/shaders/RasterVS.hlsl" /Fo "$W/rvss_gl.spv" 2>&1 | head -5
ls -la "$W/rvss_gl.spv" 2>&1

echo
echo "############ 2. offsets DX vs GL (o dado critico) ############"
spirv-dis "$W/rvss_gl.spv" > "$W/rvss.gl.spvasm" 2>&1
echo '--- diff MemberDecorate+ArrayStride (vazio = identicos) ---'
diff <(grep -E 'OpMemberDecorate|ArrayStride' "$W/rvss.dx.spvasm" | sed 's/^ *//' | sort) \
     <(grep -E 'OpMemberDecorate|ArrayStride' "$W/rvss.gl.spvasm" | sed 's/^ *//' | sort)
echo '--- fim diff ---'
echo 'GL strides:'; grep -n 'ArrayStride' "$W/rvss.gl.spvasm" | sed 's/^ *//'

echo
echo "############ 3. spirv-cross ES 320 no SPIR-V GL-layout ############"
spirv-cross --version 320 --es "$W/rvss_gl.spv" --output "$W/rvss_gl.vert.glsl" 2>&1 | head -3
if [ -f "$W/rvss_gl.vert.glsl" ]; then
  echo 'OK: convertido'; echo '--- cabecalho ---'; head -18 "$W/rvss_gl.vert.glsl"
fi

echo
echo "############ 4. prova do fix: padding explicito no header dual (copia isolada) ############"
rm -rf "$P"; mkdir -p "$P/shared"
cp "$SRC/shared/"*.h "$P/shared/"
python3 - <<'PY'
p='/root/bhrecomp/m1_pad/shared/rt64_rdp_params.h'
s=open(p).read()
# vec3 precisa de offset multiplo de 16 em std430 -> padding explicito apos keyCenter;
# tail padding para o struct fechar em 144 (mesmo em C++, que nao aplica regras HLSL).
s=s.replace("        float3 keyCenter;\n", "        float3 keyCenter;\n        int padding1;\n")
s=s.replace("        int convertK[6];\n", "        int convertK[6];\n        int padding2[3];\n")
open(p,'w').write(s)
print(s)
PY

echo
echo "############ 5. com padding: offsets DX vs GL coincidem? ############"
"$DX" -spirv -fspv-target-env=vulkan1.0 -fvk-use-dx-layout -I"$P" -I"$SRC" -E VSMain -T vs_6_3 \
  -fvk-invert-y -D SPEC_CONSTANT_RENDER_PARAMS "$SRC/shaders/RasterVS.hlsl" /Fo "$W/rvss_pad_dx.spv" 2>&1 | head -3
"$DX" -spirv -fspv-target-env=vulkan1.0 -fvk-use-gl-layout -I"$P" -I"$SRC" -E VSMain -T vs_6_3 \
  -fvk-invert-y -D SPEC_CONSTANT_RENDER_PARAMS "$SRC/shaders/RasterVS.hlsl" /Fo "$W/rvss_pad_gl.spv" 2>&1 | head -3
spirv-dis "$W/rvss_pad_dx.spv" > "$W/rvss_pad.dx.spvasm" 2>&1
spirv-dis "$W/rvss_pad_gl.spv" > "$W/rvss_pad.gl.spvasm" 2>&1
echo '--- diff DX vs GL COM padding (vazio = identicos) ---'
diff <(grep -E 'OpMemberDecorate|ArrayStride' "$W/rvss_pad.dx.spvasm" | sed 's/^ *//' | sort) \
     <(grep -E 'OpMemberDecorate|ArrayStride' "$W/rvss_pad.gl.spvasm" | sed 's/^ *//' | sort)
echo '--- fim diff ---'
echo '--- offsets COM padding (DX) ---'
grep -E 'OpMemberDecorate %RDPParams|ArrayStride' "$W/rvss_pad.dx.spvasm" | sed 's/^ *//'
echo '--- diff vs SEM padding (mostra o deslocamento) ---'
diff <(grep -E 'OpMemberDecorate %RDPParams|ArrayStride' "$W/rvss.dx.spvasm" | sed 's/^ *//' | sort) \
     <(grep -E 'OpMemberDecorate %RDPParams|ArrayStride' "$W/rvss_pad.dx.spvasm" | sed 's/^ *//' | sort)

echo
echo "############ 6. teste chave: spirv-cross ES 320 no SPIR-V *DX-layout* COM padding ############"
echo '(se converter, nao precisamos de -fvk-use-gl-layout: um unico conjunto de blobs serve p/ Vulkan+D3D12+Metal+GLES)'
spirv-cross --version 320 --es "$W/rvss_pad_dx.spv" --output "$W/rvss_pad_dx.vert.glsl" 2>&1 | head -3
if [ -f "$W/rvss_pad_dx.vert.glsl" ]; then
  echo 'OK: CONVERTEU'; echo '--- trecho do SSBO gerado ---'; grep -n -A16 'buffer instanceRDPParams' "$W/rvss_pad_dx.vert.glsl" | head -25
fi

echo
echo "############ 7. tamanho do struct no host C++ (sizeof/offsetof) ############"
cat > "$W/chk.cpp" <<'CPP'
#include <cstdio>
#include <cstddef>
#define HLSL_CPU
#include "shared/rt64_rdp_params.h"
int main() {
    using namespace interop;
    printf("sizeof(RDPParams)=%zu align=%zu\n", sizeof(RDPParams), alignof(RDPParams));
    printf("  primColor=%zu primLOD=%zu primDepth=%zu envColor=%zu fogColor=%zu blendColor=%zu\n",
        offsetof(RDPParams, primColor), offsetof(RDPParams, primLOD), offsetof(RDPParams, primDepth),
        offsetof(RDPParams, envColor), offsetof(RDPParams, fogColor), offsetof(RDPParams, blendColor));
    printf("  keyCenter=%zu padding1=%zu keyScale=%zu convertK=%zu padding2=%zu\n",
        offsetof(RDPParams, keyCenter), offsetof(RDPParams, padding1),
        offsetof(RDPParams, keyScale), offsetof(RDPParams, convertK), offsetof(RDPParams, padding2));
    return 0;
}
CPP
echo '--- SEM padding (arvore atual) ---'
g++ -std=c++17 -I"$SRC" -I"$SRC/shared" -o "$W/chk_now" "$W/chk.cpp" 2>&1 | head -5 && "$W/chk_now"
echo '--- COM padding (copia isolada) ---'
g++ -std=c++17 -I"$P" -o "$W/chk_pad" "$W/chk.cpp" 2>&1 | head -5 && "$W/chk_pad"