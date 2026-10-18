# Evidência — M2-GLES: gate `RT64_GLES_BACKEND` (integração do backend GLES ao RT64)

Data: 2026-10-18 · Sessão: M2 (fechamento estrutural) — passo "gate CMake + `GraphicsAPI::GLES`"
Objetivo: tirar o backend `plume_gles` do isolamento (smoke test) e colocá-lo **dentro do
build real do RT64**, selecionável por `GraphicsAPI::GLES`, sem afetar os backends existentes.

## 0. Resumo

| Item | Resultado |
|---|---|
| Gate `RT64_GLES_BACKEND` (default **OFF**) | criado em `lib/rt64/CMakeLists.txt` + `lib/rt64/src/contrib/plume/CMakeLists.txt` |
| `GraphicsAPI::GLES` | adicionado ao enum + JSON (`"GLES"`) + Combo do inspector |
| Seleção condicional | `isGraphicsAPISupported(GLES)` = `true` **somente** com o gate ligado |
| Caso do switch (`rt64_application.cpp`) | criado (com criação real do contexto ES 3.2 via `SDL_GL_CreateContext`) |
| Janela | `ApplicationWindow::setup(..., useOpenGL)` → `SDL_WINDOW_OPENGL` (e sem `SDL_WINDOW_VULKAN`) |
| Build aarch64 **OFF** | ✅ verde; **0** símbolos `GLESDevice`/`GLESInterface`/`CreateGLESInterface` no binário |
| Build aarch64 **ON** | ✅ verde; **83** símbolos GLES no binário (22.971.520 B, md5 `a895ada8…`) |
| Script de aplicação | `evidencias/tools/m2_gles_gate_apply.py` (apply/revert/check; idempotente por sondas) |

## 1. Arquivos alterados (11) e md5

Pristino → aplicado (md5 completos no `manifest.json` em
`/root/bhrecomp/m2_gles_gate_20261018/manifest.json`). O ciclo `revert` → `apply` foi exercitado no
fim da sessão e reproduz **byte-a-byte** estes valores (11/11 `OK`, 0 falhas).

| Arquivo | md5 pristino | md5 aplicado |
|---|---|---|
| `CMakeLists.txt` (raiz) | `212d74fdfff97b2eb3029470befb5c30` | `e076662cce2a8d41b4ee4947f52bf279` |
| `src/main/main.cpp` | `99e13c73f5efa3c4397ae1b6ecb6fdba` | `4d7412b37bfe60d18db7ce753d4b6bb5` |
| `lib/rt64/CMakeLists.txt` | `aab8b85f9eb8d9a9ad3133ca26c65087` | `1387438f97efdb4149e85e540688f174` |
| `lib/rt64/src/contrib/plume/CMakeLists.txt` | `af322168585d97d90926d429dc1d0789` | `11b37cb37b09ab936ad5d742ce47b3b9` |
| `lib/rt64/src/contrib/plume/plume_gles.h` | `54aaf80881b6fa2a24e9b5a8e8d38f84` | `483f7921abcb3b640994dadd9fd1cea2` |
| `lib/rt64/src/common/rt64_user_configuration.h` | `40eb7b66c5cb969d59138b0b83ebec5f` | `39078868adf57660918764e205d9bf04` |
| `lib/rt64/src/common/rt64_user_configuration.cpp` | `3c741d1d7f6a50fb4c4fe8a1e9e67761` | `62ca74742e1ed8b7b29af86d29974641` |
| `lib/rt64/src/hle/rt64_application_window.h` | `d578d39f4deec688488559706544590d` | `5dc16cff745693465da8ee218dacf2d6` |
| `lib/rt64/src/hle/rt64_application_window.cpp` | `98ba056b36dcc93aba3c37f79859ccbc` | `3b09c139ccc320ed929ebaf18233386c` |
| `lib/rt64/src/hle/rt64_application.cpp` | `23eab33e6a1a87347c8f947cb492cb08` | `befeacf9723168d4cf45afcb9be1dad8` |
| `lib/rt64/src/hle/rt64_state.cpp` | `6c727088bd589ef825f1882707d39d53` | `514113ee38b3eeb5ee622291e910ad68` |

## 2. Corpus de edições (22 substituições)

Aplicadas por `m2_gles_gate_apply.py` com asserção de unicidade (`count(old) == 1`) e
pós-condição por **sonda** (string que só existe no texto aplicado). As 22 foram aplicadas em dois
lotes (20 + 2, os dois últimos para o `main.cpp` e o `CMakeLists.txt` raiz); a segunda execução de
cada lote resultou em `SKIP` total (22/22), comprovando a idempotência.

