# Evidência M1.3 — Estágio 2: `spirv-cross` linkado no runtime + casos `GLSL_ES`

- **Data**: 2026-10-18
- **Conta/Alvo**: árvore local `/root/bhrecomp` (WSL), cross-compile aarch64 (`Toolchain-aarch64.cmake`) + host x86_64
- **Escopo**: M1.3 (decidir o shader em runtime) — Estágio 2 do `docs/PLANO_BACKEND_GLES_R36S.md`
- **Artefatos de execução**: `/root/bhrecomp/m1_3_gles/stage2/` (backup, logs, patch, binário host, ESSL)
- **Autores dos scripts**: `evidencias/tools/staged/` (ver §5)

---

## 1. Objetivo e resultado

O M1.2 gerou, para cada shader, um blob SPIR-V compilado com `-D HLSL_GLES`. Ele **não pode** ser
embutido como ESSL: o RT64 especializa 5 *spec constants* (`otherMode.L/H`, `colorCombiner.L/H`,
`flags.value`) **em runtime** via `respv::Optimizer::run`. Logo a conversão SPIR-V → ESSL 3.20
precisa acontecer **dentro do binário**.

| Item | Antes (M1.2) | Depois (M1.3 estágio 2) |
|---|---|---|
| `spirv-cross` no binário aarch64 | ❌ (só CLI de build, `find_program`) | ✅ **linkado** (`spirv-cross-c`) |
| Casos `RenderShaderFormat::GLSL_ES` no runtime | só `CREATE_SHADER_INPUTS` | ✅ raster + ubershader + post-blend + hw-resolve + cache |
| Blobs `*BlobGLSLES` referenciados no ELF | 31 arrays | ✅ **54 arrays** |
| Tamanho do binário | 19.869.608 B | 22.860.752 B (**+2.991.144 B**) |
| Aceite final (blob → re-spirv → spirv-cross → ESSL) | não executável | ✅ **12/12 shaders, `glslangValidator` 12/12** |

---

## 2. Prova (a) — `spirv-cross-c` linkado no binário aarch64

Log: `m1_3_stage2/logs/aarch64_build_tail.log`, `m1_3_stage2/logs/aarch64_driver.log`,
`m1_3_stage2/logs/reconfigure.log`.

```
=== reconfigure 2026-10-18T14:07:04-03:00 ===
reconfigure rc=0
=== build 2026-10-18T14:07:06-03:00 ===
ninja rc=0
=== link final ===
-rwxr-xr-x 1 root root 22860752 Oct 18 14:18 /root/bhrecomp/build-aarch64/BodyHarvestRecompiled
=== simbolos GLSLES ===
108
=== simbolos spirv-cross no binario ===
228
```

Bibliotecas estáticas geradas no build cross (passos 6/10/11 de 231):

```
[6/231]  Linking CXX static library rt64/src/contrib/spirv-cross/libspirv-cross-core.a
[10/231] Linking CXX static library rt64/src/contrib/spirv-cross/libspirv-cross-glsl.a
[11/231] Linking CXX static library rt64/src/contrib/spirv-cross/libspirv-cross-c.a
```

Verificações independentes no ELF final (`aarch64-linux-gnu-nm --defined-only`):

```
binario 22860752 B  md5 002ebe73398da05613b3396d4bb2d615
BlobGLSLES (pares array+_size) ....... 108   (=> 54 arrays)
dos quais arrays (sem _size) ......... 54    (M1.2: 31)
simbolos spvc_ definidos ............. 228
```

**Conclusão (fato verificado)**: o `spirv-cross` (backend GLSL + API C) está resolvido no link do
binário aarch64 e os 54 blobs do canal GLES passaram a ser referenciados (o linker não os descarta
mais, pois `rt64` é `STATIC` e antes nenhum caminho `GLSL_ES` do raster os alcançava).

### Perfil de build do spirv-cross (deliberadamente mínimo)

`SPIRV_CROSS_CLI=OFF`, `SPIRV_CROSS_ENABLE_TESTS=OFF`, `SPIRV_CROSS_SKIP_INSTALL=ON`,
`ENABLE_HLSL/MSL/CPP/REFLECT/UTIL=OFF`, `ENABLE_C_API=ON`, `STATIC=ON`.
GATE em `RT64_GLSL_ES_SHADERS=ON` → builds DX/VK/MSL **permanecem byte-idênticos**.

