#!/bin/bash
# M1 probe4 - disseca o erro "Buffer block cannot be expressed" do SPIRV-Cross
# e levanta as opcoes reais de flags. Nao altera nada no RT64.
set -u
REP=/root/bhrecomp/m1_probe4.txt
exec > "$REP" 2>&1
B=/root/bhrecomp/build-aarch64
OUT=/root/bhrecomp/m1_glsles
DX=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux

echo "############ 0. GROUND TRUTH a partir dos logs existentes ############"
echo "--- xc.log que falharam (threw an exception) ---"
grep -l 'threw an exception' "$OUT"/*.xc.log 2>/dev/null | wc -l
grep -l 'threw an exception' "$OUT"/*.xc.log 2>/dev/null | xargs -r -n1 basename | sed 's/\.xc\.log//'
echo "--- glslang.log que falharam (ERROR) ---"
grep -l 'ERROR' "$OUT"/*.glslang.log 2>/dev/null | wc -l
grep -l 'ERROR' "$OUT"/*.glslang.log 2>/dev/null | xargs -r -n1 basename | sed 's/\.glslang\.log//'

echo
echo "############ 1. help completo do spirv-cross (opcoes relevantes) ############"
spirv-cross --help > /root/bhrecomp/spirvcross_help.txt 2>&1
wc -l /root/bhrecomp/spirvcross_help.txt
grep -n -i -E 'flatten|unused|enhanced|ubo|plain|separate|ssbo|stem' /root/bhrecomp/spirvcross_help.txt

echo
echo "############ 2. spirv-tools ############"
ls -la /usr/bin/spirv-dis /usr/bin/spirv-val 2>&1
apt-get install -y --no-install-recommends spirv-tools 2>&1 | tail -3
command -v spirv-dis && echo "spirv-dis OK" || echo "spirv-dis AUSENTE"

echo
echo "############ 3. onde estao os .spv que falharam ############"
for n in RSPProcessCS RasterVSSpecConstant RasterPSDynamic; do
  echo "$n : $(find $B -name "${n}.hlsl.spv" | head -1)"
done
SPV=$(find "$B" -name 'RasterVSSpecConstant.hlsl.spv' | head -1)

echo
echo "############ 4. reflection (--reflect) de RasterVSSpecConstant ############"
spirv-cross --reflect "$SPV" --output /root/bhrecomp/rastervs.json 2>&1 | head -5
echo "rc=$?"
python3 - <<'PY'
import json
try:
    d = json.load(open('/root/bhrecomp/rastervs.json'))
except Exception as e:
    print('erro json:', e); raise SystemExit
for key in d:
    if key in ('entryPoints','types','modes','inputs','outputs','textures','images'):
        print('==', key, '== (len %d)' % len(d[key]))
print('--- chaves ---', sorted(d.keys()))
ubo = d.get('ubos', d.get('uniform_buffers', {}))
print('--- UBOs ---', list(ubo.keys()))
for k, v in ubo.items():
    print('   ', k, 'block_size=', v.get('block_size'), 'members=', len(v.get('members', [])))
    for m in v.get('members', [])[:60]:
        print('        ', m.get('name'), m.get('type'), 'off=', m.get('offset'), 'size=', m.get('size'))
PY

echo
echo "############ 5. disassembly do OpTypeStruct (se spirv-dis existir) ############"
if command -v spirv-dis >/dev/null; then
  spirv-dis "$SPV" > /root/bhrecomp/rastervs.spvasm 2>&1
  wc -l /root/bhrecomp/rastervs.spvasm
  grep -n -m6 'OpDecorate.*Block\|OpMemberDecorate.*Offset\|OpTypeStruct' /root/bhrecomp/rastervs.spvasm | head -20
else
  echo "(spirv-dis ausente)"
fi

echo
echo "############ 6. flags alternativas no SPIRV-Cross (RasterVSSpecConstant) ############"
run() { echo "--- $* ---"; spirv-cross "$@" "$SPV" --output /tmp/t.glsl 2>&1 | head -3; echo "rc=$?"; }
run --version 320 --es --remove-unused-variables
run --version 320 --es --flatten-ubo
run --version 320 --es --flatten-ubo --remove-unused-variables
run --version 320 --es --separate-shader-objects
run --version 320 --es --glsl-emit-ubo-as-plain-uniforms
run --version 320 --es --glsl-emit-ubo-as-plain-uniforms --remove-unused-variables

echo
echo "############ 7. DXC vendorizado ############"
file "$DX"
ldd "$DX" 2>&1 | head -12
export LD_LIBRARY_PATH=/root/bhrecomp/lib/rt64/src/contrib/dxc/lib/x64
"$DX" --version 2>&1 | head -3
"$DX" -help 2>&1 | grep -n -i -E 'gl-layout|flatten|legalize|fspv' | head -20