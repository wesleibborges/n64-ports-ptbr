# EVIDÊNCIA — M1.2: canal OpenGL ES (ESSL 3.20) no build do RT64

- **Data**: 2026-10-18 · **Ambiente**: WSL x86_64 (Ubuntu jammy), cross-build aarch64
  (`/root/bhrecomp/build-aarch64`, CMake 4.4.4, Ninja), DXC `x64`, `spirv-cross`,
  `glslangValidator` no PATH
- **Objetivo (Passo 1 do plano)**: materializar o canal GLES no build — novo
  `RenderShaderFormat::GLSL_ES`, 4º blob em `CREATE_SHADER_INPUTS`, alvo CMake de geração
  GLES, correção do `DEPENDS` latente — com aceite: *"o build aarch64 gera os blobs GLES,
  `ninja -t deps` lista os headers como dependência, `-D HLSL_GLES` não altera os blobs
  DX/VK (regress 58/58)"*.
- **Pré-requisitos**: M1 (padding de layout) + M1.1 (adaptações de fonte gated por
  `HLSL_GLES`, 57/57 ESSL) — `evidence_m1_1_glsl_es_shaders_20261018.md`.

## 0. Decisão de rota (registro)

Rota **B** (backend `plume_gles` próprio no RT64) mantida. O GLideN64 é rejeitado como
implementação (arquitetura HLE-GBI × plugin LLE de mupen64plus; licença GPL-2 contra
MIT do RT64) e passa a ser usado **apenas como oráculo de validação visual**, se
necessário. Nada no M1.2 depende do GLideN64.

## 1. Artefatos de fonte editados (com backup e md5)

Script idempotente com backup/revert: `evidencias/tools/m1_2_apply_gles_channel.py`
(`apply` / `revert` / `check`). Backups em `/root/bhrecomp/m1_2_gles/backup/`.

| Arquivo | O que mudou | md5 pós-patch |
|---|---|---|
| `lib/rt64/src/contrib/plume/plume_render_interface_types.h` | `RenderShaderFormat::GLSL_ES` (APPEND ao fim, preserva DXIL=1/SPIRV=2/METAL=3) | `bc8d0d186d9b6b61141172db90eb6d88` |
| `lib/rt64/src/render/rt64_shader_library.cpp` | 44 includes `.hlsl.glsl_es.h` (gated `RT64_GLSL_ES_BLOBS`), macro `CREATE_SHADER_INPUTS` com 4 blobs, 32 call sites com `<X>BlobGLSLES` | `3ca7b5b953c4b3a21d090409ed97ff2a` |
| `lib/rt64/CMakeLists.txt` | `option(RT64_GLSL_ES_SHADERS OFF)`, `build_shader_glsl_es_impl`, hooks em `build_shader()`/`build_shader_spirv()`, alvo `rt64_glsl_es_validate`, headers no `DEPENDS` | `a7fff41162511165b5cfc8941cae4212` |

Fonte patcheada com `-D HLSL_GLES` (aplicação **definitiva**, inerte sem a macro — o gate
é do M1.1): `shared/rt64_hlsl.h` `c85cabfd0af1b326417ab11b2f3dd4a4`,
`shaders/FbRendererCommon.hlsli` `7bdaefcbc9a2cf4a3f11125a6ad3391e`,
`shaders/TextureDecoder.hlsli` `a2d2043a0b5bc98fbd66c4d9da846502`,
`shaders/FbReinterpretCS.hlsl` `17540b5c9d7abf550120fc9d1efda977`,
`shaders/TextureDecodeCS.hlsl` `75fb99cf9a02960cd47ca48665ede803` (5/5 iguais ao baseline
"after" do M1.1). Novos: `src/tools/glsl_es_sanitize.cmake`, `src/tools/glsl_es_validate.cmake`.

## 2. O que o `build.ninja` passou a conter (prova RAW)

