# M1-GLES -- sanitizador do ESSL 3.20 emitido por 'spirv-cross --es'.
#
# O spirv-cross nao expoe opcao para os tres artefatos abaixo; esta logica espelha
# EXATAMENTE o sanitizador validado no M1.1 (57/57 em glslangValidator) -- ver
# evidencias/tools/m1_1_emit_glsl_es.py e evidence_m1_1_glsl_es_shaders_20261018.md.
#
#   1. 'noperspective' nao existe em ESSL 3.20 -> removido (interpolacao passa a
#      smooth; afeta apenas o overlay de debug do im3d).
#   2. 'precision mediump float;' -> highp (RT64 assume fp32 no raster; no Mali-G31
#      mediump e fp16 e degradaria coordenadas de textura e depth).
#   3. injeta 'precision highp float;' quando o shader nao declara precisao default.
#
# A extensao espuria GL_NV_gpu_shader5 (capability ShaderNonUniformEXT) NAO e tratada
# textualmente de proposito: ela foi eliminada na FONTE via -D HLSL_GLES
# (macro NonUniformResourceIndex identidade). Se reaparecer e REGRESSO e o build falha.
function(glsl_es_sanitize_file IN_FILE OUT_FILE)
    file(READ "${IN_FILE}" _text)
    if (_text MATCHES "GL_NV_gpu_shader5")
        message(FATAL_ERROR
            "GLES: ${IN_FILE} contem a extensao GL_NV_gpu_shader5 (capability "
            "ShaderNonUniformEXT). Regresso do fix de fonte gated por HLSL_GLES "
            "(NonUniformResourceIndex).")
    endif()
    string(REPLACE "noperspective " "" _text "${_text}")
    string(REPLACE "precision mediump float;" "precision highp float;" _text "${_text}")
    if (NOT _text MATCHES "precision highp float;")
        string(REPLACE "#version 320 es" "#version 320 es\nprecision highp float;" _text "${_text}")
    endif()
    file(WRITE "${OUT_FILE}" "${_text}")
endfunction()

# Modo script: cmake -DIN=<raw> -DOUT=<final> -P glsl_es_sanitize.cmake
if (DEFINED IN AND DEFINED OUT)
    glsl_es_sanitize_file("${IN}" "${OUT}")
endif()