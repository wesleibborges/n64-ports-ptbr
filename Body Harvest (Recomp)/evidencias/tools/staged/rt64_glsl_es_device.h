//
// RT64
//
// M1-GLES -- wrapper de criacao de shader para o canal OpenGL ES.
//
// Header-only de proposito: depende de `plume` (RenderDevice/RenderShader) e por isso NAO
// pode ser compilado num host sem SDL/X11. Toda a logica testavel vive em `rt64_glsl_es.h`.
//

#pragma once

#include <cassert>
#include <cstdio>

#include "rt64_glsl_es.h"
#include "common/rt64_plume.h"

namespace RT64 {
    // Cria o shader no dispositivo aplicando a conversao de formato quando necessario.
    //
    // - `format == GLSL_ES`: `data` e o SPIR-V do canal GLES; ele e convertido para ESSL
    //   3.20 antes de chegar ao device (`entryPointName` e preservado).
    // - Qualquer outro formato: repasse direto para `device->createShader`, comportamento
    //   identico ao original (zero mudanca para DXIL/SPIRV/METAL).
    //
    // Retorna `nullptr` (com mensagem em stderr) se a conversao falhar -- o que so pode
    // acontecer com um blob corrompido, pois o conjunto embutido foi validado no M1.2.
    inline std::unique_ptr<RenderShader> createShader(RenderDevice *device, const void *data, uint32_t size, const char *entryPointName, RenderShaderFormat format) {
        assert(device != nullptr);

        if (format == RenderShaderFormat::GLSL_ES) {
            std::string source;
            std::string error;
            if (!convertSPIRVToGLSLES(data, size, source, &error)) {
                fprintf(stderr, "RT64 GLES: SPIR-V -> ESSL 3.20 conversion failed for '%s' (%s).\n",
                    (entryPointName != nullptr) ? entryPointName : "<null>", error.c_str());
                assert(false && "GLES: SPIR-V -> ESSL 3.20 conversion must always succeed for the blobs shipped with the build.");
                return nullptr;
            }

            return device->createShader(source.data(), source.size(), entryPointName, format);
        }

        return device->createShader(data, size, entryPointName, format);
    }
};