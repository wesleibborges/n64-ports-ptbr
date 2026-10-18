## Matriz de layout DX vs GL — 58 shaders

Fonte: `/root/bhrecomp/m1_layout_matrix2/results.tsv`

| metrica | DX layout (atual) | GL layout (candidato) |
|---|---|---|
| DXC falhou | 0 | 0 |
| spirv-val falhou (SPIR-V invalido) | 13 | 0 |
| SPIRV-Cross falhou (>=ES 320) | 10 | 0 |
| glslangValidator falhou | 4 | 10 |

### spirv-val FALHOU com layout DX (SPIR-V Vulkan invalido) (13)

| shader | stage | rc |
|---|---|---|
| RasterPSDynamic.hlsl.spv | ps_6_3 | 1 |
| RasterPSDynamicMS.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstant.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstantMS.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstantFlat.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstantFlatMS.hlsl.spv | ps_6_3 | 1 |
| RasterVSDynamic.hlsl.spv | vs_6_3 | 1 |
| RasterVSSpecConstant.hlsl.spv | vs_6_3 | 1 |
| RasterVSSpecConstantFlat.hlsl.spv | vs_6_3 | 1 |
| PostBlendDitherNoiseAddPS.hlsl.spv | ps_6_3 | 1 |
| PostBlendDitherNoiseSubPS.hlsl.spv | ps_6_3 | 1 |
| PostBlendDitherNoiseSubNegativePS.hlsl.spv | ps_6_3 | 1 |
| RSPProcessCS.hlsl.spv | cs_6_3 | 1 |

### SPIRV-Cross FALHOU com layout DX (10)

| shader | stage | rc |
|---|---|---|
| RasterPSDynamic.hlsl.spv | ps_6_3 | 1 |
| RasterPSDynamicMS.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstant.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstantMS.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstantFlat.hlsl.spv | ps_6_3 | 1 |
| RasterPSSpecConstantFlatMS.hlsl.spv | ps_6_3 | 1 |
| RasterVSDynamic.hlsl.spv | vs_6_3 | 1 |
| RasterVSSpecConstant.hlsl.spv | vs_6_3 | 1 |
| RasterVSSpecConstantFlat.hlsl.spv | vs_6_3 | 1 |
| RSPProcessCS.hlsl.spv | cs_6_3 | 1 |

### SPIRV-Cross FALHOU com layout GL (0)

_nenhum_

### glslangValidator FALHOU com layout DX (4)

| shader | stage | rc |
|---|---|---|
| FbReinterpretCS.hlsl.spv | cs_6_3 | 2 |
| TextureDecodeCS.hlsl.spv | cs_6_3 | 2 |
| Im3DVS.hlsl.spv | vs_6_3 | 2 |
| DebugPS.hlsl.spv | ps_6_3 | 2 |

### glslangValidator FALHOU com layout GL (10)

| shader | stage | rc |
|---|---|---|
| RasterPSDynamic.hlsl.spv | ps_6_3 | 2 |
| RasterPSDynamicMS.hlsl.spv | ps_6_3 | 2 |
| RasterPSSpecConstant.hlsl.spv | ps_6_3 | 2 |
| RasterPSSpecConstantMS.hlsl.spv | ps_6_3 | 2 |
| RasterPSSpecConstantFlat.hlsl.spv | ps_6_3 | 2 |
| RasterPSSpecConstantFlatMS.hlsl.spv | ps_6_3 | 2 |
| FbReinterpretCS.hlsl.spv | cs_6_3 | 2 |
| TextureDecodeCS.hlsl.spv | cs_6_3 | 2 |
| Im3DVS.hlsl.spv | vs_6_3 | 2 |
| DebugPS.hlsl.spv | ps_6_3 | 2 |

### glslang FALHA em AMBOS os layouts (independente de layout) (4)

- DebugPS.hlsl.spv
- FbReinterpretCS.hlsl.spv
- Im3DVS.hlsl.spv
- TextureDecodeCS.hlsl.spv

### glslang falhava so em DX e passou em GL (resolvido pelo layout) (0)


### Nao executados (99) com GL (xc nao produziu GLSL): checar

val_dx  : []
val_gl  : []
