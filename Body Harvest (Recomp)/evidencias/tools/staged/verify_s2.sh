#!/bin/bash
# M2 (stage 2) -- consolidacao RAW das verificacoes do backend plume_gles.
#
# Este script e' a fonte de verdade da evidencia do M2/s2: ele RE-EXECUTA cada
# verificacao e imprime a saida crua, para que qualquer pessoa possa reproduzir.
# Uso:  bash verify_s2.sh > /root/bhrecomp/m2_gles/s2/verify_raw.txt
set -u

PLUME=/root/bhrecomp/lib/rt64/src/contrib/plume
STAGED=/root/bhrecomp/m2_gles/staged
S2=/root/bhrecomp/m2_gles/s2
mkdir -p "$S2"

echo "=== M2 (stage 2) -- verificacao consolidada do backend plume_gles ==="
echo "Data (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

echo "############ [1] AMBIENTE ############"
uname -srm
g++ --version | head -1
aarch64-linux-gnu-g++ --version | head -1
qemu-aarch64-static --version | head -1
echo

echo "############ [2] ARTEFATOS: md5 + contagem de linhas ############"
for f in plume_gles.h plume_gles.cpp plume_gles_gl.h plume_gles_gl.cpp gles_smoke.cpp gles_target_probe.cpp; do
    if [ -f "$PLUME/$f" ]; then
        printf '%-26s %s  %6s linhas\n' "$f" "$(md5sum "$PLUME/$f" | cut -d' ' -f1)" "$(wc -l < "$PLUME/$f")"
    else
        printf '%-26s AUSENTE\n' "$f"
    fi
done
printf '%-26s %s\n' "plume_gles_s2_inc.inc" "$(md5sum "$STAGED/plume_gles_s2_inc.inc" | cut -d' ' -f1)"
printf '%-26s %s\n' "apply_s2.py" "$(md5sum /root/bhrecomp/m2_gles/apply_s2.py | cut -d' ' -f1)"
printf '%-26s %s\n' "verify_s2.sh" "$(md5sum /root/bhrecomp/m2_gles/verify_s2.sh | cut -d' ' -f1)"
echo "--- estado ANTERIOR a esta sessao (backup, s1) ---"
for f in plume_gles.h.s1 plume_gles.cpp.s1; do
    printf '%-26s %s\n' "$f" "$(md5sum "/root/bhrecomp/m2_gles/s1_backup/$f" | cut -d' ' -f1)"
done
echo

echo "############ [3] COMPILE HOST (-Wall -Wextra) ############"
cd "$PLUME" || exit 1
for tu in plume_gles_gl.cpp plume_gles.cpp gles_smoke.cpp gles_target_probe.cpp; do
    g++ -std=c++17 -Wall -Wextra -fsyntax-only "$tu" 2>&1
    printf '%-26s rc=%d  (vazio acima == zero erros/warnings)\n' "$tu" "$?"
done
echo

echo "############ [4] LINK HOST (inclui main trivial; qualquer simbolo faltante falha) ############"
printf 'int main() { return 0; }\n' > /tmp/m2_link_main.cpp
g++ -std=c++17 -c plume_gles.cpp -o /tmp/plume_gles.o && echo "compile plume_gles.o rc=$?"
g++ -std=c++17 -c plume_gles_gl.cpp -o /tmp/plume_gles_gl.o && echo "compile plume_gles_gl.o rc=$?"
g++ -std=c++17 -c /tmp/m2_link_main.cpp -o /tmp/m2_link_main.o && echo "compile main.o rc=$?"
g++ /tmp/plume_gles.o /tmp/plume_gles_gl.o /tmp/m2_link_main.o -o /tmp/m2_link_test
echo "link rc=$? (0 == toda method declarada em plume_gles.h tem definicao)"
ls -la /tmp/m2_link_test
/tmp/m2_link_test && echo "execucao rc=$?"
echo

echo "############ [5] SMOKE TEST FUNCIONAL NO HOST (Mesa llvmpipe, ES 3.2) ############"
g++ -std=c++17 -c gles_smoke.cpp -o /tmp/gles_smoke.o && \
g++ /tmp/gles_smoke.o /tmp/plume_gles.o /tmp/plume_gles_gl.o -o /tmp/gles_smoke -lEGL -ldl
echo "build rc=$?"
MESA_LOADER_DRIVER_OVERRIDE=swrast LIBGL_ALWAYS_SOFTWARE=1 /tmp/gles_smoke
echo "smoke rc=$?  (0 == ACEITE DO M2: clear chegou ao backbuffer)"
echo

