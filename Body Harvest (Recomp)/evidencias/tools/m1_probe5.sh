#!/bin/bash
# M1 probe5 - causa raiz do "Buffer block cannot be expressed" + fix candidato
# (-fvk-use-gl-layout no DXC, so para o ramo GLSL ES)
set -u
REP=/root/bhrecomp/m1_probe5.txt
exec > "$REP" 2>&1
SH=/root/bhrecomp/build-aarch64/src/shaders
DX=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/x64
S="$SH/RasterVSSpecConstant.hlsl.spv"

echo "############ 1. ninja: comando exato do DXC para um shader que falha ############"
grep -n -m2 -B3 -A12 'RasterVSSpecConstant.hlsl.spv' /root/bhrecomp/build-aarch64/build.ninja | head -60

echo
echo "############ 2. tipos/offsets de RasterVSSpecConstant ############"
spirv-dis "$S" > /root/bhrecomp/rvss.spvasm 2>&1
wc -l /root/bhrecomp/rvss.spvasm
grep -n -E 'OpName |OpTypeStruct|OpMemberDecorate|OpDecorate|OpTypeArray|OpTypeMatrix|OpTypeVector|OpTypeFloat|OpTypeInt|OpTypeBool|OpTypePointer|OpTypeRuntimeArray' /root/bhrecomp/rvss.spvasm | head -120

echo
echo "############ 3. controle: outros backends no MESMO spv ############"
echo '--- 3a. --vulkan-semantics (deve passar, e o mesmo layout) ---'
spirv-cross --vulkan-semantics "$S" --output /tmp/v.glsl 2>&1 | head -3
echo '--- 3b. --msl (Metal) ---'
spirv-cross --msl "$S" --output /tmp/m.msl 2>&1 | head -3
echo '--- 3c. --hlsl (volta para HLSL) ---'
spirv-cross --hlsl "$S" --output /tmp/h.hlsl 2>&1 | head -3

echo
echo "############ 4. FIX CANDIDATO: regerar o .spv com -fvk-use-gl-layout ############"
HLSL=/root/bhrecomp/lib/rt64/src/shaders/RasterVSSpecConstant.hlsl
ls -la "$HLSL" 2>&1
for N in RasterVSSpecConstant RasterVSDynamic RasterPSSpecConstant RasterPSDynamic RSPProcessCS; do
  SRC="/root/bhrecomp/lib/rt64/src/shaders/$N.hlsl"
  [ -f "$SRC" ] || { echo "$N: HLSL AUSENTE ($SRC)"; continue; }
  OUTSPV="/root/bhrecomp/m1_gl_layout/$N.gl.spv"
  mkdir -p /root/bhrecomp/m1_gl_layout
  case "$N" in
    *VS*) prof=vs_6_0 ;;
    *PS*) prof=ps_6_0 ;;
    *CS*) prof=cs_6_0 ;;
    *)    prof=vs_6_0 ;;
  esac
  echo "--- $N (perfil $prof) ---"
  "$DX" -spirv -T "$prof" -E main -fvk-use-gl-layout "$SRC" -Fo "$OUTSPV" 2>&1 | head -5
  if [ -f "$OUTSPV" ]; then
    echo "    spv gerado: $(stat -c %s "$OUTSPV") bytes"
    echo -n "    spirv-cross ES320: "
    spirv-cross --version 320 --es "$OUTSPV" --output "/root/bhrecomp/m1_gl_layout/$N.gl.glsl" 2>&1 | head -2
    echo "    rc=$?"
  fi
done

echo
echo "############ 5. diffs de layout (original vs gl-layout) ############"
for N in RasterVSSpecConstant; do
  spirv-dis "$SH/$N.hlsl.spv" > /tmp/a.spvasm 2>&1
  spirv-dis "/root/bhrecomp/m1_gl_layout/$N.gl.spv" > /tmp/b.spvasm 2>&1
  echo "--- offsets originais vs gl-layout ($N) ---"
  diff <(grep -E 'OpMemberDecorate' /tmp/a.spvasm | sed 's/^ *//' | sort) \
       <(grep -E 'OpMemberDecorate' /tmp/b.spvasm | sed 's/^ *//' | sort) | head -40
done