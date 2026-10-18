#!/bin/bash
# M1 - matriz de layout DX vs GL (medicao autoritativa)
# Para CADA comando DXC do build.ninja, gera o SPIR-V em dois layouts:
#   dx = -fvk-use-dx-layout (atual do RT64)
#   gl = -fvk-use-gl-layout (candidato)
# e mede: rc DXC, conversao SPIRV-Cross -> GLSL ES 3.20, validacao glslangValidator.
set -u
cd /root/bhrecomp/build-aarch64 || exit 1
DXCDIR=/root/bhrecomp/lib/rt64/src/contrib/dxc
OUT=/root/bhrecomp/m1_layout_matrix
mkdir -p "$OUT"
rm -f "$OUT"/*.spv "$OUT"/*.log "$OUT"/*.vert "$OUT"/*.frag "$OUT"/*.comp "$OUT"/results.tsv
RES="$OUT/results.tsv"
printf 'shader\tstage\tdxc_dx\txc_dx\tglsl_dx\tdxc_gl\txc_gl\tglsl_gl\n' > "$RES"

ninja -t commands > "$OUT/ninja_cmds.txt" 2>/dev/null
grep 'dxc' "$OUT/ninja_cmds.txt" | grep '\.hlsl' > "$OUT/dxc_cmds.txt" || true
echo "comandos dxc encontrados: $(wc -l < "$OUT/dxc_cmds.txt")"

while IFS= read -r CMD; do
  [ -z "$CMD" ] && continue
  # normaliza escapes do ninja (ex.: '-T\ ps_6_3' -> '-T ps_6_3')
  CMDN=$(printf '%s' "$CMD" | sed 's/\\//g')
  SRC=$(printf '%s' "$CMDN" | awk '{print $NF}')
  NAME=$(basename "$SRC")
  STAGE=$(printf '%s' "$CMDN" | sed -n 's/.*-T \([a-z][a-z]_[0-9]_[0-9]\).*/\1/p')
  case "${STAGE%%_*}" in vs) EXT=vert ;; ps) EXT=frag ;; cs) EXT=comp ;; *) EXT=vert ;; esac
  BIN=$(printf '%s' "$CMDN" | awk '{print $1}')
  if printf '%s' "$BIN" | grep -q arm64; then
    export LD_LIBRARY_PATH="$DXCDIR/lib/arm64"
  else
    export LD_LIBRARY_PATH="$DXCDIR/lib/x64"
  fi

  ROW="$NAME	$STAGE"
  for L in dx gl; do
    if [ "$L" = dx ]; then C="$CMDN"; else C=$(printf '%s' "$CMDN" | sed 's/-fvk-use-dx-layout/-fvk-use-gl-layout/'); fi
    COUT=$(printf '%s' "$C" | sed "s|-Fo \([^ ]*\)|-Fo $OUT/$NAME.$L.spv|")
    eval "$COUT" > "$OUT/$NAME.$L.dxc.log" 2>&1
    RCD=$?
    if [ -s "$OUT/$NAME.$L.spv" ]; then
      spirv-cross "$OUT/$NAME.$L.spv" --es --version 320 --output "$OUT/$NAME.$L.$EXT" > "$OUT/$NAME.$L.xc.log" 2>&1
      RCX=$?
    else
      RCX=99
    fi
    RCG=99
    if [ "$RCX" = "0" ] && [ -s "$OUT/$NAME.$L.$EXT" ]; then
      glslangValidator -S "$EXT" "$OUT/$NAME.$L.$EXT" > "$OUT/$NAME.$L.glslang.log" 2>&1
      RCG=$?
    fi
    ROW="$ROW	$RCD	$RCX	$RCG"
  done
  printf '%s\n' "$ROW" >> "$RES"
done < "$OUT/dxc_cmds.txt"

echo '=== RESUMO ==='
awk -F'\t' 'NR>1{t++; if($4==0)o++; if($7==0)o2++; if($5==0)g++; if($8==0)g2++} END{printf "shaders=%d  converteDX=%d  converteGL=%d  compilaDX=%d  compilaGL=%d\n",t,o,o2,g,g2}' "$RES"
echo '=== FALHAS DX (xc!=0) ==='
awk -F'\t' 'NR>1 && $4!=0 {printf "%-34s stage=%-8s xc=%s\n",$1,$2,$4}' "$RES"
echo '=== FALHAS GL (xc!=0) ==='
awk -F'\t' 'NR>1 && $7!=0 {printf "%-34s stage=%-8s xc=%s\n",$1,$2,$7}' "$RES"
echo '=== FALHAS GLSLANG com layout GL (glsl!=0) ==='
awk -F'\t' 'NR>1 && $8!=0 {printf "%-34s stage=%-8s glslang=%s\n",$1,$2,$8}' "$RES"
cp "$RES" "$OUT/report.tsv"
echo "resultados: $RES"