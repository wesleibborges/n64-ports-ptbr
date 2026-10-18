# EVIDÊNCIA — Aplicação REAL do padding de layout M1 + rebuild aarch64 (RT64)

- **Data**: 2026-10-18 · **Ambiente**: WSL x86_64 (Ubuntu jammy) + cross-compile aarch64
- **Objetivo**: aplicar na árvore real a correção de layout validada no PoC v3
  (`-fvk-use-dx-layout` + padding explícito nos 6 headers duais => offsets idênticos ao
  std430), regenerar os 58 blobs SPIR-V e reconstruir o binário aarch64 para o R36S.
- **Pré-requisito**: `evidencias/evidence_m1_layout_matrix_20261018.md` (matriz 58×2,
  PoC v3, decisão da opção (b)) e `evidencias/evidence_m1_restore_dx_blobs_20261018.md`
  (integridade dos blobs restaurada).

## 1. Artefatos

| Item | Caminho |
|---|---|
| Backup dos 6 headers originais | `/root/bhrecomp/m1_apply_20261018/backup_headers/` |
| Header SDL2 original (pré-fix) | `/root/bhrecomp/m1_apply_20261018/SDL_video.h.orig` |
| md5 headers (antes/depois) | `.../md5_headers_backup.txt`, `.../md5_headers_applied.txt` |
| md5 dos blobs (antes/depois) | `.../md5_blobs_before.txt`, `.../md5_blobs_after.txt` |
| Tabela de validação (58 shaders) | `.../validacao_blobs.tsv` |
| Log do build aarch64 | `.../ninja_build.log` |
| Scripts | `evidencias/tools/m1_apply_padding.sh`, `m1_fix_sysroot_sdl2_headers.sh` (correção de raiz), `m1_fix_sysroot_sdl2.sh` (remendos pontuais, histórico), `m1_regen_blobs.py`, `m1_validate_blobs.py`, `m1_offset_compare.py`, `m1_build_detached.sh`, `m1_build_aarch64.sh` |
| Backup include/SDL2 do sysroot (pré-fix 2.30.3) | `.../sysroot_SDL2_include_orig/` (80 arquivos) |
| Binário final | `/root/bhrecomp/build-aarch64/BodyHarvestRecompiled` e `BodyHarvestRecompiled.m1_padding_20261018` |

## 2. Aplicação do padding na árvore real

Os 6 headers em `lib/rt64/src/shared/` foram confirmados **byte-idênticos** ao
`headers_orig` do PoC (`md5sum` 1:1) antes da aplicação — o patch era aplicável direto.

`m1_apply_padding.sh` (md5 RAW dos originais):

```
7f8b04aa7dfdfd6f79d6d31bb3393c7d  backup_headers/rt64_gpu_tile.h
c50a1a009e4792b599a91904e9bd6a91  backup_headers/rt64_raster_params.h
35cb2b1735c2c05ae7b97811c3be3efb  backup_headers/rt64_rdp_params.h
821fa2735a9df60adf9965f9f8bbf713  backup_headers/rt64_rsp_light.h
f7355dc8d54fb8110a74092dc2829a66  backup_headers/rt64_rsp_lookat.h
733867a54a6fbe8f144f2a57ad79bccd  backup_headers/rt64_rsp_viewport.h
```

Pós-aplicação (o md5 "validado" é o artefato exato aprovado no PoC v3):

```
rt64_gpu_tile.h       validado=ba8b846316e45b305433b952dcde8cb8 aplicado=ba8b846316e45b305433b952dcde8cb8  OK
rt64_raster_params.h  validado=f58c2f74387a3b3dc8ffd9ebc19548dc aplicado=f58c2f74387a3b3dc8ffd9ebc19548dc  OK
rt64_rdp_params.h     validado=0ead44287e7b94e7493b3672bc065acf aplicado=0ead44287e7b94e7493b3672bc065acf  OK
rt64_rsp_light.h      validado=71819ea25f3ccbf7a442d1537692c76e aplicado=71819ea25f3ccbf7a442d1537692c76e  OK
rt64_rsp_lookat.h     validado=38ce5c3de04db949929c1670570438d3 aplicado=38ce5c3de04db949929c1670570438d3  OK
rt64_rsp_viewport.h   validado=3e4b6f677ec5ea66bf21b382f96fd60e aplicado=3e4b6f677ec5ea66bf21b382f96fd60e  OK
```

