#!/usr/bin/env python3
#
# M2-GLES -- gate RT64_GLES_BACKEND: integra o backend OpenGL ES 3.2 (plume_gles)
# ao RT64 e liga GraphicsAPI::GLES na configuracao, no switch de criacao da
# interface e na criacao da janela SDL.
#
# Uso:
#   python3 m2_gles_gate_apply.py check    # so relata o estado (nao escreve nada)
#   python3 m2_gles_gate_apply.py apply    # aplica (backup + md5; idempotente)
#   python3 m2_gles_gate_apply.py revert   # restaura os originais dos backups
#
# Disciplina (mesma dos scripts do M1): cada substituicao tem que casar EXATAMENTE
# uma vez; qualquer ambiguidade ABORTA sem escrever nada. Backup e md5 antes/depois
# ficam em /root/bhrecomp/m2_gles_gate_20261018/.
#
import hashlib
import json
import os
import shutil
import sys

ROOT = "/root/bhrecomp"
WORK = os.path.join(ROOT, "m2_gles_gate_20261018")
BACKUP = os.path.join(WORK, "backups")
MANIFEST = os.path.join(WORK, "manifest.json")


def md5(path):
    with open(path, "rb") as handle:
        return hashlib.md5(handle.read()).hexdigest()


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def backup_path(rel):
    return os.path.join(BACKUP, rel.replace("/", "__"))

EDITS = []


def add(rel, tag, old, new):
    EDITS.append((rel, tag, old, new))


# ---------------------------------------------------------------------------
# 1) plume/CMakeLists.txt -- compila o backend somente com o gate ligado.
# ---------------------------------------------------------------------------
add(
    "lib/rt64/src/contrib/plume/CMakeLists.txt",
    "plume_cmake_sources",
    r"""# Basic source files that are always included
set(PLUME_SOURCES
    plume_vulkan.cpp
    plume_vulkan.h
)
""",
    r"""# M2-GLES -- backend OpenGL ES 3.2 (plume_gles) para o R36S / Mali-G31.
#
# GATE: default OFF -- com OFF o grafo de build fica identico ao de DX/VK/MSL
# (nenhum objeto plume_gles* e' compilado). Ver docs/PLANO_BACKEND_GLES_R36S.md.
# Requer o canal de shaders GLES do RT64 (RT64_GLSL_ES_SHADERS=ON): este backend
# declara shaderFormat = RenderShaderFormat::GLSL_ES e consome os blobs
# *BlobGLSLES em runtime via spirv-cross (M1.2/M1.3).
# A variavel vive na cache do projeto -- o add_subdirectory compartilha a cache com
# lib/rt64/CMakeLists.txt, que declara o mesmo option para o codigo do RT64.
option(RT64_GLES_BACKEND "Compila o backend OpenGL ES 3.2 de plume (plume_gles)" OFF)

# Basic source files that are always included
set(PLUME_SOURCES
    plume_vulkan.cpp
    plume_vulkan.h
)

if(RT64_GLES_BACKEND)
    list(APPEND PLUME_SOURCES
        plume_gles.cpp
        plume_gles.h
        plume_gles_gl.cpp
        plume_gles_gl.h
    )
    # O backend nao inclui <SDL.h> nem <GLES3/*.h>: os 358 entry points vem do
    # carregador gerado (plume_gles_gl.*). Nada extra a linkar -- nenhum
    # -lGLESv2/-lEGL (mesma politica do vkprobe no M0).
endif()
""",
)

add(
    "lib/rt64/src/contrib/plume/CMakeLists.txt",
    "plume_cmake_status",
    r"""message(STATUS "Plume - Building with backends: Vulkan=1 Metal=${APPLE} D3D12=${WIN32}")""",
    r"""message(STATUS "Plume - Building with backends: Vulkan=1 Metal=${APPLE} D3D12=${WIN32} GLES=${RT64_GLES_BACKEND}")""",
)

