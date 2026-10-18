#!/usr/bin/env python3
"""M1.3 estagio 2 -- plumbing do canal GLES no runtime (spirv-cross linkado + casos GLSL_ES).

Aplica edicoes em:
  lib/rt64/CMakeLists.txt                     (add_subdirectory spirv-cross + link + source)
  lib/rt64/src/render/rt64_shader_library.cpp (37x createShader + caso GLSL_ES hw-resolve)
  lib/rt64/src/render/rt64_raster_shader.cpp  (14x createShader + 2 switches + ctor)
  lib/rt64/src/render/rt64_raster_shader.h    (initialize(shaderFormat))
  lib/rt64/src/render/rt64_raster_shader_cache.cpp (initialize(shaderFormat))

Copia os fontes novos de `staged/` para a arvore:
  rt64_glsl_es.{h,cpp}, rt64_glsl_es_device.h

Nao idempotente por design: cada substituicao exige a contagem exata, entao rodar duas
vezes aborta em vez de corromper o arquivo. Backup completo em m1_3_gles/stage2/backup/.
"""
import hashlib
import os
import shutil
import sys

TREE = "/root/bhrecomp/lib/rt64"
RENDER = os.path.join(TREE, "src", "render")
BACKUP = "/root/bhrecomp/m1_3_gles/stage2/backup"
STAGED = os.path.dirname(os.path.abspath(__file__))

CMAKELISTS = os.path.join(TREE, "CMakeLists.txt")
SHADER_LIB = os.path.join(RENDER, "rt64_shader_library.cpp")
RASTER_SHADER = os.path.join(RENDER, "rt64_raster_shader.cpp")
RASTER_SHADER_H = os.path.join(RENDER, "rt64_raster_shader.h")
RASTER_CACHE = os.path.join(RENDER, "rt64_raster_shader_cache.cpp")

NEW_FILES = {
    "rt64_glsl_es.h": os.path.join(RENDER, "rt64_glsl_es.h"),
    "rt64_glsl_es.cpp": os.path.join(RENDER, "rt64_glsl_es.cpp"),
    "rt64_glsl_es_device.h": os.path.join(RENDER, "rt64_glsl_es_device.h"),
}

TEXT_FILES = [CMAKELISTS, SHADER_LIB, RASTER_SHADER, RASTER_SHADER_H, RASTER_CACHE]

# md5 do estado PRE-patch. Re-executar o script sobre uma arvore ja patchada duplicaria
# edicoes (as ancoras de 1 ocorrencia continuam casando) e, ao abortar depois, o restore
# apagaria os fontes novos. Este guard impede isso: so roda sobre a arvore PRE.
BASELINE_MD5 = {
    "CMakeLists.txt": "9dfb65cd9bd76bad806daaaf3f56db1b",
    "rt64_shader_library.cpp": "3ca7b5b953c4b3a21d090409ed97ff2a",
    "rt64_raster_shader.cpp": "fa672a7e9e8694579014c86c44d4e38a",
    "rt64_raster_shader.h": "aba39baa6fe1385218765ea81a2d3412",
    "rt64_raster_shader_cache.cpp": "a6c812831a918f68f089977d1994c81b",
}


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def patch(path, old, new, count):
    text = read(path)
    found = text.count(old)
    if found != count:
        raise SystemExit(
            "ABORT: %s -- esperava %d ocorrencia(s) de %r, encontrou %d"
            % (os.path.basename(path), count, old[:70], found)
        )
    write(path, text.replace(old, new))
    return count


def backup():
    os.makedirs(BACKUP, exist_ok=True)
    for path in TEXT_FILES:
        shutil.copy2(path, os.path.join(BACKUP, os.path.basename(path)))


def copy_new_sources():
    for name, dest in NEW_FILES.items():
        src = os.path.join(STAGED, name)
        if not os.path.exists(src):
            raise SystemExit("ABORT: fonte staged ausente: %s" % src)
        shutil.copy2(src, dest)


