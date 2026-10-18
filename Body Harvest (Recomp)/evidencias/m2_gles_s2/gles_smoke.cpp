// RTLD_DEFAULT (usado como reserva do resolvedor) e' um simbolo GNU. O g++ ja' define
// _GNU_SOURCE por padrao; a guarda evita o aviso de redefinicao.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

//
// gles_smoke -- teste de fumaca do backend plume_gles (M2, sessao 2).
//
// Este arquivo faz o papel de CHAMADOR do backend (o que o SDL2 faz no R36S): cria o
// contexto, resolve os simbolos GL e fornece o swap. Usa EGL PURO -- e nao SDL -- para
// rodar tanto no host x86_64 quanto sob QEMU aarch64, sem depender de display.
//
// O que cada checagem PROVA:
//   [1]  contexto EGL + GLES 3.2 real (pbuffer) obtido; sem isso nada abaixo vale;
//   [2]  os 358 entry points resolvem pelo caminho que o backend usa;
//   [3]  CreateGLESInterface + createDevice (carrega o loader e consulta o contexto);
//   [4]  queue + command list + swapchain criados pelo CAMINHO DO BACKEND;
//   [5]  clear na FBO 0 (backbuffer) + present;
//   [6]  leitura de volta do pixel central: o clear REALMENTE chegou ao drawable;
//   [7]  textura + framebuffer + clear + resolveTexture + leitura de volta;
//   [8]  shutdown limpo (destrutores GL reais, com contexto ainda corrente).
//
// O passo [6] e' o aceite do M2 em forma VERIFICAVEL sem display: o "quadro" e' o
// conteudo do backbuffer, e le'-lo de volta e' a prova mais forte disponivel.
//
// NAO inclui <GLES3/gl3*.h>: todo simbolo GL vem do loader gerado (plume_gles_gl.h),
// exatamente como o backend faz. Assim o teste nao pode "escapar" do loader.
//

#include <EGL/egl.h>
#include <EGL/eglext.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>

#include "plume_gles.h"
#include "plume_gles_gl.h"

// O backend escreve `glClearColor(...)` etc. dentro de `namespace plume` graças a um
// using-directive local. Aqui fazemos o mesmo no escopo do arquivo de teste.
using namespace plume::gl;

namespace {
    int g_failures = 0;

    void check(bool condition, const char *what) {
        std::printf("[smoke] %-62s %s\n", what, condition ? "OK" : "FALHOU");
        if (!condition) {
            g_failures++;
        }
    }

    // Tolerancia de +-2 por canal: a conversao float->UNORM8 arredonda de forma que pode
    // diferir entre drivers (64 vs 63 para 0.25). Comparar exato seria testar o driver,
    // nao o backend.
    bool nearChannel(unsigned value, unsigned expected) {
        return (value + 2 >= expected) && (value <= expected + 2);
    }

    // Resolvedor de simbolos do HARNESS. Espelha o que o SDL faz no device: primeiro
    // eglGetProcAddress (correto para entry points de extensao/ES3) e, como reserva,
    // dlsym no objeto global (alguns drivers so' exportam o core pela DSO).
    void *resolveGL(const char *name) {
        void *pointer = reinterpret_cast<void *>(eglGetProcAddress(name));
        if (pointer == nullptr) {
            pointer = dlsym(RTLD_DEFAULT, name);
        }
        return pointer;
    }

    EGLDisplay g_display = EGL_NO_DISPLAY;
    EGLContext g_context = EGL_NO_CONTEXT;
    EGLSurface g_surface = EGL_NO_SURFACE;

    // Cria display + config + pbuffer + contexto ES 3.x e o torna corrente.
    bool createEGLContext(int width, int height) {
        // A plataforma "surfaceless" da Mesa permite contexto GLES sem X11 nem Wayland --
        // exatamente a situacao de um teste headless sob QEMU. Se o driver nao tiver a
        // extensao, cai para o display default (que funcionara' onde ha' display real).
        PFNEGLGETPLATFORMDISPLAYEXTPROC getPlatformDisplay =
            reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(eglGetProcAddress("eglGetPlatformDisplayEXT"));

        if (getPlatformDisplay != nullptr) {
            g_display = getPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, nullptr);
        }
        if (g_display == EGL_NO_DISPLAY) {
            g_display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        }
        if (g_display == EGL_NO_DISPLAY) {
            std::printf("[smoke]     eglGetDisplay/GetPlatformDisplay falhou\n");
            return false;
        }

