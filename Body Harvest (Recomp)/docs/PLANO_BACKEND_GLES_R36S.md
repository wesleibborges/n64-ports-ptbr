# PLANO — Backend OpenGL ES (HW) para o RT64 no R36S

Status: **aprovado (decisão B)** · Data: 2026-10-17 · atualizado 2026-10-18
Decisão (2026-10-18): **rota B mantida** (backend `plume_gles` no RT64). O **GLideN64 fica
apenas como oráculo de validação** visual (golden frames no PC), nunca como implementação —
motivos de arquitetura (HLE-GBI × plugin LLE de mupen64plus) e licença (GPL-2 × MIT) estão
em `evidence_m1_2_gles_channel_20261018.md` §0 e na análise da sessão anterior.
Evidências: `evidencias/evidence_firmware_vulkan_audit_20261017.md`,
`evidencias/evidence_gles_backend_recon_20261017.md`,
`evidencias/evidence_m1_restore_dx_blobs_20261018.md`,
`evidencias/evidence_m1_layout_matrix_20261018.md` (+ relatórios
`m1_matrix_dx_vs_gl_20261018.md`, `m1_layout_diff_dx_gl_20261018.md` e patches em
`m1_patches_headers/`),
`evidencias/evidence_m1_padding_applied_20261018.md`,
`evidencias/evidence_m1_1_glsl_es_shaders_20261018.md`,
`evidencias/evidence_m1_2_gles_channel_20261018.md`,
`evidencias/evidence_m1_3_link_and_stage1_20261018.md`
`evidencias/evidence_m2_gles_gate_20261018.md`
`evidencias/evidence_m5_gles_api_select_20261018.md`

## Por que GLES

Nenhum Vulkan do firmware apresenta em KMSDRM (nenhum ICD expoe `VK_KHR_display`; o blob Mali
tem Vulkan 1.0.x **sem WSI**). O único caminho com **aceleração de hardware** no R36S é
**OpenGL ES 3.2 pelo blob ARM** (EGL + GBM), que o SDL2 KMSDRM sabe usar
(`SDL_VIDEODRIVER=kmsdrm` + `SDL_GL_*`).

## Arquitetura alvo

```
BodyHarvestRecompiled (librecomp + recompui)
        |
        +-- RT64  (RDP/renderer)
              |
              +-- RHI "Plume"  (~103 metodos)  <-- NOVO BACKEND: plume_gles
              |     Vulkan | D3D12 | Metal | --> GLES <--
              |
              +-- shaders: HLSL -> DXC -> SPIR-V -> { MSL (Apple) | GLSL ES 3.20 (novo) }
        |
        +-- SDL2 2.30.9 (bundled, com KMSDRM+GLES)  -> EGL/GBM -> blob Mali -> /dev/dri
```

Pontos de extensão (todos já existentes, vereados no recon):
- `UserConfiguration::GraphicsAPI` + `switch` em `src/hle/rt64_application.cpp` (~157-188)
- macro `CREATE_SHADER_INPUTS` em `src/render/rt64_shader_library.cpp` (152-175)
- pipeline de shader em `lib/rt64/CMakeLists.txt` (`build_shader_spirv_impl`, 116-155)
- `RenderDeviceCapabilities` (17 flags) em `contrib/plume/plume_render_interface_types.h:1764`

## Marcos

### M0 — Recon offline ✅ CONCLUÍDO
Entregas: seam identificado; capacidades GLES do blob medidas; sysroot/headers GLES 3.2
confirmados; `glesprobe` (aarch64) criado, compilado e validado sob QEMU (contexto ES 3.2 real,
16/18 extensões úteis, swap OK).

### M1 — Pipeline de shaders GLSL ES (build-time)
- novo valor `RenderShaderFormat::GLSL_ES`
- novo ramo em `CREATE_SHADER_INPUTS` (Linux/aarch64) selecionando blobs `BlobGLSLES`
- novo passo no CMake espelhando `spirv_cross_msl`: `.spv` -> GLSL ES 3.20
  (usar o `spirv-cross` já vendorizado: `CompilerGLSL` com `set_es(true)`/`version=320`)
- **Aceite:** o build aarch64 do RT64 gera TODOS os arrays `*BlobGLSLES` (mesma quantidade de
  entradas `CREATE_SHADER_INPUTS`) e o GLSL ES gerado compila (glslangValidator com `-DES 320`,
  ou compilação no device via `glShaderSource`).

#### M1 — RESULTADO DO BLOQUEIO DE LAYOUT ✅ RESOLVIDO (2026-10-18)

Medição autoritativa (58 shaders × DX/GL, `spirv-val` + `spirv-cross --es --version 320` +
`glslangValidator`), vide `evidence_m1_layout_matrix_20261018.md`:

- **Causa raiz**: `-fvk-use-dx-layout` posiciona `vec3` em offsets não múltiplos de 16
  (`RDPParams.keyScale`@92, `GPUTile.textureDimensions`@36, `RSPViewport.translate`@12,
  `RasterParams.padding`@4). Isso é legal em D3D/Vulkan-DX mas **não é expressável em std430**.
- **Efeito**: 10 blobs não convertem para GLSL ES; 13 são **SPIR-V Vulkan inválido** (`spirv-val`).
- **Decisão**: **opção (b)** — manter UM único conjunto de blobs e o layout C++ atual, inserindo
  **padding explícito em 6 headers duais** (`rt64_rdp_params.h`, `rt64_gpu_tile.h`,
  `rt64_rsp_viewport.h`, `rt64_rsp_lookat.h`, `rt64_rsp_light.h`, `rt64_raster_params.h`).
  Rejeitada a opção (a) `-fvk-use-gl-layout`, que exigiria **dois layouts no C++ host**.
- **Prova**: com o patch de padding e mantendo `-fvk-use-dx-layout`, **12/12 shaders testados
  (incluindo os 10 que falhavam) passam em `spirv-val` e `spirv-cross`**. Patch pronto em
  `evidencias/m1_patches_headers/layout_padding.patch`.
- **Regras de padding** (empíricas): (1) todo `vec3` em offset múltiplo de 16; (2) tamanho da
  struct múltiplo de 16; (3) **o padding deve ser escalar** (um `uint3` de padding exigiria
  alinhamento 16); (4) `vec2` exige alinhamento 8.

#### M1 — PADDING APLICADO NA ÁRVORE REAL + 58 BLOBS REGENERADOS ✅ (2026-10-18)

Vide `evidence_m1_padding_applied_20261018.md`. Resumo dos fatos verificados:

- Patch aplicado em `lib/rt64/src/shared/` com md5 pós-aplicação **idêntico** ao artefato
  aprovado no PoC (6/6) e backup dos originais em `/root/bhrecomp/m1_apply_20261018/`.
- **58 blobs regenerados** executando os comandos DXC exatos do `build.ninja`. Necessário
  porque os `add_custom_command` do DXC declaram **apenas `DEPENDS ${FILENAME}`** (o `.hlsl`)
  — os headers não entram nas dependências do ninja.
- **Apenas 13 blobs mudaram** (exatamente o conjunto antes inválido); **45 permaneceram
  md5-idênticos** → raio de impacto mínimo.
- **Aceite atingido:** `spirv-val` falhas **13 → 0**; `spirv-cross --es --version 320`
  falhas **10 → 0**. `m1_offset_compare.py`: **103 structs, 0 divergências** vs std430
  (`RDPParams.keyScale@96`, stride 144; `RSPLight` stride 64; `RasterParams.screenScale@32`;
  `GPUTile.textureDimensions@48`; `RSPViewport.translate@16`).
- Bloqueio **pré-existente e ortogonal** resolvido: sysroot aarch64 com **headers SDL2 2.0.20 e
  biblioteca SDL2 2.30.3** (`SDL_GetWindowSizeInPixels`, `SDL_JoystickPath`,
  `SDL_GetJoystickGUIDInfo`, `SDL_HINT_WINDOWS_DPI_AWARENESS` não declarados). Correção de raiz:
  instalar no sysroot os headers públicos do SDL 2.30.3 (`/root/SDL2-2.30.3/include`) — ver
  seções 3 e 8 da evidência.
- **Rebuild aarch64 CONCLUÍDO**: `ninja: no work to do`, binário ELF aarch64
  md5 `13b708c21762bff9e183c494512e5776` (19.770.744 bytes), com os 58 blobs com padding
  comprovadamente embutidos (cadeia `.spv` → `.spirv.c` → `.o` → binário) e sem drift no
  agregado md5 dos blobs. Artefato em
  `BodyHarvestRecompiled.m1_padding_20261018` (o binário anterior foi preservado).
- Pendente nesta etapa: reconstrução do `build-cmake` (x86_64) com os novos headers, se um
  binário x86_64 for necessário; e correção do `DEPENDS` no CMake (bug latente).

#### M1.1 — Lacunas de perfil GLES ✅ CONCLUÍDO (2026-10-18)

Vide `evidencias/evidence_m1_1_glsl_es_shaders_20261018.md`. Fatos verificados:

- **Baseline corrigido**: as "13 falhas" eram **10 reais + 3 falsos-positivos**. O validador
  derivava o estágio por regex de nome de arquivo e classificava os 3 `RasterVS*` (vertex) como
  fragment → o erro de `precision` era inexistente. Provado: `glslangValidator -S vert` → rc=0
  nos 3.
