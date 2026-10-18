#!/usr/bin/env python3
"""M1.2 - Liga o canal de shaders OpenGL ES (ESSL 3.20) na arvore do RT64.

Edita 3 arquivos e materializa os scripts CMake do canal:

  A. src/contrib/plume/plume_render_interface_types.h
       -> novo valor `RenderShaderFormat::GLSL_ES` (APPEND ao fim, preservando os
          valores numericos de DXIL/SPIRV/METAL).
  B. src/render/rt64_shader_library.cpp
       -> includes dos headers `.hlsl.glsl_es.h` (gated por RT64_GLSL_ES_BLOBS)
       -> CREATE_SHADER_INPUTS passa a receber 4 blobs (DXIL, SPIRV, MSL, GLSLES);
          o 4o argumento e ignorado pelos builds sem o canal.
       -> os 35 call sites recebem o 4o blob (`<X>BlobGLSLES`, derivado de `<X>BlobSPIRV`).
  C. lib/rt64/CMakeLists.txt
       -> opcao RT64_GLSL_ES_SHADERS (default OFF)
       -> headers no DEPENDS dos shaders (corrige bug latente)
       -> build_shader_glsl_es_impl (SPIR-V com -D HLSL_GLES + blob embutido)
       -> target `rt64_glsl_es_validate` (aceite: ESSL 3.20 compila)

Uso:
  python3 m1_2_apply_gles_channel.py apply     # backup + aplica
  python3 m1_2_apply_gles_channel.py revert    # restaura do backup
  python3 m1_2_apply_gles_channel.py check     # so relata o estado
"""
import hashlib
import os
import re
import shutil
import sys

RT64 = '/root/bhrecomp/lib/rt64'
SRC = os.path.join(RT64, 'src')
OUT = '/root/bhrecomp/m1_2_gles'
BACKUP = os.path.join(OUT, 'backup')

F_ENUM = os.path.join(SRC, 'contrib', 'plume', 'plume_render_interface_types.h')
F_LIB = os.path.join(SRC, 'render', 'rt64_shader_library.cpp')
F_CMAKE = os.path.join(RT64, 'CMakeLists.txt')

FILES = [F_ENUM, F_LIB, F_CMAKE]

# --------------------------------------------------------------------- A: enum
ENUM_OLD = """    enum class RenderShaderFormat {
        UNKNOWN,
        DXIL,
        SPIRV,
        METAL
    };
"""

ENUM_NEW = """    enum class RenderShaderFormat {
        UNKNOWN,
        DXIL,
        SPIRV,
        METAL,
        // M1-GLES -- alvo OpenGL ES (ESSL 3.20). O blob carregado nesta modalidade e
        // SPIR-V compilado com as adaptacoes `-D HLSL_GLES` (texturas 2D no lugar de
        // 1D, sem descriptor indexing). A conversao final para ESSL e feita pelo
        // backend GLES em runtime (re-spirv + spirv-cross), conforme M1.3.
        // APPEND ao final de proposito: preserva os valores numericos de DXIL/SPIRV/METAL.
        GLSL_ES
    };
"""

