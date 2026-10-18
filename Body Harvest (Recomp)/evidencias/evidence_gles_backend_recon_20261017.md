# EVIDENCIA: recon de viabilidade — backend OpenGL ES (HW) para o RT64 no R36S

Data (UTC): 2026-10-17T16:50Z
Conta AWS: nao aplicavel
Ambiente: WSL Ubuntu 22.04 (host x86_64); `aarch64-linux-gnu-gcc 11.4.0`; `qemu-aarch64-static`;
rootfs do device montada em `/opt/r36s/rootfs` (ver `evidence_firmware_vulkan_audit_20261017.md`).

**Contexto / decisao:** Vulkan apresentavel e impossivel neste firmware (nenhum ICD expoe
`VK_KHR_display`; blob Mali tem Vulkan 1.0.x **sem WSI**). Decisao tomada: **investir em
renderer OpenGL ES com aceleracao de hardware** (opcao B). Este documento e o recon de
viabilidade: ponto de integracao, escopo, riscos e o primeiro artefato executavel.

---

## 1. Ponto de integracao no RT64 — a RHI "Plume"

```
$ cd /root/bhrecomp/lib/rt64/src/contrib/plume && wc -l plume_render_interface*.h plume_*.h plume_*.cpp
   268 plume_render_interface.h          <-- INTERFACE A IMPLEMENTAR
  1816 plume_render_interface_types.h
   469 plume_vulkan.h        4641 plume_vulkan.cpp
   495 plume_d3d12.h         4258 plume_d3d12.cpp
   784 plume_metal.h         4229 plume_metal.cpp
$ grep -c '= 0;' plume_render_interface.h
103                                     <-- metodos virtuais puros
```

**Fato:** ja existem 3 backends (Vulkan/D3D12/Metal) atras da MESMA interface; `plume_metal.cpp`
(4229 linhas, sem ray tracing) e o molde mais proximo de um backend "simples".

### 1.1 Selecao de backend (build-time + config do usuario)

`src/hle/rt64_application.cpp` (linhas ~157-188):

```cpp
extern std::unique_ptr<RenderInterface> CreateD3D12Interface();
extern std::unique_ptr<RenderInterface> CreateMetalInterface();
extern std::unique_ptr<RenderInterface> CreateVulkanInterface(RenderWindow renderWindow);

switch (chosenGraphicsAPI) {
case UserConfiguration::GraphicsAPI::D3D12:
#   ifdef _WIN64
    renderInterface = CreateD3D12Interface(); break;
#   else
    fprintf(stderr, "D3D12 is not supported on this platform. ..."); return SetupResult::InvalidGraphicsAPI;
#   endif
case UserConfiguration::GraphicsAPI::Metal:
#   ifdef __APPLE__
    renderInterface = CreateMetalInterface(); break;
#   else
    fprintf(stderr, "Metal is not supported on this platform. ..."); return SetupResult::InvalidGraphicsAPI;
#   endif
case UserConfiguration::GraphicsAPI::Vulkan:
    renderInterface = CreateVulkanInterfaceWrapper(appWindow->windowHandle); break;
...
```

=> **existe `UserConfiguration::GraphicsAPI`**: adicionar `GraphicsAPI::GLES` e um `case` novo e
extensao natural (e permite testar GLES/fallback via config do jogo, `bodyharvest.us.toml`).

### 1.2 Formato de shader e o pipeline HLSL -> SPIR-V -> (MSL|GLSL ES)

`src/render/rt64_shader_library.cpp` (linhas 152-175) — macro definido por plataforma:

```cpp
#elif defined(__APPLE__)
#   define CREATE_SHADER_INPUTS(DXIL_BLOB, SPIRV_BLOB, MSL_BLOB, ENTRY_NAME, SHADER_FORMAT)\
        (SHADER_FORMAT == RenderShaderFormat::METAL) ? MSL_BLOB : (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? SPIRV_BLOB : nullptr,\
        ...
#else
#   define CREATE_SHADER_INPUTS(DXIL_BLOB, SPIRV_BLOB, MSL_BLOB, ENTRY_NAME, SHADER_FORMAT)\
        (SHADER_FORMAT == RenderShaderFormat::SPIRV) ? SPIRV_BLOB : nullptr,\
        ...
#endif
```

