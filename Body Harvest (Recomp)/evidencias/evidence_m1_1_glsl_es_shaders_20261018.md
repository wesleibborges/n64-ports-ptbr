(`SPV_KHR_ray_tracing`) não existe em GLES — o backend GLES usa o caminho raster.

# EVIDÊNCIA — M1.1: conjunto de shaders GLSL ES 3.20 do RT64 (build-time)

- **Data**: 2026-10-18 · **Ambiente**: WSL x86_64 (Ubuntu jammy) + toolchain de shaders
  (DXC `x64` via `bin/arm64/dxc-linux` → symlink; `spirv-val`; `spirv-cross`; `glslangValidator`)
- **Objetivo**: fechar as **lacunas de perfil ES 320** remanescentes do M1 (13 falhas
  reportadas), produzindo o conjunto **GLSL ES 3.20** dos shaders do RT64 que **compila**
  (`glslangValidator`) — pré-requisito do backend `plume_gles`.
- **Pré-requisitos**: `evidence_m1_padding_applied_20261018.md` (padding de layout aplicado;
  `spirv-val` 13→0 e `spirv-cross --es --version 320` 10→0 nos 58 blobs).
- **Natureza desta etapa**: *ortogonal ao layout* — nenhum struct/offset foi tocado.

## 1. Correção do baseline: eram 10 falhas reais, não 13

O validador anterior (`m1_validate_blobs.py`) escolhia o estágio por **nome de arquivo**:

```python
RE_STAGE = re.compile(r'(CS|VS|PS|GS)(?:MS|2X|4X|8X)?\.hlsl\.spv$')
```

Esse regex **não casa** os nomes de variante (`RasterPSDynamic`, `RasterVSSpecConstant`, …),
e o fallback era `'frag'`. Consequência: os 3 vertex shaders `RasterVS*` foram validados como
**fragment** e o `glslangValidator` acusou `type requires declaration of default precision
qualifier` — erro **inexistente** para vertex shaders (em ESSL só o fragment shader exige
`precision` default).

Prova (revalidação com o estágio correto):

| shader | validação anterior (`-S frag`) | validação correta (`-S vert`) |
|---|---|---|
| `RasterVSDynamic` | 2 erros (`precision`) | **rc=0** |
| `RasterVSSpecConstant` | 2 erros (`precision`) | **rc=0** |
| `RasterVSSpecConstantFlat` | 2 erros (`precision`) | **rc=0** |

O novo harness (`m1_1_emit_glsl_es.py`) passa a derivar o estágio do **entry point do comando
DXC** (`-E PSMain|VSMain|CSMain|GSMain`), autoritativo e independente do nome do arquivo.

**Baseline honesto do M1.1: 10 falhas** (não 13).

## 2. Diagnóstico por causa raiz (10 falhas)

| # | Causa (`glslangValidator`) | Shaders | Causa raiz medida |
|---|---|---|---|
| 1 | `'usampler1D' : Reserved word` | 6× `RasterPS*` + `FbReinterpretCS` + `TextureDecodeCS` | `Texture1D<uint> gTMEM[8192]` e declarações locais 1D: **ESSL 3.20 não possui texturas 1D** |
| 2 | `'#extension' : extension not supported: GL_NV_gpu_shader5` | 6× `RasterPS*` | `NonUniformResourceIndex()` em `TextureSampler.hlsli` → DXC emite decoração `NonUniform`/capability `ShaderNonUniformEXT` → `spirv-cross` ES emite `#extension GL_NV_gpu_shader5 : require` |
| 3 | `'noperspective' : Reserved word` | `Im3DVS` | `noperspective float m_size : SIZE` em `Im3DCommon.hlsli`; **ESSL não tem `noperspective`** |
| 4 | `'image load-store format' : not supported with this profile: es` | `DebugPS` | `layout(..., rgba32f) uniform readonly image2D` (G-buffer do caminho RT) |

