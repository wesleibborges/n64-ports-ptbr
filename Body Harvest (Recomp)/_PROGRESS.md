# Body Harvest (Recomp) — Progresso do Port para R36S

## Artefatos principais
| Item | Local |
|---|---|
| Binário BodyHarvestRecompiled (x86_64, testado) | pasta do port + /mnt/c/e-core/ |
| bh_aspMain.toml (corrigido, 8 endereços IMEM absolutos) | /root/bhrecomp/ |
| aspMain.cpp gerado (labels L_1118, L_1470, ...) | /root/bhrecomp/rsp/ |
| bh_main.cpp (640x480) | /root/bhrecomp/src/main/ |
| Checkpoints Docker | bh-checkpoint-01, bh-checkpoint-02-buildok (1.41GB, x86_64) |
| Fontes | /root/bh + /root/bhrecomp (WSL) |

## Sessão original — Build funcional (WSL)
- Build x86_64 completo: ninja BodyHarvestRecompiled — 21.5 MB, binário funcional
- Teste no WSL com llvmpipe (Vulkan 1.3.255 por software): OK, janela abriu
- Resolução fixada em 640x480 em main.cpp
- aspMain corrigido: extra_indirect_branch_targets com endereços IMEM absolutos
  (0x1118 0x1470 0x11DC 0x1B38 0x1214 0x187C 0x1254 0x12D0)
  - dispatch do audio ucode: lh v0, 0x10(); jr v0 — jump table em DMEM 0x0010
  - tabela de handlers em ucode_data (ROM 0x3FC60, 0x800 bytes), ref. D_8003F060_3FC60
- PortMaster estruturado na pasta do projeto com BodyHarvest.sh + assets

## Sessão 2026-10-16 — Diagnóstico de renderização (R36S)
- diag1/diag2 no R36S (clone dArkOS): kernel 4.4.189 com blob ARM mali_kbase,
  /dev/mali0. Mesa com libvulkan_panfrost.so + lavapipe presentes, mas panvk
  exige driver kernel panfrost (mainline) -> Vulkan HW inviável neste kernel.
- Decisão: testar outro sistema com kernel 5.x e rodar diag3.

## Sessão 2026-10-16 (cont.) — Diagnóstico do novo sistema (diag3)
- vulkaninfo mostra 2 GPUs:
  - Mali-G31 (blob libmali.so, Vulkan 1.0.108) — INSUFICIENTE p/ RT64 (exige 1.3)
  - llvmpipe (Mesa 25.0.7, Vulkan 1.4.305) — funcional por software
- Kernel continua 4.4.189 (sem /dev/panfrost) -> panvk continua inviável
- Caminho viável: RT64 sobre llvmpipe (mesma rota validada no WSL)

## Sessão 2026-10-16 (cont.) — Rebuild aarch64: bloqueado por infra

Tentativas de rebuild aarch64:
1. apt no WSL: gcc-aarch64-linux-gnu — TIMEOUT em todos os métodos
2. Docker QEMU arm64: exec format error — binfmt sem qemu-aarch64 registrado
3. Docker buildx: apenas linux/amd64(+v2/v3) — sem emulação arm64

Entregas:
- /root/bhrecomp/BUILD_AARCH64.md — guia completo de cross-compile
- /root/bhrecomp/Toolchain-aarch64.cmake — toolchain file pronto

Status do projeto:
- Fontes: /root/bh + /root/bhrecomp (WSL) — intactos
- Binário atual: x86_64 (funcional em llvmpipe, testado)
- bh_aspMain.toml: CORRIGIDO (8 endereços IMEM absolutos)
- Build aarch64: BLOQUEADO (aguardando ambiente com apt estável ou qemu binfmt)

Retomada: seguir BUILD_AARCH64.md no primeiro ambiente com apt funcional.

## Sessão 2026-10-17 (cont.) — SIGSEGV aarch64: causa raiz + GTK removido (patch v2)

**Sintoma:** binário aarch64 (19,7 MB PIE) morria com SIGSEGV imediato (antes de
qualquer código do jogo), mesmo sem GTK.

**Causa raiz (evidência RAW):**
- `gdb-multiarch` + gdbstub qemu: `_start` → `_dl_runtime_resolve` em
  `ld-linux-aarch64.so.1` → SIGSEGV. Crash na resolução **lazy** de
  `__libc_start_main`.
- `readelf -l`: `GNU_RELRO 0x101ad70 (+0x1b290)` cobre `.data.rel.ro` **e** `.got`
  (`.got=0x1033ac8`, `DT_PLTGOT=0x1033ac8`) — layout típico de link `-z now`.
- Patch v1 zerou `DT_FLAGS`/`DT_FLAGS_1` (BIND_NOW) ⇒ glibc fez binding lazy, mas o
  GOT já estava selado read-only pelo RELRO ⇒ store no GOT ⇒ `SEGV_ACCERR`.
- Agravante: `patchelf --add-needed` reescreveu o `.dynamic` e **derrubou**
  `DT_VERSYM`, `DT_VERNEED`, `DT_VERNEEDNUM`, `DT_RELACOUNT`, `DT_FLAGS` e
  `FLAGS_1` (entrada NULL final com valor `0x8`).

**Correção — `_patch_elf_v2.py` (100% in-place, sem patchelf):**
1. `DT_NEEDED "libgtk-3.so.0"` → `"libgtkshim.so"` (13 chars + NUL: mesma largura)
2. `DT_NEEDED` gdk/gobject/glib → tag `0x6FFFFF00` (desconhecida, ignorada)
3. `DT_VERSYM`/`VERNEED`/`VERNEEDNUM` → tag `0x6FFFFF01` (sem version check)
4. `DT_FLAGS=0x8` (BIND_NOW) e `FLAGS_1=NOW|PIE` **preservados** ⇒ binding eager
   preenche o GOT antes do mprotect do RELRO

**Shim:** `libs/libgtkshim.so` (aarch64, SONAME `libgtkshim.so`), 39 stubs:
31 `gtk_`/`gdk_` + 8 glib (`g_free`→`free`, `g_slist_*`, `g_signal_*`,
`g_type_check_instance_*`). `gtk_init_check()` → FALSE ⇒ launcher usa a UI interna
sem file dialog GTK.

**Validação:**
- Asserts do patcher: NEEDED limpa, sem versionamento, BIND_NOW presente, nº de
  entradas `.dynamic` e tamanho do arquivo inalterados.
- qemu-aarch64-static (SDL dummy): boot OK até `main()`; para em
  `Failed to create window: Vulkan ... dummy` (esperado, sem Vulkan no dummy).
- Cobertura: 39/39 símbolos `gtk_/gdk_/g_` UND resolvidos (`comm -23` vazio).
- Evidência: `evidencias/evidence_gtk_patch_v2_20261017_162606.md`;
  logs `_ldbind.log`, `_ldlibs.log`, `_qtrace.log`, `_run_v2.log`.

**Pendente:** copiar `BodyHarvestRecompiled` + `libs/libgtkshim.so` para o R36S,
rodar `BodyHarvest.sh` e coletar `log.txt` (esperado RT64/llvmpipe 3–8 fps).

---

## Sessão 2026-10-17 (cont. 2) — 1ª execução no R36S: shim OK, SDL/Vulkan quebrado

**Log do device** (`log.txt`, dArkOSen 4.4.189 aarch64, RK3326, glibc 2.41):
```
libgtkshim.so => /roms2/ports/Body Harvest (Recomp)/libs/libgtkshim.so   <-- shim OK
libSDL2-2.0.so.0 => /lib/aarch64-linux-gnu/libSDL2-2.0.so.0              <-- SDL do SISTEMA
Failed to create window: Vulkan support is either not configured in SDL or not available
  in current SDL video driver (KMSDRM) or platform
```
⇒ Patch v2 validado no hardware (sem SIGSEGV, chega ao `main()`). Dois problemas novos:

