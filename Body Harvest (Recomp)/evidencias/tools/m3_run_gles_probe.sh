#!/bin/sh
# run_gles_probe.sh -- executa as sondas GLES do R36S e deixa tudo em gles_probe_log.txt
#
# NAO precisa de SDL, nem do port, nem da pasta libs/: as duas sondas resolvem EGL/GLES em
# runtime (dlopen). Rode de DENTRO da pasta onde estao os binarios.
#
#   cd <pasta_descompactada>
#   sh run_gles_probe.sh
#
# Melhor rodar do console (fora do EmulationStation): o probe abre /dev/dri/card0 e o SDL do
# ES pode estar com o DRM master. Se gbm_device falhar, o script JA' repete sozinho com
# --no-gbm (EGL_DEFAULT_DISPLAY puro) -- e' o caminho do SDL sem KMS/DRM livre.
#
# O probe cobre DUAS coisas: o aceite do M2 (contexto ES 3.2 real + clear/readback) e a
# MEDICAO do M3 (secao [9]: compilar/linkar sampler array -- a forma atual do M1.3, a janela
# de N, o orcamento multiplicativo). A secao [9] tem `timeout 180` por causa dos casos de
# 163.840 samplers, que sao justamente a forma que o port gera hoje.
# A secao [9c] faz o mesmo com o ESSL DE PRODUCAO (pares VS+PS em `shader_cases/`, colocado por
# PROBE_SHADER_DIR abaixo): e' o unico teste que mede o orcamento de samplers sobre o artefato
# REAL que o build do M1.3 gera, no COMPILADOR DO MALI.
#
# Saida: gles_probe_log.txt (anexe esse arquivo no ticket).

LOG=gles_probe_log.txt
: > "$LOG"

# Os casos [9c] ficam ao lado deste script (a pasta `shader_cases/` do pacote). O probe tambem
# aceita `--shader-dir DIR`; via ambiente funciona para a 1a rodada e para o fallback [1b].
DIR=$(cd "$(dirname "$0")" && pwd)
if [ -d "$DIR/shader_cases" ]; then
    PROBE_SHADER_DIR="$DIR/shader_cases"
    export PROBE_SHADER_DIR
fi

emit() { echo "$@" | tee -a "$LOG"; }

emit "============================================================"
emit " run_gles_probe -- sondas GLES nativas (M3) -- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
emit "============================================================"

# --- ambiente: NAO herdar LD_LIBRARY_PATH do launcher do port (pode ter um libEGL.so.1 estranho)
unset LD_LIBRARY_PATH
emit "[env] LD_LIBRARY_PATH=<vazio de proposito>"

emit "[env] uname: $(uname -a)"
if [ -r /etc/os-release ]; then
    emit "[env] os: $(grep -E '^PRETTY_NAME' /etc/os-release | cut -d= -f2-)"
fi
emit "[env] /dev/dri:"; ls -la /dev/dri 2>&1 | tee -a "$LOG"
if [ -r /dev/dri/card0 ]; then
    emit "[env] /dev/dri/card0: legivel"; else emit "[env] /dev/dri/card0: AUSENTE/ilegivel"; fi

# --- que libEGL o loader resolve de fato? (prova de que NAO ha stub no caminho)
# `ldd` e' a prova mais direta: mostra o caminho REAL que o device usara.
# Usa-se o gles_smoke_aarch64 (e nao o probe) porque ELE tem DT_NEEDED libEGL.so.1 -- o
# probe, por desenho, nao linka EGL (tudo por dlopen) e portanto nao aparece no ldd.
emit "[env] resolucao do loader (prova de que NAO ha stub):"
if command -v ldd >/dev/null 2>&1; then
    ldd ./gles_smoke_aarch64 2>&1 | sed 's/^/    /' | tee -a "$LOG"
else
    for lib in libEGL.so.1 libGLESv2.so.2 libgbm.so.1; do
        emit "    $lib -> $(ldconfig -p 2>/dev/null | grep -F "$lib " | head -1 | sed 's/^[[:space:]]*//')"
    done
fi
emit "[env] ldconfig (filtrado):"
( ldconfig -p 2>/dev/null | grep -iE 'libEGL|libGLESv2|libgbm|libmali' ) | tee -a "$LOG"