Sobreposição: os 6 `RasterPS*` têm as causas **1 e 2**; o `glslangValidator` para na primeira,
portanto a causa 1 estava mascarada neles.

### 2.1 Provas de perfil (probes `glslangValidator`, ESSL 320)

```
$ glslangValidator /root/bhrecomp/m1_1_probe/dynidx.frag      # uniform sampler2D gTextures[8192]; texelFetch(gTextures[idx], ...)
rc=0                       # indexacao DINAMICA de array de sampler e ACEITA em ESSL 320
$ glslangValidator /root/bhrecomp/m1_1_probe/tmemarray.comp   # uniform usampler2D gTMEM[8192]
rc=0                       # declaracao de array de 8192 samplers e ACEITA
$ glslangValidator /root/bhrecomp/m1_1_probe/img_nofmt.frag   # image2D SEM format qualifier
rc=0 (1 erro)              # 'image variables not declared 'writeonly' and without a format layout qualifier': not supported with this profile: es
```

**Consequência arquitetural (registrada para o M3)**: o array `gTextures[8192]`/`gTMEM[8192]`
**não** é bloqueio de sintaxe — é bloqueio de **binding/driver**: ESSL não tem descriptor
indexing e o Mali-G31 expõe ~16 unidades de textura por estágio. O array existe no shader,
mas o runtime não tem como preenchê-lo (ver `RenderDeviceCapabilities::descriptorIndexing`
em `plume_render_interface_types.h:1780`).

## 3. Adaptações de fonte (gated por `-D HLSL_GLES`)

Princípio de projeto: **o caminho DX/VK/MSL (compilado SEM `-D HLSL_GLES`) permanece
byte-idêntico**. As abstrações são macros e os `#ifdef HLSL_GLES` só trocam tipo/caminho.

| Arquivo | md5 antes | md5 depois |
|---|---|---|
| `lib/rt64/src/shared/rt64_hlsl.h` | `41ef45d02737d6e96ab97a9733324577` | `c85cabfd0af1b326417ab11b2f3dd4a4` |
| `lib/rt64/src/shaders/FbRendererCommon.hlsli` | `2b142b401c609db44e09d598814f0cdc` | `7bdaefcbc9a2cf4a3f11125a6ad3391e` |
| `lib/rt64/src/shaders/TextureDecoder.hlsli` | `2c68f0775d62bff9bfb6bf5be15f3e17` | `a2d2043a0b5bc98fbd66c4d9da846502` |
| `lib/rt64/src/shaders/FbReinterpretCS.hlsl` | `5d13d9647dad23dae73f8b569fdeb015` | `17540b5c9d7abf550120fc9d1efda977` |
| `lib/rt64/src/shaders/TextureDecodeCS.hlsl` | `1a79d08ef4633d59036ed08854ef1328` | `75fb99cf9a02960cd47ca48665ede803` |

Núcleo da adaptação (`shared/rt64_hlsl.h`, **dentro do ramo não-`HLSL_CPU`** — o host C++ não é afetado):