        EGLint major = 0;
        EGLint minor = 0;
        if (eglInitialize(g_display, &major, &minor) != EGL_TRUE) {
            std::printf("[smoke]     eglInitialize falhou (erro 0x%X)\n", static_cast<unsigned>(eglGetError()));
            return false;
        }

        std::printf("[smoke]     EGL %d.%d, vendor=%s\n", major, minor,
                    eglQueryString(g_display, EGL_VENDOR));

        // Config: pbuffer 8/8/8/8 + depth 24, renderizavel por ES 3.
        const EGLint configAttributes[] = {
            EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
            EGL_RED_SIZE, 8,
            EGL_GREEN_SIZE, 8,
            EGL_BLUE_SIZE, 8,
            EGL_ALPHA_SIZE, 8,
            EGL_DEPTH_SIZE, 24,
            EGL_NONE
        };

        EGLConfig config = nullptr;
        EGLint configCount = 0;
        if ((eglChooseConfig(g_display, configAttributes, &config, 1, &configCount) != EGL_TRUE) ||
            (configCount == 0)) {
            std::printf("[smoke]     eglChooseConfig falhou (erro 0x%X)\n", static_cast<unsigned>(eglGetError()));
            return false;
        }

        const EGLint surfaceAttributes[] = {
            EGL_WIDTH, width,
            EGL_HEIGHT, height,
            EGL_NONE
        };
        g_surface = eglCreatePbufferSurface(g_display, config, surfaceAttributes);
        if (g_surface == EGL_NO_SURFACE) {
            std::printf("[smoke]     eglCreatePbufferSurface falhou (erro 0x%X)\n",
                        static_cast<unsigned>(eglGetError()));
            return false;
        }

        // EGL_CONTEXT_CLIENT_VERSION=3 entrega o ES 3.x mais alto disponivel no driver
        // (num blob 3.2, exatamente o alvo deste backend).
        const EGLint contextAttributes[] = {
            EGL_CONTEXT_CLIENT_VERSION, 3,
            EGL_NONE
        };
        g_context = eglCreateContext(g_display, config, EGL_NO_CONTEXT, contextAttributes);
        if (g_context == EGL_NO_CONTEXT) {
            std::printf("[smoke]     eglCreateContext(ES3) falhou (erro 0x%X)\n",
                        static_cast<unsigned>(eglGetError()));
            return false;
        }

        if (eglMakeCurrent(g_display, g_surface, g_surface, g_context) != EGL_TRUE) {
            std::printf("[smoke]     eglMakeCurrent falhou (erro 0x%X)\n", static_cast<unsigned>(eglGetError()));
            return false;
        }

        return true;
    }
}

