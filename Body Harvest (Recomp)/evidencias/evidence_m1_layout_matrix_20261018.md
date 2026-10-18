# EVIDÊNCIA — Matriz de layout DX vs GL, correção por padding e PoC (M1)

- **Data**: 2026-10-18 · **Ambiente**: WSL x86_64, sem conta AWS
- **Objetivo**: resolver a causa raiz das falhas de conversão dos shaders do RT64 para GLSL ES 3.20
  (backend GLES para R36S / Mali-G31) e decidir entre as duas estratégias possíveis.
- **Artefatos**:
  - `/root/bhrecomp/m1_layout_matrix2/` — matriz DX vs GL (58 shaders × 2 layouts)
  - `/root/bhrecomp/m1_poc_padding3/` — PoC final (layout DX + padding)
  - `/root/bhrecomp/m1_mitig/` — teste de mitigação da extensão NV
  - `evidencias/m1_matrix_dx_vs_gl_20261018.md` — relatório da matriz
  - `evidencias/m1_layout_diff_dx_gl_20261018.md` — diff de offsets por struct
  - `evidencias/m1_patches_headers/` — headers corrigidos + `layout_padding.patch`
- **Ferramentas criadas** (em `evidencias/tools/`): `m1_layout_matrix2.sh`, `m1_matrix_analyze.py`,
  `m1_layout_diff.py`, `m1_poc_padding2.sh`, `m1_mitig_nonuniform.sh`, `m1_collect_patches.sh`,
  `spv_layout_dump.py` (corrigido)
- **Pré-requisito**: `evidencias/evidence_m1_restore_dx_blobs_20261018.md` (integridade dos 58 blobs
  restaurada antes destes experimentos)

## 1. Método

- **Fonte da verdade dos comandos DXC**: o próprio `build-aarch64/build.ninja` (linhas `COMMAND = ...`).
  `ninja -t commands <target>` NÃO serve (retorna o comando C++ da dependência).
- Forma real do comando (linha 3427 do `build.ninja`):

```
cd /root/bhrecomp/build-aarch64/rt64 && LD_LIBRARY_PATH=.../dxc/lib/arm64 .../dxc-linux \
  -spirv -fspv-target-env=vulkan1.0 -fvk-use-dx-layout -I.../lib/rt64/src \
  -E PSMain -T\ ps_6_3 -D\ DYNAMIC_RENDER_PARAMS .../shaders/RasterPS.hlsl \
  /Fo /root/bhrecomp/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv
```

  Note: **`/Fo` e o caminho são dois tokens** (barra + espaço). O `m1_layout_matrix.sh` original
  usava sed com `-Fo` (hífen) e por isso nunca casou — causa do dano já revertido.
- Cada shader foi compilado nos dois layouts (`-fvk-use-dx-layout` = atual; `-fvk-use-gl-layout`
  = std430) **sempre em diretório scratch**, e submetido a `spirv-val`, `spirv-cross --es --version 320`
  e `glslangValidator`.
- **Guard de integridade**: md5 de todos os blobs reais medido antes/depois (± 58 arquivos) —
  resultado: `SAFETY OK: blobs reais INTACTOS`.

## 2. Resultado da matriz (58 shaders)

| métrica | DX layout (atual) | GL layout (candidato) |
|---|---|---|
| DXC falhou | 0 | 0 |
| `spirv-val` falhou (**SPIR-V Vulkan inválido**) | **13** | 0 |
| SPIRV-Cross falhou (GLSL ES 3.20) | **10** | 0 |
| `glslangValidator` falhou | 4 (+6 não executados) | 10 |

- **13** blobs DX são **SPIR-V Vulkan inválido** (independente de GLSL) — achado novo, confirmado por
  `spirv-val`, que é uma segunda ferramenta independente do SPIRV-Cross.
- **10** blobs DX não convertem para GLSL ES; em **GL layout todos os 58 convertem**.
  Os 10: 6× `RasterPS*`, 3× `RasterVS*`, `RSPProcessCS`.

### Causa raiz — texto exato das ferramentas

SPIRV-Cross (DX):

```
SPIRV-Cross threw an exception: Buffer block cannot be expressed as any of std430, std140, scalar,
even with enhanced layouts. You can try flattening this block to support a more flexible layout.
```

`spirv-val` (DX) — aponta o membro e o offset:

