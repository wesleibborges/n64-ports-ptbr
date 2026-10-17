# Guia completo — Language Pack PT-BR para Banjo-Kazooie (Lighthouse) no R36S

> Documento técnico e reproduzível. Cobre ferramentas, formatos binários, pipeline,
> validação e lições aprendidas. Base: sessão de 17/10/2026 que gerou
> `bk_pt-BR.o2r` (284.577 bytes, 1026 assets) funcionando no R36S / dArkOS.

---

## 1. Objetivo

Traduzir **Banjo-Kazooie no port Lighthouse (HarbourMasters)** para PT-BR usando a
ROM traduzida brasileira (base PAL), **sem** alterar o `bk.o2r` base e **sem**
depender de Vulkan (o que inviabiliza o port concorrente no R36S).

Resultado entregue:

| Item | Valor |
|---|---|
| Artefato | `mods/~lang/bk_pt-BR.o2r` |
| Tamanho | 284.577 bytes (1026 entradas) |
| Conteúdo | 748 diálogos, 169 quiz, 29 Grunty questions, fonte 0x6EB (76 chunks), 16 strings de UI |
| Base do port | `bk.o2r` US Rev1 (v1.1) — **não modificado** |
| `version` stamp | `0xB1CC3F73` (`BK_VER_PAL`) |
| `langinfo` | `Portuguese (BR)`, índice 0, script Latin + tabela de 16 strings |

---

## 2. Por que não usar o Banjo: Recompiled

O projeto **Banjo: Recompiled** (N64Recomp + RT64) tem tradução PT-BR pronta, mas o
RT64 renderiza **somente** via Vulkan/D3D12/Metal. O R36S (RK3326 + Mali-G31 MP2)
depende do driver `panvk`, experimental/ausente no ArkOS. Já o Lighthouse usa
**OpenGL ES** (`libGLESv2`, panfrost) e roda nativamente em `aarch64`.

Conclusão: no R36S o caminho é **Lighthouse + language pack**, não Recompiled.

---

## 3. Arquitetura do sistema de idiomas do Lighthouse

### 3.1 Descoberta dos packs

`src/port/Engine.cpp` → `LoadLanguagePacks()` varre `mods/~lang/` e adiciona cada
`.o2r` como archive:

```cpp
for (const auto& p : directory_iterator(lang_path))
    if (p.path().extension() == ".o2r")
        ArchiveManager()->AddArchive(p.path().generic_string());
```

Packs dentro de `mods/~lang/<hack>/` são *scoped* ao romhack; na raiz valem para o
jogo base.

### 3.2 Registro do idioma (`langinfo`)

`src/port/Localization/Language.cpp` → `RescanLanguages()` lê o arquivo `langinfo`
de cada archive. Formato binário (little-endian):

```
u32 version          // deve ser 1
u32 count            // número de idiomas
repete count:
    u32 index        // slot do idioma dentro dos blobs de diálogo
    u32 script       // 0 = Latin, 1 = JP
    str name         // u32 len + bytes (nome exibido no dropdown)
[opcional] u32 scount
repete scount:
    str key          // string em inglês (chave)
    str value        // tradução
```

Sem `langinfo` o pack é ignorado. Sem a tabela de strings, a **UI** (tela de save,
menu de pausa) permanece em inglês — só os diálogos são traduzidos.

### 3.3 Selo de versão (`version`)

`src/port/GameVersion/BaseGameVersion.cpp` → `ReadStampedCrc()`:

```
byte 0      = endianness (0x01 = big)
bytes 1..4  = CRC da versão (lido big-endian)
```

Valores conhecidos (`src/port/Engine.h`):

| Constante | Valor |
|---|---|
| `BK_VER_US_10` | `0x0693BFA4` |
| `BK_VER_US_11` | `0xAC5975CD` |
| `BK_VER_PAL` | `0xB1CC3F73` |
| `BK_VER_JP` | `0x20D56851` |

