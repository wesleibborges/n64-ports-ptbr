# Evidência — M5-GLES: seleção de API OpenGL ES 3.2 (config + launcher)

Data: 2026-10-18 · Máquina: WSL2 (`DESKTOP-K746DMK`), fonte em `/root/bhrecomp`
Toolchain: `/usr/bin/aarch64-linux-gnu-g++` (`-O3 -DNDEBUG`, C++20) · Alvo: R36S / RK3326 / Mali-G31
Cache: `RT64_GLES_BACKEND:BOOL=ON` + `RT64_GLSL_ES_SHADERS:BOOL=ON` em `build-aarch64`

---

## 1. Descoberta que redefiniu o escopo do M5 (correção do M2)

O M2 registrou como pré-condição de execução: *"(b) `graphicsAPI: "GLES"` no `rt64.json`"*.
**Essa via não existe neste port.** A cadeia real, lida no código:

```
graphics.json["api_option"]  ("Auto" | "D3D12" | "Vulkan" | "Metal")
  -> recomp::config::ConfigOptionEnum        (librecomp/config.hpp: guarda a CHAVE textual
                                              + o valor uint32 = static_cast<uint32_t>(enum))
  -> ultramodern::renderer::GraphicsApi      (ultramodern/config.hpp)
  -> switch em recompui/src/renderer/rt64_render_context.cpp:287  ("Pick an API if the user
     has set an override")
  -> app->userConfig.graphicsAPI             (RT64::UserConfiguration::GraphicsAPI)
  -> RT64::Application::setup() -> chosenGraphicsAPI
```

Provas de que o `rt64.json` está fora do caminho:

| Evidência | Local |
| :--- | :--- |
| `appConfig.useConfigurationFile = false;` (não lê arquivo de config do RT64) | `recompui/src/renderer/rt64_render_context.cpp:271` |
| A API é atribuída pelo `switch (cur_config.api_option)` | `recompui/src/renderer/rt64_render_context.cpp:287-300` |
| Config do recompui vive em `<app_folder>/graphics.json` | `librecomp/src/config.cpp:52` (`get_path_to_config`), `:65` (`id + ".json"`) |
| `get_app_folder_path()` = `$HOME/.config/<program_id>` no Linux | `recompui/src/util/file.cpp:104-110` |
| `program_id` deste port = `bhrecomp` | `include/bh_config.h:8` + `src/main/main.cpp:411` |

⇒ No device o arquivo é **`$HOME/.config/bhrecomp/graphics.json`** (não a pasta do port; a cópia
em `$port_dir` só vale com `portable.txt`/`APP_FOLDER_PATH`, que o launcher não usa).
Isso **resolve o R11** sem heurística: as duas pontas passam a ser escritas pelo launcher a
partir de um único botão.

## 2. Edits de código (7 substituições, 4 arquivos)

Ferramenta: `evidencias/tools/m5_gles_api_select_apply.py` (`check` / `apply` / `revert`,
backup + md5, sonda de idempotência por edit — 5 dos 7 edits têm o texto antigo como substring
do novo, logo `old not in text` não serve como teste de estado).
Work dir: `/root/bhrecomp/m5_gles_api_select_20261018/` (backups + `manifest.json`).