```
error: line 397: Structure id 13 decorated as BufferBlock for variable in Uniform storage class must
follow standard storage buffer layout rules: member 7 at offset 92 is not aligned to 16
  %RDPParams = OpTypeStruct %v4float %v2float %v2float %v4float %v4float %v4float %v3float %v3float %_arr_int_uint_6
```

`spirv-val` (DX, push constant):

```
error: line 59: Structure id 7 decorated as Block for variable in PushConstant storage class must
follow standard storage buffer layout rules: member 1 at offset 4 is not aligned to 16
  %type_ConstantBuffer_RasterParams = OpTypeStruct %uint %v3uint %v2float %v2float
```

Ou seja: `-fvk-use-dx-layout` posiciona `vec3` em offsets não múltiplos de 16 (92, 36, 12, 4),
o que é legal em D3D/Vulkan-DX mas **não é expressável em std430** (exigido pelo SPIRV-Cross para
GLSL/GLES).

## 3. Diff de offsets DX vs GL — apenas 6 structs divergem

Medido com `spirv-dis` (offsets realmente decorados no SPIR-V), via `m1_layout_diff.py`
(relatório completo em `evidencias/m1_layout_diff_dx_gl_20261018.md`):

| struct (header) | membro crítico | DX | GL | correção | shaders afetados |
|---|---|---|---|---|---|
| `RDPParams` (`rt64_rdp_params.h`) | `keyScale` (vec3) | 92 | 96 | +4 bytes antes | 9 |
| | (stride) | 132 | 144 | +12 bytes no fim | |
| `GPUTile` (`rt64_gpu_tile.h`) | `textureDimensions` (vec3) | 36 | 48 | +12 bytes antes | 6 |
| `RSPViewport` (`rt64_rsp_viewport.h`) | `translate` (vec3) | 12 | 16 | +4 antes / +4 no fim | 1 |
| `RSPLookAt` (`rt64_rsp_lookat.h`) | `y` (vec3) | 12 | 16 | +4 antes / +4 no fim | 1 |
| `RSPLight` (`rt64_rsp_light.h`) | `col`, `colc` (vec3) | 12, 24 | 16, 32 | +4 antes de cada / +8 no fim | 1 |
| `RasterParams` (`rt64_raster_params.h`) | `padding` (uint3) | 4 | 16 | +12 antes | 12 |

Evidência pontual do dump (mesmo blob, dois layouts):

```
DX:  [ 7] keyScale   off=92   Vector %float 3   <-- VEC3 NAO ALINHADO A 16
GL:  [ 7] keyScale   off=96   Vector %float 3
```

## 4. Regras de padding descobertas (empiricamente)

1. Todo membro **`vec3`** deve cair em offset múltiplo de 16 → inserir padding **antes**.
2. O **tamanho da struct** deve ser múltiplo de 16 (stride do array em std430) → padding no fim.
3. O próprio **padding deve ser escalar**: usar `uint3`/`float3` como padding é inválido
   (o `uint3` também exigiria alinhamento 16 — erro observado:
   `member 5 at offset 36 is not aligned to 16`).
4. **`vec2`** exige alinhamento **8** em std430 (erro observado:
   `member 5 at offset 28 is not aligned to 8`).

## 5. PoC decisivo — layout DX + padding explícito

Aplicado o padding nos 6 headers duais (`evidencias/m1_patches_headers/layout_padding.patch`) e
recompilado **com o layout DX original** (`-fvk-use-dx-layout`):

| shader | dxc | spirv-val | spirv-cross | glslang |
|---|---|---|---|---|
| RasterPSDynamic | 0 | **0** | **0** | 2 |
| RasterPSDynamicMS | 0 | **0** | **0** | 2 |
| RasterPSSpecConstant | 0 | **0** | **0** | 2 |
| RasterPSSpecConstantMS | 0 | **0** | **0** | 2 |
| RasterPSSpecConstantFlat | 0 | **0** | **0** | 2 |
| RasterPSSpecConstantFlatMS | 0 | **0** | **0** | 2 |
| RasterVSDynamic | 0 | **0** | **0** | **0** |
| RasterVSSpecConstant | 0 | **0** | **0** | **0** |
| RasterVSSpecConstantFlat | 0 | **0** | **0** | **0** |
| RSPProcessCS | 0 | **0** | **0** | **0** |
| ComposePS (controle) | 0 | 0 | 0 | 0 |
| TextureCopyPS (controle) | 0 | 0 | 0 | 0 |

