# Evidência RAW — publicação do Body Harvest (Recomp) no repositório de engenharia

- **Data/hora:** 2026-10-18 (UTC-3)
- **Repo local:** `C:\Users\wesle\dev\ports` (WSL: `/mnt/c/Users/wesle/dev/ports`)
- **Remoto:** `git@github.com:wesleibborges/n64-ports-ptbr.git` — branch `master`
- **Objetivo:** publicar o trabalho do backend OpenGL ES do Body Harvest (M1–M5) no repo de
  engenharia, respeitando a política "sem conteúdo protegido"
  (`.clinerules/ports-recompilacao-jogos.md`, regras 1 e 2).

## 1. Pré-checagem (saída RAW)

| Verificação | Comando | Saída |
|---|---|---|
| Remote | `git remote -v` | `origin git@github.com:wesleibborges/n64-ports-ptbr.git` |
| Estado inicial | `git log --oneline -1` | `344972a docs: aponta para o verificador de ROM online` (= `origin/master`) |
| Ignore da pasta | `git check-ignore -v 'Body Harvest (Recomp)'` | `.gitignore:26:Body Harvest (Recomp)/` |
| Tamanho da pasta | `du -sh 'Body Harvest (Recomp)'` | `147M` |
| Autenticação | `ssh -T git@github.com` | `Permission denied (publickey)` (chave padrão do WSL) |
| Autenticação | `ssh -i /root/.ssh/id_ed25519_github -T git@github.com` | `Hi wesleibborges! You've successfully authenticated...` |
| Repo dedicado | `git ls-remote .../body-harvest-ptbr.git` | `ERROR: Repository not found` |

## 2. Política aplicada (o que **não** foi publicado)

| Excluído | Motivo | Tamanho |
|---|---|---|
| `Body Harvest (USA)/` (`.z64`) | ROM — conteúdo protegido | 12,6 MB |
| `BodyHarvestRecompiled*` (8 arquivos) | binários de jogo + backups | ~157 MB |
| `recomp/bh.us.elf`, `recomp/bh_recomp_out.tar.gz` | derivados de ROM | 18,7 MB |
| `assets/` | fontes/SVGs de terceiros (IP Banjo) | 1,3 MB |
| `libs/` (`libSDL2`, `libgtkshim`) | binários de terceiros | 1,9 MB |
| `glesprobe`, `vkprobe` | binários de probe (fonte fica em `evidencias/tools/`) | 31 KB |
| `diag_results/` | dump do device (contém serial/UUID/MAC) | 244 KB |
| `*.log` (topo), `log.txt`, `graphics.json.auto/.gles` | estado de execução | ~1,2 MB |
| `.clinerules/` | configuração local do Cline | — |

Publicado: **243 arquivos** de engenharia (plano, evidências RAW M1–M5, ESSL real de
produção, ferramentas, scripts, configs, `recomp/n64patch/` e `shaders/`).

## 3. Verificação do conjunto antes do commit

```
$ git add --dry-run 'Body Harvest (Recomp)' | wc -l
243

$ git add --dry-run 'Body Harvest (Recomp)' | sed 's/^add //' | tr -d '\047' \
    | xargs -d '\n' stat -c '%s %n' | sort -rn | head -3
262267 Body Harvest (Recomp)/evidencias/m1_3_stage2/essl/RasterPSDynamicMS.essl
260962 Body Harvest (Recomp)/evidencias/m3_gles_probe/shader_cases/prod_asis.frag.essl
260962 Body Harvest (Recomp)/evidencias/gles_device_probe_pkg/shader_cases/prod_asis.frag.essl
```

**Conclusão:** maior blob = **262 KB** (ESSL real) — nenhum arquivo `.z64`, `.elf` de jogo
ou `.so` entrou. Únicos binários publicados: SPIR-V de UI (`shaders/*.spv`, 1,3–4,5 KB) e os
probes aarch64 do pacote de device (~250 KB, com fonte em `evidencias/tools/`).

## 4. Commits e push (saída RAW)

```
$ git log --oneline -4
fce650b docs: indexa o caso de estudo Body Harvest (backend GLES/R36S) no README e corrige LEIA-ME
4ece692 docs(port): plano, evidencias RAW M1-M5 e ferramentas do backend GLES do Body Harvest (R36S)
a936ae2 chore(ignore): publica somente engenharia do Body Harvest; .clinerules fica local
344972a docs: aponta para o verificador de ROM online

$ git show --stat --oneline (resumo)
a936ae2  .gitignore | 20 +++++++++++++++++++-   (19 insertions, 1 deletion)
4ece692  243 files changed, 149605 insertions(+)
fce650b  README.md 26 +  |  LEIA-ME_TRADUCOES_PT-BR.md 12 +++++++-----  (33 insertions, 5 deletions)

$ git push origin master
To github.com:wesleibborges/n64-ports-ptbr.git
   344972a..fce650b  master -> master

$ git ls-remote origin refs/heads/master
fce650b4b75b0f72730f20bf61b8a896b7ec7339	refs/heads/master

$ git status -sb
## master...origin/master
```

## 5. Limpeza de artefato acidental

O editor de arquivos do Cline resolveu o caminho `/mnt/c/...` como `C:\mnt\c\...` e criou um
arquivo perdido de 36 B em `C:\mnt\c\Users\wesle\dev\ports\.gitignore`
(`/mnt/c/mnt/c/Users/wesle/dev/ports/.gitignore`). O stray foi **removido** (`rm -f`) e o
`.gitignore` real editado com caminho Windows. Observação: `C:\mnt\c\` já continha lixo de
16/10 (`e-core/bh_main.cpp`, cópias de `_PROGRESS.md`, `_patch_elf_remove_gtk.py`) não
relacionado a esta operação — preservado.

## 6. Conclusão

- **FATO VERIFICADO:** o `master` remoto aponta para `fce650b4b75b0f72730f20bf61b8a896b7ec7339`,
  idêntico ao HEAD local; worktree limpo (exceto `pocket-native-0.1.1/` + `.zip`, untracked
  pré-existentes, deixados fora por decisão do usuário).
- Publicados **apenas** código, scripts, documentação e evidências, conforme a política do repo.
- `LEIA-ME_TRADUCOES_PT-BR.md` §4.4 ("sem port") foi corrigido; README ganhou a seção do
  trabalho em andamento.
- **Pendência inalterada:** run no device (M3) — 3 ✅ / 3 ⏳; a medição de
  `GL_MAX_TEXTURE_IMAGE_UNITS` no Mali-G31 continua necessária.