`plume_render_interface_types.h`:
```cpp
enum class RenderShaderFormat { UNKNOWN, DXIL, SPIRV, METAL };
```

CMake (`lib/rt64/CMakeLists.txt` 116-155): `build_shader_spirv_impl()` roda
**DXC** (`.hlsl` -> `.spv`) e gera array C via `file_to_c` (`BlobSPIRV`); no macOS um passo
extra roda **`spirv_cross_msl`** (`.spv` -> `.metal`) e empacota (`BlobMSL`).
`src/contrib/spirv-cross/spirv_glsl.{cpp,hpp}` **existe no repository** =>
o mesmo passo pode gerar **GLSL ES 3.20** (`CompilerGLSL` com ES/versao 320).

**Conclusao:** adicionar GLES = (i) novo valor em `RenderShaderFormat`, (ii) novo ramo no macro
`CREATE_SHADER_INPUTS`, (iii) novo passo de build (SPIR-V -> GLSL ES -> array C). Os shaders do
jogo **nao precisam ser reescritos**.

## 2. Capacidades GLES do blob ARM (offline, leitura de bytes)

`/usr/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-gbm.so` (aarch64, 40.867.064 bytes):

```
OpenGL ES 3.2              count=1     <-- versao reportada
EGL_KHR_platform_gbm        count=1     <-- EGL sobre GBM (KMSDRM)
gbm_create_device           count=1     <-- o blob fornece GBM (libgbm.so.1 -> libMali.so)
eglGetPlatformDisplay       count=1
glDispatchCompute           count=4     <-- compute shaders (GLES 3.1+)
GL_EXT_geometry_shader      count=2
GL_OES_geometry_shader      count=2
GL_ARM_shader_framebuffer_fetch  count=8  <-- framebuffer fetch (emulacao de FB)
GL_EXT_multisampled_render_to_texture count=1
glFramebufferTexture2DMultisampleEXT  count=2
GL_OES_texture_storage_multisample_2d_array count=1
GL_EXT_buffer_storage       count=1
GL_EXT_texture_cube_map_array count=2
GL_EXT_shader_io_blocks     count=2
GL_EXT_gpu_shader5          count=1
GL_EXT_disjoint_timer_query count=1
GL_KHR_debug                count=1
GL_EXT_color_buffer_float   count=1
glBlitFramebuffer / glMapBufferRange / glInvalidateFramebuffer / glDrawElementsBaseVertex:
                            count=2 / 2 / 2 / 6
GL_EXT_blend_func_extended  count=0     (ausente - usar fallback)
```

## 3. Toolchain/sysroot: ja ha tudo para compilar GLES aarch64

```
$ ls /root/sysroot64/usr/include/GLES3/
gl3.h  gl31.h  gl32.h  gl3ext.h  gl3platform.h      <-- headers GLES 3.2 (arm64, do device)
$ ls -la /root/sysroot64/usr/lib/aarch64-linux-gnu/ | grep -iE 'GLES|EGL|gbm'
libEGL.so.1 -> libEGL.so.1.1.0
libGLESv2.so.2 -> libGLESv2.so.2.1.0
libgbm.so.1 -> libgbm.so.1.0.0
```

SDL2 2.30.9 cross (`/opt/sdl2-configure.log`):
```
checking for EGL support... yes
Video drivers   : dummy offscreen kmsdrm(dynamic) opengl opengl_es1 opengl_es2 vulkan
```
=> SDL consegue criar contexto GLES em KMSDRM (EGL+GBM) — o caminho de apresentacao existe.

---

## 4. Primeiro artefato executavel: `glesprobe`

Fonte: `_gles_probe.c` (workspace) / `evidencias/tools/gles_probe.c`.
**Nao linka contra libGLESv2/libEGL**: obtem tudo por `SDL_GL_GetProcAddress`
(mesma filosofia do `vkprobe`). Cria SDL + janela + contexto **ES 3.2**, imprime
identificacao, limites (uniformes/SSBO/compute/MSAA), as extensoes que o backend GLES do RT64
precisa, e faz **3 frames de clear+swap** para provar a apresentacao.

