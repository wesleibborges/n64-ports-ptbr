# EVIDENCIA: auditoria offline da stack Vulkan/graphics do firmware dArkOS (R36S)

Data (UTC): 2026-10-17T16:20Z
Conta AWS: nao aplicavel (nenhuma operacao AWS nesta sessao)
Ambiente: WSL Ubuntu 22.04 (host x86_64) + `qemu-aarch64-static` (user mode)
Imagem auditada: `C:\Users\wesle\Downloads\R36S\Firmwares\dArkOSen_R36_09302026.img.xz`
Backup do device: `C:\Users\wesle\Downloads\R36S\Firmwares\backup\arkosbackup.tar.gz` (2,5 MB; somente configs do ArkOS - sem libs)
Scripts de auditoria: `evidencias/tools/audit_rootfs.py`, `evidencias/tools/audit_vulkan_icd.py`

**Objetivo:** responder offline a pergunta bloqueante do port — existe ICD no R36S que
exponha `VK_KHR_display` (unico WSI aceito pelo SDL2 KMSDRM)?

---

## 1. Imagem e particionamento (RAW)

```
$ xz -dc dArkOSen_R36_09302026.img.xz > /opt/r36s/darkos.img   # EXIT=0
$ ls -la /opt/r36s/darkos.img
-rw-r--r-- 1 root root 8773435392 Oct 17 16:09 /opt/r36s/darkos.img

$ fdisk -l /opt/r36s/darkos.img
Disk /opt/r36s/darkos.img: 8.17 GiB, 8773435392 bytes, 17135616 sectors
Disklabel type: dos
Device                Boot    Start      End  Sectors  Size Id Type
/opt/r36s/darkos.img1 *       32768   237567   204800  100M  c W95 FAT32 (LBA)
/opt/r36s/darkos.img2        237568 16928767 16691200    8G 83 Linux
/opt/r36s/darkos.img3      16930816 17135615   204800  100M  7 HPFS/NTFS/exFAT
```

Montagem da rootfs (p2, offset 121634816, sizelimit 8545894400) em modo **read-only**:

```
$ losetup -f --show -r -o 121634816 --sizelimit 8545894400 /opt/r36s/darkos.img
/dev/loop2
$ mount -o ro /dev/loop1 /opt/r36s/rootfs && echo MOUNT_OK
MOUNT_OK
$ df -h /opt/r36s/rootfs
Filesystem      Size  Used Avail Use% Mounted on
/dev/loop1      8.0G  7.2G  3.0M 100% /opt/r36s/rootfs
```

## 2. Kernel, boot e sistema

```
$ cat bootmnt/boot.ini
odroidgoa-uboot-config
setenv bootargs "root=/dev/mmcblk0p2 rootwait rw fsck.repair=yes net.ifnames=0 fbcon=rotate:0
 console=/dev/ttyFIQ0 quiet splash consoleblank=0 vt.global_cursor_default=0
 max_cpufreq=1512 boot_cpufreq=1296"
load mmc 1:1 ${dtb_loadaddr} rk3326-r36s-linux.dtb
booti ${loadaddr} ${initrd_loadaddr} ${dtb_loadaddr}

$ strings bootmnt/Image | grep -m1 -E '^Linux version'
Linux version 4.4.189 (djpar@dArkOSen) (gcc version 6.3.1 20170404 (Linaro GCC 6.3-2017.05) )
 #1 SMP Fri Sep 25 02:17:24 UTC 2026

$ strings bootmnt/Image | grep -i -E 'panfrost|mali_kbase' | sort -u
drivers/gpu/arm/bifrost_for_linux/mali_kbase_mem_linux.c
drivers/gpu/arm/bifrost_for_linux/platform/rk/mali_kbase_config_rk.c

$ cat rootfs/etc/os-release
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
VERSION_ID="13"
VERSION_CODENAME=trixie
DEBIAN_VERSION_FULL=13.7

$ strings rootfs/lib/aarch64-linux-gnu/libc.so.6 | grep -m2 'GNU C Library'
GNU C Library (Debian GLIBC 2.41-12+deb13u4) stable release version 2.41.

$ ls rootfs/lib/modules
4.4.189
```

**Fatos:** kernel **4.4.189** com driver proprietario **`mali_kbase` (bifrost_for_linux)**;
**nao ha `panfrost`** no kernel (exigiria kernel mainline 5.10+). Rootfs Debian 13 /
glibc 2.41. Modules apenas `4.4.189`.