1. **SDL bundled não foi carregado**: `libs/` só tinha `libSDL2-2.0.so.0.3000.3`, sem o nome
   `libSDL2-2.0.so.0` — symlink não sobrevive em FAT/exFAT. Corrigido com arquivo físico +
   bloco defensivo (`ln -s` → `cp -f`) no `BodyHarvest.sh`.
2. **Nenhum SDL do device tem Vulkan**: o bundled antigo (2.30.3) só tinha vídeo
   `dummy/offscreen` (**sem kmsdrm, sem vulkan**); o do sistema tem `kmsdrm` mas foi
   compilado sem `--enable-video-vulkan` (mensagem exata do ramo `!_this->Vulkan_LoadLibrary`).

**Correção — SDL2 2.30.9 cross-compilado** (`C:\e-core\_build_sdl2_aarch64.sh`):
```
Video drivers   : dummy offscreen kmsdrm(dynamic) opengl opengl_es1 opengl_es2 vulkan
Audio drivers   : disk dummy oss alsa(dynamic)
Using libudev   : YES    dbus/ime: NO
```
Artefato `libs/libSDL2-2.0.so.0.3000.9` (+ cópia `libSDL2-2.0.so.0`), 1,6 MB strip,
NEEDED só `libm/libc`; dlopen em runtime de `libdrm.so.2`, `libgbm.so.1`,
`libvulkan.so.1`, `libasound.so.2`, `libudev.so.1`.
Validação qemu (`_sdl_probe.c`): `video drivers (4): KMSDRM offscreen dummy evdev`,
`SDL-2.30.9`, e o erro de Vulkan muda para o ramo "driver dummy não suporta Vulkan"
(ou seja: **SDL agora tem Vulkan**).

**Risco aberto (bloqueante):** lavapipe/llvmpipe (Mesa 23.2.1) **não expõe
`VK_KHR_display`** — só `VK_KHR_surface` + xcb/xlib/wayland. O SDL KMSDRM usa
exclusivamente `VK_KHR_display` (`vkCreateDisplayPlaneSurfaceKHR`). Se o R36S só tiver
`lvp_icd.json`, falhará com `Installed Vulkan doesn't implement the VK_KHR_display
extension` mesmo com SDL correto.

**Recon adicionado no launcher** (roda antes do jogo, sai no `log.txt`):
`/dev/dri`, listagem+conteúdo de `/usr/share/vulkan/icd.d/*.json`, `ldconfig -p` de
libvulkan/gbm/drm/mali, e `vkprobe` (aarch64, dlopen — não depende de `vulkaninfo`)
por ICD, imprimindo `VK_KHR_display: SIM/NAO` e os devices físicos.

Evidência: `evidencias/evidence_device_log_sdl_vulkan_20261017.md`.

---

## Sessão 2026-10-17 (cont. 3) — AUDITORIA OFFLINE DO FIRMWARE: bloqueio definitivo do Vulkan

Pivô de estratégia: em vez de levar o `vkprobe` ao console (reboot/cópia no SD), a
imagem oficial foi auditada **offline no WSL**: descompressão do
`dArkOSen_R36_09302026.img.xz` (8.773.435.392 bytes, `EXIT=0`), montagem read-only da
partição 2 (offset 121.634.816, loop device) e execução do `vkprobe` (aarch64) sob
`qemu-aarch64-static -L /opt/r36s/rootfs` **contra os ICDs reais do device**.

Evidência RAW completa: `evidencias/evidence_firmware_vulkan_audit_20261017.md`.

**Respostas (fatos medidos):**