- **4 causas-raiz** (não 5 supostas): `usampler1D` (8 shaders), extensão NV espúria (6),
  `noperspective` (1), image format qualifier (1).
- **Correção na fonte**, gated por `-D HLSL_GLES` (não por pós-processamento): `TMEMTexture`
  (`Texture1D<uint>` → `Texture2D<uint>`), `tmemLoadTMEM(...)`, `NonUniformResourceIndex`
  identidade. Prova: o output **cru** do `spirv-cross --es` já não contém `usampler1D` nem
  `GL_NV_gpu_shader5`.
- **Aceite atingido: 57/57** shaders compilam em `glslangValidator` (`#version 320 es`),
  **0 falhas** (antes: 10).
- **`DebugPS` excluído por design**: probe prova que ESSL 3.20 rejeita `readonly image2D` **com
  e sem** format qualifier; é o shader de debug do caminho RT (inexistente em GLES).
- **NÃO-REGRESSO provado**: 58/58 blobs recompilados **sem** `HLSL_GLES` são **md5-idênticos**
  → o binário do M1 permanece válido e **nenhum rebuild foi necessário**.
- Sanitizador do codegen ES (3 ações): `nv-ext-stripped` (guarda defensiva),
  `noperspective-removed` (1), `precision-mediump->highp` (28 — `mediump` = fp16 no Mali-G31
  degradaria coordenadas de textura/depth).

**Achados de arquitetura que redefinem o escopo de M1.2/M2/M3** (medidos; §8 da evidência):

1. `gTextures[8192]`/`gTMEM[8192]` **são válidos em ESSL 320** (inclusive a indexação dinâmica,
   provado por probe) → o bloqueio **não é sintaxe, é binding/driver**: ESSL não tem descriptor
   indexing e o Mali-G31 expõe ~16 unidades de textura por estágio.
2. O maior GLSL ES tem **704.897 bytes** (conjunto: 3,47 MB de texto vs 1,57 MB de SPIR-V).
   GLES compila shader em **runtime** → o ubershader **não pode** ser compilado como está no
   device; exige especialização em runtime (mecanismo já existente no RT64 via `re-spirv`).

#### M1.2 — Canal GLES no build ✅ CONCLUÍDO (2026-10-18)

Vide `evidencias/evidence_m1_2_gles_channel_20261018.md`. Fatos verificados:

- **Enum**: `RenderShaderFormat::GLSL_ES` **anexado ao fim** do enum do Plume (preserva
  DXIL=1/SPIRV=2/METAL=3 — sem quebra de ABI/ordenação).
- **`CREATE_SHADER_INPUTS` com 4 blobs** (`DXIL, SPIRV, MSL, GLSLES`): os 32 call sites passam
  `<X>BlobGLSLES`; o 4º argumento é **ignorado** nos builds sem o canal
  (gate `#ifdef RT64_GLSL_ES_BLOBS`), portanto Windows/macOS/Linux-sem-canal não mudam.
- **CMake**: `option(RT64_GLSL_ES_SHADERS OFF)` + `build_shader_glsl_es_impl`
  (DXC `+ -D HLSL_GLES` → `<x>.glsl_es.spv` → `file_to_c` → `<X>BlobGLSLES`) e hooks em
  `build_shader()`/`build_shader_spirv()` (cobrem os 58 shaders, inclusive os do frontend).
- **`DEPENDS` corrigido (bug latente do M1)**: `DEPENDS ${FILENAME}` → `+ ${RT64_SHADER_HEADERS}`
  (20 `.hlsli` + 30 `shared/*.h`), provado no `build.ninja`. Consequência medida: o DXC
  **re-executou os 58** shaders — e os 56 `.spirv.c` ficaram **md5-idênticos** (regressão zero).
- **Aceite**: `ninja -C build-aarch64 rt64_glsl_es_validate` →
  `RESUMO M1.2 GLES: shaders=58 ok=57 excluidos=1 ausentes=0 falhas=0`
  (`DebugPS` excluído: caminho de ray tracing não expressável em ESSL 3.20).
- **Decisão de desenho (desvio registrado do texto original deste plano)**: o blob embutido é o
  **SPIR-V com `-D HLSL_GLES`** (1.584.516 B), **não** o texto ESSL (3.468.332 B; 2,2× maior).
  O ESSL continua sendo gerado e **validado** (byproduct) e esta é a única forma compatível com
  o M1.3 aprovado (especializar com `re-spirv` **antes** de converter). Reversível trocando o
  argumento do `file_to_c` em `build_shader_glsl_es_impl`.
- **Descoberta de caminho**: o estágio era derivado de `${ARGN}`, que chega como **lista** do
  CMake (`-E;PSMain`) → 27 falsos-positivos de `glslangValidator` (mesmo padrão do M1.1 §1);
  corrigido com `-E[^A-Za-z0-9]+([A-Za-z0-9_]+)` (30 frag / 22 comp / 6 vert).
- **Bloqueio de ambiente resolvido** (ortogonal): o `sdl2-config.cmake` do sysroot declarava
  `prefix "/usr"` e o CMake falhava no generate
  (`SDL2::SDL2 includes non-existent path "/usr/include/SDL2"`); corrigido para
  `prefix "/root/sysroot64/usr"` (`evidencias/tools/m1_2_fix_sysroot_sdl2_prefix.sh`).
- **~~Pendente (é M1.3/M2, não M1.2)~~ ✅ RESOLVIDO no M1.3 estágio 2 (2026-10-18)**: os `switch` de
  runtime **têm** o caso `GLSL_ES` e o pipeline GLES é montado (blobs → `re-spirv` → `spirv-cross`
  → `device->createShader(..., GLSL_ES)`). O que **permanece** para o M2/M3 é a *apresentação*:
  nenhum `RenderDevice` GLES existe ainda (é o `plume_gles`), então a validação de execução no
  Mali-G31 continua aberta.
- **Pendência de ambiente (não é regressão do M1.2) — ✅ RESOLVIDA em 2026-10-18**: o **link** CMake
  do binário aarch64 falhava na cadeia GTK/cairo. Causa-raiz medida: **cache obsoleto
  `pkgcfg_lib_GTK3_*`** no `CMakeCache.txt` (escolhia `libcairo.a`/`libglib-2.0.a`/`libharfbuzz.a`
  do sysroot, arrastando `pcre`/`gpg-error`/`LZ4`) + falta de `--allow-shlib-undefined`. Correção
  **sem tocar em fonte** (`cmake -U 'pkgcfg_lib_GTK3_*'` + `CMAKE_EXE_LINKER_FLAGS_INIT` no
  `Toolchain-aarch64.cmake`). Resultado: `[241/242] Linking CXX executable` e
  `ninja: no work to do`, binário 19.869.608 B md5 `b35315d9…`. Detalhes e provas RAW em
  `evidencias/evidence_m1_3_link_and_stage1_20261018.md` §1.
- **Achado que aposenta o `libgtkshim.so`**: auditoria do rootfs **do device** (`darkos.img` +
  `diag_results/diag*.txt`, Debian 13 trixie) prova que `libgtk-3.so.0`, `libgdk-3.so.0`,
  `libglib-2.0.so.0.8400.4`, `libgobject-2.0.so.0`, `libdbus-1.so.3` e `libfreetype.so.6` **existem
  no R36S** → a lista `NEEDED` do binário é satisfeita no device. O shim era só consequência do link
  quebrado. Risco novo registrado: o sysroot é **Ubuntu 22.04** e o device é **Debian 13** (glib 2.72
  × 2.84) → recomendação de regerar o sysroot a partir do rootfs do device (§2.1 da evidência).

#### M1.3 — Decisão de shader em runtime ✅ CONCLUÍDO (2026-10-18)

Vide `evidencias/evidence_m1_3_link_and_stage1_20261018.md` §3 (prova host-side, 6 shaders):

| shader | SPV glsl_es | SPV após `re-spirv` | ESSL cloud (orig) | **ESSL pós-especialização** | `re-spirv` | `spirv-cross` |
|---|---|---|---|---|---|---|
| RasterPSSpecConstant | 284.228 | 28.132 | 703.529 | **28.986** | 15,7 ms | 209 ms |
| RasterPSSpecConstantFlat | 284.376 | 28.180 | 703.588 | **29.030** | 1,6 ms | 170 ms |
| RasterPSSpecConstantMS | 285.160 | 28.184 | 704.827 | **28.986** | 6,0 ms | 71 ms |
| RasterPSSpecConstantFlatMS | 285.308 | 28.232 | 704.897 | **29.033** | 1,5 ms | 175 ms |
| RasterVSSpecConstant | 4.676 | 2.876 | 2.793 | **1.283** | 0,03 ms | 27 ms |
| RasterVSSpecConstantFlat | 4.748 | 2.924 | 2.874 | **1.330** | 0,03 ms | 70 ms |

- **Aceite do plano (`< 50 KB`) atingido**: 28.986-29.033 B ⇒ **≈24× menor** que o ubershader ESSL.
  Validado em `glslangValidator -S vert|frag` (rc=0 nos 6, sem sanitização nova além da do M1.1).
- **Custo medido no host**: 0,03-0,22 s por especialização (re-spirv + spirv-cross). Extrapolado para
  o Mali-G31/RK3326: **≈0,3-4 s por shader** ⇒ **requisito registrado para M2/M6: cache em disco da
  especialização** (hoje o RT64 só tem cache de shader para DXIL).