### Estado canônico preservado

```
NFD_PORTAL:BOOL=OFF
RT64_GLSL_ES_SHADERS:BOOL=ON
Toolchain-aarch64.cmake:18  set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--allow-shlib-undefined")
ninja -C build-aarch64 BodyHarvestRecompiled  ->  ninja: no work to do.
```
---

## 3. Prova (c) — aceite final: blob GLES → `respv::Optimizer::run` → `spirv-cross` → ESSL 3.20

O aceite **não** é um simulador: `evidencias/tools/staged/m1_3_stage2_host.cpp` chama o **código de
produção** (`lib/rt64/src/render/rt64_glsl_es.cpp` + `respv::Optimizer`) sobre os **blobs GLES reais**
extraídos do build cross. Log: `m1_3_stage2/host_test.txt` / `m1_3_stage2/validate.log`.

```
M1.3 estagio 2 -- aceite host-side do caminho de runtime do canal GLES
spec constants: omL=0x00504A50 omH=0x00000080 ccL=0xFC127E24 ccH=0xFFFFF3F9 flags=0x00000005

SHADER                     STAGE    SPV_IN   SPV_OPT      ESSL  RESPV_MS   XC_MS OK   NOTE
RasterVSSpecConstant       vert       4676      2320      1124      0.03     2.4 ok
RasterVSSpecConstantFlat   vert       4748      2368      1171      0.01     0.4 ok
RasterPSSpecConstant       frag     284228     11120      8777      2.98     3.4 ok
RasterPSSpecConstantMS     frag     285160     11172      8777      2.71     2.6 ok
RasterPSSpecConstantFlat   frag     284376     11244      8814      1.61     2.1 ok
RasterPSSpecConstantFlatMS frag     285308     11296      8814      1.18     2.4 ok
RasterVSDynamic            vert       5220      5220      2964      0.00     0.7 ok
RasterPSDynamic            frag     113652    113652    260915      0.00    52.5 ok
RasterPSDynamicMS          frag     114584    114584    262267      0.00    41.5 ok
FullScreenVS               vert        860       860       373      0.00     0.3 ok
TextureCopyPS              frag       1212      1212       623      0.00     0.3 ok
PostBlendDitherNoiseAddPS  frag       7676      7676      4807      0.00     2.3 ok

shaders=12 ok=12 fail=0 essl_total=569426 B respv_total=8.5 ms cross_total=111.0 ms
host_test rc=0
```

Validação do ESSL emitido com `glslangValidator -S vert|frag` (mesmo validador do M1.1/M1.2):

```
glslangValidator: pass=12 fail=0
```

Invariantes textuais do sanitizador conferidas shader a shader (12/12):

```
ver=#version 320 es   highp=1  nopersp=0  mediump=0  nvgpu=0
```

### Leitura dos números

- **Caminho quente (spec constants)**: SPIR-V GLES 284 KB → **11,1 KB** pós-`re-spirv` →
  **8.777–8.814 B** de ESSL. Aceite do plano (`< 50 KB`) **superado com folga (~5,7×)**.
  Custo no host x86-64: `re-spirv` 1,2–3,0 ms + `spirv-cross` 2,1–3,9 ms.
- **Caminho do ubershader (`RasterPSDynamic*`)**: **260.915 / 262.267 B de ESSL** — sem especialização
  (usa `DYNAMIC_RENDER_PARAMS` via UBO). Ver risco **R7** em §6.

---

## 4. Mudanças no código (15 edições + 3 arquivos novos)

Auditoria de integridade (`m1_3_stage2/apply.log`; backup em `/root/bhrecomp/m1_3_gles/stage2/backup/`):

