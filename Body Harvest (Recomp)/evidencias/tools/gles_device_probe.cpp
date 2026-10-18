//
// gles_device_probe -- sonda GLES NATIVA do R36S (Mali-G31), independente do port.
//
// POR QUE ESTE ARQUIVO EXISTE:
// o glesprobe (M0) so' perguntava ao SDL "existe driver GLES?"; o gles_smoke (M2) valida o
// backend plume_gles, mas roda no HOST (Mesa/llvmpipe). Nenhum dos dois responde a pergunta
// que decidiu o M2 no device: "o EGL + GLES 3.2 do blob Mali consegue criar contexto, quanto
// de ES 3.2 real ele tem, e quais extensoes o RT64 vai precisar existem?"
//
// COMO ELE RESOLVE O PROBLEMA DE LINK (medido em 2026-10-18):
// o rootfs do dArkOS tem `libEGL.so.1 -> libMali.so -> libmali-bifrost-g31-rxp0-gbm.so`
// (blob ARM de 40,8 MB). Esse blob NAO tem SONAME e tem `.dynsym` malformado para o
// binutils ("dynsym local symbol at index 3 (>= sh_info of 3)"), ou seja: e' IMPOSSIVEL
// linkar contra ele (ver evidencia, teste de link reproduzivel). Portanto esta sonda NAO
// linka EGL nem GLES: ela faz dlopen("libEGL.so.1") + dlsym de tudo. Isso a torna
// independente do blob, do dispatcher e do sysroot -- e' o mesmo padrao que o SDL usa.
//
// O QUE ELE PROVA (cada passo e' um aceite em forma verificavel):
//   [1] o blob EGL do device carrega em runtime e exporta o nucleo EGL 1.4/1.5;
//   [2] existe caminho de display: GBM (/dev/dri/card0) ou default;
//   [3] eglInitialize + config ES3 + pbuffer + contexto ES 3.2 correntes;
//   [4] GL_VERSION/RENDERER/VENDOR/SHADING_LANGUAGE_VERSION reais (ES 3.2 exigido);
//   [5] inventario de extensoes x o que os M3/M4 do plano precisam;
//   [6] limites de hardware relevantes (texture units, SSBO/UBO, MSAA) == numeros para M3;
//   [7] clear em FBO 0 + glReadPixels de volta: o clear chegou ao drawable e glGetError()==0;
//   [8] a rota GBM window surface (a mesma do SDL/KMSDRM);
//   [9] COMPILACAO DE SHADER na forma que o M3 exige: janela de N samplers com indice DINAMICO
//       (inclusive NAO-UNIFORME, por varying flat) e a forma REAL do M1.3 (20 arrays de
//       `sampler2D[8192]`). Esta secao e' a medicao que o Passo 4 do plano chama de "medir antes
//       de fixar N"; ela existe porque foi MEDIDO que o glslangValidator do host ACEITA indice
//       dinamico de sampler (rc=0 ate' sem extensao), logo o aceite "57/57 ESSL" do M1.3 NAO
//       prova legalidade em GLSL ES -- a autoridade e' o compilador do blob, ou seja, isto aqui.
//   [9c] ESSL DE PRODUCAO (ARQUIVO): o mesmo teste, agora no artefato REAL -- cada par
//       `<nome>.vert.essl` + `<nome>.frag.essl` em `--shader-dir DIR` (ou PROBE_SHADER_DIR) e'
//       compilado e LINKADO. E' o unico caso que mede o furo do M1.3 (o orcamento de samplers so'
//       aparece no LINK) sobre o ESSL que o build realmente gera, e nao sobre uma forma sintetica.
//
// Uso: ./gles_device_probe            (tudo)
//      ./gles_device_probe --short    (sem o dump completo de extensoes)
//      ./gles_device_probe --no-gbm   (pula o GBM; usa EGL_DEFAULT_DISPLAY -- o mesmo com
//                                      PROBE_NO_GBM=1 no ambiente)
//      ./gles_device_probe --shader-dir DIR  (casos [9c]: pares VS+PS em ESSL)
//
// Saida: linhas "PROBE <campo>=<valor>" (estaveis, para grep) + resumo final "PROBE result=".
//

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl32.h>

#include <dlfcn.h>
#include <dirent.h>
#include <link.h>

#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fcntl.h>
#include <unistd.h>
#include <string>
#include <vector>