`ClassifyArchiveVersion()` aceita o valor direto **ou** com byteswap. Um pack cujo
selo não seja reconhecido é **recusado**:

> `[Lang] '{}': pack version stamp matches no known ROM; refusing to apply it.`

### 3.4 Remap de IDs (v1.0 ↔ v1.1 ↔ PAL ↔ JP)

`BuildPackOverride()` escolhe a tabela inversa conforme o selo do pack
(`sV10toV11Remap`, `sV10toPALRemap`, `sV10toJPRemap`) e converte cada ID do pack
para o ID canônico **v1.0**. O `ResourceHelpers` então injeta aliases v1.0 → versão
base, de modo que o código decompilado (que usa IDs v1.0) resolva o asset do pack.

Por isso o pack **precisa** ser selado com a região de onde os assets vieram
(aqui, PAL).

### 3.5 Descoberta de assets por ID

`AssetHexFromPath()` extrai o ID numérico de `ASSET_<HEX>_` no **path** dentro do
zip. Consequência prática: o nome depois do ID é livre; só o hex importa.

`DropUnchangedOverrides()` descarta overrides cujo conteúdo seja byte-idêntico ao
base — mas só quando **toda a família** de IDs iguais é idêntica. Famílias
parciais são mantidas.

### 3.6 Prioridade de archive

`ArchiveManager::AddArchive()` faz `mFileToArchive[hash] = archive` — o **último
archive adicionado vence**. Como packs de idioma são adicionados depois do
`bk.o2r`, os chunks do pack sobresscrevem os do base em paths iguais.

### 3.7 Fontes (`0x6EB` diálogo / `0x6EC` bold)

O pack de idioma pode repontar as fontes. No nosso caso:

| Asset | US | BR/PAL | Ação |
|---|---|---|---|
| `0x6EB` DIALOG_FONT_ALPHAMASK | 11.464 B | 11.472 B | **incluir** (72/76 chunks diferem — acentos) |
| `0x6EC` BOLD_FONT_LETTERS | 58.336 B | idêntico | omitir |

**Lição crítica:** o texto PT-BR usa bytes do charset BK (ex.: `a`=Ç, `c`=Á,
`d`=Ê, `g`=Í, `^`=Ó, `[`=Ã, `b`=É). Os acentos vivem na fonte `0x6EB`. A fonte
bold `0x6EC` não foi alterada pela tradução → **não usar acentos** em strings de
UI desenhadas com a bold.

---

## 4. Ferramentas utilizadas

| Ferramenta | Versão / Origem | Para quê |
|---|---|---|
| `git` | 2.34 (WSL Ubuntu) | clonar fontes, versionar |
| `cmake` | 3.22+ | configurar build do Torch |
| `ninja` | 1.x | build incremental do Torch |
| `gcc/g++` | 11.4 | compilar Torch |
| `tmux` | 3.x | manter build longo vivo (o terminal da sessão mata processos em 30 s) |
| `python3` | 3.10 | extração/conversão (stdlib: `zlib`, `zipfile`, `struct`, `re`, `hashlib`) |
| **Torch** | `github.com/HarbourMasters/Torch` | exportar sprites/modelos no formato O2R |
| **Lighthouse** (fonte) | `github.com/HarbourMasters/Lighthouse` | ler o código do sistema de idiomas |
| **libultraship** (fonte) | `github.com/HarbourMasters/libultraship` | archive/prioridade/versão |
| R36S / dArkOS | `/roms2/ports` | alvo de execução |

### Por que compilar o Torch?

O formato O2R de **sprites** e **modelos** não é o formato bruto da ROM: o Torch
parseia, re-encoda e publica múltiplos assets (metadados + chunks de textura). Para
a fonte `0x6EB` isso é obrigatório. Diálogos/quiz/grunty, ao contrário, são
conversões mecânicas que fizemos em Python (mais rápido e auditável).

### Build do Torch (comandos exatos)