| # | Arquivo | Tag | md5 antes → depois |
| :- | :--- | :--- | :--- |
| 1 | `ultramodern/include/ultramodern/config.hpp` | `config_hpp_enum` | `5d273263800e58b0bae191ee304148c5` → `653b8d8e35ca1b5a2d18016cd05d1bf7` |
| 2 | `ultramodern/include/ultramodern/config.hpp` | `config_hpp_json` | `653b8d8e…` → `66198d83b43438cde11c0becffac1fd3` |
| 3 | `ultramodern/src/renderer_context.cpp` | `renderer_context_name` | `438de9062e5a6350c75e580fe09c45b2` → `f56cbe42c04251ffeda392dca511972d` |
| 4 | `recompui/src/config/ui_config_tab_graphics.cpp` | `ui_graphics_allow_gles` | `f1013b5057d189715db91e03d642c748` → `64f88c8c270f3537df60679a86e3ce5a` |
| 5 | `recompui/src/config/ui_config_tab_graphics.cpp` | `ui_graphics_option_entry` | `64f88c8c…` → `bd2f51537b3d065c3425f434ee6da003` |
| 6 | `recompui/src/renderer/rt64_render_context.cpp` | `rt64_rc_switch` | `ab9d431b204f24dc3a0c36e3ee4f56ae` → `f6995d51e4e20fecc8180eb317f50560` |
| 7 | `recompui/src/renderer/rt64_render_context.cpp` | `rt64_rc_map` | `f6995d51…` → `92c5c28d3d61c72877bddcd74009ca58` |

Decisões registradas (com o porquê, não só o quê):

1. **`GLES` entra no enum DEPOIS de `Metal`** (valor 4; `OptionCount` 4→5). O valor numérico
   circula como `uint32` (`ConfigOptionEnumOption::value` = `static_cast<uint32_t>(enum)`,
   `find_option_from_value`), então renumerar `Vulkan`/`Metal` quebraria configs já salvas.
2. **Bloco `NLOHMANN_JSON_SERIALIZE_ENUM` duplicado sob `#ifdef`/`#else`**: diretiva de
   pré-processador dentro da lista de argumentos de macro é comportamento indefinido
   ([cpp] *"would otherwise act as preprocessing directives"*), logo não dá para colocar o
   `#ifdef` só na linha do `GLES`.
3. **`map_graphics_api` também recebeu o case.** Sem ele, com GLES funcionando o port
   imprimiria `Unhandled 'RT64::UserConfiguration::GraphicsAPI' ?` e abortaria no
   `assert(false)` — ou seja: o backend funcionaria e o port morreria, o pior modo de falha.
4. **Nome da API** (`get_graphics_api_name`) ganhou `"GLES"`. Nenhum callback substitui
   `render_callbacks.get_graphics_api_name` neste port (verificado), então o default do
   ultramodern é o que aparece nas mensagens de `events.cpp:605/608`; sem o case o usuário
   leria `[Unknown graphics API]` justamente na primeira execução no device.
5. **`ALLOW_GLES` só em Linux + gate ON** — espelha o padrão existente
   (`ALLOW_D3D12`/`ALLOW_VULKAN`/`ALLOW_METAL`) e mantém a opção fora do seletor quando o
   backend não está no binário.

Validação da ferramenta:

- `check` antes: `7/7 PENDENTE`, cada alvo casando **exatamente 1×** (a ferramenta aborta se ≠1).
- `apply`: `alterados=7 ja_aplicados=0 total=7`, pós-condição (sonda) verificada em cada edit.
- `check` depois: `7/7 APLICADO`. `apply` de novo: `alterados=0 ja_aplicados=7` (**idempotente**).

## 3. Gate OFF — verificação cirúrgica por translation unit

O M2 provou o invariante no **binário inteiro** (gate OFF ⇒ 0 símbolo/string GLES). Todo o código
do M5 está dentro de `#ifdef RT64_GLES_BACKEND` em 3 TUs (+ 1 header incluído por uma delas), então
a prova equivalente (e barata) é recompilar **exatamente** esses TUs sem o define.
Ferramenta: `evidencias/tools/m5_gate_off_tu_check.sh` — extrai a linha de compilação do próprio
`build.ninja`, remove `-DRT64_GLES_BACKEND` e desvia `-o`/`-MF` para um tmp (não suja o build).