# ---------------------------------------------------------------------------
# 2) lib/rt64/CMakeLists.txt -- declara o gate e define RT64_GLES_BACKEND no alvo.
# ---------------------------------------------------------------------------
add(
    "lib/rt64/CMakeLists.txt",
    "rt64_cmake_option",
    r"""option(RT64_GLSL_ES_SHADERS "Gera o canal GLES (SPIR-V com -D HLSL_GLES + validacao ESSL 3.20)" OFF)
""",
    r"""option(RT64_GLSL_ES_SHADERS "Gera o canal GLES (SPIR-V com -D HLSL_GLES + validacao ESSL 3.20)" OFF)

# M2-GLES -- backend OpenGL ES 3.2 (plume_gles) INTEGRADO ao RT64.
#
# GATE: default OFF -> builds DX/VK/MSL permanecem byte-identicos (nenhum objeto
# plume_gles* e nenhum -DRT64_GLES_BACKEND). Ver docs/PLANO_BACKEND_GLES_R36S.md.
#
# Com ON:
#   * src/contrib/plume/CMakeLists.txt (mesma variavel de cache) compila
#     plume_gles.{cpp,h} + plume_gles_gl.{cpp,h} dentro do alvo plume;
#   * -DRT64_GLES_BACKEND no alvo rt64, habilitando:
#       - GraphicsAPI::GLES em src/common/rt64_user_configuration.{h,cpp};
#       - o caso do switch em src/hle/rt64_application.cpp (com criacao do
#         contexto GL via SDL_GL_CreateContext);
#       - SDL_WINDOW_OPENGL em src/hle/rt64_application_window.cpp.
# O canal de shaders (RT64_GLSL_ES_SHADERS) e' independente, mas sem ele o backend
# nao tem blobs ESSL para consumir -- aviso explicito logo abaixo.
option(RT64_GLES_BACKEND "Integra o backend OpenGL ES 3.2 (plume_gles) ao RT64" OFF)

if (RT64_GLES_BACKEND AND NOT RT64_GLSL_ES_SHADERS)
    message(WARNING "RT64_GLES_BACKEND=ON com RT64_GLSL_ES_SHADERS=OFF: o backend GLES nao tera blobs GLSL ES e os shaders falharao em runtime. Habilite os dois.")
endif()
""",
)

add(
    "lib/rt64/CMakeLists.txt",
    "rt64_cmake_define",
    r"""target_link_libraries(rt64 plume)
""",
    r"""target_link_libraries(rt64 plume)

# M2-GLES -- liga o codigo condicional do backend GLES dentro do RT64 (enum
# GraphicsAPI::GLES, caso do switch de criacao da interface e janela OpenGL).
# PRIVATE: nenhum consumidor externo do rt64 precisa saber disto.
if (RT64_GLES_BACKEND)
    target_compile_definitions(rt64 PRIVATE RT64_GLES_BACKEND)
endif()
""",
)

# ---------------------------------------------------------------------------
# 3) plume_gles.h -- corrige o contrato de CreateGLESInterface (nao cria contexto).
# ---------------------------------------------------------------------------
add(
    "lib/rt64/src/contrib/plume/plume_gles.h",
    "plume_gles_h_contract",
    r"""    // Cria o contexto GL (chamar com o SDL_Window* ja existente) e devolve a
    // interface. `window` tambem e usado para o swapchain. `procResolver` e'
    // usado para carregar os 358 entry points (na pratica SDL_GL_GetProcAddress).""",
    r"""    // Cria a interface. NAO cria o contexto GL: ele precisa JA estar corrente,
    // porque GLESDevice resolve os 358 entry points do contexto ATUAL.
    // Quem cria o contexto e' o chamador (SDL_GL_CreateContext no R36S -- ver
    // RT64::CreateGLESInterfaceWrapper em rt64_application.cpp; EGL/pbuffer no
    // gles_smoke.cpp). `window` e' usado apenas pelo swapchain e `procResolver`
    // e' o resolvedor (na pratica SDL_GL_GetProcAddress).""",
)

# ---------------------------------------------------------------------------
# 4) rt64_user_configuration.{h,cpp} -- GraphicsAPI::GLES + suporte condicional.
# ---------------------------------------------------------------------------
add(
    "lib/rt64/src/common/rt64_user_configuration.h",
    "config_h_enum",
    r"""        enum class GraphicsAPI {
            D3D12,
            Vulkan,
            Metal,
            Automatic,
            OptionCount
        };""",
    r"""        enum class GraphicsAPI {
            D3D12,
            Vulkan,
            Metal,
            // M2-GLES -- backend OpenGL ES 3.2 (Plume). So' e' selecionavel quando o
            // gate RT64_GLES_BACKEND esta ligado (ver isGraphicsAPISupported).
            // Inserido ANTES de Automatic para a lista da UI ficar coerente; a
            // serializacao JSON e' por NOME, logo configs salvas nao sao afetadas.
            // ATENCAO: a ordem aqui tem que casar com o Combo de rt64_state.cpp.
            GLES,
            Automatic,
            OptionCount
        };""",
)