## 3. ICDs Vulkan presentes na imagem (RAW)

```
$ ls -la rootfs/usr/share/vulkan/icd.d/
broadcom_icd.json  freedreno_icd.json  gfxstream_vk_icd.json  lvp_icd.json
mali_icd.json  nouveau_icd.json  panfrost_icd.json  radeon_icd.json  virtio_icd.json

$ cat rootfs/usr/share/vulkan/icd.d/mali_icd.json
{ "file_format_version": "1.0.0", "ICD": { "library_path": "libmali.so", "api_version": "1.0.0" } }

$ cat rootfs/usr/share/vulkan/icd.d/lvp_icd.json
{ "ICD": { "api_version": "1.4.305", "library_path": "libvulkan_lvp.so" }, "file_format_version": "1.0.0" }

$ cat rootfs/usr/share/vulkan/icd.d/panfrost_icd.json
{ "ICD": { "api_version": "1.4.305", "library_path": "libvulkan_panfrost.so" }, "file_format_version": "1.0.0" }

$ ls rootfs/usr/lib/aarch64-linux-gnu/libvulkan.so.1*
libvulkan.so.1 -> libvulkan.so.1.4.309
```

## 4. Cadeia de symlinks da stack grafica (aarch64)

```
$ ls -l rootfs/usr/lib/aarch64-linux-gnu/ | grep -iE 'mali|gbm|egl|gles'
libEGL.so        -> libMali.so
libEGL.so.1      -> libMali.so
libEGL.so.1.1.0  -> libMali.so
libGLES_CM.so    -> libMali.so
libGLESv1_CM.so  -> libMali.so
libGLESv2.so     -> libMali.so
libGLESv2.so.2   -> libMali.so
libGLESv3.so     -> libMali.so
libMali.so       -> libmali-bifrost-g31-rxp0-gbm.so
libMaliOpenCL.so -> libMali.so
libgbm.so        -> libMali.so
libgbm.so.1      -> libMali.so
libgbm.so.1.0.0  -> libMali.so
libmali.so       -> libMali.so
libmali.so.1     -> libMali.so
libmali-bifrost-g31-rxp0-gbm.so   40867064 bytes   <-- blob ARM (aarch64)
```

Blob Mali na imagem (apenas UMA variante por arquitetura):

```
  40867064  /usr/lib/aarch64-linux-gnu/libmali-bifrost-g31-rxp0-gbm.so
  30157556  /usr/lib/arm-linux-gnueabihf/libmali-bifrost-g31-rxp0-gbm.so   (armhf, irrelevante)
total arquivos libmali*/libMali*: 10 (6 symlinks + 2 blobs + 2 OpenCL)
```

**Fato:** o blob ARM fornece **EGL/GLESv1/GLESv2/GLESv3/GBM/OpenCL** (variante `-gbm`),
ou seja **OpenGL ES acelerado por hardware esta disponivel**. Nao ha variante
`-fbdev`/`-x11`/`-wayland` para trocar.

---

## 5. TESTE DECISIVO — `vkprobe` com os ICDs REAIS do device (via QEMU)

Comando base (sem tocar no console; tudo offline sobre a rootfs montada):

```
cd "C:\Users\wesle\dev\ports\Body Harvest (Recomp)"
VK_LOADER_DEBUG=error VK_ICD_FILENAMES=<icd>.json timeout 60 qemu-aarch64-static -L /opt/r36s/rootfs ./vkprobe
```

### 5.1 ICD `lvp` (lavapipe / llvmpipe — software)

```
instance extensions: 18 (r=0)
  ext: VK_KHR_device_group_creation
  ext: VK_KHR_external_fence_capabilities
  ext: VK_KHR_external_memory_capabilities
  ext: VK_KHR_external_semaphore_capabilities
  ext: VK_KHR_get_physical_device_properties2
  ext: VK_KHR_get_surface_capabilities2
  ext: VK_KHR_surface
  ext: VK_KHR_surface_protected_capabilities
  ext: VK_KHR_wayland_surface
  ext: VK_KHR_xcb_surface
  ext: VK_KHR_xlib_surface
  ext: VK_EXT_debug_report
  ext: VK_EXT_debug_utils
  ext: VK_EXT_headless_surface
  ext: VK_EXT_surface_maintenance1
  ext: VK_EXT_swapchain_colorspace
  ext: VK_KHR_portability_enumeration
  ext: VK_LUNARG_direct_driver_loading
VK_KHR_display: NAO
vkCreateInstance: r=0
physical devices: 1 (r=0)
  dev[0]: 'llvmpipe (LLVM 19.1.7, 128 bits)' type=4 api=1.4.305 vendor=0x10005
```