| Arquivo | md5 ANTES | md5 DEPOIS |
|---|---|---|
| `lib/rt64/CMakeLists.txt` | `9dfb65cd9bd76bad806daaaf3f56db1b` | `aab8b85f9eb8d9a9ad3133ca26c65087` |
| `src/render/rt64_shader_library.cpp` | `3ca7b5b953c4b3a21d090409ed97ff2a` | `96c20c248ba1d7a3532bd5206ee23700` |
| `src/render/rt64_raster_shader.cpp` | `fa672a7e9e8694579014c86c44d4e38a` | `1306d9fd2d1631558bd25d895b899d50` |
| `src/render/rt64_raster_shader.h` | `aba39baa6fe1385218765ea81a2d3412` | `68bc02533ef33fd2d4a70904749f33ae` |
| `src/render/rt64_raster_shader_cache.cpp` | `a6c812831a918f68f089977d1994c81b` | `949a39bdc0ec5f84f56f3b86d1f2df35` |
| `src/render/rt64_glsl_es.h` **(novo)** | — | `58eb4b478dfd948f49ad376c0a481b49` |
| `src/render/rt64_glsl_es.cpp` **(novo)** | — | `d2128832b770d8ab3f9fd8ec627cf864` |
| `src/render/rt64_glsl_es_device.h` **(novo)** | — | `9532faa979c8ae862abf7e8202304054` |

Conferência de contagens automatizada (`apply.log`):

```
createShader(device,  em shader_library : 37
createShader(device,  em raster_shader  : 20   (17 substituicoes + 3 insercoes novas)
device->createShader( residual          : shader_library=0, raster_shader=0
case RenderShaderFormat::GLSL_ES        : shader_library=3, raster_shader=4, cache=1
```

### Decisões de arquitetura (e por quê)

1. **`rt64_glsl_es.{h,cpp}` é livre de `plume`.** Contém a única lógica conversora
   (`convertSPIRVToGLSLES`). Isso permite compilá-la e exercitá-la num **host x86_64 sem SDL/X11**,
   que é exatamente o que o aceite usa. O wrapper que toca o dispositivo ficou em
   `rt64_glsl_es_device.h` (**header-only**, `inline`), pois depende de `plume`.
2. **Um único ponto de conversão.** `RT64::createShader(device, data, size, entry, format)` converte
   quando `format == GLSL_ES` e **repassa inalterado** nos demais formatos. Todos os 57 pontos de
   `device->createShader(` dos dois arquivos passaram a usá-lo → **zero mudança semântica** para
   DXIL/SPIRV/METAL.
3. **Fidelidade ao pipeline já validado.** A conversão reproduz o CLI `spirv-cross --es --version 320`
   **incluindo os defaults que o CLI aplica quando `--vulkan-semantics` não é passado**
   (`combined_image_samplers = true` + `build_dummy_sampler = true`, com
   `DescriptorSet=0/Binding=0` no dummy). Sem isso o ESSL não compila em ESSL 3.20. O sanitizador
   (`noperspective`, `mediump→highp`, injeção de `precision highp float;`) foi portado 1:1 de
   `src/tools/glsl_es_sanitize.cmake` — o **mesmo** validado no M1.1/M1.2.
4. **Blobs SPIRV ≠ blobs GLES no caminho de hardware resolve.** O `RtCopy*`/`TextureResolve*`
   passou a ter bloco `GLSL_ES` próprio com `*BlobGLSLES`: os blobs SPIRV padrão usam textura 1D /
   descriptor indexing e gerariam ESSL inválido. Também `OptimizerCacheSPIRV::initialize(format)`
   passa a parsear o canal correto.
5. **GATE em `RT64_GLSL_ES_SHADERS`.** `add_subdirectory(src/contrib/spirv-cross)`, o link e o
   `target_sources` só ocorrem nesse modo, preservando a invariante "builds DX/VK/MSL byte-idênticos".

---

## 5. Reprodução

Todos os scripts foram autorados em `evidencias/tools/staged/` (lado Windows) e copiados para
`/root/bhrecomp/m1_3_gles/stage2/staged/` antes de rodar — evita a armadilha do runner que remove
`$var` da linha de comando.

| Script | Função |
|---|---|
| `m1_3_stage2_apply.sh` | copia os fontes novos, roda o patcher Python, confere contagens |
| `m1_3_stage2_apply.py` | as 15 edições; **exige contagem exata** por ancoragem; guard de md5 que recusa rodar sobre árvore já patchada; backup automático |
| `m1_3_stage2_build_aarch64.sh` | reconfigure + `ninja` desacoplado (`setsid`) + contagem de símbolos |
| `m1_3_stage2_host.sh` | configura/builda o projeto host standalone |
| `m1_3_stage2_validate.sh` | roda o aceite + `glslangValidator` + invariantes textuais (foreground) |
| `CMakeLists.host.txt` | projeto CMake standalone (spirv-cross + re-spirv + `rt64_glsl_es.cpp` + 12 blobs `.c`) |
| `m1_3_stage2_host.cpp` | harness: 12 shaders (6 spec-constant + 6 blob direto) |
| `rt64_glsl_es.h` / `.cpp` / `rt64_glsl_es_device.h` | código de produção |