add(
    "lib/rt64/src/common/rt64_user_configuration.h",
    "config_h_json",
    r"""        { UserConfiguration::GraphicsAPI::Metal, "Metal" },
        { UserConfiguration::GraphicsAPI::Automatic, "Automatic" },""",
    r"""        { UserConfiguration::GraphicsAPI::Metal, "Metal" },
        { UserConfiguration::GraphicsAPI::GLES, "GLES" },
        { UserConfiguration::GraphicsAPI::Automatic, "Automatic" },""",
)

add(
    "lib/rt64/src/common/rt64_user_configuration.cpp",
    "config_cpp_supported",
    r"""    bool UserConfiguration::isGraphicsAPISupported(GraphicsAPI graphicsAPI) {
#   if defined(_WIN32)""",
    r"""    bool UserConfiguration::isGraphicsAPISupported(GraphicsAPI graphicsAPI) {
        // M2-GLES -- GLES so' existe quando o backend foi compilado de fato (gate
        // RT64_GLES_BACKEND). Sem ele, uma config salva com "GLES" cai em Automatic
        // via validate(), em vez de tentar um backend que nao esta no binario.
        if (graphicsAPI == GraphicsAPI::GLES) {
#       ifdef RT64_GLES_BACKEND
            return true;
#       else
            return false;
#       endif
        }

#   if defined(_WIN32)""",
)

# ---------------------------------------------------------------------------
# 5) rt64_application_window.{h,cpp} -- janela OpenGL + contexto GL.
# ---------------------------------------------------------------------------
add(
    "lib/rt64/src/hle/rt64_application_window.h",
    "window_h_setup",
    r"""        void setup(const char *windowTitle, Listener *listener);""",
    r"""        // M2-GLES -- useOpenGL faz a janela nascer com SDL_WINDOW_OPENGL (o SDL2
        // exige essa flag para depois aceitar SDL_GL_CreateContext) e suprime
        // SDL_WINDOW_VULKAN. Ver Application::setup() em rt64_application.cpp.
        void setup(const char *windowTitle, Listener *listener, bool useOpenGL = false);""",
)

add(
    "lib/rt64/src/hle/rt64_application_window.h",
    "window_h_members",
    r"""        SDL_Window *sdlWindow = nullptr;
        SDL_EventFilter sdlEventFilterStored = nullptr;""",
    r"""        SDL_Window *sdlWindow = nullptr;
        // M2-GLES -- contexto GL criado pelo wrapper do RT64 (SDL_GL_CreateContext).
        // Fica aqui para sobreviver a vida da janela; nullptr nos demais backends.
        SDL_GLContext glContext = nullptr;
        bool useOpenGL = false;
        SDL_EventFilter sdlEventFilterStored = nullptr;""",
)

add(
    "lib/rt64/src/hle/rt64_application_window.cpp",
    "window_cpp_setup_sig",
    r"""    void ApplicationWindow::setup(const char *windowTitle, Listener *listener) {
        assert(windowTitle != nullptr);
""",
    r"""    void ApplicationWindow::setup(const char *windowTitle, Listener *listener, bool useOpenGL) {
        assert(windowTitle != nullptr);

        // M2-GLES -- guardado para a criacao do contexto GL (wrapper no RT64) e para
        // a limpeza em ~ApplicationWindow().
        this->useOpenGL = useOpenGL;
""",
)

add(
    "lib/rt64/src/hle/rt64_application_window.cpp",
    "window_cpp_flags",
    r"""        // Create window.
        uint32_t flags = SDL_WINDOW_RESIZABLE;
        # if defined(__APPLE__)
        flags |= SDL_WINDOW_METAL;
        # elif defined(RT64_SDL_WINDOW_VULKAN)
        flags |= SDL_WINDOW_VULKAN;
        #endif
""",
    r"""        // Create window.
        uint32_t flags = SDL_WINDOW_RESIZABLE;
        # if defined(__APPLE__)
        flags |= SDL_WINDOW_METAL;
        # elif defined(RT64_SDL_WINDOW_VULKAN)
        // M2-GLES -- SDL_WINDOW_VULKAN e SDL_WINDOW_OPENGL sao mutuamente exclusivos:
        // a janela do GLES nao pode pedir surface Vulkan.
        if (!useOpenGL) {
            flags |= SDL_WINDOW_VULKAN;
        }
        #endif
        if (useOpenGL) {
            flags |= SDL_WINDOW_OPENGL;
        }
""",
)