| ICD do firmware | Vulkan | `VK_KHR_display` | WSI |
|---|---|---|---|
| `mali_icd.json` → `libmali-bifrost-g31-rxp0-gbm.so` (blob ARM 40 MB) | 1.0.x | **NÃO** | **nenhum** (`VK_KHR_surface` count=0 no binário) |
| `lvp_icd.json` (lavapipe, llvmpipe LLVM 19.1.7) | 1.4.305 | **NÃO** | wayland/xcb/xlib/**headless** |
| `panfrost_icd.json` (panvk) | 1.4.305 | **NÃO** | wayland/xcb/xlib/headless |
| `radeon`/`nouveau` (**controle positivo**) | 1.4.305 | **SIM** | display/wayland/xcb/xlib |

- O controle positivo (radv/nvk, mesmo Mesa 25.0.7 do device) dá `SIM` → o resultado
  `NÃO` de lvp/mali/panfrost é **fato**, não artefato do QEMU.
- Fonte do Mesa (`panvk_instance.c`) confirma: panvk só liga `.KHR_display` com
  `VK_USE_PLATFORM_DISPLAY_KHR` definido no build — não é o caso do panvk do Debian 13.
- Kernel do firmware: **4.4.189 + `mali_kbase` (bifrost)**, sem panfrost ⇒ panvk inviável
  de qualquer forma. Rootfs: Debian 13 (trixie), glibc 2.41.
- Blob ARM entrega **GLES 1/2/3 + EGL + GBM acelerados por HW**
  (`libgbm.so.1 -> libMali.so`), mas **Vulkan sem WSI**.
- SDL 2.30.9 do port está correto (`KMSDRM` + `Vulkan` compilados) e usa
  **exclusivamente `VK_KHR_display`** ⇒ o problema nunca foi o SDL.

**Decisão:** **não implantar** o caminho Vulkan/KMSDRM no R36S com este firmware — o
bloqueio é ausência de recurso no driver (não é configurável por env/ICD/SDL). Caso
aplicável do ponto de decisão do plano: "somente lavapipe" (e pior: lavapipe também
não serve para KMSDRM).

**Opções para a próxima sessão:** (A) manter o port para devices com WSI display;
(B) renderer GLES/HW no lugar do RT64 (reescrita grande); (C) fallback software
(lavapipe + X11/Wayland na device) apenas para medir fps; (D) `VK_EXT_headless_surface`
(lavapipe) + apresentação própria via KMS/dumb buffer (patch no frontend + RT64).

Ferramentas reutilizáveis (no projeto): `evidencias/tools/audit_rootfs.py`,
`evidencias/tools/audit_vulkan_icd.py` (md5 `ec8c2117eaec2d992a8c58b291b448d1` e
`cbbcd6ba62e6c76cf1bacb6f4fb0083c`).

**Launcher atualizado:** `BodyHarvest.sh` (md5 `f004d2500a07784554b60beccd23ef68` no instante
desta etapa; depois passou a `1f1962b445d5def4f62ab14bd1048141` com o bloco de recon GLES —
ver sessão cont. 4) imprime o diagnóstico definitivo quando nenhum ICD expõe
`VK_KHR_display` + device — sem mudar o comportamento (segue tentando rodar).

---

## Sessão 2026-10-17 (cont. 4) — DECISÃO B: backend OpenGL ES (HW) para o RT64

**Decisão do usuário:** investir em renderer OpenGL ES com aceleracao de hardware (o unico
caminho HW disponivel no R36S), no lugar do RT64/Vulkan.

**Recon de viabilidade (offline) — evidência `evidencias/evidence_gles_backend_recon_20261017.md`:**

- **Seam:** a RHI do RT64 é o **Plume** (`src/contrib/plume/`): interface de **268 linhas / 103
  métodos virtuais puros**; já existem 3 backends (Vulkan 4641 linhas, D3D12 4258, Metal 4229 —
  Metal é o melhor molde). Escopo estimado do backend GLES: **~3,5–4,5k linhas**.
- **Extensão já prevista:** `UserConfiguration::GraphicsAPI` + `switch` em
  `rt64_application.cpp` (~157-188) ⇒ adicionar `GraphicsAPI::GLES` é natural e testável por config.
- **Shaders:** HLSL → DXC → SPIR-V → (MSL via `spirv_cross_msl` no macOS). O **SPIRV-Cross
  vendorizado tem backend GLSL** (`spirv_glsl.{cpp,hpp}`) ⇒ GLES = novo `RenderShaderFormat::GLSL_ES`
  + ramo novo em `CREATE_SHADER_INPUTS` + passo `.spv → GLSL ES 3.20` no CMake. **Shaders do jogo
  não precisam ser reescritos.**
- **Blob Mali (offline):** `OpenGL ES 3.2`, `EGL_KHR_platform_gbm`, `gbm_create_device`,
  `glDispatchCompute` (compute), `GL_EXT_geometry_shader`, **`GL_ARM_shader_framebuffer_fetch`**,
  `GL_EXT_multisampled_render_to_texture` + `glFramebufferTexture2DMultisampleEXT`,
  `GL_EXT_buffer_storage`, `glBlitFramebuffer`, `glMapBufferRange`, `glInvalidateFramebuffer`.
- **Toolchain pronto:** sysroot com `GLES3/gl32.h`, `libGLESv2.so.2`, `libEGL.so.1`, `libgbm.so.1`;
  nosso SDL 2.30.9 com `EGL support: yes` + `kmsdrm` + `opengl_es2`.

**Entregue — `glesprobe`** (aarch64, 18.840 bytes, NEEDED só libSDL2/libc; funções GL por
`SDL_GL_GetProcAddress`), fonte em `evidencias/tools/gles_probe.c`:
- Execução sob QEMU com o SDL do device: **contexto OpenGL ES 3.2 criado**, 158 extensões
  reportadas, **16/18 extensões úteis presentes**, `3 frames em 76 ms (swap OK)` ⇒ lógica validada.
- Execução com o **nosso SDL 2.30.9**: drivers `KMSDRM offscreen dummy evdev` (o SDL **do sistema
  não tem KMSDRM**) e falha graciosa de EGL offline (sem `/dev/dri`) ⇒ o port **precisa continuar
  embarcando SDL**.
- Integrado ao `BodyHarvest.sh` (bloco de recon; desligável com `BH_NO_GLES_RECON=1`).

**Discrepância detectada (a confirmar):** a imagem auditada (`dArkOSen 09302026`, kernel
`#1 SMP Fri Sep 25 02:17:24 UTC 2026`) não é o build que estava instalado no console no log
anterior (kernel `4.4.189 #62 Sat Dec 13 08:49:45 CST 2025`) — o SDL da imagem não tem KMSDRM.
Confirmar qual build está rodando antes de medir FPS.

**Plano:** `docs/PLANO_BACKEND_GLES_R36S.md` — marcos M0 (concluído), M1 shaders GLSL ES,
M2 esqueleto `plume_gles` + apresentação, M3 descriptors sem bindless, M4 raster RDP
(FB/TMEM/MSAA/fetch), M5 integração + medição de FPS, M6 otimização/empacotamento, com critérios
de aceite e de rollback.

**Próximo passo:** M1 (pipeline de shaders GLSL ES) — valida-se antes de escrever o backend,
porque é o maior risco evitável (saber que os shaders do RT64 compilam em GLSL ES 3.20).

---

## Sessão 2026-10-18 (cont.) — M1.2 CONCLUÍDO: canal GLES no build

**Decisão de rota (registrada):** rota **B** (backend `plume_gles` no RT64) mantida. O
**GLideN64 fica apenas como oráculo de validação** visual (golden frames no PC) — nunca como
implementação: arquitetura incompatível (o port é HLE-GBI; GLideN64 é plugin LLE RDP de
mupen64plus) e licença GPL-2 × MIT do RT64.

**Entregue (M1.2 — 1ª parte do Passo 1 do plano):**

- `RenderShaderFormat::GLSL_ES` no enum do Plume (APPEND ao fim: DXIL=1/SPIRV=2/METAL=3 intactos).
- `CREATE_SHADER_INPUTS` com **4 blobs** (`DXIL, SPIRV, MSL, GLSLES`): 32 call sites passam
  `<X>BlobGLSLES`; o 4º argumento é ignorado sem o gate `RT64_GLSL_ES_BLOBS`.
- CMake: `option(RT64_GLSL_ES_SHADERS OFF)` + `build_shader_glsl_es_impl`
  (DXC `+ -D HLSL_GLES` → `.glsl_es.spv` → `file_to_c` → `<X>BlobGLSLES`) + hooks em
  `build_shader()`/`build_shader_spirv()` + alvo `rt64_glsl_es_validate`.
- **Bug latente do M1 corrigido**: `DEPENDS ${FILENAME}` → `+ ${RT64_SHADER_HEADERS}`
  (20 `.hlsli` + 30 `shared/*.h`), provado no `build.ninja`.
- **Aceite**: `RESUMO M1.2 GLES: shaders=58 ok=57 excluidos=1 ausentes=0 falhas=0`
  (DebugPS = caminho RT não expressável em ESSL 3.20). Não-regressão DX/VK: **56/56 md5 idênticos**.
- **Desvio registrado**: o blob embutido é o **SPIR-V GLES** (1.584.516 B) e não o texto ESSL
  (3.468.332 B), para casar com o M1.3 ("especializar com `re-spirv` → converter com `spirv-cross`").
- Scripts novos: `evidencias/tools/m1_2_apply_gles_channel.py` (apply/revert/check, com backup e md5),
  `m1_2_fix_sysroot_sdl2_prefix.sh`, `evidencias/tools/staged/glsl_es_{sanitize,validate}.cmake`.
- Evidência RAW: `evidencias/evidence_m1_2_gles_channel_20261018.md`.

**Bloqueios de ambiente resolvidos nesta sessão (ortogonais):**
1. `sdl2-config.cmake` do sysroot com `prefix "/usr"` → CMake falhava o **generate**
   (`SDL2::SDL2 includes non-existent path`). Restaurado `prefix "/root/sysroot64/usr"` **e** os
   **dois** include dirs (`.../include/SDL2;.../include`) — sem o segundo, `recompui/ui_state.cpp`
   falha com `SDL2/SDL_video.h: No such file` (era o estado do build M1, conforme log de 10-18).
2. Regex de estágio derivado de `${ARGN}` no CMake (chega como lista: `-E;PSMain`) → 27
   falsos-positivos de `glslangValidator` (mesmo padrão do M1.1 §1); corrigido.

**Próximo passo:** M1.3 (runtime: `re-spirv` + `spirv-cross` no binário; < 50 KB por shader) e,
em paralelo, validar o binário `BodyHarvestRecompiled.m1_padding_20261018` no R36S.

---

## Sessão 2026-10-18 (cont. 2) — LINK aarch64 DESBLOQUEADO + M1.3 estágio 1 MEDIDO

**Entregue:**

- **Link CMake/ninja do binário aarch64 RESOLVIDO** (bloqueio pré-existente, ~0,5 sessão):
  causa-raiz = **cache obsoleto `pkgcfg_lib_GTK3_*`** no `CMakeCache.txt` (escolhia `libcairo.a`,
  `libglib-2.0.a`, `libharfbuzz.a`, `libgio-2.0.a`, `libgobject-2.0.a`, `libcairo-gobject.a` do
  sysroot, arrastando `pcre`/`gpg-error`/`LZ4`), + `--allow-shlib-undefined` necessário para DSOs
  transitivos com deps ausentes do sysroot. **Nenhuma fonte editada** (md5 dos 3 CMakeLists
  inalterados). Correções: `cmake -U 'pkgcfg_lib_GTK3_*'` e
  `set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--allow-shlib-undefined")` no `Toolchain-aarch64.cmake`.
- **Resultado**: `[241/242] Linking CXX executable` → `ninja: no work to do`;
  binário **19.869.608 B**, md5 `b35315d93a86378c007999b99bb6cf5c`, com **31 símbolos `*BlobGLSLES`**
  no ELF (o canal GLES do M1.2 agora existe dentro de um binário linkado por CMake).
- **`libgtkshim.so` aposentado**: auditoria do rootfs **do device** (extraído de `darkos.img` +
  `diag_results/diag*.txt`, `dArkOSen-r36` Debian 13 trixie) prova que `libgtk-3.so.0`,
  `libgdk-3.so.0`, `libglib-2.0.so.0.8400.4`, `libgobject-2.0.so.0`, `libdbus-1.so.3` e
  `libfreetype.so.6` existem no R36S → a lista NEEDED é satisfeita. O shim era só consequência do
  link quebrado. (Armadilha registrada: um `grep | head -20` deu falso negativo "GTK não existe".)
- **M1.3 estágio 1 (aceite do plano) medido**: `re-spirv` especializa o SPIR-V GLES (284 KB → 28 KB)
  e o `spirv-cross --es --version 320` gera **28.986-29.033 B** de ESSL válido
  (**< 50 KB**, ≈24× menor que os 704.897 B do ubershader). Custo: 0,03-0,22 s por especialização
  no host ⇒ extrapolado ≈0,3-4 s no Mali-G31 → **requisito de cache em disco para M2/M6**.
- Perfil alternativo medido: `-DNFD_PORTAL=ON` (link só com `libdbus-1.so`, sem GTK); canônico
  segue **GTK** (default upstream).
- Artefatos: `BodyHarvestRecompiled.m1_2_cmake_gtk_20261018` e
  `BodyHarvestRecompiled.m1_3_cmake_portal_20261018`; script
  `evidencias/tools/m1_3_stage1_specialize.sh`; evidência RAW
  `evidencias/evidence_m1_3_link_and_stage1_20261018.md`.

**Lições de método (registradas):** `run_commands` **apaga `$var`** do comando (heredoc gera script
com variável vazia → usar arquivos criados pelo editor e `bash /mnt/c/...`); `head` em listagem
grande produz falso negativo.

**Próximo passo:** M1.3 **estágio 2** (~1 sessão) — linkar `spirv-cross` (target `spirv-cross-c`) no
binário + casos `RenderShaderFormat::GLSL_ES` nos switch de runtime
(`rt64_shader_library.cpp:705/741/776`, `rt64_raster_shader.cpp:101/140/418/425/432/499/505`,
`rt64_raster_shader_cache.cpp:109`); depois M2 (`plume_gles` + frames na tela).

---

## Sessão 2026-10-18 (cont. 3) — M1.3 ESTÁGIO 2 CONCLUÍDO (`spirv-cross` linkado + `GLSL_ES` no runtime)

**Entregue:**

- **`spirv-cross` LINCADO no binário aarch64.** `add_subdirectory(src/contrib/spirv-cross)` +
  `target_link_libraries(rt64 spirv-cross-c)`, com **GATE em `RT64_GLSL_ES_SHADERS=ON`** (builds
  DX/VK/MSL seguem byte-idênticos). Perfil mínimo: CLI/tests/install/HLSL/MSL/CPP/reflect/util OFF,
  C_API/STATIC ON. Prova: `libspirv-cross-{core,glsl,c}.a` gerados; `ninja rc=0`; binário
  **22.860.752 B** (md5 `002ebe73398da05613b3396d4bb2d615`, **+2,99 MB**), **228 símbolos `spvc_`**
  e **54 arrays `*BlobGLSLES`** no ELF (era 31 — `rt64` é `STATIC`, então o linker descartava os
  blobs que nenhum caminho `GLSL_ES` alcançava).
- **Casos `RenderShaderFormat::GLSL_ES` no runtime** — 15 edições + 3 arquivos novos:
  `lib/rt64/src/render/rt64_glsl_es.{h,cpp}` (conversor SPIR-V→ESSL, **livre de `plume`** para ser
  testável no host) e `rt64_glsl_es_device.h` (wrapper **header-only** `RT64::createShader`).
  Cobertura: ctor do `RasterShader` (re-spirv + conversão), blobs do `RasterShaderUber`
  (`RasterVSDynamic`/`PSDynamic`/`PSDynamicMS`), post-blend, bloco de *hardware resolve* do
  `rt64_shader_library` (**com blobs GLES próprios** — os SPIRV usam textura 1D/descriptor indexing)
  e `OptimizerCacheSPIRV::initialize(format)`. Os **57** pontos de `device->createShader(` passaram
  pelo wrapper → zero mudança semântica para DXIL/SPIRV/METAL.
- **Fidelidade ao pipeline validado**: a C API do `spirv-cross` reproduz o CLI `--es --version 320`
  *incluindo* os defaults aplicados quando `--vulkan-semantics` não é passado
  (`combined_image_samplers=true` + `build_dummy_sampler=true` com set 0/binding 0) — sem isso o ESSL
  não compila em 3.20. O sanitizador foi portado 1:1 de `src/tools/glsl_es_sanitize.cmake`.
- **Aceite (item c do plano) medido com o CÓDIGO DE PRODUÇÃO sobre os BLOCOS REAIS** (12 shaders:
  6 spec-constant + 6 blob direto): **12/12 OK**, `glslangValidator` **12/12**, rc=0.
  Caminho especializado: SPV 284.228 B → **11.120 B** pós-`re-spirv` → **8.777-8.814 B** de ESSL
  (aceite `< 50 KB` superado ~5,7×). Custo host x86-64: `re-spirv` 1,2-3,0 ms + `spirv-cross` 2,1-3,9 ms.
- **Estado canônico preservado**: `NFD_PORTAL=OFF`, `--allow-shlib-undefined` no toolchain,
  `ninja -C build-aarch64 BodyHarvestRecompiled` → **`ninja: no work to do`**.

**Risco novo registrado — R7 (para M2/M6):** o caminho do **ubershader**
(`RasterPSDynamic`/`RasterPSDynamicMS`) produz **260.915 / 262.267 B de ESSL** porque não passa por
especialização (`DYNAMIC_RENDER_PARAMS` via UBO). Extrapolando o Mali-G31 do estágio 1 (~20-50× o
host; no host o `spirv-cross` sozinho leva ~50 ms), o *stall* de partida pode ser de **segundos**.
Mitigações a decidir no M2: não materializar o ubershader em GLES / cache em disco da especialização
/ medir antes de otimizar.

**Lições de método (registradas):**
- **Patcher destrutivo não pode ser re-executado.** A 2ª execução de `m1_3_stage2_apply.sh` abortou
  numa contagem e o *restore* apagou os 3 fontes novos (o backup havia sido refeito já no estado
  patchado). Corrigido com um guard `BASELINE_MD5` que recusa rodar sobre árvore já patchada.
- **`rm -rf build/` enquanto um build roda nele** derruba a compilação (`fatal error: opening
  dependency file ….d: No such file or directory`). Esperar o processo morrer antes de limpar.
- A armadilha do `$var` reapareceu: loops de validação com `$pass`/`$stage` viraram comandos quebrados
  (`pass=`/`fail=` vazios). Sempre autorar script em arquivo e invocar por caminho literal.

**Artefatos:** `evidencias/evidence_m1_3_stage2_20261018.md` (RAW completo),
`evidencias/m1_3_stage2/` (apply.log, validate.log, host_test.txt, logs/{aarch64_driver,reconfigure,
aarch64_build_tail}.log, **12 arquivos `.essl`**), scripts em `evidencias/tools/staged/`
(`m1_3_stage2_apply.{sh,py}`, `m1_3_stage2_build_aarch64.sh`, `m1_3_stage2_host.sh`,
`m1_3_stage2_validate.sh`, `CMakeLists.host.txt`, `m1_3_stage2_host.cpp`, os 3 fontes de produção).
Mirror de execução: `/root/bhrecomp/m1_3_gles/stage2/`.

## M2 — Esqueleto `plume_gles` + apresentação — **Sessão 1 ✅ CONCLUÍDA (2026-10-18)**

Evidência RAW: `evidencias/evidence_m2_gles_skeleton_s1_20261018.md`.
Estado: **esqueleto completo e host-testável**; o aceite do M2 (`gles_smoke` apresentando
frames **no device**) **ainda não foi executado** — falta a etapa 2.

- **Carregador GLES auto-contido gerado** (`evidencias/tools/gen_gles_loader.py`, padrão do
  `volk/generate.py` já vendorizado no repo): **358/358** entry points, **1006** constantes,
  22 tipos ⇒ `plume_gles_gl.h` (1799 linhas) + `plume_gles_gl.cpp`. Conferido por `comm`
  contra o `gl32.h` do Khronos: **zero lacunas**. Por que gerar em vez de
  `#include <GLES3/gl32.h>`: o header do Khronos **emite os protótipos**, o que impediria a
  tabela de ponteiros homônima, além de criar dependência do sysroot.
- **Host-testável (disciplina do M1.3 preservada)**: compila no x86_64 **sem sysroot, sem
  SDL2 e sem link a `libGLESv2`** (`g++ -Wall -Wextra -c plume_gles_gl.cpp` → rc=0,
  260.208 B de `.o`).
- **Cobertura da interface provada por `static_assert`** (`m2_hdr_coverage.cpp`): 22 classes
  concretas instanciáveis + `GLESPipeline` abstrata. Um virtual puro esquecido não gera erro
  por si só (a classe apenas fica abstrata, e o erro só aparece no `new`, no device) —
  agora é **erro de compilação no host**.
- **Decisão de desenho (backend SDK-free)**: `plume_gles` **não inclui `<SDL.h>`**.
  Janela/apresentação entram por `GLESSwapChainFunctions` (4 ponteiros: `swapWindow`,
  `getWindowSize`, `setSwapInterval`, `getDisplayRefreshRate`) e os entry points por
  `GLESProcResolver`. Motivação medida: o host **não tem** `/usr/include/SDL2/SDL.h` (só o
  sysroot aarch64 tem) — sem o shim, o backend perderia a testabilidade fora do device.
- **Implementado**: tradutores `toGLES*` com tabela única `RenderFormat -> (externo, interno,
  tipo)`; `GLESInterface` completa (`shaderFormat = GLSL_ES`); `GLESDevice` com carga dos
  entry points (falha **nomeada**), `queryContextInfo()` (versão/vendor/renderer/GLSL, lista
  de extensões via `glGetStringi`, 9 limites), `hasExtension()` por token e as 17 capacidades
  derivadas de medição. `unimplemented()` = ponto único de falha alta.
- **9 erros reais** encontrados pela compilação contra os headers reais (nenhum por leitura):
  `RenderPipelineType`/`RenderBlendFactor`/`RenderStencilOperation`/`RenderMipmapFilter`
  inexistentes, `RenderCommandListType::GRAPHICS` inexistente (os reais são
  `UNKNOWN/DIRECT/COMPUTE/COPY`), `RenderSwapChain` tem **14** métodos (não 10:
  `acquireTexture`/`getWindow`/`isEmpty`/`getRefreshRate`), `RenderTextureDesc` usa
  `multisampling.sampleCount`/`arraySize`, `RenderDeviceVendor` **não tem `ARM`**, e dois
  achados materiais novos (abaixo).
- **R8 (NOVO, M3/M4)** — ES 3.2 core **não tem `GL_BGRA`** (`B8G8R8A8_UNORM`) **nem UNORM de
  16 bits** (`GL_RGBA16`/`GL_RGBA16_SNORM`/`GL_RG16`/`GL_R16`). Provado por grep no
  `gl32.h`. Atinge diretamente TMEM/framebuffer do RT64. Mitigação a decidir:
  `GL_EXT_texture_norm16` (confirmar no blob Mali) ou downgrade + `GL_TEXTURE_SWIZZLE_*`.
  Até lá caem em `unimplemented()`.
- **R9 (NOVO, M3)** — sem `GL_MIRROR_CLAMP_TO_EDGE`; `RenderTextureAddressMode::MIRROR_ONCE`
  precisa de fallback explícito.
- **Pendente (2-3 sessões)**: `GLESDevice::create*` + recursos (buffer/texture/sampler/
  framebuffer/fence/semaphore/queryPool/pipeline), `CommandQueue`+`CommandList` em **modo
  imediato** (clear+swap reais; reavaliar no M3), `SwapChain` via o shim, gate
  `RT64_GLES_BACKEND` no CMake (builds DX/VK/MSL seguem byte-idênticos), `gles_smoke.cpp` e
  execução sob QEMU contra `/opt/r36s/rootfs` (receita já validada no M0).
- Artefatos: `evidencias/tools/gen_gles_loader.py`, `evidencias/tools/staged/` (`plume_gles.h`
  md5 `f0f0c175…`, `plume_gles.cpp` md5 `4cab3324…`, `plume_gles_gl.h` md5 `9678cf48…`,
  `plume_gles_gl.cpp` md5 `573fa89a…`, `m2_hdr_coverage.cpp`). Espelho de execução:
  `/root/bhrecomp/m2_gles/staged/`.

**Próximo passo:** **M2 etapa 2** — fechar `create*`/recursos/`CommandList`/`SwapChain` +
gate CMake + `gles_smoke` sob QEMU (gate 1: frames na tela), já com **R7** (ubershader
~260 KB de ESSL) e **R8**/**R9** na mesa. Depois M3 (descriptor windowing) → M4 → M5 → M6.