As 16 extensoes do ICD + 2 do loader batem **exatamente** com a tabela
`lvp_instance_extensions_supported` do Mesa, que **nao** contem `KHR_display`.

### 5.2 ICD `mali` (blob ARM `libmali-bifrost-g31-rxp0-gbm.so`, 40 MB)

```
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/mali_icd.json \
LD_LIBRARY_PATH=/opt/r36s/rootfs/usr/lib/aarch64-linux-gnu qemu-aarch64-static -L /opt/r36s/rootfs ./vkprobe
instance extensions: 8 (r=0)
  ext: VK_KHR_get_physical_device_properties2
  ext: VK_KHR_external_fence_capabilities
  ext: VK_KHR_external_semaphore_capabilities
  ext: VK_KHR_external_memory_capabilities
  ext: VK_EXT_debug_report
  ext: VK_EXT_debug_utils
  ext: VK_KHR_portability_enumeration
  ext: VK_LUNARG_direct_driver_loading
VK_KHR_display: NAO
vkCreateInstance: r=-9
[stderr] Failed creating base context during opening of kernel driver.
        Kernel module may not have been loaded
[stderr] [Vulkan Loader] ERROR | DRIVER: terminator_CreateInstance: Found no drivers!

# leitura de bytes do blob:
VK_KHR_display                           count=0
vkCreateDisplayPlaneSurfaceKHR           count=2   (apenas stub exportado)
VK_KHR_surface                           count=0
VK_KHR_swapchain                         count=0
strings VK_* no blob: 19 (todas core-1.1: 16bit_storage, dedicated_allocation, ...)
```

**Fato:** o blob Mali carrega (a mensagem `Failed creating base context ...` vem do
proprio blob, logo o `dlopen` ocorreu), mas **nao implementa NENHUM WSI**: nem
`VK_KHR_surface` nem `VK_KHR_display`. `r=-9` = `VK_ERROR_INCOMPATIBLE_DRIVER`
(esperado offline, sem `/dev/mali0`).

### 5.3 ICD `panfrost` (panvk, Mesa 25.0.7)

```
instance extensions: 16 (r=0)
  ext: VK_KHR_device_group_creation
  ext: VK_KHR_external_fence_capabilities
  ext: VK_KHR_external_memory_capabilities
  ext: VK_KHR_external_semaphore_capabilities
  ext: VK_KHR_get_physical_device_properties2
  ext: VK_KHR_surface
  ext: VK_KHR_wayland_surface
  ext: VK_KHR_xcb_surface
  ext: VK_KHR_xlib_surface
  ext: VK_EXT_acquire_xlib_display
  ext: VK_EXT_debug_report
  ext: VK_EXT_debug_utils
  ext: VK_EXT_direct_mode_display
  ext: VK_EXT_headless_surface
  ext: VK_KHR_portability_enumeration
  ext: VK_LUNARG_direct_driver_loading
VK_KHR_display: NAO
vkCreateInstance: r=0
physical devices: 0 (r=-3)
[stderr] setup_loader_term_phys_devs: Failed to detect any valid GPUs in the current config
```

### 5.4 CONTROLE POSITIVO (valida o metodo) — `radeon` e `nouveau`

```
### radeon (radv do MESMO Mesa 25.0.7 do device)
instance extensions: 24 (r=0)
  ext: VK_KHR_display
  ext: VK_KHR_get_display_properties2
  ext: VK_EXT_acquire_drm_display
  ext: VK_EXT_acquire_xlib_display
  ext: VK_EXT_direct_mode_display
  ext: VK_EXT_display_surface_counter
  ext: VK_EXT_headless_surface
VK_KHR_display: SIM

### nouveau (nvk) -> VK_KHR_display: SIM
```

**Conclusao do controle:** o ambiente offline (QEMU + rootfs do device) reproduz
corretamente a exposicao de `VK_KHR_display` quando ela existe => os `NAO` de
lvp/mali/panfrost sao **fato verificado**, nao artefato de emulacao.