add(
    "lib/rt64/src/hle/rt64_application_window.cpp",
    "window_cpp_dtor",
    r"""    ApplicationWindow::~ApplicationWindow() {
        if (HookedApplicationWindow == this) {
            HookedApplicationWindow = nullptr;
        }

#   ifdef _WIN32
        if (windowHook != nullptr) {
            UnhookWindowsHookEx(windowHook);
        }
#   endif
    }
""",
    r"""    ApplicationWindow::~ApplicationWindow() {
        if (HookedApplicationWindow == this) {
            HookedApplicationWindow = nullptr;
        }

#   ifdef _WIN32
        if (windowHook != nullptr) {
            UnhookWindowsHookEx(windowHook);
        }
#   endif

        // M2-GLES -- o contexto GL morre com a janela. Guardado por
        // SDL_WasInit(SDL_INIT_VIDEO) porque o video pode ja' ter sido finalizado
        // (mesmo criterio usado em setup() para achar o sdlWindow).
        if ((glContext != nullptr) && SDL_WasInit(SDL_INIT_VIDEO)) {
            SDL_GL_DeleteContext(glContext);
            glContext = nullptr;
        }
    }
""",
)

# ---------------------------------------------------------------------------
# 6) rt64_application.cpp -- include, ponte SDL<->GLES, caso do switch, janela, inspector.
# ---------------------------------------------------------------------------
add(
    "lib/rt64/src/hle/rt64_application.cpp",
    "app_cpp_include",
    r"""#include "common/rt64_dynamic_libraries.h"
#include "common/rt64_elapsed_timer.h"
""",
    r"""#include "common/rt64_dynamic_libraries.h"
#include "common/rt64_elapsed_timer.h"
#ifdef RT64_GLES_BACKEND
// M2-GLES -- backend GLES + SDL (criacao do contexto GL). O gate impede que estes
// headers entrem em builds sem o backend.
#include "SDL.h"
#include "plume_gles.h"
#endif
""",
)

add(
    "lib/rt64/src/hle/rt64_application.cpp",
    "app_cpp_wrapper",
    r"""    static std::unique_ptr<RenderInterface> CreateVulkanInterfaceWrapper(RenderWindow renderWindow) {
#ifdef RT64_SDL_WINDOW_VULKAN
        return plume::CreateVulkanInterface(renderWindow);
#else
        return plume::CreateVulkanInterface();
#endif
    }
""",
    r"""    static std::unique_ptr<RenderInterface> CreateVulkanInterfaceWrapper(RenderWindow renderWindow) {
#ifdef RT64_SDL_WINDOW_VULKAN
        return plume::CreateVulkanInterface(renderWindow);
#else
        return plume::CreateVulkanInterface();
#endif
    }

#ifdef RT64_GLES_BACKEND
    // M2-GLES -- ponte SDL <-> backend GLES. O backend NAO conhece SDL (ver o
    // cabecalho de plume_gles.h): ele recebe o resolvedor de entry points e os 4
    // ponteiros de apresentacao. Este TU e' o unico lugar do RT64 que fala SDL_GL.
    static void *glesProcResolver(const char *name) {
        return SDL_GL_GetProcAddress(name);
    }

    static void glesSwapWindow(void *window) {
        SDL_GL_SwapWindow(static_cast<SDL_Window *>(window));
    }

    static void glesGetWindowSize(void *window, int *width, int *height) {
        SDL_GL_GetDrawableSize(static_cast<SDL_Window *>(window), width, height);
    }

    static void glesSetSwapInterval(int interval) {
        SDL_GL_SetSwapInterval(interval);
    }

    static uint32_t glesGetDisplayRefreshRate(void *window) {
        SDL_DisplayMode mode;
        const int displayIndex = SDL_GetWindowDisplayIndex(static_cast<SDL_Window *>(window));
        if ((displayIndex >= 0) && (SDL_GetCurrentDisplayMode(displayIndex, &mode) == 0)) {
            return static_cast<uint32_t>(mode.refresh_rate);
        }

        return 0;
    }

    // Cria o contexto OpenGL ES 3.2 da janela e devolve a interface de renderizacao.
    // A janela precisa ter sido criada com SDL_WINDOW_OPENGL (useOpenGL em
    // ApplicationWindow::setup). Devolver nullptr aqui e' erro explicito e o
    // chamador reporta "Unable to initialize the OpenGL ES graphics API".
    static std::unique_ptr<RenderInterface> CreateGLESInterfaceWrapper(ApplicationWindow *appWindow) {
        if (appWindow->sdlWindow == nullptr) {
            fprintf(stderr, "GLES: janela SDL ausente -- nao ha onde criar o contexto.\n");
            return nullptr;
        }

        // ES 3.2 via EGL (o R36S nao tem GL desktop). O backend exige os 358 entry
        // points do ES 3.2 -- sem eles GLESDevice aborta de proposito (ver M0/M2).
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_EGL, 1);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 2);
        SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);

        appWindow->glContext = SDL_GL_CreateContext(appWindow->sdlWindow);
        if (appWindow->glContext == nullptr) {
            fprintf(stderr, "GLES: falha ao criar contexto OpenGL ES 3.2: %s\n", SDL_GetError());
            return nullptr;
        }

        if (SDL_GL_MakeCurrent(appWindow->sdlWindow, appWindow->glContext) != 0) {
            fprintf(stderr, "GLES: falha ao tornar o contexto corrente: %s\n", SDL_GetError());
            SDL_GL_DeleteContext(appWindow->glContext);
            appWindow->glContext = nullptr;
            return nullptr;
        }

        // Vsync ligado por padrao: em 640x480 no Mali-G31 apresentar sem sincronia
        // so' queima CPU. O swapchain do backend sabe alternar isto em runtime.
        if (SDL_GL_SetSwapInterval(1) != 0) {
            fprintf(stderr, "GLES: aviso -- nao foi possivel ligar o vsync: %s\n", SDL_GetError());
        }

        plume::GLESSwapChainFunctions swapFunctions;
        swapFunctions.swapWindow = &glesSwapWindow;
        swapFunctions.getWindowSize = &glesGetWindowSize;
        swapFunctions.setSwapInterval = &glesSetSwapInterval;
        swapFunctions.getDisplayRefreshRate = &glesGetDisplayRefreshRate;

        return plume::CreateGLESInterface(appWindow->sdlWindow, &glesProcResolver, swapFunctions);
    }
#endif
""",
)

