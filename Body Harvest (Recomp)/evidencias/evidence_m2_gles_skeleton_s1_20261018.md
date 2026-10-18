# EVIDENCIA: M2 (sessao 1) — esqueleto `plume_gles` + carregador GLES

Data (UTC): 2026-10-18
Conta AWS: nao aplicavel
Ambiente: WSL Ubuntu 22.04 (host x86_64); `g++ 11.4.0`; sysroot do device em
`/opt/r36s/rootfs` (Debian 13 trixie); arvore do porte em `/root/bhrecomp`.
Marco: **M2 — Esqueleto `plume_gles` + apresentacao** (`docs/PLANO_BACKEND_GLES_R36S.md`).
Estado: **sessao 1 de 4-6 CONCLUIDA e VERIFICADA**. O aceite do M2 (`gles_smoke` no
device) ainda NAO foi executado: falta completar a implementacao (ver §5).

---

## 1. Artefatos criados

| Arquivo | Linhas | md5 | Natureza |
|---|---|---|---|
| `src/contrib/plume/plume_gles_gl.h` | 1799 | `9678cf48ca0c72a70e4901b579a35052` | **gerado** |
| `src/contrib/plume/plume_gles_gl.cpp` | 42 | `573fa89a6a295188f5f9b3c77da15aba` | **gerado** |
| `src/contrib/plume/plume_gles.h` | 604 | `f0f0c175d3a09c4902ee119d620bf335` | autoral |
| `src/contrib/plume/plume_gles.cpp` | 473 | `4cab332420421dbe1516f9dda9e8b180` | autoral (parcial, §5) |
| `evidencias/tools/gen_gles_loader.py` | 280 | — | gerador |
| `evidencias/tools/staged/m2_hdr_coverage.cpp` | 61 | `17ba6157b6bbbef108a3e40d81c079c4` | prova de cobertura |

Diretorio de trabalho: `/root/bhrecomp/m2_gles/staged/`. Fontes-verdade (auditaveis)
em `evidencias/tools/staged/`.

---

## 2. Carregador GLES auto-contido (`gen_gles_loader.py`)

### 2.1 Por que gerar em vez de `#include <GLES3/gl32.h>`

`GLES3/gl32.h` **emite os prototipos** das 358 funcoes. Isso impediria a tabela de
ponteiros homonima (padrao `volk`, ja usado neste repositorio para Vulkan) e criaria
dependencia de headers do sysroot. O gerador emite um header **autocontido** — mesma
disciplina que tornou `rt64_glsl_es.{h,cpp}` testavel no host no M1.3.

Precedente no proprio repo: `src/contrib/plume/contrib/volk/generate.py`.

### 2.2 Comando RAW e saida

```
$ python3 evidencias/tools/gen_gles_loader.py \
    /opt/r36s/rootfs/usr/include/GLES3/gl32.h . plume_gles_gl
gen_gles_loader: fonte=/opt/r36s/rootfs/usr/include/GLES3/gl32.h
  -> ./plume_gles_gl.h (1799 linhas)
  -> ./plume_gles_gl.cpp (42 linhas)
  tipos=22 constantes=1006 entry_points=358
```

Contagens confirmadas por grep independente no gerado:

```
$ grep -c '^typedef .*PFN_gl' plume_gles_gl.h   -> 358
$ grep -c '^#define GL_'      plume_gles_gl.h   -> 1006
$ grep -c '^    X('           plume_gles_gl.h   -> 358
```

Conferencia de completude (nenhum prototipo do header do Khronos ficou de fora):

```
$ grep -oP '^GL_APICALL.*GL_APIENTRY \Kgl\w+' /opt/r36s/rootfs/usr/include/GLES3/gl32.h \
    | sort > /tmp/all.txt          # 358 nomes
$ grep -oP '^    X\(\Kgl\w+' plume_gles_gl.h | sort > /tmp/gen.txt   # 358 nomes
$ comm -23 /tmp/all.txt /tmp/gen.txt
(vazio)                            # 358/358 -- cobertura total
```

### 2.3 Design dos simbolos

Todos os ponteiros ficam em `namespace plume::gl` (nunca no escopo global), logo NAO
colidem com os simbolos reais de libGLESv2 caso o binario linke os dois. A carga usa
uma **lista X-macro** (`PLUME_GL_FUNCTIONS`), de modo que declaracao, definicao e carga
usam a mesma lista — e' impossivel esquecer de carregar um ponteiro:

```cpp
#define PLUME_GL_DEFINE_PTR(name) PFN_##name name = nullptr;
PLUME_GL_FUNCTIONS(PLUME_GL_DEFINE_PTR)

bool load(PlumeGLProcResolver resolver);   // nullptr => entra em missing()
```

---

## 3. Validacoes RAW executadas no host (sem GPU, sem sysroot, sem libGLESv2)

Propositalmente todas rodam no x86_64 sem o sysroot do device. Se o backend GLES
dependesse de headers de GLES/SDL, nenhuma destas provas seria possivel.

### 3.1 O carregador gerado compila sozinho

```
$ g++ -std=c++17 -Wall -Wextra -c plume_gles_gl.cpp -o /tmp/plume_gles_gl_host.o
HOST_COMPILE_RC=0
-rw-r--r-- 1 root root 260208 /tmp/plume_gles_gl_host.o
```

### 3.2 O header do backend compila contra a interface real do Plume

```
$ g++ -std=c++17 -fsyntax-only -I. -I/root/bhrecomp/lib/rt64/src/contrib/plume _hdr_check.cpp
(sem saida)   # 0 erros
```

### 3.3 Cobertura dos 113 metodos virtuais puros — provada por `static_assert`

Um metodo virtual puro nao sobrescrito NAO gera erro por si so: a classe apenas
permanece abstrata, e o erro so' aparece no primeiro `new`, muitas vezes no device.
`m2_hdr_coverage.cpp` transforma isso em erro de compilacao:

```
$ g++ -std=c++17 -fsyntax-only -I. -I/root/bhrecomp/lib/rt64/src/contrib/plume m2_hdr_coverage.cpp
(linhas de saida = 0)
```

22 assercoes `REQUIRE_CONCRETE` (todas as classes instanciaveis) + 1 `REQUIRE_ABSTRACT`
em `GLESPipeline` (base comum, que nao implementa `getName`/`getProgram`). **Isto
prova que o esqueleto cobre a interface inteira**, nao apenas que "compila".

### 3.4 A implementacao compila sem avisos

```
$ g++ -std=c++17 -fsyntax-only -Wall -Wextra -I. \
      -I/root/bhrecomp/lib/rt64/src/contrib/plume plume_gles.cpp
(sem saida)   # 0 avisos, 0 erros
```

---

## 4. Erros REAIS encontrados pela compilacao (e as correcoes)

Todos abaixo foram detectados por compilar contra os headers reais — nenhum foi
"achado na leitura". Registrados porque cada um e' uma armadilha de GLES 3.2 core:

| # | Erro | Causa medida | Correcao |
|---|---|---|---|
| 1 | `RenderPipelineType` inexistente | inventei o enum | Espelhei `MetalPipeline::Type` (enum aninhado `{Unknown,Compute,Graphics,Raytracing}`) + `GLESComputePipeline`/`GLESGraphicsPipeline` |
| 2 | `RenderSwapChain` com 14 metodos (eu tinha 10) | nomes supostos (`getCurrentTextureIndex`, `getHDRSupport`…) | Nomes reais: `acquireTexture`, `getWindow`, `isEmpty`, `getRefreshRate` |
| 3 | `RenderCommandListType::GRAPHICS` | enumerador inexistente | Os reais sao `UNKNOWN, DIRECT, COMPUTE, COPY` |
| 4 | `RenderBlendFactor` / `RenderStencilOperation` / `RenderMipmapFilter` | nomes inventados | Reais: `RenderBlend`, `RenderStencilOp`, `RenderMipmapMode` |
| 5 | `RenderTextureDesc::sampleCount` | campo inexistente | Real: `desc.multisampling.sampleCount` (+ `arraySize`, nao `layers`) |
| 6 | Structs do backend fora do namespace (`expected class-name`) | um `};` de fechamento foi inserido antes do fim | Reordenado o fechamento do namespace |
| 7 | **`GL_BGRA` nao existe** no gl32.h | ES 3.2 core nao tem BGRA | `B8G8R8A8_UNORM` removido do mapa e documentado (§4.1) |
| 8 | **`GL_RGBA16`, `GL_RG16`, `GL_R16`, `GL_RGBA16_SNORM` nao existem** | ES 3.2 core nao tem 16-bit UNORM | Formatos UNORM de 16 bits removidos do mapa e documentados (§4.1) |
| 9 | `RenderDeviceVendor::ARM` inexistente | o enum do Plume so' tem AMD/NVIDIA/INTEL/APPLE | `UNKNOWN` (o nome real do GPU segue em `description.name`) |