```
--- ultramodern_renderer_context ---
  ultramodern_renderer_context.o  strings-GLES=0 simbolos-GLES=0  (esperado 0/0)
--- recompui_ui_graphics ---
  recompui_ui_graphics.o  strings-GLES=0 simbolos-GLES=0  (esperado 0/0)
--- recompui_rt64_rc ---
  recompui_rt64_rc.o  strings-GLES=0 simbolos-GLES=0  (esperado 0/0)
RESUMO GATE-OFF (TU): falhas=0
```

RAW: `/root/bhrecomp/m5_gles_api_select_20261018/gate_off_tu.log`.

## 4. Build gate ON (aarch64) — verde

RAW: `/root/bhrecomp/m5_gles_api_select_20261018/ninja_bg.log` (`EXIT=0`, **0** ocorrências de
`error:` / `FAILED`).

| Medida | Valor |
| :--- | :--- |
| Binário | `build-aarch64/BodyHarvestRecompiled` — **22.988.496 B** |
| md5 | `fa3e4b59011263de4547191c1c811fe1` |
| Formato | ELF 64-bit LSB pie, ARM aarch64, not stripped, BuildID `6ea8276de0fae867070e780e1b54ba37927b6977` |
| Símbolos GLES (`nm -C --defined-only \| grep -ci gles`) | **311** |
| Strings com `GLES` (`strings -a \| grep -c`) | **389** |
| `CreateGLESInterface` | `plume::CreateGLESInterface(void*, void* (*)(char const*), plume::GLESSwapChainFunctions)` ✅ |
| Calibração `VulkanDevice` (`nm -C \| grep -c`) | **106** |

Comparação com o artefato do M2 (mesmo cache, antes dos edits de config):
`22.971.520 B` / `a895ada8f061127cf72264ee6c6f7864` ⇒ **+16.976 B**, o custo das 4 pontas novas
(enum, json, nome da API, seleção por config).

Reprovas de determinismo (duas, independentes):

1. um `ninja` completo posterior (**243 alvos**, disparado pela regeneração dos shaders via
   `file_to_c`) reproduziu o **mesmo md5** `fa3e4b59…`;
2. após o ciclo `revert` → `apply` da ferramenta de edits (4 arquivos reescritos, mtime novo), um
   rebuild de **55 alvos** (`ninja_settle.log`, `EXIT=0`) voltou a produzir `fa3e4b59…` — isto é, o
   binário publicado não depende da ordem/histórico do build nem do caminho de aplicação dos patches.

Amostra de strings do *path* novo (a "falha nomeada" do M2 continua lá):

```
GLES
GLES: falha ao criar contexto OpenGL ES 3.2: %s
GLES: janela SDL ausente -- nao ha onde criar o contexto.
GLES: falha ao tornar o contexto corrente: %s
GLESCommandList::drawInstanced (caminho de raster = M4)
```

## 5. Launcher (`BodyHarvest.sh`) — um único botão

Bloco *backend gráfico (M5)* inserido antes do `exec`. `BH_GLES=1` liga GLES escrevendo as
**duas** pontas coerentes:

- `export BH_GRAPHICS_API=gles` (flag da janela SDL, decidida em `src/main/main.cpp` **antes** de
  qualquer config — M2);
- `graphics.json` ← `graphics.json.gles` (`api_option: "GLES"`), gravado em
  `$HOME/.config/bhrecomp/` **e** em `$port_dir/`; a linha de log mostra o valor **lido de volta**
  do arquivo ⇒ evidência auto-verificável dentro do `log.txt` do device.

Sem `BH_GLES=1`: se qualquer um dos arquivos tiver `"GLES"` (execução anterior), o launcher
**reverte** para `graphics.json.auto` — senão o boot seguinte nasceria com janela Vulkan +
`api_option=GLES` (falha garantida). `BH_GRAPHICS_API` setado sem `BH_GLES=1` é **avisado e
ignorado**.

Arquivos novos no port: `graphics.json.auto` (template Auto) e `graphics.json.gles` (template
GLES — idêntico ao Auto exceto `api_option`, para que a única variável sob teste seja a API).