add(
    "lib/rt64/src/hle/rt64_application.cpp",
    "app_cpp_switch",
    r"""            case UserConfiguration::GraphicsAPI::Vulkan:
                renderInterface = CreateVulkanInterfaceWrapper(appWindow->windowHandle);
                break;
            default:
                fprintf(stderr, "Unknown Graphics API specified in configuration.\n");
                return SetupResult::InvalidGraphicsAPI;
            }
""",
    r"""            case UserConfiguration::GraphicsAPI::Vulkan:
                renderInterface = CreateVulkanInterfaceWrapper(appWindow->windowHandle);
                break;
            case UserConfiguration::GraphicsAPI::GLES:
#ifdef RT64_GLES_BACKEND
                renderInterface = CreateGLESInterfaceWrapper(appWindow.get());
                if (renderInterface == nullptr) {
                    fprintf(stderr, "Unable to initialize the OpenGL ES graphics API.\n");
                }
                break;
#else
                fprintf(stderr, "OpenGL ES is not supported in this build. Please select a different Graphics API.\n");
                return SetupResult::InvalidGraphicsAPI;
#endif
            default:
                fprintf(stderr, "Unknown Graphics API specified in configuration.\n");
                return SetupResult::InvalidGraphicsAPI;
            }
""",
)

add(
    "lib/rt64/src/hle/rt64_application.cpp",
    "app_cpp_window",
    r"""        else {
            appWindow->setup(windowTitle, this);
        }
""",
    r"""        else {
            // M2-GLES -- a janela tem que nascer com SDL_WINDOW_OPENGL quando a API
            // resolvida for GLES (o SDL2 exige a flag para aceitar SDL_GL_CreateContext
            // depois). resolveGraphicsAPI e' puro (sem efeito colateral), logo resolver
            // aqui devolve o MESMO valor que seria' usado logo abaixo.
            const bool windowUsesOpenGL = (UserConfiguration::resolveGraphicsAPI(userConfig.graphicsAPI) == UserConfiguration::GraphicsAPI::GLES);
            appWindow->setup(windowTitle, this, windowUsesOpenGL);
        }
""",
)