- Reprodução: `evidencias/tools/m1_3_stage1_specialize.sh` (não altera fontes).
- **Estágio 2 ✅ CONCLUÍDO (2026-10-18)** — vide `evidencias/evidence_m1_3_stage2_20261018.md`:
  - **(a) `spirv-cross` linkado no binário aarch64.** `add_subdirectory(src/contrib/spirv-cross)` +
    `target_link_libraries(rt64 spirv-cross-c)`, ambos com **GATE em `RT64_GLSL_ES_SHADERS`** (builds
    DX/VK/MSL seguem byte-idênticos). Perfil mínimo: `CLI/TESTS/SKIP_INSTALL/HLSL/MSL/CPP/REFLECT/UTIL`
    off, `C_API/STATIC` on. Prova: `ninja rc=0`; `libspirv-cross-{core,glsl,c}.a` gerados;
    binário **22.860.752 B** (md5 `002ebe73398da05613b3396d4bb2d615`, **+2,99 MB**), **228 símbolos
    `spvc_`** e **54 arrays `*BlobGLSLES`** (era 31 — o linker não os descarta mais).
  - **(b) casos `RenderShaderFormat::GLSL_ES` no runtime.** 15 edições + 3 arquivos novos
    (`rt64_glsl_es.{h,cpp}` = conversor livre de `plume`; `rt64_glsl_es_device.h` = wrapper
    header-only `RT64::createShader`). Cobertura: ctor do `RasterShader` (re-spirv + conversão),
    blobs do `RasterShaderUber` (VSDynamic/PSDynamic/MS), post-blend, bloco de *hardware resolve*
    do `rt64_shader_library` (com blobs GLES próprios, pois os SPIRV usam textura 1D/descriptor
    indexing) e `OptimizerCacheSPIRV::initialize(format)`. Os 57 pontos de `device->createShader(`
    passaram pelo wrapper → **zero mudança semântica** para DXIL/SPIRV/METAL.
  - **(c) aceite final medido** (`respv::Optimizer::run` + `spirv-cross` reais, **código de
    produção** sobre os **blobs reais**): **12/12 shaders OK**, `glslangValidator` **12/12**.
    Caminho especializado: 284 KB SPIR-V → **11,1 KB** pós-`re-spirv` → **8.777–8.814 B** de ESSL
    (aceite `< 50 KB` superado ~5,7×). `re-spirv` 1,2–3,0 ms + `spirv-cross` 2,1–3,9 ms (host
    x86-64). Estado canônico preservado (`NFD_PORTAL=OFF`, `--allow-shlib-undefined`,
    `ninja: no work to do`).
  - **(d) medir o custo no device** pertence ao **M5**.
  - **⚠️ Risco novo R7**: o caminho do **ubershader** (`RasterPSDynamic`/`RasterPSDynamicMS`) produz
    **260,9/262,3 KB de ESSL** (não passa por especialização — `DYNAMIC_RENDER_PARAMS` via UBO).
    Extrapolando o Mali-G31 do estágio 1 (~20–50× o host), pode haver *stall* de segundos na
    partida. Decidir mitigação no M2 (não materializar o ubershader em GLES / cache em disco /
    medir antes).

### M2 — Esqueleto `plume_gles` + apresentação

> **Refinamento (2026-10-18)**: ver **Passo 3** em *Plano de execução dos próximos passos*.
> Modelo recomendado: `plume_metal.cpp` (emula sem bindless real); ~4.000-4.600 LOC.
>
> **SESSÃO 1 ✅ CONCLUÍDA (2026-10-18)** — RAW em
> `evidencias/evidence_m2_gles_skeleton_s1_20261018.md`. Estado: **esqueleto completo +
> testável no host**; o aceite do M2 (frames no device) ainda não foi executado.
> - **Carregador GLES auto-contido gerado** (`gen_gles_loader.py`, padrão do `volk` já
>   vendorizado): **358/358** entry points, **1006** constantes, 22 tipos, 1799 linhas.
>   Conferido por `comm` contra o `gl32.h` do Khronos: **zero lacunas**. Compila no host
>   x86_64 sem sysroot, sem SDL2 e sem link a `libGLESv2` (260.208 B de `.o`).
> - **`plume_gles.h` cobre a interface inteira**, provado por `static_assert`: 22 classes
>   concretas instanciáveis + `GLESPipeline` abstrata. Um virtual puro esquecido passaria
>   despercebido até o `new` no device; agora é erro de compilação no host.
> - **Decisão de desenho (SDK-free):** o backend não inclui `<SDL.h>`. Janela/apresentação
>   entram por `GLESSwapChainFunctions` (4 ponteiros) e os entry points por
>   `GLESProcResolver`. Medido: o host **não tem** `/usr/include/SDL2/SDL.h` — sem o shim,
>   o backend perderia a testabilidade fora do device (disciplina do M1.3).
> - **9 erros reais** encontrados pela compilação e corrigidos (nomes de enum/struct
>   inventados, `RenderCommandListType::GRAPHICS` inexistente,
>   `RenderTextureDesc::multisampling.sampleCount`, …). Dois são **achados novos e
>   materiais**: ES 3.2 core **não tem `GL_BGRA`** nem UNORM de 16 bits
>   (`GL_RGBA16`/`GL_RG16`/`GL_R16`) ⇒ **R8**; e não tem `GL_MIRROR_CLAMP_TO_EDGE` ⇒ **R9**.
>   Ambos atingem TMEM/framebuffer e ficam em `unimplemented()` (falha alta e nomeada) até
>   o M3/M4 decidir entre `GL_EXT_texture_norm16` / downgrade + swizzle.
> - **Pendente para fechar o M2** (2-3 sessões): `create*`/recursos, `CommandQueue`/
>   `CommandList` em modo imediato (clear+swap reais), `SwapChain`, gate
>   `RT64_GLES_BACKEND` no CMake, `gles_smoke` e execução sob QEMU.
>
> **SESSÃO 2 ✅ CONCLUÍDA (2026-10-18)** — RAW em
> `evidencias/m2_gles_s2/verify_raw.txt`; narrativa em
> `evidencias/evidence_m2_gles_skeleton_s2_20261018.md`. `plume_gles.cpp` **473 → 2344 linhas**
> (`plume_gles.h` 604 → 609, +`GLESShader::source`).
> - **Implementado e linkado**: os 16 `GLESDevice::create*`; todos os recursos (buffer, texture,
>   texture view, sampler, framebuffer, shader, pipelines, pipeline layout, descriptor set, pool,
>   query pool, fence, semaphore); `GLESCommandQueue` (create list/swapchain, execute, fence);
>   `GLESCommandList` (begin/end, framebuffer, viewport, scissor, clear color/depth/stencil, depth
>   bias, barriers, dispatch, setPipeline, cópia de buffer, resolve); `GLESSwapChain` completo.
> - **Achado metodológico**: a verificação da sessão 1 usou `-fsyntax-only`, que **não linka** —
>   logo não podia detectar símbolo *declarado e nunca definido*. Ao linkar, apareceram
>   `GLESDevice::hasExtension` e `validateShaderFormat` sem definição. **O aceite desta sessão
>   passa a incluir LINK real** (`rc=0`), que cobre a superfície inteira da interface porque
>   `~GLESDevice()` é a *key function* e obriga a emissão da vtable.
> - **Aceite do M2 cumprido em forma verificável**: `gles_smoke.cpp` (chamador EGL puro, sem SDL)
>   obtém contexto **ES 3.2 real** (Mesa llvmpipe) e faz `command list → clear em FBO 0 → present`,
>   então **lê o pixel de volta**: `RGBA(64,128,191,255)` — exatamente a cor pedida — com
>   `glGetError() == 0`. **15/15 checagens OK**. Também valida `glTexStorage2D` +
>   `createFramebuffer` + `resolveTexture` (blit) lendo `RGBA(255,0,0,255)` da textura de destino.
> - **On-target (QEMU/aarch64)**: `gles_target_probe.cpp` roda **7/7 OK** — carregador (358 entry
>   points, ambos os caminhos de `load`) e camada de interface executam corretamente no alvo.
> - **Limitação delimitada (não é falha do backend)**: o smoke **não** roda sob QEMU porque o
>   rootfs aponta `libEGL.so.1 → libMali.so` (blob exige GPU real) e **não há dispatcher GLVND**
>   (a única lib EGL real é `libEGL_mesa.so.0.0.0`, uma lib *vendor* que não exporta
>   `eglGetDisplay` — comprovado por erro de link). Validação funcional completa exige hardware.
> - **3 erros reais** pela compilação: `GL_TEXTURE_MAX_ANISOTROPY_EXT` não existe no `gl32.h` (é de
>   `gl2ext.h`, valor `0x84FE`); `RenderFormat::D24_UNORM_S8_UINT` não existe (só
>   `D32_FLOAT_S8_UINT`); e `&RenderViewport(rvalue)` no smoke. Zero warnings (`-Wall -Wextra`),
>   host e aarch64.
> - **Raster/draw continua abortando de propósito** (input layout + estado fixo = M4), assim como
>   push constants, binding real de descriptors e TMEM (M3).
> - **Pendente para fechar o M2**: gate `RT64_GLES_BACKEND` no CMake (default OFF; builds
>   DX/VK/MSL byte-idênticos), smoke integrado ao RT64 e execução real no R36S via SDL2 → Mali
>   (exige hardware).