### 4.1 Achado tecnico novo (registrar para M3/M4)

Uma verificacao por grep no header do Khronos prova a ausencia das constantes:

```
$ grep -E '^#define (GL_RGBA16F|GL_RG16F|GL_R16F|GL_RGBA32F|GL_RG32F|GL_R32F|GL_R32UI|
    GL_R32I|GL_DEPTH32F_STENCIL8|GL_FLOAT_32_UNSIGNED_INT_24_8_REV|GL_DEPTH_COMPONENT32F|
    GL_DEPTH_COMPONENT16|GL_HALF_FLOAT|GL_BGRA|GL_RGBA16|GL_R16|GL_RG16|GL_RGBA16_SNORM|...) '
    plume_gles_gl.h | cut -d' ' -f2
GL_SRC_ALPHA_SATURATE GL_FUNC_SUBTRACT GL_FUNC_REVERSE_SUBTRACT GL_SHORT GL_INT
GL_UNSIGNED_INT GL_LEQUAL GL_NOTEQUAL GL_GEQUAL GL_INCR_WRAP GL_DECR_WRAP GL_CLAMP_TO_EDGE
GL_MIRRORED_REPEAT GL_DEPTH_COMPONENT16 GL_TEXTURE_3D GL_MIN GL_MAX GL_RGBA32F GL_RGBA16F
GL_TEXTURE_2D_ARRAY GL_DEPTH_COMPONENT32F GL_DEPTH32F_STENCIL8
GL_FLOAT_32_UNSIGNED_INT_24_8_REV GL_HALF_FLOAT GL_R16F GL_R32F GL_RG16F GL_RG32F GL_R32I
GL_R32UI GL_TEXTURE_2D_MULTISAMPLE
                        # ^ GL_BGRA, GL_RGBA16, GL_R16, GL_RG16, GL_RGBA16_SNORM e
                        #   GL_MIRROR_CLAMP_TO_EDGE NAO aparecem => nao existem no ES 3.2
```

**Consequencia para o porte:** `B8G8R8A8_UNORM` e os formatos UNORM de 16 bits (que o
RT64 usa em TMEM/framebuffer) **nao tem equivalente direto** em ES 3.2 core. O M3/M4
tera' que resolve-los com `GL_EXT_texture_norm16` (a confirmar no blob Mali) ou
downgrade explicito + swizzle de textura. Ate' entao, caem em `unimplemented()` —
**falha alta e nomeada, nunca estado GL silenciosamente errado**.

---

## 5. Estado exato: implementado vs. pendente

### 5.1 Implementado e verificado nesta sessao

- **Carregador** (358/358 entry points, 1006 constantes, 22 tipos) — compila no host.
- **`plume_gles.h` completo**: as 19 structs da interface, 22 classes concretas,
  cobertura provada por `static_assert`. Nenhum metodo virtual puro em falta.