```bash
cmake -B build-aarch64 -DRT64_GLSL_ES_SHADERS=ON      # Configuring done / Generating done
grep -c 'glsl_es' build-aarch64/build.ninja           # 590 linhas
wc -l build-aarch64/glsl_es_stages.txt                # 58 (mapa <spv> <stage>)
grep -c ' frag$' build-aarch64/glsl_es_stages.txt     # 30
grep -c ' comp$' build-aarch64/glsl_es_stages.txt     # 22
grep -c ' vert$' build-aarch64/glsl_es_stages.txt     # 6   (30+22+6 = 58)
```

Comando DXC gerado (shader de fragmento, prova do `-D HLSL_GLES`):

```
LD_LIBRARY_PATH=.../dxc/lib/arm64 .../dxc-linux -spirv -fspv-target-env=vulkan1.0 \
  -fvk-use-dx-layout -D HLSL_GLES -I.../src -E PSMain -T ps_6_3 -D DYNAMIC_RENDER_PARAMS \
  /root/bhrecomp/lib/rt64/src/shaders/RasterPS.hlsl \
  /Fo /root/bhrecomp/build-aarch64/src/shaders/RasterPSDynamic.hlsl.glsl_es.spv
```

**`DEPENDS` corrigido (bug latente do M1)** — a regra agora lista os headers de verdade
(20 `.hlsli` + 30 `shared/*.h`), provado no `build.ninja`:

```
build src/shaders/FullScreenVS.hlsl.glsl_es.spv | ...: CUSTOM_COMMAND \
  /root/bhrecomp/lib/rt64/src/shaders/FullScreenVS.hlsl \
  /root/bhrecomp/lib/rt64/src/shaders/Background.hlsli ... \
  /root/bhrecomp/lib/rt64/src/shared/rt64_hlsl.h ... \
  /root/bhrecomp/lib/rt64/src/shared/rt64_video_interface.h || file_to_c
```

Compile definition do canal: `DEFINES = ... -DPLUME_SDL_VULKAN_ENABLED -DRT64_GLSL_ES_BLOBS ...`.
## 3. Aceite — conjunto ESSL 3.20 valida

```bash
cmake -B build-aarch64 -DRT64_GLSL_ES_SHADERS=ON
ninja -C build-aarch64 shaders/InterfacePS.hlsl.glsl_es.c shaders/InterfaceVS.hlsl.glsl_es.c \
      rt64_glsl_es_validate
```

```
[164/165] M1.2 GLES: validando o conjunto ESSL 3.20 com glslangValidator
-- RESUMO M1.2 GLES: shaders=58 ok=57 excluidos=1 ausentes=0 falhas=0
```

Igual ao critério do M1.1: **57/57 compilam**, com `DebugPS` excluído por design
(`readonly image2D` do caminho de ray tracing, não expressável em ESSL 3.20).
Log RAW: `/root/bhrecomp/m1_2_gles/ninja_validate2.log`.

O alvo converte cada `.glsl_es.spv` com `spirv-cross --es --version 320`, sanitiza
(`src/tools/glsl_es_sanitize.cmake`: `noperspective` removido, `mediump`→`highp`, preâmbulo
de precisão; a extensão `GL_NV_gpu_shader5` **falha o build** por ser tratada como regresso
da fonte) e valida com `glslangValidator -S <stage>`.

### 3.1 Falso-positivo de estágio encontrado no caminho (corrigido)

A 1ª execução do alvo deu `ok=28 ... falhas=27`, exatamente o padrão de falso-positivo do
M1.1 §1 (vertex/compute validados como fragment). Causa: `${ARGN}` chega ao CMake como
**lista** (`-E;PSMain`), e o regex usava `-E +` (espaço). Corrigido para
`-E[^A-Za-z0-9]+([A-Za-z0-9_]+)`; mapa passou de 58×`frag` para 30 frag / 22 comp / 6 vert.

## 4. Não-regressão dos blobs DX/VK

Os 56 `*.spirv.c` de `build-aarch64/src/shaders/` foram md5-somados antes e depois do canal
GLES (o DXC **re-executou** todos, porque o `DEPENDS` passou a incluir os headers):

```
diff md5_spirv_before.txt md5_spirv_after.txt   ->  vazio
IDENTICOS 56/56
```

Conclusão: o canal GLES não altera um byte do caminho DX/VK; o binário do M1 permanece válido.