```hlsl
#ifdef HLSL_GLES
// ESSL 3.20 nao possui texturas 1D nem descriptor indexing. O array de palavras
// de TMEM (1D de uint32) passa a ser ligado como textura 2D de altura 1, e o
// NonUniformResourceIndex passa a ser identidade (elimina a capability
// ShaderNonUniformEXT e a `#extension GL_NV_gpu_shader5` espuria).
#define TMEMTexture Texture2D<uint>
#define tmemLoadTMEM(textureObject, wordIndex) (textureObject).Load(int3(int(wordIndex), 0, 0))
#define NonUniformResourceIndex(index) (index)
#else
#define TMEMTexture Texture1D<uint>
#endif
```

Usos ajustados ao tipo abstrato `TMEMTexture`: `gTMEM[8192]` (`FbRendererCommon.hlsli`),
`gInputTLUT`/`TMEM` locais (`FbReinterpretCS.hlsl`), `TMEM` (`TextureDecodeCS.hlsl`) e os
parâmetros de `implLoadTMEM`/`sampleTMEM` (`TextureDecoder.hlsli`, que também ganhou o branch
GLES em `loadTLUT`).

**Prova de causa-raiz resolvida na fonte** (não pelo sanitizador): o output **cru** do
`spirv-cross --es --version 320` para `RasterPSDynamic` tem **0** ocorrências de
`GL_NV_gpu_shader5`, `usampler1D` e `NonUniformResourceIndex`, e o TMEM passou a ser:

```glsl
uniform highp usampler2D SPIRV_Cross_CombinedgTMEMSPIRV_Cross_DummySampler[8192];
...
texelFetch(SPIRV_Cross_CombinedgTMEMSPIRV_Cross_DummySampler[...textureIndex], ivec3(int(...), 0, 0).xy, 0);
```

## 4. Sanitizador do output ES (`sanitize()` em `m1_1_emit_glsl_es.py`)

Três correções de artefato do codegen (não existe opção upstream no `spirv-cross`):

| Ação | Ocorrências | Por quê |
|---|---|---|
| `nv-ext-stripped` | 0 (guarda defensiva) | causa-raiz já resolvida na fonte (§3) |
| `noperspective-removed` | 1 (`Im3DVS`) | ESSL não tem `noperspective`; vira `smooth` (impacto só no overlay de debug do im3d) |
| `precision-mediump->highp` | 29 | `spirv-cross --es` emite `precision mediump float;`; RT64 assume fp32 no raster (mediump = fp16 no Mali-G31 degradaria coordenadas de textura/depth). Ocorre em **todos** os 29 fragment shaders do conjunto |

## 5. Exclusão explícita: `DebugPS`

`DebugPS` é o shader de **debug do caminho de ray tracing** (G-buffer: `gShadingNormal`,
`gTransparent`, `gFlow`, `gReactiveMask`, `gLockMask`, …) com ~20 `image2D` nos bindings 47–66.
O probe da §2.1 mostra que o perfil ES rejeita `image2D` **tanto com** format qualifier
(`rgba32f`) **quanto sem**. Portanto `DebugPS` é **inexpressável em ESSL 3.20** e foi
**excluído do conjunto GLES** (`EXCLUDE` no emissor). Justificativa adicional: o caminho RT
(`SPV_KHR_ray_tracing`) não existe em GLES — o backend GLES usa o caminho raster.

## 6. Resultado (aceite do M1.1 atingido)

```
RESUMO M1.1: shaders=57 | excluidos=1 | glslang OK=57 | glslang FALHAS=0
```

| Métrica | Valor |
|---|---|
| Shaders no conjunto GLES | **57** (58 − `DebugPS` excluído) |
| `glslangValidator` (`#version 320 es`, estágio correto) | **57 OK / 0 falhas** (antes: 10) |
| `spirv-val --target-env vulkan1.0` (blobs GLES) | 57 OK / 0 falhas |
| `spirv-cross --es --version 320` | 57 OK / 0 falhas |
| Estágios | 29 `frag` · 22 `comp` · 6 `vert` |

Ações do sanitizador (agregado sobre o conjunto completo de 58): **27** arquivos sem ação,
**29** `precision-mediump->highp` (todos os 29 fragment shaders do conjunto GLES),
**1** `noperspective-removed` (`Im3DVS`), **0** `nv-ext-stripped` (causa-raiz resolvida na fonte).

> Nota: a coluna `sanitize_acoes` do `validacao_gles.tsv` registra apenas os shaders efetivamente
> (re)gerados naquela execução (o script é resumível) — o agregado acima é do conjunto completo.

### 6.1 Auditoria independente do conjunto emitido

Executada por `grep` direto nos 57 arquivos (não pelo relatório do script):

```
arquivos: 57
com GL_NV_gpu_shader5      : 0
com usampler1D             : 0
com noperspective          : 0
com precision mediump float: 0
usampler2D (TMEM abstract) : 10
```

