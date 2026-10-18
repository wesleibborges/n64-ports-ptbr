# Evidência — M3/pré: sonda GLES NATIVA no R36S (Mali-G31)

**Data:** 2026-10-18
**Escopo:** pré-validação do passo 4 do plano (`M3 — descriptors sem bindless`) — antes de
escrever código de raster/descriptors, provar no hardware o que até aqui só existia em
inferência: **o EGL + GLES 3.2 do blob Mali do R36S funciona, e com que capacidades.**
**Pasta de trabalho (WSL):** `/root/bhrecomp/m3_gles_probe/`
**RAW reproduzível:** `evidencias/m3_gles_probe/raw_offline.txt` (171 linhas, md5
`8d5b433061b949c47238c08eb569a7d1`) — gerado por `bash evidencias/tools/m3_gles_probe_raw.sh`.
**Regra aplicada:** `evidence-collection` (toda ação gera evidência RAW persistida).

---

## 0. Estatuto do que está provado aqui

| # | Afirmação | Estatuto |
| :-- | :--- | :--- |
| 1 | O device tem EGL **completo** e GLES **3.2** reais, via blob ARM | ✅ provado offline (símbolos + strings) |
| 2 | O blob **não é linkável** (sem SONAME, `.dynsym` malformado) | ✅ provado (erro de link reproduzido) |
| 3 | As sondas aarch64 carregam em runtime e resolvem EGL por `dlopen` | ✅ provado sob QEMU contra a rootfs |
| 4 | O **contexto GLES 3.2** é criado no device | ⏳ **só no device** (QEMU não tem GPU) |
| 5 | As extensões/limites listados no probe existem em runtime | ⏳ **só no device** (as strings são indício forte) |
| 6 | O backend `plume_gles` roda sobre o driver real (15/15) | ⏳ **só no device** |

Os itens 4-6 são o **aceite do M3/pré** e exigem ~1 minuto de execução no R36S (§9).

---

## 1. Cadeia de symlinks: o "driver GLES do R36S" é UM blob ARM

```
lrwxrwxrwx libEGL.so     -> libMali.so
lrwxrwxrwx libEGL.so.1   -> libMali.so
lrwxrwxrwx libGLESv2.so.2-> libMali.so
lrwxrwxrwx libGLESv3.so.3-> libMali.so
lrwxrwxrwx libgbm.so.1   -> libMali.so
lrwxrwxrwx libMali.so    -> libmali-bifrost-g31-rxp0-gbm.so   (40.867.064 bytes)
```

Consequência que organiza todo o resto: **EGL, GLESv2/v3 e GBM são o MESMO arquivo**. Não há
dispatcher, não há `eglGetProcAddress` de terceiros, e o `libEGL_mesa.so.0.0.0` presente na
rootfs **não** é uma implementação alternativa (exporta **1** símbolo, `__egl_Main`).

---

## 2. Correções a afirmações anteriores (importante)

### 2.1 A nota do M2 sobre EGL estava ERRADA

`evidencias/m2_gles_s2/gles_target_probe.cpp` afirma, no cabeçalho:

> "o rootfs do dArkOS aponta `libEGL.so.1 -> libMali.so` (blob ARM, exige GPU Mali real) e NAO
> contem o dispatcher GLVND; a unica lib EGL real e' `libEGL_mesa.so.0.0.0`, que e' uma lib
> VENDOR do GLVND (**nao exporta eglGetDisplay/eglGetProcAddress** -- comprovado por erro de link)"

O blob Mali **exporta** o núcleo EGL inteiro. RAW:

```
  eglGetDisplay                EXPORTA
  eglGetProcAddress            EXPORTA
  eglInitialize                EXPORTA
  eglChooseConfig              EXPORTA
  eglCreatePbufferSurface      EXPORTA
  eglCreateContext             EXPORTA
  eglMakeCurrent               EXPORTA
  eglTerminate / eglGetError   EXPORTA
  total de simbolos T no blob: 1175
```

e, em runtime sob QEMU, **`15/15`** entry points resolvem por `dlsym` no blob.

O que **era** verdade é a parte do *link*: o blob não serve de biblioteca de link (§3). A
conclusão do M2 ("sob QEMU não existe caminho para obter contexto GLES") continua correta
**por outro motivo** — ausência de GPU —, não porque o EGL não exista.

### 2.2 R6 (risco de link) — **confirmado**, com causa exata

```
--- SONAME / RPATH (esperado: vazio) ---
(nenhum SONAME/RUNPATH/RPATH nos DT_* do blob)
--- teste de link real contra o blob ---
ld: .../libEGL.so.1: .dynsym local symbol at index 3 (>= sh_info of 3)
ld: .../libEGL.so.1: .dynsym local symbol at index 4 (>= sh_info of 3)
...
link_rc=2  (diferente de 0 == blob NAO e' linkavel; usar o stub)
```

### 2.3 R8 (`sem BGRA`, `sem 16-bit UNORM`) — **metade caiu**

`GL_EXT_texture_format_BGRA8888` **está presente** no blob (strings), enquanto
`GL_EXT_texture_norm16` **não está**. Ou seja: o LADO BGRA do R8 provavelmente não existe;
o lado 16-bit UNORM existe. **Confirmação exige o device** (§6/§9) — strings de blob são
indício, não prova de `glGetString(GL_EXTENSIONS)`.

### 2.4 R9 (`sem GL_MIRROR_CLAMP_TO_EDGE`) — a substituição disponível melhorou

O blob cita `GL_EXT_texture_border_clamp` — que é o mecanismo ES correto para o que o
MIRROR_CLAMP_TO_EDGE fazia no Vulkan/D3D12. Ainda é trabalho do M3, mas deixa de ser "sem
alternativa".

### 2.5 As extensões que o M4 dava como risco estão TODAS presentes (offline)

```
  GL_ARM_shader_framebuffer_fetch                      PRESENTE   <- M4 (framebuffer fetch)
  GL_EXT_multisampled_render_to_texture                PRESENTE   <- M4 (MSAA/resolve)
  GL_EXT_buffer_storage                                PRESENTE   <- M2/M3
  GL_EXT_texture_storage                               PRESENTE
  GL_EXT_texture_format_BGRA8888                       PRESENTE   <- R8
  GL_KHR_debug                                         PRESENTE
  GL_EXT_disjoint_timer_query                           PRESENTE   <- M5 (medir FPS)
  GL_EXT_geometry_shader                               PRESENTE   <- M4
  GL_EXT_texture_border_clamp                          PRESENTE   <- R9
  GL_OES_texture_storage_multisample_2d_array          PRESENTE
  GL_EXT_texture_norm16          NAO citado
  GL_EXT_render_snorm            NAO citado
```

E a versão embutida no blob:

```
OpenGL ES 3.2 v1.r13p0-01rel0.8747d14aec16ec21ac2b2da252c4ec5f
```

Isto é o **alvo exato** do backend (ES 3.2), medido antes de qualquer linha de raster.

---

## 3. Decisão de projeto derivada: sondas **sem link** contra EGL/GLES

Como o blob não é linkável, as duas sondas foram escritas para **não referenciar EGL/GLES no
link**:

* `gles_device_probe_aarch64` — 100% `dlopen`/`dlsym`. `DT_NEEDED` final:
  ```
  libstdc++.so.6, libgcc_s.so.1, libc.so.6, ld-linux-aarch64.so.1
  RPATH/RUNPATH: (vazio)
  ```
  Nenhuma linha `libEGL`/`libGLES` no link. Roda em qualquer aarch64 com libc.
* `gles_smoke_aarch64` — o smoke do M2 (15/15 no host) chama 10 entry points EGL de forma
  direta; para linká-lo foi criado um **stub de link-time** `libEGL.so.1`
  (`evidencias/tools/gles_egl_stub.c`), com `SONAME=libEGL.so.1` e corpos no-op.
  `DT_NEEDED` final inclui `libEGL.so.1` — que **no device resolve para o blob Mali real**.
  O stub **não é publicado** (§7): o pacote é auditado para não conter nenhuma `libEGL*`.

Trava de segurança no stub: um `__attribute__((constructor))` grita em `stderr` se ele for
carregado, e `eglGetProcAddress` devolve `NULL` (falha honesta, sem falsos positivos). No teste
sob QEMU dessa evidência esse aviso **não** apareceu — prova de que o stub não está no caminho
de runtime nem por acidente.

---

## 4. Artefatos entregues (auditados)

| Artefato | Bytes | md5 | Papel |
| :--- | ---: | :--- | :--- |
| `gles_device_probe_aarch64` | 29.912 | `e141cc2a3164b476320d1c5c12b5eb83` | sonda EGL/GLES/GBM + extensões + limites + readback |
| `gles_smoke_aarch64` | 186.856 | `dae329b148fce3a1bdaf5d1cb01ecb34` | backend `plume_gles` sobre o driver real |
| `libEGL.so.1` (stub, **não publicado**) | 8.696 | `bbdb2c644aa97a2d05cb435ac40b3698` | só link-time |
| `run_gles_probe.sh` | 3.795 | `f70306ceaa6e48e6dda5d60abdff2d94` | runner no device |
| `README.txt` | 3.385 | `eb51eff800c93aab7f920fb196e0f13a` | instruções do pacote |
| `gles_device_probe_pkg.tar.gz` | 70.274 | `f547a0c3e41fb940de318c42346133bf` | pacote pronto para o SD |

Trecho da auditoria RAW:

```
--- gles_device_probe_aarch64 ---
ELF 64-bit LSB pie executable, ARM aarch64, ... interpreter /lib/ld-linux-aarch64.so.1
    RPATH/RUNPATH: (vazio)
--- gles_smoke_aarch64 ---
ELF 64-bit LSB pie executable, ARM aarch64, ...
    DT_NEEDED: libEGL.so.1, libstdc++.so.6, libgcc_s.so.1, libc.so.6, ld-linux-aarch64.so.1
    RPATH/RUNPATH: (vazio)
```

:warning: **Atualização 2026-10-18 (§13) — os md5 desta tabela são da 1ª entrega (M2).** Depois de a
sonda ganhar a seção `[9]` (§12) e a seção `[9c]` (§13), a versão **corrente** é: sonda
`5bda42acb705bcc11df35e05dfd78c0f` (**61.328 B**), runner `3def8b96b3292106a5ea6ce4b4963933`,
README `86761024b863bfb2ea7f8cde3082f96d`, tarball `2f1bbd1c55b0870214d824f631ac36fa` (250.201 B,
agora com `shader_cases/`). O **smoke segue idêntico** (`dae329b1…`) e o **stub também**
(`bbdb2c64…`) — é o teste de regressão do build: só o binário da sonda mudou, porque só a **fonte
dele** mudou.

Nenhum caminho do PC vaza para dentro dos binários (RPATH vazio) — não há como o R36S puxar
biblioteca do host por acidente.

**Determinismo do build (medido, não presumido):** `m3_build_gles_probe.sh` foi reexecutado por
inteiro (stub + probe + smoke, `rc=0` nos três) e os **três md5 acima se reproduziram idênticos**
(`e141cc2a…`, `dae329b1…`, `bbdb2c64…`). É a mesma disciplina de reprodutibilidade aplicada ao
binário do port (que já tinha duas provas) — agora também para os artefatos de sonda.

---

## 5. O que a sonda cobre (seções, com aceite verificável)

| Seção | Verifica | Por que importa para o plano |
| :--- | :--- | :--- |
| [1]/[1b] | `dlopen("libEGL.so.1")` + 15 entry points do núcleo EGL | refuta a nota do M2; confirma R6 no *link*, não no runtime |
| [2] | display: `GBM(/dev/dri/card0)` → `eglGetDisplay(gbm_device)` → default | é a rota do SDL/KMSDRM; `eglGetPlatformDisplay*` **não** existe no blob |
| [3] | `eglInitialize` + config `PBUFFER+ES3+RGBA8888+depth24` + pbuffer + contexto ES3 + makeCurrent | o "existe contexto ES 3.2?" que decidia o M2 |
| [4] | `GL_VERSION`/`GL_RENDERER`/`GL_VENDOR`/`GL_SHADING_LANGUAGE_VERSION` + teste `>= 3.2` | prova documental do alvo |
| [5] | inventário de extensões + 15 extensões nomeadas (M3/M4/M5/R8/R9) | converte "risco" em lista PRESENTE/AUSENTE |
| [6] | 15 limites (`MAX_TEXTURE_IMAGE_UNITS`, `MAX_SHADER_STORAGE_BUFFER_BINDINGS`, `UNIFORM_BUFFER_OFFSET_ALIGNMENT`, `MAX_SAMPLES`, …) | **é o número de N** que o M3 precisa para a janela de texturas |
| [7] | `glClear` em FBO 0 + `glReadPixels` + `glGetError` | o clear chegou ao drawable (mesmo aceite do M2/s2) |
| [8] | `gbm_surface_create` + `eglCreateWindowSurface` + `eglSwapBuffers` | a rota **exata** do SDL/KMSDRM, testável fora do port |
| [9] | compila+**linka** 10 shaders sintéticos (janela de N, orçamento multiplicativo, índice literal vs variável) | mede, no compilador do blob, **qual estratégia do M3 é viável** (ver §12) |
| [9c] | compila+**linka** os pares VS+PS **reais** de `shader_cases/` (`--shader-dir`/`PROBE_SHADER_DIR`) | é o único teste que mede o **orçamento de samplers sobre o ESSL de produção**; expôs 2 defeitos do artefato (ver §13) |
| — | `--short` reduz a saída (para logs de ticket) | — |