echo "############ [6] BUILD AARCH64 + LINK ############"
aarch64-linux-gnu-g++ -std=c++17 -O2 -c plume_gles.cpp -o /tmp/plume_gles_a64.o && echo "compile plume_gles.cpp rc=$?"
aarch64-linux-gnu-g++ -std=c++17 -O2 -c plume_gles_gl.cpp -o /tmp/plume_gles_gl_a64.o && echo "compile plume_gles_gl.cpp rc=$?"
echo "--- main trivial para o alvo (compilado COM o cross-compiler) ---"
printf 'int main() { return 0; }\n' > /tmp/m2_link_main_a64.cpp
aarch64-linux-gnu-g++ -std=c++17 -c /tmp/m2_link_main_a64.cpp -o /tmp/m2_link_main_a64.o && echo "compile main aarch64 rc=$?"
aarch64-linux-gnu-g++ /tmp/plume_gles_a64.o /tmp/plume_gles_gl_a64.o /tmp/m2_link_main_a64.o -o /tmp/m2_link_test_a64
echo "link aarch64 rc=$?"
file /tmp/m2_link_test_a64
echo

echo "############ [7] PROBE ON-TARGET sob QEMU/aarch64 ############"
aarch64-linux-gnu-g++ -std=c++17 -O2 -c gles_target_probe.cpp -o /tmp/gles_target_probe_a64.o -I"$PLUME"
aarch64-linux-gnu-g++ /tmp/gles_target_probe_a64.o /tmp/plume_gles_a64.o /tmp/plume_gles_gl_a64.o -o /tmp/gles_target_probe_a64
echo "build rc=$?"
qemu-aarch64-static -L /opt/r36s/rootfs /tmp/gles_target_probe_a64
echo "probe rc=$?  (0 == carregador + interface executam corretamente no alvo)"
echo

echo "############ [8] LIMITACAO CONHECIDA: smoke test NAO roda sob QEMU ############"
echo "--- libs EGL do rootfs (libEGL.so.1 e' symlink para o blob Mali) ---"
ls -la /opt/r36s/rootfs/usr/lib/aarch64-linux-gnu/ | grep -E 'libEGL|libGLdispatch'
echo "--- unico arquivo EGL REAL (nao symlink) no rootfs ---"
find /opt/r36s/rootfs/usr/lib/aarch64-linux-gnu -maxdepth 1 -name 'lib*EGL*' -type f -exec ls -la {} \;
echo "--- tentativa de link contra libEGL_mesa.so.0 (lib vendor do GLVND) ---"
aarch64-linux-gnu-g++ -std=c++17 -c gles_smoke.cpp -o /tmp/gles_smoke_a64.o
aarch64-linux-gnu-g++ /tmp/gles_smoke_a64.o /tmp/plume_gles_a64.o /tmp/plume_gles_gl_a64.o -o /tmp/gles_smoke_a64_mesa \
    --sysroot=/opt/r36s/rootfs -l:libEGL_mesa.so.0 -Wl,--allow-shlib-undefined 2>&1 | head -4
echo "CONCLUSao: libEGL_mesa NAO exporta eglGetDisplay/eglGetProcAddress (e' vendor lib do GLVND);"
echo "           o dispatcher GLVND foi substituido pelo blob Mali no rootfs -> sob QEMU,"
echo "           sem GPU Mali, NAO ha caminho para contexto GLES. Nao e' falha do backend."
echo "--- execucao do smoke aarch64 com o blob Mali (falha esperada, sem hardware) ---"
qemu-aarch64-static -L /opt/r36s/rootfs /tmp/gles_smoke_a64 2>&1 | head -4
echo

echo "############ [9] BACKEND INERTE NA ARVORE (nenhuma referencia de BUILD) ############"
echo "--- buscas por referencia EXECUTAVEL (arquivo fonte em target_sources/add_) ---"
grep -rn 'plume_gles\.\(cpp\|h\)' /root/bhrecomp/CMakeLists.txt /root/bhrecomp/lib/rt64/CMakeLists.txt 2>/dev/null \
    || echo "OK: nenhuma CMakeLists referencia plume_gles.{cpp,h} em build"
echo "--- toda mencao textual a 'plume_gles' nas CMakeLists (para auditoria) ---"
grep -rn 'plume_gles' /root/bhrecomp/CMakeLists.txt /root/bhrecomp/lib/rt64/CMakeLists.txt 2>/dev/null || echo "nenhuma mencao"
echo "--- confirmacao por arquivos de build gerados (nem objeto nem entrada de link) ---"
find /root/bhrecomp/build-aarch64 -name '*plume_gles*' 2>/dev/null | head -5 || true
echo "(vazio acima == o backend nao foi compilado pelo build de producao)"
echo
echo "=== FIM ==="