- `src/contrib/plume/plume_gles.{h,cpp}`: `RenderInterface`/`RenderDevice`/`RenderCommandQueue`/
  `RenderCommandList`/`RenderBuffer`/`RenderTexture`/`RenderSampler`/`RenderShader`/
  `RenderPipeline`/`RenderFramebuffer`/`RenderDescriptorSet` mínimos
- entrada de função via `SDL_GL_GetProcAddress` (sem link direto a libGLESv2, política `vkprobe`)
- `getCapabilities()` preenchido com os dados reais (bindless=false, RT=false, geometryShader=true,
  triangleFan=true, uma=true, maxTextureSize do GL)
- **Aceite:** binário de teste `gles_smoke` no device apresenta N frames (clear+swap) por dentro
  da interface `plume_gles`, sem erro de GL (com `GL_KHR_debug`).

### M2 — FECHAMENTO ESTRUTURAL ✅ CONCLUÍDO (2026-10-18)

Evidência: `evidencias/evidence_m2_gles_gate_20261018.md` · script `evidencias/tools/m2_gles_gate_apply.py`
(22 substituições, idempotente por **sondas**, com backup/md5 e `revert`) · build em fatias
`evidencias/tools/m2_build_aarch64.sh`.

**Entregue (11 arquivos, 22 substituições):**

1. **Gate `RT64_GLES_BACKEND` (default OFF)** em `lib/rt64/CMakeLists.txt` (option + aviso quando
   ligado sem `RT64_GLSL_ES_SHADERS` + `-DRT64_GLES_BACKEND` no alvo `rt64`) e em
   `lib/rt64/src/contrib/plume/CMakeLists.txt` (mesma variável de cache → compila
   `plume_gles.{cpp,h}` + `plume_gles_gl.{cpp,h}` dentro do alvo `plume`). O status do configure
   passou a imprimir `GLES=${RT64_GLES_BACKEND}`.
2. **`GraphicsAPI::GLES`** no enum (antes de `Automatic`; ordem casada com o `ImGui::Combo`
   posicional de `rt64_state.cpp:2099`), no `NLOHMANN_JSON_SERIALIZE_ENUM` (`"GLES"`) e no rótulo
   do inspector. `isGraphicsAPISupported(GLES)` responde `true` **apenas** com o gate ligado — sem
   ele, uma config com `"GLES"` cai em `Automatic` via `validate()`.
3. **Caso do switch** em `rt64_application.cpp` + ponte SDL↔GLES sob `#ifdef`: contexto **ES 3.2**
   real (`SDL_GL_SetAttribute(SDL_GL_CONTEXT_EGL/…_PROFILE_ES/3.2)` → `SDL_GL_CreateContext` →
   `MakeCurrent` → `SetSwapInterval(1)`) e os 4 ponteiros de `GLESSwapChainFunctions`.
4. **Janela**: `ApplicationWindow::setup(..., bool useOpenGL)` → `SDL_WINDOW_OPENGL` **sem**
   `SDL_WINDOW_VULKAN`, contexto GL liberado em `~ApplicationWindow`.
5. **Lacuna descoberta e fechada (não estava no plano)**: quem cria a janela é
   `src/main/main.cpp` (ela é entregue ao RT64 via `WindowHandle`) — e o SDL2 **rejeita** duas
   flags de backend na mesma janela (`SDL_video.c`: *"Conflicting window flags specified"*). Logo
   a flag precisa nascer no `main.cpp`: `BH_GRAPHICS_API=gles/opengl/gl` ⇒ `SDL_WINDOW_OPENGL`.
   Como o `main.cpp` vive no alvo `BodyHarvestRecompiled` (não no `rt64`), o gate também passou a
   adicionar `-DRT64_GLES_BACKEND` globalmente no `CMakeLists.txt` raiz.

**Aceite medido (números RAW no `ninja_build_{off,on,on2}.log`):**

| Medição | Valor |
|---|---|
| Build aarch64 **OFF** | ✅ verde, 0 erros |
| Binário OFF: símbolos `GLESDevice`/`GLESInterface`/`CreateGLESInterface` | **0** (`plume_gles` em strings: **0**) |
| Calibração (binário não-stripped) | `VulkanDevice` em `strings`: **107** |
| Build aarch64 **ON** | ✅ verde, 0 erros |
| Objetos GLES compilados pelo build normal | `plume_gles.cpp.o` 151.600 B + `plume_gles_gl.cpp.o` 148.352 B |
| Binário **ON**: símbolos GLES | **83** (ex.: `plume::CreateGLESInterface(void*, void* (*)(char const*), plume::GLESSwapChainFunctions)`, `plume::GLESSwapChain::present`) |
| Strings do wrapper/switch no binário ON | `GLES: falha ao criar contexto OpenGL ES 3.2`, `GLES: janela SDL ausente`, `Unable to initialize the OpenGL ES graphics API.`, `Inspector is not available: the GLES backend has no ImGui implementation yet.` |

**Desvio registrado no critério de aceite (importante).** O plano pedia "builds DX/VK/MSL
byte-idênticos" com o gate OFF. Isso **não se sustenta**: 5 dos edit são compilados
incondicionalmente (membro do enum, entrada JSON, `useOpenGL` na janela, `windowUsesOpenGL` no
`Application::setup`, string do Combo), logo o binário OFF difere do pré-gate
(`002ebe73…` → `dbf71397…`, +4.160 B) por razões **semânticas-neutras** (o `useOpenGL` é `false`
sempre que o backend não está compilado). O critério objetivo que **substitui** a byte-identidade
é: **gate OFF ⇒ zero símbolo/string GLES no binário** (medido: 0 vs 107 de calibração). O delta
completo dos 9 primeiros arquivos está em `m2_gles_gate_20261018/gate_off_delta.diff` (393 linhas).

**Artefato desta etapa:** `BodyHarvestRecompiled.m2_gles_gate_20261018` na pasta do port —
22.971.520 B, md5 `a895ada8f061127cf72264ee6c6f7864` (ELF aarch64 PIE, com o backend GLES dentro).
O `CMakeCache.txt` de `build-aarch64` ficou com `RT64_GLES_BACKEND:BOOL=ON` (a opção **default**
continua `OFF`; o cache é que está ligado para os próximos passos — desligue com
`-DRT64_GLES_BACKEND=OFF` se precisar do build sem o backend).

**Pré-condição de execução (para o teste no device, M5).** O caminho GLES exige **duas** coisas
coordenadas: (a) `BH_GRAPHICS_API=gles` no ambiente (define a flag da janela no `main.cpp`) e
(b) a API GLES selecionada na configuração lida **depois** da janela existir. Ligar só uma das
duas produz falha explícita — (a) sem (b): interface Vulkan sobre janela GL; (b) sem (a):
`SDL_GL_CreateContext` falha (janela criada com `SDL_WINDOW_VULKAN`).

> **CORREÇÃO (2026-10-18, durante o M5):** a versão original deste parágrafo dizia
> `graphicsAPI: "GLES"` no **`rt64.json`**. **Essa via não existe neste port**:
> `appConfig.useConfigurationFile = false` (`recompui/src/renderer/rt64_render_context.cpp:271`) e a
> API vem do `switch (cur_config.api_option)` (`:287`) alimentado pelo **`graphics.json` do
> recompui**, cujo `program_id` é `bhrecomp` ⇒ **`$HOME/.config/bhrecomp/graphics.json`**. Detalhes e
> provas em `evidencias/evidence_m5_gles_api_select_20261018.md` §1.

**Riscos abertos desta etapa:** **R10** — o Inspector (ImGui) não existe para GLES; a criação é
recusada com mensagem nomeada em vez de meio-inicializar. **R11** — a flag da janela precede a
leitura da config, logo a seleção automática de API (M5) precisa decidir *antes* do
`create_window()` (provavelmente por env var escrita pelo launcher, não por `rt64.json`).

> **Refinamento (2026-10-18)**: ver **Passo 4**. O bloqueio medido não é sintático (ESSL 320
> aceita arrays de sampler indexados dinamicamente), é de **binding**: sem descriptor indexing e
> com ~16 unidades de textura no Mali-G31, o `gTextures[8192]`/`gTMEM[8192]` exige **janela de N
> texturas + remap no CPU + rebind por draw**, com redução do array sob `HLSL_GLES`.

- emulação de descriptor sets (arrays de UBO/SSBO com rebind por draw; grupos de binding)
- pipeline layout, formats de vertex, estados de blend/depth/cull, samplers (sem
  `samplerMirrorClampToEdge` -> fallback de wrap)
- **Aceite:** passe de composição (FullScreenVS + ComposePS) desenha um quad texturizado vindo de
  um `RenderTexture` criado pelo próprio backend.

> **STATUS DOS RISCOS DO M3 (2026-10-18, após a sonda do device):** **R6** (blob Mali não
> linkável) ✅ **confirmado com causa** (sem SONAME + `.dynsym` malformado) ⇒ política
> *dlopen sempre*; **R8** ⚠️ **reduzido a metade** — `GL_EXT_texture_format_BGRA8888` **existe**,
> só `GL_EXT_texture_norm16` falta (o "sem BGRA" não procede); **R9** ⚠️ **com alternativa** —
> `GL_EXT_texture_border_clamp` cobre o caso do `samplerMirrorClampToEdge`. Detalhes, RAW e
> comandos de reprodução em `evidencias/evidence_m3_gles_device_probe_20261018.md` e na seção
> *M3 — PRÉ-VALIDAÇÃO NO DEVICE* abaixo.