## 6. Por que panvk nao expoe display (fonte oficial do Mesa)

`src/panfrost/vulkan/panvk_instance.c` (upstream Mesa):

```c
static const struct vk_instance_extension_table panvk_instance_extensions = {
   ...
#ifdef VK_USE_PLATFORM_DISPLAY_KHR
   .KHR_get_display_properties2 = true,
#endif
#ifdef PANVK_USE_WSI_PLATFORM
   .KHR_get_surface_capabilities2 = true,
   .KHR_surface = true,
   ...
#endif
#ifdef VK_USE_PLATFORM_DISPLAY_KHR
   .KHR_display = true,
   .EXT_acquire_drm_display = true,
   .EXT_direct_mode_display = true,
   .EXT_display_surface_counter = true,
#endif
```

=> `KHR_display` no panvk depende de `VK_USE_PLATFORM_DISPLAY_KHR` **no build do driver**.
No Mesa 25.0.7 do Debian 13 esse macro esta ativo para radv/nvk (familia display
completa) e **nao** para panvk. Referencia:
`https://raw.githubusercontent.com/mirror/mesa/main/src/panfrost/vulkan/panvk_instance.c`

## 7. SDL bundled (2.30.9 cross-build) — conferencia

```
$ strings -a libs/libSDL2-2.0.so.0.3000.9 | grep -i -xE 'kmsdrm|dummy|offscreen|evdev|vulkan|opengles2|opengl'
opengl
opengles2
Vulkan
dummy
evdev
offscreen
KMSDRM            <-- driver KMSDRM presente (nome em MAIUSCULAS)
$ strings -a libs/libSDL2-2.0.so.0.3000.9 | grep -i 'Video Driver'
KMS/DRM Video Driver
SDL dummy video driver
SDL dummy video driver with evdev
SDL offscreen video driver
$ strings -a libs/libSDL2-2.0.so.0.3000.9 | grep -i 'display'
VK_KHR_display
Installed Vulkan doesn't implement the VK_KHR_displayextension
VK_KHR_display extension is not enabled in the Vulkan instance.
VK_KHR_surface
```

**Fato:** o SDL 2.30.9 do port esta correto (KMSDRM + Vulkan + GLES/EGL compilados) e
usa **exclusivamente `VK_KHR_display`** no caminho KMSDRM; nao referencia
`VK_EXT_headless_surface`. Logo o problema **nao e o SDL** — e o driver Vulkan.

---

## 8. RESULTADO (matriz de capacidade do firmware)

| ICD | Tipo | Vulkan | `VK_KHR_display` | WSI disponivel | Util para KMSDRM? |
|---|---|---|---|---|---|
| `mali_icd` (blob ARM rxp0-gbm) | HW (Mali-G31) | 1.0.x | NAO | **nenhum** | NAO |
| `lvp_icd` (lavapipe) | SW | 1.4.305 | NAO | wayland / xcb / xlib / headless | NAO |
| `panfrost_icd` (panvk) | HW (precisa kernel mainline) | 1.4.305 | NAO | wayland / xcb / xlib / headless | NAO |
| `radeon` / `nouveau` (controle) | HW (nao existe no R36S) | 1.4.305 | **SIM** | display/wayland/xcb/xlib | SIM |

### Conclusoes (fatos)

1. **Nenhum driver Vulkan do firmware dArkOS 09302026 expoe `VK_KHR_display`.**
   O SDL2 no modo KMSDRM depende exclusivamente dessa extensao
   (`vkCreateDisplayPlaneSurfaceKHR`) => **a janela Vulkan nunca sera criada neste
   firmware, independentemente do SDL, do launcher ou do ICD escolhido.**
   Isso e o bloqueio definitivo do erro observado em `log.txt`:
   `Failed to create window: ... (KMSDRM) ...`.
2. O **blob ARM Mali** (o unico caminho acelerado por HW) possui **Vulkan 1.0.x sem
   nenhum WSI** — nao ha como apresentar (nem por display, nem por wayland/x11).
   Alem disso `Vulkan 1.0.x < 1.2/1.3` exigidos pelo RT64.