def main():
    applied = 0

    if "--verify-only" in sys.argv:
        print("verify-only: nada a fazer")
        return 0

    # Guard: recusa rodar sobre arvore ja patchada (ver BASELINE_MD5).
    dirty = []
    for path in TEXT_FILES:
        name = os.path.basename(path)
        if md5(path) != BASELINE_MD5[name]:
            dirty.append("%s (md5=%s, esperado=%s)" % (name, md5(path), BASELINE_MD5[name]))
    if dirty:
        print("ABORT: arvore NAO esta no estado PRE-patch. Nada foi alterado.")
        for item in dirty:
            print("  %s" % item)
        print("Restaure do backup (%s) antes de reaplicar." % BACKUP)
        return 1

    print("== md5 ANTES ==")
    for path in TEXT_FILES:
        print("  %s  %s" % (md5(path), os.path.relpath(path, TREE)))
    for dest in NEW_FILES.values():
        print("  %s  %s" % ("(ausente)" if not os.path.exists(dest) else md5(dest), os.path.relpath(dest, TREE)))

    backup()
    copy_new_sources()
    print("== backup em %s ==" % BACKUP)

    # ---------------------------------------------------------------- 1. CMakeLists
    patch(CMAKELISTS,
          'option(RT64_GLSL_ES_SHADERS "Gera o canal GLES (SPIR-V com -D HLSL_GLES + validacao ESSL 3.20)" OFF)\n',
          'option(RT64_GLSL_ES_SHADERS "Gera o canal GLES (SPIR-V com -D HLSL_GLES + validacao ESSL 3.20)" OFF)\n'
          '\n'
          '# M1-GLES -- M1.3 estagio 2: `spirv-cross` LINKA DO no runtime.\n'
          '# O canal GLES nao pode embutir ESSL pronto: o blob `-D HLSL_GLES` precisa ser\n'
          '# especializado por `respv::Optimizer::run` em runtime ANTES da conversao. Logo a\n'
          '# conversao SPIR-V -> ESSL 3.20 tem que acontecer no binario final.\n'
          '# Alvo: apenas o backend GLSL + API C (`spirv-cross-c`); sem CLI, sem testes, sem\n'
          '# HLSL/MSL/CPP/reflect/util (reduz tempo de build e tamanho do binario).\n'
          '# GATE: so com RT64_GLSL_ES_SHADERS=ON -> builds DX/VK/MSL permanecem byte-identicos.\n'
          'if (RT64_GLSL_ES_SHADERS)\n'
          '    set(SPIRV_CROSS_CLI OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_TESTS OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_SKIP_INSTALL ON CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_HLSL OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_MSL OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_CPP OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_REFLECT OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_UTIL OFF CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_ENABLE_C_API ON CACHE BOOL "" FORCE)\n'
          '    set(SPIRV_CROSS_STATIC ON CACHE BOOL "" FORCE)\n'
          '    add_subdirectory(src/contrib/spirv-cross)\n'
          'endif()\n', 1)
    applied += 1

    patch(CMAKELISTS,
          'set_target_properties(rt64 PROPERTIES PREFIX "")\n',
          'set_target_properties(rt64 PROPERTIES PREFIX "")\n'
          '\n'
          '# M1-GLES -- M1.3 estagio 2: conversor SPIR-V -> ESSL 3.20 usado pelo backend GLES.\n'
          'if (RT64_GLSL_ES_SHADERS)\n'
          '    target_sources(rt64 PRIVATE "${PROJECT_SOURCE_DIR}/src/render/rt64_glsl_es.cpp")\n'
          'endif()\n', 1)
    applied += 1

    patch(CMAKELISTS,
          'target_link_libraries(rt64 re-spirv)\n',
          'target_link_libraries(rt64 re-spirv)\n'
          '\n'
          '# M1-GLES -- M1.3 estagio 2: `spirv-cross-c` (backend GLSL) linkado no rt64.\n'
          'if (RT64_GLSL_ES_SHADERS)\n'
          '    target_link_libraries(rt64 spirv-cross-c)\n'
          'endif()\n', 1)
    applied += 1

    print("CMakeLists.txt: 3 edicoes")

    # ------------------------------------------- 2. rt64_shader_library.cpp
    patch(SHADER_LIB,
          '#include "rt64_descriptor_sets.h"\n#include "rt64_render_target.h"\n',
          '#include "rt64_descriptor_sets.h"\n#include "rt64_render_target.h"\n'
          '\n'
          '// M1-GLES -- wrapper de criacao de shader: converte SPIR-V -> ESSL 3.20 quando o\n'
          '// formato e GLSL_ES e repassa inalterado nos demais formatos.\n'
          '#include "rt64_glsl_es_device.h"\n', 1)
    applied += 1

    # 32x CREATE_SHADER_INPUTS + 5x blobs do caminho de hardware resolve.
    patch(SHADER_LIB, 'device->createShader(', 'createShader(device, ', 37)
    applied += 1

    patch(SHADER_LIB,
          '        else {\n'
          '            assert(false && "Unknown shader format.");\n'
          '        }\n',
          '#ifdef RT64_GLSL_ES_BLOBS\n'
          '        // M1-GLES -- GLSL_ES usa o MESMO conjunto de permutacoes por contagem de amostras,\n'
          '        // mas a partir dos blobs `*BlobGLSLES` (SPIR-V com `-D HLSL_GLES`); a conversao\n'
          '        // para ESSL 3.20 acontece em `createShader()` acima. Os blobs SPIRV padrao NAO\n'
          '        // servem aqui: usam texturas 1D/descriptor indexing, invalidos em ESSL 3.20.\n'
          '        else if (shaderFormat == RenderShaderFormat::GLSL_ES) {\n'
          '            RtCopyDepthToColorPSBlob = RtCopyDepthToColorPSBlobGLSLES;\n'
          '            RtCopyDepthToColorPSBlobSize = std::size(RtCopyDepthToColorPSBlobGLSLES);\n'
          '            RtCopyColorToDepthPSBlob = RtCopyColorToDepthPSBlobGLSLES;\n'
          '            RtCopyColorToDepthPSBlobSize = std::size(RtCopyColorToDepthPSBlobGLSLES);\n'
          '\n'
          '            switch (multisampling.sampleCount) {\n'
          '            case RenderSampleCount::COUNT_2:\n'
          '                TextureResolvePSBlob = TextureResolveSamples2XPSBlobGLSLES;\n'
          '                TextureResolvePSBlobSize = std::size(TextureResolveSamples2XPSBlobGLSLES);\n'
          '                RtCopyDepthToColorPSMSBlob = RtCopyDepthToColor2XPSBlobGLSLES;\n'
          '                RtCopyDepthToColorPSMSBlobSize = std::size(RtCopyDepthToColor2XPSBlobGLSLES);\n'
          '                RtCopyColorToDepthPSMSBlob = RtCopyColorToDepth2XPSBlobGLSLES;\n'
          '                RtCopyColorToDepthPSMSBlobSize = std::size(RtCopyColorToDepth2XPSBlobGLSLES);\n'
          '                break;\n'
          '            case RenderSampleCount::COUNT_4:\n'
          '                TextureResolvePSBlob = TextureResolveSamples4XPSBlobGLSLES;\n'
          '                TextureResolvePSBlobSize = std::size(TextureResolveSamples4XPSBlobGLSLES);\n'
          '                RtCopyDepthToColorPSMSBlob = RtCopyDepthToColor4XPSBlobGLSLES;\n'
          '                RtCopyDepthToColorPSMSBlobSize = std::size(RtCopyDepthToColor4XPSBlobGLSLES);\n'
          '                RtCopyColorToDepthPSMSBlob = RtCopyColorToDepth4XPSBlobGLSLES;\n'
          '                RtCopyColorToDepthPSMSBlobSize = std::size(RtCopyColorToDepth4XPSBlobGLSLES);\n'
          '                break;\n'
          '            case RenderSampleCount::COUNT_8:\n'
          '                TextureResolvePSBlob = TextureResolveSamples8XPSBlobGLSLES;\n'
          '                TextureResolvePSBlobSize = std::size(TextureResolveSamples8XPSBlobGLSLES);\n'
          '                RtCopyDepthToColorPSMSBlob = RtCopyDepthToColor8XPSBlobGLSLES;\n'
          '                RtCopyDepthToColorPSMSBlobSize = std::size(RtCopyDepthToColor8XPSBlobGLSLES);\n'
          '                RtCopyColorToDepthPSMSBlob = RtCopyColorToDepth8XPSBlobGLSLES;\n'
          '                RtCopyColorToDepthPSMSBlobSize = std::size(RtCopyColorToDepth8XPSBlobGLSLES);\n'
          '                break;\n'
          '            }\n'
          '        }\n'
          '#endif\n'
          '        else {\n'
          '            assert(false && "Unknown shader format.");\n'
          '        }\n', 1)
    applied += 1

    print("rt64_shader_library.cpp: 3 edicoes")

    # ------------------------------------------- 3. rt64_raster_shader.cpp
    patch(RASTER_SHADER,
          '#include "shaders/PostBlendDitherNoiseSubNegativePS.hlsl.spirv.h"\n',
          '#include "shaders/PostBlendDitherNoiseSubNegativePS.hlsl.spirv.h"\n'
          '#ifdef RT64_GLSL_ES_BLOBS\n'
          '#   include "shaders/RasterPSDynamic.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterPSDynamicMS.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterPSSpecConstant.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterPSSpecConstantMS.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterPSSpecConstantFlat.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterPSSpecConstantFlatMS.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterVSDynamic.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterVSSpecConstant.hlsl.glsl_es.h"\n'
          '#   include "shaders/RasterVSSpecConstantFlat.hlsl.glsl_es.h"\n'
          '#   include "shaders/PostBlendDitherNoiseAddPS.hlsl.glsl_es.h"\n'
          '#   include "shaders/PostBlendDitherNoiseSubPS.hlsl.glsl_es.h"\n'
          '#   include "shaders/PostBlendDitherNoiseSubNegativePS.hlsl.glsl_es.h"\n'
          '#endif\n', 1)
    applied += 1

    patch(RASTER_SHADER,
          '#include "rt64_descriptor_sets.h"\n',
          '#include "rt64_descriptor_sets.h"\n'
          '\n'
          '// M1-GLES -- wrapper de criacao de shader: converte SPIR-V -> ESSL 3.20 quando o\n'
          '// formato e GLSL_ES e repassa inalterado nos demais formatos.\n'
          '#include "rt64_glsl_es_device.h"\n', 1)
    applied += 1

    patch(RASTER_SHADER, 'device->createShader(', 'createShader(device, ', 17)
    applied += 1

    patch(RASTER_SHADER,
          '    void OptimizerCacheSPIRV::initialize() {\n',
          '    void OptimizerCacheSPIRV::initialize(RenderShaderFormat shaderFormat) {\n'
          '#ifdef RT64_GLSL_ES_BLOBS\n'
          '        // M1-GLES -- o canal GLES especializa os MESMOS shaders, mas a partir dos blobs\n'
          '        // compilados com `-D HLSL_GLES` (texturas 2D no lugar de 1D, sem descriptor\n'
          '        // indexing). Os blobs SPIRV padrao aqui gerariam ESSL invalido em ESSL 3.20.\n'
          '        if (shaderFormat == RenderShaderFormat::GLSL_ES) {\n'
          '            rasterVS.parse(RasterVSSpecConstantBlobGLSLES, std::size(RasterVSSpecConstantBlobGLSLES));\n'
          '            rasterVSFlat.parse(RasterVSSpecConstantFlatBlobGLSLES, std::size(RasterVSSpecConstantFlatBlobGLSLES));\n'
          '            rasterPS.parse(RasterPSSpecConstantBlobGLSLES, std::size(RasterPSSpecConstantBlobGLSLES));\n'
          '            rasterPSMS.parse(RasterPSSpecConstantMSBlobGLSLES, std::size(RasterPSSpecConstantMSBlobGLSLES));\n'
          '            rasterPSFlat.parse(RasterPSSpecConstantFlatBlobGLSLES, std::size(RasterPSSpecConstantFlatBlobGLSLES));\n'
          '            rasterPSFlatMS.parse(RasterPSSpecConstantFlatMSBlobGLSLES, std::size(RasterPSSpecConstantFlatMSBlobGLSLES));\n'
          '            assert(!rasterVS.empty());\n'
          '            assert(!rasterVSFlat.empty());\n'
          '            assert(!rasterPS.empty());\n'
          '            assert(!rasterPSMS.empty());\n'
          '            assert(!rasterPSFlat.empty());\n'
          '            assert(!rasterPSFlatMS.empty());\n'
          '            return;\n'
          '        }\n'
          '#else\n'
          '        (void)shaderFormat;\n'
          '#endif\n', 1)
    applied += 1

    patch(RASTER_SHADER,
          '        if (shaderFormat == RenderShaderFormat::SPIRV) {\n'
          '            // Choose the pre-compiled shader permutations.\n',
          '        // M1-GLES -- o canal GLES reusa o caminho de `respv::Optimizer` do SPIRV\n'
          '        // (mesmos 5 spec constants) e converte o resultado para ESSL em `createShader()`.\n'
          '        if ((shaderFormat == RenderShaderFormat::SPIRV) || (shaderFormat == RenderShaderFormat::GLSL_ES)) {\n'
          '            // Choose the pre-compiled shader permutations.\n', 1)
    applied += 1

    print("rt64_raster_shader.cpp: 5 edicoes (parte 1)")

    patch(RASTER_SHADER,
          '        default:\n'
          '            assert(false && "Unknown shader format.");\n'
          '            return;\n'
          '        }\n'
          '\n'
          '        vertexShader =',
          '#ifdef RT64_GLSL_ES_BLOBS\n'
          '        case RenderShaderFormat::GLSL_ES:\n'
          '            // M1-GLES -- o ubershader nao usa spec constants (DYNAMIC_RENDER_PARAMS): o blob\n'
          '            // SPIR-V vai direto para `createShader()`, que o converte para ESSL 3.20.\n'
          '            VSBlob = RasterVSDynamicBlobGLSLES;\n'
          '            PSBlob = useMSAA ? RasterPSDynamicMSBlobGLSLES : RasterPSDynamicBlobGLSLES;\n'
          '            VSBlobSize = uint32_t(std::size(RasterVSDynamicBlobGLSLES));\n'
          '            PSBlobSize = uint32_t(useMSAA ? std::size(RasterPSDynamicMSBlobGLSLES) : std::size(RasterPSDynamicBlobGLSLES));\n'
          '            break;\n'
          '#endif\n'
          '        default:\n'
          '            assert(false && "Unknown shader format.");\n'
          '            return;\n'
          '        }\n'
          '\n'
          '        vertexShader =', 1)
    applied += 1

    patch(RASTER_SHADER,
          '        default:\n'
          '            assert(false && "Unknown shader format.");\n'
          '            return;\n'
          '        }\n'
          '\n'
          '        RenderGraphicsPipelineDesc postBlendDesc;',
          '#ifdef RT64_GLSL_ES_BLOBS\n'
          '        case RenderShaderFormat::GLSL_ES:\n'
          '            postBlendAddPixelShader = createShader(device, PostBlendDitherNoiseAddPSBlobGLSLES, std::size(PostBlendDitherNoiseAddPSBlobGLSLES), "PSMain", shaderFormat);\n'
          '            postBlendSubPixelShader = createShader(device, PostBlendDitherNoiseSubPSBlobGLSLES, std::size(PostBlendDitherNoiseSubPSBlobGLSLES), "PSMain", shaderFormat);\n'
          '            postBlendSubNegativePixelShader = createShader(device, PostBlendDitherNoiseSubNegativePSBlobGLSLES, std::size(PostBlendDitherNoiseSubNegativePSBlobGLSLES), "PSMain", shaderFormat);\n'
          '            break;\n'
          '#endif\n'
          '        default:\n'
          '            assert(false && "Unknown shader format.");\n'
          '            return;\n'
          '        }\n'
          '\n'
          '        RenderGraphicsPipelineDesc postBlendDesc;', 1)
    applied += 1

    print("rt64_raster_shader.cpp: 7 edicoes")

    # ------------------------------------------- 4. rt64_raster_shader.h
    patch(RASTER_SHADER_H,
          '        void initialize();\n',
          '        // M1-GLES -- o formato decide de qual canal os blobs sao parseados\n'
          '        // (SPIRV padrao ou GLSLES com `-D HLSL_GLES`).\n'
          '        void initialize(RenderShaderFormat shaderFormat = RenderShaderFormat::SPIRV);\n', 1)
    applied += 1
    print("rt64_raster_shader.h: 1 edicao")

    # ------------------------------------------- 5. rt64_raster_shader_cache.cpp
    patch(RASTER_CACHE,
          '        if (shaderFormat == RenderShaderFormat::SPIRV) {\n'
          '            optimizerCacheSPIRV.initialize();\n'
          '        }\n',
          '        // M1-GLES -- o canal GLES especializa os mesmos shaders em runtime, mas a partir\n'
          '        // dos blobs `*BlobGLSLES` (ver OptimizerCacheSPIRV::initialize).\n'
          '        if ((shaderFormat == RenderShaderFormat::SPIRV) || (shaderFormat == RenderShaderFormat::GLSL_ES)) {\n'
          '            optimizerCacheSPIRV.initialize(shaderFormat);\n'
          '        }\n', 1)
    applied += 1
    print("rt64_raster_shader_cache.cpp: 1 edicao")

    print("\n== md5 DEPOIS ==")
    for path in TEXT_FILES:
        print("  %s  %s" % (md5(path), os.path.relpath(path, TREE)))
    for dest in NEW_FILES.values():
        print("  %s  %s" % (md5(dest), os.path.relpath(dest, TREE)))

    print("\nOK: %d edicoes aplicadas + %d fontes novos." % (applied, len(NEW_FILES)))
    return applied


if __name__ == "__main__":
    main()