---

## M2 — `plume_gles` sessão 2: device, recursos, command list e swapchain (2026-10-18) ✅

Evidência: RAW em `evidencias/m2_gles_s2/verify_raw.txt` (reprodutível por
`evidencias/tools/staged/verify_s2.sh`); narrativa em
`evidencias/evidence_m2_gles_skeleton_s2_20261018.md`.

**Escopo entregue.** `plume_gles.cpp` foi de **473 → 2344 linhas** (`plume_gles.h` 604 → 609).
Implementados os 16 `GLESDevice::create*` e todos os recursos: buffer (`glBufferData`/
`glMapBufferRange` com recorte de faixa), texture (`glTexStorage2D/3D/2DMultisample`, imutável),
texture view, sampler (objeto real de sampler, com anisotropia/LOD/comparação), framebuffer
(anexos + `glCheckFramebufferStatus`), shader (compila ESSL **no pipeline**, que conhece o
estágio), pipelines compute/graphics (link + log de erro), pipeline layout, descriptor set
(armazenamento para o M3), pool, query pool, fence, semaphore. Mais: `GLESCommandQueue`,
`GLESCommandList` em **modo imediato** (begin/end, framebuffer com espelho, viewport, scissor,
clear color/depth/stencil, depth bias, barriers, dispatch, setPipeline, cópia de buffer,
resolve por blit) e `GLESSwapChain` completo.