int main() {
    const int width = 256;
    const int height = 256;

    const bool contextOK = createEGLContext(width, height);
    check(contextOK, "[1] contexto EGL + GLES (pbuffer 256x256) corrente");

    if (!contextOK) {
        std::printf("[smoke] ===== sem contexto: %d falha(s) =====\n", g_failures);
        return 1;
    }

    // Todo o trabalho que toca GL fica em escopos internos: assim os destrutores dos
    // recursos rodam com o contexto AINDA corrente (glDelete* sem contexto e' erro de API).
    {
        if (plume::gl::load(resolveGL)) {
            check(true, "[2] os 358 entry points resolvem (eglGetProcAddress + dlsym)");
        } else {
            const std::vector<std::string> &missing = plume::gl::missing();
            std::printf("[smoke]     %zu entry points NAO resolvidos; primeiros 10:\n", missing.size());
            for (size_t i = 0; i < missing.size() && i < 10; i++) {
                std::printf("[smoke]       ausente: %s\n", missing[i].c_str());
            }
            check(false, "[2] os 358 entry points resolvem (eglGetProcAddress + dlsym)");
        }

        // Nenhuma funcao de swap: modo headless. O swapchain degrada para glFinish() e
        // infere o tamanho pelo viewport do contexto -- comportamento documentado no header.
        const plume::GLESSwapChainFunctions swapFunctions = {};

        std::unique_ptr<plume::RenderInterface> renderInterface =
            plume::CreateGLESInterface(nullptr, resolveGL, swapFunctions);
        check(renderInterface != nullptr, "[3] CreateGLESInterface");

        std::unique_ptr<plume::RenderDevice> device = renderInterface->createDevice("");
        check(device != nullptr, "[3b] createDevice (carrega loader + consulta contexto)");

        if (device == nullptr) {
            std::printf("[smoke] ===== device nulo: %d falha(s) =====\n", g_failures);
            return 1;
        }

        const plume::GLESDevice *glesDevice = static_cast<const plume::GLESDevice *>(device.get());
        std::printf("[smoke]     GL_VERSION  = %s\n", glesDevice->glVersion.c_str());
        std::printf("[smoke]     GL_RENDERER = %s\n", glesDevice->glRenderer.c_str());
        std::printf("[smoke]     GL_VENDOR   = %s\n", glesDevice->glVendor.c_str());
        std::printf("[smoke]     GLSL        = %s\n", glesDevice->glShadingLanguageVersion.c_str());
        std::printf("[smoke]     maxTextureSize=%u maxColorAttachments=%u maxSamples=%u extBytes=%zu\n",
                    glesDevice->maxTextureSize, glesDevice->maxColorAttachments, glesDevice->maxSamples,
                    glesDevice->glExtensions.size());

        // As capacidades declaradas decidem o caminho de renderizacao do RT64: verificar as
        // tres que mais impactam (sem RT, sem descriptor indexing, triangle fan em core).
        const plume::RenderDeviceCapabilities &capabilities = device->getCapabilities();
        const plume::RenderDeviceDescription &description = device->getDescription();
        check((!description.name.empty()) && capabilities.triangleFan && (!capabilities.raytracing) &&
              (!capabilities.descriptorIndexing),
              "[3c] getCapabilities/getDescription coerentes com GLES 3.2");

        // ---- [4] Fila + command list + swapchain pelo caminho do backend ----
        std::unique_ptr<plume::RenderCommandQueue> queue =
            device->createCommandQueue(plume::RenderCommandListType::DIRECT);
        check(queue != nullptr, "[4] createCommandQueue(DIRECT)");

        std::unique_ptr<plume::RenderCommandList> commandList = queue->createCommandList();
        check(commandList != nullptr, "[4b] createCommandList");

        // RenderWindow vazio: este harness nao tem janela (caso headless).
        const plume::RenderWindow noWindow = {};
        std::unique_ptr<plume::RenderSwapChain> swapChain = queue->createSwapChain(
            plume::RenderSwapChainDesc(noWindow, plume::RenderFormat::R8G8B8A8_UNORM, 1));

        // O swapchain sem janela infere o tamanho pelo viewport corrente -- que o EGL
        // inicializa com o tamanho do drawable (256x256 do pbuffer). Se este assert passa,
        // o caminho "headless" do swapchain esta' correto.
        check((swapChain != nullptr) &&
              (swapChain->getWidth() == static_cast<uint32_t>(width)) &&
              (swapChain->getHeight() == static_cast<uint32_t>(height)),
              "[4c] createSwapChain (tamanho herdado do viewport do pbuffer)");

        check((swapChain != nullptr) && (swapChain->getTextureCount() == 1) &&
              (swapChain->getTexture(0) != nullptr),
              "[4d] swapchain expoe 1 textura de backbuffer");

        // ---- [5]/[6] ACEITE M2: clear no backbuffer + present + prova por leitura ----
        // Cor de clear escolhida para ser inequivoca na leitura: ~64/128/191.
        commandList->begin();
        commandList->setFramebuffer(nullptr);   // nullptr == FBO 0 == backbuffer do pbuffer
        // A sobrecarga de 1 argumento (por referencia) evita ter que tirar endereco de um
        // temporario -- `&RenderViewport(...)` nem compila.
        commandList->setViewports(plume::RenderViewport(0.0f, 0.0f, static_cast<float>(width),
                                                        static_cast<float>(height)));
        commandList->clearColor(0, plume::RenderColor(0.25f, 0.50f, 0.75f, 1.0f));
        commandList->end();

        queue->executeCommandLists(commandList.get());
        check(swapChain->present(0, nullptr, 0), "[5] command list executado + present()");

        unsigned char pixel[4] = { 0, 0, 0, 0 };
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glReadPixels(width / 2, height / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);

        std::printf("[smoke]     pixel central do backbuffer = RGBA(%u,%u,%u,%u)\n",
                    static_cast<unsigned>(pixel[0]), static_cast<unsigned>(pixel[1]),
                    static_cast<unsigned>(pixel[2]), static_cast<unsigned>(pixel[3]));

        check(nearChannel(pixel[0], 64) && nearChannel(pixel[1], 128) && nearChannel(pixel[2], 191) &&
              (pixel[3] >= 253),
              "[6] ACEITE M2: o clear chegou ao backbuffer (RGB ~64/128/191)");

        // ---- [7] Recursos: textura + framebuffer + clear + resolveTexture ----
        const uint32_t textureSize = 64;
        plume::RenderTextureDesc textureDesc = plume::RenderTextureDesc::Texture(
            plume::RenderTextureDimension::TEXTURE_2D, textureSize, textureSize, 1, 1, 1,
            plume::RenderFormat::R8G8B8A8_UNORM, plume::RenderTextureFlag::RENDER_TARGET);

        std::unique_ptr<plume::RenderTexture> sourceTexture = device->createTexture(textureDesc);
        std::unique_ptr<plume::RenderTexture> resolvedTexture = device->createTexture(textureDesc);
        check((sourceTexture != nullptr) && (resolvedTexture != nullptr),
              "[7] createTexture x2 (64x64 RGBA8, glTexStorage2D imutavel)");

        const plume::RenderTexture *sourceAttachments[1] = { sourceTexture.get() };
        std::unique_ptr<plume::RenderFramebuffer> sourceFramebuffer =
            device->createFramebuffer(plume::RenderFramebufferDesc(sourceAttachments, 1));
        check(sourceFramebuffer != nullptr, "[7b] createFramebuffer(color=textureA)");

        commandList->begin();
        commandList->setFramebuffer(sourceFramebuffer.get());
        commandList->setViewports(plume::RenderViewport(0.0f, 0.0f, static_cast<float>(textureSize),
                                                       static_cast<float>(textureSize)));
        commandList->clearColor(0, plume::RenderColor(1.0f, 0.0f, 0.0f, 1.0f));
        // resolveTexture usa glBlitFramebuffer com FBOs temporarios (ver backend): aqui ele
        // leva o vermelho da textura A para a textura B.
        commandList->resolveTexture(resolvedTexture.get(), sourceTexture.get());
        commandList->end();
        queue->executeCommandLists(commandList.get());

        // Para LER a textura B ela precisa estar anexada a um framebuffer.
        const plume::RenderTexture *resolvedAttachments[1] = { resolvedTexture.get() };
        std::unique_ptr<plume::RenderFramebuffer> resolvedFramebuffer =
            device->createFramebuffer(plume::RenderFramebufferDesc(resolvedAttachments, 1));

        commandList->begin();
        commandList->setFramebuffer(resolvedFramebuffer.get());
        commandList->end();
        queue->executeCommandLists(commandList.get());

        unsigned char resolvedPixel[4] = { 0, 0, 0, 0 };
        glReadPixels(static_cast<int>(textureSize / 2), static_cast<int>(textureSize / 2), 1, 1, GL_RGBA,
                     GL_UNSIGNED_BYTE, resolvedPixel);
        std::printf("[smoke]     pixel resolvido na textura B = RGBA(%u,%u,%u,%u)\n",
                    static_cast<unsigned>(resolvedPixel[0]), static_cast<unsigned>(resolvedPixel[1]),
                    static_cast<unsigned>(resolvedPixel[2]), static_cast<unsigned>(resolvedPixel[3]));

        check(nearChannel(resolvedPixel[0], 255) && (resolvedPixel[1] <= 2) && (resolvedPixel[2] <= 2),
              "[7c] resolveTexture levou o vermelho de A para B");

        // Saude geral: ate' aqui nenhuma chamada do backend pode ter gerado erro de API.
        const GLenum glError = glGetError();
        std::printf("[smoke]     glGetError() = 0x%X (0 == GL_NO_ERROR)\n", static_cast<unsigned>(glError));
        check(glError == GL_NO_ERROR, "[7d] nenhum erro de API GL acumulado");
    }

    // O contexto e' liberado DEPOIS dos destrutores acima (que chamam glDelete*).
    const bool released =
        eglMakeCurrent(g_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT) == EGL_TRUE;
    if (released) {
        eglTerminate(g_display);
    }
    check(released, "[8] contexto liberado apos os destrutores GL");

    std::printf("[plume_gles smoke] ===== %d checagem(ns) FALHARAM =====\n", g_failures);
    return (g_failures == 0) ? 0 : 1;
}