| Artefato | Valor |
|---|---|
| md5 agregado do conjunto GLSL ES | `b43d307153562d59f0c9a427808c68d4` |
| Tamanho total do GLSL ES (texto) | 3.468.724 bytes |
| Tamanho total do SPIR-V (GLES) | 1.571.200 bytes |
| Maior arquivo | `RasterPSSpecConstantFlatMS.hlsl.glsl` = **704.897 bytes** |

## 7. Prova de NÃO-REGRESSO do caminho DX/VK/MSL

`m1_1_emit_glsl_es.py regress` recompila os **58** blobs **sem** `-D HLSL_GLES` (comandos DXC
exatos do `build.ninja`) e compara `md5` com os blobs reais embutidos no binário:

```
RESUMO REGRESS: identicos=58 divergentes=0 falhas=0
```

Conclusões verificadas:

1. As adaptações de fonte são **100% transparentes** para DX/VK/MSL (blobs byte-idênticos).
2. `shared/rt64_hlsl.h` foi alterado apenas **dentro do ramo não-`HLSL_CPU`** → o build do
   **host C++** (`HLSL_CPU`) não é afetado.
3. O binário aarch64 do M1 (`BodyHarvestRecompiled.m1_padding_20261018`,
   md5 `13b708c21762bff9e183c494512e5776`) **continua válido** — os 58 blobs embutidos nele
   são idênticos aos reconstruídos. **Nenhum rebuild foi necessário nesta etapa.**

## 8. Limitações e itens abertos (não bloqueiam a conclusão do M1.1)

| # | Item | Situação |
|---|---|---|
| 1 | **Descriptor arrays em GLES** (`gTextures[8192]`, `gTMEM[8192]`) | **Não resolvido.** Os probes da §2.1 provam que é sintaticamente válido em ESSL 320, mas ESSL **não tem descriptor indexing** e o Mali-G31 expõe ~16 unidades de textura/estágio → o array **não pode ser preenchido em runtime**. Escopo do M3 |
| 2 | **Tamanho do ubershader** | O maior GLSL ES tem **704.897 bytes**. GLES compila shader em **runtime** (`glShaderSource`/`glCompileShader`), ao contrário de Vulkan/D3D12 → compilar isso no Mali-G31 é inviável **sem especialização**. O RT64 já possui o mecanismo: `rt64_raster_shader.h:13` inclui `re-spirv/re-spirv.h`, guarda `respv::Shader rasterVS/rasterPS/rasterPSMS/...` (`rt64_raster_shader.h:28-35`) e especializa via `respv::Optimizer::run(Shader, const SpecConstant*, count, std::vector<uint8_t>&, Options)` (`contrib/re-spirv/re-spirv.h:128`), com o cache inicializado em `rt64_raster_shader_cache.cpp:108`. Ver decisão de arquitetura no plano |
| 3 | Integração no build (`RenderShaderFormat::GLSL_ES`, `CREATE_SHADER_INPUTS`, CMake) | Não iniciada (M1.2) |
| 4 | Compilação real no **driver Mali** (`glCompileShader`) | Não testada — requer device (R36S) |
| 5 | `DebugPS` excluído | Por design (§5) |
| 6 | Precisão `mediump → highp` | Desvio deliberado do default do `spirv-cross --es`; **não validado em device** |

### 8.1 Custo medido da conversão SPIR-V → GLSL ES (`spirv-cross`)

Medição no host (AMD Ryzen 7 PRO 3700U), comando exato do pipeline
(`spirv-cross --es --version 320 <in> --output <out>`):

| SPIR-V de entrada | GLSL ES de saída | Tempo |
|---|---|---|
| `FullScreenVS` — 860 B | 350 B | **7 ms** |
| `FbWriteColorCS` — 15.448 B | 8.557 B | **11 ms** |
| `RasterPSSpecConstantFlatMS` (ubershader) — 285.308 B | 704.899 B | **142 ms** |

