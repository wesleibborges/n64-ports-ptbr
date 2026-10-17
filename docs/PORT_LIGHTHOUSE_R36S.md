# Port Lighthouse (Banjo-Kazooie) — R36S / dArkOS

Este diretório publica o **port Lighthouse** empacotado no padrão PortMaster, mais o
language pack PT-BR. É o mesmo conteúdo que roda em `/roms2/ports/lighthouse`.

---

## 1. Estrutura

```
Banjo-Kazooie (BR)/lighthouse/
├── Lighthouse                 # binário aarch64 (build Jeod / PortMaster)
├── lighthouse.o2r             # assets do PORT (não do jogo)
├── Lighthouse.sh              # launcher (PortMaster)
├── port.json                  # metadados PortMaster
├── config.yml                 # hashes de ROM aceitos + yaml de extração
├── lighthouse.gptk            # mapeamento gptokeyb (L3=F1, R3=TAB)
├── gamecontrollerdb.txt       # banco SDL de controles
├── gameinfo.xml               # metadados EmulationStation
├── assets/yaml/{us,pal,jp}/   # definições de asset por região/rev
├── libs/                      # SDL2_net, ogg, vorbis, zip, zlib…
├── licenses/                  # licenças (Lighthouse, LibUltraShip, Torch…)
├── randomizer/                # (vazio em runtime)
├── baseroms/                  # opcional: ROM aqui é "staged" no 1º boot
├── mods/
│   ├── .gitkeep
│   └── ~lang/bk_pt-BR.o2r     # language pack PT-BR (284 KB)
├── cover.png · screenshot.png · thumb.png
└── README.md
```

> **Não versionados** (regeneráveis): `bk.o2r`, `bk.z64`, `*.z64` (ROM),
> `saves/`, `logs/`, `log.txt`, `imgui.ini`, `lighthouse.cfg.json`.

---

## 2. ROMs compatíveis

O binário só aceita as 4 revisões abaixo (validação por **SHA-1** em
`GameExtractor::mGameList`). Qualquer ROM modificada/patcheada é rejeitada na
geração do `bk.o2r`.

| Região / Revisão | SHA-1 | Observação |
|---|---|---|
| **US v1.0 (Rev 0)** | `1fe1632098865f639e22c11b9a81ee8f29c75d7a` | **Recomendada** — única base aceita para romhacks |
| **US v1.1 (Rev 1)** | `ded6ee166e740ad1bc810fd678a84b48e245ab80` | Base deste port e do pack PT-BR |
| **PAL** | `bb359a75941df74bf7290212c89fbc6e2c5601fe` | 50 Hz; base das traduções europeias |
| **JP** | `90726d7e7cd5bf6cdfd38f45c9acbf4d45bd9fd8` | Adiciona japonês/fonte kana |

Formato: `.z64` (big-endian, magic `80 37 12 40`).
`.n64` (byte-swapped) e `.v64` precisam ser convertidos — veja
`adaptar_ports_br.py` (`n64_para_z64`).

Verificação rápida do hash:

```bash
sha1sum "Banjo-Kazooie (U) (V1.1).z64"
```

---

## 3. Instalação no R36S (dArkOS)

1. Copie a pasta para o cartão:
   ```
   /roms2/ports/lighthouse/
   ```
   (algumas firmwares usam `/roms/ports`) O launcher deve ficar em
   `/roms2/ports/Lighthouse.sh`.

2. Coloque sua ROM em `baseroms/` **ou** deixe o picker abrir:
   ```
   /roms2/ports/lighthouse/baseroms/Banjo-Kazooie (U) (V1.1).z64
   ```

3. Inicie pelo menu **Ports**. No primeiro boot o Torch embutido lê a ROM e gera
   `bk.o2r` (≈24 MB, ~30 s no R36S).

4. Atualize a lista de jogos se o ícone não aparecer (Options → Restart).

---

## 4. Regenerar o `bk.o2r` (obrigatório após clonar)

O `bk.o2r` **não** é versionado: ele contém assets extraídos da ROM.

- **No device:** apague `bk.o2r` (se existir) e abra o port com a ROM em
  `baseroms/` — o Torch do próprio port regenera.
- **No PC (opcional):**
  ```bash
  torch o2r "Banjo-Kazooie (U) (V1.1).z64" -s . -d .
  ```
  (requer o `config.yml` e `assets/yaml` deste diretório)

---

## 5. Language pack PT-BR

Arquivo: `mods/~lang/bk_pt-BR.o2r`
Base de origem: tradução brasileira (Brazilian Warriors / Nintendo BR, ferramenta
PacoChan) aplicada sobre ROM PAL; conversão para O2R feita por
`gerar_langpack_ptbr_lighthouse.py`.

Ativação no jogo:

```
Settings → General → Languages → Portuguese (BR)
```

Conteúdo: 748 diálogos, 169 quiz, 29 perguntas da Grunty, fonte de diálogo 0x6EB
(acentos) e 16 strings de UI (tela de save + menu de pausa).

Detalhes técnicos: [`docs/GUIA_LANGPACK_O2R_LIGHTHOUSE.md`](../../docs/GUIA_LANGPACK_O2R_LIGHTHOUSE.md).

---

## 6. Controles (padrão)

| Botão | Ação |
|---|---|
| Analógico esquerdo | mover |
| A / B / Z | ações do jogo |
| Start | menu do jogo |
| **L3** | menu ImGui do port (F1) |
| **R3** | alternar tela cheia (TAB) |

Mapeamento ajustável em `lighthouse.gptk` (gptokeyb) e no menu do port
(*Controller → Mapper*), que grava um arquivo de mapeamento customizado.

---

## 7. Solução de problemas

| Sintoma | Causa provável | Ação |
|---|---|---|
| "Missing ROM" / pede ROM sempre | ROM ausente ou hash inválido | conferir SHA-1 na tabela da seção 2 |
| Tela preta + crash no áudio | race na thread de áudio do port no R36S | ver `log.txt`; testar com áudio em 22050 Hz; reportar |
| Intro não toca | `Start` detectado no boot + save existente | não há auto-skip; conferir *Enhancements → Cutscenes* |
| Não abre (erro Vulkan) | você está usando **Banjo: Recompiled**, não Lighthouse | Lighthouse usa OpenGL ES; Recompiled exige Vulkan |
| Pack PT-BR não aparece | `langinfo` ausente ou `version` inválido | revalidar o `.o2r` (ver guia, Passo 8) |

---

## 8. Créditos e licenças

- **Lighthouse** — HarbourMasters (Malkierian, JeodC, Caladius, aMannus) — código CC0-1.0
- **Torch** — HarbourMasters — MIT
- **libultraship** — HarbourMasters — MIT
- **Empacotamento PortMaster (aarch64)** — Jeod
- **Tradução PT-BR** — Brazilian Warriors / Nintendo BR (Xujozer, Kamppello, Sergio-F), ferramenta de PacoChan
- **Conversão para language pack / scripts** — este repositório

Nenhum asset de jogo é distribuído aqui. Você precisa da sua própria ROM.