Prova de identidade (`diff -q` real x artefato validado): **6/6 idênticos**.
Marcadores `M1-GLES` presentes: gpu_tile=1, raster_params=2, rdp_params=2, rsp_light=3,
rsp_lookat=2, rsp_viewport=2.

### 2.1 Por que foi necessário invalidar os 58 blobs

`lib/rt64/CMakeLists.txt` (macro `build_shader_spirv_impl`):

```cmake
add_custom_command(OUTPUT ${OUTNAME}.spv
    COMMAND ${DXC} ${DXC_SPV_OPTS} ${ARGN} ${FILENAME} /Fo ${OUTNAME}.spv
    DEPENDS ${FILENAME})
```

`DEPENDS` declara **apenas o `.hlsl`**. Os headers inclusos via `-I${PROJECT_SOURCE_DIR}/src`
**não** entram nas dependências do ninja — confirmado no `build.ninja`:

```
build src/shaders/RasterPSDynamic.hlsl.spv | ...: CUSTOM_COMMAND /root/bhrecomp/lib/rt64/src/shaders/RasterPS.hlsl
```

Ou seja: **mudar header de layout não dispara o DXC** (bug latente upstream, risco de blobs
silenciosamente obsoletos). Por isso os 58 `.hlsl.spv` / `.spirv.c` / `.spirv.h` e o
`.hlsli.rw*` foram removidos para forçar a regeneração.

## 3. Bloqueio pré-existente encontrado no build (ortogonal ao M1)

O primeiro rebuild aarch64 **falhou** — mas em código não relacionado ao padding:

```
FAILED: rt64/src/contrib/plume/CMakeFiles/plume.dir/plume_vulkan.cpp.o
/root/bhrecomp/lib/rt64/src/contrib/plume/plume_vulkan.cpp:2467:9: error:
  'SDL_GetWindowSizeInPixels' was not declared in this scope; did you mean 'SDL_GetWindowSize'?
```

### Causa raiz (comprovada)

1. O `.ninja_log` **perdeu o registro** do objeto do plume, então o ninja passou a
   recompilá-lo (diagnóstico autoritativo do próprio ninja):
   ```
   $ ninja -C build-aarch64 -d explain -n src/shaders/ComposePS.hlsl.spv
   ninja explain: command line not found in log for rt64/src/contrib/plume/CMakeFiles/plume.dir/plume_vulkan.cpp.o
   ninja explain: rt64/src/contrib/plume/CMakeFiles/plume.dir/plume_vulkan.cpp.o is dirty
   ```
2. O objeto não recompilava porque o **sysroot aarch64 tem headers e biblioteca SDL2 de
   versões diferentes**:

```
$ grep -E 'SDL_MAJOR_VERSION|SDL_MINOR_VERSION|SDL_PATCHLEVEL' /root/sysroot64/usr/include/SDL2/SDL_version.h
#define SDL_MAJOR_VERSION   2
#define SDL_MINOR_VERSION   0
#define SDL_PATCHLEVEL      20          <-- headers = SDL 2.0.20 (jammy)

$ ls -l /root/sysroot64/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0
... -> .../libSDL2-2.0.so.0.3000.3    <-- lib = SDL 2.30 (aRkOS)

$ nm -D --defined-only .../libSDL2-2.0.so.0 | grep GetWindowSizeInPixels
000000000004a610 T SDL_GetWindowSizeInPixels   <-- a BIBLIOTECA exporta a API de 2.26+
```

`plume_vulkan.cpp` (não modificado desde 2026-10-16 13:47) usa
`SDL_GetWindowSizeInPixels` (SDL ≥ 2.26), que os headers 2.0.20 não declaram.