Smoketest offline (`evidencias/tools/m5_launcher_smoketest.sh`; sandbox com `HOME`/`port_dir`
temporários e binário stub): **13 verificações, 0 falhas** —

| Cenário | Resultado |
| :--- | :--- |
| A) sem `BH_GLES` | `vulkan/auto`; `api_option=Auto`; config do `HOME` **não** criado |
| B) `BH_GLES=1` | `OpenGL ES 3.2` / `BH_GRAPHICS_API=gles`; `api_option=GLES` nas **duas** cópias; log lê de volta |
| C) `BH_GLES=1` → execução normal | `revertendo api_option=GLES`; volta a `Auto` nas duas cópias |
| D) `BH_GRAPHICS_API=gles` sem `BH_GLES=1` | aviso `sem BH_GLES=1 -- ignorado`; `api_option=Auto` |
| E) sintaxe | `bash -n BodyHarvest.sh` OK |

> Armadilha registrada (custo de 2 iterações): `run() { ( ... "$@" env ... ) }` **não** funciona —
> um assignment vindo de expansão não é reconhecido como assignment pelo bash (vira argumento de
> `bash`), logo o script nunca executava. O smoketest usa parâmetros nomeados.

## 6. Como testar no R36S (primeira execução real)

```sh
# no device, na pasta do port:
BH_GLES=1 ./BodyHarvest.sh
# leitura do log:
grep -E 'backend grafico|api_option|GLES' log.txt
```

Esperado nesta etapa — **sem imagem na tela, por desenho**: janela SDL criada com
`SDL_WINDOW_OPENGL` → contexto ES 3.2 criado (`GLES: falha ao criar contexto` NÃO deve aparecer)
→ `GLESInterface`/`GLESDevice`/swapchain inicializados → e o **abort nomeado no draw**
(`GLESCommandList::drawInstanced (caminho de raster = M4)`), porque o raster é justamente o M4.

Se aparecer `GLES: falha ao criar contexto OpenGL ES 3.2: <err>`, o problema é EGL/KMSDRM
(blob Mali × SDL dinâmico) — e não a seleção de API, que é o que este passo testa.

## 7. Riscos

- **R11 — FECHADO.** Não há mais heurística de decisão: o launcher escreve as duas pontas a partir
  de um botão. Residual (decisão consciente): rodar o binário direto com `api_option=GLES` e sem
  `BH_GRAPHICS_API` continua produzindo falha explícita e nomeada.
- **R12 — NOVO (baixo).** O config do device está em `$HOME/.config/bhrecomp/`; outro usuário teria
  outro `HOME`. Mitigado: o launcher grava também em `$port_dir` e a execução é sempre via
  PortMaster (mesmo `HOME`, hoje `ark`).
- **R10** (Inspector/ImGui inexistente para GLES) segue declarado; **R7** (ubershaders ESSL ≈260 KB
  em Mali-G31) e **R8/R9** (sem BGRA / sem 16-bit UNORM / sem `GL_MIRROR_CLAMP_TO_EDGE`) pertencem
  ao M3.

## 8. Artefatos

| Artefato | Caminho / hash |
| :--- | :--- |
| Binário M5 publicado | `BodyHarvestRecompiled.m5_gles_api_20261018` — 22.988.496 B, md5 `fa3e4b59011263de4547191c1c811fe1` |
| Ferramenta de edits | `evidencias/tools/m5_gles_api_select_apply.py` |
| Build em fatias | `evidencias/tools/m5_build_aarch64.sh` |
| Checagem gate OFF por TU | `evidencias/tools/m5_gate_off_tu_check.sh` |
| Smoketest do launcher | `evidencias/tools/m5_launcher_smoketest.sh` |
| Templates de config | `graphics.json.auto`, `graphics.json.gles` |
| Logs RAW | `/root/bhrecomp/m5_gles_api_select_20261018/{ninja_bg,gate_off_tu}.log`, `manifest.json` |