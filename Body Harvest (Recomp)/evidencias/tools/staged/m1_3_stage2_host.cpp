//
// M1.3 estagio 2 -- aceite host-side do caminho de runtime do canal GLES.
//
// Exercita o MESMO codigo de producao que o backend GLES usara:
//
//   blob GLES embutido (`*BlobGLSLES`, gerado no M1.2)
//     -> [respv::Optimizer::run quando o shader usa spec constants]
//     -> RT64::convertSPIRVToGLSLES (spirv-cross C API + sanitizador do M1.1)
//     -> ESSL 3.20
//
// e valida as invariantes que ja foram provadas em glslangValidator no M1.1/M1.2.
// A validacao ESSL final continua sendo feita por `glslangValidator -S <stage>` (script
// driver), para nao duplicar a logica de validacao dentro do binario.
//
// Uso: m1_3_stage2_host <diretorio-de-saida>
//

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "re-spirv/re-spirv.h"
#include "rt64_glsl_es.h"

// Blobs GLES embutidos no binario (headers gerados pelo canal M1.2).
#include "FullScreenVS.hlsl.glsl_es.h"
#include "PostBlendDitherNoiseAddPS.hlsl.glsl_es.h"
#include "RasterPSDynamic.hlsl.glsl_es.h"
#include "RasterPSDynamicMS.hlsl.glsl_es.h"
#include "RasterPSSpecConstant.hlsl.glsl_es.h"
#include "RasterPSSpecConstantFlat.hlsl.glsl_es.h"
#include "RasterPSSpecConstantFlatMS.hlsl.glsl_es.h"
#include "RasterPSSpecConstantMS.hlsl.glsl_es.h"
#include "RasterVSDynamic.hlsl.glsl_es.h"
#include "RasterVSSpecConstant.hlsl.glsl_es.h"
#include "RasterVSSpecConstantFlat.hlsl.glsl_es.h"
#include "TextureCopyPS.hlsl.glsl_es.h"

namespace {
    struct TestCase {
        const char *name;
        const char *stage;
        const char *data;
        size_t size;
        bool specialize; // true => caminho RasterShader (spec constants 0..4)
    };

#define GLES_CASE(NAME, STAGE, SYM, SPEC) { NAME, STAGE, SYM, SYM##_size, SPEC }

    // Os 6 primeiros sao os shaders do caminho `RasterShader` (spec constants + re-spirv);
    // os 6 ultimos sao do caminho `RasterShaderUber`/`ShaderLibrary` (blob direto).
    const TestCase Cases[] = {
        GLES_CASE("RasterVSSpecConstant",        "vert", RasterVSSpecConstantBlobGLSLES,        true),
        GLES_CASE("RasterVSSpecConstantFlat",    "vert", RasterVSSpecConstantFlatBlobGLSLES,    true),
        GLES_CASE("RasterPSSpecConstant",        "frag", RasterPSSpecConstantBlobGLSLES,        true),
        GLES_CASE("RasterPSSpecConstantMS",      "frag", RasterPSSpecConstantMSBlobGLSLES,      true),
        GLES_CASE("RasterPSSpecConstantFlat",    "frag", RasterPSSpecConstantFlatBlobGLSLES,    true),
        GLES_CASE("RasterPSSpecConstantFlatMS",  "frag", RasterPSSpecConstantFlatMSBlobGLSLES,  true),
        GLES_CASE("RasterVSDynamic",             "vert", RasterVSDynamicBlobGLSLES,             false),
        GLES_CASE("RasterPSDynamic",             "frag", RasterPSDynamicBlobGLSLES,             false),
        GLES_CASE("RasterPSDynamicMS",           "frag", RasterPSDynamicMSBlobGLSLES,           false),
        GLES_CASE("FullScreenVS",                "vert", FullScreenVSBlobGLSLES,                false),
        GLES_CASE("TextureCopyPS",               "frag", TextureCopyPSBlobGLSLES,               false),
        GLES_CASE("PostBlendDitherNoiseAddPS",   "frag", PostBlendDitherNoiseAddPSBlobGLSLES,   false),
    };

    // Mesmos valores que o `RasterShader` usa (otherMode.L/H, colorCombiner.L/H, flags.value).
    const uint32_t SpecConstantValues[5] = { 0x00504A50u, 0x00000080u, 0xFC127E24u, 0xFFFFF3F9u, 0x00000005u };

