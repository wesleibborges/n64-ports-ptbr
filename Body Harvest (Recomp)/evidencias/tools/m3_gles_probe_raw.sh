#!/bin/bash
# M3 (pre-validacao no device) -- consolidacao RAW da sonda GLES do R36S (Mali-G31).
#
# Fonte de verdade da evidencia evidence_m3_gles_device_probe_20261018.md: RE-EXECUTA cada
# verificacao e imprime a saida crua, para que qualquer pessoa reproduza.
#
# Uso: bash m3_gles_probe_raw.sh > /root/bhrecomp/m3_gles_probe/raw_offline.txt
set -u

ROOTFS=/opt/r36s/rootfs
LIBDIR="$ROOTFS/usr/lib/aarch64-linux-gnu"
BLOB="$LIBDIR/libmali-bifrost-g31-rxp0-gbm.so"
OUT="${OUT_DIR:-/root/bhrecomp/m3_gles_probe}"
PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"

echo "=== M3 | RAW -- sonda GLES do R36S (Mali-G31) ==="
echo "data_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "rootfs=$ROOTFS"
echo "blob=$BLOB"
echo

echo "########## [1] CADEIA DE SYMLINKS DO EGL/GLES NO DEVICE ##########"
( cd "$LIBDIR" && ls -la libEGL.so* libGLESv2.so* libGLESv3.so* libgbm.so* libmali* libMali* )
echo

echo "########## [2] O BLOB E' LINKAVEL COMO BIBLIOTECA? (esperado: NAO) ##########"
echo '--- SONAME / RPATH (esperado: vazio) ---'
readelf -d "$BLOB" | grep -iE 'SONAME|RUNPATH|RPATH' || echo "(nenhum SONAME/RUNPATH/RPATH nos DT_* do blob)"
echo '--- teste de link real contra o blob ---'
printf '#include <EGL/egl.h>\nint main(){ EGLDisplay d = eglGetDisplay(EGL_DEFAULT_DISPLAY); (void)d; return 0; }\n' > /tmp/m3_egl_link_test.c
aarch64-linux-gnu-gcc -O1 /tmp/m3_egl_link_test.c -o /tmp/m3_egl_link_test \
    -L"$LIBDIR" -l:libEGL.so.1 2>&1 | head -6
echo "link_rc=${PIPESTATUS[0]} (diferente de 0 == blob NAO e' linkavel; usar o stub)"
echo

echo "########## [3] O BLOB EXPORTA O NUCLEO EGL + GLES + GBM? ##########"
for symbol in eglGetDisplay eglGetProcAddress eglInitialize eglQueryString eglBindAPI \
              eglChooseConfig eglCreatePbufferSurface eglCreateContext eglMakeCurrent \
              eglTerminate eglGetError eglReleaseThread eglCreateWindowSurface eglSwapBuffers \
              eglQuerySurface eglGetConfigAttrib eglDestroyContext eglDestroySurface; do
    if nm -D --defined-only "$BLOB" 2>/dev/null | grep -q " T $symbol$"; then
        printf '  %-28s EXPORTA\n' "$symbol"
    else
        printf '  %-28s ausente\n' "$symbol"
    fi
done
echo '--- simbolos que a nota do M2 supunha ausentes ---'
for symbol in eglGetPlatformDisplay eglGetPlatformDisplayEXT; do
    if nm -D --defined-only "$BLOB" 2>/dev/null | grep -q " T $symbol$"; then
        printf '  %-28s EXPORTA\n' "$symbol"
    else
        printf '  %-28s AUSENTE (SDL usa eglGetDisplay(gbm_device))\n' "$symbol"
    fi
done
echo '--- GBM ---'
nm -D --defined-only "$BLOB" 2>/dev/null | grep -E ' T gbm_(create_device|surface_create|bo_create|device_get_fd)$' | sed 's/^/  /'
echo '--- GL core (amostra) ---'
nm -D --defined-only "$BLOB" 2>/dev/null | grep -E ' T gl(GetString|Clear|ClearColor|ReadPixels|GenTextures|FramebufferTexture2D)$' | sed 's/^/  /'
echo "total de simbolos T no blob: $(nm -D --defined-only "$BLOB" 2>/dev/null | grep -cE ' T ')"
echo