# ------------------------------------------------------------- B: macro 4 blobs
MACRO_NEW = r"""#ifdef _WIN32
#   define CREATE_SHADER_INPUTS(DXIL_BLOB, SPIRV_BLOB, MSL_BLOB, GLSLES_BLOB, ENTRY_NAME, SHADER_FORMAT)\
        (SHADER_FORMAT == RenderShaderFormat::DXIL) ? DXIL_BLOB : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? SPIRV_BLOB : nullptr,\
        (SHADER_FORMAT == RenderShaderFormat::DXIL) ? sizeof(DXIL_BLOB) : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? sizeof(SPIRV_BLOB) : 0,\
        ENTRY_NAME,\
        SHADER_FORMAT
#elif defined(__APPLE__)
#   define CREATE_SHADER_INPUTS(DXIL_BLOB, SPIRV_BLOB, MSL_BLOB, GLSLES_BLOB, ENTRY_NAME, SHADER_FORMAT)\
        (SHADER_FORMAT == RenderShaderFormat::METAL) ? MSL_BLOB : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? SPIRV_BLOB : nullptr,\
        (SHADER_FORMAT == RenderShaderFormat::METAL) ? sizeof(MSL_BLOB) : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? sizeof(SPIRV_BLOB) : 0,\
        ENTRY_NAME,\
        SHADER_FORMAT
#else
#   ifdef RT64_GLSL_ES_BLOBS
// M1-GLES -- canal OpenGL ES. `GLSLES_BLOB` e o SPIR-V gerado com `-D HLSL_GLES`
// (adaptacoes de ESSL 3.20); o backend converte para ESSL em runtime (M1.3).
#       define CREATE_SHADER_INPUTS(DXIL_BLOB, SPIRV_BLOB, MSL_BLOB, GLSLES_BLOB, ENTRY_NAME, SHADER_FORMAT)\
        (SHADER_FORMAT == RenderShaderFormat::GLSL_ES) ? GLSLES_BLOB : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? SPIRV_BLOB : nullptr,\
        (SHADER_FORMAT == RenderShaderFormat::GLSL_ES) ? sizeof(GLSLES_BLOB) : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? sizeof(SPIRV_BLOB) : 0,\
        ENTRY_NAME,\
        SHADER_FORMAT
#   else
#       define CREATE_SHADER_INPUTS(DXIL_BLOB, SPIRV_BLOB, MSL_BLOB, GLSLES_BLOB, ENTRY_NAME, SHADER_FORMAT)\
        (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? SPIRV_BLOB : nullptr,\
        (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? sizeof(SPIRV_BLOB) : 0,\
        ENTRY_NAME,\
        SHADER_FORMAT
#   endif
#endif
"""
# ------------------------------------------------------------------- C: CMake
CMAKE_OPT_ANCHOR = 'set (DXC_RT_OPTS "${DXC_COMMON_OPTS}" "-D" "RT_SHADER" "-T" "lib_6_3" "-fspv-target-env=vulkan1.1spirv1.4" "-fspv-extension=SPV_KHR_ray_tracing" "-fspv-extension=SPV_EXT_descriptor_indexing")\n'

CMAKE_OPT_BLOCK = r"""
# M1-GLES -- canal de shaders OpenGL ES (ESSL 3.20).
# Gera, por shader, um blob SPIR-V compilado com as adaptacoes `-D HLSL_GLES`
# (TMEM como textura 2D, sem descriptor indexing) e permite validar o ESSL 3.20
# resultante. O backend GLES (plume_gles) converte o SPIR-V especializado para ESSL
# em runtime -- ver src/tools/glsl_es_{sanitize,validate}.cmake e docs/PLANO_BACKEND_GLES_R36S.md.
# Default OFF: builds DX/VK/MSL permanecem byte-identicos.
option(RT64_GLSL_ES_SHADERS "Gera o canal GLES (SPIR-V com -D HLSL_GLES + validacao ESSL 3.20)" OFF)

# Headers compartilhados por todos os shaders. Sem isto, alterar um header NAO
# re-dispara o DXC (bug latente: os add_custom_command declaravam so
# `DEPENDS ${FILENAME}`, o proprio .hlsl) -- comprovado na sessao do M1.
file(GLOB_RECURSE RT64_SHADER_HEADERS CONFIGURE_DEPENDS
    "${PROJECT_SOURCE_DIR}/src/shaders/*.hlsli"
    "${PROJECT_SOURCE_DIR}/src/shared/*.h"
    "${PROJECT_SOURCE_DIR}/src/shared/*.hpp")

# Fora do conjunto ESSL: DebugPS usa `readonly image2D` (G-buffer do caminho de ray
# tracing, inexistente em GLES) -- ESSL 3.20 rejeita image2D com e sem format
# qualifier (probe do M1.1).
set(RT64_GLSL_ES_TEXT_SKIP "DebugPS.hlsl")

if (RT64_GLSL_ES_SHADERS)
    file(WRITE "${CMAKE_BINARY_DIR}/glsl_es_stages.txt" "")
    find_program(SPIRV_CROSS_EXECUTABLE spirv-cross)
    find_program(GLSLLANG_EXECUTABLE glslangValidator)
    if (NOT SPIRV_CROSS_EXECUTABLE OR NOT GLSLLANG_EXECUTABLE)
        message(WARNING "RT64_GLSL_ES_SHADERS=ON, mas spirv-cross/glslangValidator nao estao no PATH: os blobs GLES serao gerados, a validacao ESSL nao.")
    endif()
endif()
"""

