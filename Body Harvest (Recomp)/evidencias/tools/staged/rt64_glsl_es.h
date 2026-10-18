//
// RT64
//
// M1-GLES -- canal OpenGL ES (ESSL 3.20).
//
// Este modulo encapsula a unica parte do runtime que depende do `spirv-cross`:
// converter o SPIR-V do canal GLES (`-D HLSL_GLES`, gerado no M1.2) em ESSL 3.20.
// Ele reproduz EXATAMENTE o pipeline validado no M1.1/M1.2 e medido no M1.3-estagio-1:
//
//   spirv-cross --es --version 320   (= opcoes default do CLI: combined image samplers
//                                     + dummy sampler; sem vulkan semantics)
//   -> sanitizador de src/tools/glsl_es_sanitize.cmake (3 correcoes textuais)
//
// PROPOSITALMENTE sem dependencia de `plume`: o wrapper que chega ao dispositivo fica em
// `rt64_glsl_es_device.h` (header-only). Assim este par .h/.cpp pode ser compilado e
// exercitado num host x86_64 sem SDL/X11 -- e exatamente o que o aceite do M1.3-estagio-2
// usa (evidencias/tools/m1_3_stage2_host/).
//

#pragma once

#include <stdint.h>

#include <string>

namespace RT64 {
    // Converte um modulo SPIR-V (idealmente ja especializado por `respv::Optimizer::run`)
    // para o texto ESSL 3.20 correspondente.
    //
    // Retorna `false` se o SPIR-V for invalido, se a conversao falhar ou se o sanitizador
    // detectar um regresso (extensao GL_NV_gpu_shader5 -- ver glsl_es_sanitize.cmake).
    // `outError`, quando fornecido, recebe a mensagem do `spirv-cross` em caso de falha.
    bool convertSPIRVToGLSLES(const void *spirvData, size_t spirvSize, std::string &outSource, std::string *outError = nullptr);
};