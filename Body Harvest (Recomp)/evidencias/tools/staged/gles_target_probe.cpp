//
// gles_target_probe -- prova de execucao ON-TARGET (aarch64/QEMU) sem GPU.
//
// POR QUE ESTE ARQUIVO EXISTE (e por que ele nao e' o smoke test):
// o R36S nao tem EGL que funcione sem hardware. O rootfs do dArkOS aponta
// `libEGL.so.1 -> libMali.so` (blob ARM, exige GPU Mali real) e NAO contem o dispatcher
// GLVND; a unica lib EGL real e' `libEGL_mesa.so.0.0.0`, que e' uma lib VENDOR do GLVND
// (nao exporta eglGetDisplay/eglGetProcAddress -- comprovado por erro de link, ver
// evidencia). Portanto, sob QEMU, nao existe caminho para obter contexto GLES.
//
// O que RESTA verificavel no alvo, e que este probe cobre:
//   [0] o binario e' de fato aarch64 (auto-identificacao);
//   [1] o carregador gerado executa em aarch64 e, com resolvedor nulo, reporta os 358
//       entry points ausentes -- contrato de FALHA EXPLICITA e completa;
//   [2] o caminho de SUCESSO do carregador (358 resolvidos, 0 ausentes) tambem executa;
//   [3] a camada de interface (CreateGLESInterface/getDeviceNames/getCapabilities)
//       executa e declara shaderFormat = GLSL_ES.
//
// A validacao FUNCIONAL do backend (contexto real + clear + present + leitura de volta)
// e' feita pelo gles_smoke.cpp no HOST com Mesa/llvmpipe -- ver a evidencia do M2/s2.
//
// ============================== CORRECAO (2026-10-18) ==============================
// A afirmacao ACIMA de que o blob Mali "nao exporta eglGetDisplay/eglGetProcAddress"
// esta' ERRADA. Foi medida e refutada em 2026-10-18:
//   * `nm -D --defined-only libmali-bifrost-g31-rxp0-gbm.so` tem 1175 simbolos T e EXPORTA
//     eglGetDisplay, eglGetProcAddress, eglInitialize, eglCreateContext, eglChooseConfig,
//     eglMakeCurrent, eglCreateWindowSurface, eglSwapBuffers e o GBM inteiro
//     (gbm_create_device, gbm_surface_create, gbm_bo_create);
//   * sob QEMU contra a rootfs do device, o dlopen do blob resolve 15/15 entry points do
//     nucleo EGL (medido; ver PROBE egl_symbols_found=15/15).
// O que CONTINUA verdade e' apenas a parte do LINK: o blob nao tem SONAME e tem .dynsym
// malformado para o binutils ("dynsym local symbol at index 3 (>= sh_info of 3)"), logo
// NAO serve como biblioteca de link -- esse e' o risco R6 do plano, confirmado.
// A conclusao deste arquivo ("sob QEMU nao existe caminho para obter contexto GLES")
// permanece valida, mas por AUSENCIA DE GPU -- nao por ausencia de EGL.
// RAW: evidencias/m3_gles_probe/raw_offline.txt
//      evidencias/evidence_m3_gles_device_probe_20261018.md
// ==================================================================================
//

#include <cstdio>
#include <string>
#include <vector>

#include "plume_gles.h"
#include "plume_gles_gl.h"

namespace {
    int g_failures = 0;

    void check(bool condition, const char *what) {
        std::printf("[probe] %-66s %s\n", what, condition ? "OK" : "FALHOU");
        if (!condition) {
            g_failures++;
        }
    }

    void *nullResolver(const char *name) {
        (void)name;
        return nullptr;
    }

    // Resolvedor "de sucesso": devolve sempre um ponteiro NAO nulo. Os ponteiros nunca
    // sao CHAMADOS (o probe so' exercita load(), nao o GL), entao isso e' seguro e prova
    // o caminho de sucesso do carregador no alvo.
    int g_dummy = 0;

    void *fakeResolver(const char *name) {
        (void)name;
        return &g_dummy;
    }
}

int main() {
#if defined(__aarch64__)
    std::printf("[probe] arquitetura de compilacao = aarch64 (ponteiro de %zu bytes)\n", sizeof(void *));
    check(true, "[0] binario compilado para aarch64");
#else
    std::printf("[probe] arquitetura de compilacao = NAO-aarch64 (ponteiro de %zu bytes)\n", sizeof(void *));
    check(false, "[0] binario compilado para aarch64");
#endif

    // [1] Falha explicita: resolvedor nulo => 0 carregados e 358 reportados ausentes.
    const bool loadedWithNull = plume::gl::load(nullResolver);
    const std::vector<std::string> &missing = plume::gl::missing();
    std::printf("[probe] entry points ausentes com resolvedor nulo = %zu\n", missing.size());
    check((!loadedWithNull) && (missing.size() == 358),
          "[1] gl::load(nulo) == false e reporta os 358 entry points");

    // [2] Sucesso: resolvedor que responde a tudo => nenhum ausente.
    const bool loadedWithAll = plume::gl::load(fakeResolver);
    const std::vector<std::string> &missingAfter = plume::gl::missing();
    std::printf("[probe] entry points ausentes com resolvedor completo = %zu\n", missingAfter.size());
    check(loadedWithAll && missingAfter.empty(),
          "[2] gl::load(resolvedor completo) == true e 0 ausentes");

    // [3] Interface (nao toca em GL).
    plume::GLESSwapChainFunctions swapFunctions = {};
    std::unique_ptr<plume::RenderInterface> renderInterface =
        plume::CreateGLESInterface(nullptr, nullResolver, swapFunctions);

    check(renderInterface != nullptr, "[3] CreateGLESInterface executa no alvo");
    check((renderInterface != nullptr) && (renderInterface->getDeviceNames().size() == 1),
          "[3b] getDeviceNames() expoe exatamente 1 dispositivo");
    check((renderInterface != nullptr) &&
          (renderInterface->getCapabilities().shaderFormat == plume::RenderShaderFormat::GLSL_ES),
          "[3c] getCapabilities().shaderFormat == GLSL_ES");

    std::printf("[plume_gles probe] ===== %d checagem(ns) FALHARAM =====\n", g_failures);
    return (g_failures == 0) ? 0 : 1;
}