CMAKE_IMPL = r"""
function(build_shader_glsl_es_impl TARGETOBJ FILENAME TARGET_NAME OUTNAME)
    # SPIR-V com as adaptacoes GLES (as fontes sao gated por `-D HLSL_GLES`).
    add_custom_command(OUTPUT ${OUTNAME}.glsl_es.spv
        COMMAND ${DXC} ${DXC_SPV_OPTS} -D HLSL_GLES ${ARGN} ${FILENAME} /Fo ${OUTNAME}.glsl_es.spv
        DEPENDS ${FILENAME} ${RT64_SHADER_HEADERS})
    # Blob embutido no binario (`<TARGET>BlobGLSLES`).
    add_custom_command(OUTPUT ${OUTNAME}.glsl_es.c
        COMMAND file_to_c ${OUTNAME}.glsl_es.spv ${TARGET_NAME}BlobGLSLES ${OUTNAME}.glsl_es.c ${OUTNAME}.glsl_es.h
        DEPENDS ${OUTNAME}.glsl_es.spv file_to_c
        BYPRODUCTS ${OUTNAME}.glsl_es.h)
    target_sources(${TARGETOBJ} PRIVATE ${OUTNAME}.glsl_es.c)

    # Mapa <spv> <stage> consumido pelo alvo de validacao ESSL (rt64_glsl_es_validate).
    # Atencao: `${ARGN}` chega como LISTA do CMake (itens separados por `;`), portanto
    # o separador depois de `-E` pode ser `;` e nao espaco -- regex cobre os dois.
    string(REGEX MATCH "-E[^A-Za-z0-9]+([A-Za-z0-9_]+)" _gles_entry "${ARGN}")
    set(_gles_entry "${CMAKE_MATCH_1}")
    if (_gles_entry STREQUAL "VSMain")
        set(_gles_stage vert)
    elseif (_gles_entry STREQUAL "CSMain")
        set(_gles_stage comp)
    elseif (_gles_entry STREQUAL "GSMain")
        set(_gles_stage geom)
    else()
        set(_gles_stage frag)
    endif()
    file(APPEND "${CMAKE_BINARY_DIR}/glsl_es_stages.txt" "${OUTNAME}.glsl_es.spv ${_gles_stage}\n")
    set_property(GLOBAL APPEND PROPERTY RT64_GLSL_ES_BLOBS ${OUTNAME}.glsl_es.c)
endfunction()

"""

CMAKE_HOOK = r"""    if (RT64_GLSL_ES_SHADERS)
        build_shader_glsl_es_impl(${TARGETOBJ} ${FILENAME} ${TARGET_NAME} ${OUTNAME} ${OPTIONS} ${EXTRA_ARGS})
    endif()
"""

CMAKE_TAIL = r"""
# M1-GLES -- aceite do M1.2: valida que o conjunto ESSL 3.20 compila (glslangValidator).
# Uso: ninja -C <build> rt64_glsl_es_validate
if (RT64_GLSL_ES_SHADERS)
    target_compile_definitions(rt64 PRIVATE RT64_GLSL_ES_BLOBS)
    if (SPIRV_CROSS_EXECUTABLE AND GLSLLANG_EXECUTABLE)
        get_property(RT64_GLSL_ES_BLOB_FILES GLOBAL PROPERTY RT64_GLSL_ES_BLOBS)
        add_custom_target(rt64_glsl_es_validate
            COMMAND ${CMAKE_COMMAND}
                "-DMAP_FILE=${CMAKE_BINARY_DIR}/glsl_es_stages.txt"
                "-DSANITIZE_FILE=${PROJECT_SOURCE_DIR}/src/tools/glsl_es_sanitize.cmake"
                "-DSPIRV_CROSS=${SPIRV_CROSS_EXECUTABLE}"
                "-DGLSLLANG=${GLSLLANG_EXECUTABLE}"
                "-DSKIP_LIST=${RT64_GLSL_ES_TEXT_SKIP}"
                -P ${PROJECT_SOURCE_DIR}/src/tools/glsl_es_validate.cmake
            DEPENDS ${RT64_GLSL_ES_BLOB_FILES}
            COMMENT "M1.2 GLES: validando o conjunto ESSL 3.20 com glslangValidator")
    endif()
endif()
"""
def md5(path):
    with open(path, 'rb') as fh:
        return hashlib.md5(fh.read()).hexdigest()