**Achado metodológico (o mais importante desta sessão).** A verificação da sessão 1 usou
`-fsyntax-only`, que **não linka** — por isso não podia detectar símbolo *declarado e nunca
definido*. Ao adicionar **link real** ao aceite, apareceram dois: `GLESDevice::hasExtension` e
`validateShaderFormat`. O link cobre a interface inteira porque `~GLESDevice()` é a *key
function* da classe: a vtable é emitida nesse TU e referencia **todos** os virtuais. Regra
adotada: validar backend escrito contra header grande exige **compilar E linkar**.

**Aceite do M2 cumprido em forma verificável (sem hardware).** `gles_smoke.cpp` é o *chamador*
do backend (papel do SDL2 no device), mas via **EGL puro** e **sem incluir `<GLES3/gl3*.h>`** —
todo símbolo GL vem do carregador gerado, então o teste não pode escapar do caminho real. Com
contexto **ES 3.2 real** (Mesa llvmpipe) ele faz `command list → clear colorido em FBO 0 →
present` e **lê o pixel de volta**: `RGBA(64,128,191,255)`, exatamente a cor pedida, com
`glGetError() == 0`. **15/15 checagens OK.** Também cobre `glTexStorage2D` + `createFramebuffer`
+ `resolveTexture` (blit com FBOs temporários) lendo `RGBA(255,0,0,255)` da textura de destino, e
valida o caminho *headless* do swapchain (sem janela ele herda o tamanho do viewport que o EGL
inicializa com as dimensões do drawable).

