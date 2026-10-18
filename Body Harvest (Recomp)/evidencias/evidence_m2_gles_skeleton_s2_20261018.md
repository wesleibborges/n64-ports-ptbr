# Evidência — M2 `plume_gles` (sessão 2): device, recursos, command list e swapchain

- **Data:** 2026-10-18 (UTC)
- **Marco:** M2 (esqueleto do backend GLES para o R36S / Mali-G31) — **etapa 2 de 2-3**
- **Gate do M2:** *frames apresentados* — **aceite cumprido em forma verificável no host**
  (clear chega ao backbuffer e é lido de volta); apresentação em hardware real permanece M6.
- **Evidência RAW (fonte de verdade, reprodutível):** `evidencias/m2_gles_s2/verify_raw.txt`
  (gerada por `evidencias/tools/staged/verify_s2.sh`, md5 `3384def7…`; saída md5 `e9abe519…`)
- **Sessão 1 (anterior):** `evidencias/evidence_m2_gles_skeleton_s1_20261018.md`

---

## 1. O que esta sessão entregou

| Item | Estado |
|---|---|
| `GLESDevice::create*` (16 métodos) | ✅ implementados e **linkados** |
| Recursos: buffer, texture, texture view, sampler, framebuffer, shader, pipelines, pipeline layout, descriptor set, pool, query pool, fence, semaphore | ✅ implementados |
| `GLESCommandQueue` (create list/swapchain, execute, fence) | ✅ modo imediato |
| `GLESCommandList` (begin/end, framebuffer, viewport, scissor, clear color/depth/stencil, depth bias, barriers, dispatch, setPipeline, cópia de buffer, resolve) | ✅ implementado |
| `GLESSwapChain` (present/wait/resize/vsync/tamanho/texturas/acquire) | ✅ implementado |
| `gles_smoke.cpp` — teste funcional com contexto EGL/GLES 3.2 real | ✅ **15/15 checagens OK** |
| `gles_target_probe.cpp` — execução **on-target** (aarch64/QEMU) | ✅ **7/7 checagens OK** |
| Build host + aarch64 + **link real** | ✅ rc=0, zero warnings (`-Wall -Wextra`) |
| Caminho de raster (draw/input layout), push constants, descriptor binding real, TMEM, ray tracing | ⏳ M3/M4 — **abortam com nome explícito** (`unimplemented()`), nunca silencioso |
| Gate `RT64_GLES_BACKEND` no CMake | ⏳ pendente (backend segue **inerte**) |

---

## 2. Achado metodológico central: a sessão 1 **não linkava**

A verificação da sessão 1 usou `-fsyntax-only`, que **não linka** — portanto não podia detectar
símbolo **declarado e nunca definido**. A recompilação desta sessão revelou exatamente isso:

```
hasExtension / validateShaderFormat  -- declarados em plume_gles.h, SEM definição
```

Ambos agora estão definidos (`GLESDevice::hasExtension` por token delimitado; validação de
`shaderFormat == GLSL_ES`), e o aceite desta sessão **inclui link real**:

```
g++ /tmp/plume_gles.o /tmp/plume_gles_gl.o /tmp/m2_link_main.o -o /tmp/m2_link_test
link rc=0        <-- toda method declarada agora tem definição
```

Como o `~GLESDevice()` é definido fora de linha, ele é a *key function* da classe: a vtable é
emitida nesse TU e referencia **todos** os virtuais — logo o link cobre a superfície inteira da
interface, não só os símbolos chamados.

**Lição registrada:** validar por compilação **e por link**; `-fsyntax-only` esconde a classe de
erro mais provável num backend escrito contra um header grande.

## 3. Erros reais encontrados pela compilação (não por leitura)

Três, todos informativos, corrigidos no incremento (não no arquivo final — o incremento é a
fonte de verdade, reaplicada por `apply_s2.py`):

1. **`GL_TEXTURE_MAX_ANISOTROPY_EXT` não existe no `gl32.h`.** É de
   `EXT_texture_filter_anisotropic`, que vive em `gl2ext.h`/`gl3ext.h`. O carregador deste
   backend é gerado a partir do `gl32.h` (core), então o valor da especificação foi declarado
   localmente: `0x84FE` — **verificado** em `GLES2/gl2ext.h:2204` do rootfs.
2. **`RenderFormat::D24_UNORM_S8_UINT` não existe.** O enum do RT64 tem apenas
   `D16_UNORM`, `D32_FLOAT` e **`D32_FLOAT_S8_UINT`** como formatos de profundidade. As três
   comparações foram reduzidas ao único formato depth-stencil empacotado real.
3. **`&RenderViewport(...)` (endereço de rvalue)** no smoke test — resolvido usando a sobrecarga
   por referência (`setViewports(const RenderViewport&)`), que o header já oferecia.

