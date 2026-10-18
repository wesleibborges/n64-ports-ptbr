#!/bin/bash
# M5-GLES -- verificacao CIRURGICA do gate OFF.
#
# O M2 provou o invariante no BINARIO INTEIRO (gate OFF => 0 simbolo/string GLES).
# Rebuildar tudo com OFF custa um rebuild completo; como TODO o codigo do M5 esta'
# dentro de `#ifdef RT64_GLES_BACKEND` em 3 translation units (+ 1 header incluido por
# uma delas), a prova equivalente e' recompilar EXATAMENTE esses TUs sem o define e
# medir os objetos resultantes:
#
#   renderer_context.cpp.o     -> enum/NLOHMANN do config.hpp + nome da API
#   ui_config_tab_graphics.cpp -> ALLOW_GLES + entrada "GLES" no vetor de opcoes
#   rt64_render_context.cpp    -> cases do switch e do map_graphics_api
#
# A linha de comando e' extraida do proprio build.ninja (nada de reconstruir flags a
# mao) e so' sofre 3 alteracoes: tira -DRT64_GLES_BACKEND e desvia -o/-MF para o tmp
# (para nao sujar o build real).
#
# Uso: bash m5_gate_off_tu_check.sh
set -u
WORK=/root/bhrecomp/m5_gles_api_select_20261018
VOL=/root/bhrecomp/build-aarch64
TMP="$WORK/nogate"
mkdir -p "$TMP"
FAIL=0

check_one() { # $1 = caminho do .o (relativo ao build dir) | $2 = apelido
  rel=$1; name=$2
  # `ninja -t commands <alvo>` imprime a CADEIA inteira de dependencias (para os TUs do
  # recompui a 1a linha e' o tool host file_to_c). Seleciona a linha que realmente
  # compila ESTE objeto: a que contem "-o <rel>".
  ninja -C "$VOL" -t commands "$rel" | grep -F -- "-o $rel" | head -1 > "$TMP/cmd_$name.txt"
  if [ ! -s "$TMP/cmd_$name.txt" ]; then
    echo "  FALHA: nenhuma linha de compilacao com -o $rel"
    FAIL=$((FAIL+1))
    return
  fi
  cmd=$(sed -E \
          -e 's/ -DRT64_GLES_BACKEND//' \
          -e "s#-o [^ ]*$rel#-o $TMP/$name.o#" \
          -e "s#-MF [^ ]*#-MF $TMP/$name.o.d#" \
          "$TMP/cmd_$name.txt")
  echo "--- $name ---"
  if ! ( cd "$VOL" && eval "$cmd" ) > "$TMP/build_$name.log" 2>&1; then
    echo "  FALHA compilacao (ver $TMP/build_$name.log)"
    tail -3 "$TMP/build_$name.log"
    FAIL=$((FAIL+1))
    return
  fi
  [ -f "$TMP/$name.o" ] || { echo "  FALHA objeto nao gerado"; FAIL=$((FAIL+1)); return; }
  n=$(strings -a "$TMP/$name.o" | grep -c 'GLES' || true)
  s=$(nm -C "$TMP/$name.o" 2>/dev/null | grep -ci 'gles' || true)
  echo "  $name.o  strings-GLES=$n simbolos-GLES=$s  (esperado 0/0)"
  if [ "$n" != "0" ] || [ "$s" != "0" ]; then
    echo "  FALHA: gate OFF vazou GLES para este TU"
    strings -a "$TMP/$name.o" | grep 'GLES' | head -5
    FAIL=$((FAIL+1))
  fi
}

check_one lib/N64ModernRuntime/ultramodern/CMakeFiles/ultramodern.dir/src/renderer_context.cpp.o ultramodern_renderer_context
check_one lib/RecompFrontend/recompui/CMakeFiles/recompui.dir/src/config/ui_config_tab_graphics.cpp.o recompui_ui_graphics
check_one lib/RecompFrontend/recompui/CMakeFiles/recompui.dir/src/renderer/rt64_render_context.cpp.o recompui_rt64_rc

echo "RESUMO GATE-OFF (TU): falhas=$FAIL"
exit $((FAIL > 0))