> **ACHADO DO M3.1 — 2026-10-18 (medido, `-Wall` limpo, host + cross + QEMU):** o ESSL que o M1.3
> gera para os raster PS declara **20 arrays de `sampler2D[8192]`** (`grep -c 'Sampler\[8192\]'`
> = 20 nos 4 raster PS) e os indexa por **variável** (`...Sampler[GPUTiles._m0[_707].textureIndex]`,
> 20 call sites). Medido num driver ES 3.2 **conformante** (llvmpipe/ES 3.2, RAW em
> `evidencias/m3_gles_probe/raw_host_reference_llvmpipe.txt`):
> * `arr8192` **isolada** (1 array de 8192 com índice variável) **não linka**:
>   `error: Too many fragment shader texture samplers` ⇒ **a forma atual do M1.3 não linka**;
> * o orçamento é **multiplicativo**: `2×16=32` linka, `3×16=48` **não**, `20×16=320` **não**
>   ⇒ a "janela de N" **sozinha não basta** (o ×20 dos combos de sampler estoura antes do N entrar);
> * `const_idx_8192` (índice **literal**) **linka** ⇒ o que quebra é o **índice resolvido em
>   runtime**, não o tamanho da array;
> * o aceite do M1.3 ("57/57 ESSL") **não cobria link**: o `glslangValidator` do host devolve
>   **rc=0 para índice dinâmico de sampler até SEM extensão** (medido) — ele é permissivo, logo
>   aquele aceite provava *tradução*, nunca *legalidade ES*.
> * `GL_EXT_gpu_shader5` (o que **legaliza** índice dinâmico em GLSL ES; o RAW offline só checava a
>   variante **`NV`**) está **PRESENTE** nas strings do blob — legalidade de indexar ≠ orçamento de
>   samplers: o M3 precisa das duas, e são independentes.
>
> **Consequência (estratégia do M3 revista):** **(1)** *especializar o raster PS por combo de
> sampler* para o shader ter **1** array em vez de 20 (o stream de especialização do M1.3 já existe
> e já está linkado no binário); **(2)** só então a janela `N ≤ GL_MAX_TEXTURE_IMAGE_UNITS` com
> remap no CPU + rebind por draw; **(3)** `gTMEM[8192]` entra **no mesmo orçamento**. A sonda passou a
> medir isso no device (nova seção `[9]`, 10 casos, com `compile=`/`link=` + log cru do driver).

> **ACHADO DO M3.1b — 2026-10-18 (medido no artefato REAL, driver ES 3.2 conformante):** a sonda
> ganhou a seção `[9c]`, que compila e **LINKA** pares VS+PS **de verdade** (o ESSL que o M1.3 gera:
> `RasterPSDynamic` + `RasterVSDynamic`), porque o orçamento de samplers só aparece no **link**.
> Ela **reprovou dois pontos do aceite do M1.1/M1.3** *antes* de medir o M3:
>
> * **D1 — dual-source sem `#extension`:** 6 dos 12 ESSL usam `layout(location = 0, index = 1) out`
>   (2 alvos, para emular o blender do RDP) e o codegen **não** habilita
>   `GL_EXT_blend_func_extended`. Medido: `error: index layout qualifier requires
>   EXT_blend_func_extended`. **Corrigido** no sanitizador de produção (`m1_1_emit_glsl_es.py`, ação
>   `blend-func-extended-required`); regenerar/revalidar os 57 ESSL é o passo de fecho.
> * **D2 — qualificador de interpolação assimétrico:** o PS lê `location = 2` como `flat in` e o VS
>   declara o `out` da mesma location **sem** `flat` ⇒ o **link do par** recusa (medido). A correção
>   é coerência entre estágios (protótipo: `--flat-from-ps` na ferramenta de casos).
>
> Com D1/D2 neutralizados **no protótipo** (e prova mecânica de que o **corpo** do shader não mudou:
> 0 divergências após normalizar nomes/janela), o link do par real deu: `prod_asis` (20 × `[8192]`)
> **FALHOU** (`Too many fragment shader texture samplers`); `2 × [8192]` e `2 × [32]` **FALHOU**;
> `2 × [16]` **FALHOU**; `2 × [15]` **ok**; `2 × [8]` e `2 × [4]` **ok**.
>
> **A regra do N fica corrigida (não é `2 × N`):**
> ```
> n_arrays_com_janela × N + n_samplers_escalares <= GL_MAX_TEXTURE_IMAGE_UNITS
> ```
> O shader real tem **2** arrays com janela (`gTextures` + `gTMEM`) **mais 1 escalar**
> (`gBackgroundDepth`) ⇒ no llvmpipe (32 unidades) o teto medido é **N = 15** (31 ✓ / 33 ✗). Duas
> consequências para o M3: (a) colapsar os 18 combos em 1 array por imagem **não** libera o
> orçamento inteiro — as duas arrays e o escalar precisam entrar na conta; (b) se o
> `gTMEM[8192]` continuar indexado dinamicamente, ele come `N` do **mesmo** orçamento, logo a
> especialização tem de decidir entre **janela compartilhada** ou **sub-janela por array**.

### M4 — Caminho de raster do RDP
- framebuffer/TMEM/texture ops; compute passes do framebuffer (`FbWriteColorCS`, `FbReinterpretCS`,
  `FbReadAnyChangesCS`, `FbChangesClearCS`)
- MSAA + resolve (`GL_EXT_multisampled_render_to_texture`,
  `glFramebufferTexture2DMultisampleEXT`); framebuffer fetch (`GL_ARM_shader_framebuffer_fetch`);
  geometry shader path
- **Aceite:** renderiza cenas do Body Harvest sem corrupção visível em pelo menos 3 fases distintas.

### M5 — Integração e medição
- `GraphicsAPI::GLES` no switch + seleção automática no `BodyHarvest.sh` (KMSDRM + `SDL_VIDEODRIVER`)
- **Aceite:** FPS medidos no device em 640x480, registrados em evidência (com `glFinish`/timer);
  decisão explícita: jogável / otimizar / reverter.

#### M5 — SELEÇÃO DE API: ENTREGUE (2026-10-18) ✅ (medição de FPS fica para depois do M4)

Escopo real (o `rt64.json` do plano não existia — ver correção acima): a cadeia é
`graphics.json["api_option"] → ultramodern::renderer::GraphicsApi → switch no recompui →
RT64::UserConfiguration::GraphicsAPI`. Entregue em **7 edits / 4 arquivos**, todos sob
`#ifdef RT64_GLES_BACKEND`:

| Ponta | Arquivo | O que foi feito |
| :--- | :--- | :--- |
| Enum | `ultramodern/include/ultramodern/config.hpp` | `GLES` **depois** de `Metal` (valor 4; `OptionCount` 4→5 — preserva configs salvas) + par NLOHMANN |
| Nome da API | `ultramodern/src/renderer_context.cpp` | `get_graphics_api_name(GLES) = "GLES"` (senão a falha nomeada vira `[Unknown graphics API]`) |
| UI/catálogo | `recompui/src/config/ui_config_tab_graphics.cpp` | `ALLOW_GLES` (Linux + gate) + entrada `{GLES, "GLES"}` no vetor de opções |
| Seleção | `recompui/src/renderer/rt64_render_context.cpp` | case no `switch(cur_config.api_option)` **e** no `map_graphics_api` (sem o 2º o port abortaria no `assert` ao ler `chosenGraphicsAPI`) |
| Janela | `src/main/main.cpp` (M2) | `BH_GRAPHICS_API=gles` ⇒ `SDL_WINDOW_OPENGL` em vez de `SDL_WINDOW_VULKAN` |
| Launcher | `BodyHarvest.sh` | **um botão** `BH_GLES=1` escreve as duas pontas e reverte ao sair do modo |

**Aceite medido:** build aarch64 verde (`ninja EXIT=0`, 0 erros) → **22.988.496 B**,
md5 `fa3e4b59011263de4547191c1c811fe1`, **311** símbolos GLES, `CreateGLESInterface` presente;
**gate OFF ⇒ 3/3 TUs do M5 com 0 string e 0 símbolo GLES**; smoketest do launcher **13/13 OK**
(4 cenários de estado + sintaxe). Ferramenta de edits idempotente (`apply` → 7/7; `apply` de novo
→ SKIP 7/7). RAW em `evidencias/evidence_m5_gles_api_select_20261018.md` e
`/root/bhrecomp/m5_gles_api_select_20261018/`.

**Pré-condição do teste no device (nova forma):** basta `BH_GLES=1 ./BodyHarvest.sh`. Sem imagem
ainda, **por desenho** (o raster é o M4): o esperado é chegar até o abort nomeado
`GLESCommandList::drawInstanced (caminho de raster = M4)`.

**R11 — fechado** (não há mais decisão heurística antes de `create_window()`, o launcher escreve as
duas pontas). **R12 (novo, baixo)** — o config vive em `$HOME/.config/bhrecomp/`; mitigado gravando
também em `$port_dir`. **R13 (novo, ALTO)** — `GL_EXT_blend_func_extended`: os raster PS escrevem
**2 alvos** (`layout(location = 0, index = 1) out`, dual-source) para emular o blender do RDP e o
GLSL ES **exige** essa extensão habilitada. Medido: o llvmpipe **tem** (corrigido no sanitizador); as
strings do blob Mali **não citam** (indício, não prova — `strings` pode não listar nome montado em
runtime). A sonda agora checa a extensão e a seção `[9c]` dá o veredito de compilação do PS real no
Mali; **se o Mali não tiver, o caminho do blender do RDP muda (arquitetura, não shader)** — decisão
antecipada para o M4. Ver `evidencias/evidence_m3_gles_device_probe_20261018.md` §13.

