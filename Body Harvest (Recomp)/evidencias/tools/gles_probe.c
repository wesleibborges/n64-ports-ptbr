/* glesprobe - cria um contexto OpenGL ES pelo SDL2 (KMSDRM/EGL/GBM) e reporta
 * as capacidades reais que um backend GLES do RT64 precisa.
 *
 * Por que existe: no R36S (dArkOS, kernel 4.4.189) NAO existe Vulkan que
 * apresente em KMSDRM (nenhum ICD expoe VK_KHR_display - ver
 * evidencias/evidence_firmware_vulkan_audit_20261017.md). O unico caminho com
 * aceleracao de hardware e OpenGL ES pelo blob ARM (libmali, EGL+GBM).
 * Este probe confirma, NO PROPRIO DEVICE, o que o SDL KMSDRM+GLES entrega.
 *
 * NAO linka contra libGLESv2/libEGL: todas as funcoes vem via
 * SDL_GL_GetProcAddress (funciona com qualquer driver instalado).
 *
 * Uso:
 *   ./glesprobe                 (usa o driver de video automatico do SDL)
 *   SDL_VIDEODRIVER=kmsdrm ./glesprobe
 *   SDL_VIDEODRIVER=dummy   ./glesprobe   (smoke test sem GPU)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <SDL2/SDL.h>
#include <GLES3/gl32.h> /* somente constantes/tipos; sem link com libGLESv2 */

typedef const GLubyte *(*PFN_glGetString)(GLenum name);
typedef void (*PFN_glGetIntegerv)(GLenum pname, GLint *params);
typedef const GLubyte *(*PFN_glGetStringi)(GLenum name, GLuint index);
typedef void (*PFN_glClearColor)(GLclampf r, GLclampf g, GLclampf b, GLclampf a);
typedef void (*PFN_glClear)(GLbitfield mask);
typedef void (*PFN_glFinish)(void);

static PFN_glGetString p_glGetString;
static PFN_glGetIntegerv p_glGetIntegerv;
static PFN_glGetStringi p_glGetStringi;
static PFN_glClearColor p_glClearColor;
static PFN_glClear p_glClear;
static PFN_glFinish p_glFinish;

/* Capacidades usadas pelo backend GLES do RT64 (Plume) */
static const char *need_exts[] = {
    "GL_EXT_geometry_shader",
    "GL_OES_geometry_shader",
    "GL_EXT_multisampled_render_to_texture",
    "GL_ARM_shader_framebuffer_fetch",
    "GL_EXT_shader_framebuffer_fetch",
    "GL_EXT_buffer_storage",
    "GL_EXT_texture_cube_map_array",
    "GL_EXT_shader_io_blocks",
    "GL_EXT_gpu_shader5",
    "GL_OES_texture_storage_multisample_2d_array",
    "GL_EXT_disjoint_timer_query",
    "GL_EXT_blend_func_extended",
    "GL_EXT_draw_buffers_indexed",
    "GL_EXT_copy_image",
    "GL_EXT_texture_filter_anisotropic",
    "GL_KHR_debug",
    "GL_EXT_map_buffer_range",
    "GL_OES_EGL_image",
    NULL
};

static int has_ext(const char *name)
{
    GLint n = 0, i;
    if (!p_glGetStringi) {
        /* fallback estilo GLES2: lista separada por espacos */
        const char *s = (const char *)p_glGetString(GL_EXTENSIONS);
        size_t len = strlen(name);
        const char *p = s;
        if (!s) return 0;
        while ((p = strstr(p, name)) != NULL) {
            char after = p[len];
            if ((p == s || p[-1] == ' ') && (after == ' ' || after == '\0')) return 1;
            p += len;
        }
        return 0;
    }
    p_glGetIntegerv(GL_NUM_EXTENSIONS, &n);
    for (i = 0; i < n; i++) {
        const char *e = (const char *)p_glGetStringi(GL_EXTENSIONS, (GLuint)i);
        if (e && strcmp(e, name) == 0) return 1;
    }
    return 0;
}

static void p_int(const char *label, GLenum pname)
{
    GLint v = 0;
    if (!p_glGetIntegerv) return;
    p_glGetIntegerv(pname, &v);
    printf("  %-46s %d\n", label, (int)v);
}