add(
    "lib/rt64/src/hle/rt64_application.cpp",
    "app_cpp_inspector",
    r"""                const std::lock_guard lock(presentQueue->inspectorMutex);
                if (presentQueue->inspector == nullptr) {
                    presentQueue->inspector = std::make_unique<Inspector>(device.get(), swapChain.get(), chosenGraphicsAPI, appWindow->sdlWindow);
""",
    r"""                const std::lock_guard lock(presentQueue->inspectorMutex);
                if (presentQueue->inspector == nullptr) {
                    // M2-GLES -- o Inspector usa os backends ImGui do RT64 (DX12/Vulkan).
                    // No GLES nao existe backend ImGui: criar o Inspector deixaria um
                    // objeto pela metade (o construtor dele faz assert(false) no default).
                    // Falha explicita e nomeada, em vez de inspector silenciosamente vazio.
                    if (chosenGraphicsAPI == UserConfiguration::GraphicsAPI::GLES) {
                        fprintf(stderr, "Inspector is not available: the GLES backend has no ImGui implementation yet.\n");
                        break;
                    }

                    presentQueue->inspector = std::make_unique<Inspector>(device.get(), swapChain.get(), chosenGraphicsAPI, appWindow->sdlWindow);
""",
)

# ---------------------------------------------------------------------------
# 7) rt64_state.cpp -- Combo posicional (ordem do enum) + rotulo do inspector.
# ---------------------------------------------------------------------------
add(
    "lib/rt64/src/hle/rt64_state.cpp",
    "state_cpp_combo",
    r"""                    genConfigChanged = ImGui::Combo("Graphics API", reinterpret_cast<int *>(&userConfig.graphicsAPI), "D3D12\0Vulkan\0Metal\0Automatic\0") || genConfigChanged;""",
    r"""                    // M2-GLES -- a ORDEM desta lista casa com o enum GraphicsAPI (GLES
                    // entrou antes de Automatic): o ImGui::Combo e' posicional.
                    genConfigChanged = ImGui::Combo("Graphics API", reinterpret_cast<int *>(&userConfig.graphicsAPI), "D3D12\0Vulkan\0Metal\0GLES\0Automatic\0") || genConfigChanged;""",
)

add(
    "lib/rt64/src/hle/rt64_state.cpp",
    "state_cpp_label",
    r"""                    case UserConfiguration::GraphicsAPI::Metal:
                        ImGui::Text("Graphics API: Metal");
                        break;
""",
    r"""                    case UserConfiguration::GraphicsAPI::Metal:
                        ImGui::Text("Graphics API: Metal");
                        break;
                    case UserConfiguration::GraphicsAPI::GLES:
                        ImGui::Text("Graphics API: OpenGL ES");
                        break;
""",
)

# ---------------------------------------------------------------------------
# 8) Definicao global do gate + janela OpenGL no main.cpp do port.
#
# Por que: quem cria a janela SDL e' src/main/main.cpp (ela e' entregue ao RT64 via
# WindowHandle), e o SDL2 aceita apenas UMA flag de backend grafico por janela
# (SDL_video.c: "Conflicting window flags specified" se OPENGL/VULKAN/METAL se
# misturarem). Logo a flag precisa ser escolhida ANTES de o RT64 ler a configuracao
# -- e o main.cpp precisa saber se o backend GLES existe (define global).
# ---------------------------------------------------------------------------
add(
    "CMakeLists.txt",
    "root_cmake_gles_define",
    r"""add_subdirectory(${CMAKE_SOURCE_DIR}/lib/rt64 ${CMAKE_BINARY_DIR}/rt64)
""",
    r"""add_subdirectory(${CMAKE_SOURCE_DIR}/lib/rt64 ${CMAKE_BINARY_DIR}/rt64)

# M2-GLES -- o proprio port (BodyHarvestRecompiled) precisa saber se o backend GLES
# foi compilado: quem cria a JANELA SDL e' src/main/main.cpp e o SDL2 aceita apenas
# UMA flag de backend grafico por janela (SDL_video.c: "Conflicting window flags
# specified" quando OPENGL/VULKAN/METAL se misturam). Mesma variavel de cache
# declarada em lib/rt64/CMakeLists.txt.
if (RT64_GLES_BACKEND)
    add_compile_definitions("RT64_GLES_BACKEND")
endif()
""",
)