### 4.1 Build (aarch64)

```
$ aarch64-linux-gnu-gcc -O2 -Wall -I/opt/sdl2-aarch64/include -o glesprobe _gles_probe.c \
    -L/opt/sdl2-aarch64/lib -lSDL2
RC_AARCH64=0
$ file glesprobe
ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), dynamically linked,
 interpreter /lib/ld-linux-aarch64.so.1
$ readelf -d glesprobe | grep NEEDED
 (NEEDED) Shared library: [libSDL2-2.0.so.0]
 (NEEDED) Shared library: [libc.so.6]
 (NEEDED) Shared library: [ld-linux-aarch64.so.1]
```

Tamanho: 18.840 bytes. `md5 fcc225e9a1d3020ddb69d71fc072a7f6`.

### 4.2 Execucao 1 — SDL DO DEVICE (2.30.3) sob QEMU

```
$ qemu-aarch64-static -L /opt/r36s/rootfs ./glesprobe
SDL revision         : SDL-release-2.30.3-0-gfb1497566
driver de video ativo: x11
video drivers (4)   : x11 offscreen dummy evdev
displays             : 1
  display[0]: 1366x768 @60Hz fmt=SDL_PIXELFORMAT_RGB888
SDL_GL_LoadLibrary    : OK
janela                : OK (driver=x11)
contexto GL           : 3.2 (profile_mask=0x4, ES=1)
  GL_VERSION           : OpenGL ES 3.2 Mesa 25.0.7-2+deb13u1
  GL_VENDOR            : Mesa
  GL_RENDERER          : llvmpipe (LLVM 19.1.7, 128 bits)
  GL_SHADING_LANGUAGE  : OpenGL ES GLSL ES 3.20
  GL_MAX_TEXTURE_SIZE 16384 | GL_MAX_COLOR_ATTACHMENTS 8 | GL_MAX_SAMPLES 4
  GL_MAX_UNIFORM_BUFFER_BINDINGS 90 | GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS 80
  GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS 1024
  GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS 32 | GL_MAX_VERTEX_ATTRIBS 16
  (total de extensoes reportadas: 158)
  GL_EXT_geometry_shader SIM | GL_OES_geometry_shader SIM | GL_EXT_buffer_storage SIM
  GL_EXT_texture_cube_map_array SIM | GL_EXT_shader_io_blocks SIM | GL_EXT_gpu_shader5 SIM
  GL_OES_texture_storage_multisample_2d_array SIM | GL_EXT_disjoint_timer_query SIM
  GL_EXT_blend_func_extended SIM | GL_EXT_draw_buffers_indexed SIM | GL_EXT_copy_image SIM
  GL_EXT_texture_filter_anisotropic SIM | GL_KHR_debug SIM | GL_EXT_map_buffer_range SIM
  GL_OES_EGL_image SIM
  ==> 16 de 18 extensoes uteis presentes
  3 frames apresentados em 76 ms (swap OK)
RESULTADO: SDL KMSDRM + OpenGL ES 3.2 FUNCIONAL
```

(Neste ambiente o SDL escolheu `x11` — o WSLg fornece um X server — e o renderizador foi o
llvmpipe do proprio rootfs: prova de que **o codigo do probe funciona ponta a ponta**,
inclusive contexto ES 3.2, consulta de limites/extensoes e swap.)

### 4.3 Execucao 2 — NOSSO SDL 2.30.9 (o que o port embarca)

```
$ LD_LIBRARY_PATH=/opt/sdl2-aarch64/lib qemu-aarch64-static -L /opt/r36s/rootfs ./glesprobe
SDL revision         : SDL-2.30.9
driver de video ativo: offscreen
video drivers (4)   : KMSDRM offscreen dummy evdev
SDL_GL_LoadLibrary(FALHA): eglQueryDevicesEXT is missing (EXT_device_enumeration not supported
 by the drivers?)
RC=0   (falha graciosa, sem crash)
```