Sequência:

```bash
bash "/mnt/c/.../evidencias/tools/staged/m1_3_stage2_apply.sh"      # 1. patch (rapido)
bash "/mnt/c/.../evidencias/tools/staged/m1_3_stage2_build_aarch64.sh"  # 2. build aarch64 (detached)
bash "/mnt/c/.../evidencias/tools/staged/m1_3_stage2_host.sh"       # 3. build host (detached)
bash "/mnt/c/.../evidencias/tools/staged/m1_3_stage2_validate.sh"   # 4. aceite + validacao
```

### Notas de campo (aprendidas nesta sessão)

- **`runner` remove `$var`** de qualquer comando passado por `run_commands`: loops com `$pass`/`$stage`
  viram comandos quebrados (a primeira tentativa de validação deu `pass=`/`fail=` vazios). Sempre
  autorar script em arquivo e invocar por caminho literal entre aspas.
- **Não re-executar um patcher destrutivo**: a 2ª execução de `m1_3_stage2_apply.sh` abortou na
  contagem e o *restore* apagou os 3 fontes novos (o backup havia sido refeito já no estado patchado).
  Corrigido com o guard `BASELINE_MD5`.
- **Não apagar `build/` enquanto um build roda** nele: o `rm -rf` da 1ª tentativa do host removeu
  diretórios de `.d` no meio da compilação de `spirv_glsl.cpp` (fatal `opening dependency file`).
- `rt64` é `STATIC`: blobs GLES não referenciados eram **descartados pelo linker** — o salto de 31 → 54
  arrays no ELF é a prova de que os caminhos `GLSL_ES` agora alcançam o raster.

---

## 6. Riscos / pendências

- **R7 (novo, importante para M2/M6) — custo do ubershader.** `RasterPSDynamic` /
  `RasterPSDynamicMS` produzem **260.915 / 262.267 B** de ESSL, porque não passam por
  especialização (`DYNAMIC_RENDER_PARAMS` via UBO). No host o `spirv-cross` sozinho leva ~50 ms;
  extrapolando para o Mali-G31/RK3326 (§M1.3 estágio 1: ~20–50× o host) o *stall* de partida pode
  ser de **segundos**. Mitigações a avaliar no M2: (i) não materializar o ubershader em GLES e
  depender do caminho `RasterShader`; (ii) cache em disco da especialização; (iii) medir de fato no
  device antes de decidir. **Nota**: o mesmo risco já existia em SPIRV (113 KB), mas 260 KB de ESSL
  *texto* é ordens de grandeza pior para o compilador do driver.
- **R1 (herdado) — sysroot Ubuntu 22.04 (glib 2.72) vs device Debian 13 (glib 2.84).**
  Continua valendo regenerar o sysroot a partir de `/opt/r36s/rootfs` (também permitiria remover
  `--allow-shlib-undefined`).
- **R2 (herdado) — RUNPATH em `/root/sysroot64/…`** (inócuo no device); decidir `CMAKE_SKIP_RPATH` no M5.
- **`DebugPS`**: tem blob GLES gerado, mas está no `RT64_GLSL_ES_TEXT_SKIP` da validação (usa
  `readonly image2D` do caminho de ray tracing). Não entra no aceite acima — segue fora do conjunto
  ESSL por decisão do M1.1.
- **Custo no device** (item (d) do plano) continua sendo escopo do **M5** — nada aqui mede o Mali-G31.

---

## 7. Conclusão

O M1.3 estágio 2 está **concluído**: `spirv-cross` está linkado no binário aarch64
(`ninja rc=0`, 228 símbolos `spvc_`, +2,99 MB) e os casos `RenderShaderFormat::GLSL_ES` cobrem o
caminho quente do raster, o ubershader, o post-blend, o hardware resolve e o cache do otimizador.
O aceite roda o **código de produção** sobre os **blobs reais** e produz ESSL 3.20 válido em
**12/12** shaders, com o caminho especializado entre **8,8 KB e 8,8 KB** (era 284 KB de SPIR-V).
O próximo passo do plano é o **M2** (`plume_gles` + apresentação), já com o risco **R7** registrado.