Interpretação (a ser confirmada em device): mesmo o **ubershader completo** converte em 142 ms
no host; um shader **já especializado** é ~10-50× menor, portanto a conversão em runtime no
R36S (Cortex-A35, ~5-10× mais lento) deve ficar na casa de **dezenas de ms**. Isso sustenta a
recomendação do Passo 2 do plano (*especializar → converter*), em contraste com o custo de
deixar o compilador GLSL do Mali processar 688 KB de fonte.

## 9. Artefatos

| Item | Caminho |
|---|---|
| Conjunto GLSL ES 3.20 (57) | `/root/bhrecomp/m1_1_gles/glsl/*.hlsl.glsl` |
| SPIR-V GLES (`-D HLSL_GLES`) | `/root/bhrecomp/m1_1_gles/spv/*` |
| SPIR-V regressão (sem a macro) | `/root/bhrecomp/m1_1_gles/regress/*` |
| Tabela de validação (58 linhas) | `/root/bhrecomp/m1_1_gles/validacao_gles.tsv` |
| Resultado do não-regresso | `/root/bhrecomp/m1_1_gles/regress_dx.tsv` |
| Backup dos 5 fontes | `/root/bhrecomp/m1_1_gles/backup_src/` (+ `md5_src_backup.txt`, `md5_src_after.txt`) |
| Probes de perfil ESSL | `/root/bhrecomp/m1_1_probe/{dynidx.frag,tmemarray.comp,img_nofmt.frag,nvext.frag}` |
| Logs | `/root/bhrecomp/m1_1_gles/{emit_gles.log,regress.log}` |
| Scripts | `evidencias/tools/m1_1_apply_gles_macros.py`, `evidencias/tools/m1_1_emit_glsl_es.py` |

## 10. Comandos de reprodução

```bash
# 1) aplica as adaptacoes gated por HLSL_GLES (backup + md5)
python3 ".../evidencias/tools/m1_1_apply_gles_macros.py" apply

# 2) emite + valida o conjunto GLSL ES 3.20 (resumavel)
python3 ".../evidencias/tools/m1_1_emit_glsl_es.py" gles --workers 8

# 3) prova de nao-regresso do caminho DX/VK/MSL (58/58 md5 identicos)
python3 ".../evidencias/tools/m1_1_emit_glsl_es.py" regress --workers 8

# 4) reverter os fontes
python3 ".../evidencias/tools/m1_1_apply_gles_macros.py" revert
```

> Nota de runner: `run_commands` encerra a sessão em ~30 s; os passos 2/3 foram executados
> destacados (`setsid nohup ... > log 2>&1 < /dev/null &`) e acompanhados por `tail`.

## 11. Conclusão (fatos verificados)

1. As **13 falhas** de `glslangValidator` reportadas no M1 eram, na verdade, **10 reais** + 3
   falsos-positivos do estágio derivado por regex no validador (§1).
2. As 10 falhas reais tinham **4 causas-raiz** distintas, todas identificadas por atribuição de
   mensagem e **comprovadas por probes** de perfil ESSL (§2).
3. As causas 1 e 2 foram corrigidas **na fonte** (gated por `HLSL_GLES`), não por
   pós-processamento: o output **cru** do `spirv-cross` já não contém `usampler1D` nem a
   extensão NV (§3).
4. O conjunto **GLSL ES 3.20 de 57 shaders compila em `glslangValidator` com 0 falhas** (§6),
   com auditoria independente por `grep` (§6.1).
5. As adaptações **não alteram** o caminho DX/VK/MSL: **58/58 blobs md5-idênticos** (§7) —
   o binário do M1 permanece válido e **nenhum rebuild foi necessário**.
6. Restam itens **arquiteturais** (descriptor arrays/bindless; especialização em runtime do
   ubershader de 688 KB; integração de build) que definem o escopo real do backend GLES —
   registrados em `docs/PLANO_BACKEND_GLES_R36S.md` e na §8.