def backup_files():
    os.makedirs(BACKUP, exist_ok=True)
    for f in FILES:
        dst = os.path.join(BACKUP, os.path.basename(f))
        if not os.path.exists(dst):
            shutil.copy2(f, dst)


# ------------------------------------------------------------------ patches
def patch_enum(text):
    if 'GLSL_ES' in text:
        return text, 'ja aplicado'
    if ENUM_OLD not in text:
        raise SystemExit('ERRO: ancora do enum nao encontrada em ' + F_ENUM)
    return text.replace(ENUM_OLD, ENUM_NEW, 1), 'ok'


def patch_shader_library(text):
    tag = 'ja aplicado'
    if 'GLSLES_BLOB' not in text:
        # B1: includes dos headers GLES, derivados do bloco de includes SPIR-V.
        incs = re.findall(r'#include "shaders/([A-Za-z0-9_]+\.hlsl)\.spirv\.h"\n', text)
        if not incs:
            raise SystemExit('ERRO: nenhum include SPIR-V encontrado em ' + F_LIB)
        block = '#ifdef RT64_GLSL_ES_BLOBS\n'
        for base in incs:
            block += '#   include "shaders/%s.glsl_es.h"\n' % base
        block += '#endif\n'
        matches = list(re.finditer(r'#include "shaders/[A-Za-z0-9_]+\.hlsl\.spirv\.h"\n', text))
        at = matches[-1].end()
        text = text[:at] + block + text[at:]

        # B2: macro com 4 blobs.
        start = text.index('#ifdef _WIN32\n#   define CREATE_SHADER_INPUTS')
        end_marker = '        SHADER_FORMAT\n#endif\n'
        end = text.index(end_marker, start) + len(end_marker)
        text = text[:start] + MACRO_NEW + text[end:]

        # B3: call sites ganham o 4o blob (<X>BlobGLSLES, derivado de <X>BlobSPIRV).
        def add_blob(m):
            base = m.group(2).replace('BlobSPIRV', 'BlobGLSLES')
            return 'CREATE_SHADER_INPUTS(%s, %s, %s, %s, "' % (
                m.group(1), m.group(2), m.group(3), base)

        text, n = re.subn(
            r'CREATE_SHADER_INPUTS\((\w+),\s*(\w+),\s*(\w+),\s*"', add_blob, text)
        tag = 'ok (%d call sites, %d includes)' % (n, len(incs))
    return text, tag