### M3 — PRÉ-VALIDAÇÃO NO DEVICE: SONDA GLES NATIVA ENTREGUE (2026-10-18)

Como o passo 4 exige **medir antes de fixar N**, o M3 começou por medição — e a medição pode ser
feita *fora do port*, o que é mais barato que instrumentar o raster. Entregue:

| Peça | O que é |
| :--- | :--- |
| `evidencias/tools/gles_device_probe.cpp` | sonda EGL/GLES/GBM **dlopen-only** (não linka EGL/GLES): núcleo EGL, caminho de display (GBM/default), contexto ES3, `GL_VERSION/RENDERER/VENDOR`, inventário de extensões, 15 limites relevantes, clear+readback, e a rota **GBM window surface** (`gbm_surface_create` + `eglCreateWindowSurface` + `eglSwapBuffers` = a rota do SDL/KMSDRM) |
| `evidencias/tools/gles_egl_stub.c` | stub `libEGL.so.1` **só de link-time** (com trava de segurança em `stderr`), necessário porque o blob Mali **não é linkável** — ver R6 |
| `evidencias/tools/m3_{build,package,run,gles_probe_raw}*.sh` | build cross + auditoria + pacote SD + runner + RAW |
| `evidencias/gles_device_probe_pkg.tar.gz` | pacote pronto para o SD (70.274 B, md5 `f547a0c3e41fb940de318c42346133bf`) |

**Aceite medido (offline + emulação):** probe aarch64 **29.912 B**, md5
`e141cc2a3164b476320d1c5c12b5eb83`, `DT_NEEDED` só libc/libstdc++ (**sem** EGL/GLES) e RPATH
vazio; smoke aarch64 **186.856 B**, md5 `dae329b148fce3a1bdaf5d1cb01ecb34`, `DT_NEEDED`
`libEGL.so.1` (resolvido no device para o blob); sob QEMU o blob carrega e **15/15** entry points
EGL resolvem; o pacote é auditado para **não** conter nenhuma `libEGL*`; o runner foi exercitado
ponta-a-ponta sem o device (resumo + `gles_probe_log.txt` corretos). RAW em
`evidencias/m3_gles_probe/raw_offline.txt` (md5 `8d5b433061b949c47238c08eb569a7d1`); narrativa em
`evidencias/evidence_m3_gles_device_probe_20261018.md`.

**Achados que mexem no plano (todos com RAW):**

- **R6 confirmado com causa:** o blob não tem SONAME e tem `.dynsym` malformado
  (`ld: .dynsym local symbol at index 3 (>= sh_info of 3)`) ⇒ **regra do backend: dlopen sempre,
  nunca link direto** (a política "SDK-free" do M2 já estava certa; agora está justificada).
- **Correção de uma nota do M2:** o comentário em `evidencias/m2_gles_s2/gles_target_probe.cpp`
  dizia que o blob "não exporta `eglGetDisplay`/`eglGetProcAddress`". **É falso** — exporta o
  núcleo EGL inteiro (1175 símbolos `T`, incluindo GBM e `eglCreateWindowSurface`/`eglSwapBuffers`).
  O que é verdade é só a parte do *link*. Corrigido no arquivo com nota datada.
- **R8 pela metade:** `GL_EXT_texture_format_BGRA8888` **presente**; `GL_EXT_texture_norm16`
  ausente ⇒ o lado "sem BGRA" cai, o lado 16-bit UNORM permanece.
- **R9 com alternativa:** `GL_EXT_texture_border_clamp` presente.
- **M4 desriscado offline:** `GL_ARM_shader_framebuffer_fetch` e
  `GL_EXT_multisampled_render_to_texture` **presentes**; também `GL_EXT_geometry_shader`,
  `GL_EXT_buffer_storage`, `GL_EXT_texture_storage`, `GL_KHR_debug` e — para medir FPS —
  `GL_EXT_disjoint_timer_query`. Versão embutida no blob: `OpenGL ES 3.2 v1.r13p0-01rel0`.

**Pendência única (1 minuto de device):** rodar `sh run_gles_probe.sh` no R36S e anexar
`gles_probe_log.txt`. Só então os números de `GL_MAX_TEXTURE_IMAGE_UNITS`/`MAX_COMBINED_*`
(⇒ o **N** da janela do M3) deixam de ser estimativa, e o M2 (smoke sobre o driver real) fecha
em hardware.

### M6 — Otimização e empacotamento
- reduzir passes/MSAA, resolução adaptativa, tuning para Mali-G31
- empacotamento PortMaster, launcher final, README do port

## Estimativa do que falta

Base factual (medida nesta etapa): `plume_render_interface.h` tem **103** e
`plume_render_interface_types.h` **92** interfaces/métodos puros (**195** no total); os backends
existentes têm `plume_vulkan.cpp` **4.641 LOC**, `plume_d3d12.cpp` **4.258 LOC**,
`plume_metal.cpp` **4.229 LOC**. Ou seja, um backend novo é **~4.000-4.600 LOC** de código
análogo, sendo `plume_metal` o melhor modelo (sem descriptor indexing real em GPUs Apple3+, com
emulação de argument buffers).