**On-target (aarch64/QEMU).** `gles_target_probe.cpp` roda **7/7 OK** sob
`qemu-aarch64-static -L /opt/r36s/rootfs`: prova que o carregador (358 entry points, **ambos** os
caminhos de `load`) e a camada de interface executam corretamente no alvo.

**Limitação delimitada com evidência (não é falha do backend).** O smoke **não** roda sob QEMU:
o rootfs aponta `libEGL.so.1 → libMali.so` (blob exige GPU Mali real) e **não existe dispatcher
GLVND** — a única lib EGL real é `libEGL_mesa.so.0.0.0`, que é lib *vendor* e **não exporta**
`eglGetDisplay`/`eglGetProcAddress` (comprovado por erro de link). Consequência registrada para o
M6: validação funcional completa exige hardware (ou rootfs com GLVND + Mesa softpipe).

**Erros reais pela compilação (3, todos informativos).** `GL_TEXTURE_MAX_ANISOTROPY_EXT` **não
existe** no `gl32.h` (é de `gl2ext.h`; valor `0x84FE` verificado no rootfs) → constante declarada
localmente; `RenderFormat::D24_UNORM_S8_UINT` **não existe** (o enum só tem `D32_FLOAT_S8_UINT`
como depth-stencil empacotado); e `&RenderViewport(rvalue)` no smoke (resolvido com a sobrecarga
por referência). Mais 3 *warnings* de `-Wextra` silenciados com `(void)` justificado. Resultado:
**zero warnings** nos 4 TUs, host e aarch64.

**Escopo consciente (aborta de propósito, nunca em silêncio).** O caminho de **raster/draw**
(input layout + estado fixo do pipeline = M4), push constants, binding real de descriptors (M3),
`copyTexture`/TMEM (M3) e ray tracing abortam via `unimplemented()` com nome. Justificado:
desenhar antes de ter input layout + estado fixo produziria imagem errada sem aviso;
`GLESAccelerationStructure` inclusive não define construtor (a capacidade `raytracing` é `false`).

**Artefatos.** `plume_gles.h` md5 `54aaf808…` (609 linhas), `plume_gles.cpp` md5 `57a43775…`
(2344), `gles_smoke.cpp` md5 `c6e95463…`, `gles_target_probe.cpp` md5 `eb2fe629…`; incremento
`plume_gles_s2_inc.inc` md5 `11968b91…` aplicado por `apply_s2.py` md5 `f92fb722…` (determinístico
e idempotente). Estado anterior preservado em `evidencias/m2_gles_s2/*.s1` (`f0f0c175…`,
`4cab3324…`). Backend segue **inerte**: nenhuma `CMakeLists` referencia `plume_gles.{cpp,h}` e
nenhum objeto `*plume_gles*` existe em `build-aarch64/` (a menção no `lib/rt64/CMakeLists.txt:119`
é um **comentário**).

---

## Sessão 2026-10-18 (cont. 3) — M2 FECHADO (estrutural): gate `RT64_GLES_BACKEND` + `GraphicsAPI::GLES`

**Objetivo:** tirar o backend `plume_gles` do isolamento (smoke test) e colocá-lo **dentro do
build real do RT64**, selecionável por `GraphicsAPI::GLES`, sem afetar os backends existentes.

**Entregue (11 arquivos, 22 substituições)** — script
`evidencias/tools/m2_gles_gate_apply.py` (`check`/`apply`/`revert`, backup + md5, **idempotente por
sondas** porque 6 dos textos novos contêm o antigo como substring; 20/20 + 2/2 aplicadas):

- **Gate `RT64_GLES_BACKEND` (default OFF)**: `option` em `lib/rt64/CMakeLists.txt` e em
  `lib/rt64/src/contrib/plume/CMakeLists.txt` (mesma variável de cache → `plume_gles.{cpp,h}` +
  `plume_gles_gl.{cpp,h}` dentro do alvo `plume`); `-DRT64_GLES_BACKEND` no alvo `rt64` e (global)
  no `BodyHarvestRecompiled`; aviso explícito quando ligado sem `RT64_GLSL_ES_SHADERS`; status do
  configure passa a imprimir `GLES=${RT64_GLES_BACKEND}`.
- **`GraphicsAPI::GLES`**: enum (antes de `Automatic`, ordem casada com o `ImGui::Combo`
  posicional), `"GLES"` no JSON, rótulo do inspector; `isGraphicsAPISupported(GLES)` = `true`
  **só** com o gate ligado (sem ele, config com `"GLES"` cai em `Automatic`).
- **`rt64_application.cpp`**: caso do switch + `CreateGLESInterfaceWrapper` (contexto **ES 3.2**
  real via `SDL_GL_CreateContext` + `MakeCurrent` + `SDL_GL_SetSwapInterval(1)` + os 4 ponteiros de
  `GLESSwapChainFunctions`); Inspector recusado para GLES com mensagem nomeada (R10).
- **`rt64_application_window.{h,cpp}`**: `setup(..., useOpenGL)` ⇒ `SDL_WINDOW_OPENGL` **sem**
  `SDL_WINDOW_VULKAN`; contexto GL liberado no destrutor.
- **Lacuna nova descoberta e fechada:** a janela nasce em `src/main/main.cpp` (entregue ao RT64 via
  `WindowHandle`) e o SDL2 **rejeita duas flags de backend** na mesma janela
  (`SDL_video.c`: *"Conflicting window flags specified"*) ⇒ `BH_GRAPHICS_API=gles` decide a flag lá.

**Aceite medido (RAW em `/root/bhrecomp/m2_gles_gate_20261018/ninja_build_{off,on,on2}.log`):**

- gate **OFF**: build verde, 0 erros; **0** símbolos `GLESDevice/GLESInterface/CreateGLESInterface`
  e **0** `plume_gles` em strings (calibração: `VulkanDevice` = **107**; binário não-stripped);
- gate **ON**: build verde, 0 erros; objetos `plume_gles.cpp.o` (151.600 B) +
  `plume_gles_gl.cpp.o` (148.352 B) dentro do `libplume.a`; **83** símbolos GLES no binário aarch64,
  incluindo `plume::CreateGLESInterface(void*, void* (*)(char const*), plume::GLESSwapChainFunctions)`;
  strings do wrapper/switch presentes no ELF.

**Desvio de aceite (registrado, não maquiado):** o plano pedia "builds DX/VK/MSL byte-idênticos"
com o gate OFF. **Não se sustenta:** 5 edits são compilados incondicionalmente (membro do enum,
entrada JSON, `useOpenGL`/`windowUsesOpenGL` na janela, string do Combo) ⇒ o binário OFF difere do
pré-gate (`002ebe73…` → `dbf71397…`, +4.160 B) por razões **semântico-neutras**. Critério objetivo
que substitui a byte-identidade: **gate OFF ⇒ zero símbolo/string GLES** (medido: 0).

**Pendente para o teste real (M5):** o launcher `BodyHarvest.sh` precisa ligar as **duas** chaves
coerentes — `BH_GRAPHICS_API=gles` (flag da janela) **e** `graphicsAPI: "GLES"` no `rt64.json`
(a config do RT64 é lida depois da janela existir). Depois: primeira execução real no R36S via
SDL2→Mali (o raster continua abortando de propósito — M4).

**Riscos:** **R10** Inspector (ImGui) inexistente para GLES; **R11** flag da janela precede a
leitura da config ⇒ a seleção automática de API tem de ser decidida antes de `create_window()`.

---

## M5 — SELEÇÃO DE API GLES (config + launcher) ✅ ENTREGUE (2026-10-18)

Evidência completa: `evidencias/evidence_m5_gles_api_select_20261018.md`.
Ferramentas: `evidencias/tools/m5_gles_api_select_apply.py`,
`m5_build_aarch64.sh`, `m5_gate_off_tu_check.sh`, `m5_launcher_smoketest.sh`.
RAW: `/root/bhrecomp/m5_gles_api_select_20261018/`.