### Correção aplicada

Duas etapas (a segunda substitui a primeira, que era um remendo pontual):

**(a) Remendo pontual inicial** — `m1_fix_sysroot_sdl2.sh` acrescentou ao
`SDL_video.h` do sysroot a declaração de `SDL_GetWindowSizeInPixels` (backup em
`SDL_video.h.orig`, md5 `a25dfc375a9a3710e5c778e67fdb8902`). Isso destravou o
`plume`, mas o build voltou a falhar em outras APIs da mesma classe:

```
lib/RecompFrontend/recompinput/src/input_events.cpp:80:  'SDL_JoystickPath' was not declared
lib/RecompFrontend/recompinput/src/profiles.cpp:279:     'SDL_GetJoystickGUIDInfo' was not declared
src/main/main.cpp:65:                                    'SDL_HINT_WINDOWS_DPI_AWARENESS' was not declared
```

**(b) Correção de raiz** — `m1_fix_sysroot_sdl2_headers.sh` instalou no sysroot os
**headers públicos reais do SDL 2.30.3**, que existem localmente em `/root/SDL2-2.30.3/include/`
(exatamente a versão da biblioteca linkada), preservando o `SDL_config.h` Debian
(cuja indireção `#include <SDL2/_real_SDL_config.h>` já funciona no build):

```
--- headers antes ---                        --- biblioteca linkada ---
#define SDL_MINOR_VERSION   0               -> /root/sysroot64/usr/lib/libSDL2-2.0.so.0.3000.3
#define SDL_PATCHLEVEL      20              (SONAME 3000.3 = SDL 2.30.3)

--- headers instalados agora (fonte: /root/SDL2-2.30.3/include) ---
#define SDL_MINOR_VERSION   30
#define SDL_PATCHLEVEL      3
```

Backup completo em `m1_apply_20261018/sysroot_SDL2_include_orig/` (80 arquivos;
`SDL_version.h` md5 `8a50d1c4eca8ce1c0fce084ec6c1fb24`, `SDL_config.h` md5
`729c38704a46ff12244fb9e067ad552b`). Verificação da instalação:

```
md5sum sysroot64/usr/include/SDL2/SDL_joystick.h  /root/SDL2-2.30.3/include/SDL_joystick.h
71a60fe71605edeada15570add438ee8  (idênticos)

grep -c SDL_JoystickPath          SDL_joystick.h -> 5
grep -c SDL_GetJoystickGUIDInfo   SDL_joystick.h -> 1
grep -c SDL_GetWindowSizeInPixels SDL_video.h    -> 1
grep -c SDL_HINT_WINDOWS_DPI_AWARENESS SDL_hints.h -> 1
```

Nota metodológica: como `cp -a` preserva mtimes, o ninja **não** considerou sujos os
objetos que já compilavam; para garantir build **homogêneo**, os headers SDL2 foram
`touch`ados e os dependentes recompilados (o ABI do SDL2 é estável dentro do 2.x, mas a
consistência total é preferível num artefato de entrega).

**Fundamento da correção**: o binário **que já roda no dispositivo** importa
`SDL_GetWindowSizeInPixels` (`_und.txt`: linha 53), e o SDL2 do aRkOS (2.30.x) o resolve em
runtime — ou seja, o código do port e o alvo já eram 2.24+/2.30; apenas os *headers* do
sysroot estavam desatualizados. Instalar os headers 2.30.3 apenas **restaura a consistência
headers↔lib**, sem mudança de comportamento em runtime.

## 4. Regeneração dos 58 blobs

Como o DXC não é disparado por mudança de header (item 2.1), a regeneração foi feita com
`m1_regen_blobs.py` (6 workers, retomável), executando os **comandos exatos do
`build.ninja`** (forma autoritativa, `/Fo <path>` em dois tokens) e gravando diretamente
nos caminhos reais de saída:

```
COMMAND = cd /root/bhrecomp/build-aarch64/rt64 && LD_LIBRARY_PATH=.../dxc/lib/arm64 .../dxc-linux \
  -spirv -fspv-target-env=vulkan1.0 -fvk-use-dx-layout -I.../lib/rt64/src \
  -E PSMain -T\ ps_6_3 -D\ DYNAMIC_RENDER_PARAMS .../shaders/RasterPS.hlsl \
  /Fo /root/bhrecomp/build-aarch64/src/shaders/RasterPSDynamic.hlsl.spv
```

Resultado: `gerados agora: 58 | ja existiam: 0 | falhas: 0` → **blobs presentes: 58/58**.
Comandos DXC encontrados no `build.ninja`: 58 (1:1 com os blobs).

### 4.1 Raio de impacto (md5 antes/depois)

**13 blobs mudaram** — exatamente o conjunto antes inválido (as 13 falhas de `spirv-val`):

```
PostBlendDitherNoiseAddPS.hlsl.spv         RasterPSSpecConstantFlat.hlsl.spv
PostBlendDitherNoiseSubNegativePS.hlsl.spv RasterPSSpecConstantFlatMS.hlsl.spv
PostBlendDitherNoiseSubPS.hlsl.spv         RasterPSSpecConstantMS.hlsl.spv
RSPProcessCS.hlsl.spv                      RasterVSDynamic.hlsl.spv
RasterPSDynamic.hlsl.spv                   RasterVSSpecConstant.hlsl.spv
RasterPSDynamicMS.hlsl.spv                 RasterVSSpecConstantFlat.hlsl.spv
RasterPSSpecConstant.hlsl.spv
```

Os outros **45 blobs ficaram md5-idênticos**: o padding não perturba shaders que não usam
as 6 structs ajustadas (raio de impacto mínimo). md5 agregado do snapshot pós-regeneração:
`35f19a93da32acb8968a220e587dae52`.

## 5. Validação dos 58 blobs (critérios de aceite M1)

`m1_validate_blobs.py` (tabela completa em `validacao_blobs.tsv`):

| métrica | antes (layout DX puro) | depois (DX + padding) |
|---|---|---|
| `spirv-val --target-env vulkan1.0` falhas | **13** | **0** ✅ |
| `spirv-cross --es --version 320` falhas | **10** | **0** ✅ |
| `glslangValidator` falhas | 4 (+6 não executados) | 13 (lacunas GLES, ver M1.1) |

Os 13 shaders que ainda não compilam em ESSL 320 são exatamente as lacunas de GLES
**ortogonais ao layout** (`usampler1D` em 8: 6× `RasterPS*`, `RasterVS*`×3, `TextureDecodeCS`,
`FbReinterpretCS`; `noperspective` em `Im3DVS`; image load-store format em `DebugPS`) —
escopo do M1.1. Note-se que `spirv-cross` **converte todos os 58** agora (antes 10 falhavam
com "Buffer block cannot be expressed as any of std430... even with enhanced layouts").

## 6. Prova de offsets nos blobs REAIS

### 6.1 `RDPParams` (StructuredBuffer) — `RasterPSDynamic.hlsl.spv`

```
struct RDPParams (id %RDPParams)
  [ 0] primColor    off=0    Vector %float 4
  [ 1] primLOD      off=16   Vector %float 2
  [ 2] primDepth    off=24   Vector %float 2
  [ 3] envColor     off=32   Vector %float 4
  [ 4] fogColor     off=48   Vector %float 4
  [ 5] blendColor   off=64   Vector %float 4
  [ 6] keyCenter    off=80   Vector %float 3
  [ 7] padding      off=92   Float 32          <-- M1-GLES (novo)
  [ 8] keyScale     off=96   Vector %float 3   <-- era 92 (nao multiplo de 16)
  [ 9] convertK     off=108  Array %int %uint_6
  [10] padding2     off=132  Array %int %uint_3 <-- M1-GLES (novo)
```