### 2.1 Gate no CMake

- `lib/rt64/CMakeLists.txt`: `option(RT64_GLES_BACKEND "..." OFF)` + aviso explícito quando
  `RT64_GLES_BACKEND=ON` e `RT64_GLSL_ES_SHADERS=OFF` (backend sem blobs ESSL);
  `target_compile_definitions(rt64 PRIVATE RT64_GLES_BACKEND)` após `target_link_libraries(rt64 plume)`.
- `lib/rt64/src/contrib/plume/CMakeLists.txt`: `option(RT64_GLES_BACKEND ...)` (mesma variável de
  cache) + `list(APPEND PLUME_SOURCES plume_gles.cpp plume_gles.h plume_gles_gl.cpp plume_gles_gl.h)`;
  status do configure passa a imprimir `GLES=${RT64_GLES_BACKEND}`.

### 2.2 Seleção da API

- enum: `GLES` **antes** de `Automatic` (a serialização JSON é por NOME; a ordem casa com o
  `ImGui::Combo` posicional de `rt64_state.cpp:2099`, também atualizado).
- `NLOHMANN_JSON_SERIALIZE_ENUM`: `{ GLES, "GLES" }`.
- `isGraphicsAPISupported`: `GLES` ⇒ `#ifdef RT64_GLES_BACKEND` (`true`) / `#else` (`false`) ⇒
  sem o gate, uma config com `"GLES"` cai em `Automatic` via `validate()`.
- rótulo do inspector: `case GraphicsAPI::GLES: "Graphics API: OpenGL ES"`.

### 2.3 Criação da interface e do contexto (SDL)

`rt64_application.cpp` ganha, sob `#ifdef RT64_GLES_BACKEND`:

- `glesProcResolver` → `SDL_GL_GetProcAddress`;
- os 4 ponteiros de `GLESSwapChainFunctions` (`SDL_GL_SwapWindow`,
  `SDL_GL_GetDrawableSize`, `SDL_GL_SetSwapInterval`, `SDL_GetCurrentDisplayMode().refresh_rate`);
- `CreateGLESInterfaceWrapper`: `SDL_GL_SetAttribute` (EGL, perfil **ES**, 3.2, double buffer) →
  `SDL_GL_CreateContext` → `SDL_GL_MakeCurrent` → `SDL_GL_SetSwapInterval(1)` →
  `plume::CreateGLESInterface(window, resolver, swapFunctions)`.
  Contexto em `ApplicationWindow::glContext` (destruído em `~ApplicationWindow` se o vídeo
  ainda estiver inicializado).

### 2.4 Janela

`ApplicationWindow::setup(..., bool useOpenGL)`:

- `useOpenGL` ⇒ `flags |= SDL_WINDOW_OPENGL` **e** omite `SDL_WINDOW_VULKAN` (são mutuamente
  exclusivos no SDL2);
- `Application::setup()` passa `windowUsesOpenGL` calculado por `resolveGraphicsAPI(...)`.

### 2.5 Definição global do gate + a janela do port (`main.cpp`)

Descoberta durante a integração: quem cria a janela SDL é **`src/main/main.cpp`**
(`create_window()`, que devolve `WindowHandle{ window }` para o RT64). Isso tem duas consequências:

1. o SDL2 **rejeita mais de uma** flag de backend gráfico por janela
   (`SDL_video.c`: `graphics_flags = flags & (OPENGL|METAL|VULKAN); if (graphics_flags & (graphics_flags - 1))`
   ⇒ *"Conflicting window flags specified"*). Logo a janela do GLES precisa ser criada **sem**
   `SDL_WINDOW_VULKAN` e **com** `SDL_WINDOW_OPENGL`;
2. essa escolha acontece **antes** de o RT64 ler o `rt64.json`, portanto não pode vir da config.

Solução adotada (mínima e explícita):

- `CMakeLists.txt` (raiz): com o gate ligado, `add_compile_definitions("RT64_GLES_BACKEND")` — o
  `main.cpp` pertence ao alvo `BodyHarvestRecompiled`, não ao `rt64`, então a define `PRIVATE` do
  `rt64` não o alcançava;
- `src/main/main.cpp`: `usesOpenGLWindow()` lê **`BH_GRAPHICS_API`** (`gles`/`opengl`/`gl`,
  case-insensitive) e `create_window()` faz
  `flags |= usesOpenGLWindow() ? SDL_WINDOW_OPENGL : SDL_WINDOW_VULKAN;` — tudo sob
  `#ifdef RT64_GLES_BACKEND`, logo com o gate OFF o `main.cpp` compila exatamente como antes.

