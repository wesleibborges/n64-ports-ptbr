#!/bin/bash
# M2/s2 -- espelha os artefatos e a evidencia para o diretorio de evidencias do projeto.
# Existe como script porque o executor de comandos remove variaveis de shell ($VAR) da
# linha de comando; dentro de um arquivo elas funcionam normalmente.
set -eu

D='/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias'
P=/root/bhrecomp/lib/rt64/src/contrib/plume
M=/root/bhrecomp/m2_gles

mkdir -p "$D/m2_gles_s2"

# Evidencia RAW da sessao.
cp "$M/s2_verify_raw.txt" "$D/m2_gles_s2/verify_raw.txt"

# Fontes de producao (as que vivem na arvore do rt64).
cp "$P/plume_gles.h"          "$D/tools/staged/plume_gles.h"
cp "$P/plume_gles.cpp"        "$D/tools/staged/plume_gles.cpp"
cp "$P/gles_smoke.cpp"        "$D/tools/staged/gles_smoke.cpp"
cp "$P/gles_target_probe.cpp" "$D/tools/staged/gles_target_probe.cpp"

# Ferramentas de aplicacao/verificacao.
cp "$M/apply_s2.py" "$D/tools/staged/apply_s2.py"
cp "$M/verify_s2.sh" "$D/tools/staged/verify_s2.sh"

# Copias arquivadas dentro do pacote de evidencia da sessao.
cp "$P/plume_gles.h" "$P/plume_gles.cpp" "$P/gles_smoke.cpp" "$P/gles_target_probe.cpp" \
   "$M/staged/plume_gles_s2_inc.inc" "$M/s2_verify_raw.txt" "$D/m2_gles_s2/"

# Backups do estado anterior (s1), para auditoria de "antes/depois".
cp "$M/s1_backup/plume_gles.h.s1"   "$D/m2_gles_s2/plume_gles.h.s1"
cp "$M/s1_backup/plume_gles.cpp.s1" "$D/m2_gles_s2/plume_gles.cpp.s1"

echo "=== MIRROR OK ==="
ls -la "$D/m2_gles_s2/"
echo
echo "=== HASHES: producao == evidencia ==="
for f in plume_gles.h plume_gles.cpp gles_smoke.cpp gles_target_probe.cpp; do
    printf '%-24s prod=%s  evid=%s\n' "$f" \
        "$(md5sum "$P/$f" | cut -d' ' -f1)" \
        "$(md5sum "$D/m2_gles_s2/$f" | cut -d' ' -f1)"
done
printf '%-24s                  evid=%s\n' "verify_raw.txt" "$(md5sum "$D/m2_gles_s2/verify_raw.txt" | cut -d' ' -f1)"
printf '%-24s                  evid=%s\n' "plume_gles_s2_inc.inc" "$(md5sum "$D/m2_gles_s2/plume_gles_s2_inc.inc" | cut -d' ' -f1)"