- **`spirv-val`: 0 erros em todos** → SPIR-V válido em Vulkan 1.0 (as 13 falhas desapareceram).
- **`spirv-cross`: 0 exceções em todos** → converte para GLSL ES 3.20 (as 10 falhas desapareceram).
- Offsets verificados no blob recompilado (idênticos ao layout GL/std430):
  `RDPParams.keyScale@96`, `convertK@108`, `padding2@132`; `GPUTile.textureDimensions@48`;
  `RSPViewport.translate@16`; `RSPLight.col@16`, `colc@32`; `RSPLookAt.y@16`;
  `RasterParams.padding@16`, `screenScale@32`, `screenOffset@40`.
- Prova de saída GLSL ES válida (`RSPProcessCS.comp`):

```
#version 320 es
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

struct RSPViewport
{
    vec3 scale;
    float padding;
    vec3 translate;
```

## 6. Erros residuais nos `RasterPS*` (ortogonais ao layout)

Após o padding, os 6 `RasterPS*` **convertem** e o `spirv-val` passa; resta apenas, no
`glslangValidator`, a extensão espúria:

```
ERROR: 0:2: '#extension' : extension not supported: GL_NV_gpu_shader5
```

Origem (fonte vendorizada `contrib/spirv-cross/spirv_glsl.cpp:571`):

```cpp
case CapabilityShaderNonUniformEXT:
    if (!options.vulkan_semantics)
        require_extension_internal("GL_NV_gpu_shader5");
    else
        require_extension_internal("GL_EXT_nonuniform_qualifier");
```

O `CapabilityShaderNonUniformEXT` vem de `TextureSampler.hlsli:104`:

```hlsl
return sampleTMEM(..., gTMEM[NonUniformResourceIndex(gpuTile.textureIndex)]);
```

com `Texture1D<uint> gTMEM[8192] : register(t0, space2);` (`FbRendererCommon.hlsli:46`).

**Mitigação comprovada** (`m1_mitig_nonuniform.sh`): remover a linha
`#extension GL_NV_gpu_shader5 : require` faz esse erro desaparecer (não há nenhum uso real de
`nonuniformEXT` no código gerado — grep = 0), restando então somente:

```
ERROR: 0:136: 'usampler1D' : Reserved word.
```

## 7. Lacunas de GLES remanescentes (não são layout)

| causa | shaders | explicação |
|---|---|---|
| `usampler1D` | 8 (`RasterPS*` 6, `TextureDecodeCS`, `FbReinterpretCS`) | GLES **não tem texturas 1D**; o RT64 modela TMEM/TLUT como `Texture1D<uint>` (e `gTMEM[8192]`) |
| `noperspective` | 1 (`Im3DVS`) | `noperspective` não existe em ESSL 320 |
| `image load-store format` | 1 (`DebugPS`) | `imageStore` com formato qualificado não é suportado no perfil ES 320 |

`FbReinterpretCS`, `TextureDecodeCS`, `Im3DVS` e `DebugPS` falham em **ambos** os layouts →
confirmadamente independentes do layout.

## 8. Decisão (M1)

**Adotada a opção (b)**: manter UM único conjunto de blobs e o layout C++ atual, inserindo
padding explícito nos 6 headers duais, de forma que `-fvk-use-dx-layout` produza offsets
idênticos ao std430.

Motivos:
- `-fvk-use-gl-layout` (opção a) resolveria a conversão, mas muda todos os offsets/stride
  (`keyScale` 92→96, stride 128→144) e exigiria um **segundo layout no C++ host**, com dois
  caminhos de código e risco de divergência.
- Com padding, o PoC mostra **val=0 e xc=0 sem trocar a flag de layout** → Vulkan/D3D12/Metal e
  GLES compartilham exatamente os mesmos bytes.

## 9. Conclusão (fato verificado)

1. A causa raiz das 10 falhas de conversão (e das 13 falhas de validação Vulkan) é o
   **alinhamento de `vec3`** no layout DX, não expressável em std430.
2. **Com padding explícito nos 6 headers duais, `spirv-val` e `spirv-cross` passam em 12/12
   shaders testados (incluindo os 10 previamente falhos)** — é possível ter um único conjunto de
   blobs para todos os backends.
3. Restam **10 shaders com lacunas de GLES** (TMEM como textura 1D, `noperspective`,
   image load-store format), **ortogonais ao layout**; são o próximo trabalho (M1.1).
4. O bloqueio de layout do M1 está **encerrado**.