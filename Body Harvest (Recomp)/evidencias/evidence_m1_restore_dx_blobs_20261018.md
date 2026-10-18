# EVIDÊNCIA — Restauração dos 58 blobs SPIR-V DX-layout (M1)

- **Data/hora da operação**: 2026-10-18 (execução em WSL, host x86_64)
- **Conta/host**: local (WSL), sem conta AWS envolvida
- **Diretórios**:
  - Danificado: `/root/bhrecomp/build-aarch64/{src/shaders,shaders}/`
  - Fonte pristine: `/root/bhrecomp/build-cmake/{src/shaders,shaders}/`
  - Backup do dano: `/root/bhrecomp/m1_restore/damaged_gl/`
  - Relatório: `/root/bhrecomp/m1_restore/restore.tsv`
- **Script**: `evidencias/tools/m1_restore_dx_blobs.sh`

## Causa raiz do dano

`m1_layout_matrix.sh` tentava redirecionar a saída do DXC com:

```bash
sed "s|-Fo \([^ ]*\)|-Fo $OUT/$NAME.$L.spv|"
```

mas o comando DXC real (extraído de `ninja -t commands`) usa **barra + espaço**:

```
... /Fo /root/bhrecomp/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv
```

Ou seja, `/Fo` e o caminho são **dois tokens separados**. O `sed` nunca casou (`-Fo` com hífen),
então o DXC da passada `gl` (`-fvk-use-gl-layout`) escreveu no **caminho original**,
sobrescrevendo **todos os 56 blobs** em `build-aarch64/src/shaders/` (mais os 2 de `build-aarch64/shaders/`).

Prova do dano (md5):

| Arquivo | md5 | Layout |
|---|---|---|
| `build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv` (antes do restore) | `b2eb6b9f315cf3ab2c7b551f54526200` | GL (errado) |
| `build-cmake/src/shaders/RasterPSDynamic.hlsl.spv` | `d592de4472eee211c696407c669d6702` | DX (correto) |
| `m1_fix/RasterPSDynamic.dx.spv` (backup independente) | `d592de4472eee211c696407c669d6702` | DX (correto) |

## Fonte de restauração e sua validade

`/root/bhrecomp/build-cmake` é um build **x86_64** de `2026-10-16 14:11` (pré-dano) que usou
o mesmo DXC com `-fvk-use-dx-layout`. **O DXC produz SPIR-V idêntico independentemente da
arquitetura-alvo do build** (a saída depende apenas de fonte + flags + versão do DXC), o que é
confirmado empiricamente pelo md5 `d592de44…` ser idêntico ao backup independente `m1_fix/RasterPSDynamic.dx.spv`.

`build-cmake` contém **56** blobs em `src/shaders/` + **2** em `shaders/` = **58**, exatamente o
conjunto coberto pelos 58 comandos DXC em `ninja -t commands`.

## Resultado da operação (RAW)

```
backup dos danificados: 58 arquivos em /root/bhrecomp/m1_restore/damaged_gl
=== RESTORE ===
restaurados OK   : 58
destino ausente  : 0
divergentes      : 0
--- linhas com status != OK ---
=== VERIFY: contagem de blobs por diretorio ===
src/shaders    src=56  dst=56
shaders        src=2   dst=2
=== VERIFY: conjunto de nomes identico? ===
src/shaders: nomes IDENTICOS
=== VERIFY: layout DX autoritativo (spirv-dis) do RasterPSDynamic ===
--- esperado: keyScale off=92 (nao 96), ArrayStride 128 (nao 144) ---
30:               OpMemberName %RDPParams 7 "keyScale"
198:              OpMemberDecorate %RDPParams 6 Offset 80
199:              OpMemberDecorate %RDPParams 7 Offset 92
201:              OpDecorate %_runtimearr_RDPParams ArrayStride 128
=== VERIFY: md5 global do conjunto (src/shaders) ===
c41da4803d4f0e00d511fc8c98f44292  -
c41da4803d4f0e00d511fc8c98f44292  -
(as duas linhas acima devem ser IGUAIS)
```

## Conclusão (fato verificado)

1. Os **58** blobs foram restaurados **byte a byte** (`src` md5 == `dst` md5, 0 divergentes).
2. O layout DX está **confirmado por leitura direta do SPIR-V** (`spirv-dis`):
   - `RDPParams.keyScale` em **Offset 92** (o layout DX "compacto" que causa a falha do SPIRV-Cross);
   - `ArrayStride` do array de `RDPParams` = **128** (não 144).
3. O **hash agregado** dos conjuntos `src/shaders` é idêntico
   (`c41da4803d4f0e00d511fc8c98f44292`), provando equivalência integral do conjunto.
4. A integridade do baseline para os experimentos de layout (DX vs GL) está **restabelecida**.