Tamanho resultante = 132 + 12 = **144** (múltiplo de 16, exigido para stride de array em
std430). Antes: `keyScale@92`, stride 128.

### 6.2 Outras structs (idênticas às do PoC validado)

```
struct RSPLight                      struct type.ConstantBuffer.RasterParams
  [0] posDir  off=0                    [0] renderIndex  off=0
  [1] padding0 off=12                  [1] padding0     off=4
  [2] col     off=16                   [4] padding      off=16
  [3] padding1 off=28                  [5] padding3     off=28
  [4] colc    off=32                   [6] screenScale  off=32
  [5] kc      off=44                   [7] screenOffset off=40
  ... [9] padding3 off=60  (stride 64)
```

`GPUTile.textureDimensions@48` (era 36) · `RSPViewport.translate@16` (stride 32) ·
`RSPLookAt.y@16` (stride 32).

### 6.3 Comparação por membro significativo — `m1_offset_compare.py`

Comparar index-a-index seria inválido (o padding adicionou **membros novos**). O script
compara pela **interseção de nomes** de membros: se todo membro significativo cai no mesmo
offset do std430, o layout DX+padding == std430.

```
structs comparados: 103 | divergentes: 0

RasterPSDynamic   RDPParams                            OK
RasterPSDynamic   GPUTile                              OK
RasterPSDynamic   type.ConstantBuffer.RasterParams     OK
RasterVSDynamic   RDPParams                            OK
RSPProcessCS      RSPViewport / RSPLight / RSPLookAt    OK
(...) todos os 103 OK
```

**Fato verificado**: 103 structs, **0 divergências** — o layout dos blobs reais
(DX + padding) é idêntico ao std430 em todos os membros significativos. Somado ao
`spirv-val` = 0 (que valida formalmente as regras de layout de storage buffer), o objetivo
do M1 está comprovado **nos artefatos de build reais**, não apenas no PoC.

## 7. Lacunas de GLES remanescentes — escopo refinado do M1.1

Atribuição exata (primeira mensagem de erro de cada shader) via `validacao_blobs.tsv` +
logs `xc/<shader>.glslang.log`:

| # | primeira mensagem de erro | shaders |
|---|---|---|
| 6 | `ERROR: 0:2: '#extension' : extension not supported: GL_NV_gpu_shader5` | 6× `RasterPS*` |
| 2 | `ERROR: 0:18: 'float' : type requires declaration of default precision qualifier` | `RasterVSSpecConstant`, `RasterVSSpecConstantFlat` |
| 1 | `ERROR: 0:5: 'float' : type requires declaration of default precision qualifier` | `RasterVSDynamic` |
| 1 | `ERROR: 0:54: 'image load-store format' : not supported with this profile: es` | `DebugPS` |
| 1 | `ERROR: 0:26: 'usampler1D' : Reserved word.` | `FbReinterpretCS` |
| 1 | `ERROR: 0:18: 'usampler1D' : Reserved word.` | `TextureDecodeCS` |
| 1 | `ERROR: 0:46: 'noperspective' : Reserved word.` | `Im3DVS` |

Observações (fatos verificados):

- A extensão `GL_NV_gpu_shader5` é **espúria**: vem de
  `CapabilityShaderNonUniformEXT` (SPIRV-Cross emite `GL_NV_gpu_shader5` quando
  `vulkan_semantics` está desligado), originada do
  `NonUniformResourceIndex(gpuTile.textureIndex)` em `TextureSampler.hlsli`. A mitigação
  já comprovada (remover a linha `#extension`, grep de `nonuniformEXT` = 0) segue válida.
- `usampler1D` aparece como **primeira** mensagem apenas em 2 shaders; nos 6 `RasterPS*`
  ele está oculto atrás do erro de extensão, portanto o conjunto afetado por TMEM-1D é
  ≥ 8 (como já mapeado).
- **Novo achado**: 3 shaders falham por **ausência de qualificador de precisão default**
  (`RasterVSDynamic`, `RasterVSSpecConstant`, `RasterVSSpecConstantFlat`) — item a somar ao
  M1.1 (o SPIRV-Cross pode emitir `precision highp float;` conforme a opção usada).

