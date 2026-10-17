# EVIDENCIA RAW - Language Pack PT-BR para Lighthouse (R36S)

Data: 2026-10-17T12:30:00Z
Ambiente: maquina local (WSL x86_64), sem AWS
Artefato: `Banjo-Kazooie (BR)/lighthouse/mods/~lang/bk_pt-BR.o2r` (350.123 bytes)

## 1. Insumos

| Item | Valor |
|---|---|
| ROM base PT-BR | `Banjo-Kazooie (BR).z64` (PAL, game code NBKP, 16.777.216 bytes) |
| SHA-1 (.z64) | `C85EF782B43313845034C1C3ED371F63B652ACA7` |
| Base do port | `bk.o2r` US Rev1 (v1.1), CRC `0xCD7559AC` -> `BK_VER_US_11 0xAC5975CD` |
| Verdade do formato | Torch (HarbourMasters) compilado 2026-10-17 + codigo `src/port/Localization/Language.cpp` |

## 2. Metodo (extracao direta da ROM)

Descompressao BKZIP: header `11 72` + u32 BE de tamanho, corpo em zlib raw (`wbits=-15`).

Tabela de assets: offset `0x5E90`; `u32` count; `dataStart = 0x5E90 + 8 + count*8`;
entradas de 8 bytes `(u32 blobOffset, i16 compressionFlag, i16 tFlag)`.

### Formatos N64 -> O2R

| Tipo | N64 (PAL) | O2R gerado |
|---|---|---|
| dialog | `03 07 00` + fr/de u16 + bloco | header `LDKB` 64B + u32 langCount + u32 bottom + (u8 cmd, u32 len, str)* + u32 top + ... |
| quizq | `03 01 02` + 3 u16 + u8 size | header `QQKB` + u32 langCount + u32 text + (u8 cmd, u32 len, str)* + u32 opts + ... |
| gruntyq | `03 03 00` + 3 u16 + u8 size | header `QGKB` + u32 langCount + u32 text + (u8 cmd, u32 len, str)* + u32 opts + (u8 cmd, u8 unk0, u8 unk1, u32 len, str)* |

## 3. Resultado da geracao

```
TOTAL ENTRADAS: 1057
raiz: portVersion, assets/portVersion, version, langinfo
categorias: dialog 748 | quizq 169 | gruntyq 29 | font 0x6EB 76 | outros lang assets 31
duplicados: 0
zip integrity: OK
```

Arquivos de controle:

```
version  = 01 b1 cc 3f 73   -> 0xB1CC3F73 = BK_VER_PAL
langinfo = 01000000 01000000 00000000 00000000 0f000000 "Portuguese (BR)"
```

### Amostras de conteudo (bytes verbatim da ROM PT-BR)

```
ASSET_90B_BLUBBER_FIRST_MEET    -> "AH, OLc! SOU O CAPIT[O GORDURA,  PERDI MEU TESOURO..."
ASSET_A52_BOTTLES_BRIDGE_BROKEN -> "EI! ONDE VOCdS EST[O INDO?"
ASSET_C01_FF_QUIZ_QUESTION      -> "VOCd ENCONTROU O SUFICIENTE E b ISSO O QUE IMPORTA,"
ASSET_CAB_FF_GRUNTY_QUESTION    -> "LEMBRE-SE AGORA, N[O FIQUE CONFUSO,"
```

Os bytes `c`, `[`, `d`, `b`, `^` sao indices do charset BK e renderizam como acentos
quando a fonte 0x6EB do pack esta ativa.

## 4. Fonte de dialogo (0x6EB) - obrigatoria

Comparacao do asset cru na ROM:

```
US 0x6EB: 11464 bytes  sha1=14fe20bc784d...
BR 0x6EB: 11472 bytes  sha1=eb61963c9352...
bytes divergentes no overlap: 438 | extra BR: 8
```

No O2R exportado (via Torch): 72 de 76 chunks diferem. Sem essa fonte os acentos
PT-BR nao renderizam corretamente.

## 5. Assets graficos de idioma incluidos (diferem do base)

```
ASSET_4EB RACE_BANNER_START   : 2 entradas
ASSET_54E COPYRIGHT_OVERLAY   : 8 entradas
ASSET_55C PRESS_START_OVERLAY : 2 entradas
ASSET_563 LEVEL_ENTRY_SIGNS   : 19 entradas
ASSET_6EB DIALOG_FONT         : 72 entradas
```

Assets de idioma identicos ao base (nao incluidos): 2EE, 46C, 486, 48B, 4EA, 50A,
54C, 54D, 55D, 56C, 6EC.

## 6. Como o Lighthouse consome o pack (codigo verificado)

`src/port/Localization/Language.cpp`:

- `RescanLanguages()` le `langinfo` de cada archive e registra nome/indice/script.
- `BuildPackOverride()` le `version`, chama `ClassifyArchiveVersion()` e usa o
  inverso de `sV10toPALRemap` para converter IDs PAL -> v1.0.