Sem `BH_GRAPHICS_API` o comportamento é o de sempre (Vulkan) — a variável é opt-in do launcher.

### 2.6 Desvios conscientes (registrados)

1. **Inspector desabilitado no GLES**: `processDeveloperShortcut` recusa criar o `Inspector`
   para `GraphicsAPI::GLES` com mensagem explícita (o construtor do `Inspector` faz
   `assert(false)` no `default` do switch de API; não existe backend ImGui para GLES no RT64).
   Sem isso o inspector ficaria meio-inicializado em builds Release (assert compilado fora).
2. **`CreateGLESInterface` não cria contexto**: o comentário do header dizia que criava. O
   contrato real (e agora documentado) é "contexto já corrente" — quem cria é o chamador.

## 3. Resultado do build (aarch64, `build-aarch64`)

Baseline preservado antes de qualquer edição de build: `m2_gles_gate_20261018/BodyHarvestRecompiled.pre_gate_off`
— 22.860.752 B, md5 `002ebe73398da05613b3396d4bb2d615`.

### 3.1 Gate OFF (não-regressão)

```
cmake -B build-aarch64 -DCMAKE_TOOLCHAIN_FILE=/root/bhrecomp/Toolchain-aarch64.cmake -DRT64_GLES_BACKEND=OFF
-- Plume - Building with backends: Vulkan=1 Metal= D3D12= GLES=OFF
RT64_GLES_BACKEND:BOOL=OFF
ninja -C build-aarch64 BodyHarvestRecompiled   -> 43 arestas, 0 erros (ninja_build_off.log)
```

| Sonda no ELF (binário não-stripped, 46.530 símbolos no `nm`) | Resultado |
|---|---|
| `nm -C … \| grep -c 'GLESDevice\|GLESInterface\|CreateGLESInterface'` | **0** |
| `strings … \| grep -c 'plume_gles'` | **0** |
| `strings … \| grep -c 'VulkanDevice'` (calibração) | **107** |

Artefato: `m2_gles_gate_20261018/BodyHarvestRecompiled.gate_off`, 22.864.912 B, md5 `dbf71397b37b409d973c43bb69fbaeda`.

**Desvio vs o critério original ("byte-idêntico")**: `002ebe73…` → `dbf71397…` (**+4.160 B**). Delta
completo (393 linhas, 9 arquivos) em `m2_gles_gate_20261018/gate_off_delta.diff`. Motivo: 5 edits são
compilados **mesmo com o gate OFF**:

| Edit incondicional | Efeito com o gate OFF |
|---|---|
| membro `GLES` no enum `GraphicsAPI` | desloca `Automatic` (3→4); a serialização JSON é por nome |
| `{ GraphicsAPI::GLES, "GLES" }` | mapeamento só de compilação |
| `Combo("D3D12\0Vulkan\0Metal\0GLES\0Automatic\0")` | 5º item na UI, recusado por `isGraphicsAPISupported` |
| `useOpenGL` (param/membro/atribuição) + `if (useOpenGL)` | é sempre `false` ⇒ ramo morto |
| `windowUsesOpenGL` em `Application::setup` | `resolveGraphicsAPI` nunca devolve `GLES` sem o gate |

Nenhuma delas altera comportamento sem o gate; o critério objetivo que **substitui** a
byte-identidade é **zero símbolo/string GLES no binário** (medido: 0, contra 107 de calibração).

### 3.2 Gate ON (backend dentro do binário)

```
cmake -B build-aarch64 -DCMAKE_TOOLCHAIN_FILE=/root/bhrecomp/Toolchain-aarch64.cmake -DRT64_GLES_BACKEND=ON
-- Plume - Building with backends: Vulkan=1 Metal= D3D12= GLES=ON
RT64_GLES_BACKEND:BOOL=ON
grep -c 'plume_gles' build.ninja                     -> 5   (plume_gles.cpp + plume_gles_gl.cpp)
grep -c 'RT64_GLES_BACKEND' build.ninja              -> 210 (DEFINES do alvo rt64)
ninja -C build-aarch64 BodyHarvestRecompiled         -> 218 arestas, 0 erros   (ninja_build_on.log)
ninja -C build-aarch64 BodyHarvestRecompiled         -> 470 arestas, 0 erros   (ninja_build_on2.log, após o edit do main.cpp)
ninja -C build-aarch64 BodyHarvestRecompiled         -> "ninja: no work to do."
```