## 5. Tamanhos medidos (subsidiam a decisão do M1.3)

| Conjunto | Total | Observação |
|---|---|---|
| SPIR-V GLES (`.glsl_es.spv`) | **1.584.516 B** (~1,58 MB) | **blob embutido** como `<X>BlobGLSLES` |
| ESSL 3.20 sanitizado (`.glsl_es`) | 3.468.332 B (~3,47 MB) | byproduct de validação (2,2× maior) |
| C gerado dos 56 SPIR-V GLES (`.glsl_es.c`) | 5.496.185 B | `file_to_c` emite inteiros decimais |
| Contagens | 56 `.glsl_es.spv` + 56 `.glsl_es.c` (rt64) + 2 (frontend) = **58**; 55 `.glsl_es` sanitizados | DebugPS sem ESSL |

**Decisão de desenho (explícita)**: o blob embutido é o **SPIR-V compilado com
`-D HLSL_GLES`**, não o texto ESSL. Motivos: (a) 2,2× menor; (b) é o único formato que
permite o caminho aprovado do M1.3 — otimizar com `re-spirv` **antes** de converter com
`spirv-cross` (não há como especializar texto ESSL); (c) o texto continua no build dir para
validação/fallback. O plano descrevia o blob como "GLSL ES"; a troca fica registrada no
plano (§M1.2) e é reversível trocando o argumento do `file_to_c` em
`build_shader_glsl_es_impl`.

## 6. Bloqueio de ambiente resolvido (ortogonal, pré-existente)

Reconfigurar o build aarch64 falhava com:

```
CMake Generate step failed. Imported target "SDL2::SDL2" includes non-existent path "/usr/include/SDL2"
```

Causa: `/root/sysroot64/usr/lib/aarch64-linux-gnu/cmake/SDL2/sdl2-config.cmake` declara
`set(prefix "/usr")` (path **do device**). Correção idempotente com backup:
`evidencias/tools/m1_2_fix_sysroot_sdl2_prefix.sh` → `prefix "/root/sysroot64/usr"`.
md5 antes `a2f42bdde106dd87be38297144aa59f5` → depois `f2cf0570c5296d6345f7d37035b3cf0f`
(backup em `/root/bhrecomp/m1_2_gles/sdl2-config.cmake.orig`).

## 6.1 Link do binário completo: bloqueio de ambiente (pré-existente, pendente)

O `ninja -C build-aarch64 BodyHarvestRecompiled` chega a **121/122** (todos os objetos, incluindo
`rt64_shader_library.cpp` com a macro de 4 blobs e os 44 includes GLES) e falha **apenas no link**,
por incompletude do sysroot (cadeia GTK/cairo que chega via `nfd`/pkg-config):

```
ld: libcairo.a(cairo-png.o): undefined reference to symbol 'png_read_end@@PNG16_0'
ld: libpng16.so.16: error adding symbols: DSO missing from command line
```

Tentativas medidas nesta sessão (todas **revertidas**, para não deixar meia-solução na árvore):

- `libpng16.so` explícito no alvo do port → o CMake emite libs diretas **antes** das transitivas e,
  com `--as-needed` (default), a DSO é descartada naquela posição (o erro muda, não fecha).
- `libpng16.so` no `nfd` (após `GTK3_LINK_LIBRARIES`) → **não chegou** à linha de link gerada.
- `-Wl,--no-as-needed` / `-Wl,--copy-dt-needed-entries` → o segundo faz o `ld` seguir `DT_NEEDED` e
  passa a puxar `libz.so.1` e `libgcrypt.so.20`; esta última exige `gpgrt_rewind@GPG_ERROR_1.0` e
  **`libgpg-error` não existe no sysroot** → caminho sem fim por essa via.

Conclusão honesta: é a mesma classe de problema que a sessão anterior resolveu com
"link manual iterativo" (`_link_all3.sh`, `_ldbind.log` no diretório do port). **Não é regressão do
M1.2** (nenhuma alteração de link foi deixada na árvore) e **não afeta o aceite**: os blobs GLES, o
ESSL 57/57 e a não-regressão DX/VK independem do link. O binário M1 do port segue **intacto**
(`BodyHarvestRecompiled.m1_padding_20261018`, md5 `13b708c21762bff9e183c494512e5776`, 19.770.744 B).