def patch_cmake(text):
    if 'build_shader_glsl_es_impl' in text:
        return text, 'ja aplicado'

    # C1: opcao + headers + skip list, logo apos os DXC_*_OPTS.
    if CMAKE_OPT_ANCHOR not in text:
        raise SystemExit('ERRO: ancora dos DXC opts nao encontrada em ' + F_CMAKE)
    text = text.replace(CMAKE_OPT_ANCHOR, CMAKE_OPT_ANCHOR + CMAKE_OPT_BLOCK, 1)

    # C2: headers no DEPENDS (bug latente do M1: so o .hlsl era declarado).
    n_dep = text.count('DEPENDS ${FILENAME})')
    text = text.replace('DEPENDS ${FILENAME})', 'DEPENDS ${FILENAME} ${RT64_SHADER_HEADERS})')
    n_dep += text.count('DEPENDS ${INFILE})')
    text = text.replace('DEPENDS ${INFILE})', 'DEPENDS ${INFILE} ${RT64_SHADER_HEADERS})')

    # C3: funcao do canal GLES, antes de build_shader().
    anchor3 = 'function(build_shader TARGETOBJ SHADERNAME OPTIONS)\n'
    text = text.replace(anchor3, CMAKE_IMPL.lstrip('\n') + '\n' + anchor3, 1)

    # C4/C5: hooks em build_shader() e build_shader_spirv().
    anchor4 = ('    build_shader_spirv_impl(${TARGETOBJ} ${FILENAME} ${TARGET_NAME} ${OUTNAME} ${OPTIONS} ${EXTRA_ARGS})\n'
               'endfunction()\n\nfunction(build_shader_dxil TARGETOBJ SHADERNAME OPTIONS)\n')
    if anchor4 not in text:
        raise SystemExit('ERRO: ancora do hook em build_shader nao encontrada')
    text = text.replace(anchor4,
                        '    build_shader_spirv_impl(${TARGETOBJ} ${FILENAME} ${TARGET_NAME} ${OUTNAME} ${OPTIONS} ${EXTRA_ARGS})\n'
                        + CMAKE_HOOK + 'endfunction()\n\nfunction(build_shader_dxil TARGETOBJ SHADERNAME OPTIONS)\n', 1)

    anchor5 = ('    build_shader_spirv_impl(${TARGETOBJ} ${FILENAME} ${TARGET_NAME} ${OUTNAME} ${OPTIONS} ${EXTRA_ARGS})\n'
               'endfunction()\n\nfunction(build_shader_msl TARGETOBJ SHADERNAME OPTIONS)\n')
    if anchor5 not in text:
        raise SystemExit('ERRO: ancora do hook em build_shader_spirv nao encontrada')
    text = text.replace(anchor5,
                        '    build_shader_spirv_impl(${TARGETOBJ} ${FILENAME} ${TARGET_NAME} ${OUTNAME} ${OPTIONS} ${EXTRA_ARGS})\n'
                        + CMAKE_HOOK + 'endfunction()\n\nfunction(build_shader_msl TARGETOBJ SHADERNAME OPTIONS)\n', 1)

    # C6: alvo de validacao + compile definition do canal.
    text = text.rstrip('\n') + '\n' + CMAKE_TAIL
    return text, 'ok (DEPENDS corrigidos: %d)' % n_dep
def apply():
    backup_files()
    for f, patcher in ((F_ENUM, patch_enum),
                       (F_LIB, patch_shader_library),
                       (F_CMAKE, patch_cmake)):
        with open(f, encoding='utf-8') as fh:
            text = fh.read()
        new_text, tag = patcher(text)
        if tag == 'ja aplicado':
            print('  %-28s %s' % (os.path.basename(f), tag))
            continue
        with open(f, 'w', encoding='utf-8', newline='') as fh:
            fh.write(new_text)
        print('  %-28s %s -> md5=%s' % (os.path.basename(f), tag, md5(f)))
    with open(os.path.join(OUT, 'md5_aplicado.txt'), 'w') as fh:
        for f in FILES:
            fh.write('%s  %s\n' % (md5(f), f))


def revert():
    for f in FILES:
        src = os.path.join(BACKUP, os.path.basename(f))
        if not os.path.exists(src):
            raise SystemExit('ERRO: backup ausente para ' + f)
        shutil.copy2(src, f)
        print('  restaurado %-28s md5=%s' % (os.path.basename(f), md5(f)))


def check():
    with open(F_ENUM, encoding='utf-8') as fh:
        t = fh.read()
    print('  enum GLSL_ES           :', 'GLSL_ES' in t)
    with open(F_LIB, encoding='utf-8') as fh:
        t = fh.read()
    print('  macro GLSLES_BLOB      :', 'GLSLES_BLOB' in t)
    print('  call sites com 4 blobs :', len(re.findall(r'CREATE_SHADER_INPUTS\((\w+),\s*(\w+),\s*(\w+),\s*(\w+),\s*"', t)))
    print('  includes .glsl_es.h    :', len(re.findall(r'#\s*include "shaders/[A-Za-z0-9_]+\.hlsl\.glsl_es\.h"', t)))
    with open(F_CMAKE, encoding='utf-8') as fh:
        t = fh.read()
    print('  build_shader_glsl_es   :', 'build_shader_glsl_es_impl' in t)
    print('  DEPENDS com headers    :', t.count('${RT64_SHADER_HEADERS})'))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'apply':
        apply()
    elif cmd == 'revert':
        revert()
    elif cmd == 'check':
        check()
    else:
        raise SystemExit(__doc__)