# --- sonda 1: gles_device_probe (EGL/GLES/GBM + extensoes + limites + readback)
emit ""
emit "============================================================"
emit " [1] gles_device_probe_aarch64"
emit "============================================================"
if [ -x ./gles_device_probe_aarch64 ]; then
    # `timeout` e' protecao real: a secao [9] manda o compilador do Mali linkar shaders com
    # ate' 163.840 samplers (a forma do M1.3); um driver que trave ali travaria o teste todo.
    PROBE_TMP=./.gles_probe_tmp.txt
    if command -v timeout >/dev/null 2>&1; then
        timeout 180 ./gles_device_probe_aarch64 > "$PROBE_TMP" 2>&1; probe_rc=$?
    else
        ./gles_device_probe_aarch64 > "$PROBE_TMP" 2>&1; probe_rc=$?
    fi
    cat "$PROBE_TMP" | tee -a "$LOG"
    emit "[1] exit=$probe_rc"
    # Fallback: se o caminho GBM nao abriu display, repete com EGL_DEFAULT_DISPLAY puro -- e'
    # o caminho que o SDL usa quando nao ha KMS/DRM livre (ex.: EmulationStation no controle).
    if grep -qE 'result=FAIL \((sem display|eglInitialize|eglChooseConfig|pbuffer|contexto)|gbm_device=FALHOU|display_path=none' "$PROBE_TMP"; then
        emit ""
        emit "[1b] GBM/display nao abriu -> repetindo com --no-gbm (EGL_DEFAULT_DISPLAY puro)"
        if command -v timeout >/dev/null 2>&1; then
            timeout 180 ./gles_device_probe_aarch64 --no-gbm > "$PROBE_TMP" 2>&1; probe_rc=$?
        else
            ./gles_device_probe_aarch64 --no-gbm > "$PROBE_TMP" 2>&1; probe_rc=$?
        fi
        cat "$PROBE_TMP" | tee -a "$LOG"
        emit "[1b] exit=$probe_rc"
    fi
    rm -f "$PROBE_TMP"
else
    emit "[1] BINARIO AUSENTE"
fi

# --- sonda 2: gles_smoke (o backend plume_gles sobre o driver REAL: 15 checagens do M2)
emit ""
emit "============================================================"
emit " [2] gles_smoke_aarch64 (backend plume_gles no driver real)"
emit "============================================================"
if [ -x ./gles_smoke_aarch64 ]; then
    ./gles_smoke_aarch64 2>&1 | tee -a "$LOG"
    emit "[2] exit=$?"
else
    emit "[2] BINARIO AUSENTE"
fi

# --- resumo automatico (as linhas que interessam)
emit ""
emit "============================================================"
emit " RESUMO"
emit "============================================================"
emit "checks: $(grep -c 'PROBE check=' "$LOG" | tr -d ' ') | linhas FALHOU: $(grep -c 'FALHOU' "$LOG" | tr -d ' ')"
# TODAS as linhas de resultado (probe + smoke): com o fallback [1b] o probe pode emitir
# DUAS, e um `tail -1` faria o resumo mostrar so' o resultado do smoke.
result_lines=$(grep -E 'PROBE result=' "$LOG")
emit "results (na ordem do log):"
emit "$result_lines"
# Os greps leem o proprio log: guardar em variavel ANTES de fazer tee (evita realimentacao).
info_lines=$(grep -E 'PROBE (gl_version|gl_renderer|gl_vendor|display_path|libEGL_path|gl_extensions_count)=' "$LOG")
ext_lines=$(grep -E '^PROBE +GL_(ARM|EXT|OES|KHR)[A-Za-z0-9_]* +(PRESENTE|AUSENTE)' "$LOG")
limit_lines=$(grep -E '^PROBE +GL_MAX_(TEXTURE_IMAGE_UNITS|COMBINED_TEXTURE_IMAGE_UNITS|VERTEX_TEXTURE_IMAGE_UNITS|UNIFORM_BUFFER_BINDINGS|SHADER_STORAGE_BUFFER_BINDINGS) ' "$LOG")
m3_lines=$(grep -E 'compile=(ok|FALHOU)' "$LOG")
m3_verdict=$(grep -E '^PROBE +[a-z0-9_]+ +(COMPILA|NAO_COMPILA)$' "$LOG")
file_lines=$(grep -E '^PROBE +prod_[A-Za-z0-9_]+ +compile=' "$LOG")
blend_line=$(grep -E '^PROBE +GL_EXT_blend_func_extended ' "$LOG")
emit "$info_lines"
emit "$ext_lines"
emit "--- limites relevantes ao M3 ---"
emit "$limit_lines"
emit "--- M3: sampler array (forma atual do M1.3 x janela de N) ---"
emit "$m3_lines"
emit "$m3_verdict"
emit "--- M3/9c: ESSL DE PRODUCAO (par VS+PS real) no compilador do Mali ---"
emit "$file_lines"
emit "--- extensao que o PS de producao usa (index=1, dual-source) ---"
emit "$blend_line"
emit ""
emit "log completo em: $LOG"