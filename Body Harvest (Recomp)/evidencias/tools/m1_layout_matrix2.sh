#!/bin/bash
# M1 - Matriz de layout DX vs GL (medicao autoritativa) -- VERSAO 2 (corrigida)
#
# Correcoes em relacao ao v1 (m1_layout_matrix.sh):
#  1) O sed do v1 usava `-Fo \(...\)` (HIFEN) mas o comando DXC real usa `/Fo <path>`
#     (BARRA + ESPACO). O sed nunca casava, entao o DXC da passada "gl" escreveu no
#     caminho ORIGINAL e sobrescreveu os 58 blobs DX-layout (dano ja revertido, vide
#     evidencias/evidence_m1_restore_dx_blobs_20261018.md).
#     -> agora a substituicao usa `/Fo [^ ]*` e escreve SEMPRE em $OUT (scratch).
#  2) A fonte dos comandos agora e o proprio build.ninja (linha `COMMAND = ...`),
#     que e a fonte da verdade; `ninja -t commands <target>` retorna o comando C++
#     da dependencia quando um target e passado.
#  3) Guard de integridade: snapshot md5 dos blobs reais antes/depois.
set -u
cd /root/bhrecomp/build-aarch64 || exit 1

OUT=/root/bhrecomp/m1_layout_matrix2
rm -rf "$OUT"; mkdir -p "$OUT"
DXCDIR=/root/bhrecomp/lib/rt64/src/contrib/dxc
export LD_LIBRARY_PATH="$DXCDIR/lib/arm64"
T=$'\t'   # tab real (dentro de "...", \t seria literal)

# ---------------------------------------------------- guard: snapshot ANTES
snap() { ( cd /root/bhrecomp/build-aarch64 && md5sum src/shaders/*.spv shaders/*.spv 2>/dev/null | sort -k2 ); }
snap > "$OUT/md5_real_before.txt"
echo "blobs reais no snapshot: $(wc -l < "$OUT/md5_real_before.txt")"

# ---------------------------------------------------- extrai comandos do build.ninja
grep 'dxc-linux' build.ninja | sed 's/^ *COMMAND = //' > "$OUT/cmds_raw.txt"
N=$(wc -l < "$OUT/cmds_raw.txt")
echo "comandos DXC encontrados no build.ninja: $N"

RES="$OUT/results.tsv"
printf 'shader\tstage\tdxc_dx\tval_dx\txc_dx\tglsl_dx\tdxc_gl\tval_gl\txc_gl\tglsl_gl\n' > "$RES"
HAVE_VAL=0; command -v spirv-val >/dev/null 2>&1 && HAVE_VAL=1
echo "spirv-val disponivel: $HAVE_VAL"

while IFS= read -r RAW; do
  [ -z "$RAW" ] && continue
  CMD=$(printf '%s' "$RAW" | sed 's/\\//g')                       # remove escapes do ninja
  OUTPATH=$(printf '%s' "$CMD" | sed -n 's#.* /Fo \([^ ]*\)$#\1#p')
  if [ -z "$OUTPATH" ]; then echo "SKIP (sem /Fo no fim): $RAW" >&2; continue; fi
  NAME=$(basename "$OUTPATH")
  PROF=$(printf '%s' "$CMD" | sed -n 's/.*-T \([a-z][a-z]_[0-9]_[0-9]\).*/\1/p')
  case "${PROF%%_*}" in
    vs) EXT=vert ;; ps) EXT=frag ;; cs) EXT=comp ;; gs) EXT=geom ;; *) EXT=vert ;;
  esac

  ROW="$NAME${T}$PROF"
  for L in dx gl; do
    if [ "$L" = dx ]; then
      C=$(printf '%s' "$CMD" | sed "s#/Fo [^ ]*#/Fo $OUT/$NAME.dx.spv#")
    else
      C=$(printf '%s' "$CMD" \
          | sed 's/-fvk-use-dx-layout/-fvk-use-gl-layout/' \
          | sed "s#/Fo [^ ]*#/Fo $OUT/$NAME.gl.spv#")
    fi
    rm -f "$OUT/$NAME.$L.spv" "$OUT/$NAME.$L.$EXT"
    eval "$C" > "$OUT/$NAME.$L.dxc.log" 2>&1
    RCD=$?
    if [ ! -s "$OUT/$NAME.$L.spv" ]; then
      ROW="$ROW${T}$RCD${T}MISSING${T}99${T}99"; continue
    fi
    RCV=NA
    if [ "$HAVE_VAL" = 1 ]; then
      spirv-val --target-env vulkan1.0 "$OUT/$NAME.$L.spv" > "$OUT/$NAME.$L.val.log" 2>&1
      RCV=$?
    fi
    spirv-cross --es --version 320 "$OUT/$NAME.$L.spv" --output "$OUT/$NAME.$L.$EXT" > "$OUT/$NAME.$L.xc.log" 2>&1
    RCX=$?
    RCG=99
    if [ "$RCX" = 0 ] && [ -s "$OUT/$NAME.$L.$EXT" ]; then
      glslangValidator -S "$EXT" "$OUT/$NAME.$L.$EXT" > "$OUT/$NAME.$L.glslang.log" 2>&1
      RCG=$?
    fi
    ROW="$ROW${T}$RCD${T}$RCV${T}$RCX${T}$RCG"
  done
  printf '%s\n' "$ROW" >> "$RES"
done < "$OUT/cmds_raw.txt"

echo '=== RESUMO ==='
awk -F'\t' 'NR>1{t++; if($5==0)o++; if($9==0)o2++; if($6==0)g++; if($10==0)g2++} END{printf "shaders=%d  xcDX_ok=%d  xcGL_ok=%d  glslDX_ok=%d  glslGL_ok=%d\n",t,o,o2,g,g2}' "$RES"
echo '=== FALHAS DX (spirv-cross != 0) ==='
awk -F'\t' 'NR>1 && $5!=0 {printf "%-38s stage=%-8s dxc=%s xc=%s\n",$1,$2,$3,$5}' "$RES"
echo '=== FALHAS GL (spirv-cross != 0) ==='
awk -F'\t' 'NR>1 && $9!=0 {printf "%-38s stage=%-8s dxc=%s xc=%s\n",$1,$2,$7,$9}' "$RES"
echo '=== FALHAS glslang com layout GL ==='
awk -F'\t' 'NR>1 && $10!=0 {printf "%-38s stage=%-8s glsl=%s\n",$1,$2,$10}' "$RES"
echo '=== PRIMEIRO ERRO DX (exemplo) ==='
f=$(awk -F'\t' 'NR>1 && $5!=0 {print $1".dx.xc.log"; exit}' "$RES")
if [ -n "${f:-}" ] && [ -f "$OUT/$f" ]; then echo "--- $f ---"; head -6 "$OUT/$f"; fi

# ---------------------------------------------------- guard: snapshot DEPOIS
snap > "$OUT/md5_real_after.txt"
if diff -q "$OUT/md5_real_before.txt" "$OUT/md5_real_after.txt" >/dev/null 2>&1; then
  echo "### SAFETY OK: blobs reais em build-aarch64 INTACTOS (md5 identico antes/depois)"
else
  echo "### SAFETY FAIL: blobs reais ALTERADOS pelo run!"
  diff "$OUT/md5_real_before.txt" "$OUT/md5_real_after.txt"
fi
echo "results: $RES"