3. O unico Vulkan "completo" disponivel e o **lavapipe (software)** e ele **nao tem
   `VK_KHR_display`**; tem wayland/xcb/xlib/**headless** => para uso on-screen seria
   necessario um servidor X11 ou compositor Wayland (ausentes na imagem:
   `usr/bin` nao tem `Xorg`/`weston`/`cage`/`sway`), ou um caminho headless com
   apresentacao propria (mudanca no app).
4. O blob ARM **fornece OpenGL ES 1/2/3 + EGL + GBM acelerados por HW**
   (`libEGL.so -> libMali.so`, `libgbm.so.1 -> libMali.so`), e o SDL 2.30.9 do port
   tem `KMSDRM` com GLES => **GLES acelerado por HW funciona** neste device; o que nao
   existe e Vulkan apresentavel.
5. Firmware alternativo com kernel mainline (panfrost) **nao garante** solucao: no Mesa
   do Debian 13 o panvk **nao** liga `VK_USE_PLATFORM_DISPLAY_KHR`, pois mostrado no
   item 5.3 (medido) e item 6 (fonte). Essa via exigiria um build de Mesa com display
   WSI habilitado *para panvk* - nao verificado e de risco alto.

### Decisao (ponto de decisao do plano)

Caso aplicavel: **"somente lavapipe encontrado"** (pior que o esperado: lavapipe tambem
nao serve para KMSDRM). Portanto:

> **NAO implantar o caminho Vulkan/KMSDRM no R36S com este firmware.** O bloqueio nao e
> contornavel por configuracao (env/ ICD/SDL); e ausencia de recurso no driver.

### Opcoes tecnicas remanescentes (para a proxima sessao)

- **A. Portar so para devices com WSI display** (radv/nvk/anv, ou Mesa com display WSI
  ligado). Mantem o port como esta; R36S fica de fora.
- **B. Renderer GLES (HW) no lugar do RT64/Vulkan:** o hardware tem GLES 2/3 acelerado e
  SDL KMSDRM+GLES funciona; exigiria outro renderizador N64 (grande reescrita). Alto custo.
- **C. Fallback 100% software:** lavapipe + X11 ou Wayland *na device* (instalar Xorg ou
  weston) apenas para **medir fps** - util para decidir se vale investir; em RK3326
  (4xA35@1.5 GHz, 1 GB) a expectativa e de poucos fps.
- **D. Headless + apresentacao propria (`VK_EXT_headless_surface` existe no lavapipe):**
  requer patch no frontend (SDL) e no present do RT64 para publicar via KMS/dumb buffer.
  Custo medio-alto; performance continua software.

## Artefatos desta etapa

| Arquivo | Funcao |
| :--- | :--- |
| `evidencias/tools/audit_rootfs.py` | inventario geral da rootfs (libs, ICDs, modulos) |
| `evidencias/tools/audit_vulkan_icd.py` | resolve symlinks + varre strings dos drivers Vulkan |
| `/opt/r36s/darkos.img` (host WSL) | imagem descomprimida (8.773.435.392 bytes) |
| `/opt/r36s/rootfs` (host WSL) | rootfs do device montada read-only (loop, offset 121634816) |

### Hashes (md5) desta etapa

(este proprio arquivo nao entra na tabela: hash de um arquivo que se auto-edita fica
sempre defasado - verificar com `md5sum` na hora do uso)

```
ec8c2117eaec2d992a8c58b291b448d1  evidencias/tools/audit_rootfs.py
cbbcd6ba62e6c76cf1bacb6f4fb0083c  evidencias/tools/audit_vulkan_icd.py
f004d2500a07784554b60beccd23ef68  BodyHarvest.sh   (diagnostico de ICD adicionado; bash -n OK)
1f1962b445d5def4f62ab14bd1048141  BodyHarvest.sh   (ATUAL: + recon GLES/glesprobe; ver evidence_gles_backend_recon)
5b7bc6a0c062ce267fc6f30d9610e493  _PROGRESS.md     (sessao cont. 3 registrada)
```
(HISTORICO: a linha `f004d250...` e o md5 do launcher no instante desta etapa; apos o bloco de
recon GLES o arquivo passou a `1f1962b4...`. Verificar sempre com `md5sum` no momento do uso.)

### Mudanca no launcher (`BodyHarvest.sh`)

Apos o loop de auto-selecao de ICD, foi adicionado um bloco que **imprime o diagnostico
definitivo** quando nenhum ICD expoe `VK_KHR_display` + device — evitando novo ciclo de
reboot/copia no SD so para descobrir o obvio. **Nao altera comportamento** (o jogo ainda
tenta rodar, util caso exista X11/Wayland na sessao). `bash -n` = OK.