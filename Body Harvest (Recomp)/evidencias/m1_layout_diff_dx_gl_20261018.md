# Diff de layout DX vs GL — 58 pares de blobs

## Structs com layout divergente (precisam de padding explicito)

### GPUTile  (stride DX=None GL=None) — em 6 shader(s)

| idx | membro | off DX | off GL | tipo | acao |
|---|---|---|---|---|---|
| 0 | ulScale | 0 | 0 | Vector %float 2 |  |
| 1 | tcScale | 8 | 8 | Vector %float 2 |  |
| 2 | texelShift | 16 | 16 | Vector %uint 2 |  |
| 3 | texelMask | 24 | 24 | Vector %uint 2 |  |
| 4 | textureIndex | 32 | 32 | Int 32 0 |  |
| 5 | textureDimensions | 36 | 48 | Vector %float 3 | inserir 12 byte(s) de padding antes (vec3 precisa alinhar a 16) |
| 6 | flags | 48 | 60 | Int 32 0 | deslocado em +12 (consequencia do padding anterior) |

### RDPParams  (stride DX=None GL=None) — em 9 shader(s)

| idx | membro | off DX | off GL | tipo | acao |
|---|---|---|---|---|---|
| 0 | primColor | 0 | 0 | Vector %float 4 |  |
| 1 | primLOD | 16 | 16 | Vector %float 2 |  |
| 2 | primDepth | 24 | 24 | Vector %float 2 |  |
| 3 | envColor | 32 | 32 | Vector %float 4 |  |
| 4 | fogColor | 48 | 48 | Vector %float 4 |  |
| 5 | blendColor | 64 | 64 | Vector %float 4 |  |
| 6 | keyCenter | 80 | 80 | Vector %float 3 |  |
| 7 | keyScale | 92 | 96 | Vector %float 3 | inserir 4 byte(s) de padding antes (vec3 precisa alinhar a 16) |
| 8 | convertK | 104 | 108 | Array %int %uint_6 | deslocado em +4 (consequencia do padding anterior) |

### RSPLight  (stride DX=None GL=None) — em 1 shader(s)

| idx | membro | off DX | off GL | tipo | acao |
|---|---|---|---|---|---|
| 0 | posDir | 0 | 0 | Vector %float 3 |  |
| 1 | col | 12 | 16 | Vector %float 3 | inserir 4 byte(s) de padding antes (vec3 precisa alinhar a 16) |
| 2 | colc | 24 | 32 | Vector %float 3 | inserir 8 byte(s) de padding antes (vec3 precisa alinhar a 16) |
| 3 | kc | 36 | 44 | Int 32 0 | deslocado em +8 (consequencia do padding anterior) |
| 4 | kl | 40 | 48 | Int 32 0 | deslocado em +8 (consequencia do padding anterior) |
| 5 | kq | 44 | 52 | Int 32 0 | deslocado em +8 (consequencia do padding anterior) |

### RSPLookAt  (stride DX=None GL=None) — em 1 shader(s)

| idx | membro | off DX | off GL | tipo | acao |
|---|---|---|---|---|---|
| 0 | x | 0 | 0 | Vector %float 3 |  |
| 1 | y | 12 | 16 | Vector %float 3 | inserir 4 byte(s) de padding antes (vec3 precisa alinhar a 16) |

### RSPViewport  (stride DX=None GL=None) — em 1 shader(s)

| idx | membro | off DX | off GL | tipo | acao |
|---|---|---|---|---|---|
| 0 | scale | 0 | 0 | Vector %float 3 |  |
| 1 | translate | 12 | 16 | Vector %float 3 | inserir 4 byte(s) de padding antes (vec3 precisa alinhar a 16) |

### type.ConstantBuffer.RasterParams  (stride DX=None GL=None) — em 12 shader(s)

| idx | membro | off DX | off GL | tipo | acao |
|---|---|---|---|---|---|
| 0 | renderIndex | 0 | 0 | Int 32 0 |  |
| 1 | padding | 4 | 16 | Vector %uint 3 | inserir 12 byte(s) de padding antes (vec3 precisa alinhar a 16) |
| 2 | screenScale | 16 | 32 | Vector %float 2 | deslocado em +16 (consequencia do padding anterior) |
| 3 | screenOffset | 24 | 40 | Vector %float 2 | deslocado em +16 (consequencia do padding anterior) |

## Lista consolidada de headers a ajustar (6 structs)

- `GPUTile` — afeta 6 shader(s)
- `RDPParams` — afeta 9 shader(s)
- `RSPLight` — afeta 1 shader(s)
- `RSPLookAt` — afeta 1 shader(s)
- `RSPViewport` — afeta 1 shader(s)
- `type.ConstantBuffer.RasterParams` — afeta 12 shader(s)