O blob expõe tudo o que a seção [8] precisa (RAW):

```
  0000000000681a90 T gbm_create_device
  00000000006823b4 T gbm_surface_create
  000000000054aec4 T eglCreateWindowSurface
  000000000054c3bc T eglSwapBuffers
  000000000054a014 T eglQuerySurface
```

---

## 6. Execução sob QEMU (teto do fluxo) — e o que ela **não** prova

```
PROBE arch=aarch64/64 (64-bit pointers)
PROBE dlopen_libEGL=ok
PROBE libEGL_path=/lib/aarch64-linux-gnu/libEGL.so.1
PROBE egl_symbols_found=15/15
PROBE egl_symbols_missing=(nenhum)
PROBE check=[1] dlopen(libEGL.so.1)                                    ok
PROBE check=[1b] os 15 entry points do nucleo EGL resolvem             ok
PROBE gbm_create_device=ok
PROBE open_dri_card0=ok
PROBE gbm_device=FALHOU
PROBE display_path=eglGetDisplay(EGL_DEFAULT_DISPLAY)
PROBE display_handle=(nil)
PROBE check=[2] EGLDisplay obtido                                      FALHOU
PROBE result=FAIL (sem display EGL)
qemu_rc=1
```

**Prova:** o binário é aarch64 válido, o blob carrega, o núcleo EGL resolve inteiro, e o fluxo
chega até a criação de display.
**Não prova:** nada sobre a GPU. `gbm_device=FALHOU` e `display_handle=(nil)` são a ausência de
hardware Mali sob emulação — o mesmo que qualquer app GLES daria ali.

O smoke se comporta de forma coerente (falha no passo [1], **sem crash**):

```
[smoke]     eglGetDisplay/GetPlatformDisplay falhou
[smoke] [1] contexto EGL + GLES (pbuffer 256x256) corrente             FALHOU
[smoke] ===== sem contexto: 1 falha(s) =====
qemu_rc=1
```

---

## 7. Validação do runner **sem o device**

`run_gles_probe.sh` foi exercitado ponta-a-ponta substituindo os dois binários aarch64 por
stubs host que emitem saída de device (`/root/bhrecomp/m3_gles_probe/runner_test/`). Saída real
do runner (fim do `gles_probe_log.txt`):

```
checks: 1 | linhas FALHOU: 0
result:  PROBE result=PASS
PROBE gl_version=OpenGL ES 3.2 v1.r13p0
PROBE gl_renderer=Mali-G31
PROBE display_path=eglGetDisplay(gbm_device)
PROBE libEGL_path=/usr/lib/aarch64-linux-gnu/libEGL.so.1
PROBE gl_extensions_count=173
PROBE   GL_EXT_texture_format_BGRA8888              PRESENTE  # R8
PROBE   GL_EXT_texture_norm16                       AUSENTE  # R8
log completo em: gles_probe_log.txt
```

Isto valida: coleta de ambiente, execução das duas sondas, resumo automático, geração do
`gles_probe_log.txt` (2.646 bytes) e — o detalhe que importa — os **padrões de `grep` do resumo
casam com o formato real de saída do probe** (as linhas `PRESENTE/AUSENTE` e as `gl_*` foram
extraídas corretamente). `ldd` aponta para `gles_smoke_aarch64` porque o probe, por desenho,
**não** tem `DT_NEEDED libEGL.so.1`.

---

## 8. Pacote para o cartão SD (entregue)

`evidencias/gles_device_probe_pkg/` + `evidencias/gles_device_probe_pkg.tar.gz`:

```
gles_device_probe_pkg/
  gles_device_probe_aarch64
  gles_smoke_aarch64
  run_gles_probe.sh
  README.txt
```

Auditoria crítica automatizada (`m3_package_gles_probe.sh`, seção [3]):

```
ok  nenhuma lib de sistema no pacote (o device resolve libEGL.so.1 -> blob Mali)
```

### Como rodar no R36S (~1 minuto)

```sh
# 1) copiar a pasta (ou descompactar o tar.gz) no SD, ex.: /roms/ports/glesprobe/
# 2) sair do EmulationStation (o ES pode segurar o DRM master)
# 3) por SSH ou console:
cd /roms/ports/glesprobe
sh run_gles_probe.sh
# 4) anexar gles_probe_log.txt na evidência
```

Saída esperada no device (o que fecha o aceite deste passo):

* `PROBE result=PASS` **e** `gl_version=OpenGL ES 3.2 ...` → EGL/GLES 3.2 funcionam;
* `display_path=eglGetDisplay(gbm_device)` + seção `[8] ... ok` → a rota do SDL/KMSDRM funciona;
* `[smoke] ===== 0 falha(s) =====` → o backend `plume_gles` roda no driver real;
* as seções `extensions_need` e `limits` dão a lista/valores definitivos para o M3.

---

## 9. Limitações declaradas (honestidade do escopo)

1. **Nada foi executado no R36S nesta sessão.** Toda a prova de GPU é pendente (§8). O que se
   prova aqui é: o EGL existe, é completo, é ES 3.2, não é linkável, e as sondas que o
   exercitam estão prontas, auditadas e validadas sob emulação.
2. As extensões de §2.5 vêm de `strings` do blob, **não** de `glGetString(GL_EXTENSIONS)`. São
   indício forte — a confirmação é do device.
3. O teste GBM de §8 requer `/dev/dri/card0` acessível e, idealmente, o DRM master livre. Se
   `gbm_surface_create` falhar por isso, **não** é limitação do backend.
4. A seção [8] usa constantes do `gbm.h` escritas à mão (não há `gbm.h` no toolchain):
   `GBM_BO_USE_SCANOUT=1`, `GBM_BO_USE_RENDERING=4`, `GBM_FORMAT_XRGB8888=0x34325258`.
   Documentado no código; se o driver recusar, esse é o primeiro suspeito.
5. O stub é ferramenta de build. Se aparecer no device
   `*** AVISO: libEGL STUB DE LINK-TIME foi carregada. ***`, o problema é empacotamento /
   `LD_LIBRARY_PATH`, não o backend.

---

## 10. Reprodução

```bash
PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"

# 1) build aarch64 das sondas (stub + probe + smoke) + auditoria + sanity QEMU
bash "$PROJ/evidencias/tools/m3_build_gles_probe.sh"

# 2) RAW consolidado desta evidência (offline + QEMU + pacote)
bash "$PROJ/evidencias/tools/m3_gles_probe_raw.sh" \
  > /root/bhrecomp/m3_gles_probe/raw_offline.txt

# 3) monta o pacote do SD + auditoria anti-lib + tar.gz
bash "$PROJ/evidencias/tools/m3_package_gles_probe.sh"

# 4) (device) fecha o aceite
#    cd /roms/ports/glesprobe && sh run_gles_probe.sh
```