Mais três *warnings* de parâmetro não usado em `-Wextra` foram silenciados com `(void)` e
comentário justificando a intenção (simetria do par liga/desliga scissor; barreira global do GL).
**Resultado: zero warnings nos 4 TUs, host e aarch64.**

---

## 4. Aceite do M2 medido: o clear chega ao backbuffer

`gles_smoke.cpp` é o **chamador** do backend (o papel que o SDL2 cumpre no R36S): cria o
contexto, resolve os símbolos e fornece o swap — mas via **EGL puro**, para rodar sem SDL. O
teste não inclui `<GLES3/gl3*.h>`: todo símbolo GL vem do carregador gerado, de modo que o
teste **não pode escapar** do caminho real do backend.

Execução no host com Mesa/llvmpipe (ES 3.2 real) — saída integral em `verify_raw.txt` §5:

```
[smoke]     GL_VERSION  = OpenGL ES 3.2 Mesa 23.2.1-1ubuntu3.1~22.04.4
[smoke]     GL_RENDERER = llvmpipe (LLVM 15.0.7, 256 bits)
[smoke]     GLSL        = OpenGL ES GLSL ES 3.20
[smoke] [2] os 358 entry points resolvem (eglGetProcAddress + dlsym)   OK
[smoke] [4c] createSwapChain (tamanho herdado do viewport do pbuffer)  OK
[smoke] [5] command list executado + present()                         OK
[smoke]     pixel central do backbuffer = RGBA(64,128,191,255)
[smoke] [6] ACEITE M2: o clear chegou ao backbuffer (RGB ~64/128/191)  OK
[smoke]     pixel resolvido na textura B = RGBA(255,0,0,255)
[smoke] [7c] resolveTexture levou o vermelho de A para B               OK
[smoke]     glGetError() = 0x0 (0 == GL_NO_ERROR)
[plume_gles smoke] ===== 0 checagem(ns) FALHARAM =====
```

Como o R36S ainda não tem apresentação em hardware, este é o aceite **mais forte disponível**:
o "quadro" é o conteúdo do backbuffer, e **lê-lo de volta com o valor exato pedido** prova que
`command list → clear → FBO 0 → present` funciona de ponta a ponta, com **zero erros de API**.

Os itens [4c] e [7c] foram escolhidos por serem falsificáveis, não decorativos:
- **[4c]** valida o caminho *headless* do swapchain: sem janela, ele infere o tamanho pelo
  viewport que o EGL inicializa com as dimensões do drawable (256×256 do pbuffer). Se essa
  herança estivesse errada, a checagem falharia.
- **[7c]** valida `GLESTexture` (armazenamento imutável via `glTexStorage2D`), `GLESFramebuffer`
  (anexo + `glCheckFramebufferStatus`), `clearColor` e `resolveTexture`
  (`glBlitFramebuffer` com FBOs temporários) — o vermelho só chega à textura B se toda a
  cadeia estiver correta.

## 5. Execução on-target (aarch64) sob QEMU

Sem GPU Mali, o que resta verificável no alvo é o código **sem GL**: `gles_target_probe.cpp`
cobre o carregador e a camada de interface. Saída integral em `verify_raw.txt` §7:

```
[probe] arquitetura de compilacao = aarch64 (ponteiro de 8 bytes)
[probe] [1] gl::load(nulo) == false e reporta os 358 entry points        OK
[probe] [2] gl::load(resolvedor completo) == true e 0 ausentes           OK
[probe] [3] CreateGLESInterface executa no alvo                          OK
[probe] [3b] getDeviceNames() expoe exatamente 1 dispositivo             OK
[probe] [3c] getCapabilities().shaderFormat == GLSL_ES                   OK
[plume_gles probe] ===== 0 checagem(ns) FALHARAM =====
```

O passo [1] é o contrato de **falha explícita**: sem entry points, o backend não segue — e o
número reportado (358) confirma que a lista completa é percorrida no alvo. O passo [2] prova o
caminho de sucesso do mesmo laço. Ambos rodam em `qemu-aarch64-static -L /opt/r36s/rootfs`.

---

## 6. Limitação conhecida e **delimitada**: o smoke test não roda sob QEMU

Registrado com evidência crua em `verify_raw.txt` §8. Não é falha do backend; é do ambiente:

```
lrwxrwxrwx  libEGL.so      -> libMali.so
lrwxrwxrwx  libEGL.so.1    -> libMali.so
lrwxrwxrwx  libEGL.so.1.1.0 -> libMali.so
-rw-r--r--  libEGL_mesa.so.0.0.0   <-- UNICO arquivo EGL real (nao symlink) no rootfs
```