add(
    "src/main/main.cpp",
    "main_cpp_gles_window",
    r"""SDL_Window* window;

ultramodern::renderer::WindowHandle create_window(ultramodern::gfx_callbacks_t::gfx_data_t) {
    uint32_t flags = SDL_WINDOW_RESIZABLE;

#if defined(__APPLE__)
    flags |= SDL_WINDOW_METAL;
#elif defined(RT64_SDL_WINDOW_VULKAN)
    flags |= SDL_WINDOW_VULKAN;
#endif
""",
    r"""SDL_Window* window;

#ifdef RT64_GLES_BACKEND
// M2-GLES -- escolha da flag de backend grafico da janela.
//
// O SDL2 aceita APENAS UMA entre SDL_WINDOW_OPENGL/METAL/VULKAN por janela
// (SDL_video.c: "Conflicting window flags specified"), e esta janela e' criada
// AQUI e so' depois entregue ao RT64 (WindowHandle) -- portanto a flag tem que ser
// decidida antes de o RT64 ler a configuracao. Quem conhece o alvo e' o launcher do
// port, que exporta BH_GRAPHICS_API=gles (ver BodyHarvest.sh).
static bool usesOpenGLWindow() {
    const char *api = SDL_getenv("BH_GRAPHICS_API");
    if (api == nullptr) {
        return false;
    }

    return (SDL_strcasecmp(api, "gles") == 0) || (SDL_strcasecmp(api, "opengl") == 0) || (SDL_strcasecmp(api, "gl") == 0);
}
#endif

ultramodern::renderer::WindowHandle create_window(ultramodern::gfx_callbacks_t::gfx_data_t) {
    uint32_t flags = SDL_WINDOW_RESIZABLE;

#if defined(__APPLE__)
    flags |= SDL_WINDOW_METAL;
#elif defined(RT64_SDL_WINDOW_VULKAN)
#   ifdef RT64_GLES_BACKEND
    flags |= usesOpenGLWindow() ? SDL_WINDOW_OPENGL : SDL_WINDOW_VULKAN;
#   else
    flags |= SDL_WINDOW_VULKAN;
#   endif
#endif
""",
)

# ---------------------------------------------------------------------------
# Sondas de idempotencia.
#
# Um `old not in text` NAO serve como "ja aplicado": em 6 destes edits o texto
# novo CONTEM o antigo como substring (ex.: o bloco do PLUME_SOURCES e' reescrito
# mantendo o set() original), logo o antigo continua presente depois de aplicar.
# Cada sonda abaixo existe apenas no texto APLICADO e nunca no pristino.
# ---------------------------------------------------------------------------
PROBES = {
    "plume_cmake_sources": r'option(RT64_GLES_BACKEND "Compila o backend OpenGL ES 3.2 de plume (plume_gles)" OFF)',
    "plume_cmake_status": r"GLES=${RT64_GLES_BACKEND}",
    "rt64_cmake_option": r'option(RT64_GLES_BACKEND "Integra o backend OpenGL ES 3.2 (plume_gles) ao RT64" OFF)',
    "rt64_cmake_define": r"target_compile_definitions(rt64 PRIVATE RT64_GLES_BACKEND)",
    "plume_gles_h_contract": r"// Cria a interface. NAO cria o contexto GL: ele precisa JA estar corrente,",
    "config_h_enum": r"// ATENCAO: a ordem aqui tem que casar com o Combo de rt64_state.cpp.",
    "config_h_json": r'{ UserConfiguration::GraphicsAPI::GLES, "GLES" },',
    "config_cpp_supported": r"if (graphicsAPI == GraphicsAPI::GLES) {",
    "window_h_setup": r"void setup(const char *windowTitle, Listener *listener, bool useOpenGL = false);",
    "window_h_members": r"SDL_GLContext glContext = nullptr;",
    "window_cpp_setup_sig": r"void ApplicationWindow::setup(const char *windowTitle, Listener *listener, bool useOpenGL) {",
    "window_cpp_flags": r"flags |= SDL_WINDOW_OPENGL;",
    "window_cpp_dtor": r"SDL_GL_DeleteContext(glContext);",
    "app_cpp_include": r'#include "plume_gles.h"',
    "app_cpp_wrapper": r"static std::unique_ptr<RenderInterface> CreateGLESInterfaceWrapper(ApplicationWindow *appWindow) {",
    "app_cpp_switch": r"renderInterface = CreateGLESInterfaceWrapper(appWindow.get());",
    "app_cpp_window": r"const bool windowUsesOpenGL = ",
    "app_cpp_inspector": r"the GLES backend has no ImGui implementation yet",
    "state_cpp_combo": r'"D3D12\0Vulkan\0Metal\0GLES\0Automatic\0"',
    "state_cpp_label": r'ImGui::Text("Graphics API: OpenGL ES");',
    "root_cmake_gles_define": r'add_compile_definitions("RT64_GLES_BACKEND")',
    "main_cpp_gles_window": r'SDL_getenv("BH_GRAPHICS_API")',
}


