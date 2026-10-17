# Adaptando os ports N64Recomp para traduções PT-BR — R36S / dArkOS

## 1. O que foi estudado

**[N64Recomp](https://github.com/N64Recomp/N64Recomp)** é a ferramenta que recompila estaticamente
binários de N64 em código C nativo. Os ports desta pasta usam esse ecossistema:

| Pasta | Port | Base (ecossistema) | Entrada exigida |
|---|---|---|---|
| `zeldaocarina/` | **Ship of Harkinian (SoH)** | Shipwright (OoT decomp) | ROM **original** aceita → gera `oot.o2r` |
| `zeldamajora/` | **2Ship2Harkinian (2S2H)** | 2Ship (MM decomp) | ROM **original** N64-US ou GC-US → gera `mm.o2r` |
| `Banjo-Kazooie (BR)/lighthouse/` | **Lighthouse** | Torch (HarbourMasters) | ROM **original** aceita → gera `bk.o2r` |
| `Body Harvest (USA)/` | — (não existe port N64Recomp deste jogo) | — | Jogar via emulação N64 do dArkOS |

## 2. Por que as ROMs PT-BR não funcionam diretamente nos ports

Todos esses ports validam o **SHA-1 da ROM** contra uma lista de hashes oficiais no momento
de gerar o arquivo `.o2r` (pacote de recursos extraídos da ROM). ROMs traduzidas/patcheadas
têm hash diferente e são **rejeitadas**. Evidências medidas nestas ROMs (ver
`evidencias/evidence_roms_identificacao.md` e `evidencias/evidence_adaptacao_ports_br.md`):

| ROM | Base | SHA-1 (.z64) | Hash aceito? |
|---|---|---|---|
| `Banjo-Kazooie (BR)....n64` | **PAL** (game code `NBKP`, 16 MB) | `C85EF782B43313845034C1C3ED371F63B652ACA7` (convertida) | ❌ |
| `Ocarina of Time (em portugues).z64` | **USA 1.0** (game code `CZLE`) | `59CA9A0170EE94EE273D3A558A17C67B9F883603` | ❌ |
| `Majora's Mask (E) [PT-BR].n64` | **PAL** (game code `NZSP`) | `ABC2B733C1110A722087E2CBE7D8B678A723BB47` | ❌ |

Além disso:
- O **Lighthouse** só aceita **romhacks com base US v1.0** (herança do Banjo's Backpack);
  a tradução BR do BK é base **PAL** → extração como romhack não é suportada.
- O formato `.n64` **não é detectado** pelo Torch (só `.z64` big-endian).

**A solução correta** é manter o port rodando a partir da ROM original e aplicar a
**tradução como MOD** (ports Zelda/BK suportam mods que sobrescrevem textos). As ROMs
PT-BR continuam úteis para emulação direta (núcleo N64 do dArkOS).

## 3. O que foi feito (adaptações nesta pasta)

1. **ROM BK convertida** `.n64` → `.z64`: `Banjo-Kazooie (BR)/lighthouse/Banjo-Kazooie (BR).z64`
   (original preservada; conversão por troca de pares de bytes, magic `80371240` validado).
2. **Mod PT-BR do SoH instalado** em `zeldaocarina/soh/mods/`:
   - `TraducaoPTBR-SolidOne-LordeJabiraca.otr` (tradução completa de textos)
   - `TraducaoPTBR_Reloaded_Letras.otr` (fonte com acentos)
   - Fonte: <https://gamebanana.com/mods/473895> — MD5 verificado.
3. **Mod PT-BR do 2S2H** (Release 1.3) para `zeldamajora/soh2/mods/`
   (fonte: <https://gamebanana.com/mods/542278>) — ver seção 4.2.
4. **Script de preparação**: `adaptar_ports_br.py` (converte ROM, instala mods e gera evidências).
   Script de identificação: `identificar_roms.py`.

## 4. Passo a passo no R36S (dArkOS)

Os ports vivem em `/roms2/ports` (algumas firmwares usam `/roms/ports`; o log do Lighthouse
confirma `/roms2/ports/lighthouse`). Copie as pastas via SSH (usuário `arkos`, senha `arkos`).

### 4.1 Ocarina of Time — Ship of Harkinian ⚠️ 1 ajuste pendente
A pasta contém `soh.o2r` + `soh.otr` (gerados anteriormente), **mas o launcher
(`Ship of Harkinian.sh`) só aceita `oot.o2r` ou `oot-mq.o2r`** — com o `soh.o2r` ele
falhará ("Missing ROM files!"). Duas saídas:
1. **Renomear** `soh.o2r` → `oot.o2r` (o binário carrega qualquer `.o2r` da pasta; teste e,
   se der crash/versão errada, use a opção 2).
2. **Gerar de novo**: colocar uma ROM **original aceita** (p.ex. NTSC 1.0 US, SHA-1
   `ad69c911…`) em `soh/baseroms/` e iniciar — o launcher gera o `oot.o2r` sozinho.
   Lista completa de hashes:
   <https://github.com/HarbourMasters/Shipwright/blob/develop/docs/supportedHashes.json>

Os mods PT-BR já estão em `soh/mods/` (`TraducaoPTBR-SolidOne-LordeJabiraca.otr` = textos,
`TraducaoPTBR_Reloaded_Letras.otr` = fonte com acentos) e carregam automaticamente;
idioma em *Settings → Languages*.


### 4.2 Majora's Mask — 2Ship2Harkinian ⚠️ exige ROM original
A pasta já tem um `2ship.o2r` pré-gerado, **mas o launcher exige `mm.o2r`** (gerado na
primeira execução a partir de uma ROM aceita):
- N64 US — SHA-1 `d6133ace5afaa0882cf214cf88daba39e266c078`
- GC US — SHA-1 `9743aa026e9269b339eb0e3044cd5830a440c1fd`

(Verifique em <https://2ship.equipment>.) A ROM PAL PT-BR **não** pode gerar o `.o2r`.
1. Obtenha a ROM N64 **US original** e coloque em `zeldamajora/soh2/baseroms/`.
2. Copie a pasta para `/roms2/ports/soh2` e inicie — o script gera o `mm.o2r`.
3. O mod PT-BR (R1.3) já está em `soh2/mods/`.
- **Teste opcional sem ROM**: se o `2ship.o2r` for realmente um `mm.o2r` renomeado, copiá-lo
  como `mm.o2r` pode fazer o port abrir (`cp 2ship.o2r mm.o2r`). Se o jogo reclamar de
  versão/crashar, use a via ROM original.

### 4.3 Banjo-Kazooie — Lighthouse ✅ language pack PT-BR próprio (17/10/2026)

O Lighthouse **não** aceita a ROM traduzida como romhack (base PAL ≠ US v1.0). A solução
adotada foi gerar um **language pack** `.o2r` a partir da própria ROM PT-BR:

- Arquivo: `Banjo-Kazooie (BR)/lighthouse/mods/~lang/bk_pt-BR.o2r` (285 KB, 1026 entradas)
- Conteúdo: **748 diálogos + 169 quiz + 29 Grunty questions** + **fonte de diálogo 0x6EB**
  (76 chunks, inclui os acentos) + **16 strings de UI** (tela de save e menu de pausa)
- `version` = `BK_VER_PAL (0xB1CC3F73)` e `langinfo` = `"Portuguese (BR)"` + tabela `strings:`
- Gerado por `gerar_langpack_ptbr_lighthouse.py` (v3)
- Evidência RAW: `evidencias/evidence_langpack_ptbr_lighthouse_20261017.md`

**Tela de seleção de save:** os rótulos ("JOGO 1", ": VAZIO", ": TEMPO", "QUEBRA-CABECA",
"NOTA", "APERTE A PARA JOGAR…") vêm da tabela `strings:` do `langinfo`, não dos diálogos.
Sem essa tabela o Lighthouse mantém o inglês — era o caso da v1/v2.
Rótulos sem acento de propósito: usam a fonte bold (0x6EC), que é idêntica à US e não
tem glifos PT-BR. Só os balões de diálogo usam a fonte acentuada (0x6EB).

**Intro:** o pack v3 não inclui overrides de modelo (a v1/v2 incluía modelos
`COPYRIGHT_OVERLAY`, `PRESS_START_OVERLAY`, `LEVEL_ENTRY_SIGNS` e `RACE_BANNER_START` de
forma parcial, o que podia quebrar o boot). Se a intro continuar sem tocar, verifique em
**Settings → Enhancements → Cutscenes** se "Skip Boot Logos"/"Start Skip Intro" estão
desligados e confira o `log.txt` (há registro antigo de crash na thread de áudio no R36S).

**Como usar no R36S:**

1. Copie `bk_pt-BR.o2r` para `/roms2/ports/lighthouse/mods/~lang/` (ou `/roms/ports/...`).
2. Abra o jogo → menu (SELECT/L3) → **Settings → General → Languages**.
3. Selecione **Portuguese (BR)**. Não é necessário reiniciar.

Observações:
- O `bk.o2r` base (US v1.1) **não** é alterado — o pack apenas repointa os assets de texto.
- A ROM `Banjo-Kazooie (BR).z64` pode ficar na pasta; ela é a origem do pack, não é usada
  em runtime.
- **Banjo: Recompiled** continua inviável no R36S (RT64 exige Vulkan; o Mali-G31 não tem
  `panvk` funcional no ArkOS).


### 4.4 Body Harvest — sem port
Não existe projeto N64Recomp para este jogo. Mantenha a ROM em
`/roms/n64` para rodar via emulação (dArkOS). Caso exista interesse, a criação de um port
exigiria um projeto de decompilação completo (fora do escopo de adaptação de ports).

## 5. Novos projetos criados (16/10/2026)

### `Banjo-Recompiled (BR)/` — port do Banjo: Recompiled para R36S ✅
- Binário aarch64 oficial v1.0.2 (glibc ≤ 2.35 ✓), modo portátil (`portable.txt`),
  empacotado no padrão PortMaster (`BanjoRecompiled.sh`, `port.json`, `banjorecomp.gptk`,
  `gameinfo.xml`).
- **Tradução PT-BR pré-instalada** em `banjorecomp/mods/` (`Banjo_PtBr_EduardoA.nrm` = textos,
  `Banjo_PtBr_EduardoA.rtz` = fontes/texturas HD — mod de Eduardo Angelo).
- Requer ROM **US 1.0** (SHA-1 `1fe1632098865f639e22c11b9a81ee8f29c75d7a`) — a US Rev 1
  usada pelo Lighthouse **não** é aceita.
- ⚠️ **Compatibilidade**: RT64 renderiza só via Vulkan — o Mali-G31 do R36S depende do
  driver panvk (experimental no ArkOS). Ver `README.md` do port.

### `Body Harvest (Recomp)/` — pipeline decomp→recomp iniciado ⚙️
- Decomp do jaytheham (84,53% matched / 99,97% decompilado) **compilado com a ROM do
  usuário → `build/bh.us.z64: OK` (byte-perfect)** e `bh.us.elf` com 6.933 símbolos.
- **N64Recomp executado: 7.117 funções recompiladas** (patch próprio
  `use_lookup_for_all_function_calls` adicionado ao N64Recomp para resolver jal entre overlays).
- Artefatos em `recomp/`; roadmap do runtime em `README_PORT.md`; evidência RAW em `evidencias/`.
- Para ficar jogável falta: runtime (vídeo/áudio/input no modelo Starship/N64ModernRuntime),
  RSPRecomp e eventos de overlay — trabalho de engenharia documentado no README do projeto.

## 6. Referências oficiais
- N64Recomp: <https://github.com/N64Recomp/N64Recomp>
- Banjo: Recompiled: <https://github.com/BanjoRecomp/BanjoRecomp> (releases com binário ARM64)
- Mod PT-BR BanjoRecomp: <https://gamebanana.com/mods/671137>
- Lighthouse (README romhacks/language packs): <https://github.com/HarbourMasters/Lighthouse>
- Shipwright — hashes suportados: <https://github.com/HarbourMasters/Shipwright/blob/develop/docs/supportedHashes.json>
- Verificador 2Ship: <https://2ship.equipment>
- Mods PT-BR Zelda: <https://gamebanana.com/mods/473895> (OoT/SoH) · <https://gamebanana.com/mods/542278> (MM/2S2H)
- Body Harvest decomp: <https://github.com/jaytheham/body-harvest-decompilation>
- Conversão de formatos de ROM: <https://hack64.net/tools/swapper.php>