- `AssetHexFromPath()` extrai o ID de `ASSET_<HEX>_` no path.
- `DropUnchangedOverrides()` mantem o override quando qualquer membro da familia difere.

`ArchiveManager::AddArchive()`: packs em `mods/~lang/*.o2r` sao adicionados depois do
base e `mFileToArchive[hash]` e sobrescrito, entao os chunks do pack vencem.

`src/port/Engine.cpp:115`: `InitResourceManager({assets_path}, {}, 3, true)` — lista de
versoes validas vazia, portanto o stamp PAL e aceito.

## 7. Conclusao

Pack PT-BR gerado e estruturalmente validado: 946 assets de texto + fonte acentuada +
31 assets graficos traduzidos.

Instalacao: copiar `bk_pt-BR.o2r` para `mods/~lang/` e selecionar "Portuguese (BR)" em
Settings -> General -> Languages.

## 8. Revisao v3 (17/10/2026 - apos teste no R36S)

Feedback do teste: dialogs em PT-BR OK, porem (a) a intro do jogo nao tocou e
(b) os textos da tela de selecao de save ficaram em ingles.

### 8.1 Tela de saves (causa e correcao)

Os rotulos da tela de save NAO estao nos dialogs: sao strings fixas do codigo,
localizadas via a tabela opcional de strings do arquivo `langinfo`
(rotina `ParseLangInfo` -> `ResourceMgr_GetLangString`). A versao v2 nao trazia
essa tabela, por isso nada foi traduzido ali.

Chaves adicionadas (16), extraidas de `src/core2/gameSelect.c`,
`src/core2/gc/pauseMenu.c` e de `Localization.cpp` (`buildPackFileSelectInfo`):

```
USE THE CONTROL STICK TO SELECT A GAME.           -> USE O ANALOGICO PARA ESCOLHER UM JOGO.
PRESS A TO PLAY THE GAME OR Z TO ERASE IT!        -> APERTE A PARA JOGAR OU Z PARA APAGAR!
ARE YOU SURE? PRESS A TO CONFIRM, OR B TO CANCEL. -> TEM CERTEZA? APERTE A PARA CONFIRMAR OU B PARA CANCELAR.
GAME  -> JOGO            : EMPTY -> : VAZIO        : TIME  -> : TEMPO
 JIGSAW  ->  QUEBRA-CABECA     JIGSAWS ->  QUEBRA-CABECAS
 NOTE    ->  NOTA              NOTES   ->  NOTAS
RETURN TO GAME       -> VOLTAR AO JOGO
EXIT TO WITCH'S LAIR -> SAIR PARA O COVIL DA BRUXA
VIEW TOTALS          -> VER TOTAIS
SAVE AND QUIT        -> SALVAR E SAIR
ARE YOU SURE?        -> TEM CERTEZA?
A - YES, B - NO      -> A - SIM, B - NAO
```

Sem acentos de proposito: essas linhas sao desenhadas com a fonte bold (0x6EC),
que no pack e byte-identica a US e nao possui glifos PT-BR. A fonte com acentos
(0x6EB) e usada nos baloes de dialogo.

### 8.2 Intro (investigacao)

Hipotese de causa no pack: a v2 incluia overrides PARCIAIS de modelos
(ASSET_54E COPYRIGHT_OVERLAY, ASSET_55C PRESS_START_OVERLAY, ASSET_563
LEVEL_ENTRY_SIGNS, ASSET_4EB) - apenas os sub-assets divergentes. Familia
incompleta (modelo do base + texturas PAL) pode quebrar o desenho no boot, e o
listener `OnModelLoad` forca reload desses modelos a cada troca de idioma.

Acao: esses 4 assets foram REMOVIDOS na v3. Ficaram apenas familias completas:
dialogs, quiz, grunty e a sprite da fonte 0x6EB (todas as 76 entradas).

Logica de skip de intro no codigo (nao depende do pack):
`cutscene_skip.c` -> `cutscene_skipIntroCutsceneCheck()` so pula se
`controller_getStartButtonSafe(0) == 1` e existir save; `func_8031D0C0()`
avanca os logos com Start. Nao existe auto-skip.
Complemento: o log antigo do device (2026-08-10, anterior ao pack) registra
crash na thread de audio (`audioManagerThread_entry` / `osAiGetLength`), o que
pode abortar a cutscene de intro.

### 8.3 Estado final v3

```
tamanho: 284.577 bytes | entradas: 1026 | integridade: OK
categorias: dialog 748 | quizq 169 | gruntyq 29 | font 0x6EB 76 | controle 4
langinfo: version=1, 1 idioma (Portuguese (BR), idx 0, script 0), 16 strings
version: 0xB1CC3F73 (BK_VER_PAL)
```
