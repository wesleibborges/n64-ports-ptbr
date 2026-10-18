# Body Harvest — Caminho de Decomp → Recomp (projeto iniciado)

## Status atual (2026-10-16)

| Etapa | Status | Resultado |
|---|---|---|
| Decomp | 84,53% matched / 99,97% decompilado | ✅ build byte-perfect |
| ELF com símbolos | ✅ `recomp/bh.us.elf` | ✅ |
| Recompilação N64Recomp | 7.117 funções | ✅ |
| **Runtime (em desenvolvimento)** | **projeto criado em `/root/bhrecomp` (WSL), baseado no BanjoRecomp/N64ModernRuntime** | ⚙️ |
| — Análise de ucodes RSP | gfx = **F3DEX 1.21** (suportado pelo RT64); áudio = **ucode custom da DMA Design** (derivado de L3DEX 1.21, usa regs DPC como temporizador e CFC2/CTC2) | ✅ |
| — Patch RSPRecomp #1 | `mfc0/mtc0` para regs DPC (8–15): leitura→0, escrita→ignorada | ✅ aplicado |
| — Patch RSPRecomp #2 | codegen para `cfc2/ctc2` (o runtime já tinha VCO/VCC/VCE implementados na VU de `librecomp/rsp_vu.hpp`) | ✅ aplicado |
| — **Áudio recompilado (fix 2026-10-16)** | bh_aspMain.toml corrigido: text_size=0x1018 (rspboot faz DMA hardcoded de 0xF80 bytes -> apenas blob[0..0xF80] executa em IMEM 0x1080..0x1FFF) + extra_indirect_branch_targets com 8 endereços IMEM ABSOLUTOS da tabela de dispatch em DMEM 0x10 (0x1118 0x1470 0x11DC 0x1B38 0x1214 0x187C 0x1254 0x12D0, extraída do ucode_data @ ROM 0x3FC60). Patch no RSPRecomp mascarando labels/alvos com rsp_mem_mask (evita wrap de branches >= 0x2000). | ✅ |
| — Projeto BodyHarvestRecomp | CMake adaptado, main.cpp BH, recomp_data_api.cpp (modelo Banjo), ordem de link recompinput->recompui, set_program_id u8string | ✅ linkado |


### Descobertas técnicas (ucodes)

- A ROM guarda os ucodes **sem as strings de versão**; as strings de identificação
  ("RSP Gfx ucode F3DEX 1.21" / "L3DEX 1.21") vivem no `ucode_data` (`src.us/core/rsp_data.c`).
- O blob rotulado "audioucode" (ROM 0x2FF10, 0x1E10 bytes) é um **ucode de áudio customizado
  da DMA Design derivado do L3DEX** (string de identidade residual no `ucode_data` em 0x401D0),
  que usa os registradores **DPC (8–15) do cop0 do RSP** como fonte de tempo/estado — legal no
  hardware (o RSP acessa DPC, conforme implementação de referência do Ares), aproximado como
  leitura=0/escrita ignorada no runtime recompilado.
- Hash do port (XXH3-64 da ROM US, como valida o librecomp): **0x9949AA9BC66F33CB**.


## O que existe nesta pasta

- `recomp/bh.us.elf` — ELF final do build decomp, com todos os símbolos (entrada para o N64Recomp).
- `recomp/bh_recomp_out.tar.gz` — saída completa do N64Recomp: `RecompiledFuncs/` (C gerado),
  `bodyharvest.us.toml` (config) e `relocatable_sections.txt`.
