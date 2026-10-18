#!/bin/bash
# M1 - preparacao de ferramentas + dissecacao do buffer block que falha
set -u
REP=/root/bhrecomp/m1_tools.txt
exec > "$REP" 2>&1
B=/root/bhrecomp/build-aarch64
DX=/root/bhrecomp/lib/rt64/src/contrib/dxc/bin/x64/dxc-linux

echo "############ 1. dxc-linux: por que rc=127 ############"
file "$DX"
ldd "$DX" 2>&1 | head -20
echo "--- tentativa direta ---"
"$DX" --version 2>&1 | head -5; echo "rc=$?"

echo
echo "############ 2. spirv-tools disponivel? ############"
command -v spirv-dis spirv-val spirv-opt || true
apt-get install -y --no-install-recommends spirv-tools 2>&1 | tail -6
echo "--- depois ---"
command -v spirv-dis spirv-val spirv-opt || true

echo
echo "############ 3. spirv-cross help: perspective ############"
spirv-cross --help 2>&1 | grep -n -i -B2 -A4 'perspective' | head -40

echo
echo "############ 4. spirv-cross help: flatten / buffer ############"
spirv-cross --help 2>&1 | grep -n -i -E 'flatten|buffer block|ssbo|storage' | head -30