Nada disso é layout: são lacunas de perfil ES 320, ortogonais ao M1 (como já estabelecido
na matriz).

## 8. Rebuild aarch64

- Build disparado por `ninja -C build-aarch64 BodyHarvestRecompiled` (rebuild **completo**,
  não incremental: o `.ninja_log` tinha perdido registros — inclusive o objeto do plume, o
  que revelou o problema do SDL2). Isso é desejável aqui: garante que **nenhum objeto host
  ficou obsoleto** em relação ao novo layout das structs duais.
- Como o runner de comandos encerra a sessão (~30 s) e mata jobs em background, o build foi
  conduzido em duas formas: fatias `timeout` (`m1_build_aarch64.sh`, progresso preservado
  pelo `.ninja_log`) e, por fim, sessão desacoplada (`m1_build_detached.sh`, `setsid` +
  `nohup`), que sobrevive entre chamadas.
- Log: `/root/bhrecomp/m1_apply_20261018/ninja_build.log` (blobs regenerados 58/58;
  as 3 entradas `FAILED` do log são **históricas** — resolvidas pela correção do SDL2 — e o
  ninja confirma a conclusão com `ninja: no work to do`).
- **Resultado final (sucesso)**:
  ```
  $ ninja -C build-aarch64 BodyHarvestRecompiled
  ninja: no work to do.

  $ file build-aarch64/BodyHarvestRecompiled
  ELF 64-bit LSB pie executable, ARM aarch64, version 1 (GNU/Linux),
  dynamically linked, interpreter /lib/ld-linux-aarch64.so.1,
  BuildID[sha1]=805a11de50e2bccff84405fd89cc764bf10a9d7a, for GNU/Linux 3.7.0, not stripped

  md5 13b708c21762bff9e183c494512e5776   (19.770.744 bytes, 2026-10-18 08:18)
  ```
  (avisos `ld: warning: libpcre/liblz4/libcap/libgpg-error ... not found` são apenas
  `-rpath-link` de dependências indiretas — pré-existentes e não fatais.)
- **Cadeia de inclusão dos shaders no binário** (prova de que os blobs com padding entraram):
  `*.hlsl.spv` (07:45) → `*.hlsl.spirv.c` (07:47) → objetos `*.hlsl.spirv.c.o`
  (≤ 08:00:55) → **binário (08:10 / 08:18)**. O agregado md5 dos 58 blobs após todo o
  rebuild permaneceu `35f19a93da32acb8968a220e587dae52` — **sem drift**.
- Artefato copiado para o port como `BodyHarvestRecompiled.m1_padding_20261018`
  (md5 `13b708c21762bff9e183c494512e5776`); o `BodyHarvestRecompiled` anterior de 2026-10-17
  (md5 `dbc386ba918d898a01038d7ff943768a`) foi **preservado** (promoção é decisão sua /
  teste no R36S).

## 9. Limitações e pendências

1. **`build-cmake` (x86_64) permanece no layout ANTES do padding.** É o snapshot pristine
   usado para a restauração dos blobs; não foi reconstruído. Se for necessário um binário
   x86_64/Windows, é preciso rebuildá-lo com os headers já corrigidos (o binário e os
   blobs x86_64 ficarão inconsistentes com o novo layout até isso ser feito).
2. **Bug latente no CMake (recomenda-se corrigir)**: os `add_custom_command` do DXC usam
   `DEPENDS ${FILENAME}` — os headers não entram nas dependências. Sugestão: acrescentar os
   headers de `src/shared/*.h` ao `DEPENDS` (ou usar um depfile do DXC) para que alterações
   de layout disparem a regeneração dos `.spv`.
3. **`-fvk-use-gl-layout` (opção a) segue descartada** — mantido o layout DX único para
   Vulkan/D3D12/Metal **e** GLES, conforme decisão registrada.
