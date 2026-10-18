#!/bin/bash
# M1 - Restauracao dos 56 blobs SPIR-V DX-layout sobrescritos por m1_layout_matrix.sh
#
# Contexto do dano:
#   m1_layout_matrix.sh fazia `sed "s|-Fo \([^ ]*\)|-Fo $OUT/...|"` mas o comando DXC real
#   usa `/Fo <path>` (barra + ESPACO, dois tokens). O sed nunca casou, entao o DXC da
#   passada "gl" escreveu no caminho ORIGINAL, sobrescrevendo os 56 blobs DX-layout.
#
# Fonte de restauracao (pristine, pre-dano):
#   /root/bhrecomp/build-cmake  (build x86_64 de 2026-10-16 14:11, DXC -fvk-use-dx-layout)
#   Prova de equivalencia: RasterPSDynamic = d592de4472eee211c696407c669d6702
#   == backup DX independente /root/bhrecomp/m1_fix/RasterPSDynamic.dx.spv
#   (DXC gera SPIR-V identico independente da arquitetura-alvo do build.)
#
# Este script faz copia 1:1 (preserva md5), guarda backup dos danificados e verifica layout.
set -u

SRC=/root/bhrecomp/build-cmake
DST=/root/bhrecomp/build-aarch64
BK=/root/bhrecomp/m1_restore
mkdir -p "$BK/damaged_gl"

RES="$BK/restore.tsv"
: > "$RES"
printf 'rel\tmd5_src\tmd5_dst\tstatus\n' > "$RES"

# ---------------------------------------------------------------- 1) backup danificado
nbk=0
for d in "src/shaders" "shaders"; do
  [ -d "$DST/$d" ] || continue
  for f in "$DST/$d"/*.spv; do
    [ -e "$f" ] || continue
    tag=$(printf '%s' "$d" | tr '/' '_')
    cp -f "$f" "$BK/damaged_gl/${tag}__$(basename "$f")" 2>/dev/null && nbk=$((nbk + 1))
  done
done
echo "backup dos danificados: $nbk arquivos em $BK/damaged_gl"

# ---------------------------------------------------------------- 2) restauracao 1:1
ok=0; miss=0; badd=0
for d in "src/shaders" "shaders"; do
  for s in "$SRC/$d"/*.spv; do
    [ -e "$s" ] || continue
    n=$(basename "$s")
    t="$DST/$d/$n"
    if [ ! -e "$t" ]; then
      printf '%s\t-\t-\tMISSING_DST\n' "$d/$n" >> "$RES"
      miss=$((miss + 1))
      continue
    fi
    ms=$(md5sum "$s" | awk '{print $1}')
    cp -f "$s" "$t"
    mt=$(md5sum "$t" | awk '{print $1}')
    if [ "$ms" = "$mt" ]; then st=OK; ok=$((ok + 1)); else st=DIVERGE; badd=$((badd + 1)); fi
    printf '%s\t%s\t%s\t%s\n' "$d/$n" "$ms" "$mt" "$st" >> "$RES"
  done
done

echo "=== RESTORE ==="
echo "restaurados OK   : $ok"
echo "destino ausente  : $miss"
echo "divergentes      : $badd"
echo "--- linhas com status != OK ---"
awk -F'\t' 'NR>1 && $4!="OK"' "$RES"

# ---------------------------------------------------------------- 3) verificacao estrutural
echo "=== VERIFY: contagem de blobs por diretorio ==="
for d in "src/shaders" "shaders"; do
  printf '%-14s src=%-3s dst=%-3s\n' "$d" \
    "$(ls "$SRC/$d"/*.spv 2>/dev/null | wc -l)" \
    "$(ls "$DST/$d"/*.spv 2>/dev/null | wc -l)"
done

echo "=== VERIFY: conjunto de nomes identico? ==="
cd /root/bhrecomp
ls "$SRC/src/shaders"/*.spv 2>/dev/null | xargs -n1 basename | sort > "$BK/names_src.txt"
ls "$DST/src/shaders"/*.spv 2>/dev/null | xargs -n1 basename | sort > "$BK/names_dst.txt"
diff "$BK/names_src.txt" "$BK/names_dst.txt" >/dev/null 2>&1 && echo "src/shaders: nomes IDENTICOS" || { echo "src/shaders: DIVERGENCIA de nomes:"; diff "$BK/names_src.txt" "$BK/names_dst.txt"; }

echo "=== VERIFY: layout DX autoritativo (spirv-dis) do RasterPSDynamic ==="
echo "--- esperado: keyScale off=92 (nao 96), ArrayStride 128 (nao 144) ---"
spirv-dis "$DST/src/shaders/RasterPSDynamic.hlsl.spv" 2>/dev/null \
  | grep -nE 'Offset (8[0-9]|9[0-9])|ArrayStride (12[0-9]|14[0-9])|"keyScale"' | head -20

echo "=== VERIFY: md5 global do conjunto (src/shaders) ==="
( cd "$DST/src/shaders" && md5sum *.spv | sort -k2 ) | md5sum
( cd "$SRC/src/shaders" && md5sum *.spv | sort -k2 ) | md5sum
echo "(as duas linhas acima devem ser IGUAIS)"
echo "resultados: $RES"