**Correção de escopo (o M2 apontava para o alvo errado):** a pré-condição registrada era
`graphicsAPI: "GLES"` no **`rt64.json`** — essa via **não existe** neste port
(`appConfig.useConfigurationFile = false` em `recompui/src/renderer/rt64_render_context.cpp:271`).
A cadeia real é `graphics.json["api_option"]` → `ultramodern::renderer::GraphicsApi` (enum) →
`switch` no recompui → `RT64::UserConfiguration::GraphicsAPI`. E o `graphics.json` do device vive em
**`$HOME/.config/bhrecomp/`** (`program_id = "bhrecomp"`; `get_app_folder_path()` no Linux), não na
pasta do port.

**Entregue — 7 edits / 4 arquivos** (todos sob `#ifdef RT64_GLES_BACKEND`):

| Ponta | Arquivo | Conteúdo |
| :--- | :--- | :--- |
| Enum | `ultramodern/include/ultramodern/config.hpp` | `GLES` **depois** de `Metal` (valor 4) + par NLOHMANN (bloco duplicado sob `#ifdef`/`#else` porque `NLOHMANN_JSON_SERIALIZE_ENUM` é macro) |
| Nome | `ultramodern/src/renderer_context.cpp` | `get_graphics_api_name` → `"GLES"` |
| UI/catálogo | `recompui/src/config/ui_config_tab_graphics.cpp` | `ALLOW_GLES` (Linux + gate) + `{GLES, "GLES"}` |
| Seleção | `recompui/src/renderer/rt64_render_context.cpp` | case no `switch(cur_config.api_option)` **e** em `map_graphics_api` (sem o 2º: `assert` → `exit`) |
| Launcher | `BodyHarvest.sh` | **um botão**: `BH_GLES=1` ⇒ `BH_GRAPHICS_API=gles` + `graphics.json` ← `graphics.json.gles` (em `$HOME/.config/bhrecomp/` e `$port_dir/`); sem o botão, **reverte** `api_option=GLES` para `Auto` |

**Aceite medido:** build aarch64 **verde** (`ninja EXIT=0`, 0 erros) → `BodyHarvestRecompiled`
**22.988.496 B**, md5 `fa3e4b59011263de4547191c1c811fe1` (M2 era 22.971.520 B ⇒ +16.976 B);
**311** símbolos GLES + `plume::CreateGLESInterface(...)` presente (calibração `VulkanDevice`=106);
um `ninja` completo posterior (243 alvos) reproduziu o **mesmo md5** (build determinístico).
**Gate OFF:** 3/3 TUs do M5 recompilados sem o define ⇒ **0 string / 0 símbolo GLES**.
**Launcher:** smoketest offline **13/13 OK** (sem `BH_GLES` / `BH_GLES=1` / revert / env solto / sintaxe).
Ferramenta de edits: `apply` 7/7 e `apply` repetido → **SKIP 7/7** (idempotente por sonda).

**Como testar no device:** `BH_GLES=1 ./BodyHarvest.sh` e `grep -E 'backend grafico|api_option|GLES' log.txt`.
Sem imagem **por desenho** (raster = M4): espera-se o abort nomeado
`GLESCommandList::drawInstanced (caminho de raster = M4)`.

**R11 — FECHADO.** **R12 (novo, baixo):** config em `$HOME/.config/bhrecomp/` — mitigado gravando
também em `$port_dir`.

**Próximo passo:** **M3** (descriptor windowing + R8 sem BGRA/16-bit UNORM + R9 sem
`GL_MIRROR_CLAMP_TO_EDGE`) → **M4** (raster: o gate visual) → medição de FPS (fecha o M5) → M6.
Opção mais barata antes disso: empacotar `glesprobe`/`gles_smoke` no cartão e capturar `log.txt`
(primeira validação real do caminho GLES no Mali, independente do port).

---

## M3/pré — SONDA GLES NATIVA NO DEVICE: ENTREGUE (2026-10-18) ✅ (aceite de GPU depende de 1 run)

O passo 4 do plano exige **medir antes de fixar N**. A medição foi feita *fora do port*, com duas
sondas aarch64 independentes — mais barato que instrumentar o raster e útil para o M4/M5 também.

**Entregue:**

| Peça | O que é |
|---|---|
| `evidencias/tools/gles_device_probe.cpp` | sonda EGL/GLES/GBM **dlopen-only** (não linka EGL/GLES): 15 entry points EGL, caminho de display (GBM `/dev/dri/card0` → `eglGetDisplay(gbm_device)` → default), contexto ES3, `GL_VERSION/RENDERER/VENDOR/SL`, inventário de extensões, 15 limites, clear+readback e a rota **GBM window surface** = a rota exata do SDL/KMSDRM |
| `evidencias/tools/gles_egl_stub.c` | stub `libEGL.so.1` **só de link-time** (trava em `stderr`; nunca publicado) |
| `evidencias/tools/m3_build_gles_probe.sh` | build cross + auditoria de `DT_NEEDED`/RPATH + sanity QEMU |
| `evidencias/tools/m3_package_gles_probe.sh` | pacote SD + auditoria que **barra** qualquer `libEGL*` no pacote + `tar.gz` |
| `evidencias/tools/m3_run_gles_probe.sh` | runner do device (gera `gles_probe_log.txt` + resumo) |
| `evidencias/tools/m3_gles_probe_raw.sh` | RAW consolidado reproduzível |
| `evidencias/gles_device_probe_pkg.tar.gz` | **79.398 B**, md5 `26e61c3a75fe5c84e78115f90b7e0316` (reempacotado com a seção `[9]`) |

**Aceite medido (offline + emulação):** probe **45.888 B** md5 `a9d2903e1dffc81cdbb628612fd8def7`
(cresceu de 29.912 B com a seção `[9]`; `DT_NEEDED` só libc/libstdc++ — **sem** EGL/GLES; RPATH
vazio); smoke **186.856 B** md5 `dae329b148fce3a1bdaf5d1cb01ecb34` (**inalterado** — prova de que o
smoke não foi tocado); sob QEMU o blob carrega e **15/15** entry points EGL resolvem, com falha
graciosa em `[2]` (sem GPU) ⇒ sem regressão; pacote **sem** lib de sistema; runner exercitado
ponta-a-ponta sem device — inclusive o **fallback `[1b]`** (`result=FAIL (eglChooseConfig)` →
repete com `--no-gbm` → `result=PASS`) e o resumo do M3. RAW em
`evidencias/m3_gles_probe/raw_offline.txt` (md5 `115adc429e2a4caec79c7734d1f651fa`);
referência de driver ES 3.2 conformante em `raw_host_reference_llvmpipe.txt`
(md5 `9f47cc9a36eecb6ce607d2154333dab8`).

**Achados (RAW):**
- **R6 CONFIRMADO com causa:** o blob não tem SONAME e tem `.dynsym` malformado
  (`ld: .dynsym local symbol at index 3 (>= sh_info of 3)`) ⇒ **regra: dlopen sempre**.
- **Nota do M2 CORRIGIDA:** o blob **exporta** o núcleo EGL inteiro (1175 símbolos `T`, + GBM e
  `eglCreateWindowSurface`/`eglSwapBuffers`). O que era verdade é só a parte do *link*.
  Comentário corrigido com nota datada em `evidencias/m2_gles_s2/gles_target_probe.cpp`
  e `evidencias/tools/staged/gles_target_probe.cpp`.
- **R8 pela metade:** `GL_EXT_texture_format_BGRA8888` **presente** ⇒ "sem BGRA" cai;
  `GL_EXT_texture_norm16` ausente ⇒ só o lado 16-bit UNORM fica.
- **R9 com alternativa:** `GL_EXT_texture_border_clamp` presente.
- **M4 desriscado offline:** `GL_ARM_shader_framebuffer_fetch`,
  `GL_EXT_multisampled_render_to_texture`, `GL_EXT_geometry_shader`, `GL_EXT_buffer_storage`,
  `GL_EXT_texture_storage`, `GL_KHR_debug`, `GL_EXT_disjoint_timer_query` (para medir FPS no M5).
  Blob: `OpenGL ES 3.2 v1.r13p0-01rel0`.

