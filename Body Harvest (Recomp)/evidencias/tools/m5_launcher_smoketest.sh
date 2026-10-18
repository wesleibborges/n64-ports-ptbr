#!/bin/bash
# M5-GLES -- smoketest OFFLINE do bloco de backend do BodyHarvest.sh.
#
# Nao precisa do R36S: prova a logica de estados do launcher (o que o device vai
# executar) num sandbox, com HOME/port_dir temporarios e o binario substituido por
# um stub. Cobre os 4 casos que importam:
#   A) sem BH_GLES            -> vulkan/auto, api_option=Auto
#   B) BH_GLES=1              -> OpenGL ES, api_option=GLES (nas DUAS copias)
#   C) BH_GLES=1 e depois sem -> reverte api_option=GLES -> Auto (senao o boot quebra)
#   D) BH_GRAPHICS_API=gles sem BH_GLES=1 -> avisa e IGNORA (evita janela GL + Vulkan)
#
# Uso: bash m5_launcher_smoketest.sh
set -u
SRC="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"
BASE=/tmp/bh_m5_smoke
FAIL=0

prep() { # $1 = nome do cenario
  SB="$BASE/$1"
  rm -rf "$SB"
  mkdir -p "$SB/port/gamedata" "$SB/home"
  cp "$SRC/BodyHarvest.sh" "$SB/port/"
  cp "$SRC/graphics.json.auto" "$SRC/graphics.json.gles" "$SB/port/"
  cp "$SRC/graphics.json.auto" "$SB/port/graphics.json"
  printf '#!/bin/sh\necho "[stub] binario executado"\n' > "$SB/port/BodyHarvestRecompiled"
  chmod +x "$SB/port/BodyHarvestRecompiled"
}

run() { # $1 = BH_GLES (opcional) | $2 = BH_GRAPHICS_API (opcional)
  # NAO usar "$@" como prefixo de env: um assignment vindo de expansao nao e'
  # reconhecido como assignment pelo bash (vira um ARGUMENTO de `bash`), entao o
  # script nunca executava. Parametros nomeados, aplicados aqui, sao deterministicos.
  ( cd "$SB/port" \
      && HOME="$SB/home" SDL_VIDEODRIVER=dummy \
         BH_GLES="${1:-}" BH_GRAPHICS_API="${2:-}" \
         bash ./BodyHarvest.sh ) >/dev/null 2>&1
  sleep 1  # o log.txt e' escrito por um `tee` (process substitution): da' tempo ao flush
}

check() { # $1 = rotulo, $2 = arquivo, $3 = texto esperado (literal: -F)
  if grep -qF -- "$3" "$2" 2>/dev/null; then
    echo "  OK   $1: '$3'"
  else
    echo "  FALHA $1: esperado '$3' em $2"
    FAIL=$((FAIL+1))
  fi
}

echo "=== A) sem BH_GLES (estado de fabrica) ==="
prep A; run
check "A log" "$SB/port/log.txt" "backend grafico: vulkan/auto"
check "A api_option" "$SB/port/graphics.json" '"api_option": "Auto"'
if [ -e "$SB/home/.config/bhrecomp/graphics.json" ]; then
  echo "  FALHA A fallback: NAO deveria existir em modo normal"
  FAIL=$((FAIL+1))
else
  echo "  OK   A fallback: nao criado em modo normal (so' sob demanda)"
fi

echo "=== B) BH_GLES=1 ==="
prep B; run 1
check "B log" "$SB/port/log.txt" "backend grafico: OpenGL ES 3.2"
check "B BH_GRAPHICS_API" "$SB/port/log.txt" "BH_GRAPHICS_API=gles"
check "B api_option port_dir" "$SB/port/graphics.json" '"api_option": "GLES"'
check "B api_option fallback" "$SB/home/.config/bhrecomp/graphics.json" '"api_option": "GLES"'
check "B log le de volta" "$SB/port/log.txt" "api_option[$SB/home/.config/bhrecomp/graphics.json] = \"api_option\": \"GLES\""

echo "=== C) BH_GLES=1 seguido de execucao normal (revert) ==="
prep C; run 1; run
check "C log" "$SB/port/log.txt" "revertendo api_option=GLES"
check "C api_option port_dir" "$SB/port/graphics.json" '"api_option": "Auto"'
check "C fallback" "$SB/home/.config/bhrecomp/graphics.json" '"api_option": "Auto"'

echo "=== D) BH_GRAPHICS_API=gles sem BH_GLES=1 ==="
prep D; run "" gles
check "D aviso" "$SB/port/log.txt" "sem BH_GLES=1 -- ignorado"
check "D api_option" "$SB/port/graphics.json" '"api_option": "Auto"'

echo "=== E) sintaxe do launcher ==="
if bash -n "$SRC/BodyHarvest.sh"; then echo "  OK   bash -n BodyHarvest.sh"; else echo "  FALHA bash -n"; FAIL=$((FAIL+1)); fi

echo "RESUMO SMOKETEST: falhas=$FAIL"
exit $((FAIL > 0))