Ferramentas novas desta sessão:

| Arquivo | Papel |
| :--- | :--- |
| `evidencias/tools/gles_device_probe.cpp` | fonte da sonda (dlopen-only, seções [1]-[8]) |
| `evidencias/tools/gles_egl_stub.c` | stub de link-time `libEGL.so.1` (com trava de segurança) |
| `evidencias/tools/m3_build_gles_probe.sh` | build cross + auditoria + sanity QEMU |
| `evidencias/tools/m3_package_gles_probe.sh` | pacote SD + verificação anti-lib + tar.gz |
| `evidencias/tools/m3_run_gles_probe.sh` | runner do device |
| `evidencias/tools/m3_pkg_README.txt` | README do pacote |
| `evidencias/tools/m3_gles_probe_raw.sh` | consolidação RAW reproduzível |

---

## 11. Impacto no plano (o que muda a partir daqui)

| Item do plano | Antes | Agora |
| :--- | :--- | :--- |
| nota do M2 sobre o EGL do device | "não exporta `eglGetDisplay`/`eglGetProcAddress`" | **errada** — exporta o núcleo inteiro; corrigir o comentário em `gles_target_probe.cpp` |
| **R6** | "blob Mali pode não ser linkável" | **confirmado com causa**: sem SONAME + `.dynsym` malformado → regra passa a ser **dlopen sempre** |
| **R8** | "sem BGRA, sem 16-bit UNORM" | BGRA **presente**; 16-bit UNORM ausente → revisar o escopo do R8 no M3 |
| **R9** | "sem `GL_MIRROR_CLAMP_TO_EDGE`" | disponível `GL_EXT_texture_border_clamp` (alternativa ES correta) |
| **M4** | framebuffer fetch e MSAA = risco **alto** | `GL_ARM_shader_framebuffer_fetch` + `GL_EXT_multisampled_render_to_texture` **presentes** → risco cai |
| **M5 (medir FPS)** | sem base de medição | `GL_EXT_disjoint_timer_query` presente |
| **M3 (janela de N texturas)** | N a medir | §6 dará `GL_MAX_TEXTURE_IMAGE_UNITS`/`MAX_COMBINED_*` reais **assim que o device rodar a sonda** |
| passo 4 do plano ("M3: descriptors") | começar às cegas | começou por medição, como o plano exigia ("medir o número máximo de texturas distintas por draw antes de fixar N") |

**Aceite deste passo:** os 6 itens de §0 — **3 ✅** provados (offline/emulação) e **3 ⏳**
dependentes da execução única no device descrita em §8. O passo **não** é "concluído" enquanto
---

## 12. MEDIÇÃO DO M3 (seção [9] da sonda): **a forma de ESSL que o M1.3 gera não linka** (2026-10-18)

Esta seção foi adicionada depois de §1–§11 e é o resultado de estender a **mesma sonda** com uma
seção `[9]` de compilação real de shader. Ela não substitui nada acima: acrescenta a medição que o
Passo 4 do plano chamava de *"medir o número máximo de texturas distintas por draw antes de fixar
N"* — e que só podia ser feita **compilando**, não estimando.

### 12.1 O achado estrutural, medido no artefato gerado

O ESSL que o M1.3 gera para os raster PS (`build-aarch64/src/shaders/RasterPSSpecConstant.hlsl.glsl_es`,
produção, sem edição) contém:

```glsl
uniform highp sampler2D SPIRV_Cross_CombinedgTexturesgLinearClampMirrorSampler[8192];   // 16 combos
uniform highp sampler2D SPIRV_Cross_CombinedgTexturesgLinearClampWrapSampler[8192];     //  de gTextures
...                                                                                     //  x linear/nearest
uniform highp sampler2D SPIRV_Cross_CombinedgTexturesgNearestClampClampSampler[8192];   //  x 9 wraps
uniform highp sampler2D SPIRV_Cross_CombinedgTexturesSPIRV_Cross_DummySampler[8192];    // + TMEM/dummy
```

* **20 arrays de `sampler2D[8192]`** por shader (`grep -c 'Sampler\[8192\]'` = **20**, idêntico nos 4
  raster PS: `RasterPSSpecConstant`, `RasterPSDynamic`, `RasterPSSpecConstantMS`, `RasterPSDynamicMS`).
* Todos indexados por **variável, dentro do shader**:
  `textureGrad(SPIRV_Cross_CombinedgTexturesgLinearWrapWrapSampler[GPUTiles._m0[_707].textureIndex], ...)`
  — 20 call sites distintos (linhas 472–2326 do arquivo gerado), índice vindo de `GPUTiles[].textureIndex`,
  ou seja **não-uniforme, por fragmento**.
* A origem é `lib/rt64/src/shaders/FbRendererCommon.hlsli:43,46`:
  `Texture2D<float4> gTextures[8192] : register(t0, space1);` e `TMEMTexture gTMEM[8192] : register(t0, space2);`,
  consumidos com `NonUniformResourceIndex(gpuTile.textureIndex)` (`TextureSampler.hlsli:104,108,171,276`).
* Do lado CPU, o conjunto de descriptors é dimensionado pelo **cache inteiro** e re-bound **1x por
  frame**, não por draw: `rt64_framebuffer_renderer.cpp:313-315` (`descTextureSet` com
  `textureCacheSize`) e `:396-404` (`descTextureSet->setTexture(i, ...)` num laço sobre as versões do
  cache) — é o padrão "bindless", que o GLES não tem.

### 12.2 Por que o host não podia responder isso (e o M1.3 não provou)

O aceite do M1.3 foi "**57/57 ESSL**" via `glslangValidator`. Medido agora, o validador é
**permissivo** e responde `rc=0` para indexação dinâmica de sampler **mesmo sem extensão**:

```bash
# caso sintético (8 samplers, índice variável): rc=0 SEM nenhuma extensão
printf '#version 320 es\nprecision highp float;\nuniform sampler2D s[8];\nuniform int i;\nout vec4 c;\nvoid main(){ c = texture(s[i], vec2(0.5)); }\n' > d1.frag
glslangValidator -S frag d1.frag; echo "rc=$?"          # rc=0
# e o ESSL REAL do raster PS (20 arrays de [8192]) também passa sem uma única mensagem:
glslangValidator -S frag build-aarch64/src/shaders/RasterPSSpecConstant.hlsl.glsl_es; echo "rc=$?"   # rc=0
```

Ou seja: **`glslangValidator` rc=0 não é prova de legalidade em GLSL ES.** O M1.3 validou
*tradução*, nunca *link* — e o link é onde o problema aparece.