**M3.1 — MEDIÇÃO QUE MUDOU A ESTRATÉGIA DO M3 (2026-10-18):** a sonda ganhou a seção `[9]`, que
**compila e linka shader de verdade** (10 casos). Ela existe porque foi medido que o `glslangValidator`
do host é **permissivo**: devolve `rc=0` para índice dinâmico de sampler **até sem extensão** — logo o
aceite "57/57 ESSL" do M1.3 provava *tradução*, nunca *legalidade ES*.
- O ESSL de produção dos raster PS tem **20 arrays de `sampler2D[8192]`** com índice **variável**
  (`Sampler[GPUTiles._m0[_707].textureIndex]`, 20 call sites; `grep -c 'Sampler\[8192\]'` = 20).
- Num driver ES 3.2 **conformante** (llvmpipe/ES 3.2): `arr8192` **isolada não linka**
  (`error: Too many fragment shader texture samplers`) ⇒ **a forma atual do M1.3 não linka**; o
  orçamento é **multiplicativo** (`2×16=32` linka, `3×16=48` não, `20×16=320` não) ⇒ **a janela de N
  sozinha não basta**; `const_idx_8192` (índice **literal**) **linka** ⇒ o que quebra é o índice
  resolvido em runtime, não o tamanho da array.
- `GL_EXT_gpu_shader5` (que **legaliza** índice dinâmico) está **PRESENTE** nas strings do blob — mas
  legalidade de indexar ≠ orçamento de samplers: o M3 precisa das duas, e são independentes.
- A sonda também ganhou `--no-gbm` (o runner repete sozinho quando o GBM não abre display) e
  `timeout 180` (os casos de 163.840 samplers podem ser pesados no Mali).

**Consequência:** a ordem do M3 passa a ser **(1)** especializar o raster PS por combo de sampler
(sobra **1** array em vez de 20 — o stream de especialização do M1.3 já existe e já está linkado no
binário) → **(2)** janela `N ≤ GL_MAX_TEXTURE_IMAGE_UNITS` + remap no CPU + rebind por draw →
**(3)** `gTMEM[8192]` no mesmo orçamento. Detalhes: bloco "ACHADO DO M3.1" em
`docs/PLANO_BACKEND_GLES_R36S.md` e §12 de `evidencias/evidence_m3_gles_device_probe_20261018.md`.

**Como fechar o aceite (device, ~1 minuto):**
```sh
# copiar evidencias/gles_device_probe_pkg/ (ou o tar.gz) para o SD, ex.: /roms/ports/glesprobe/
# sair do EmulationStation (DRM master) e:
cd /roms/ports/glesprobe && sh run_gles_probe.sh   # anexar gles_probe_log.txt
```
Esperado: `PROBE result=PASS` + `gl_version=OpenGL ES 3.2 ...` + `[smoke] ===== 0 falha(s) =====`
+ `display_path=eglGetDisplay(gbm_device)`. Com isso, os valores de `GL_MAX_TEXTURE_IMAGE_UNITS`
e `MAX_COMBINED_*` deixam de ser estimativa e definem o **N** da janela de texturas do M3 — e a
tabela `PROBE m3_shader_measurement` (seção `[9]`) diz, **no compilador do Mali**, qual estratégia
do M3 é viável.

**Próximo passo (ordem atual):** rodar a sonda no device (fecha M2 em hardware + dá o N **e** a
medição de sampler array do M3) → **M3** (especializar por combo + windowing; R8 agora só 16-bit
UNORM) → **M4** (raster: o gate visual) → medição de FPS (fecha M5) → M6.

**M3.1b — MEDIÇÃO NO ARTEFATO REAL (2026-10-18, offline, driver ES 3.2 conformante):** a sonda ganhou
a seção **`[9c]`**, que compila e **LINKA pares VS+PS de verdade** (`--shader-dir DIR` /
`PROBE_SHADER_DIR`, arquivos `shader_cases/*.vert.essl` + `*.frag.essl`). Motivo: o erro de orçamento
de samplers só aparece no **LINK** — compilar arquivo isolado (o aceite antigo) nunca o vê.
- O caso é gerado do ESSL de produção (`RasterPSDynamic` + `RasterVSDynamic`) por
  `evidencias/tools/m3_make_shader_cases.sh` + `evidencias/tools/m3_essl_specialize.py` (novos), com
  prova mecânica de que **o corpo do shader não muda** (normalizando nomes de sampler e janela, o
  diff é **0**).
- **A medição reprovou DOIS pontos do artefato do M1.1/M1.3, antes de chegar no M3:**
  **D1**: 6 dos 12 ESSL usam `layout(location = 0, index = 1) out` (2 alvos, blender do RDP) sem
  habilitar `GL_EXT_blend_func_extended` → driver recusa com `error: index layout qualifier requires
  EXT_blend_func_extended`. **Corrigido no sanitizador de produção** (`m1_1_emit_glsl_es.py`, ação
  `blend-func-extended-required`); falta regenerar/revalidar os 57 ESSL.
  **D2**: o PS lê `location = 2` como `flat in` e o VS não declara `flat` no `out` da mesma location
  → o **link do par** recusa. Correção é coerência entre estágios (protótipo `--flat-from-ps`).
- **A REGRA DO ORÇAMENTO FICOU CORRIGIDA** (era lida como `2 × N`): medido no llvmpipe (32 unidades):
  `prod_asis` (20 × `[8192]`) **FALHA**; `2 × [8192]`, `2 × [32]`, `2 × [16]` **FALHAM**;
  `2 × [15]` **linka**; `2 × [8]`/`2 × [4]` linkam. Isto é
  `n_arrays_com_janela × N + n_samplers_escalares ≤ GL_MAX_TEXTURE_IMAGE_UNITS` — e o shader real tem
  **2 arrays** (`gTextures`, `gTMEM`) **+ 1 escalar** (`gBackgroundDepth`), logo no Mali o
  `N = (unidades − 1) / 2` (com o número real de unidades vindo da seção `[6]`).
- **R13 (novo, ALTO):** `GL_EXT_blend_func_extended` — o llvmpipe **tem**; as strings do blob Mali
  **não citam** (indício). A extensão entrou no inventário da sonda ⇒ o run no device responde, e a
  seção `[9c]` mostra o veredito de **compilação do PS real no Mali**. Se o Mali não tiver, o caminho
  do **blender do RDP muda** (arquitetura, não shader) — pergunta antecipada para o M4.
- **Pacote atualizado** (leva `shader_cases/`, 7 pares): sonda `5bda42acb705bcc11df35e05dfd78c0f`
  (61.328 B), smoke **inalterado** `dae329b148fce3a1bdaf5d1cb01ecb34`, runner
  `3def8b96b3292106a5ea6ce4b4963933`, README `86761024b863bfb2ea7f8cde3082f96d`, tarball
  `2f1bbd1c55b0870214d824f631ac36fa` (250.201 B). RAW novos:
  `m3_gles_probe/raw_host_prod_essl_linktest.txt` (`43101ad16e73b795635fa121bff8440a`) e
  `raw_offline.txt` regenerado (`7d22d7d0b1f0eb8d7687c696ce30f47f`; seção `[9]` **sem regressão**:
  0 linhas de diferença nas 10 medições anteriores). Tudo em
  `evidencias/evidence_m3_gles_device_probe_20261018.md` §13.

**Próximo passo (ordem atual, REVISTA pelo M3.1b):** rodar a sonda no device (**~1 min**) — o MESMO
run agora fecha o M2 **e** responde 4 coisas novas: o **N** real do Mali (`[6]`+`[9]`), a viabilidade
da janela com a regra corrigida, se o **ESSL de produção** compila/linka no Mali (`[9c]`) e se existe
`GL_EXT_blend_func_extended` (**R13**) → depois **M3** (especializar por combo + janela contando as 2
arrays e o escalar; R8 só 16-bit UNORM) → **M4** → medição de FPS (M5) → M6.