namespace {

int g_failures = 0;
int g_checks = 0;
bool g_short = false;
bool g_noGbm = false;

void check(bool condition, const char *what) {
    g_checks++;
    std::printf("PROBE check=%-58s %s\n", what, condition ? "ok" : "FALHOU");
    if (!condition) {
        g_failures++;
    }
}

void info(const char *key, const char *fmt, ...) {
    std::printf("PROBE %s=", key);
    va_list args;
    va_start(args, fmt);
    std::vprintf(fmt, args);
    va_end(args);
    std::printf("\n");
}

// ---------------------------------------------------------------------------------------
// Ponteiros EGL/GLES -- NENHUMA referencia de link para libEGL/libGLESv2.
// ---------------------------------------------------------------------------------------
#define EGL_FN(name) decltype(&name) p_##name = nullptr
EGL_FN(eglGetDisplay);
EGL_FN(eglGetProcAddress);
EGL_FN(eglInitialize);
EGL_FN(eglQueryString);
EGL_FN(eglBindAPI);
EGL_FN(eglChooseConfig);
EGL_FN(eglGetConfigAttrib);
EGL_FN(eglCreatePbufferSurface);
EGL_FN(eglCreateContext);
EGL_FN(eglMakeCurrent);
EGL_FN(eglDestroyContext);
EGL_FN(eglDestroySurface);
EGL_FN(eglTerminate);
EGL_FN(eglGetError);
EGL_FN(eglReleaseThread);
#undef EGL_FN

// Fora do nucleo EGL 1.4 (usados so' na secao [8], resolvidos por dlsym avulso).
using PFN_eglCreateWindowSurface_t = EGLSurface (*)(EGLDisplay, EGLConfig, EGLNativeWindowType, const int *);
using PFN_eglSwapBuffers_t = EGLBoolean (*)(EGLDisplay, EGLSurface);

// GL: assinaturas declaradas a mao (o contexto so' existe em runtime).
using PFN_glGetString_t = const unsigned char *(*)(unsigned);
using PFN_glGetStringi_t = const unsigned char *(*)(unsigned, unsigned);
using PFN_glGetIntegerv_t = void (*)(unsigned, int *);
using PFN_glGetError_t = unsigned (*)();
using PFN_glClearColor_t = void (*)(float, float, float, float);
using PFN_glClear_t = void (*)(unsigned);
using PFN_glFinish_t = void (*)();
using PFN_glViewport_t = void (*)(int, int, int, int);
using PFN_glReadPixels_t = void (*)(int, int, int, int, unsigned, unsigned, void *);

// GL: compilacao/link de shader -- usadas so' na secao [9] (a MEDICAO do M3).
using PFN_glCreateShader_t = unsigned (*)(unsigned);
using PFN_glShaderSource_t = void (*)(unsigned, int, const char *const *, const int *);
using PFN_glCompileShader_t = void (*)(unsigned);
using PFN_glGetShaderiv_t = void (*)(unsigned, unsigned, int *);
using PFN_glGetShaderInfoLog_t = void (*)(unsigned, int, int *, char *);
using PFN_glDeleteShader_t = void (*)(unsigned);
using PFN_glCreateProgram_t = unsigned (*)();
using PFN_glAttachShader_t = void (*)(unsigned, unsigned);
using PFN_glLinkProgram_t = void (*)(unsigned);
using PFN_glGetProgramiv_t = void (*)(unsigned, unsigned, int *);
using PFN_glGetProgramInfoLog_t = void (*)(unsigned, int, int *, char *);
using PFN_glDeleteProgram_t = void (*)(unsigned);

PFN_glGetString_t p_glGetString = nullptr;
PFN_glGetStringi_t p_glGetStringi = nullptr;
PFN_glGetIntegerv_t p_glGetIntegerv = nullptr;
PFN_glGetError_t p_glGetError = nullptr;
PFN_glClearColor_t p_glClearColor = nullptr;
PFN_glClear_t p_glClear = nullptr;
PFN_glFinish_t p_glFinish = nullptr;
PFN_glViewport_t p_glViewport = nullptr;
PFN_glReadPixels_t p_glReadPixels = nullptr;

PFN_glCreateShader_t p_glCreateShader = nullptr;
PFN_glShaderSource_t p_glShaderSource = nullptr;
PFN_glCompileShader_t p_glCompileShader = nullptr;
PFN_glGetShaderiv_t p_glGetShaderiv = nullptr;
PFN_glGetShaderInfoLog_t p_glGetShaderInfoLog = nullptr;
PFN_glDeleteShader_t p_glDeleteShader = nullptr;
PFN_glCreateProgram_t p_glCreateProgram = nullptr;
PFN_glAttachShader_t p_glAttachShader = nullptr;
PFN_glLinkProgram_t p_glLinkProgram = nullptr;
PFN_glGetProgramiv_t p_glGetProgramiv = nullptr;
PFN_glGetProgramInfoLog_t p_glGetProgramInfoLog = nullptr;
PFN_glDeleteProgram_t p_glDeleteProgram = nullptr;

void *g_eglHandle = nullptr;
void *g_gbmHandle = nullptr;

// Secao [9c]: diretorio com os pares VS+PS em ESSL (o artefato de producao do M1.3).
std::string g_shaderDir;

// Resolve um entry point de GL: primeiro eglGetProcAddress (correto para ES3/extensao),
// depois dlsym no objeto global. Mesma politica do smoke do M2 e do SDL.
void *resolveGL(const char *name) {
    void *pointer = nullptr;
    if (p_eglGetProcAddress != nullptr) {
        pointer = reinterpret_cast<void *>(p_eglGetProcAddress(name));
    }
    if (pointer == nullptr) {
        pointer = dlsym(RTLD_DEFAULT, name);
    }
    return pointer;
}

// Nome do arquivo realmente carregado por um handle (prova de QUAL lib resolveu).
std::string loadedPath(void *handle) {
    struct link_map *map = nullptr;
    if (dlinfo(handle, RTLD_DI_LINKMAP, &map) == 0 && map != nullptr && map->l_name != nullptr) {
        return std::string(map->l_name);
    }
    return std::string("<desconhecido>");
}

std::string extensionList() {
    if (p_glGetString == nullptr) {
        return std::string();
    }
    const unsigned char *extensions = p_glGetString(GL_EXTENSIONS);
    return extensions != nullptr ? std::string(reinterpret_cast<const char *>(extensions))
                                 : std::string();
}

bool hasExtension(const std::string &list, const char *needle) {
    return list.find(needle) != std::string::npos;
}

// Le um arquivo inteiro (secao [9c]). Devolve false se nao existir / estiver vazio.
bool readWholeFile(const std::string &path, std::string &out) {
    std::FILE *file = std::fopen(path.c_str(), "rb");
    if (file == nullptr) {
        return false;
    }
    out.clear();
    char buffer[4096];
    size_t read = 0;
    while ((read = std::fread(buffer, 1, sizeof(buffer), file)) > 0) {
        out.append(buffer, read);
    }
    std::fclose(file);
    return !out.empty();
}

} // namespace