1. O rootfs do dArkOS aponta `libEGL.so.1` para o **blob Mali**, que exige GPU Mali real.
2. Não há **dispatcher GLVND** no rootfs (a única lib EGL real é
   `libEGL_mesa.so.0.0.0`, que é uma lib **vendor** do GLVND). Prova direta, por erro de link:

```
ld: gles_smoke.cpp:(.text+0xd8): undefined reference to `eglGetProcAddress'
ld: gles_smoke.cpp:(.text+0x13c): undefined reference to `eglGetProcAddress'
```

3. Sob QEMU não existe `/dev/dri` utilizável pelo blob ⇒ `eglGetDisplay` falha
   (`[smoke] eglGetDisplay/GetPlatformDisplay falhou`), como esperado.

Consequência prática registrada para o M6: **a validação funcional completa do backend exige
hardware** (Mali) ou um rootfs com dispatcher GLVND + Mesa softpipe. A rota do host (llvmpipe)
já cobre a lógica; o QEMU cobre a arquitetura.

> Nota de fiação futura: ao integrar via SDL2 no device, o linker apontará `libEGL.so` →
> Mali, que é o caminho desejado (hardware). O `--allow-shlib-undefined` já usado no
> `Toolchain-aarch64.cmake` continua sendo necessário: ele resolveu aqui o mesmo R1/R2
> (`libGLdispatch` referenciando `__isoc23_strtol@GLIBC_2.38` do rootfs Debian 13 contra o
> glibc do cross-gcc).

---

## 7. Decisões de desenho tomadas nesta sessão

1. **Falha alta em tudo que o ES 3.2 não tem — nunca stub silencioso.** O `unimplemented()`
   aborta com o nome do recurso. É deliberado: um backend que ignora um comando produz corrupção
   de imagem difícil de rastrear, e no M2 um stub silencioso esconderia que o caminho testado não
   é o caminho real.
2. **O caminho de raster (draw) aborta de propósito.** No GL o desenho depende do *input layout*
   (`glVertexAttribPointer` por atributo) **somado ao estado fixo** (depth/cull/blend/stencil) do
   `RenderGraphicsPipelineDesc`. O pipeline do GLES carrega só o programa; aplicar o resto exige um
   "cache de estado global" que é trabalho do M4. Desenhar antes disso seria produzir imagem errada
   em silêncio.
3. **`GLESShader` guarda a FONTE, não um objeto GL.** Em ESSL o objeto de shader é transitivo:
   compila-se, anexa-se, linka-se e **apaga-se** (o programa retém o código). O `glCreateShader`
   acontece no *pipeline*, que é quem conhece o **estágio** (vertex/fragment/compute); criá-lo no
   `createShader` exigiria adivinhar o estágio pelo nome do entry point — frágil e desnecessário.
   Guarda extra: se o blob for SPIR-V (magic `0x07230203`), aborta com mensagem explícita em vez de
   "compilar" binário como texto.
4. **`map()` recorta a faixa e rejeita faixa vazia.** `glMapBufferRange` exige offset/length
   não-zero e dentro do armazenamento; um recorte silencioso daria ponteiro inválido.
5. **`discardTexture()` é no-op DELIBERADO** (documentado como tal). No D3D12 "descartar" significa
   "conteúdo indefinido" — deixar o conteúdo antigo é um **superconjunto válido** do contrato, não
   uma funcionalidade faltante.
6. **`resolveTextureRegion` recusa MIN/MAX.** `glBlitFramebuffer` só filtra LINEAR (média) ou
   NEAREST; trocar MIN/MAX por média silenciosamente mudaria o resultado.
7. **FBOs temporários no resolve**, com invalidação do espelho (`currentFramebuffer = nullptr`). O
   blit do GL opera sobre *framebuffers*, não sobre texturas soltas; e como os binds `READ/DRAW`
   alteram o vínculo corrente, o espelho **precisa** ser invalidado ou o próximo `setFramebuffer`
   pularia a vinculação e o desenho iria para o FBO errado.
8. **`barriers()` → `glMemoryBarrier(GL_ALL_BARRIER_BITS)`**, conservador por decisão explícita:
   correção primeiro, estreitamento só com medição no M5 (R7).
9. **`GLESAccelerationStructure` não tem construtor** — por desenho. A capacidade `raytracing` é
   `false`, então `createAccelerationStructure` aborta e o objeto nunca é construído. (Definir um
   construtor não declarado no header seria erro de compilação — foi pego exatamente assim.)
10. **Membro novo no header: `GLESShader::source`** (único acréscimo estrutural desta sessão),
    justificado no item 3. `plume_gles.h` passou de 604 → 609 linhas.