echo "########## [4] CAPACIDADES OFFLINE (strings do blob) ##########"
echo '--- versao GLES embutida (o alvo ES 3.2 existe antes de rodar) ---'
strings -a "$BLOB" | grep -aE '^OpenGL ES [0-9]' | sort -u
echo '--- checagem NEGATIVA (esperado ausente) ---'
# ATENCAO: GL_NV_gpu_shader5 (variante NVIDIA) NAO e' o mesmo que GL_EXT_gpu_shader5, que e' o
# que decide a legalidade do indice dinamico de sampler (M3) -- este ultimo esta' na POSITIVA.
for needle in GL_EXT_texture_norm16 GL_EXT_render_snorm GL_NV_gpu_shader5 NV_mesh_shader; do
    if strings -a "$BLOB" | grep -qa "$needle"; then printf '  %-30s citado\n' "$needle"; else printf '  %-30s NAO citado\n' "$needle"; fi
done
echo '--- checagem POSITIVA (dirigida ao plano) ---'
for needle in GL_EXT_gpu_shader5 GL_EXT_blend_func_extended GL_ARM_shader_framebuffer_fetch \
              GL_EXT_multisampled_render_to_texture \
              GL_EXT_buffer_storage GL_EXT_texture_storage GL_EXT_texture_format_BGRA8888 \
              GL_KHR_debug GL_EXT_disjoint_timer_query GL_EXT_geometry_shader \
              GL_EXT_texture_border_clamp GL_OES_texture_storage_multisample_2d_array; do
    if strings -a "$BLOB" | grep -qa "$needle"; then printf '  %-52s PRESENTE\n' "$needle"; else printf '  %-52s AUSENTE\n' "$needle"; fi
done
echo

echo "########## [5] STUB DE LINK-TIME ##########"
ls -la "$OUT/stub/libEGL.so.1" 2>/dev/null
readelf -d "$OUT/stub/libEGL.so.1" 2>/dev/null | grep -iE 'SONAME'
md5sum "$OUT/stub/libEGL.so.1" 2>/dev/null
echo

echo "########## [6] BINARIOS ##########"
for binary in gles_device_probe_aarch64 gles_smoke_aarch64; do
    echo "--- $binary ---"
    if [ -f "$OUT/$binary" ]; then
        md5sum "$OUT/$binary"
        stat -c '    tamanho=%s bytes' "$OUT/$binary"
        file -b "$OUT/$binary"
        echo '    DT_NEEDED:'
        readelf -d "$OUT/$binary" | grep -i needed | sed 's/^/      /'
        printf '    RPATH/RUNPATH: '
        readelf -d "$OUT/$binary" | grep -iE 'rpath|runpath' || echo "(vazio)"
    else
        echo "    AUSENTE (rode m3_build_gles_probe.sh)"
    fi
    echo
done

echo "########## [7] EXECUCAO SOB QEMU CONTRA A ROOTFS DO DEVICE ##########"
echo '(o teto do fluxo deve passar; a criacao de contexto deve FALHAR por ausencia de GPU)'
for binary in gles_device_probe_aarch64 gles_smoke_aarch64; do
    echo "--- $binary ---"
    if [ -f "$OUT/$binary" ]; then
        timeout 120 qemu-aarch64-static -L "$ROOTFS" "$OUT/$binary" --short 2>&1
        echo "qemu_rc=$?"
    else
        echo "AUSENTE"
    fi
    echo
done

echo "########## [8] PACOTE PARA O CARTAO SD ##########"
if find "$PROJ/evidencias/gles_device_probe_pkg" -name 'libEGL*' -o -name 'libGLES*' -o -name 'libgbm*' 2>/dev/null | grep -q .; then
    echo "FALHA: lib de sistema encontrada no pacote"
else
    echo "ok: o pacote so' tem binarios + runner + README + os casos de ESSL de producao"
fi
( cd "$PROJ/evidencias/gles_device_probe_pkg" && ls -la && echo && find . -maxdepth 1 -type f | sort | xargs md5sum )
echo '--- casos de ESSL de producao (secao [9c] da sonda) ---'
( cd "$PROJ/evidencias/gles_device_probe_pkg/shader_cases" 2>/dev/null && ls -la \
  && echo && find . -type f | sort | xargs md5sum )
echo "--- quantos arrays de sampler por caso (o orcamento do M3) ---"
for frag in "$PROJ"/evidencias/gles_device_probe_pkg/shader_cases/*.frag.essl; do
    printf '  %-32s arrays_com_janela=%s ocorrencias_8192=%s\n' "$(basename "$frag")" \
        "$(grep -cE '^uniform .*sampler.*\[[0-9]+\];' "$frag")" "$(grep -c '8192' "$frag")"
done
echo '--- tarball ---'
ls -la "$PROJ/evidencias/gles_device_probe_pkg.tar.gz" 2>/dev/null
md5sum "$PROJ/evidencias/gles_device_probe_pkg.tar.gz" 2>/dev/null
tar tzf "$PROJ/evidencias/gles_device_probe_pkg.tar.gz" 2>/dev/null

echo
echo "=== fim do RAW ==="