- Patch aplicado ao N64Recomp (em `C:\e-core\n64patch\`): nova chave de TOML
  `use_lookup_for_all_function_calls` — necessária porque o ELF final do decomp não carrega
  tabelas de relocação e o Body Harvest faz jal entre overlays (`.overlay_level_*` → `.core`).

## Como reproduzir

**Opção A — Docker (recomendada, validada em 2026-10-16):** o repositório tem Dockerfile oficial
e o Docker CE está instalado e funcionando neste WSL (systemd ativo):

```bash
git clone --depth 1 https://github.com/jaytheham/body-harvest-decompilation /root/bh
cp "Body Harvest (USA).z64" /root/bh/baserom.us.z64   # SHA-1 bbb6666f5014a473747ee4145f036d9fb25d7348
cd /root/bh
docker build -q -t bh-local .                          # imagem ubuntu:22.04 + toolchain (278 MB) ✓ validado
docker run --rm -v /root/bh:/bh bh-local bash -c "make --jobs && tail -1 /tmp/inner.log"
# -> build/bh.us.z64: OK (byte-perfect) — dentro do container o gcc-mips-linux-gnu instala sem conflito
```

Vantagens: ambiente idêntico ao dos desenvolvedores do decomp, sem poluir o host, sem conflito
gcc-mips × gcc-multilib (o packages.txt da imagem não inclui gcc-multilib).

**Opção B — nativo no WSL (também validada):** toolchain parcial via `dpkg -x` (binutils-mips
2.40 em `/root/tools/gnu-mips` + wrappers em `/usr/local/bin`, sem `apt install`), `pip3 install
cmake ninja -r requirements.txt`, `make extract && make -j` (com `HOSTCC=fake_cc` para pular o
lint -m32, hoje desnecessário: clang/gcc-multilib instalados após o reparo do apt). DCC usa o
IDO 5.3 recompilado (tools/ido5.3_recomp), que compila todas as unidades com sucesso.

Depois do build, gerar o código do port: `/root/n64recomp/build-cmake/N64Recomp bodyharvest.us.toml`
(→ `RecompiledFuncs/`). O patch do N64Recomp está em `recomp/n64patch/`.

## O que falta para o port jogável (roadmap)

1. **Runtime**: adotar o modelo do [Starship (Star Fox 64 Recompiled)](https://github.com/HarbourMasters/Starship) /
   [N64ModernRuntime](https://github.com/Wiseguy/N64ModernRuntime): vídeo (RT64 ou backend
   GL leve), áudio, input, agendador de threads/eventos do libultra.
2. **RSP**: rodar o `RSPRecomp` para os microcódigos do jogo (o decomp tem `asm/data/rsp`);
   Body Harvest usa ucode S2DEX/F3DEX — mapear para o runtime.
3. **Eventos/patches**: registrar eventos de troca de overlay e hooks para o load das
   seções (o jogo troca `overlay_gameplay` e `overlay_level` em runtime).
4. **Empacotamento PortMaster**: mesmo formato usado no `Banjo-Recompiled (BR)` (port.json,
   launcher `.sh`, gptk).
5. **Tradução PT-BR**: após o runtime estável, portar o texto (a ROM PAL traduzida pode
   servir de referência de tradução; o texto do BH é RNC-comprimido — ferramentas já no decomp).

## Evidências

- `evidencias/evidence_bodyharvest_port.md` — log RAW do build e da recompilação.


## Estrutura (formato PortMaster: pasta do projeto + script .sh)

```
Body Harvest (Recomp)/
├── BodyHarvest.sh              <- launcher PortMaster (640x480, panvk/llvmpipe)
├── BodyHarvestRecompiled       <- binário (21 MB, build com aspMain corrigido)
├── assets/                     <- assets de UI (fonts, svgs)
├── shaders/                    <- shaders runtime
├── gamedata/
│   ├── bodyharvest.us.toml     <- toml do jogo (rom base)
│   └── bh_aspMain.toml         <- toml do aspMain com fix dos 8 endereços absolutos
├── general.json / graphics.json / sound.json / recompcontrollerdb.txt
├── Body Harvest (USA)/         <- ROM (não redistribuir)
├── recomp/                     <- artefatos de recomp (bh_recomp_out, n64patch)
├── evidencias/                 <- logs, screenshots, evidência do fix aspMain
└── README_PORT.md              <- este arquivo
```

## Status do build (2026-10-16, sessao recovery)

- **BodyHarvestRecompiled compila e roda no Linux/WSL.** Binario 21.5MB (build-cmake, ninja).
- Fix de audio ucode: bh_aspMain.toml com extra_indirect_branch_targets ABSOLUTOS
  (0x1118 0x1470 0x11DC 0x1B38 0x1214 0x187C 0x1254 0x12D0 — tabela de dispatch em
  ucode_data @ ROM 0x3FC60, DMEM 0x10; rsp_recomp.cpp com BH-patch de mascaramento).
  Erros 'label used but not defined' eliminados; link OK.
- Janela de teste limitada a **640x480** (SDL_CreateWindow em src/main/main.cpp) —
  resolucao nativa do R36S, conforme decisao de otimizacao.
- Validacao WSL: binario executado; UI/RmlUi inicializada, fonts carregadas,
  RT64 inicializado sobre **llvmpipe (Vulkan 1.3.255 software)**. Sem falhas no boot.
- Proximo passo (hardware): testar no R36S com panvk experimental
  (PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1, Mesa >= 24.x com panvk Bifrost).
- Persistencia: binario + TOML + aspMain.cpp gerado + main.cpp copiados para
  /mnt/c/e-core/ (bh_aspMain.toml, bh_aspMain_generated.cpp, bh_main.cpp,
  BodyHarvestRecompiled, bh_run_test_640x480.log, bh_shot_640x480.png).
- Alternativa GLideN64 descartada (glitches de colisao/graficos conhecidos no BH;
  plugin mupen64 Android que funciona ficou nao identificado).


## Build AARCH64 concluido (2026-10-17)

- **BodyHarvestRecompiled ARM aarch64** (19,7 MB, ELF aarch64 pie, md5 dc33bc4c...) na pasta do port.
- SDL2 2.30.3 arm64 bundled em  (o device tem 2.0.20; o port usa SDL_GetWindowSizeInPixels).
- BodyHarvest.sh: PortMaster control.txt + LD_LIBRARY_PATH libs/ + fallback lavapipe.
- Sysroot arm64 manual: /root/sysroot64 (WSL), scripts: _fix_sysroot_links.sh, _link_all3.sh.
- Toolchain file: /root/bhrecomp/Toolchain-aarch64.cmake; guia: /root/bhrecomp/BUILD_AARCH64.md.
- Docker checkpoint: bh-checkpoint-03-aarch64:20261017.
- Proximo passo: copiar a pasta para o R36S (via SD) e rodar ./BodyHarvest.sh.

## GTK removido do binario aarch64 (2026-10-17) — patch ELF v2

O binario nao depende mais de GTK/GDK/GLib. O `libgdk-3.so.0` do dArkOS traz
`libwayland-egl.so.1` sem o simbolo `wl_egl_window_destroy`, o que abortava o
carregamento mesmo sem o codigo GTK ser chamado. Solucao definitiva:

| Item | Detalhe |
| :--- | :--- |
| Patcher | `_patch_elf_v2.py` — edicao in-place do `.dynamic`/`.dynstr` (SEM patchelf) |
| NEEDED | `libgtk-3.so.0` -> `libgtkshim.so`; gdk/gobject/glib neutralizadas (`tag 0x6FFFFF00`) |
| Versionamento | `DT_VERSYM`/`DT_VERNEED`/`DT_VERNEEDNUM` neutralizadas (`tag 0x6FFFFF01`) |
| Binding | `BIND_NOW` **preservado** (`DT_FLAGS=0x8`, `FLAGS_1=NOW|PIE`) |
| Shim | `libs/libgtkshim.so` (aarch64) — 39 stubs (`gtk_/gdk_/g_`), incluido via LD_LIBRARY_PATH do `BodyHarvest.sh` |

**Por que BIND_NOW e obrigatorio:** o binario foi linkado com `-z now`, entao o
`PT_GNU_RELRO` cobre `.data.rel.ro` **e** `.got` (`.got=0x1033ac8`,
`DT_PLTGOT=0x1033ac8`). Com binding lazy, o `_dl_runtime_resolve` tenta gravar no
GOT ja protegido read-only e o processo morre com SIGSEGV dentro do
`ld-linux-aarch64.so.1` — antes de qualquer codigo do jogo. Foi exatamente o bug
investigado com `gdb-multiarch` (`_start` -> `_dl_runtime_resolve` -> SIGSEGV).

**Comportamento do shim:** `gtk_init_check()` retorna FALSE, entao o launcher usa
a UI interna (RmlUi) e nao abre file dialog GTK. `g_free()` chama `free()` real;
`g_slist_*`/`g_signal_*` retornam vazio; `g_type_check_instance_cast()` devolve a
instancia.

**Verificacao:** sob `qemu-aarch64-static` o binario inicializa, chega ao `main()`
e para apenas em `Failed to create window: Vulkan ... dummy` (sem Vulkan no driver
dummy) — ou seja, loader/relocacao/shims estao corretos. Evidencia:
`evidencias/evidence_gtk_patch_v2_20261017_162606.md`.

**Teste no device:** copiar a pasta para o SD e rodar `BodyHarvest.sh`; o `log.txt`
deve mostrar RT64 inicializando sobre llvmpipe (3-8 fps nesta GPU/kernel 4.4).

---

## SDL2 exigido (cross-build proprio)

O SDL do dArkOS (2.0.20) foi compilado **sem** `--enable-video-vulkan`, e o SDL
bundled original tambem nao tinha `kmsdrm` nem `vulkan`. Por isso o port traz um
SDL2 2.30.9 compilado com:

```
Video drivers : dummy offscreen kmsdrm(dynamic) opengl opengl_es1 opengl_es2 vulkan
Audio drivers : disk dummy oss alsa(dynamic)
```

| Item | Detalhe |
| :--- | :--- |
| Build script | `C:\e-core\_build_sdl2_aarch64.sh` (WSL, `aarch64-linux-gnu-gcc`, prefix `/opt/sdl2-aarch64`) |
| Dependencias de build | `libdrm-dev:arm64`, `libgbm-dev:arm64`, `libasound2-dev:arm64`, `libudev-dev:arm64` (extraido a mao em `/opt/arm64-stage`) |
| Artefato | `libs/libSDL2-2.0.so.0.3000.9` + copia `libs/libSDL2-2.0.so.0` (FAT nao guarda symlink) |
| dlopen em runtime | `libdrm.so.2`, `libgbm.so.1`, `libvulkan.so.1`, `libasound.so.2`, `libudev.so.1` |

**Requisito do KMSDRM:** o SDL usa `VK_KHR_display` (`vkCreateDisplayPlaneSurfaceKHR`)
para apresentar. lavapipe/llvmpipe **nao expoe** essa extensao (so xcb/xlib/wayland),
entao o ICD precisa suportar display (ex.: blob Mali/panvk) ou o caminho de
apresentacao precisa ser trocado (patch no RT64). O `BodyHarvest.sh` roda `vkprobe`
por ICD e registra `VK_KHR_display: SIM/NAO` no `log.txt` antes de iniciar o jogo.

## Backend OpenGL ES 3.2 (M5, 2026-10-18) — botao `BH_GLES`

Como **nenhum** Vulkan do firmware apresenta em KMSDRM (nenhum ICD expoe `VK_KHR_display`), o
caminho com aceleracao de hardware no R36S e' **OpenGL ES 3.2 pelo blob Mali** (EGL/GBM), que o
SDL2 empacotado sabe usar (`opengl_es1`/`opengl_es2` aparecem na lista de drivers de video dele).

Ligar o backend GLES do RT64 com **um unico botao**:

```sh
BH_GLES=1 ./BodyHarvest.sh          # OpenGL ES 3.2
./BodyHarvest.sh                    # Vulkan/auto (padrao); reverte config de GLES se houver
```

O `BH_GLES=1` escreve as **duas** pontas que precisam concordar (liga-las separadamente falha):

1. `BH_GRAPHICS_API=gles` -> a janela SDL nasce com `SDL_WINDOW_OPENGL` (`src/main/main.cpp`;
   o SDL2 aceita so' uma entre OPENGL/VULKAN/METAL por janela, e a janela e' criada **antes**
   de o RT64 ler qualquer configuracao);
2. `graphics.json` <- template `graphics.json.gles` (`api_option: "GLES"`), gravado em
   `$HOME/.config/bhrecomp/` (onde o recompui realmente le; `program_id = "bhrecomp"`) **e** na
   pasta do port. O log mostra o valor lido de volta:
   `api_option[$HOME/.config/bhrecomp/graphics.json] = "api_option": "GLES"`.

Sem `BH_GLES=1`, se algum `graphics.json` tiver `"GLES"` o launcher **reverte** para
`graphics.json.auto` (janela Vulkan + `api_option=GLES` seria falha garantida).

**Status:** selecao de API entregue e verificada (build aarch64 verde; proximo gate e' o raster,
M4 — ate' la' o draw aborta de proposito com `GLESCommandList::drawInstanced (caminho de raster =
M4)`). Detalhes: `evidencias/evidence_m5_gles_api_select_20261018.md` e
`docs/PLANO_BACKEND_GLES_R36S.md`.

---

## Sonda GLES no R36S (M3/pre, 2026-10-18) — validar o driver SEM abrir o port

Antes de escrever descriptors/raster, ha' um teste de **1 minuto** que responde tudo o que se
supunha sobre o driver: `evidencias/gles_device_probe_pkg/` (ou o `.tar.gz`). Nao precisa do port,
nem de SDL, nem da pasta `libs/` — as sondas resolvem EGL/GLES por `dlopen` em runtime.

```sh
# copiar a pasta para o SD (ex.: /roms/ports/glesprobe/), sair do EmulationStation (DRM master) e:
cd /roms/ports/glesprobe
sh run_gles_probe.sh          # gera gles_probe_log.txt -- anexar no ticket/evidencia
```

O que ele mede, direto no Mali-G31:

| Sonda | Mede |
|---|---|
| `gles_device_probe_aarch64` | 15 entry points EGL, caminho de display (GBM/`/dev/dri/card0`), contexto **ES 3.2**, `GL_VERSION/RENDERER/VENDOR`, extensoes (inclui `GL_EXT_gpu_shader5` e **`GL_EXT_blend_func_extended`**), 15 limites, clear+readback, a rota **GBM window surface** (= a rota exata do SDL/KMSDRM), a **secao `[9]`: compila/linka 10 shaders sinteticos** e a **secao `[9c]`: compila/linka os 7 pares VS+PS REAIS** de `shader_cases/` (a MEDICAO do M3 sobre o ESSL de producao) |
| `gles_smoke_aarch64` | o backend `plume_gles` (15/15 no host) rodando sobre o driver REAL |

Se o caminho GBM nao abrir display, o runner **repete sozinho** com `--no-gbm`
(`EGL_DEFAULT_DISPLAY` puro) e registra um bloco `[1b]` no log.

Esperado: `PROBE result=PASS`, `gl_version=OpenGL ES 3.2 ...` e `[smoke] ===== 0 falha(s) =====`.
Alem disso, a tabela `PROBE m3_shader_measurement` diz se o compilador do Mali aceita a forma de
shader que o port gera hoje (20 arrays de `sampler2D[8192]` com indice variavel) e qual estrategia
do M3 e' viavel — no host, um driver ES 3.2 conformante **recusa** essa forma no *link*
(`Too many fragment shader texture samplers`). A tabela `PROBE file_shader_measurement` faz o mesmo
sobre o **ESSL de producao de verdade** (os 7 casos `prod_*`, gerados por
`evidencias/tools/m3_make_shader_cases.sh`).

**Já medido no PC, no artefato real (llvmpipe/ES 3.2, §13 da evidencia):** `prod_asis` **compila e
falha no link**; colapsando os 18 combos de sampler em 1 array por imagem, `2x[16]` **ainda falha** e
`2x[15]` linka ⇒ a regra e' `n_arrays_com_janela x N + samplers_escalares <= unidades` (o shader real
tem 2 arrays + 1 escalar). O run no device da' o numero de unidades do Mali e o veredito de
compilacao dos mesmos casos no compilador do Mali.

**Cuidado:** nenhum `libEGL.so*` acompanha o pacote, e nao deve: no device `libEGL.so.1 ->
libMali.so` (o blob ARM de 40,8 MB, que **nao** e' linkavel — so' `dlopen`). Se aparecer a mensagem
`*** AVISO: libEGL STUB DE LINK-TIME foi carregada. ***`, o problema e' `LD_LIBRARY_PATH`/
empacotamento, nao o backend.

Detalhes, RAW e achados (o blob **exporta** o nucleo EGL inteiro; `GL_ARM_shader_framebuffer_fetch`
e `GL_EXT_multisampled_render_to_texture` existem; **§12: a forma de ESSL do M1.3 nao linka** num
driver conformante e a estrategia do M3 foi revista por medicao; **§13: o link do par VS+PS REAL
reprovou 2 defeitos do artefato do M1.1/M1.3 — dual-source sem `#extension GL_EXT_blend_func_extended`
(corrigido no sanitizador) e `flat` assimetrico — e fixou a regra exata do N; `GL_EXT_blend_func_extended`
virou o risco **R13** porque as strings do blob Mali nao o citam**):
`evidencias/evidence_m3_gles_device_probe_20261018.md`.