| Etapa | Conteúdo | Estimativa | Risco | Depende de |
|---|---|---|---|---|
| **M1.2** | Canal GLES no build ✅ **CONCLUÍDO (2026-10-18, 1 sessão)**: `RenderShaderFormat::GLSL_ES`, 4º blob em `CREATE_SHADER_INPUTS` (32 call sites), `build_shader_glsl_es_impl` + alvo `rt64_glsl_es_validate` (57/57 ESSL), correção do `DEPENDS`; não-regressão DX/VK 56/56 md5 | — | — | — |
| **M1.3** | Estratégia de shader em runtime: especializar (`re-spirv`) **antes** de converter p/ GLSL ES, com `spirv-cross` linkado no binário. ✅ **CONCLUÍDO (2026-10-18, 2 estágios)**: **Estágio 1** — ESSL especializado **28.986-29.033 B** (≈24× menor que os 704.897 B do ubershader), ESSL 3.20 válido, 0,03-0,22 s/especialização no host. **Estágio 2** — `spirv-cross-c` linkado no binário aarch64 (228 símbolos `spvc_`, +2,99 MB) + casos `GLSL_ES` nos switches de runtime; aceite com o **código de produção sobre os blobs reais**: **12/12** shaders, `glslangValidator` **12/12**, **8.777-8.814 B** de ESSL no caminho especializado. Risco novo **R7** (ubershader = 260 KB de ESSL) registrado para o M2 | ✅ | — | M1.2 |
| **M2** | Esqueleto `plume_gles` (~4,5 mil LOC): device/queue/cmdlist/buffers/textures/shaders/pipelines/descriptors + `getCapabilities`. **Sessão 1 ✅ (2026-10-18)**: carregador GLES gerado (358/358 entry points, host-testável), `plume_gles.h` cobrindo as 19 structs (cobertura provada por `static_assert`), `GLESInterface`+`GLESDevice`+tradurores implementados, backend SDK-free; achados **R8**/**R9** (ES 3.2 sem BGRA/UNORM-16 e sem MIRROR_CLAMP_TO_EDGE). Pendente: `create*`/recursos, `CommandList` modo imediato, `SwapChain`, gate CMake, `gles_smoke`, QEMU. **Sessão 2 ✅ (2026-10-18)**: `create*`+todos os recursos+`CommandQueue`/`CommandList` (modo imediato)+`SwapChain` implementados **e linkados** (link real revelou `hasExtension`/`validateShaderFormat` sem definição — invisível ao `-fsyntax-only` da s1); `gles_smoke` **15/15 OK** com ES 3.2 real (llvmpipe): clear em FBO 0 lido de volta como `RGBA(64,128,191,255)`, `glGetError()==0`; probe on-target QEMU/aarch64 **7/7 OK**; smoke sob QEMU impossível por limitação do rootfs (blob Mali + sem dispatcher GLVND) — delimitado com evidência. Pendente: gate `RT64_GLES_BACKEND`, smoke integrado ao RT64, execução real no device | 1-2 sessões restantes | **alto** | M1.2 |
| **M3** | Descriptors sem bindless + emulação de samplers. **Estratégia REVISTA por medição (M3.1/M3.1b, 2026-10-18)**: a "janela de N" **sozinha não resolve** — o ESSL do M1.3 tem **20 arrays** de `sampler2D[8192]` com índice variável e o orçamento é **multiplicativo**. Medido **no artefato real** (par VS+PS, llvmpipe/ES 3.2): `2×[16]` **falha** e `2×[15]` linka ⇒ a regra é `n_arrays_com_janela × N + n_samplers_escalares ≤ MAX_TEXTURE_IMAGE_UNITS` (o shader real tem 2 arrays + 1 escalar). Ordem nova: **(1)** especializar o raster PS por combo de sampler → **1** array por imagem em vez de 18 combos; **(2)** janela `N ≤ (unidades − escalares)/arrays` (Mali: a medir, seção `[6]`) + remap no CPU + rebind por draw; **(3)** `gTMEM[8192]` **no mesmo orçamento** (a especialização tem de decidir janela compartilhada × sub-janela). A sonda mede os 10 casos sintéticos (`[9]`) **e os 7 pares reais** (`[9c]`) no device. **Bônus medido: 2 defeitos do artefato do M1.1/M1.3 (dual-source sem `#extension` — corrigido no sanitizador — e `flat` assimétrico no par VS/PS) e R13 novo (`GL_EXT_blend_func_extended`)** | 2-3 sessões (+1 já gasto no M3.1/M3.1b) | **alto** | M2 |
| **M4** | Caminho raster do RDP: framebuffer/TMEM/texture ops, compute passes do FB, MSAA/resolve, framebuffer fetch | 4-6 sessões | **alto** | M3 |
| **M5** | `GraphicsAPI::GLES` + KMSDRM/EGL/GBM + medição de FPS no device | 1-2 sessões | médio | M4 |
| **M6** | Otimização para Mali-G31 + PortMaster/empacotamento | 2-3 sessões | médio | M5 |
| Manut. | Rebuild `build-cmake` (x86_64) com os headers com padding, se um binário x86_64 for necessário | 0,5 sessão | baixo | — |

**Total: ~15-23 sessões** (≈70% concentrado em M2-M4), sem contar surpresas de driver — que são
o risco dominante (ver critérios de rollback).

## Plano de execução dos próximos passos

### Passo 1 — M1.2: canal GLSL ES no build ✅ CONCLUÍDO (2026-10-18)

> **Resultado**: implementado conforme os itens 1-5, com **um desvio de desenho registrado**:
> o blob embutido como `<X>BlobGLSLES` é o **SPIR-V com `-D HLSL_GLES`** (1.584.516 B) e não o
> texto ESSL (3.468.332 B), porque (a) é 2,2× menor e (b) é o único formato compatível com o
> "especializar → converter" aprovado no Passo 2. O ESSL segue gerado e **validado**
> (57/57) pelo alvo `rt64_glsl_es_validate`. Detalhes e provas RAW em
> `evidencias/evidence_m1_2_gles_channel_20261018.md`.
1. `contrib/plume/plume_render_interface_types.h`: adicionar `GLSL_ES` ao
   `enum class RenderShaderFormat` (hoje: `UNKNOWN, DXIL, SPIRV, METAL`).
2. `render/rt64_shader_library.cpp`: `CREATE_SHADER_INPUTS` passa a receber um 4º blob
   (`GLSLES_BLOB`) + `sizeof`, com branch para `RenderShaderFormat::GLSL_ES` (mesmo padrão do ramo
   `__APPLE__`/`METAL`).
3. `lib/rt64/CMakeLists.txt`: `build_shader_glsl_es_impl` espelhando `build_shader_msl_impl`, com
   DXC `+ -D HLSL_GLES` e `spirv_cross_glsl_es` = `spirv-cross --es --version 320` + sanitizador
   (`m1_1_emit_glsl_es.py`); usar `file_to_c` para gerar o blob de texto.
4. **Corrigir o bug latente** (agora bloqueante): `DEPENDS ${FILENAME}` →
   incluir `${PROJECT_SOURCE_DIR}/src/shared/*.h` e `src/shaders/*.hlsli`; senão alterar header
   não re-dispara o DXC (comprovado na sessão do M1).
5. **Aceite**: o build aarch64 gera os **57** blobs GLES; `ninja -t deps` lista os headers como
   dependências; `-D HLSL_GLES` não altera os 58 blobs DX (regress 58/58).

### Passo 2 — M1.3: decisão de shader em runtime ✅ CONCLUÍDO (2026-10-18)

> **Resultado do estágio 1 (medido, RAW em `evidence_m1_3_link_and_stage1_20261018.md` §3)**:
> a decisão "especializar primeiro, converter depois" está **validada com números** — o ESSL
> pós-especialização tem **28.986-29.033 B** (aceite `< 50 KB` atingido; ≈24× menor que os 704.897 B
> do ubershader), válido em ESSL 3.20; custo 0,03-0,22 s/especialização no host.
>
> **Resultado do estágio 2 (2026-10-18)** — RAW completo em `evidence_m1_3_stage2_20261018.md`:
> `spirv-cross-c` **linkado** no binário aarch64 (`ninja rc=0`, 228 símbolos `spvc_`, +2,99 MB) e os
> casos `GLSL_ES` cobrindo raster/ubershader/post-blend/hardware-resolve/cache. O aceite roda o
> **código de produção** (`respv::Optimizer::run` + `RT64::convertSPIRVToGLSLES`) sobre os **blobs
> reais** → **12/12 shaders** e `glslangValidator` **12/12**; o caminho especializado cai para
> **8.777-8.814 B** (real, com spec constants de verdade). O "dado já medido" (142 ms para o
> ubershader completo) permanece válido como pior caso e confirma o gargalo: não é a conversão, é o
> Mali compilar centenas de KB — agora **quantificado em 260 KB de ESSL** (risco **R7**).

Decisão **recomendada**: *especializar primeiro, converter depois* — embedar o **SPIR-V GLES**
(1,57 MB), rodar `respv::Optimizer::run` em runtime e só então converter o SPIR-V especializado
para GLSL ES com o `spirv-cross` **linkado no binário**, entregando ao driver um shader pequeno.
- Alternativa rejeitada: embedar os 3,47 MB de GLSL ES e deixar o Mali compilar o ubershader de
  688 KB em runtime (inviável — segundos a minutos, ou falha do compilador).
- **Aceite**: medir, no host, o tempo de `spirv-cross` por especialização e o tamanho do GLSL
  resultante (esperado < 50 KB) vs o ubershader; registrar em evidência.
- **Dado já medido** (host Ryzen 7 3700U, §8.1 da evidência): `spirv-cross --es --version 320`
  converte o **ubershader completo** (285 KB de SPIR-V → 705 KB de GLSL) em **142 ms**; um shader
  pequeno em **7-11 ms**. Um shader especializado (~10-50× menor) deve custar dezenas de ms no
  device → a conversão em runtime é viável (o gargalo real seria o Mali compilar 688 KB).

### Passo 3 — M2: esqueleto `plume_gles` (4-6 sessões)
Portar de `plume_metal.cpp` (melhor modelo: sem bindless real, com emulação). Entrada de funções
por `SDL_GL_GetProcAddress` (sem link direto a `libGLESv2`, política do `vkprobe`).
`getCapabilities()` com `descriptorIndexing=false`, `raytracing=false`, `geometryShader=true`,
`maxTextureSize` real. **Aceite**: `gles_smoke` no device apresenta N frames (clear+swap) por
dentro da interface `plume_gles`, sem erro de GL (com `GL_KHR_debug`).

### Passo 4 — M3: descriptors sem bindless (2-3 sessões)
Estratégia a validar por medição: **janela de N texturas** (N ≤ 16, valor a medir) + tabela de
remap no CPU + rebind por draw; reduzir `gTextures[N]`/`gTMEM[N]` sob `HLSL_GLES` para N. Medir o
número máximo de texturas **distintas por draw** no jogo real antes de fixar N.
**Aceite**: `FullScreenVS` + `ComposePS` desenha um quad texturizado vindo de um `RenderTexture`
criado pelo próprio backend.

> **A medição do M3.1 (2026-10-18) mudou a estratégia acima — leia o bloco "ACHADO DO M3.1" no
> STATUS DOS RISCOS acima e a §12 da evidência.** Resumo do que a medição impõe:
> 1. o "N" **não é o único parâmetro**: o ESSL atual tem **20 arrays** de sampler e o orçamento é
>    `n_arrays × N ≤ GL_MAX_TEXTURE_IMAGE_UNITS` ⇒ **especializar o raster PS por combo de sampler
>    primeiro** (para sobrar **1** array) e só então dimensionar N; `gTMEM` entra no mesmo orçamento;
> 2. **`glslangValidator` rc=0 não valida este caminho** (é permissivo com índice dinâmico): o gate
>    do M3 tem de ser **link + draw** (seção `[9]` da sonda no device dá o link; o draw é o M4);
> 3. a chave `gTextures[8192]`/`gTMEM[8192]` (`FbRendererCommon.hlsli`) e o bind por cache inteiro
>    (`rt64_framebuffer_renderer.cpp:313-315,396-404`) são os dois pontos a mudar no M3.

> **A medição do M3.1b (2026-10-18) corrigiu a conta acima — leia o bloco "ACHADO DO M3.1b" no
> STATUS DOS RISCOS e a §13 da evidência.** Ela foi feita **no artefato real** (par VS+PS de verdade,
> não em forma sintética) e impõe:
> 1. a regra do orçamento é
>    `n_arrays_com_janela × N + n_samplers_escalares ≤ GL_MAX_TEXTURE_IMAGE_UNITS` — medido no
>    llvmpipe: `2×[16]+1 = 33` **falha**, `2×[15]+1 = 31` linka (o `2 × N` do item 1 acima estava
>    otimista: o shader real tem 2 arrays **e** 1 escalar `gBackgroundDepth`). Logo
>    **N ≤ (unidades − escalares) / arrays** com os números do **Mali** (seção `[6]` da sonda);
> 2. **dois defeitos do artefato do M1.1/M1.3** aparecem *antes* do M3 e têm de ser corrigidos no
>    gerador: (D1) o PS escreve 2 alvos e o ESSL não habilitava `GL_EXT_blend_func_extended`
>    (**já corrigido** no sanitizador `m1_1_emit_glsl_es.py`; falta regenerar/revalidar os 57 ESSL);
>    (D2) o `flat` do PS não existe no `out` do VS ⇒ o **link do par** recusa (correção: coerência
>    entre estágios, mesma classe do sanitizador);
> 3. o gate do M3 continua **link + draw** — e agora as duas pontas são executáveis: o link sai da
>    seção `[9c]` (pares reais) e o draw é o M4;
> 4. **R13** (`GL_EXT_blend_func_extended`, dual-source) passou a ser pré-requisito de **compilação**
>    dos raster PS: se o Mali não tiver, o caminho do blender do RDP muda.

> **Ferramentas novas do M3.1b (reproduzível):** `evidencias/tools/m3_make_shader_cases.sh` (gera os
> 7 pares VS+PS de produção a partir de `evidencias/m1_3_stage2/essl/`) e
> `evidencias/tools/m3_essl_specialize.py` (protótipo da especialização: `--collapse-samplers`,
> `--window N`, `--enable-extension`, `--flat-from-ps`). Medição local:
> `bash evidencias/tools/m3_make_shader_cases.sh` +
> `PROBE_SHADER_DIR=... ./probe_host_x86_64 --no-gbm` (RAW em
> `evidencias/m3_gles_probe/raw_host_prod_essl_linktest.txt`).

### Passo 5 — M4 → M6
M4 (framebuffer/TMEM/compute/MSAA) e M6 (otimização/empacotamento) conforme as seções acima.
**M5 já foi antecipado e entregue** (a parte de seleção de API/launcher, que não dependia do
raster); resta dele apenas a **medição de FPS**, que só faz sentido depois do M4. A ordem prática
atual é: **M3 → M4 → (medição do M5) → M6**.

### Ordem, gates e disciplina de evidência
`M1.2 → M1.3 → M2 (gate 1: frames na tela) → M3 (gate 2: quad texturizado) → M4 (gate 3: 3 fases
sem corrupção) → M5 (gate 4: FPS medido → jogável/otimizar/reverter) → M6`.
Exceção registrada: a **fiação de seleção de API do M5** foi feita junto do M2/M3 (não depende do
raster) para que o teste no device já possa escolher GLES com um único botão (`BH_GLES=1`).
**Cada gate exige evidência RAW nova + atualização deste plano** (regra `evidence-collection`).

## Critérios de rollback (quando parar)

- M2 falha por limitação do driver (sem compute/SSBO reais) -> reavaliar opção A (só devices com
  WSI display) ou C (software, medir FPS).
- M4 mostra que o pipeline do RT64 não é expressável em GLES sem reescrita profunda -> idem.
- M5 mede FPS < ~5 de forma estrutural -> port inviável no R36S; documentar e encerrar.

## Comandos de referência (reprodução)

```bash
# probe GLES (cross)
aarch64-linux-gnu-gcc -O2 -Wall -I/opt/sdl2-aarch64/include -o glesprobe _gles_probe.c \
  -L/opt/sdl2-aarch64/lib -lSDL2

# rodar no host (QEMU) contra a rootfs do device
LD_LIBRARY_PATH=/opt/sdl2-aarch64/lib qemu-aarch64-static -L /opt/r36s/rootfs ./glesprobe

# no device (com o SDL do port no LD_LIBRARY_PATH)
SDL_VIDEODRIVER=kmsdrm LD_LIBRARY_PATH="./libs" ./glesprobe

# build aarch64 do port
cd /root/bhrecomp && cmake -B build-aarch64 -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=Toolchain-aarch64.cmake -DCMAKE_PREFIX_PATH=/root/sysroot64
ninja -C build-aarch64 BodyHarvestRecompiled
```

### Sonda GLES nativa do R36S (M3/pré, 2026-10-18)

```bash
PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"

# 1) build cross das sondas (stub de link-time + probe dlopen-only + smoke aarch64)
bash "$PROJ/evidencias/tools/m3_build_gles_probe.sh"

# 1b) MEDICAO DO M3 no HOST: referencia de um driver ES 3.2 conformante (llvmpipe).
#     O `LIBGL_ALWAYS_SOFTWARE=1` e' obrigatorio: sem ele o Mesa desta maquina entrega no
#     maximo ES 3.1/GLSL 3.10 e o `#version 320 es` nem compila (medido).
g++ -std=c++17 -O2 -Wall -Wextra -o /tmp/probe_host "$PROJ/evidencias/tools/gles_device_probe.cpp" -ldl
LIBGL_ALWAYS_SOFTWARE=1 EGL_PLATFORM=surfaceless /tmp/probe_host --no-gbm \
    > /root/bhrecomp/m3_gles_probe/raw_host_reference_llvmpipe.txt

# 2) RAW consolidado (symlinks, linkabilidade do blob, superficie EGL/GBM exportada,
#    strings/extensoes (inclui GL_EXT_gpu_shader5), binarios, QEMU, pacote) -- a evidencia
bash "$PROJ/evidencias/tools/m3_gles_probe_raw.sh" > /root/bhrecomp/m3_gles_probe/raw_offline.txt

# 3) pacote para o cartao SD (audita que NENHUMA libEGL* entra) + tar.gz
bash "$PROJ/evidencias/tools/m3_package_gles_probe.sh"

# 4) NO DEVICE (fecha o aceite do M2 E mede o M3) -- ~1 minuto
#    cd /roms/ports/glesprobe && sh run_gles_probe.sh   # gera gles_probe_log.txt
#    Se o caminho GBM nao abrir display, o runner repete sozinho com --no-gbm (bloco [1b]).
#    O que ler no log: `PROBE result=PASS`, `gl_version=OpenGL ES 3.2`, `[smoke] ===== 0 falha(s)`,
#    e a tabela `PROBE m3_shader_measurement` (os 10 casos de sampler array).
```

### Matriz de layout DX vs GL e PoC de padding (M1)

```bash
# 1) matriz: compila cada shader nos 2 layouts (saida em dir scratch) e mede
#    dxc / spirv-val / spirv-cross / glslangValidator
bash "evidencias/tools/m1_layout_matrix2.sh"
python3 evidencias/tools/m1_matrix_analyze.py /root/bhrecomp/m1_layout_matrix2/results.tsv

# 2) diff de offsets DX vs GL por struct (offsets reais via spirv-dis)
python3 evidencias/tools/m1_layout_diff.py /root/bhrecomp/m1_layout_matrix2

# 3) PoC: aplica padding nos 6 headers duais, recompila em layout DX e valida
#    (restaura os headers originais ao final; patch salvo em headers_patched/)
bash "evidencias/tools/m1_poc_padding2.sh"

# 4) mitigacao da extensao espuria GL_NV_gpu_shader5
bash "evidencias/tools/m1_mitig_nonuniform.sh"

# 5) restore dos blobs DX (a partir do build-cmake pristine)
bash "evidencias/tools/m1_restore_dx_blobs.sh"
```

### Aplicação do padding na árvore real + rebuild aarch64 (M1, 2026-10-18)

```bash
# 1) aplica o padding nos 6 headers reais (backup + md5 + invalida os 58 blobs)
bash "evidencias/tools/m1_apply_padding.sh"

# 2) corrige o mismatch SDL2 do sysroot aarch64 (headers 2.0.20 x lib 2.30)
bash "evidencias/tools/m1_fix_sysroot_sdl2.sh"

# 3) regenera os 58 blobs SPIR-V (executa os comandos DXC exatos do build.ninja)
python3 "evidencias/tools/m1_regen_blobs.py" 6

# 4) valida: spirv-val / spirv-cross ES 320 / glslang + atribuicao de causa
python3 "evidencias/tools/m1_validate_blobs.py"

# 5) offsets dos membros significativos dos blobs reais vs std430 (esperado: 0 divergencias)
python3 "evidencias/tools/m1_offset_compare.py"

# 6) rebuild aarch64 destacado (setsid; sobrevive entre chamadas do runner)
bash "evidencias/tools/m1_build_detached.sh"
tail -f /root/bhrecomp/m1_apply_20261018/ninja_build.log
```

> Nota: o runner de comandos encerra a sessão em ~30 s e mata jobs em background. Para
> builds longos use `m1_build_detached.sh` (`setsid` + `nohup`), ou fatias com
> `m1_build_aarch64.sh <segundos>` (o progresso é preservado pelo `.ninja_log`).

### M1.1 — adaptações GLES + conjunto GLSL ES 3.20 (2026-10-18)

```bash
# 1) aplica as adaptacoes de fonte gated por -D HLSL_GLES (backup + md5)
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_1_apply_gles_macros.py" apply

# 2) emite + valida o conjunto GLSL ES 3.20 (resumavel; use setsid para o run completo)
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_1_emit_glsl_es.py" gles --workers 8

# 3) prova de nao-regresso do caminho DX/VK/MSL (esperado: 58/58 md5 identicos)
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_1_emit_glsl_es.py" regress --workers 8

# 4) reverter os fontes
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_1_apply_gles_macros.py" revert
```

> Resultado esperado: `RESUMO M1.1: shaders=57 | excluidos=1 | glslang OK=57 | glslang FALHAS=0`
> e `RESUMO REGRESS: identicos=58 divergentes=0 falhas=0`.