```bash
git clone --depth 1 https://github.com/HarbourMasters/Torch torch-build
cd torch-build
cmake -S . -B build-cmake -G Ninja -DCMAKE_BUILD_TYPE=Release
tmux new-session -d -s build 'ninja -C build-cmake -j8 > /tmp/build.log 2>&1'
tail -f /tmp/build.log          # acompanhar
./build-cmake/torch --help      # binário final
```

Dependências de sistema (Ubuntu/WSL): `cmake ninja-build libbz2-dev zlib1g-dev`.

> **Pitfall:** rodar `ninja` em foreground por mais de ~30 s em um agente/terminal
> com timeout mata o build. Use `tmux` e acompanhe por log.

---

## 5. Pipeline reproduzível

### Passo 0 — Pré-requisitos

- ROM traduzida (aqui: `Banjo-Kazooie (BR).z64`, PAL, game code `NBKP`, 16 MB)
- `bk.o2r` base do port (US Rev1) para copiar headers de 64 bytes
- Torch compilado
- Fonte do Lighthouse para consulta
- Python 3

### Passo 1 — Identificar a ROM e o tipo de base

```python
rom = open('Banjo-Kazooie (BR).z64','rb').read()
# magic 0x80371240 = z64 big-endian
# 0x3B..0x3E = game code (NBKP = PAL), 0x3F = rev
```

Guardar SHA-1 para evidência.

### Passo 2 — Ler a tabela de assets

Offset fixo `0x5E90`:

```python
count     = struct.unpack('>I', rom[0x5E90:0x5E94])[0]
dataStart = 0x5E90 + 8 + count * 8
# entradas de 8 bytes:
#   u32 blobOffset (relativo a dataStart)
#   i16 compressionFlag  (1 = BKZIP)
#   i16 tFlag            (4 = slot vazio)
```

O tamanho de cada asset = distância até o próximo `blobOffset` maior.

### Passo 3 — Descomprimir BKZIP

Cada asset comprimido começa com o header `11 72`:

```python
def bk_unzip(blob):
    assert blob[0] == 0x11 and blob[1] == 0x72
    expected = struct.unpack('>I', blob[2:6])[0]
    return zlib.decompress(blob[6:], wbits=-15)   # zlib raw
```

`expected` é o tamanho descomprimido — use para validar.


### Passo 4 — Converter os 3 tipos de texto

Layouts N64 (PAL) e destino O2R:

| Tipo | N64 | O2R |
|---|---|---|
| dialog | `03 07 00` + `u16 fr` + `u16 de` + bloco EN | header `LDKB` 64 B + `u32 langCount` + `u32 bottom` + entradas + `u32 top` + entradas |
| quizq | `03 01 02` + 3×`u16` + `u8 size` | header `QQKB` + `u32 langCount` + `u32 text` + entradas + `u32 opts` + entradas |
| gruntyq | `03 03 00` + 3×`u16` + `u8 size` | header `QGKB` + `u32 langCount` + `u32 text` + entradas + `u32 opts` + entradas |

Entrada de texto N64: `u8 cmd` + `u8 len` + `len` bytes.
Entrada de texto O2R: `u8 cmd` + `u32 len` + `len` bytes (little-endian).

Grunty tem opções especiais:

- N64: `u8 cmd` + `u8 len` + `u8 unk0` + `u8 unk1` + `len-2` bytes
- O2R: `u8 cmd` + `u8 unk0` + `u8 unk1` + `u32 len` + bytes

> O texto completo de uma opção de grunty é `unk0 + unk1 + str` — os dois primeiros
> caracteres ficam nos campos de controle (ex.: `S`+`O`+`RVETE DE ATUM` = "SORVETE DE ATUM").