Próximo passo isolado (~0,5 sessão): reconstruir a linha de link com a cadeia explícita (incluindo
`libpng16`, `libz` e as libs de suporte presentes no sysroot) **ou** completar o sysroot a partir do
rootfs do device.

## 9. Estado deixado no ambiente (handoff)

| Item | Estado |
|---|---|
| Árvore RT64 | canal GLES aplicado (enum `GLSL_ES` + macro de 4 blobs + `option(RT64_GLSL_ES_SHADERS)`) |
| Fontes `-D HLSL_GLES` | aplicadas em definitivo (5 arquivos; gates inertes sem a macro) |
| Sysroot SDL2 | `sdl2-config.cmake` com `prefix "/root/sysroot64/usr"`, `SDL2_INCLUDE_DIRS` = padrão do pacote, + dir aninhado `include/SDL2/SDL2` (91 symlinks) — **sem** include global (evita sombrear o Vulkan vendorizado) |
| Backups (revert) | `/root/bhrecomp/m1_2_gles/backup/` (3 arquivos) + `sdl2-config.cmake.orig` + `nfd_src_CMakeLists.bak` + `CMakeLists.port.bak` |
| Build aarch64 | 121/122 objetos; **link pendente** (§6.1); `rt64_glsl_es_validate` = **57/57 OK** |
| Binário do port | `BodyHarvestRecompiled` (M1, md5 `dbc386ba918d898a01038d7ff943768a`) e `.m1_padding_20261018` (md5 `13b708c2…`) intactos |
| Reconfirmação final | `RESUMO M1.2 GLES: shaders=58 ok=57 excluidos=1 ausentes=0 falhas=0` (`ninja_validate3.log`), após todas as reconfigurações |

```bash
# 1) liga o canal na arvore (backup + md5; revert disponivel)
python3 ".../evidencias/tools/m1_2_apply_gles_channel.py" apply

# 2) corrige o prefix do SDL2 no sysroot (uma vez por ambiente)
bash ".../evidencias/tools/m1_2_fix_sysroot_sdl2_prefix.sh"

# 3) reconfigura e gera os blobs GLES + valida o ESSL 3.20
cmake -B build-aarch64 -DRT64_GLSL_ES_SHADERS=ON
ninja -C build-aarch64 shaders/InterfacePS.hlsl.glsl_es.c shaders/InterfaceVS.hlsl.glsl_es.c \
      rt64_glsl_es_validate

# 4) binario aarch64 completo
ninja -C build-aarch64 BodyHarvestRecompiled     # (rodar destacado: setsid nohup)

# 5) reverter a arvore
python3 ".../evidencias/tools/m1_2_apply_gles_channel.py" revert
```

> Nota de runner: `run_commands` encerra a sessão em ~30 s — os passos 3/4 rodaram
> destacados (`setsid nohup ... < /dev/null &`) com acompanhamento por `tail`.

## 8. Limitações / o que NÃO está feito aqui

1. **Runtime GLES ainda não consome o formato**: os `switch` de runtime
   (`rt64_raster_shader.cpp`, `rt64_raster_shader_cache.cpp`, seleção de blobs MSAA em
   `rt64_shader_library.cpp`, `UserConfiguration::GraphicsAPI`) seguem sem o caso
   `GLSL_ES` — é M1.3/M2 (a conversão SPIR-V→ESSL dentro do binário e o `plume_gles`).
2. `DebugPS` tem blob GLES (SPIR-V) mas **não** tem ESSL: o caminho de ray tracing não
   existe em GLES; o alvo de validação o exclui por lista explícita.
3. A validação é **de compilação** (glslangValidator), não de execução em device: o
   `glShaderSource` no Mali-G31 fica para o M2 (gate 1: frames na tela).
4. Os 2 shaders do frontend (`InterfacePS/VS`) entram no mapa porque o frontend reusa as
   funções de shader do RT64; o alvo de validação os reporta como "ausentes" quando não
   foram construídos antes (não é falha) — no run final eles estavam presentes (ausentes=0).