/*
 * gles_egl_stub.c -- STUB DE LINK-TIME para libEGL.so.1.  *** NAO VAI PARA O DEVICE ***
 *
 * POR QUE ELE EXISTE (medido em 2026-10-18):
 * o blob EGL do R36S (`libEGL.so.1 -> libMali.so -> libmali-bifrost-g31-rxp0-gbm.so`) nao tem
 * SONAME e tem `.dynsym` malformado para o binutils:
 *     ld: libEGL.so.1: .dynsym local symbol at index 3 (>= sh_info of 3)
 * Ou seja: o linker NAO consegue usar o blob como biblioteca de link. Sem este stub, o
 * gles_smoke (que chama 10 entry points EGL de forma direta) nao poderia ser sequer LINKADO
 * para aarch64 -- embora funcione perfeitamente em runtime no device.
 *
 * COMO O TRUQUE FUNCIONA:
 * o stub grava SONAME=`libEGL.so.1` e define os 10 simbolos com corpos no-op. O binario sai
 * com DT_NEEDED `libEGL.so.1`; no device, o ld.so resolve esse nome para o blob Mali REAL e o
 * stub nunca e' carregado. Este arquivo e' ferramenta de build, nada mais.
 *
 * TRAVA DE SEGURANCA:
 * o construtor abaixo grita em stderr se o stub for carregado -- isso so' acontece se alguem
 * publicar o stub junto do binario ou mexer no LD_LIBRARY_PATH. Se voce vir essa mensagem no
 * device, a causa e' o empacotamento, nao o backend.
 *
 * Os simbolos definidos sao EXATAMENTE os que o gles_smoke referencia no link (levantados por
 * `grep -oE 'egl[A-Za-z]+' gles_smoke.cpp`): o backend plume_gles NAO referencia nenhum
 * (o eglSwapBuffers que aparece la' esta' dentro de um comentario; o swap vem por
 * GLESSwapChainFunctions).
 */

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <stdio.h>

__attribute__((constructor)) static void gles_egl_stub_loaded(void) {
    fprintf(stderr,
            "\n*** AVISO: libEGL STUB DE LINK-TIME foi carregada. ***\n"
            "*** Este arquivo NAO deve ser publicado no device: la' o libEGL.so.1 e' o blob Mali.\n"
            "*** Verifique LD_LIBRARY_PATH / o conteudo do pacote. O backend NAO tem culpa. ***\n\n");
}

EGLDisplay eglGetDisplay(EGLNativeDisplayType display_id) {
    (void)display_id;
    return EGL_NO_DISPLAY;
}

EGLBoolean eglInitialize(EGLDisplay dpy, EGLint *major, EGLint *minor) {
    (void)dpy; (void)major; (void)minor;
    return EGL_FALSE;
}

const char *eglQueryString(EGLDisplay dpy, EGLint name) {
    (void)dpy; (void)name;
    return (const char *)0;
}

EGLBoolean eglChooseConfig(EGLDisplay dpy, const EGLint *attrib_list, EGLConfig *configs,
                           EGLint config_size, EGLint *num_config) {
    (void)dpy; (void)attrib_list; (void)configs; (void)config_size;
    if (num_config != 0) {
        *num_config = 0;
    }
    return EGL_FALSE;
}

EGLSurface eglCreatePbufferSurface(EGLDisplay dpy, EGLConfig config, const EGLint *attrib_list) {
    (void)dpy; (void)config; (void)attrib_list;
    return EGL_NO_SURFACE;
}

EGLContext eglCreateContext(EGLDisplay dpy, EGLConfig config, EGLContext share_context,
                            const EGLint *attrib_list) {
    (void)dpy; (void)config; (void)share_context; (void)attrib_list;
    return EGL_NO_CONTEXT;
}

EGLBoolean eglMakeCurrent(EGLDisplay dpy, EGLSurface draw, EGLSurface read, EGLContext ctx) {
    (void)dpy; (void)draw; (void)read; (void)ctx;
    return EGL_FALSE;
}

EGLBoolean eglTerminate(EGLDisplay dpy) {
    (void)dpy;
    return EGL_FALSE;
}

EGLint eglGetError(void) {
    return EGL_SUCCESS;
}

/* Devolve NULL de proposito: se o stub fosse carregado por engano, o smoke reportaria os
 * 358 entry points AUSENTES (falha honesta e imediata) em vez de "passar" contra no-ops. */
__eglMustCastToProperFunctionPointerType eglGetProcAddress(const char *procname) {
    (void)procname;
    return 0;
}