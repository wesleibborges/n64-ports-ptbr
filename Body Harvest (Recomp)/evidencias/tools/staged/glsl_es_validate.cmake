# M1-GLES -- valida o conjunto ESSL 3.20 produzido pelo canal GLES (M1.2).
#
# Pipeline por shader (mesmo do M1.1, aqui em CMake para nao depender de host tool
# cross-compilado):  .glsl_es.spv --spirv-cross--> .raw --sanitize--> .glsl
#                   --glslangValidator -S <stage>--> rc=0
#
# Entradas (via -D):
#   MAP_FILE      <build>/glsl_es_stages.txt  (linhas "<spv> <stage>")
#   SANITIZE_FILE src/tools/glsl_es_sanitize.cmake
#   SPIRV_CROSS   caminho do spirv-cross (host)
#   GLSLLANG      caminho do glslangValidator (host)
#   SKIP_LIST     shaders fora do conjunto (ex: DebugPS -- caminho RT)
#
# Falha com FATAL_ERROR se qualquer shader nao compilar em ESSL 3.20.

if (NOT DEFINED MAP_FILE OR NOT DEFINED SANITIZE_FILE)
    message(FATAL_ERROR "MAP_FILE e SANITIZE_FILE sao obrigatorios.")
endif()

include("${SANITIZE_FILE}")

if (NOT DEFINED SKIP_LIST)
    set(SKIP_LIST "")
endif()

file(STRINGS "${MAP_FILE}" _entries)

set(_total 0)
set(_ok 0)
set(_skipped 0)
set(_failed 0)
set(_missing 0)
set(_fail_msgs "")

foreach (_line IN LISTS _entries)
    string(STRIP "${_line}" _line)
    if (_line STREQUAL "")
        continue()
    endif()
    string(REGEX MATCH "^([^ ]+) *([^ ]*)$" _m "${_line}")
    set(_spv "${CMAKE_MATCH_1}")
    set(_stage "${CMAKE_MATCH_2}")
    if (_stage STREQUAL "")
        set(_stage "frag")
    endif()

    get_filename_component(_name "${_spv}" NAME)
    math(EXPR _total "${_total} + 1")

    set(_skip FALSE)
    foreach (_s IN LISTS SKIP_LIST)
        if (_name MATCHES "^${_s}")
            set(_skip TRUE)
        endif()
    endforeach()
    if (_skip)
        math(EXPR _skipped "${_skipped} + 1")
        continue()
    endif()

    string(REPLACE ".glsl_es.spv" ".glsl_es" _glsl "${_spv}")
    set(_raw "${_glsl}.raw")

    # Shaders declarados por outro alvo do build (ex: os do frontend/recompui) entram
    # neste mapa por reusarem as funcoes de shader do RT64, mas podem ainda nao ter
    # sido construidos quando o alvo de validacao roda. Nao e falha: sao reportados.
    if (NOT EXISTS "${_spv}")
        math(EXPR _missing "${_missing} + 1")
        message(STATUS "M1.2 GLES: ausente (ainda nao construido, fora deste alvo): ${_name}")
        continue()
    endif()

    execute_process(COMMAND "${SPIRV_CROSS}" --es --version 320 "${_spv}" --output "${_raw}"
        RESULT_VARIABLE _rc_xc OUTPUT_VARIABLE _out_xc ERROR_VARIABLE _err_xc)
    if (NOT _rc_xc EQUAL 0)
        math(EXPR _failed "${_failed} + 1")
        string(APPEND _fail_msgs "\n  ${_name}: spirv-cross rc=${_rc_xc} ${_err_xc}")
        continue()
    endif()

    glsl_es_sanitize_file("${_raw}" "${_glsl}")

    execute_process(COMMAND "${GLSLLANG}" -S "${_stage}" "${_glsl}"
        RESULT_VARIABLE _rc_gl OUTPUT_VARIABLE _out_gl ERROR_VARIABLE _err_gl)
    if (NOT _rc_gl EQUAL 0)
        math(EXPR _failed "${_failed} + 1")
        string(APPEND _fail_msgs "\n  ${_name} (${_stage}): glslang rc=${_rc_gl} ${_err_gl}")
    else()
        math(EXPR _ok "${_ok} + 1")
    endif()
endforeach()

message(STATUS "RESUMO M1.2 GLES: shaders=${_total} ok=${_ok} excluidos=${_skipped} ausentes=${_missing} falhas=${_failed}")

if (_failed GREATER 0)
    message(FATAL_ERROR "M1.2 GLES: ${_failed} shader(s) falharam:${_fail_msgs}")
endif()