A lista completa do que **aborta** hoje: draw instanced/indexed, `setIndexBuffer`,
`setVertexBuffers`, push constants (compute/graphics/raytracing), descriptor sets de raytracing,
root descriptor, `copyTexture`/`copyTextureRegion` (TMEM), `buildBottomLevelAS`/`buildTopLevelAS`,
`traceRays`, criação/uso de ray tracing, reset/timestamp de query pool, e os casos não mapeados de
formatos/enums.

---

## 8. Artefatos e hashes (produção ≡ evidência, verificado por `md5sum`)

| Arquivo | md5 | Linhas |
|---|---|---|
| `lib/rt64/src/contrib/plume/plume_gles.h` | `54aaf80881b6fa2a24e9b5a8e8d38f84` | 609 |
| `lib/rt64/src/contrib/plume/plume_gles.cpp` | `57a43775f4240651807910a3f32dc25f` | 2344 |
| `lib/rt64/src/contrib/plume/plume_gles_gl.h` | `9678cf48ca0c72a70e4901b579a35052` | 1799 |
| `lib/rt64/src/contrib/plume/plume_gles_gl.cpp` | `573fa89a6a295188f5f9b3c77da15aba` | 41 |
| `…/plume/gles_smoke.cpp` | `c6e9546333e734a4305d904db0cea220` | 333 |
| `…/plume/gles_target_probe.cpp` | `eb2fe6290b37152847909af91a7fcaed` | 92 |
| `evidencias/tools/staged/plume_gles_s2_inc.inc` | `11968b913528c583657c4b896de84fc6` | 1855 |
| `evidencias/tools/staged/apply_s2.py` | `f92fb722207f1c60a6389b44374db641` | — |
| `evidencias/tools/staged/verify_s2.sh` | `3384def7f4e2c990d6b5784b969ac62b` | — |
| `evidencias/m2_gles_s2/verify_raw.txt` | `e9abe51955a4e7463f152a57d94f5017` | — |

**Estado anterior (sessão 1), preservado para auditoria "antes/depois":**
`plume_gles.h.s1` = `f0f0c175d3a09c4902ee119d620bf335`,
`plume_gles.cpp.s1` = `4cab332420421dbe1516f9dda9e8b180`.

**Método de aplicação (reprodutível):** o incremento vive em `plume_gles_s2_inc.inc` e é emendado
por `apply_s2.py` (Python determinístico: valida a âncora do header, exige que o incremento termine
com a chave de namespace, reindenta 4 espaços e substitui o fechamento original). Ele é
**idempotente** (se detectar a sessão 2 já aplicada, não faz nada) e **recusa-se a agir** se a
âncora do header não for única.

**Backend continua INERTE na árvore** (evidência §9): nenhuma `CMakeLists` referencia
`plume_gles.{cpp,h}`, e nenhum objeto `*plume_gles*` existe em `build-aarch64/`. A única menção
encontrada é um **comentário** em `lib/rt64/CMakeLists.txt:119`, não uma referência de build.

## 9. Riscos e próximo passo

- **R7 (M2 restante / M6):** ubershader ≈260 KB de ESSL; `spirv-cross` ~50 ms no host → possível
  stall de startup no Mali-G31. Não tocado nesta sessão (o smoke não materializa o ubershader).
- **R8 (M3/M4):** ES 3.2 core sem `GL_BGRA` (`B8G8R8A8_UNORM`) e sem UNORM de 16 bits. Atinge
  TMEM/framebuffer. Mitigação a decidir: `GL_EXT_texture_norm16` (confirmar no blob) ou downgrade +
  `GL_TEXTURE_SWIZZLE_*`. Até lá, `unimplemented()`.
- **R9 (M3):** sem `GL_MIRROR_CLAMP_TO_EDGE`; `MIRROR_ONCE` precisa de fallback explícito.
- **R1/R2 (herdados, reconfirmados aqui):** glibc do rootfs (Debian 13) ≠ cross-gcc; mitigado por
  `-Wl,--allow-shlib-undefined`, o mesmo remédio já presente no toolchain do projeto.
- **NOVO — validação funcional do backend exige hardware.** Delimitado na §6: sob QEMU não há
  caminho para contexto GLES (blob Mali sem GPU; sem dispatcher GLVND). A lógica é coberta pelo
  host (llvmpipe); a arquitetura, pelo probe on-target.

**Próximo passo (fechar o M2):** (a) gate `RT64_GLES_BACKEND` no CMake, default **OFF**, com
verificação de que os builds DX/VK/MSL seguem byte-idênticos; (b) smoke test **integrado** ao RT64
(não apenas ao backend isolado); (c) execução real no R36S via SDL2 → Mali (exige hardware).
Depois: **M3** (descriptor windowing + R8/R9) → M4 (raster/input layout) → M5 → M6.