| Medição | Resultado |
|---|---|
| objetos GLES compilados pelo build normal | `plume_gles.cpp.o` **151.600 B** + `plume_gles_gl.cpp.o` **148.352 B** (dentro do `libplume.a`) |
| símbolos GLES no ELF | **83** |
| `nm -C … \| grep CreateGLESInterface` | `T plume::CreateGLESInterface(void*, void* (*)(char const*), plume::GLESSwapChainFunctions)` |
| `nm -C … \| grep GLESSwapChain::present` | `T plume::GLESSwapChain::present(unsigned int, plume::RenderCommandSemaphore**, unsigned int)` |
| `strings … \| grep 'OpenGL ES 3.2 (libMali'` | `OpenGL ES 3.2 (libMali blob / EGL+GBM)` |
| `strings … \| grep BH_GRAPHICS_API` | **1** (⇒ `src/main/main.cpp` compilado **com** o gate) |
| `strings … \| grep 'GLES: falha ao criar contexto OpenGL ES 3.2'` | **1** |
| `strings … \| grep 'GLES: janela SDL ausente'` | **1** |
| `strings … \| grep 'Unable to initialize the OpenGL ES graphics API.'` | **1** |
| `strings … \| grep 'has no ImGui implementation yet'` | **1** |

Binário final: **22.971.520 B**, md5 **`a895ada8f061127cf72264ee6c6f7864`**, ELF aarch64 PIE.
Artefato: `BodyHarvestRecompiled.m2_gles_gate_20261018` na pasta do port (cópia de
`/root/bhrecomp/build-aarch64/BodyHarvestRecompiled`).

## 4. Reprodução

```bash
P="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m2_gles_gate_apply.py"

# 1) corpus de edits (22) -- check/apply/revert, idempotente por sondas
python3 "$P" check        # 22/22 aplicados (ou 0/22 num clone pristino)
python3 "$P" apply        # aplica o que faltar; 2a execucao = 22x SKIP

# 2) build SEM o backend (nao-regressao: 0 simbolo GLES no ELF)
cmake -B /root/bhrecomp/build-aarch64 -DCMAKE_TOOLCHAIN_FILE=/root/bhrecomp/Toolchain-aarch64.cmake -DRT64_GLES_BACKEND=OFF
ninja -C /root/bhrecomp/build-aarch64 BodyHarvestRecompiled

# 3) build COM o backend GLES (gate ON; requer RT64_GLSL_ES_SHADERS=ON, ja no cache)
cmake -B /root/bhrecomp/build-aarch64 -DCMAKE_TOOLCHAIN_FILE=/root/bhrecomp/Toolchain-aarch64.cmake -DRT64_GLES_BACKEND=ON
bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m2_build_aarch64.sh" on 25   # repetir ate' "no work to do"

# 4) reverter TUDO ao estado pristino (11 arquivos, md5 conferido)
python3 "$P" revert
```

## 5. Execução no device (M5) — pré-condição obrigatória

O caminho GLES só é exercitado com **as duas** chaves coerentes:

1. **`BH_GRAPHICS_API=gles`** (ou `opengl`/`gl`) no ambiente — decide `SDL_WINDOW_OPENGL` em
   `src/main/main.cpp::create_window()`. Sem isso a janela nasce com `SDL_WINDOW_VULKAN` e o
   `SDL_GL_CreateContext` falha (mensagem `GLES: falha ao criar contexto OpenGL ES 3.2`);
2. **`graphicsAPI: "GLES"`** no `rt64.json` — a config do RT64 é lida **depois** de a janela existir,
   logo ela não pode decidir a flag.

Estados de falha explícita (nunca silenciosa):
- (1) sem (2) → interface **Vulkan** sobre uma janela GL;
- (2) sem (1) → `GLES: falha ao criar contexto OpenGL ES 3.2: <erro do SDL>`;
- janela ausente → `GLES: janela SDL ausente -- nao ha onde criar o contexto.`;
- contexto sem ES 3.2 → `GLESDevice` aborta listando os entry points ausentes (projeto).

O raster continua abortando por desenho consciente (`GLESCommandList::drawInstanced (caminho de
raster = M4)`), portanto o teste real no device **ainda não apresenta imagem**: nesta etapa o que se
valida é a cadeia janela → contexto ES 3.2 → `GLESInterface`/`GLESDevice` (getDescription,
swapchain, clear).

## 6. Estado dos gates

| Gate | Status |
|---|---|
| `RT64_GLES_BACKEND` ligado e verificável | ✅ (0 → 83 símbolos GLES) |
| Build do port contém o backend | ✅ |
| Seleção `GraphicsAPI::GLES` não quebra os outros backends | ✅ (0 símbolo GLES com o gate OFF) |
| Execução real no R36S | ⏳ pendente: launcher (M5) + raster (M4) |