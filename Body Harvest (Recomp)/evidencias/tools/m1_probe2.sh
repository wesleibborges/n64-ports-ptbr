#!/bin/bash
# M1 - coleta de dados decisivos para as 10 falhas do spirv-cross
set -u
B=/root/bhrecomp/build-aarch64
OUT=/root/bhrecomp/m1_glsles
REP=/root/bhrecomp/m1_probe2.txt
exec > "$REP" 2>&1

echo "############ 1. plume: backends existentes ############"
ls -la /root/bhrecomp/lib/rt64/src/contrib/plume/ | head -40
echo "--- arquivos plume_*.* ---"
find /root/bhrecomp/lib/rt64/src/contrib/plume -maxdepth 1 -type f | sort

echo
echo "############ 2. spirv-cross: opcoes relevantes (help completo) ############"
spirv-cross --help 2>&1 | sed -n '1,140p'

echo
echo "############ 3. REFLECTION dos shaders que falham ############"
for n in RasterVSSpecConstant RSPProcessCS RasterPSDynamic; do
    spv="$B/$n.hlsl.spv"
    [ -f "$spv" ] || spv=$(find "$B" -name "$n.hlsl.spv" | head -1)
    echo "=== $n  (spv=$spv) ==="
    spirv-cross --version 320 --es --reflect "$spv" 2>&1 | head -70
    echo
done

echo
echo "############ 4. teste de flags alternativas em RasterVSSpecConstant ############"
spv=$(find "$B" -name 'RasterVSSpecConstant.hlsl.spv' | head -1)
echo "--- 4a. --version 320 desktop (sem --es) ---"
spirv-cross --version 320 "$spv" --output /tmp/t1.glsl 2>&1 | head -3; echo "rc=$?"; wc -l /tmp/t1.glsl 2>/dev/null
echo "--- 4b. --version 310 --es ---"
spirv-cross --version 310 --es "$spv" --output /tmp/t2.glsl 2>&1 | head -3; echo "rc=$?"; wc -l /tmp/t2.glsl 2>/dev/null
echo "--- 4c. --version 320 --es --flatten-ubo ---"
spirv-cross --version 320 --es --flatten-ubo "$spv" --output /tmp/t3.glsl 2>&1 | head -3; echo "rc=$?"; wc -l /tmp/t3.glsl 2>/dev/null
echo "--- 4d. --version 320 --es --force-flattened-io (se existir) ---"
spirv-cross --version 320 --es --force-flattened-io "$spv" --output /tmp/t4.glsl 2>&1 | head -3; echo "rc=$?"; wc -l /tmp/t4.glsl 2>/dev/null

echo
echo "############ 5. DebugPS: linha 54 do GLSL emitido ############"
sed -n '40,60p' "$OUT/DebugPS.hlsl.spv.frag.glsl" 2>/dev/null

echo
echo "############ 6. Im3DVS: linha 46 ############"
sed -n '40,50p' "$OUT/Im3DVS.hlsl.spv.vert.glsl" 2>/dev/null

echo
echo "############ 7. dxc-linux help: flags gl-layout ############"
DX=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux
"$DX" --help 2>&1 | grep -i -E 'gl-layout|fvk|flatten|auto-bind' | head -30
echo "--- rc do help ---"; "$DX" --help >/dev/null 2>&1; echo "rc=$?"