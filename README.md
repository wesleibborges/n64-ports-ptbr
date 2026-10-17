# Ports N64 → Retro Handhelds (R36S) — Traduções PT-BR

Repositório de **documentação, scripts e evidências técnicas** sobre adaptação de
ports nativos de N64 (Lighthouse, Ship of Harkinian, 2Ship2Harkinian, N64Recomp)
para rodar em handhelds ARM — com foco em **traduções PT-BR**.

> ⚠️ **Sem conteúdo protegido.** Este repositório não contém ROMs, arquivos `.o2r`/
> `.otr`, saves, packs de idioma nem binários de jogos. Apenas código, documentação
> e registros de engenharia. Para usar os scripts você precisa da sua própria ROM.

---

## 📌 O que tem aqui

| Caminho | Descrição |
|---|---|
| [`docs/GUIA_LANGPACK_O2R_LIGHTHOUSE.md`](docs/GUIA_LANGPACK_O2R_LIGHTHOUSE.md) | **Guia completo**: arquitetura do sistema de idiomas do Lighthouse, formatos binários, pipeline reproduzível, ferramentas e lições aprendidas |
| [`LEIA-ME_TRADUCOES_PT-BR.md`](LEIA-ME_TRADUCOES_PT-BR.md) | Panorama dos ports por pasta: o que funciona, o que não funciona e por quê |
| [`gerar_langpack_ptbr_lighthouse.py`](gerar_langpack_ptbr_lighthouse.py) | Gera o language pack PT-BR (`bk_pt-BR.o2r`) direto da ROM traduzida |
| [`adaptar_ports_br.py`](adaptar_ports_br.py) | Converte ROM `.n64`→`.z64`, instala mods PT-BR e confere hashes |
| [`identificar_roms.py`](identificar_roms.py) | Identifica ROMs N64 (game code, região, rev, SHA-1) |
| [`evidencias/`](evidencias/) | Evidências RAW: formatos, contagens, amostras, investigação de bugs |

---

## 📦 Projetos relacionados

O **port pronto para jogar** (binário Lighthouse aarch64 + language pack PT-BR +
instalação no R36S) fica em repositório separado:

➡️ **[`wesleibborges/banjo-kazooie-ptbr`](https://github.com/wesleibborges/banjo-kazooie-ptbr)**

Ferramenta online do projeto (verificação de ROM por SHA-1, no navegador):
<https://wesleibborges.github.io/banjo-kazooie-ptbr/>

Este repositório aqui é a **base de engenharia**: método, formatos, scripts e
evidências reutilizáveis para outros ports/traduções.


---

## 🎯 Caso de estudo: Banjo-Kazooie (Lighthouse)

Language pack **PT-BR** para **Banjo-Kazooie (Lighthouse)** rodando no **R36S**
(usado como referência do método descrito neste repositório):

```
bk_pt-BR.o2r  —  284.577 bytes  —  1026 entradas
├── 748 diálogos
├── 169 perguntas de quiz
├──  29 perguntas da Grunty
├──  76 chunks da fonte de diálogo (acentos PT-BR)
└──  16 strings de UI (tela de save + menu de pausa)
```

Instalação:

```
/roms2/ports/lighthouse/mods/~lang/bk_pt-BR.o2r
```

No jogo: **Settings → General → Languages → Portuguese (BR)**.

---

## 🧠 Insights que economizam dias

1. **Tradução não é só diálogo.** Tela de save/menu usam strings de código →
   precisam da tabela `strings:` dentro do `langinfo` do pack.
2. **Selo `version` define o remap de IDs** (v1.0 ↔ v1.1 ↔ PAL ↔ JP). Selo errado
   faz a tradução "sumir" silenciosamente.
3. **Famílias de assets devem ser completas.** Substituir metade dos arquivos de um
   modelo quebra boot/cutscene.
4. **Fonte de diálogo (`0x6EB`) ≠ fonte bold (`0x6EC`).** Só a primeira tem acentos.
5. **Banjo: Recompiled não roda no R36S** (RT64 exige Vulkan; Mali-G31 sem `panvk`).
   Lighthouse usa OpenGL ES e roda.

Detalhes e comandos em [`docs/GUIA_LANGPACK_O2R_LIGHTHOUSE.md`](docs/GUIA_LANGPACK_O2R_LIGHTHOUSE.md).

---

## 🛠️ Ferramentas

`Python 3` · `Torch (HarbourMasters)` · `Lighthouse/Libultraship (fontes)` ·
`cmake` · `ninja` · `tmux` · `git`

---

## 📄 Licença / uso

Código e textos deste repositório: uso livre para fins pessoais e educacionais.
Marcas e jogos pertencem aos seus detentores (Rare, Nintendo, HarbourMasters e
tradutores originais). Nenhum asset de jogo é distribuído aqui.
