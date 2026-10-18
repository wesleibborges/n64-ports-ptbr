//
// RT64
//

#include "rt64_glsl_es.h"

#ifdef RT64_GLSL_ES_BLOBS
#include "spirv_cross_c.h"
#endif

namespace RT64 {
#ifdef RT64_GLSL_ES_BLOBS
    namespace {
        // Espelha `glsl_es_sanitize.cmake` (o sanitizador validado no M1.1: 57/57 em
        // glslangValidator). O `spirv-cross` nao expoe opcao para nenhum dos tres itens.
        //
        // Retorna `false` se o shader contiver a extensao GL_NV_gpu_shader5, que e um
        // REGRESSO do fix de fonte gated por `-D HLSL_GLES` (macro NonUniformResourceIndex
        // identidade) e deve falhar ruidosamente em vez de ser "consertado" no texto.
        bool sanitizeGLSLES(std::string &source) {
            if (source.find("GL_NV_gpu_shader5") != std::string::npos) {
                return false;
            }

            // 1. `noperspective` nao existe em ESSL 3.20. Removido; a interpolacao passa a
            //    `smooth` (afeta apenas o overlay de debug do im3d).
            const std::string noperspective = "noperspective ";
            for (size_t pos = source.find(noperspective); pos != std::string::npos; pos = source.find(noperspective, pos)) {
                source.erase(pos, noperspective.size());
            }

            // 2. `precision mediump float;` -> `highp`: no Mali-G31 mediump e fp16 e
            //    degradaria coordenadas de textura e depth.
            const std::string mediumpFloat = "precision mediump float;";
            const std::string highpFloat = "precision highp float;";
            for (size_t pos = source.find(mediumpFloat); pos != std::string::npos; pos = source.find(mediumpFloat, pos)) {
                source.replace(pos, mediumpFloat.size(), highpFloat);
                pos += highpFloat.size();
            }

            // 3. Injeta `precision highp float;` quando o shader nao declara precisao default.
            if (source.find(highpFloat) == std::string::npos) {
                const std::string version = "#version 320 es";
                const size_t pos = source.find(version);
                if (pos != std::string::npos) {
                    source.insert(pos + version.size(), "\n" + highpFloat);
                }
            }

            return true;
        }
    }

    bool convertSPIRVToGLSLES(const void *spirvData, size_t spirvSize, std::string &outSource, std::string *outError) {
        outSource.clear();

        if ((spirvData == nullptr) || (spirvSize == 0) || ((spirvSize % sizeof(SpvId)) != 0)) {
            if (outError != nullptr) {
                *outError = "invalid SPIR-V blob (null, empty or not word-aligned)";
            }
            return false;
        }

        spvc_context context = nullptr;
        if (spvc_context_create(&context) != SPVC_SUCCESS) {
            if (outError != nullptr) {
                *outError = "spvc_context_create failed";
            }
            return false;
        }

        bool succeeded = false;

        do {
            spvc_parsed_ir parsedIR = nullptr;
            if (spvc_context_parse_spirv(context, static_cast<const SpvId *>(spirvData), spirvSize / sizeof(SpvId), &parsedIR) != SPVC_SUCCESS) {
                if (outError != nullptr) {
                    const char *lastError = spvc_context_get_last_error_string(context);
                    *outError = (lastError != nullptr) ? lastError : "spvc_context_parse_spirv failed";
                }
                break;
            }

            spvc_compiler compiler = nullptr;
            if (spvc_context_create_compiler(context, SPVC_BACKEND_GLSL, parsedIR, SPVC_CAPTURE_MODE_TAKE_OWNERSHIP, &compiler) != SPVC_SUCCESS) {
                if (outError != nullptr) {
                    const char *lastError = spvc_context_get_last_error_string(context);
                    *outError = (lastError != nullptr) ? lastError : "spvc_context_create_compiler failed";
                }
                break;
            }

            // `--es --version 320` do CLI do spirv-cross, mais os defaults do CLI quando
            // `--vulkan-semantics` NAO e passado.
            spvc_compiler_options options = nullptr;
            spvc_compiler_create_compiler_options(compiler, &options);
            spvc_compiler_options_set_uint(options, SPVC_COMPILER_OPTION_GLSL_VERSION, 320);
            spvc_compiler_options_set_bool(options, SPVC_COMPILER_OPTION_GLSL_ES, SPVC_TRUE);
            spvc_compiler_options_set_bool(options, SPVC_COMPILER_OPTION_GLSL_VULKAN_SEMANTICS, SPVC_FALSE);
            spvc_compiler_install_compiler_options(compiler, options);

            // CLI main.cpp: `combined_image_samplers = !vulkan_semantics` (= true) e
            // `build_dummy_sampler = true`. Sem isto o ESSL gerado nao compila em ESSL 3.20.
            spvc_variable_id dummySampler = 0;
            if (spvc_compiler_build_dummy_sampler_for_combined_images(compiler, &dummySampler) == SPVC_SUCCESS) {
                if (dummySampler != 0) {
                    spvc_compiler_set_decoration(compiler, dummySampler, SpvDecorationDescriptorSet, 0);
                    spvc_compiler_set_decoration(compiler, dummySampler, SpvDecorationBinding, 0);
                }
            }

            if (spvc_compiler_build_combined_image_samplers(compiler) != SPVC_SUCCESS) {
                if (outError != nullptr) {
                    const char *lastError = spvc_context_get_last_error_string(context);
                    *outError = (lastError != nullptr) ? lastError : "spvc_compiler_build_combined_image_samplers failed";
                }
                break;
            }

            const spvc_combined_image_sampler *samplers = nullptr;
            size_t samplerCount = 0;
            spvc_compiler_get_combined_image_samplers(compiler, &samplers, &samplerCount);
            for (size_t i = 0; i < samplerCount; i++) {
                const char *imageName = spvc_compiler_get_name(compiler, samplers[i].image_id);
                const char *samplerName = spvc_compiler_get_name(compiler, samplers[i].sampler_id);
                std::string combinedName = "SPIRV_Cross_Combined";
                combinedName += (imageName != nullptr) ? imageName : "";
                combinedName += (samplerName != nullptr) ? samplerName : "";
                spvc_compiler_set_name(compiler, samplers[i].combined_id, combinedName.c_str());
            }

            const char *source = nullptr;
            if (spvc_compiler_compile(compiler, &source) != SPVC_SUCCESS || source == nullptr) {
                if (outError != nullptr) {
                    const char *lastError = spvc_context_get_last_error_string(context);
                    *outError = (lastError != nullptr) ? lastError : "spvc_compiler_compile failed";
                }
                break;
            }

            // O texto pertence ao contexto: copiar e sanitizar antes de destrui-lo.
            std::string sanitized(source);
            if (!sanitizeGLSLES(sanitized)) {
                if (outError != nullptr) {
                    *outError = "sanitizer regression: GL_NV_gpu_shader5 present in the ESSL output";
                }
                break;
            }

            outSource = std::move(sanitized);
            succeeded = true;
        } while (false);

        spvc_context_destroy(context);
        return succeeded;
    }
#else
    bool convertSPIRVToGLSLES(const void *spirvData, size_t spirvSize, std::string &outSource, std::string *outError) {
        (void)spirvData;
        (void)spirvSize;
        outSource.clear();
        if (outError != nullptr) {
            *outError = "RT64 was built without RT64_GLSL_ES_BLOBS";
        }
        return false;
    }
#endif
};