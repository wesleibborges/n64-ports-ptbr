#!/bin/bash
# M3 -- gera os CASOS DE SHADER de producao (par VS+PS real) usados pela sonda [9c].
#
# Fonte: o ESSL que o M1.3 gera (`evidencias/m1_3_stage2/essl/`). O PS do raster dinamico e' o
# artefato que MEDE o M3: 20 arrays de `sampler2D[8192]` indexadas por `GPUTiles._m0[..].textureIndex`
# (indice dinamico). O VS parceiro existe porque o orcamento de samplers e' verificado no LINK.
#
# Casos gerados (todos com o MESMO VS parceiro, `prod_*.vert.essl`):
#   prod_asis          -- PS como o M1.3 gera (20 x 8192): controle "como esta'
#   prod_spec1x_n8192  -- combos colapsados em 1 array/imagem, janela mantida (8192)
#   prod_spec1x_n32    -- idem, janela 32 (= GL_MAX_TEXTURE_IMAGE_UNITS do llvmpipe)
#   prod_spec1x_n16    -- idem, janela 16 (metade do limite: sobra para uma 2a array)
#
# Uso: bash m3_make_shader_cases.sh
set -u

PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"
E="$PROJ/evidencias/m1_3_stage2/essl"
OUT="$PROJ/evidencias/m3_gles_probe/shader_cases"
TOOL="$PROJ/evidencias/tools/m3_essl_specialize.py"

# `prod_asis` = forma do M1.3; `prod_spec1x_nN` = combos colapsados com a janela do M3 em N.
# N=32/16/15/8/4 cerca o ORCAMENTO MEDIDO (llvmpipe: 32 unidades). O shader real tem, alem das 2
# arrays com janela, 1 sampler escalar (`gBackgroundDepth`), logo a regra e' 2N+1 <= 32 -> N <= 15.
CASES="prod_asis prod_spec1x_n8192 prod_spec1x_n32 prod_spec1x_n16 prod_spec1x_n15 prod_spec1x_n8 prod_spec1x_n4"
WINDOWS="8192 32 16 15 8 4"

mkdir -p "$OUT" || exit 1
echo "=== M3 | casos de shader de PRODUCAO (par VS+PS real) ==="
echo "data_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "src=$E"
echo "out=$OUT"
echo

echo "--- [1] PS de producao: as-is + variantes especializadas (colapso de combos + janela N) ---"
python3 "$TOOL" --in "$E/RasterPSDynamic.essl" --out "$OUT/prod_asis.frag.essl" \
    --enable-extension GL_EXT_blend_func_extended
echo "linhas do as-is que diferem do artefato do M1.3 (esperado: 1 = o #extension):"
diff "$E/RasterPSDynamic.essl" "$OUT/prod_asis.frag.essl" | grep -c '^[<>]'
echo
for n in $WINDOWS; do
    python3 "$TOOL" --in "$E/RasterPSDynamic.essl" \
        --out "$OUT/prod_spec1x_n$n.frag.essl" --collapse-samplers --window "$n" \
        --enable-extension GL_EXT_blend_func_extended
    echo
done

echo "--- [2] VS parceiro (mesma base: o link e' que verifica o orcamento de samplers) ---"
for ps in $CASES; do
    python3 "$TOOL" --in "$E/RasterVSDynamic.essl" --out "$OUT/$ps.vert.essl" \
        --flat-from-ps "$OUT/$ps.frag.essl"
    echo
done

echo "--- [3] auditoria dos casos ---"
for f in "$OUT"/prod_*.frag.essl; do
    printf '%-28s decls_sampler=%-3s ocorrencias_8192=%-3s md5=%s\n' \
        "$(basename "$f")" \
        "$(grep -cE '^uniform .*sampler.*\[[0-9]+\];' "$f")" \
        "$(grep -c '8192' "$f")" \
        "$(md5sum "$f" | cut -d' ' -f1)"
done
echo '--- declaracoes de sampler que sobraram em cada caso ---'
for f in "$OUT"/prod_*.frag.essl; do
    echo "### $(basename "$f")"
    grep -nE '^uniform .*sampler.*\[[0-9]+\];' "$f" | sed 's/^/    /'
done
echo

echo '--- [3b] VS parceiro: diff vs artefato do M1.3 (esperado: 1 linha, o `flat` no out) ---'
diff "$E/RasterVSDynamic.essl" "$OUT/prod_asis.vert.essl"
echo '--- declaracoes out do VS gerado ---'
grep -nE '^layout\(location = [0-9]+\)( flat)? out ' "$OUT/prod_asis.vert.essl" | sed 's/^/    /'
echo

echo "--- [4] prova mecanica: o CORPO do shader NAO muda (so' nome de sampler e janela) ---"
# Normalizacao: tira as declaracoes de sampler, depois apaga distincao entre combos (nome -> SAMPLER)
# e entre janelas ([N] -> [N]). Se o corpo tiver sido tocado, o diff aparece aqui.
normalize() {
    grep -vE '^uniform .*sampler.*\[[0-9]+\];' "$1" \
        | sed -E 's/SPIRV_Cross_Combinedg[A-Za-z0-9_]*Sampler/SAMPLER/g
                  s/SAMPLER_[UI]/SAMPLER/g
                  s/\[[0-9]+\]/[N]/g'
}
normalize "$OUT/prod_asis.frag.essl" > /tmp/m3_norm_asis.txt
printf 'normalizado as-is   linhas=%s md5=%s\n' \
    "$(wc -l < /tmp/m3_norm_asis.txt)" "$(md5sum /tmp/m3_norm_asis.txt | cut -d' ' -f1)"
for n in 8192 32 16; do
    normalize "$OUT/prod_spec1x_n$n.frag.essl" > "/tmp/m3_norm_n$n.txt"
    printf 'normalizado n%-5s linhas=%s divergencias_vs_asis=%s md5=%s\n' "$n" \
        "$(wc -l < "/tmp/m3_norm_n$n.txt")" \
        "$(diff /tmp/m3_norm_asis.txt "/tmp/m3_norm_n$n.txt" | wc -l)" \
        "$(md5sum "/tmp/m3_norm_n$n.txt" | cut -d' ' -f1)"
done
echo
echo "=== fim ==="