def probe_for(tag):
    if tag not in PROBES:
        raise KeyError("tag sem sonda de idempotencia: %s" % tag)
    return PROBES[tag]


# ---------------------------------------------------------------------------
# Driver: check / apply / revert
# ---------------------------------------------------------------------------
def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {"edits": {}}


def save_manifest(manifest):
    os.makedirs(WORK, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)


def cmd_check():
    applied = 0
    for rel, tag, old, new in EDITS:
        path = os.path.join(ROOT, rel)
        text = read(path)
        probe = probe_for(tag)
        if probe in text:
            state = "APLICADO"
            applied += 1
        elif old in text:
            state = "PENDENTE"
        else:
            state = "AMBIGUO"
        print("[%s] %s :: %s" % (state.ljust(8), rel, tag))

    print("RESUMO CHECK: aplicados=%d/%d" % (applied, len(EDITS)))
    # 0 = tudo aplicado ou tudo pendente; 1 = estado misto/ambiguo (exige atencao).
    return 0 if applied in (0, len(EDITS)) else 1


def cmd_apply():
    manifest = load_manifest()
    manifest.setdefault("files", {})
    manifest.setdefault("edits", {})
    os.makedirs(BACKUP, exist_ok=True)
    changed = 0
    skipped = 0

    for rel, tag, old, new in EDITS:
        path = os.path.join(ROOT, rel)
        text = read(path)
        key = "%s::%s" % (rel, tag)
        probe = probe_for(tag)

        if probe in text:
            print("[SKIP    ] ja aplicado: %s" % key)
            skipped += 1
            continue

        occurrences = text.count(old)
        if occurrences != 1:
            print("[FALHA   ] %s: texto-alvo ocorre %d vezes (esperado 1). Nada foi escrito." % (key, occurrences))
            return 2

        before = md5(path)
        dst = backup_path(rel)
        # O backup e' do estado PRISTINO: so' grava na primeira vez que este arquivo
        # e' tocado (em qualquer execucao). Assim um arquivo com varios edits guarda
        # uma unica copia original e o revert e' sempre fiel.
        if not os.path.exists(dst):
            shutil.copy2(path, dst)
            manifest["files"][rel] = {"backup": os.path.relpath(dst, ROOT), "pristine_md5": before}
        elif rel not in manifest["files"]:
            # Backup de execucao anterior sem manifest: a propria copia e' a fonte
            # de verdade do md5 pristino.
            manifest["files"][rel] = {"backup": os.path.relpath(dst, ROOT), "pristine_md5": md5(dst)}

        write(path, text.replace(old, new, 1))

        # Pos-condicao: a sonda tem que existir agora. Se nao existir, aborta ALTO
        # em vez de deixar um estado meio-aplicado silencioso.
        if probe not in read(path):
            print("[FALHA   ] %s: pos-condicao falhou (sonda ausente apos aplicar)." % key)
            return 2

        after = md5(path)
        manifest["edits"][key] = {"file": rel, "md5_before": before, "md5_after": after}
        print("[APLICA  ] %s md5 %s -> %s" % (key, before, after))
        changed += 1

    save_manifest(manifest)
    print("RESUMO APPLY: alterados=%d ja_aplicados=%d total=%d" % (changed, skipped, len(EDITS)))
    return 0


def cmd_revert():
    manifest = load_manifest()
    files = manifest.get("files", {})
    if not files:
        print("[FALHA   ] manifest sem arquivos: nada para reverter (%s)" % MANIFEST)
        return 2

    failed = 0
    for rel in sorted(files):
        info = files[rel]
        src = os.path.join(ROOT, info["backup"])
        dst = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print("[FALHA   ] backup ausente para %s: %s" % (rel, src))
            failed += 1
            continue
        shutil.copy2(src, dst)
        now = md5(dst)
        status = "OK" if now == info["pristine_md5"] else "DIVERGENTE"
        print("[REVERT  ] %s md5=%s pristino=%s %s" % (rel, now, info["pristine_md5"], status))
        if status != "OK":
            failed += 1

    print("RESUMO REVERT: arquivos=%d falhas=%d" % (len(files), failed))
    return 0 if failed == 0 else 2


def main():
    if (len(sys.argv) != 2) or (sys.argv[1] not in ("check", "apply", "revert")):
        print("uso: m2_gles_gate_apply.py check|apply|revert")
        return 1

    return {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())