int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "--short") == 0) {
            g_short = true;
        } else if (std::strcmp(argv[i], "--no-gbm") == 0) {
            g_noGbm = true;
        } else if (std::strcmp(argv[i], "--shader-dir") == 0 && i + 1 < argc) {
            g_shaderDir = argv[++i];
        }
    }
    if (std::getenv("PROBE_NO_GBM") != nullptr) {
        g_noGbm = true;
    }
    if (g_shaderDir.empty()) {
        const char *fromEnv = std::getenv("PROBE_SHADER_DIR");
        if (fromEnv != nullptr) {
            g_shaderDir = fromEnv;
        }
    }

    info("arch", "%s (%zu-bit pointers)",
         sizeof(void *) == 8 ? "aarch64/64" : "32-bit/outro", sizeof(void *) * 8);

    // ---------- [0] dlopen do blob EGL ----------
    g_eglHandle = dlopen("libEGL.so.1", RTLD_NOW | RTLD_GLOBAL);
    if (g_eglHandle == nullptr) {
        info("dlopen_libEGL", "FALHOU: %s", dlerror());
        check(false, "[1] dlopen(libEGL.so.1)");
        std::printf("PROBE result=FAIL (sem libEGL)\n");
        return 1;
    }
    info("dlopen_libEGL", "ok");
    info("libEGL_path", "%s", loadedPath(g_eglHandle).c_str());
    check(true, "[1] dlopen(libEGL.so.1)");

    // ---------- [1b] nucleo EGL presente? ----------
    struct Entry { const char *name; void **slot; };
    const Entry eglEntries[] = {
        { "eglGetDisplay",           reinterpret_cast<void **>(&p_eglGetDisplay) },
        { "eglGetProcAddress",       reinterpret_cast<void **>(&p_eglGetProcAddress) },
        { "eglInitialize",           reinterpret_cast<void **>(&p_eglInitialize) },
        { "eglQueryString",          reinterpret_cast<void **>(&p_eglQueryString) },
        { "eglBindAPI",              reinterpret_cast<void **>(&p_eglBindAPI) },
        { "eglChooseConfig",         reinterpret_cast<void **>(&p_eglChooseConfig) },
        { "eglGetConfigAttrib",      reinterpret_cast<void **>(&p_eglGetConfigAttrib) },
        { "eglCreatePbufferSurface", reinterpret_cast<void **>(&p_eglCreatePbufferSurface) },
        { "eglCreateContext",        reinterpret_cast<void **>(&p_eglCreateContext) },
        { "eglMakeCurrent",          reinterpret_cast<void **>(&p_eglMakeCurrent) },
        { "eglDestroyContext",       reinterpret_cast<void **>(&p_eglDestroyContext) },
        { "eglDestroySurface",       reinterpret_cast<void **>(&p_eglDestroySurface) },
        { "eglTerminate",            reinterpret_cast<void **>(&p_eglTerminate) },
        { "eglGetError",             reinterpret_cast<void **>(&p_eglGetError) },
        { "eglReleaseThread",        reinterpret_cast<void **>(&p_eglReleaseThread) },
    };
    std::string eglMissing;
    int eglFound = 0;
    std::printf("PROBE egl_symbols=");
    for (const Entry &entry : eglEntries) {
        *entry.slot = dlsym(g_eglHandle, entry.name);
        if (*entry.slot != nullptr) {
            eglFound++;
            std::printf("%s ", entry.name);
        } else {
            eglMissing += std::string(entry.name) + " ";
        }
    }
    std::printf("\n");
    const int eglTotal = static_cast<int>(sizeof(eglEntries) / sizeof(eglEntries[0]));
    info("egl_symbols_found", "%d/%d", eglFound, eglTotal);
    info("egl_symbols_missing", "%s", eglMissing.empty() ? "(nenhum)" : eglMissing.c_str());
    check(eglFound == eglTotal, "[1b] os 15 entry points do nucleo EGL resolvem");

    // ---------- [2] display: GBM (/dev/dri/card0) ou default ----------
    g_gbmHandle = dlopen("libgbm.so.1", RTLD_NOW | RTLD_GLOBAL);
    void *gbmDevice = nullptr;
    int drmFd = -1;
    if (g_gbmHandle != nullptr) {
        info("libgbm_path", "%s", loadedPath(g_gbmHandle).c_str());
        using PFN_gbm_create_device_t = void *(*)(int);
        using PFN_gbm_device_get_fd_t = int (*)(void *);
        auto p_gbm_create_device =
            reinterpret_cast<PFN_gbm_create_device_t>(dlsym(g_gbmHandle, "gbm_create_device"));
        auto p_gbm_device_get_fd =
            reinterpret_cast<PFN_gbm_device_get_fd_t>(dlsym(g_gbmHandle, "gbm_device_get_fd"));
        info("gbm_create_device", "%s", p_gbm_create_device != nullptr ? "ok" : "ausente");
        // --no-gbm / PROBE_NO_GBM=1: pula o caminho GBM e cai em EGL_DEFAULT_DISPLAY. Serve
        // para (a) validar a propria sonda no host com EGL_PLATFORM=surfaceless e
        // (b) diagnosticar o device quando o KMS/DRM esta ocupado pelo EmulationStation.
        if (g_noGbm) {
            info("open_dri_card0", "pulado (--no-gbm)");
        } else {
            drmFd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
            info("open_dri_card0", "%s",
                 drmFd >= 0 ? "ok" : "FALHOU (sem KMS/DRM ou sem permissao)");
        }
        if (drmFd >= 0 && p_gbm_create_device != nullptr) {
            gbmDevice = p_gbm_create_device(drmFd);
            info("gbm_device", "%s", gbmDevice != nullptr ? "ok" : "FALHOU");
            if (gbmDevice != nullptr && p_gbm_device_get_fd != nullptr) {
                info("gbm_device_fd", "%d", p_gbm_device_get_fd(gbmDevice));
            }
        }
    } else {
        info("libgbm_path", "FALHOU: %s", dlerror());
    }

    const char *platformUsed = "none";
    EGLDisplay display = EGL_NO_DISPLAY;

    // eglGetPlatformDisplay* nao e' exportado pelo blob Mali (medido: 0 simbolos), mas a
    // checagem e' barata e, se existir, e' o caminho preferido do SDL 2.30.
    using PFN_eglGetPlatformDisplayEXT_t = EGLDisplay (*)(unsigned, void *, const int *);
    auto p_eglGetPlatformDisplayEXT = reinterpret_cast<PFN_eglGetPlatformDisplayEXT_t>(
        resolveGL("eglGetPlatformDisplayEXT"));
    info("eglGetPlatformDisplayEXT", "%s",
         p_eglGetPlatformDisplayEXT != nullptr ? "ok" : "ausente");

    if (p_eglGetPlatformDisplayEXT != nullptr && gbmDevice != nullptr) {
        // EGL_PLATFORM_GBM_KHR == 0x31D7 (o header do toolchain nem sempre o define).
        display = p_eglGetPlatformDisplayEXT(0x31D7u, gbmDevice, nullptr);
        platformUsed = "eglGetPlatformDisplayEXT(GBM_KHR)";
    }
    if (display == EGL_NO_DISPLAY && gbmDevice != nullptr) {
        // Convencao pre-EGL-1.5 usada pelo Mali/dArkOS: o gbm_device E' o native display.
        display = p_eglGetDisplay(reinterpret_cast<EGLNativeDisplayType>(gbmDevice));
        platformUsed = "eglGetDisplay(gbm_device)";
    }
    if (display == EGL_NO_DISPLAY) {
        display = p_eglGetDisplay(EGL_DEFAULT_DISPLAY);
        platformUsed = "eglGetDisplay(EGL_DEFAULT_DISPLAY)";
    }

    info("display_path", "%s", platformUsed);
    info("display_handle", "%p", reinterpret_cast<void *>(display));
    check(display != EGL_NO_DISPLAY, "[2] EGLDisplay obtido");

    if (display == EGL_NO_DISPLAY) {
        std::printf("PROBE result=FAIL (sem display EGL)\n");
        return 1;
    }

    // ---------- [3] initialize + config + pbuffer + contexto ES 3 ----------
    EGLint eglMajor = 0;
    EGLint eglMinor = 0;
    if (p_eglInitialize(display, &eglMajor, &eglMinor) != EGL_TRUE) {
        info("eglInitialize", "FALHOU (0x%X)", p_eglGetError());
        check(false, "[3a] eglInitialize");
        std::printf("PROBE result=FAIL (eglInitialize)\n");
        return 1;
    }
    const char *eglVendor = p_eglQueryString(display, EGL_VENDOR);
    const char *eglVersionString = p_eglQueryString(display, EGL_VERSION);
    const char *eglClientApis = p_eglQueryString(display, EGL_CLIENT_APIS);
    const char *eglExtensions = p_eglQueryString(display, EGL_EXTENSIONS);
    info("egl_version", "%d.%d", eglMajor, eglMinor);
    info("egl_vendor", "%s", eglVendor != nullptr ? eglVendor : "(nulo)");
    info("egl_version_string", "%s", eglVersionString != nullptr ? eglVersionString : "(nulo)");
    info("egl_client_apis", "%s", eglClientApis != nullptr ? eglClientApis : "(nulo)");
    info("egl_extensions_bytes", "%zu", eglExtensions != nullptr ? std::strlen(eglExtensions) : 0);
    check(true, "[3a] eglInitialize");

    if (p_eglBindAPI(EGL_OPENGL_ES_API) != EGL_TRUE) {
        info("eglBindAPI_ES", "FALHOU (0x%X)", p_eglGetError());
    } else {
        info("eglBindAPI_ES", "ok");
    }

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
    if ((p_eglChooseConfig(display, configAttributes, &config, 1, &configCount) != EGL_TRUE) ||
        configCount == 0) {
        info("eglChooseConfig", "FALHOU (0x%X, count=%d)", p_eglGetError(), configCount);
        check(false, "[3b] eglChooseConfig (pbuffer + ES3 + RGBA8888 + depth24)");
        std::printf("PROBE result=FAIL (eglChooseConfig)\n");
        return 1;
    }
    check(true, "[3b] eglChooseConfig (pbuffer + ES3 + RGBA8888 + depth24)");

    const int width = 256;
    const int height = 256;
    const EGLint surfaceAttributes[] = { EGL_WIDTH, width, EGL_HEIGHT, height, EGL_NONE };
    EGLSurface surface = p_eglCreatePbufferSurface(display, config, surfaceAttributes);
    check(surface != EGL_NO_SURFACE, "[3c] eglCreatePbufferSurface 256x256");
    if (surface == EGL_NO_SURFACE) {
        info("eglCreatePbufferSurface", "FALHOU (0x%X)", p_eglGetError());
        std::printf("PROBE result=FAIL (pbuffer)\n");
        return 1;
    }

    const EGLint contextAttributes[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
    EGLContext context = p_eglCreateContext(display, config, EGL_NO_CONTEXT, contextAttributes);
    check(context != EGL_NO_CONTEXT, "[3d] eglCreateContext(ES3)");
    if (context == EGL_NO_CONTEXT) {
        info("eglCreateContext", "FALHOU (0x%X)", p_eglGetError());
        std::printf("PROBE result=FAIL (contexto ES3)\n");
        return 1;
    }

    if (p_eglMakeCurrent(display, surface, surface, context) != EGL_TRUE) {
        info("eglMakeCurrent", "FALHOU (0x%X)", p_eglGetError());
        check(false, "[3e] eglMakeCurrent");
        std::printf("PROBE result=FAIL (make current)\n");
        return 1;
    }
    check(true, "[3e] eglMakeCurrent");

    // ---------- [4] strings do contexto ----------
    p_glGetString = reinterpret_cast<PFN_glGetString_t>(resolveGL("glGetString"));
    p_glGetStringi = reinterpret_cast<PFN_glGetStringi_t>(resolveGL("glGetStringi"));
    p_glGetIntegerv = reinterpret_cast<PFN_glGetIntegerv_t>(resolveGL("glGetIntegerv"));
    p_glGetError = reinterpret_cast<PFN_glGetError_t>(resolveGL("glGetError"));
    p_glClearColor = reinterpret_cast<PFN_glClearColor_t>(resolveGL("glClearColor"));
    p_glClear = reinterpret_cast<PFN_glClear_t>(resolveGL("glClear"));
    p_glFinish = reinterpret_cast<PFN_glFinish_t>(resolveGL("glFinish"));
    p_glViewport = reinterpret_cast<PFN_glViewport_t>(resolveGL("glViewport"));
    p_glReadPixels = reinterpret_cast<PFN_glReadPixels_t>(resolveGL("glReadPixels"));

    const bool glCore = (p_glGetString != nullptr) && (p_glGetIntegerv != nullptr) &&
                        (p_glGetError != nullptr) && (p_glClear != nullptr) &&
                        (p_glClearColor != nullptr) && (p_glReadPixels != nullptr) &&
                        (p_glViewport != nullptr);
    check(glCore, "[4a] nucleo de GL resolvido via eglGetProcAddress/dlsym");
    if (!glCore) {
        std::printf("PROBE result=FAIL (nucleo GL)\n");
        return 1;
    }

    const char *glVersion = reinterpret_cast<const char *>(p_glGetString(GL_VERSION));
    const char *glRenderer = reinterpret_cast<const char *>(p_glGetString(GL_RENDERER));
    const char *glVendor = reinterpret_cast<const char *>(p_glGetString(GL_VENDOR));
    const char *glSlVersion =
        reinterpret_cast<const char *>(p_glGetString(GL_SHADING_LANGUAGE_VERSION));
    info("gl_version", "%s", glVersion != nullptr ? glVersion : "(nulo)");
    info("gl_renderer", "%s", glRenderer != nullptr ? glRenderer : "(nulo)");
    info("gl_vendor", "%s", glVendor != nullptr ? glVendor : "(nulo)");
    info("gl_shading_language_version", "%s", glSlVersion != nullptr ? glSlVersion : "(nulo)");

    // ES 3.2 e' o alvo do backend: "OpenGL ES 3.2 ..." ou superior.
    bool es32 = false;
    if (glVersion != nullptr) {
        int major = 0;
        int minor = 0;
        if (std::sscanf(glVersion, "OpenGL ES %d.%d", &major, &minor) == 2) {
            es32 = (major > 3) || (major == 3 && minor >= 2);
        }
    }
    check(es32, "[4b] contexto reporta OpenGL ES >= 3.2 (alvo do backend)");

    // ---------- [5] extensoes que os M3/M4 precisam ----------
    const std::string extensions = extensionList();
    int extensionCount = 0;
    if (p_glGetStringi != nullptr) {
        int numExtensions = 0;
        p_glGetIntegerv(GL_NUM_EXTENSIONS, &numExtensions);
        extensionCount = numExtensions;
    } else if (!extensions.empty()) {
        extensionCount = 1;
        for (char character : extensions) {
            if (character == ' ') {
                extensionCount++;
            }
        }
    }
    info("gl_extensions_count", "%d", extensionCount);
    if (!g_short && !extensions.empty()) {
        info("gl_extensions", "%s", extensions.c_str());
    }

    struct ExtensionNeed { const char *name; const char *need; };
    const ExtensionNeed needs[] = {
        { "GL_ARM_shader_framebuffer_fetch",             "M4 (raster: framebuffer fetch)" },
        { "GL_EXT_multisampled_render_to_texture",       "M4 (MSAA / render-to-texture)" },
        { "GL_EXT_buffer_storage",                       "M2/M3 (storage imutavel/persistente)" },
        { "GL_EXT_texture_storage",                      "M2/M3 (texturas imutaveis)" },
        { "GL_EXT_texture_format_BGRA8888",              "R8 (formato BGRA)" },
        { "GL_EXT_texture_norm16",                       "R8 (16-bit UNORM - esperado AUSENTE)" },
        { "GL_EXT_render_snorm",                         "R8 (render snorm)" },
        { "GL_KHR_debug",                                "diagnostico" },
        { "GL_EXT_disjoint_timer_query",                 "M5 (medicao de FPS)" },
        { "GL_EXT_geometry_shader",                      "M4 (caminho geometry shader)" },
        { "GL_EXT_texture_border_clamp",                 "R9 (clamp-to-border)" },
        { "GL_EXT_gpu_shader5",                          "M3 DECISIVO: legaliza indice dinamico de sampler" },
        { "GL_NV_gpu_shader5",                           "variante NV (o RAW offline so' checou esta)" },
        { "GL_EXT_blend_func_extended",                  "M3/M4 DECISIVO: o raster PS escreve 2 alvos (index=1)" },
        { "GL_EXT_texture_cube_map_array",               "texturas cubemap array" },
        { "GL_OES_texture_storage_multisample_2d_array", "MSAA em texture array" },
        { "GL_EXT_copy_image",                           "copia de textura" },
        { "GL_EXT_sRGB",                                 "sRGB" },
    };
    std::printf("PROBE extensions_need=\n");
    for (const ExtensionNeed &need : needs) {
        const bool present = hasExtension(extensions, need.name);
        std::printf("PROBE   %-46s %-8s  # %s\n", need.name,
                    present ? "PRESENTE" : "AUSENTE", need.need);
    }
    check(extensionCount > 0, "[5] inventario de extensoes obtido");

    // ---------- [6] limites relevantes ----------
    struct LimitNeed { unsigned token; const char *name; const char *use; };
    const LimitNeed limits[] = {
        { GL_MAX_TEXTURE_IMAGE_UNITS,            "GL_MAX_TEXTURE_IMAGE_UNITS",            "M3 janela de texturas (frag)" },
        { GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS,   "GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS",   "M3 janela total" },
        { GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS,     "GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS",     "M3" },
        { GL_MAX_TEXTURE_SIZE,                   "GL_MAX_TEXTURE_SIZE",                   "M4 (TMEM/texturas)" },
        { GL_MAX_RENDERBUFFER_SIZE,              "GL_MAX_RENDERBUFFER_SIZE",              "M4 framebuffer" },
        { GL_MAX_SAMPLES,                        "GL_MAX_SAMPLES",                        "M4 MSAA" },
        { GL_MAX_DRAW_BUFFERS,                   "GL_MAX_DRAW_BUFFERS",                   "M4" },
        { GL_MAX_UNIFORM_BUFFER_BINDINGS,        "GL_MAX_UNIFORM_BUFFER_BINDINGS",        "M3 descriptors" },
        { GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS, "GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS", "M3/R8 SSBO" },
        { GL_MAX_COMPUTE_SHADER_STORAGE_BLOCKS,  "GL_MAX_COMPUTE_SHADER_STORAGE_BLOCKS",  "M4 compute" },
        { GL_MAX_VERTEX_UNIFORM_BLOCKS,          "GL_MAX_VERTEX_UNIFORM_BLOCKS",          "M3" },
        { GL_MAX_FRAGMENT_UNIFORM_BLOCKS,        "GL_MAX_FRAGMENT_UNIFORM_BLOCKS",        "M3" },
        { GL_UNIFORM_BUFFER_OFFSET_ALIGNMENT,    "GL_UNIFORM_BUFFER_OFFSET_ALIGNMENT",    "M3 (alinhamento)" },
        { GL_MAX_SHADER_STORAGE_BLOCK_SIZE,      "GL_MAX_SHADER_STORAGE_BLOCK_SIZE",      "R7 (ubershader/ESSL)" },
        { GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS, "GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS", "M4 compute" },
    };
    std::printf("PROBE limits=\n");
    for (const LimitNeed &limit : limits) {
        int value = -1;
        p_glGetIntegerv(limit.token, &value);
        std::printf("PROBE   %-42s %-8d  # %s\n", limit.name, value, limit.use);
    }

    // ---------- [7] clear em FBO 0 + readback (o clear chegou ao drawable?) ----------
    p_glViewport(0, 0, width, height);
    p_glClearColor(64.0f / 255.0f, 128.0f / 255.0f, 191.0f / 255.0f, 1.0f);
    p_glClear(GL_COLOR_BUFFER_BIT);
    if (p_glFinish != nullptr) {
        p_glFinish();
    }

    unsigned char pixel[4] = { 0, 0, 0, 0 };
    p_glReadPixels(width / 2, height / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);

    const unsigned error = p_glGetError();
    info("clear_readback_rgba", "%u,%u,%u,%u", pixel[0], pixel[1], pixel[2], pixel[3]);
    info("glGetError", "0x%X", error);

    const bool readbackOK = (pixel[0] + 2 >= 64) && (pixel[0] <= 66) &&
                            (pixel[1] + 2 >= 128) && (pixel[1] <= 130) &&
                            (pixel[2] + 2 >= 191) && (pixel[2] <= 193);
    check(readbackOK, "[7a] glReadPixels devolve o clear (64,128,191)");
    check(error == GL_NO_ERROR, "[7b] glGetError() == 0");

    // ---------- [8] GBM window surface: a rota EXATA do SDL/KMSDRM ----------
    // Só roda quando ha' gbm_device (no QEMU/host nao ha'). No device isto e' o teste mais
    // representativo possivel sem abrir o port: gbm_surface_create + eglCreateWindowSurface
    // + eglSwapBuffers e' literalmente o que o backend KMSDRM do SDL 2.30 faz.
    // Constantes do gbm.h (nao ha' gbm.h no toolchain): SCANOUT=1, RENDERING=4,
    // FORMAT_XRGB8888='X''R''2''4'=0x34325258.
    if (gbmDevice == nullptr) {
        info("gbm_window_surface", "pulado (sem gbm_device: sem /dev/dri/card0 ou sem KMS)");
    } else {
        using PFN_gbm_surface_create_t = void *(*)(void *, unsigned, unsigned, unsigned, unsigned);
        using PFN_gbm_surface_destroy_t = void (*)(void *);
        auto p_gbm_surface_create =
            reinterpret_cast<PFN_gbm_surface_create_t>(dlsym(g_gbmHandle, "gbm_surface_create"));
        auto p_gbm_surface_destroy =
            reinterpret_cast<PFN_gbm_surface_destroy_t>(dlsym(g_gbmHandle, "gbm_surface_destroy"));
        auto p_eglCreateWindowSurface = reinterpret_cast<PFN_eglCreateWindowSurface_t>(
            dlsym(g_eglHandle, "eglCreateWindowSurface"));
        auto p_eglSwapBuffers =
            reinterpret_cast<PFN_eglSwapBuffers_t>(dlsym(g_eglHandle, "eglSwapBuffers"));

        info("gbm_surface_create_sym", "%s", p_gbm_surface_create != nullptr ? "ok" : "ausente");
        info("eglCreateWindowSurface_sym", "%s", p_eglCreateWindowSurface != nullptr ? "ok" : "ausente");

        void *gbmSurface = nullptr;
        if (p_gbm_surface_create != nullptr && p_eglCreateWindowSurface != nullptr) {
            gbmSurface = p_gbm_surface_create(gbmDevice, static_cast<unsigned>(width),
                                              static_cast<unsigned>(height),
                                              0x34325258u /* XRGB8888 */, 1u | 4u /* SCANOUT|RENDERING */);
            info("gbm_surface_create()", "%s", gbmSurface != nullptr ? "ok" : "FALHOU");
            check(gbmSurface != nullptr, "[8a] gbm_surface_create (XRGB8888, SCANOUT|RENDERING)"); 

            if (gbmSurface != nullptr) {
                EGLSurface windowSurface = p_eglCreateWindowSurface(
                    display, config, reinterpret_cast<EGLNativeWindowType>(gbmSurface), nullptr);
                info("eglCreateWindowSurface()", "%s (0x%X)",
                     windowSurface != EGL_NO_SURFACE ? "ok" : "FALHOU", p_eglGetError());
                check(windowSurface != EGL_NO_SURFACE, "[8b] eglCreateWindowSurface(gbm_surface)");

                if (windowSurface != EGL_NO_SURFACE && p_eglMakeCurrent != nullptr) {
                    if (p_eglMakeCurrent(display, windowSurface, windowSurface, context) == EGL_TRUE) {
                        p_glViewport(0, 0, width, height);
                        p_glClearColor(191.0f / 255.0f, 64.0f / 255.0f, 128.0f / 255.0f, 1.0f);
                        p_glClear(GL_COLOR_BUFFER_BIT);
                        if (p_glFinish != nullptr) {
                            p_glFinish();
                        }
                        if (p_eglSwapBuffers != nullptr) {
                            const EGLBoolean swapped = p_eglSwapBuffers(display, windowSurface);
                            info("eglSwapBuffers()", "%s (0x%X)",
                                 swapped == EGL_TRUE ? "ok" : "FALHOU", p_eglGetError());
                        }
                        // Volta para o pbuffer (a secao [7] ja' foi lida; so' restaura o estado).
                        p_eglMakeCurrent(display, surface, surface, context);
                    } else {
                        info("eglMakeCurrent(window)", "FALHOU (0x%X)", p_eglGetError());
                    }
                    p_eglDestroySurface(display, windowSurface);
                }
                if (p_gbm_surface_destroy != nullptr) {
                    p_gbm_surface_destroy(gbmSurface);
                }
            }
        } else {
            check(false, "[8a] simbolos gbm_surface_create/eglCreateWindowSurface");
        }
    }

    // ---------- [9] MEDICAO DO M3: compilar shader na forma que a janela de N exige ---------
    // CONTEXTO (medido no host, 2026-10-18): o ESSL que o M1.3 gera para os raster PS do RT64
    // declara 20 arrays de `sampler2D[8192]` e os indexa por `GPUTiles._m0[..].textureIndex` --
    // indice DINAMICO e por-fragmento (nao-uniforme), ou seja, exatamente o que o Passo 4 do
    // plano quer trocar por uma JANELA de N. O `glslangValidator -S frag` do host devolve rc=0
    // para isso ate' SEM extensao: o validador e' permissivo, logo "57/57 ESSL" (M1.3) nao
    // prova legalidade. Esta secao mede o que importa, no compilador do blob:
    //   control      -- o compilador ES 3.20 funciona (sem isto, FAIL e' ambiguo)
    //   win16        -- a JANELA do M3: sampler2D[16] + indice dinamico uniforme
    //   win16_vary   -- idem, com indice NAO-UNIFORME vindo de `flat in uint` (caso real)
    //   arr8192      -- a forma do M1.3: sampler2D[8192] + indice dinamico
    //   const_idx_8192 -- [8192] com indice LITERAL (separa "tamanho" de "indice dinamico")
    //   arr16_2x     -- 2 arrays de [16] = 32 samplers (o ORCAMENTO e' MULTIPLICATIVO!)
    //   arr16_3x     -- 3 arrays de [16] = 48 samplers (> limite)
    //   win16_20x    -- forma-ALVO do M3: 20 arrays de [16] = 320 samplers
    //   arr8192_20x  -- forma REAL do M1.3: 20 arrays de [8192] = 163.840 samplers
    //   win16_gpu5   -- win16 + `#extension GL_EXT_gpu_shader5` (se existir, legaliza o indice)
    // Nada aqui e' criterio de aceite do M2 (sao MEDICOES): o unico check e' o controle.
    p_glCreateShader = reinterpret_cast<PFN_glCreateShader_t>(resolveGL("glCreateShader"));
    p_glShaderSource = reinterpret_cast<PFN_glShaderSource_t>(resolveGL("glShaderSource"));
    p_glCompileShader = reinterpret_cast<PFN_glCompileShader_t>(resolveGL("glCompileShader"));
    p_glGetShaderiv = reinterpret_cast<PFN_glGetShaderiv_t>(resolveGL("glGetShaderiv"));
    p_glGetShaderInfoLog =
        reinterpret_cast<PFN_glGetShaderInfoLog_t>(resolveGL("glGetShaderInfoLog"));
    p_glDeleteShader = reinterpret_cast<PFN_glDeleteShader_t>(resolveGL("glDeleteShader"));
    p_glCreateProgram = reinterpret_cast<PFN_glCreateProgram_t>(resolveGL("glCreateProgram"));
    p_glAttachShader = reinterpret_cast<PFN_glAttachShader_t>(resolveGL("glAttachShader"));
    p_glLinkProgram = reinterpret_cast<PFN_glLinkProgram_t>(resolveGL("glLinkProgram"));
    p_glGetProgramiv = reinterpret_cast<PFN_glGetProgramiv_t>(resolveGL("glGetProgramiv"));
    p_glGetProgramInfoLog =
        reinterpret_cast<PFN_glGetProgramInfoLog_t>(resolveGL("glGetProgramInfoLog"));
    p_glDeleteProgram = reinterpret_cast<PFN_glDeleteProgram_t>(resolveGL("glDeleteProgram"));

    const bool shaderCore = (p_glCreateShader != nullptr) && (p_glShaderSource != nullptr) &&
                            (p_glCompileShader != nullptr) && (p_glGetShaderiv != nullptr) &&
                            (p_glGetShaderInfoLog != nullptr) && (p_glDeleteShader != nullptr) &&
                            (p_glCreateProgram != nullptr) && (p_glAttachShader != nullptr) &&
                            (p_glLinkProgram != nullptr) && (p_glGetProgramiv != nullptr) &&
                            (p_glGetProgramInfoLog != nullptr) && (p_glDeleteProgram != nullptr);
    check(shaderCore, "[9a] nucleo de compilacao de shader (ES 3.20) resolvido");

    if (shaderCore) {
        const char *vsBase =
            "#version 320 es\n"
            "layout(location = 0) in vec2 aPos;\n"
            "void main() { gl_Position = vec4(aPos, 0.0, 1.0); }\n";
        const char *vsVarying =
            "#version 320 es\n"
            "layout(location = 0) in vec2 aPos;\n"
            "flat out uint vIndex;\n"
            // NAO usar constante aqui (ex.: `vIndex = 0u`): com indice dobrado o driver conta
            // UM sampler por array, o link "passa" e a medicao vira mentira -- foi medido no
            // llvmpipe (arr8192_20x linkava "ok" com 163.840 samplers contra um limite de 32).
            "void main() { vIndex = uint(gl_VertexID); gl_Position = vec4(aPos, 0.0, 1.0); }\n";

        struct ShaderCase {
            std::string id;
            std::string note;
            std::string decls;
            std::string body;
            bool varying;
            bool gpu5;
        };
        std::vector<ShaderCase> cases;

        cases.push_back({ "control", "compilador ES 3.20 do blob funciona", "",
                          "fragColor = vec4(1.0, 0.5, 0.25, 1.0);", false, false });

        // 1 array de tamanho T com indice dinamico (uniforme, ou NAO-UNIFORME por varying flat).
        auto oneDynamicArray = [&cases](const char *id, const char *note, unsigned size,
                                        bool varying, bool gpu5) {
            char decl[160];
            std::snprintf(decl, sizeof(decl), "uniform highp sampler2D uTex[%u];\n%s", size,
                          varying ? "flat in uint vIndex;\n" : "uniform int uIndex;\n");
            ShaderCase c;
            c.id = id;
            c.note = note;
            c.decls = decl;
            c.body = varying ? "fragColor = texture(uTex[int(vIndex)], vec2(0.5));"
                             : "fragColor = texture(uTex[uIndex], vec2(0.5));";
            c.varying = varying;
            c.gpu5 = gpu5;
            cases.push_back(c);
        };

        // `count` arrays de tamanho `size`, TODOS amostrados -- e' assim que se mede o ORCAMENTO
        // TOTAL de samplers (o M3 e' multiplicativo: count x size precisa caber no limite).
        auto manyArrays = [&cases](const char *id, const char *note, unsigned size, unsigned count,
                                   bool varying) {
            std::string decls;
            std::string body = "float a = 0.0;\n";
            char buf[192];
            for (unsigned i = 0; i < count; i++) {
                std::snprintf(buf, sizeof(buf), "uniform highp sampler2D uTex%u[%u];\n", i, size);
                decls += buf;
                std::snprintf(buf, sizeof(buf), "a += texture(uTex%u[%s], vec2(0.5)).x;\n", i,
                              varying ? "int(vIndex)" : "uIndex");
                body += buf;
            }
            decls += varying ? "flat in uint vIndex;\n" : "uniform int uIndex;\n";
            body += "fragColor = vec4(a);";
            ShaderCase c;
            c.id = id;
            c.note = note;
            c.decls = decls;
            c.body = body;
            c.varying = varying;
            c.gpu5 = false;
            cases.push_back(c);
        };

        oneDynamicArray("win16", "JANELA do M3: [16] + indice dinamico (uniform)", 16, false,
                        false);
        oneDynamicArray("win16_vary", "[16] + indice NAO-UNIFORME (flat in uint)", 16, true,
                        false);
        oneDynamicArray("arr8192", "forma do M1.3: [8192] + indice dinamico", 8192, false, false);
        oneDynamicArray("win16_gpu5", "[16] + GL_EXT_gpu_shader5 habilitada", 16, false, true);
        manyArrays("arr16_2x", "2 arrays de [16] = 32 samplers (exatamente no limite)", 16, 2, false);
        manyArrays("arr16_3x", "3 arrays de [16] = 48 samplers (> limite)", 16, 3, false);
        manyArrays("win16_20x", "forma-ALVO do M3: 20 arrays de [16] = 320 samplers", 16, 20,
                   false);
        manyArrays("arr8192_20x",
                   "forma REAL do M1.3: 20 arrays de [8192] = 163.840 samplers", 8192, 20, true);
        {
            // Separar "tamanho da array" de "indice dinamico": indice LITERAL em [8192].
            char decl[160];
            std::snprintf(decl, sizeof(decl), "uniform highp sampler2D uTex[8192];\n");
            ShaderCase c;
            c.id = "const_idx_8192";
            c.note = "[8192] + indice LITERAL 7 (o tamanho sozinho quebra?)";
            c.decls = decl;
            c.body = "fragColor = texture(uTex[7], vec2(0.5));";
            c.varying = false;
            c.gpu5 = false;
            cases.push_back(c);
        }

        std::printf("PROBE shader_compile_cases=%zu\n", cases.size());

        auto printLogLines = [](const char *id, const std::string &log) {
            std::string line;
            for (char ch : log) {
                if (ch == '\n') {
                    if (!line.empty()) {
                        std::printf("PROBE log_%s=%s\n", id, line.c_str());
                        line.clear();
                    }
                } else {
                    line += ch;
                }
            }
            if (!line.empty()) {
                std::printf("PROBE log_%s=%s\n", id, line.c_str());
            }
        };

        std::vector<std::pair<std::string, bool> > measurements;
        bool controlOk = false;

        for (const ShaderCase &c : cases) {
            std::string source = "#version 320 es\n";
            if (c.gpu5) {
                source += "#extension GL_EXT_gpu_shader5 : enable\n";
            }
            source += "precision highp float;\n";
            source += c.decls;
            source += "out vec4 fragColor;\n";
            source += "void main() {\n";
            source += c.body;
            source += "\n}\n";

            const char *sourcePtr = source.c_str();
            const unsigned fragment = p_glCreateShader(GL_FRAGMENT_SHADER);
            p_glShaderSource(fragment, 1, &sourcePtr, nullptr);
            p_glCompileShader(fragment);

            int compileStatus = 0;
            p_glGetShaderiv(fragment, GL_COMPILE_STATUS, &compileStatus);

            std::string fragmentLog;
            int logLength = 0;
            p_glGetShaderiv(fragment, GL_INFO_LOG_LENGTH, &logLength);
            if (logLength > 1) {
                std::vector<char> buffer(static_cast<size_t>(logLength) + 1, '\0');
                p_glGetShaderInfoLog(fragment, logLength, nullptr, buffer.data());
                fragmentLog = buffer.data();
            }

            int linkStatus = -1;
            std::string programLog;
            if (compileStatus == GL_TRUE) {
                const char *vsPtr = c.varying ? vsVarying : vsBase;
                const unsigned vertex = p_glCreateShader(GL_VERTEX_SHADER);
                p_glShaderSource(vertex, 1, &vsPtr, nullptr);
                p_glCompileShader(vertex);
                const unsigned program = p_glCreateProgram();
                p_glAttachShader(program, vertex);
                p_glAttachShader(program, fragment);
                p_glLinkProgram(program);
                p_glGetProgramiv(program, GL_LINK_STATUS, &linkStatus);
                int programLogLength = 0;
                p_glGetProgramiv(program, GL_INFO_LOG_LENGTH, &programLogLength);
                if (programLogLength > 1) {
                    std::vector<char> buffer(static_cast<size_t>(programLogLength) + 1, '\0');
                    p_glGetProgramInfoLog(program, programLogLength, nullptr, buffer.data());
                    programLog = buffer.data();
                }
                p_glDeleteProgram(program);
                p_glDeleteShader(vertex);
            }
            p_glDeleteShader(fragment);

            std::printf("PROBE   %-15s compile=%-7s link=%-7s  # %s\n", c.id.c_str(),
                        compileStatus == GL_TRUE ? "ok" : "FALHOU",
                        linkStatus < 0 ? "n/a" : (linkStatus == GL_TRUE ? "ok" : "FALHOU"),
                        c.note.c_str());
            // Log cru do driver: e' ele que diz POR QUE o blob recusou (a evidencia util).
            printLogLines(c.id.c_str(), fragmentLog);
            printLogLines(c.id.c_str(), programLog);

            measurements.push_back(std::make_pair(c.id, compileStatus == GL_TRUE));
            if (c.id == "control") {
                controlOk = (compileStatus == GL_TRUE);
            }
        }

        std::printf("PROBE m3_shader_measurement=\n");
        for (const std::pair<std::string, bool> &m : measurements) {
            std::printf("PROBE   %-15s %s\n", m.first.c_str(),
                        m.second ? "COMPILA" : "NAO_COMPILA");
        }
        // Unico criterio de aceite desta secao: o COMPILADOR funciona. As demais linhas sao
        // MEDICAO do M3 (um NAO_COMPILA ali diz qual estrategia a janela de N precisa).
        check(controlOk, "[9b] controle: ESSL 3.20 trivial compila no driver real");

        // --------- [9c] ESSL DE PRODUCAO (ARQUIVO): o link do SHADER REAL ---------
        // [9] mede FORMAS sinteticas; faltava o artefato de verdade. O erro de orcamento de
        // samplers ("Too many fragment shader texture samplers") so' aparece no LINK -- por isso
        // cada caso e' um PAR VS+PS: `<nome>.vert.essl` + `<nome>.frag.essl`. Sem o VS parceiro o
        // link nao e' medido (fica `link=n/a`). Nada aqui e' criterio de aceite: e' MEDICAO do M3.
        std::printf("PROBE file_shader_dir=%s\n",
                    g_shaderDir.empty() ? "(nao informado)" : g_shaderDir.c_str());
        if (!g_shaderDir.empty()) {
            std::vector<std::string> fragmentNames;
            DIR *dir = opendir(g_shaderDir.c_str());
            if (dir == nullptr) {
                std::printf("PROBE file_shader_dir_erro=nao abriu\n");
            } else {
                const std::string suffix = ".frag.essl";
                struct dirent *entry = nullptr;
                while ((entry = readdir(dir)) != nullptr) {
                    std::string name = entry->d_name;
                    if (name.size() > suffix.size() &&
                        name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0) {
                        fragmentNames.push_back(name);
                    }
                }
                closedir(dir);
            }
            std::sort(fragmentNames.begin(), fragmentNames.end());
            std::printf("PROBE file_shader_cases=%zu\n", fragmentNames.size());

            std::vector<std::pair<std::string, std::string> > fileRows;
            for (const std::string &fragmentName : fragmentNames) {
                const std::string id = fragmentName.substr(0, fragmentName.size() - 10); // .frag.essl
                const std::string fragmentPath = g_shaderDir + "/" + fragmentName;
                const std::string vertexPath = g_shaderDir + "/" + id + ".vert.essl";

                std::string fragmentSource;
                std::string vertexSource;
                const bool hasFragment = readWholeFile(fragmentPath, fragmentSource);
                const bool hasVertex = readWholeFile(vertexPath, vertexSource);

                int compileStatus = 0;
                int linkStatus = -1;
                std::string fragmentLog;
                std::string programLog;

                if (!hasFragment) {
                    std::printf("PROBE   %-18s compile=n/a     link=n/a       # ARQUIVO AUSENTE\n",
                                id.c_str());
                } else {
                    const char *sourcePtr = fragmentSource.c_str();
                    const unsigned fragment = p_glCreateShader(GL_FRAGMENT_SHADER);
                    p_glShaderSource(fragment, 1, &sourcePtr, nullptr);
                    p_glCompileShader(fragment);
                    p_glGetShaderiv(fragment, GL_COMPILE_STATUS, &compileStatus);
                    int logLength = 0;
                    p_glGetShaderiv(fragment, GL_INFO_LOG_LENGTH, &logLength);
                    if (logLength > 1) {
                        std::vector<char> buffer(static_cast<size_t>(logLength) + 1, '\0');
                        p_glGetShaderInfoLog(fragment, logLength, nullptr, buffer.data());
                        fragmentLog = buffer.data();
                    }

                    if (compileStatus == GL_TRUE && hasVertex) {
                        const char *vsPtr = vertexSource.c_str();
                        const unsigned vertex = p_glCreateShader(GL_VERTEX_SHADER);
                        p_glShaderSource(vertex, 1, &vsPtr, nullptr);
                        p_glCompileShader(vertex);
                        const unsigned program = p_glCreateProgram();
                        p_glAttachShader(program, vertex);
                        p_glAttachShader(program, fragment);
                        p_glLinkProgram(program);
                        p_glGetProgramiv(program, GL_LINK_STATUS, &linkStatus);
                        int programLogLength = 0;
                        p_glGetProgramiv(program, GL_INFO_LOG_LENGTH, &programLogLength);
                        if (programLogLength > 1) {
                            std::vector<char> buffer(static_cast<size_t>(programLogLength) + 1, '\0');
                            p_glGetProgramInfoLog(program, programLogLength, nullptr, buffer.data());
                            programLog = buffer.data();
                        }
                        p_glDeleteProgram(program);
                        p_glDeleteShader(vertex);
                    }
                    p_glDeleteShader(fragment);

                    std::printf("PROBE   %-18s compile=%-7s link=%-7s  # %s\n", id.c_str(),
                                compileStatus == GL_TRUE ? "ok" : "FALHOU",
                                linkStatus < 0 ? "n/a" : (linkStatus == GL_TRUE ? "ok" : "FALHOU"),
                                hasVertex ? "par VS+PS (link medido)"
                                          : "sem .vert.essl (link nao medido)");
                    printLogLines(id.c_str(), fragmentLog);
                    printLogLines(id.c_str(), programLog);
                    fileRows.push_back(std::make_pair(
                        id, std::string("compile=") + (compileStatus == GL_TRUE ? "ok" : "FALHOU") +
                                " link=" +
                                (linkStatus < 0 ? "n/a" : (linkStatus == GL_TRUE ? "ok" : "FALHOU"))));
                }
            }

            std::printf("PROBE file_shader_measurement=\n");
            for (const std::pair<std::string, std::string> &row : fileRows) {
                std::printf("PROBE   %-18s %s\n", row.first.c_str(), row.second.c_str());
            }
        }
    }

    // ---------- epilogo ----------
    p_eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    if (p_eglDestroyContext != nullptr) {
        p_eglDestroyContext(display, context);
    }
    if (p_eglDestroySurface != nullptr) {
        p_eglDestroySurface(display, surface);
    }
    if (p_eglReleaseThread != nullptr) {
        p_eglReleaseThread();
    }
    if (p_eglTerminate != nullptr) {
        p_eglTerminate(display);
    }
    if (drmFd >= 0) {
        close(drmFd);
    }

    info("checks_total", "%d", g_checks);
    info("checks_failed", "%d", g_failures);
    std::printf("PROBE result=%s\n", g_failures == 0 ? "PASS" : "FAIL");
    return (g_failures == 0) ? 0 : 1;
}