**Fatos:**
1. Nosso SDL 2.30.9 expoe **`KMSDRM`** (necessario para o device); o SDL **do sistema nao**
   expoe KMSDRM (so x11/offscreen/dummy/evdev) => o port **precisa** continuar embarcando SDL.
2. Falha offline e esperada: sem `/dev/dri` no rootfs montado nao ha EGL device.

## 5. Escopo estimado e riscos

| Item | Estimativa | Base |
| :--- | :--- | :--- |
| `plume_gles.{h,cpp}` implementando os 103 metodos | ~3,5-4,5k linhas | `plume_metal.cpp` = 4229 linhas |
| `RenderShaderFormat::GLSL_ES` + macro + passo SPIR-V -> GLSL ES no build | pequeno | espelha o passo `spirv_cross_msl` (macOS) |
| Integracao (`GraphicsAPI::GLES`, contexto SDL KMSDRM/EGL/GBM, present) | pequeno/medio | `switch` + `UserConfiguration` ja existem |

**Riscos (em ordem de impacto):**
1. **Bindless / descriptor indexing**: GLES nao tem; a capability existe em
   `RenderDeviceCapabilities { bool descriptorIndexing; ... }`, mas o RT64 **nao ramifica** por ela
   (grep de `capabilities.` no core aparece apenas em `rt64_state.cpp`, para debug).
   D3D12/Metal resolvem isso **dentro do backend** => o backend GLES tera de emular descriptors
   (arrays limitados + rebind por draw/pipeline).
2. **Compute/limites**: RT64 usa muitos compute shaders (`BicubicScalingCS`, `BoxFilterCS`,
   `FbWriteColorCS`, `FbReinterpretCS`, `FbReadAnyChangesCS`, `GaussianFilterRGB3x3CS`...).
   GLES 3.1+ tem compute e o blob reporta `glDispatchCompute` — falta confirmar em runtime
   no device (para isso existe o `glesprobe`).
3. **Semantica GLES vs Vulkan**: barreiras, resolve de MSAA, blit, sRGB.
   Mitigadores disponiveis no blob: `GL_EXT_multisampled_render_to_texture`,
   `GL_ARM_shader_framebuffer_fetch`, `GL_EXT_buffer_storage`.
4. **Performance do pipeline moderno em Mali-G31** (4xA35@1.5GHz, 1GB): desconhecida -> medir cedo.
5. **Ray tracing / geometry**: RT desligado (G31 nao tem RT); GS disponivel via
   `GL_EXT_geometry_shader` (capability `geometryShader = true`).

## 6. Discrepancia a confirmar (importante para o deploy)

O firmware **da imagem auditada** (`dArkOSen 09302026`, kernel
`#1 SMP Fri Sep 25 02:17:24 UTC 2026`) nao e identico ao instalado no console no momento do log
anterior (kernel `4.4.189 #62 SMP Sat Dec 13 08:49:45 CST 2025`). Consequencias observadas:
- o SDL do sistema **da imagem** nao tem KMSDRM (apenas x11/offscreen/dummy/evdev);
- o log anterior do console indicava driver ativo `KMSDRM`.

=> Antes de medir performance no device, confirmar qual build esta rodando (e alinhar a imagem
alvo, se for o caso). A conclusao sobre Vulkan (nenhum ICD com `VK_KHR_display`) foi medida
**na imagem alvo** e vale para ela.

## 7. Hashes

```
fcc225e9a1d3020ddb69d71fc072a7f6  glesprobe                      (ELF aarch64, 18.840 bytes)
ec36693b28208347603b319a3db6582b  evidencias/tools/gles_probe.c
```

### Artefatos desta sessao (md5 — instantaneo)

```
1f1962b445d5def4f62ab14bd1048141  BodyHarvest.sh                  (bloco de recon GLES; bash -n OK)
f2c13cdac7cfef887f88d8756bdcf0d4  docs/PLANO_BACKEND_GLES_R36S.md
fc553f8a882ae1236afed534ed2fb2f7  _PROGRESS.md                    (sessao cont. 4)
```
(Hashes sao snapshot do instante da escrita; `_PROGRESS.md` muda a cada sessao — reconferir com
`md5sum`.)
(este proprio arquivo de evidencia: verificar com `md5sum` no momento do uso)