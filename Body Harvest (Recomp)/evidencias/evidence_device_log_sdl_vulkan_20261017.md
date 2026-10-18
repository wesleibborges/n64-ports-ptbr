# Evidência — log do device + SDL2 2.30.9 cross-build (KMSDRM+Vulkan)

Data: 2026-10-17 17:5x UTC / 14:5x -03
Alvo: R36S / dArkOSen `4.4.189 #62 aarch64`, CFW_GLIBC=241, DEVICE_CPU=RK3326

## 1. Log do device (primeira execução pós-patch v2)

Arquivo: `C:\Users\wesle\dev\ports\Body Harvest (Recomp)\log.txt`

```
Linux dArkOSen-r36 4.4.189 #62 SMP Sat Dec 13 08:49:45 CST 2025 aarch64 GNU/Linux
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
--- ldd do binario ---
	libSDL2-2.0.so.0 => /lib/aarch64-linux-gnu/libSDL2-2.0.so.0 (0x0000007fa61e0000)
	libfreetype.so.6 => /lib/aarch64-linux-gnu/libfreetype.so.6 (0x0000007fa6100000)
	libgtkshim.so => /roms2/ports/Body Harvest (Recomp)/libs/libgtkshim.so (0x0000007fa60e0000)
	libm.so.6 => /lib/aarch64-linux-gnu/libm.so.6
	libgcc_s.so.1 => /lib/aarch64-linux-gnu/libgcc_s.so.1
	libc.so.6 => /lib/aarch64-linux-gnu/libc.so.6
	libsamplerate.so.0 => /lib/aarch64-linux-gnu/libsamplerate.so.0
	librga.so.2 => /lib/aarch64-linux-gnu/librga.so.2
	libz.so.1 / libbz2.so.1.0 / libpng16.so.16 / libbrotlidec.so.1
	libdrm.so.2 => /lib/aarch64-linux-gnu/libdrm.so.2
	libstdc++.so.6 / libbrotlicommon.so.1
--- fim ldd ---
=== executando ===
librga:RGA_GET_VERSION:4.00,4.000000
ctx=0x55855b52b0,ctx->rgaFd=4
Failed to create secure directory (/run/user/1000//pulse): No such file or directory
Failed to create window: Vulkan support is either not configured in SDL or not available in current SDL video driver (KMSDRM) or platform
Exiting with exit status '1'. Function exit_error, at file /root/bhrecomp/src/main/main.cpp:61
=== EXIT=1 ===
```

**Conclusões (fatos):**
1. Patch v2 OK: `libgtkshim.so` carregado de `libs/`, sem SIGSEGV, processo chega ao `main()`.
2. `libSDL2-2.0.so.0` veio do **sistema** (`/lib/aarch64-linux-gnu`), não de `libs/`.
3. O SDL do sistema inicializa em **KMSDRM** mas aborta em `SDL_Vulkan_CreateSurface` com a
   mensagem do ramo `!_this->Vulkan_LoadLibrary` do `SDL_video.c`
   (`Vulkan support is either not configured in SDL ...`) ⇒ **SDL do sistema compilado sem Vulkan**.

## 2. Inventário do SDL bundled antigo (`libs/libSDL2-2.0.so.0.3000.3`)

```
$ strings -a libs/libSDL2-2.0.so.0.3000.3 | grep -xE 'x11|wayland|kmsdrm|dummy|offscreen|vivante|opengl|opengles2|vulkan'
dummy
evdev
offscreen
opengl
opengles2
```
⇒ SDL 2.30.3 **sem `kmsdrm`** e **sem `vulkan`** (drivers de vídeo: só dummy/offscreen).
Inutilizável no device. Além disso, `libs/` continha **apenas** `libSDL2-2.0.so.0.3000.3` —
o symlink `libSDL2-2.0.so.0` não sobreviveu à cópia para FAT/exFAT, por isso o loader
resolveu a lib do sistema.

## 3. Fix do nome (loader)

```
$ cp libs/libSDL2-2.0.so.0.3000.3 libs/libSDL2-2.0.so.0   # arquivo físico (FAT nao tem symlink)
```
E no `BodyHarvest.sh` foi adicionado bloco defensivo que recria `libSDL2-2.0.so.0`
via `ln -s` (se o FS suportar) ou `cp -f` (fallback).

## 4. Cross-build SDL2 2.30.9 (aarch64) com KMSDRM + Vulkan

Dependências arm64 instaladas (multiarch em WSL/Ubuntu 22.04):
`libdrm-dev:arm64`, `libgbm-dev:arm64`, `libasound2-dev:arm64` +
`libudev-dev:arm64`/`libudev1:arm64` **extraídos manualmente** em `/opt/arm64-stage`
(bloqueio de Multi-Arch: amd64 em 249.11-0ubuntu3.23 vs arm64 em 249.11-0ubuntu3.22).

Script: `C:\e-core\_build_sdl2_aarch64.sh` → `/opt/SDL2-2.30.9`, prefix `/opt/sdl2-aarch64`.