- **Decisao de desenho: backend sem `#include <SDL.h>`.** A janela e a apresentacao
  entram por `GLESSwapChainFunctions` (4 ponteiros de funcao: `swapWindow`,
  `getWindowSize`, `setSwapInterval`, `getDisplayRefreshRate`) e os entry points GL
  entram por `GLESProcResolver`. Motivacao medida: o host x86_64 **nao tem**
  `/usr/include/SDL2/SDL.h` (so' o sysroot aarch64 tem) — sem esse shim, o backend
  deixaria de ser testavel fora do device, perdendo a disciplina do M1.3.
- **Tradutores `toGLES*`** com tabela unica `RenderFormat -> (externo, interno, tipo)`
  (garante que `toGLESFormat`/`toGLESInternalFormat`/`toGLESType` nunca divirjam).
- **`GLESInterface`** completa (fábrica `CreateGLESInterface`, `shaderFormat =
  GLSL_ES`).
- **`GLESDevice`**: carga dos entry points com falha nomeada, `queryContextInfo()`
  (versao/vendor/renderer/GLSL, lista de extensoes via `glGetStringi`, 9 limites
  consultados), `hasExtension()` por token (nao por `substr`), e as 17 capacidades
  de `RenderDeviceCapabilities` derivadas de medicao.
- **`unimplemented()`**: ponto unico de falha alta para tudo que ainda nao existe.
  Decisao explicita: no M2, um stub silencioso esconderia que o caminho testado nao e'
  o caminho real.

### 5.2 Pendente para fechar o M2 (estimativa: 2-3 sessoes)

1. **`GLESDevice::create*`** — reais: buffer/texture/sampler/framebuffer/fence/
   semaphore/queryPool, `createCommandQueue`; stubs altos: pipelines, pipelineLayout,
   descriptorSet, accelerationStructure, pool. Mais os getters de capacidade/descricao
   e `getSampleCountsSupported` (a partir de `GL_MAX_SAMPLES`).
2. **Recursos**: ctors/dtors de `GLESBuffer` (PBO/`glBufferData` + `glMapBufferRange`),
   `GLESTexture` (`glTexStorage2D`/`3D`/`2DMultisample`), `GLESSampler`
   (`glGenSamplers`/`glSamplerParameteri`), `GLESFramebuffer`, `GLESPipeline`
   (`glCreateProgram`/`glAttachShader`), `GLESDescriptorSet` (armazenamento para M3).
3. **`GLESCommandQueue` + `GLESCommandList`** em **modo imediato** (justificado no
   cabecalho: GL e' API de estado imediata; nao ha replay). Reais nesta etapa:
   `begin/end`, `setFramebuffer` (`glBindFramebuffer(0, ...)` para backbuffer),
   `clearColor`, `clearDepthStencil`, `setViewports`, `setScissors`. Resto: stub.
4. **`GLESSwapChain`**: `present` -> `swapFunctions.swapWindow`, `wait` -> `glFinish`,
   `resize`/tamanho via `swapFunctions.getWindowSize`, `setVsyncEnabled` ->
   `swapFunctions.setSwapInterval`, `getTexture(0)` -> textura "virtual" do
   backbuffer default (FBO 0), `acquireTexture`, `getRefreshRate`, `getWindow`.
5. **CMake**: opcao `RT64_GLES_BACKEND` (default OFF) em `lib/rt64/CMakeLists.txt` +
   `src/contrib/plume/CMakeLists.txt`, adicionando `plume_gles.cpp`,
   `plume_gles_gl.cpp` e a include dir de SDL2. GATE: builds DX/VK/MSL permanecem
   byte-identicos (mesma disciplina do M1.2/M1.3).
6. **`gles_smoke.cpp`** (aceite do M2): cria janela SDL + contexto ES 3.2, chama
   `CreateGLESInterface(window, SDL_GL_GetProcAddress, shim)`, `createDevice()`,
   loga capacidades, apresenta N frames (clear+swap) **pela interface `plume_gles`**.
7. **Build aarch64 + execucao sob QEMU** (`qemu-aarch64-static -L /opt/r36s/rootfs`),
   com `GL_KHR_debug` verificando ausencia de erro GL. Receita ja validada no M0
   (`evidencias/tools/gles_probe.c`, `evidence_gles_backend_recon_20261017.md`).

---

## 6. Riscos / observacoes registradas para os proximos marcos

- **R8 (NOVO, M3/M4):** ES 3.2 core **nao tem** `B8G8R8A8_UNORM` nem UNORM de 16 bits
  (§4.1). Isso atinge diretamente TMEM/framebuffer do RT64. Mitigacao a decidir:
  `GL_EXT_texture_norm16` (confirmar no blob) ou downgrade + `GL_TEXTURE_SWIZZLE_*`.
- **R9 (NOVO, M3):** sem `GL_MIRROR_CLAMP_TO_EDGE`; `RenderTextureAddressMode::
  MIRROR_ONCE` precisa de fallback explicito (hoje falha alto, por desenho).
- **R7 (herdado do M1.3):** ubershader gera ~260 KB de ESSL; custo de `spirv-cross`
  no Mali pode estourar o startup. Segue sendo decisao do M2 (etapa 2)/M6.
- **Modo imediato do command list** (5.2 item 3): correta para o aceite do M2; sera'
  reavaliada no M3, quando bindings/pipelines reais entrarem. Se o RT64 gravar e
  submeter listas de forma intercalada, sera' necessario um gravador real.
- **`getWindow()`** devolve `RenderWindow`, que no Linux sem `PLUME_SDL_VULKAN_ENABLED`
  e' a struct X11 `{Display*, Window}`. O swapchain GLES nao usa essa struct (usa
  `GLESSwapChainFunctions`); o retorno existe apenas para satisfazer a interface e
  deve ser revisado no M5 (integracao `GraphicsAPI::GLES`).