    bool validateESSL(const std::string &source, std::string &error) {
        if (source.empty()) {
            error = "empty output";
            return false;
        }
        if (source.rfind("#version 320 es", 0) != 0) {
            error = "output does not start with '#version 320 es'";
            return false;
        }
        if (source.find("precision highp float;") == std::string::npos) {
            error = "missing 'precision highp float;' (sanitizer fix #2/#3)";
            return false;
        }
        if (source.find("noperspective") != std::string::npos) {
            error = "'noperspective' still present (sanitizer fix #1)";
            return false;
        }
        if (source.find("GL_NV_gpu_shader5") != std::string::npos) {
            error = "GL_NV_gpu_shader5 regression";
            return false;
        }
        if (source.find("precision mediump float;") != std::string::npos) {
            error = "'precision mediump float;' still present";
            return false;
        }
        return true;
    }
}

int main(int argc, char **argv) {
    const std::string outDir = (argc > 1) ? argv[1] : ".";
    const char *outDirC = outDir.c_str();

    printf("M1.3 estagio 2 -- aceite host-side do caminho de runtime do canal GLES\n");
    printf("spec constants: omL=0x%08X omH=0x%08X ccL=0x%08X ccH=0x%08X flags=0x%08X\n\n",
        SpecConstantValues[0], SpecConstantValues[1], SpecConstantValues[2], SpecConstantValues[3], SpecConstantValues[4]);
    printf("%-26s %-5s %9s %9s %9s %9s %7s %-4s %s\n", "SHADER", "STAGE", "SPV_IN", "SPV_OPT", "ESSL", "RESPV_MS", "XC_MS", "OK", "NOTE");

    uint32_t total = 0;
    uint32_t failed = 0;
    size_t esslTotal = 0;
    double respvTotalMs = 0.0;
    double crossTotalMs = 0.0;

    for (const TestCase &testCase : Cases) {
        total++;

        const void *payload = testCase.data;
        size_t payloadSize = testCase.size;
        uint32_t spvInSize = uint32_t(testCase.size);
        uint32_t spvOptSize = 0;
        double respvMs = 0.0;
        double crossMs = 0.0;
        std::string note;
        std::string essl;

        std::vector<uint8_t> optimized;

        if (testCase.specialize) {
            respv::Shader shader;
            if (!shader.parse(testCase.data, testCase.size)) {
                note = "respv::Shader::parse failed";
            }
            else {
                std::vector<respv::SpecConstant> specConstants;
                for (uint32_t i = 0; i < 5; i++) {
                    specConstants.emplace_back(i, std::vector<uint32_t>{ SpecConstantValues[i] });
                }

                const auto respvStart = std::chrono::steady_clock::now();
                const bool runOK = respv::Optimizer::run(shader, specConstants.data(), uint32_t(specConstants.size()), optimized);
                const auto respvEnd = std::chrono::steady_clock::now();
                respvMs = std::chrono::duration<double, std::milli>(respvEnd - respvStart).count();

                if (!runOK || optimized.empty()) {
                    note = "respv::Optimizer::run failed";
                }
                else {
                    payload = optimized.data();
                    payloadSize = optimized.size();
                    spvOptSize = uint32_t(optimized.size());
                }
            }
        }
        else {
            spvOptSize = spvInSize;
        }

        if (note.empty()) {
            std::string error;
            const auto crossStart = std::chrono::steady_clock::now();
            const bool convertOK = RT64::convertSPIRVToGLSLES(payload, payloadSize, essl, &error);
            const auto crossEnd = std::chrono::steady_clock::now();
            crossMs = std::chrono::duration<double, std::milli>(crossEnd - crossStart).count();

            if (!convertOK) {
                note = "convertSPIRVToGLSLES failed: " + error;
            }
            else if (!validateESSL(essl, error)) {
                note = "ESSL invariant: " + error;
            }
        }

        const bool ok = note.empty();
        if (ok) {
            esslTotal += essl.size();
            respvTotalMs += respvMs;
            crossTotalMs += crossMs;

            char path[1024];
            snprintf(path, sizeof(path), "%s/%s.essl", outDirC, testCase.name);
            FILE *file = fopen(path, "wb");
            if (file == nullptr) {
                note = "cannot write output file";
            }
            else {
                fwrite(essl.data(), 1, essl.size(), file);
                fclose(file);
            }
        }
        else {
            failed++;
        }

        printf("%-26s %-5s %9u %9u %9u %9.2f %7.1f %-4s %s\n",
            testCase.name, testCase.stage, spvInSize, spvOptSize, uint32_t(essl.size()), respvMs, crossMs,
            (note.empty() ? "ok" : "FAIL"), note.c_str());
    }

    printf("\nshaders=%u ok=%u fail=%u essl_total=%zu B respv_total=%.1f ms cross_total=%.1f ms\n",
        total, total - failed, failed, esslTotal, respvTotalMs, crossTotalMs);
    return (failed == 0) ? 0 : 1;
}