### 12.3 Dataset de referência: um driver ES 3.2 **conformante** (llvmpipe)

Comando (host, contexto ES 3.2 real; sem ele o Mesa desta máquina entrega no máximo ES 3.1/GLSL 3.10
e `#version 320 es` nem compila — foi o que aconteceu na primeira tentativa, com o backend D3D12/AMD):

```bash
g++ -std=c++17 -O2 -Wall -Wextra -o probe_host evidencias/tools/gles_device_probe.cpp -ldl   # 0 warnings
LIBGL_ALWAYS_SOFTWARE=1 EGL_PLATFORM=surfaceless ./probe_host --no-gbm
```

RAW: `evidencias/m3_gles_probe/raw_host_reference_llvmpipe.txt` (md5 `9f47cc9a36eecb6ce607d2154333dab8`).
Contexto: `OpenGL ES 3.2 Mesa 23.2.1`, `GLSL ES 3.20`, `GL_RENDERER=llvmpipe (LLVM 15.0.7)`,
`GL_MAX_TEXTURE_IMAGE_UNITS=32`, `GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS=192`.

| caso | shader | compile | link | leitura |
| :--- | :--- | :--- | :--- | :--- |
| `control` | ESSL 3.20 trivial | ok | ok | o compilador funciona (baseline do teste) |
| `win16` | 1 × `[16]`, índice uniforme | ok | **ok** | a janela desejada cabe |
| `win16_vary` | 1 × `[16]`, índice `flat in uint` | ok | **ok** | índice **não-uniforme** também cabe |
| `win16_gpu5` | `[16]` + `#extension GL_EXT_gpu_shader5` | ok | **ok** | a extensão é aceita |
| `arr16_2x` | 2 × `[16]` = **32** samplers | ok | **ok** | exatamente no limite |
| `arr16_3x` | 3 × `[16]` = **48** | ok | **FALHOU** | orçamento estourado |
| `win16_20x` | 20 × `[16]` = **320** | ok | **FALHOU** | a "janela × 20 arrays" morre |
| `arr8192` | **1 × `[8192]`, índice variável** | ok | **FALHOU** | **a forma do M1.3** |
| `arr8192_20x` | 20 × `[8192]` = **163.840** | ok | **FALHOU** | + `count of uniform locations > MAX_UNIFORM_LOCATIONS (163840 > 81920)` |
| `const_idx_8192` | 1 × `[8192]`, índice **literal 7** | ok | **ok** | **o tamanho sozinho não quebra: o que quebra é o índice variável** |

Log cru do driver nos casos que falham (todos iguais, e é a evidência mais útil):
`error: Too many fragment shader texture samplers`.

**Três fatos que este dataset estabelece:**

1. **O orçamento de samplers é multiplicativo**: `n_arrays × N ≤ GL_MAX_TEXTURE_IMAGE_UNITS`
   (2×16=32 passa; 3×16=48 e 1×8192 falham). Não basta reduzir o N **de um** array.
2. **A forma que o M1.3 gera não linka** nem isolada (`arr8192`), quanto mais na forma real
   (20 × 8192). O erro é do **link**, não da compilação — por isso o `-fsyntax-only`/`glslangValidator`
   do M1.3 nunca o veria.
3. **Índice constante linka** (`const_idx_8192`): a array grande **não** é o problema por si; o
   problema é o **índice resolvido em runtime**. Isso aponta a saída do M3 (ver 12.4).

### 12.4 Consequência: a estratégia do M3 muda de "janela de N" para **especializar + janela**

A leitura do plano era "janela de N texturas (N ≤ 16) + tabela de remap no CPU + rebind por draw".
Medido, a janela sozinha **não resolve**, porque:

* o fator ×20 (combos de sampler linear/nearest × 9 wraps) multiplica o orçamento antes do N entrar;
* o índice do shader vem de `GPUTiles[].textureIndex`, que é o índice no **cache global** — remapear
  no CPU não ajuda enquanto o shader indexar uma array de 8192.

Estratégia revista, na ordem em que os fatos a impõem:

1. **Especializar o raster PS por combo de sampler** (o *stream* de especialização do M1.3 já existe e
   já está linkado no binário): assim o shader gerado tem **1** array de sampler em vez de 20. É o
   passo que remove o ×20 — e `const_idx_8192` mostra que o compilador aceita o resto.
2. **Só então** aplicar a janela `N ≤ GL_MAX_TEXTURE_IMAGE_UNITS` (no Mali, número da seção `[6]` da
   sonda; no llvmpipe, 32), com remap no CPU e rebind por draw.
3. `gTMEM[8192]` entra **no mesmo orçamento** (é a segunda array do mesmo shader), não num separado.

### 12.5 O que a sonda leva a mais para o device (para o M3 fechar com um único run)

* Nova **seção `[9]`**: os 10 casos acima executados no **compilador do Mali** (é a autoridade).
  Ela mede, no hardware, se o Mali confirma ou diverge do llvmpipe — e cada caso tem `compile=` e
  `link=` + o log cru do driver em linhas `PROBE log_<caso>=`.
* **`GL_EXT_gpu_shader5`** entrou no inventário de extensões (o RAW offline só checava a variante
  **`NV`** — lacuna real, agora corrigida: ver 12.6).
* **`--no-gbm` / `PROBE_NO_GBM=1`**: força `EGL_DEFAULT_DISPLAY` (serve para diagnosticar o device com
  o DRM ocupado e para rodar a própria sonda no host). O runner agora **repete sozinho** com essa
  opção quando o caminho GBM não abre display (bloco `[1b]` no log).
* **`timeout 180`** em volta do probe: a seção `[9]` manda o Mali *linkar* shaders de 163.840
  samplers — se o driver travar ali, o run inteiro não é perdido (e o travamento vira evidência).

### 12.6 `GL_EXT_gpu_shader5`: presente nas strings do blob (offline)

```bash
strings -a "$BLOB" | grep -a GL_EXT_gpu_shader5     #  PRESENTE
strings -a "$BLOB" | grep -a GL_NV_gpu_shader5      #  NAO citado
```

Se o Mali expuser `GL_EXT_gpu_shader5` em runtime (a seção `[5]` confirma no device), a indexação
dinâmica de sampler passa a ser **legal** em GLSL ES — mas isso **não** mexe no orçamento de
samplers de 12.3: legalidade de indexar ≠ número de samplers disponíveis. As duas coisas são
independentes e o M3 precisa das duas.

### 12.7 Artefatos deste passo (auditados)