Configure summary (RAW):
```
Audio drivers   : disk dummy oss alsa(dynamic)
Video drivers   : dummy offscreen kmsdrm(dynamic) opengl opengl_es1 opengl_es2 vulkan
Input drivers   : linuxev linuxkd
Using libudev       : YES
Using dbus          : NO
Using ime           : NO
```
Artefato: `libSDL2-2.0.so.0.3000.9` (SONAME `libSDL2-2.0.so.0`, NEEDED apenas
`libm/libc/ld-linux`; dlopen em runtime de `libdrm.so.2`, `libgbm.so.1`,
`libvulkan.so.1`, `libasound.so.2`, `libudev.so.1`). Strip: 6.4 MB → 1.6 MB.

Símbolos Vulkan do KMSDRM presentes (lib não-stripada):
```
t KMSDRM_Vulkan_LoadLibrary
t KMSDRM_Vulkan_CreateSurface
t KMSDRM_Vulkan_GetInstanceExtensions
```

## 5. Probe aarch64 sob QEMU (`_sdl_probe.c`)

```
SDL revision : SDL-2.30.9
video drivers (4): KMSDRM offscreen dummy evdev
driver ativo  : dummy
Vulkan_LoadLibrary(FALHA): No dynamic Vulkan support in current SDL video driver (dummy)
```
⇒ mensagem mudou: agora é o ramo **"driver atual não suporta Vulkan"** (esperado no dummy),
não mais o ramo **"SDL não tem Vulkan"**. SDL novo está com Vulkan habilitado.

Jogo sob QEMU com o SDL novo:
```
Failed to create window: Vulkan support is either not configured in SDL or not available in current SDL video driver (dummy) or platform
```
(antes o launcher carregava o SDL do sistema).

## 6. Risco aberto: lavapipe (llvmpipe) NÃO expõe `VK_KHR_display`

`vulkaninfo` local (Mesa 23.2.1, `lvp_icd.x86_64.json`, llvmpipe LLVM 15.0.7, Vulkan 1.3.255):
```
VK_KHR_surface, VK_KHR_wayland_surface, VK_KHR_xcb_surface, VK_KHR_xlib_surface
Presentable Surfaces: xcb, xlib, wayland
```
Sem `VK_KHR_display`. O SDL KMSDRM usa **exclusivamente** `VK_KHR_display`
(`vkCreateDisplayPlaneSurfaceKHR`); a própria lib contém a string
`Installed Vulkan doesn't implement the VK_KHR_display extension`.

⇒ Se o único ICD do R36S for `lvp_icd.json`, o jogo falhará em
`SDL_Vulkan_CreateSurface` com essa mensagem, **independente** do SDL.
Necessário recon no device: `ls /usr/share/vulkan/icd.d/`, `/dev/dri`, `ldconfig -p`
(libmali/libvulkan/libgbm) — já instrumentado no `BodyHarvest.sh`.

## 7. `vkprobe` (recon Vulkan autocontido)

Fonte `C:\e-core\_vulkan_probe.c`, binário `vkprobe` (aarch64, 13 KB, NEEDED só `libc`):
dlopen em `libvulkan.so.1`, lista extensões de instância, indica `VK_KHR_display: SIM/NAO`,
cria instância e imprime os devices físicos.

Validação no host (build x86 do mesmo fonte):
```
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json
instance extensions: 13 (r=0)
VK_KHR_display: NAO
vkCreateInstance: r=0
physical devices: 1 (r=0)
  dev[0]: 'llvmpipe (LLVM 15.0.7, 256 bits)' type=4 api=1.3.255 vendor=0x10005
```
Teste da lógica de seleção (`C:\e-core\_test_icd_select.sh`, ICDs do host):
```
ICD intel_hasvk: VK_KHR_display: SIM
ICD intel:       VK_KHR_display: SIM
ICD lvp:         VK_KHR_display: NAO  dev[0]: llvmpipe
ICD radeon:      VK_KHR_display: SIM
ICD virtio:      VK_KHR_display: NAO
SELECIONADO: /usr/share/vulkan/icd.d/intel_hasvk_icd.x86_64.json
```
O launcher agora, antes do jogo: (a) dump de `/dev/dri`, ICDs e `ldconfig`;
(b) roda `vkprobe` por ICD; (c) **auto-seleciona** o primeiro ICD com
`VK_KHR_display: SIM` **e** device presente, exportando `VK_ICD_FILENAMES`;
(d) imprime o SDL/gtkshim efetivamente resolvido pelo `ldd`.
Todos os `vkprobe` são limitados por `timeout 5`.

## Artefatos desta etapa
| Arquivo | md5 |
| :--- | :--- |
| `libs/libSDL2-2.0.so.0.3000.9` (SDL 2.30.9 cross) | `c44285c7d1c92b5934898229e7144c1f` |
| `libs/libgtkshim.so` | `9f22de1ea44a68f46bde075aab232616` |
| `BodyHarvestRecompiled` (patch v2) | `dbc386ba918d898a01038d7ff943768a` |
| `vkprobe` (recon Vulkan) | `9ebe16084039d65066d5f30157b41015` |
| `BodyHarvest.sh` (launcher c/ SDL fix + recon) | `c9cc0ed14985cc4b91b12f63a45d71fb` |