Terminador de bloco de diálogo: `04 01 00` após contagem zero (Banjo's Backpack).

### Passo 5 — Selecionar os assets corretos

Use o `assets.yaml` da **mesma região** da ROM (aqui `pal/rev0`) como fonte dos
nomes. **Mas** o runtime parseia cada asset pelo **tipo do base** (US rev1), então
descarte IDs cujo tipo diverge entre as duas tabelas:

```
0xC00  dialog  (PAL)  vs  quizq   (US)  -> descartar
0xCAA  quizq   (PAL)  vs  gruntyq (US)  -> descartar
0xCC8  gruntyq (PAL)  vs  level   (US)  -> descartar
```

Manter apenas `dialog`, `quizq`, `gruntyq` com mesmo tipo em ambos.

### Passo 6 — Extrair a fonte acentuada (Torch)

Registre o SHA-1 da ROM traduzida em um `config.yml` local apontando para o yaml
PAL e rode o Torch:

```yaml
c85ef782b43313845034c1c3ed371f63b652aca7:
  name: Banjo-Kazooie (BR) PAL
  path: assets/yaml/pal/rev0
  config:
    gbi: F3DEX_BK64
    sort: OFFSET
    logging: WARN
    textures: ADDITIONAL_DEFINES
    include_autogen: true
    output: { binary: bk.o2r, code: src/assets, headers: include/assets, modding: src/assets }
```

```bash
torch o2r br.z64 -s /caminho/com/config.yml -d /tmp/saida -u 1
```

Do O2R gerado, copie **todas** as entradas `ASSET_6EB*` (metadados + 76 chunks).

### Passo 7 — Montar `langinfo`, `version` e empacotar

```python
# version = 0xB1CC3F73 (PAL), big-endian após o byte de endianness
oz.writestr('version', bytes([1]) + struct.pack('>I', 0xB1CC3F73))

# langinfo
li  = struct.pack('<I', 1)               # version
li += struct.pack('<I', 1)               # 1 idioma
li += struct.pack('<I', 0)               # index 0
li += struct.pack('<I', 0)               # script Latin
li += struct.pack('<I', len(name)) + name
li += struct.pack('<I', len(strings))
for k, v in strings: li += pack_str(k) + pack_str(v)
```

Empacotar como zip deflate. Copiar também `portVersion` e `assets/portVersion`
do base.

### Passo 8 — Validar

```python
assert zip.testzip() is None                 # integridade
assert len(names) == len(set(names))         # sem duplicados
assert z.read('version')[1:] == struct.pack('>I', 0xB1CC3F73)
# langinfo: parsear até o último byte (pos == len(li))
# cada dialog: magic LDKB, langCount=1, contagens coerentes
# cada quiz:   magic QQKB ; cada grunty: magic QGKB
# sprite:      meta PSKB + chunks XETO
```

### Passo 9 — Instalar no R36S

```
/roms2/ports/lighthouse/mods/~lang/bk_pt-BR.o2r
```

No jogo: **Settings → General → Languages → Portuguese (BR)**.


---

## 6. Referência rápida de formatos

### Header O2R (64 bytes)

```
00 00 00 00  <magic 4B>  00 00 00 00  EF BE AD DE  EF BE AD DE  + zeros
```

Magics: `LDKB` (dialog), `QQKB` (quiz), `QGKB` (grunty), `PSKB` (sprite meta),
`XETO` (textura).

### Charset PT-BR (derivado do texto traduzido)

| Byte | Renderiza |
|---|---|
| `a` | Ç |
| `b` | É |
| `c` | Á |
| `d` | Ê |
| `g` | Í |
| `^` | Ó |
| `[` | Ã |
| `]` | Ü |
| `\` | Ö |

Não invente bytes novos: copie o texto **verbatim** da ROM traduzida. O jogo
renderiza com a fonte `0x6EB` do pack.

---

## 7. Lições aprendidas

1. **Nem toda "tradução" está nos diálogos.** Tela de save, menu de pausa e
   confirmações são strings de código → exigem a tabela `strings:` do `langinfo`.
   Sem ela o pack "funciona" mas a UI fica em inglês.

2. **Famílias de assets não podem ser parciais.** Modelos/sprites são compostos por
   vários arquivos que compartilham o mesmo `ASSET_<hex>`. Substituir só os que
   diferem gera estado inconsistente (modelo de uma versão + textura de outra) e
   pode quebrar boot/cutscene. **Inclua a família inteira ou nada.**

3. **Separe o pack em camadas para diagnosticar.** Texto → fonte → gráficos. Foi
   assim que ficou claro que os modelos parciais quebravam o boot e que texto/fonte
   estavam corretos.

4. **O selo `version` decide o remap.** Pack selado como PAL usa
   `sV10toPALRemap`; selado como US v1.1 usaria outro mapa. Selo errado = assets
   apontando para IDs errados (tradução "some" silenciosamente).

5. **`langinfo` sem tabela de strings ainda é válido** — mas limita a tradução aos
   diálogos. O parser só lê a tabela se ela existir; EOF = "sem overrides".

6. **Fonte de diálogo ≠ fonte bold.** `0x6EB` tinha os acentos; `0x6EC` não. Usar
   acento em texto de UI (bold) produz glifo errado.

7. **Nomes de arquivo no zip só importam pelo hex.** `AssetHexFromPath()` lê
   `ASSET_<HEX>_`; o restante do nome é decorativo.

8. **Prioridade de archive é "último vence"**, então chunks do pack sobrescrevem o
   base em paths iguais — não é preciso renomear nada.

9. **Build de ferramentas nativas precisa de sessão persistente.** Timeout de
   terminal matou o `ninja` várias vezes; `tmux` resolveu.

10. **Valide com o binário oficial quando o formato for complexo.** Para sprites,
    reimplementar em Python era arriscado; compilar o Torch e usar a saída dele foi
    mais seguro (7 s de extração).

11. **Idioma não muda a versão base.** `ResourceMgr_IsPal()` depende de
    `sDialogLanguageCount` (1 no nosso pack), não do selo. O pack PAL não "converte"
    o jogo para PAL.

12. **Intro do BK**: o skip depende de `Start` + save existente
    (`cutscene_skipIntroCutsceneCheck`). Não há auto-skip; se a intro não tocar,
    investigue input fantasma, enhancement de cutscene ou crash de áudio no device.

13. **Multi-idioma no `langinfo`**: `count > 1` só faz sentido se os blobs tiverem
    vários idiomas. Nosso pack tem `langCount=1` e `index=0` — coerente em todos os
    assets.

---

## 8. Como adaptar para outros ports

| Port | Sistema de mods | Observações |
|---|---|---|
| **Ship of Harkinian / 2Ship2Harkinian** | `.otr`/`.o2r` em `mods/` | Traduções PT-BR já existem (GameBanana). Aplicar como mod sobre o `.o2r` gerado da ROM original. |
| **Lighthouse (BK)** | `mods/~lang/*.o2r` | Este guia. |
| **Outros N64Recomp (ex.: DK64)** | varia | Verifique se há sistema de language pack; senão, mod de assets. |

Regra geral: **descubra primeiro como o runtime resolve assets de idioma**. Se
existe `langinfo`/lista de packs, gere um pack; se não, use mod de assets com paths
sobrescrevendo o base.

---

## 9. Aspectos legais

- **Não distribua ROMs nem `.o2r`/`.otr`** gerados a partir delas: são assets
  protegidos. Publique apenas **scripts, documentação e evidências técnicas**.
- Este repositório **não** contém ROM, `bk.o2r`, saves ou packs `.o2r`.
- Os scripts assumem que o usuário possui a ROM original e a tradução com licença
  de uso adequada.

---

## 10. Índice de evidências

| Arquivo | Conteúdo |
|---|---|
| `evidencias/evidence_langpack_ptbr_lighthouse_20261017.md` | formatos, contagens, amostras de texto, investigação da intro, revisão v3 |
| `evidencias/evidence_adaptacao_ports_br.md` | hashes de ROM vs hashes aceitos pelos ports |
| `evidencias/evidence_roms_identificacao.md` | identificação de ROMs (game code, região, SHA-1) |