| Artefato | Tamanho | md5 | Observação |
| :--- | ---: | :--- | :--- |
| `gles_device_probe_aarch64` (novo) | 45.888 B | `a9d2903e1dffc81cdbb628612fd8def7` | +1.975 linhas→seção `[9]`; antes `e141cc2a…` (29.912 B) |
| `gles_smoke_aarch64` | 186.856 B | `dae329b148fce3a1bdaf5d1cb01ecb34` | **inalterado** (mesmo md5 de antes ⇒ smoke não foi tocado) |
| `libEGL.so.1` (stub de link) | 8.696 B | `bbdb2c644aa97a2d05cb435ac40b3698` | inalterado |
| `run_gles_probe.sh` | 6.125 B | `072ed01d6d90a505e75fc31de0ca30fd` | +`timeout`/fallback `[1b]`/resumo do M3 |
| `README.txt` (do pacote) | 5.779 B | `45054d31658b46899dec5d9b9411c47b` | +documentação da seção `[9]` |
| `raw_offline.txt` | 9.854 B | `115adc429e2a4caec79c7734d1f651fa` | RAW reproduzível (regenerado) |
| `raw_host_reference_llvmpipe.txt` | 10.772 B | `9f47cc9a36eecb6ce607d2154333dab8` | dataset de referência de 12.3 |
| `gles_device_probe_pkg.tar.gz` | 79.398 B | `26e61c3a75fe5c84e78115f90b7e0316` | pacote do SD **com** a seção `[9]` |

Auditorias mantidas: probe **sem** `libEGL`/`libGLES` em `DT_NEEDED` (só `libstdc++/libgcc_s/libc/ld`)
e **RPATH vazio**; pacote **sem nenhuma** `libEGL*`/`libGLES*`/`libgbm*` (trava do empacotador);
compilação host e cross com **0 warnings** (`-Wall -Wextra`; o `-Wall` pegou um bug real no caminho:
`std::string` passado a `%s`). QEMU contra a rootfs do device: comportamento **idêntico** ao anterior
(falha graciosa em `[2] EGLDisplay`, sem GPU) ⇒ sem regressão.

### 12.8 Reprodução

```bash
PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"

# 0) o achado estrutural (20 arrays de [8192] + índice dinâmico no ESSL de produção)
grep -c 'Sampler\[8192\]' /root/bhrecomp/build-aarch64/src/shaders/RasterPSSpecConstant.hlsl.glsl_es   # 20
grep -n  'CombinedgTextures.*\[GPUTiles'  /root/bhrecomp/build-aarch64/src/shaders/RasterPSSpecConstant.hlsl.glsl_es | head

# 1) o validador do M1.3 é permissivo (aqui o motivo de o aceite anterior não valer)
printf '#version 320 es\nprecision highp float;\nuniform sampler2D s[8];\nuniform int i;\nout vec4 c;\nvoid main(){ c = texture(s[i], vec2(0.5)); }\n' > /tmp/d1.frag
glslangValidator -S frag /tmp/d1.frag; echo "rc=$?"                                                   # rc=0

# 2) dataset de referência (driver ES 3.2 conformante, llvmpipe)
g++ -std=c++17 -O2 -Wall -Wextra -o /tmp/probe_host "$PROJ/evidencias/tools/gles_device_probe.cpp" -ldl
LIBGL_ALWAYS_SOFTWARE=1 EGL_PLATFORM=surfaceless /tmp/probe_host --no-gbm | grep -E 'compile=|COMPILA'

# 3) rebuild aarch64 do probe + auditoria (aqui o smoke NAO muda: md5 confere)
cd /root/bhrecomp/m3_gles_probe && aarch64-linux-gnu-g++ -std=c++17 -O2 -Wall -Wextra \
    -o gles_device_probe_aarch64 "$PROJ/evidencias/tools/gles_device_probe.cpp" -ldl
readelf -d gles_device_probe_aarch64 | grep -iE 'NEEDED|libEGL|libGLES'                               # sem EGL/GLES
timeout 25 qemu-aarch64-static -L /opt/r36s/rootfs ./gles_device_probe_aarch64 --short                # falha em [2]

# 4) RAW consolidado + reempacotamento
bash "$PROJ/evidencias/tools/m3_gles_probe_raw.sh" > /root/bhrecomp/m3_gles_probe/raw_offline.txt
bash "$PROJ/evidencias/tools/m3_package_gles_probe.sh"

# 5) NO DEVICE -- agora fecha o M2 *e* mede o M3 num único run (~1 min)
#    cd /roms/ports/glesprobe && sh run_gles_probe.sh   # gera gles_probe_log.txt
```

### 12.9 Limitações declaradas

* O dataset de 12.3 é do **llvmpipe**, não do Mali. Ele estabelece a **regra** (orçamento
  multiplicativo, índice variável vs constante) e o **erro do link**; a confirmação no Mali é a
  seção `[9]` no device. Nada nesta seção afirma comportamento do Mali.
* A seção `[9]` mede **compilar + linkar**. Ela **não** prova que o draw funciona (isso é o gate do
  M4) — um shader pode linkar e ainda assim falhar ao amostrar texturas não bindadas.
* `const_idx_8192` linkar **não** significa que 8192 samplers sejam utilizáveis: significa que, com
  índice constante, o compilador só conta **1** sampler. É o que a faz uma pista para a solução, não
  uma alternativa viável.
* O número **N** definitivo depende de `GL_MAX_TEXTURE_IMAGE_UNITS` do Mali (seção `[6]`), que só o
  device dá.

### 12.10 Estado do aceite depois desta seção

Continua **3 ✅ / 3 ⏳** como em §0: nada aqui foi executado no R36S. O que mudou é **quanto** o run
pendente fecha: antes ele respondia o M2 e dava os números do M3; agora ele responde também **qual
estratégia do M3 é viável** (seção `[9]`), o que evita escrever a janela de N sobre uma premissa
que o driver rejeita.
## 13. SEÇÃO `[9c]`: o ESSL **DE PRODUÇÃO** no driver (2026-10-18)

A §12 mediu **formas sintéticas**. Esta seção mede o **artefato real**: a sonda passou a compilar e
**LINKAR** pares VS+PS de verdade (`--shader-dir DIR` / `PROBE_SHADER_DIR`), gerados a partir do ESSL
que o M1.3 produz (`evidencias/m1_3_stage2/essl/RasterPSDynamic.essl` +
`RasterVSDynamic.essl`). O motivo de ser um **par**: o erro de orçamento de samplers só aparece no
**LINK** — compilar cada arquivo isolado não o vê (foi exatamente o furo do aceite "57/57 ESSL").

RAW novo (superset do anterior, seção `[9]` **sem regressão** — 0 linhas de diferença nas 10 linhas
`compile=`):

```
evidencias/m3_gles_probe/raw_host_prod_essl_linktest.txt   md5 43101ad16e73b795635fa121bff8440a
```

**Antes de qualquer medição de sampler, o `[9c]` expos DOIS DEFEITOS do artefato gerado** que todo o
aceite anterior (glslangValidator por arquivo, compilação isolada) deixava passar:

### 13.1 Defeito 1 — o ESSL gerado usa dual-source **sem habilitar a extensão**

6 dos 12 ESSL gerados escrevem **dois alvos** (`SV_TARGET0` + `SV_TARGET1`, para emular o blender do
RDP) e o codegen emite o qualificador `index = 1` **sem** o `#extension` correspondente. Medido em
driver ES 3.2 conformante (llvmpipe):

```
0:166(30): error: index layout qualifier requires EXT_blend_func_extended
```

* O `llvmpipe` **tem** `GL_EXT_blend_func_extended` (presente na lista de extensões do RAW) — logo não
  é limitação do driver: era **omissão do artefato**.
* Corrigido no sanitizador de produção (`evidencias/tools/m1_1_emit_glsl_es.py::sanitize()`, ação nova
  `blend-func-extended-required`): quando o texto usa `index = 1`, emite
  `#extension GL_EXT_blend_func_extended : require`. Regenerar os 57 blobs ESSL e revalidar é o passo
  de fecho deste item (a alteração é do sanitizador, não do código de shader).
* **O `glslangValidator` não detecta isso** — mesma permissividade que escondeu o orçamento de
  samplers da §12. Reforça a regra: a autoridade é o **driver**, e agora o driver é o **link do par**.

### 13.2 Defeito 2 — o par VS/PS não linka por qualificador de interpolação

Com o defeito 1 resolvido, o link do par real acusou:

```
error: vertex shader output `out_var_COLOR1' specifies no interpolation qualifier,
       but fragment shader input specifies flat interpolation qualifier
```

O PS declara `layout(location = 2) flat in highp vec4 in_var_COLOR1;` e o VS declara o `out` da mesma
location **sem** `flat`. Nenhum aceite anterior linkava par nenhum — por isso passou. Protótipo da
correção na ferramenta de casos (`--flat-from-ps`, ação `flat_outputs_matched=1`): o VS recebe
`layout(location = 2) flat out vec4 out_var_COLOR1;` (1 linha alterada). A correção de produção é a
mesma classe: o gerador tem de emitir o qualificador **coerente entre os estágios**.

### 13.3 O ORÇAMENTO EXATO, medido no artefato real (llvmpipe, 32 unidades)

Com os dois defeitos neutralizados no protótipo (e o **corpo do shader provado inalterado**:
normalização de `evidencias/m3_gles_probe/shader_cases/` dá **0 divergências** vs o `as-is`), o link
do par real mediu:

| caso | arrays com janela | samplers contados | link | log do driver |
| :--- | :--- | :--- | :--- | :--- |
| `prod_asis` (forma do M1.3) | 20 × `[8192]` | 163.840 + 1 | **FALHOU** | `Too many fragment shader texture samplers` + `count of uniform locations > MAX_UNIFORM_LOCATIONS(163849 > 81920)` |
| `prod_spec1x_n8192` | 2 × `[8192]` | 16.384 + 1 | **FALHOU** | `Too many fragment shader texture samplers` |
| `prod_spec1x_n32` | 2 × `[32]` | 64 + 1 | **FALHOU** | idem |
| `prod_spec1x_n16` | 2 × `[16]` | **33** | **FALHOU** | idem |
| `prod_spec1x_n15` | 2 × `[15]` | **31** | **ok** | — |
| `prod_spec1x_n8` | 2 × `[8]` | 17 | **ok** | — |
| `prod_spec1x_n4` | 2 × `[4]` | 9 | **ok** | — |

**O limite medido é exatamente N=15** (31 ✓ / 33 ✗) e a conta **não** é `2 × N`: o shader real tem,
além das 2 arrays com janela, **1 sampler escalar** (`gBackgroundDepth`). Logo a regra do M3 é:

```
n_arrays_com_janela × N  +  n_samplers_escalares  <=  GL_MAX_TEXTURE_IMAGE_UNITS
```

Isto **corrige** a leitura otimista do achado do M3.1: colapsar os 18 combos de `gTextures` em 1
array por imagem (o que a especialização por combo faz) **não** libera o orçamento inteiro — sobram
**duas** arrays com janela (`gTextures` + `gTMEM`) mais o escalar. E é por isso que `n16` falha
mesmo estando "no limite": a conta real era 33 > 32.

### 13.4 `GL_EXT_blend_func_extended`: o llvmpipe TEM, as strings do blob NÃO citam

| fonte | `GL_EXT_blend_func_extended` | como foi medido |
| :--- | :--- | :--- |
| llvmpipe (ES 3.2 conformante) | **PRESENTE** | `glGetStringi(GL_EXTENSIONS)` no RAW da §13 |
| blob Mali-G31 (`libmali-bifrost-g31-rxp0-gbm.so`) | **AUSENTE** (string não citada) | `strings -a` (RAW offline, seção `[4]`) |

* A ausência da string é **indício forte, não prova** (nomes podem ser montados em runtime): a
  resposta autoritativa é `glGetStringi` **no device**. Por isso a extensão entrou no inventário
  dirigido da sonda (`GL_EXT_blend_func_extended  "M3/M4 DECISIVO: o raster PS escreve 2 alvos"`) e
  na checagem positiva do RAW offline (`m3_gles_probe_raw.sh`).
* **Consequência declarada, não resolvida aqui:** se o Mali não tiver essa extensão, os raster PS do
  port **não compilam** na forma atual (dual-source) e o **caminho de blender do RDP muda** — é
  decisão de arquitetura, não ajuste de shader. É pergunta do **M4**, descoberta por medição do **M3**,
  e está registrada no plano como risco novo.
* O `[9c]` responde as duas coisas no mesmo run: se os `prod_*` derem `compile=ok` no Mali, a
  extensão existe (ou o blob é leniente); se derem `compile=FALHOU` com `extension not supported`,
  ela não existe.

### 13.5 Artefatos desta seção (auditados)

| artefato | md5 |
| :--- | :--- |
| `evidencias/m3_gles_probe/raw_host_prod_essl_linktest.txt` (RAW novo, 210 linhas) | `43101ad16e73b795635fa121bff8440a` |
| `evidencias/m3_gles_probe/raw_offline.txt` (regenerado: +`blend_func_extended`, +auditoria do pacote) | `7d22d7d0b1f0eb8d7687c696ce30f47f` |
| `evidencias/tools/gles_device_probe.cpp` (sonda: seção `[9c]` + inventário) | — (binário abaixo) |
| `evidencias/tools/m3_essl_specialize.py` (**novo**: protótipo da especialização/janela) | — |
| `evidencias/tools/m3_make_shader_cases.sh` (**novo**: gera os 7 pares de casos) | — |
| `evidencias/tools/m1_1_emit_glsl_es.py` (sanitizador: defeito 1 corrigido) | — |
| `evidencias/tools/m3_run_gles_probe.sh` (runner: `PROBE_SHADER_DIR` + resumo `[9c]`) | `3def8b96b3292106a5ea6ce4b4963933` (no pacote) |
| `evidencias/tools/m3_pkg_README.txt` (documenta `[9c]` e a regra do N) | `86761024b863bfb2ea7f8cde3082f96d` (no pacote) |
| `evidencias/gles_device_probe_pkg/gles_device_probe_aarch64` (sonda) | `5bda42acb705bcc11df35e05dfd78c0f` (61.328 B) |
| `gles_smoke_aarch64` (**inalterado** — regress 0) | `dae329b148fce3a1bdaf5d1cb01ecb34` |
| `gles_device_probe_pkg.tar.gz` (250.201 B; 14 `.essl` + 2 binários + runner + README) | `2f1bbd1c55b0870214d824f631ac36fa` |

Casos de shader (idênticos no pacote e em `evidencias/m3_gles_probe/shader_cases/`): `prod_asis` PS
`27b95d9ec5105e515e3a483fcaaace2a`, `n8192` `e5ba21908fdfdd117be8debba388620e`, `n32`
`b8d47df829fb49c4fe99aeaf84453c33`, `n16` `d9dae8036b3f8fa91560cdee8c33e871`, `n15`
`ed58b599b0b570a98b9a9529b20157c0`, `n8` `2185e638220f597888df08e68bc8bdef`, `n4`
`c36ecfae17da27becf761b9a6866aecc`; VS parceiro (o mesmo para todos)
`fc5b71b8870eb320798840c5bed1b0a2`.

**Determinismo verificado (2 execuções):** comparando um run novo com o RAW arquivado, as **17 linhas
de veredicto** (7 `prod_*` + 10 sintéticas) são **idênticas** (0 linhas de diff), assim como a tabela
`m3_shader_measurement`. O que varia entre execuções é apenas: o endereço em `display_handle=` e as
**linhas `warning: 'used uninitialized'` do Mesa** (aparecem/somem conforme o caso; não afetam
veredicto). Reprodução determinística, portanto:

```bash
grep -E '^PROBE   prod_.*compile=' raws/novo.txt > /tmp/a ; grep -E '^PROBE   prod_.*compile=' raws/arquivado.txt > /tmp/b
diff /tmp/a /tmp/b      # 0 = veredictos estáveis
```

### 13.6 Reprodução

```bash
PROJ="/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)"