int main(int argc, char **argv)
{
    SDL_Window *win = NULL;
    SDL_GLContext ctx = NULL;
    const char *drv_env = getenv("SDL_VIDEODRIVER");
    int major = -1, minor = -1, profile = -1;
    int rc = 0;

    (void)argc; (void)argv;

    printf("=== glesprobe (SDL2 + OpenGL ES) ===\n");
    printf("SDL_VIDEODRIVER(env) : %s\n", drv_env ? drv_env : "(nao definido)");
    printf("SDL revision         : %s\n", SDL_GetRevision());
    printf("SDL compiled version : %d.%d.%d\n", SDL_MAJOR_VERSION, SDL_MINOR_VERSION, SDL_PATCHLEVEL);

    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        printf("SDL_Init(FALHA): %s\n", SDL_GetError());
        return 1;
    }
    printf("driver de video ativo: %s\n", SDL_GetCurrentVideoDriver());
    {
        int i, n = SDL_GetNumVideoDrivers();
        printf("video drivers (%d)   :", n);
        for (i = 0; i < n; i++) printf(" %s", SDL_GetVideoDriver(i));
        printf("\n");
    }

    if (SDL_VideoInit(NULL) != 0) {
        printf("SDL_VideoInit(FALHA): %s\n", SDL_GetError());
        goto out;
    }
    printf("driver apos VideoInit: %s\n", SDL_GetCurrentVideoDriver());
    {
        int i, n = SDL_GetNumVideoDisplays();
        printf("displays             : %d\n", n);
        for (i = 0; i < n; i++) {
            SDL_DisplayMode m;
            if (SDL_GetDesktopDisplayMode(i, &m) == 0)
                printf("  display[%d]: %dx%d @%dHz fmt=%s\n", i, m.w, m.h, m.refresh_rate,
                       SDL_GetPixelFormatName(m.format));
        }
    }

    /* pede contexto ES 3.2 (o blob Mali suporta GLES 3.2) */
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);

    if (SDL_GL_LoadLibrary(NULL) != 0) {
        printf("SDL_GL_LoadLibrary(FALHA): %s\n", SDL_GetError());
        goto out;
    }
    printf("SDL_GL_LoadLibrary    : OK\n");

    win = SDL_CreateWindow("glesprobe", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                           640, 480, SDL_WINDOW_OPENGL);
    if (!win) {
        printf("SDL_CreateWindow(FALHA): %s\n", SDL_GetError());
        rc = 2;
        goto out;
    }
    printf("janela                : OK (driver=%s)\n", SDL_GetCurrentVideoDriver());

    ctx = SDL_GL_CreateContext(win);
    if (!ctx) {
        printf("SDL_GL_CreateContext(FALHA): %s\n", SDL_GetError());
        rc = 3;
        goto out;
    }
    SDL_GL_MakeCurrent(win, ctx);

    SDL_GL_GetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, &major);
    SDL_GL_GetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, &minor);
    SDL_GL_GetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, &profile);
    printf("contexto GL           : %d.%d (profile_mask=0x%x, ES=%d)\n",
           major, minor, profile, (profile & SDL_GL_CONTEXT_PROFILE_ES) ? 1 : 0);

    p_glGetString = (PFN_glGetString)SDL_GL_GetProcAddress("glGetString");
    p_glGetIntegerv = (PFN_glGetIntegerv)SDL_GL_GetProcAddress("glGetIntegerv");
    p_glGetStringi = (PFN_glGetStringi)SDL_GL_GetProcAddress("glGetStringi");
    p_glClearColor = (PFN_glClearColor)SDL_GL_GetProcAddress("glClearColor");
    p_glClear = (PFN_glClear)SDL_GL_GetProcAddress("glClear");
    p_glFinish = (PFN_glFinish)SDL_GL_GetProcAddress("glFinish");

    if (!p_glGetString || !p_glGetIntegerv) {
        printf("glGetString/glGetIntegerv NAO resolvidos - contexto invalido\n");
        rc = 4;
        goto out;
    }
    printf("\n--- identificacao ---\n");
    printf("  GL_VERSION           : %s\n", (const char *)p_glGetString(GL_VERSION));
    printf("  GL_VENDOR            : %s\n", (const char *)p_glGetString(GL_VENDOR));
    printf("  GL_RENDERER          : %s\n", (const char *)p_glGetString(GL_RENDERER));
    printf("  GL_SHADING_LANGUAGE  : %s\n", (const char *)p_glGetString(GL_SHADING_LANGUAGE_VERSION));

    printf("\n--- limites relevantes para o RT64 ---\n");
    p_int("GL_MAX_TEXTURE_SIZE", GL_MAX_TEXTURE_SIZE);
    p_int("GL_MAX_RENDERBUFFER_SIZE", GL_MAX_RENDERBUFFER_SIZE);
    p_int("GL_MAX_COLOR_ATTACHMENTS", GL_MAX_COLOR_ATTACHMENTS);
    p_int("GL_MAX_DRAW_BUFFERS", GL_MAX_DRAW_BUFFERS);
    p_int("GL_MAX_SAMPLES", GL_MAX_SAMPLES);
    p_int("GL_MAX_UNIFORM_BUFFER_BINDINGS", GL_MAX_UNIFORM_BUFFER_BINDINGS);
    p_int("GL_MAX_UNIFORM_BLOCK_SIZE", GL_MAX_UNIFORM_BLOCK_SIZE);
    p_int("GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS", GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS);
    p_int("GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS", GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS);
    p_int("GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS", GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS);
    p_int("GL_MAX_TEXTURE_IMAGE_UNITS", GL_MAX_TEXTURE_IMAGE_UNITS);
    p_int("GL_MAX_VERTEX_UNIFORM_VECTORS", GL_MAX_VERTEX_UNIFORM_VECTORS);
    p_int("GL_MAX_FRAGMENT_UNIFORM_VECTORS", GL_MAX_FRAGMENT_UNIFORM_VECTORS);
    p_int("GL_MAX_VERTEX_ATTRIBS", GL_MAX_VERTEX_ATTRIBS);
    p_int("GL_MAX_ARRAY_TEXTURE_LAYERS", GL_MAX_ARRAY_TEXTURE_LAYERS);
    p_int("GL_MAX_3D_TEXTURE_SIZE", GL_MAX_3D_TEXTURE_SIZE);
    {
        GLint v[3] = {0, 0, 0};
        p_glGetIntegerv(GL_MAX_COMPUTE_WORK_GROUP_SIZE, v);
        printf("  %-46s %d %d %d\n", "GL_MAX_COMPUTE_WORK_GROUP_SIZE",
               (int)v[0], (int)v[1], (int)v[2]);
    }

    printf("\n--- extensoes exigidas/uteis para o backend GLES do RT64 ---\n");
    if (p_glGetStringi) {
        GLint n = 0;
        p_glGetIntegerv(GL_NUM_EXTENSIONS, &n);
        printf("  (total de extensoes reportadas: %d)\n", (int)n);
    }
    {
        int i, ok = 0;
        for (i = 0; need_exts[i]; i++) {
            int h = has_ext(need_exts[i]);
            if (h) ok++;
            printf("  %-46s %s\n", need_exts[i], h ? "SIM" : "nao");
        }
        printf("  ==> %d de %d extensoes uteis presentes\n", ok, i);
    }

    printf("\n--- teste de apresentacao (clear + swap) ---\n");
    if (p_glClearColor && p_glClear) {
        Uint32 t0 = SDL_GetTicks();
        int frame;
        for (frame = 0; frame < 3; frame++) {
            p_glClearColor((frame == 0) ? 0.1f : 0.0f, 0.2f, 0.3f, 1.0f);
            p_glClear(GL_COLOR_BUFFER_BIT);
            if (p_glFinish) p_glFinish();
            SDL_GL_SwapWindow(win);
        }
        printf("  3 frames apresentados em %u ms (swap OK)\n",
               (unsigned)(SDL_GetTicks() - t0));
    }

    printf("\nRESULTADO: SDL KMSDRM + OpenGL ES %d.%d FUNCIONAL\n", major, minor);

out:
    if (ctx) SDL_GL_DeleteContext(ctx);
    if (win) SDL_DestroyWindow(win);
    SDL_Quit();
    return rc;
}