4. **M1.1** (lacunas ES, ortogonais): `usampler1D`/TMEM-1D, extensão NV espúria,
   `noperspective`, image load-store format, precisão default.
5. Não houve validação em hardware (R36S) nesta etapa — a verificação é de build/ferramentas.

## 10. Comandos de reprodução

```bash
# 1) aplica o padding nos 6 headers reais + backup + invalida os 58 blobs
bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_apply_padding.sh"

# 2) corrige o mismatch SDL2 do sysroot (headers 2.0.20 x lib 2.30.3)
#    2a) correcao de RAIZ: instala os headers publicos reais do SDL 2.30.3 no sysroot
bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_fix_sysroot_sdl2_headers.sh"
#    2b) (historico) remendos pontuais por declaracao — supersedidos por 2a
bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_fix_sysroot_sdl2.sh"

# 3) regenera os 58 blobs SPIR-V (comandos exatos do build.ninja)
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_regen_blobs.py" 6

# 4) valida (spirv-val / spirv-cross ES 320 / glslang + causas)
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_validate_blobs.py"

# 5) compara offsets significativos dos blobs reais contra o std430 (esperado: 0 divergencias)
python3 "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_offset_compare.py"

# 6) rebuild aarch64 (destacado, sobrevive entre chamadas)
bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_build_detached.sh"
```

### Reversão do padding (se necessário)

```bash
cp /root/bhrecomp/m1_apply_20261018/backup_headers/*.h /root/bhrecomp/lib/rt64/src/shared/
# (o header SDL2 do sysroot pode ficar corrigido: e correcao de ambiente, nao do M1)
# ATENCAO: reverter os headers exige REGENERAR os 58 blobs de novo (item 2.1).
```

## 11. Conclusão (fatos verificados)

1. O padding de layout validado no PoC v3 foi **aplicado na árvore real**
   (`lib/rt64/src/shared/`), com md5 pós-aplicação **idêntico** ao artefato aprovado no PoC
   (6/6) e backup dos originais preservado.
2. Os **58 blobs SPIR-V foram regenerados** executando os comandos DXC exatos do
   `build.ninja` (necessário porque os headers não são `DEPENDS` no CMake).
   Apenas **13 mudaram** — exatamente o conjunto antes inválido; **45 permaneceram
   md5-idênticos**.
3. Critérios de aceite do M1 **atingidos nos artefatos reais**:
   `spirv-val` falhas **13 → 0**; `spirv-cross --es --version 320` falhas **10 → 0**.
4. `m1_offset_compare.py`: **103 structs, 0 divergências** — o layout DX+padding é idêntico
   ao std430 (`RDPParams.keyScale@96`, stride 144; `RSPLight` stride 64;
   `RasterParams.screenScale@32`; `GPUTile.textureDimensions@48`).
5. Um bloqueio **pré-existente e ortogonal** do ambiente foi identificado e resolvido:
   sysroot aarch64 com headers SDL2 2.0.20 e biblioteca SDL2 2.30
   (`SDL_GetWindowSizeInPixels` não declarado) — corrigido restaurando a consistência
   headers↔lib, com prova RAW de que a lib exporta o símbolo.
6. Permanecem **13 shaders com lacunas de perfil ES 320** (usampler1D/TMEM-1D, extensão NV
   espúria, `noperspective`, image load-store format, precisão default) — escopo do M1.1,
   **ortogonal ao layout** e já caracterizado com atribuição de causa por mensagem.
7. A próxima etapa (M1.1 + pipeline de build GLSL ES 3.20) está registrada em
   `docs/PLANO_BACKEND_GLES_R36S.md`.
8. O **rebuild aarch64 foi concluído com sucesso** (`ninja: no work to do`): binário ELF
   aarch64 md5 `13b708c21762bff9e183c494512e5776`, com os 58 blobs (padding) embutidos e o
   agregado md5 dos blobs inalterado. O binário está pronto para teste no R36S; a validação
   em hardware **não** foi feita nesta etapa.