# 1) gera o ESSL real (as-is + variantes) e prova que so' nome de sampler/janela/flat mudaram
bash "$PROJ/evidencias/tools/m3_make_shader_cases.sh"

# 2) mede no driver ES 3.2 conformante (build x86_64 nativo da PROPRIA sonda: ela e' dlopen-only)
g++ -std=c++17 -O2 -Wall -Wextra -o /tmp/probe_host_x86_64 "$PROJ/evidencias/tools/gles_device_probe.cpp" -ldl
LIBGL_ALWAYS_SOFTWARE=1 EGL_PLATFORM=surfaceless \
  PROBE_SHADER_DIR="$PROJ/evidencias/m3_gles_probe/shader_cases" \
  /tmp/probe_host_x86_64 --no-gbm > /tmp/raw_host_prod_essl_linktest.txt
grep -E 'prod_.*compile=|Too many fragment' /tmp/raw_host_prod_essl_linktest.txt

# 3) regress da secao [9] sintetica (0 linhas = as 10 medisoes anteriores nao mudaram)
grep -E '^PROBE   [a-z0-9_]+ +compile=' "$PROJ/evidencias/m3_gles_probe/raw_host_reference_llvmpipe.txt" | grep -v prod_ > /tmp/a
grep -E '^PROBE   [a-z0-9_]+ +compile=' /tmp/raw_host_prod_essl_linktest.txt | grep -v prod_ > /tmp/b
diff /tmp/a /tmp/b

# 4) a extensao no blob (offline) -- e o run no device da' a resposta autoritativa
bash "$PROJ/evidencias/tools/m3_gles_probe_raw.sh" > "$PROJ/evidencias/m3_gles_probe/raw_offline.txt"

# 5) rebuild aarch64 + empacotamento (o pacote passa a levar shader_cases/)
bash "$PROJ/evidencias/tools/m3_build_gles_probe.sh"
bash "$PROJ/evidencias/tools/m3_package_gles_probe.sh"

# 6) NO DEVICE (~1 min) -- fecha o M2 E mede o ESSL de producao no compilador do MALI
#    cd /roms/ports/glesprobe && sh run_gles_probe.sh   # anexar gles_probe_log.txt
```

### 13.7 Limitações declaradas

* Tudo aqui é **llvmpipe**, não Mali. O que se estabelece é a **regra** e o **defeito do artefato**;
  o Mali responde pelo `[9]`/`[9c]` no device (e a divergência dele é evidência do M3).
* O caso `prod_spec1x_*` é transformação de **forma**, não de semântica: **não** faz o remap de
  `textureIndex` para dentro da janela N (trabalho de CPU do M3) nem preserva o sampler por tile.
  Ele mede **compilar + linkar**; render é o gate do M4.
* A prova mecânica (0 divergências) garante que a transformação só tocou **nomes de sampler, tamanho
  da janela, o `#extension` e o `flat` do VS** — nunca a expressão de índice nem o corpo.
* A ausência da string da extensão no blob **não** é prova de ausência da extensão (ver 13.4).
* O *link* é a autoridade para o **orçamento de samplers**; ele não substitui o gate visual do M4.

### 13.8 Estado do aceite depois desta seção

Continua **3 ✅ / 3 ⏳**: nada disto rodou no R36S. O que mudou é **o que o run pendente fecha** — e
não só em quantidade:

1. o M2 em hardware (como antes);
2. os números reais do M3 (`GL_MAX_TEXTURE_IMAGE_UNITS` do Mali → o **N**) pela seção `[9]`;
3. **a viabilidade da estratégia do M3 no compilador do Mali** (`[9]`), agora com a regra corrigida
   (`n_arrays × N + escalares ≤ unidades`);
4. **se o ESSL de produção compila e linka no Mali** (`[9c]`, 7 pares reais);
5. **se o Mali tem `GL_EXT_blend_func_extended`** — a pergunta nova, que decide o caminho do blender
   do RDP no M4.

> Nota de honestidade sobre o escopo: nada do §13 altera o veredito do M2; ele **enriquece** a
> medição pendente e **reprova** dois pontos do aceite do M1.1/M1.3 (defeitos 1 e 2 de §13), que
> passavam por serem validações de arquivo único e não de **par**. A correção de produção do defeito
> 1 já foi aplicada no sanitizador; a do defeito 2 é a mesma classe (coerência entre estágios) e
> está registrada como ação no plano.