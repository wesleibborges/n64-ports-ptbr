# Evidência — Desbloqueio do link aarch64 + M1.3 (estágio 1) + auditoria de libs do device

- Data: 2026-10-18 (sessão ~13:00-14:00 -03)
- Host: WSL Ubuntu · árvore `/root/bhrecomp` · sysroot `/root/sysroot64`
- Device: `dArkOSen-r36` (Debian GNU/Linux 13 trixie, kernel 4.4.189 aarch64)
- Ferramentas: cmake 4.4.4, ninja, aarch64-linux-gnu-gcc 11, `spirv-cross`, `glslangValidator`,
  `spirv-val`, `re-spirv-cli` (x86_64, `/root/bhrecomp/build-cmake/re-spirv-cli`)
- Regra aplicada: só é afirmado o que tem saída RAW correspondente (§0-§5).

## §0 Resumo

| Item | Resultado (fato verificado) |
|---|---|
| Link CMake/ninja do binário aarch64 | ✅ **RESOLVIDO**. Causa-raiz: **cache obsoleto** `pkgcfg_lib_GTK3_*` (escolhia `.a` do sysroot) + falta de `--allow-shlib-undefined` para DSOs transitivos. **Zero edição em fonte.** |
| Binário gerado pelo ninja | `[241/242] Linking CXX executable`, depois `ninja: no work to do`; ELF aarch64 PIE, **19.869.608 B**, md5 `b35315d93a86378c007999b99bb6cf5c` |
| Canal GLES (M1.2) no binário | **31 símbolos `*BlobGLSLES`** distintos no ELF (ex.: `RSPModifyCSBlobGLSLES` 1.952 B, `DebugPSBlobGLSLES` 15.468 B) |
| GTK no device | ✅ **EXISTE** (`libgtk-3.so.0`, `libgdk-3.so.0`, `libglib-2.0.so.0.8400.4`, `libgobject-2.0.so.0`) → o `libgtkshim.so` do binário anterior era **desnecessário** |
| M1.3 estágio 1 (aceite do plano, `< 50 KB`) | ✅ **28.986-29.033 B** (≈24× menor que 704.897 B), ESSL 3.20 válido no `glslangValidator`; `re-spirv` 0,03-15,7 ms + `spirv-cross` 27-209 ms (host) |

## §1 Bloqueio de link — causa-raiz e correção (RAW)

### §1.1 Sintoma (log `m1_2_gles/ninja_build8.log`, sessão M1.2)

Erros em cascata, sem relação com a mudança do M1.2:
`libcairo.a(cairo-png.o)` → `png_read_end` "DSO missing from command line"; `libglib-2.0.a(gregex.c.o)`
→ `pcre_*`; `libgcrypt.so.20` → `gpgrt_*@GPG_ERROR_1.0`; `libsystemd.so.0` → `LZ4_*`.

### §1.2 Diagnóstico 1 — o pkg-config escolheu `.a` em vez de `.so`

`build-aarch64/CMakeCache.txt` **ANTES** (linhas 792-825):

```
pkgcfg_lib_GTK3_atk-1.0:FILEPATH=/root/sysroot64/usr/lib/aarch64-linux-gnu/libatk-1.0.so
pkgcfg_lib_GTK3_cairo:FILEPATH=/root/sysroot64/usr/lib/aarch64-linux-gnu/libcairo.a
pkgcfg_lib_GTK3_cairo-gobject:FILEPATH=.../libcairo-gobject.a
pkgcfg_lib_GTK3_gdk-3:FILEPATH=.../libgdk-3.so
pkgcfg_lib_GTK3_gdk_pixbuf-2.0:FILEPATH=.../libgdk_pixbuf-2.0.so
pkgcfg_lib_GTK3_gio-2.0:FILEPATH=.../libgio-2.0.a
pkgcfg_lib_GTK3_glib-2.0:FILEPATH=.../libglib-2.0.a
pkgcfg_lib_GTK3_gobject-2.0:FILEPATH=.../libgobject-2.0.a
pkgcfg_lib_GTK3_gtk-3:FILEPATH=.../libgtk-3.so
pkgcfg_lib_GTK3_harfbuzz:FILEPATH=.../libharfbuzz.a
pkgcfg_lib_GTK3_pango-1.0:FILEPATH=.../libpango-1.0.so
pkgcfg_lib_GTK3_pangocairo-1.0:FILEPATH=.../libpangocairo-1.0.so
```

Padrão medido: **todos os 6 que viraram `.a` têm `.so` ao lado** (`libcairo.so`, `libglib-2.0.so`,
`libgio-2.0.so`, `libgobject-2.0.so`, `libcairo-gobject.so`, `libharfbuzz.so`), e **todos os que
viraram `.so` não têm `.a`** (`libgtk-3.a`, `libgdk-3.a`, `libpango-1.0.a`, `libatk-1.0.a` não existem).
→ regra observada: *preferiu `.a` quando existia*.

Hipótese "sufixo `.a` preferido por configuração" **refutada** com evidência:

```
grep -rn 'FIND_LIBRARY_SUFFIXES' /root/bhrecomp/CMakeLists.txt /root/bhrecomp/Toolchain-aarch64.cmake   → vazio
grep -rn 'FIND_LIBRARY_SUFFIXES' /root/bhrecomp --include=*.cmake --include=CMakeLists.txt              → vazio
grep -n  'FIND_LIBRARY'          /root/bhrecomp/build-aarch64/CMakeCache.txt                            → vazio
```

Hipótese "sysroot incompleto na época" **refutada** por mtime: `libcairo.so` = 2026-03-30,
`libglib-2.0.so` = 2026-09-08, ambos **muito anteriores** ao CMakeCache (2026-10-18 12:21:13).
→ sobra a explicação correta: as entradas `pkgcfg_lib_*` são **cache persistente** e a escolha `.a`
foi congelada num configure antigo (quando os `.so` realmente não existiam no sysroot).

### §1.3 Correção 1 — descartar o cache do pkg-config (config, sem tocar em fonte)

```bash
cmake -U 'pkgcfg_lib_GTK3_*' -S /root/bhrecomp -B /root/bhrecomp/build-aarch64
```

`CMakeCache.txt` **DEPOIS** — 12/12 resolvidos em `.so`:

```
pkgcfg_lib_GTK3_atk-1.0 = libatk-1.0.so            pkgcfg_lib_GTK3_glib-2.0 = libglib-2.0.so
pkgcfg_lib_GTK3_cairo = libcairo.so                pkgcfg_lib_GTK3_gobject-2.0 = libgobject-2.0.so
pkgcfg_lib_GTK3_cairo-gobject = libcairo-gobject.so pkgcfg_lib_GTK3_gtk-3 = libgtk-3.so
pkgcfg_lib_GTK3_gdk-3 = libgdk-3.so                pkgcfg_lib_GTK3_harfbuzz = libharfbuzz.so
pkgcfg_lib_GTK3_gdk_pixbuf-2.0 = libgdk_pixbuf-2.0.so pkgcfg_lib_GTK3_pango-1.0 = libpango-1.0.so
pkgcfg_lib_GTK3_gio-2.0 = libgio-2.0.so            pkgcfg_lib_GTK3_pangocairo-1.0 = libpangocairo-1.0.so
```

Diff **exato** dos tokens do sysroot na linha de link (arquivos `linklibs_before.txt` → `linklibs_gtk_fixed.txt`):

```
8c8
< .../libharfbuzz.a          --->  .../libharfbuzz.so
10,11c10,11
< .../libcairo-gobject.a     --->  .../libcairo-gobject.so
< .../libcairo.a             --->  .../libcairo.so
13,15c13,15
< .../libgio-2.0.a           --->  .../libgio-2.0.so
< .../libgobject-2.0.a       --->  .../libgobject-2.0.so
< .../libglib-2.0.a          --->  .../libglib-2.0.so
```

Ou seja: **6 substituições `.a` → `.so`** (os outros 6 da cadeia já eram `.so` porque não têm `.a`
no sysroot). O link final passa a ter a cadeia GTK inteira como DSO, sem nenhum `.a` de terceiro.

Não-regressão de fonte (md5 antes/depois idênticos — nada foi editado):

```
212d74fdfff97b2eb3029470befb5c30  /root/bhrecomp/CMakeLists.txt
9dfb65cd9bd76bad806daaaf3f56db1b  /root/bhrecomp/lib/rt64/CMakeLists.txt
6b3e956b0f5c03a3519796c5736638c1  /root/bhrecomp/lib/rt64/src/contrib/nativefiledialog-extended/src/CMakeLists.txt
```

### §1.4 Diagnóstico 2 — undefined em DSOs transitivos

Depois da correção 1 a cascata de **arquivos estáticos** desapareceu, mas restou:

```
libgcrypt.so.20:  undefined reference to `gpgrt_*@GPG_ERROR_1.0'   (24 símbolos)
libsystemd.so.0:  undefined reference to `LZ4_decompress_safe' / `LZ4_versionNumber' / ...
libglib-2.0.so:   undefined reference to `pcre_free' / `pcre_config' / `pcre_fullinfo' / ...
```

Fato medido: no sysroot **não existem** `libgpg-error*` e `liblz4*`
(`ls /root/sysroot64/usr/lib/aarch64-linux-gnu/ | grep -E 'gpg|lz4'` → vazio; existe só `libpcre.so`).
Esses símbolos pertencem a dependências **transitivas de DSO** e são resolvidos pelo `ld.so` no device;
o erro é de *link-time* por causa do default `--no-allow-shlib-undefined` do GNU ld.

### §1.5 Correção 2 — `--allow-shlib-undefined` persistido no toolchain

`Toolchain-aarch64.cmake` (5 linhas acrescentadas, md5 `cde8ca7cf15d654e99f971f0252ed159` →
`ed6366ba398e87bf74311af6a85a425d`):

```cmake
# Cross-link contra sysroot parcial do device: DSOs transitivos (libgcrypt->gpg-error,
# libsystemd->lz4, libglib->pcre) tem simbolos ausentes no sysroot; sao resolvidos em
# runtime pelo ld.so do device. Sem esta flag o ld aborta com "undefined reference to
# gpg_*/LZ4_*/pcre_*" mesmo com a DSO presente na linha de link.
set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--allow-shlib-undefined")
```

### §1.6 Resultado do link (RAW)

```
[240/242] Linking CXX static library lib/RecompFrontend/recompui/librecompui.a
[241/242] Linking CXX executable BodyHarvestRecompiled
grep -ci 'error' /root/bhrecomp/m1_3_gles/link_fix_run.log   → 0
ninja BodyHarvestRecompiled                                   → ninja: no work to do.
-rwxr-xr-x 19869608  /root/bhrecomp/build-aarch64/BodyHarvestRecompiled
md5 b35315d93a86378c007999b99bb6cf5c
ELF 64-bit LSB pie executable, ARM aarch64, dynamically linked,
    interpreter /lib/ld-linux-aarch64.so.1, BuildID 82c95fc09f26bcfddd820180b5ca2234395dbe21, not stripped
NEEDED: libSDL2-2.0.so.0, libfreetype.so.6, libgtk-3.so.0, libgdk-3.so.0, libgobject-2.0.so.0,
        libglib-2.0.so.0, libm.so.6, libgcc_s.so.1, libc.so.6, ld-linux-aarch64.so.1
RUNPATH: /root/sysroot64/usr/lib/aarch64-linux-gnu      ← pendência (§4, item 3)
```

**Reprodutibilidade (verificada no fim da sessão)**: depois de gerar o perfil alternativo com
`-DNFD_PORTAL=ON` (md5 `ee808314…`) e **voltar** para `-DNFD_PORTAL=OFF`, o rebuild reproduziu
**exatamente** o mesmo binário do perfil GTK: md5 `b35315d93a86378c007999b99bb6cf5c`,
19.869.608 B, e `ninja BodyHarvestRecompiled` → `ninja: no work to do.`

Canal GLES materializado (M1.2 dentro de um binário linkado):

```
readelf -sW ... | grep -oE '[A-Za-z0-9_]*BlobGLSLES' | sort -u | wc -l   → 31
amostra: RSPModifyCSBlobGLSLES(1952 B), FbChangesDrawDepthPSBlobGLSLES(1560 B),
         HistogramClearCSBlobGLSLES(632 B), DebugPSBlobGLSLES(15468 B)
```

Artefatos preservados no repo: `BodyHarvestRecompiled.m1_2_cmake_gtk_20261018` (md5 idêntico).
Backups/logs RAW: `/root/bhrecomp/m1_3_gles/` (`link_cmd_raw.txt`, `link_cmd_after.txt`,
`linklibs_before.txt`, `linklibs_gtk_fixed.txt`, `linklibs_portal.txt`, `link_fix_run.log`,
`reconf_unset.log`, `flip_back_gtk.log`, `portal_build.log`,
`md5_cmakelists_before.txt`, `md5_toolchain_before/after.txt`).

## §2 Auditoria de libs do DEVICE — o `libgtkshim.so` era desnecessário

Fontes RAW: (a) rootfs do device extraído de `darkos.img` em `/opt/r36s/rootfs`;
(b) `diag_results/diag.txt` e `diag_results/diag2.txt`, **produzidos rodando no próprio device**.

Device: `Linux dArkOSen-r36 4.4.189 aarch64 GNU/Linux`, `PRETTY_NAME="Debian GNU/Linux 13 (trixie)"`.

```
ls /opt/r36s/rootfs/usr/lib/aarch64-linux-gnu/ | grep -E '^lib(gtk-3|glib-2|gobject-2|gdk-3|dbus-1|freetype|stdc)'
libdbus-1.so.3.38.3        libglib-2.0.so.0.8400.4     libgtk-3.so.0 -> libgtk-3.so.0.2417.32
libfreetype.so.6.20.2      libgobject-2.0.so.0.8400.4  libstdc++.so.6.0.33
libgdk-3.so.0
```

`diag2.txt` (dpkg no device):

```
ii  libgtk-3-0t64:arm64    3.24.49-3          GTK graphical user interface library
ii  libglib2.0-0t64:arm64  2.84.4-3~deb13u5   GLib library of C routines
ii  libsdl2-2.0-0:arm64    2.32.4+dfsg-1      Simple DirectMedia Layer
ii  libegl1:arm64          1.7.0-1+b2         Vendor neutral GL dispatch library -- EGL support
ii  libegl-mesa0:arm64     25.0.7-2+deb13u1   free implementation of the EGL API -- Mesa vendor library
ii  libfreetype6:arm64     2.13.3+dfsg-1+deb13u1
```

**Conclusão (fato verificado)**: a lista `NEEDED` do binário (§1.6) está **integralmente satisfeita**
no device. Logo o `libgtkshim.so` presente no binário anterior (NEEDED `libgtkshim.so`, ver sessão
2026-10-17) era **consequência do link quebrado**, não de ausência de GTK3 no device.

> **Armadilha de método registrada**: um primeiro `ls … | grep -E 'libgtk-3|libglib-2.0.so|…' | head -20`
> deu a impressão de "GTK não existe no device" — era **falso negativo** (o `head` cortou a listagem
> antes de `libg*`, que vem depois de `libSDL2*` na ordem alfabética). Conclusão corrigida com
> `grep -E '^lib(gtk-3|glib-2|…)'` sem truncamento. Mesma classe de erro do §1 do M1.1 (regex por nome).

### §2.1 Risco novo: ABI/distro do sysroot ≠ distro do device

| | sysroot (`/root/sysroot64`) | device (dArkOSen) |
|---|---|---|
| distro | Ubuntu 22.04 (debs via `apt-get download`, `_gtk_sysroot.sh`) | Debian 13 trixie |
| glib | 2.72.4 (`libglib-2.0.so.0.7200.4`) | 2.84.4 |
| GTK3 | 3.24.x | 3.24.49 |
| SDL2 (headers) | 2.30.3 | 2.32.4 |

GTK 3.24.x é ABI-estável dentro da série e o GLib mantém as versões antigas de símbolo, então o
binário atual funciona; mas a recomendação de engenharia é **regerar o sysroot a partir do rootfs do
device** (`/opt/r36s/rootfs`, já disponível), o que também elimina a necessidade de
`--allow-shlib-undefined` (verificar `libgpg-error`/`liblz4` no rootfs do device antes).

### §2.2 Perfil alternativo medido: `-DNFD_PORTAL=ON` (xdg-desktop-portal/dbus)

Comandos:

```bash
cmake -DNFD_PORTAL=ON -S /root/bhrecomp -B /root/bhrecomp/build-aarch64
ninja BodyHarvestRecompiled
[220/221] Linking CXX executable BodyHarvestRecompiled      → ninja_rc=0
-rwxr-xr-x 19921696  build-aarch64/BodyHarvestRecompiled
```

Efeito na linha de link (RAW `linklibs_portal.txt`): **a cadeia GTK/cairo/pango/harfbuzz/atk/gdk
desaparece** e sobra apenas `libdbus-1.so` (além de `libfreetype.so` e `libSDL2.so`):

```
/root/sysroot64/usr/lib/aarch64-linux-gnu/libfreetype.so
/root/sysroot64/usr/lib/aarch64-linux-gnu/libSDL2.so
/root/sysroot64/usr/lib/aarch64-linux-gnu/libdbus-1.so
```

Perfil mantido como **opcional** (não canônico): o device tem `libdbus-1.so.3` (§2), mas o backend
portal depende do serviço `xdg-desktop-portal` em D-Bus — que um R36S em KMSDRM normalmente não tem.
O perfil canônico permanece **GTK (default upstream)**, pois as libs existem no device e o uso do GTK
é limitado à função de diálogo (`nfd_gtk.cpp`), que só falha se for de fato chamada sem display.

## §3 M1.3 — estágio 1: aceite medido (SPIR-V especializado → ESSL 3.20)

Script (não altera fontes; só consome artefatos de build):
`evidencias/tools/m1_3_stage1_specialize.sh` → executado como
`bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/evidencias/tools/m1_3_stage1_specialize.sh"`.

Pipeline medido: `*.hlsl.glsl_es.spv` (SPIR-V GLES do M1.2, em `build-aarch64/src/shaders/`)
→ `re-spirv-cli` (especializa 5 spec constants, ids 0..4 = `otherMode.L`, `otherMode.H`,
`colorCombiner.L`, `colorCombiner.H`, `flags.value`; valores do próprio CLI:
3356565624 / 1584128 / 4229999620 / 4279211007 / 747626510)
→ `spirv-cross --es --version 320` → `glslangValidator -S <estágio>`.

Saída RAW (`m1_3_gles/stage1_results.txt`):

```
SHADER                             SPV_IN  SPV_OPT ESSL_ORIG  ESSL_OPT  RESP_ms  XCO_ms    VALID
RasterPSSpecConstant               284228    28132    703529     28986 15.711000     209       ok
RasterPSSpecConstantFlat           284376    28180    703588     29030 1.578000      170       ok
RasterPSSpecConstantMS             285160    28184    704827     28986 5.997000       71       ok
RasterPSSpecConstantFlatMS         285308    28232    704897     29033 1.501000      175       ok
RasterVSSpecConstant                 4676     2876      2793      1283 0.031000       27       ok
RasterVSSpecConstantFlat             4748     2924      2874      1330 0.032000       70       ok
```

`RESP_ms` = tempo de otimização reportado pelo próprio `re-spirv-cli`; `XCO_ms` = wall clock de
`spirv-cross`; `VALID` = `rc` de `spirv-cross` + saída do `glslangValidator` (logs de 0 byte = sem
diagnóstico). Todos os 6 arquivos `.glslang.log` e `.xc.err` estão vazios.

### §3.1 Conclusões (com números)

1. **Aceite do plano (`< 50 KB`) atingido com folga**: ESSL especializado = **28.986-29.033 B**;
   o não-especializado equivalente tem **703.529-704.897 B** → **fator ≈ 24×**.
   Mecanismo medido: `re-spirv` derruba o SPIR-V de 284 KB para ~28 KB (eliminação dos ramos dos
   5 spec constants) **antes** da conversão.
2. **Custo no host** (Ryzen 7 3700U): `re-spirv` 0,03-15,7 ms + `spirv-cross` 27-209 ms ⇒
   **≈ 0,03-0,22 s por especialização**. Extrapolando para o Mali-G31/RK3326 (10-20× mais lento em
   single-thread) ⇒ **≈ 0,3-4 s por shader especializado**.
   ⇒ **Requisito registrado para M2/M6: a especialização + conversão precisa de cache em disco**
   (o RT64 só tem cache de shader para DXIL hoje). Sem cache, cada permutação nova de pipeline paga
   esse custo em runtime no device.
3. **Validade GLSL ES 3.20 confirmada** nos 6 (`glslangValidator -S vert|frag` rc=0), sem nova
   sanitização além da do M1.1 — o output convertido já é entregável ao driver.
4. **Confirma o desvio de desenho do M1.2** (embutir o SPIR-V GLES e não o texto ESSL): com o texto
   ESSL não haveria como aplicar `re-spirv`, e o Mali teria de compilar **704 KB** de ubershader.
5. **Escopo do que falta no M1.3 (estágio 2)** — não é mais medição, é código:
   `spirv-cross` **ainda não é linkado** (existe só como executável de build, `spirv_cross_msl` e
   `find_program(SPIRV_CROSS_EXECUTABLE)`); `lib/rt64/CMakeLists.txt:508` linka apenas `re-spirv`.
   Falta: (a) `add_subdirectory(src/contrib/spirv-cross)` + link do target C (`spirv-cross-c`) — **viabilidade confirmada**: o
   vendorizado traz o `CMakeLists.txt` upstream completo (targets `spirv-cross-core`/`-glsl`/`-c`,
   com `SPIRV_CROSS_CLI`/`SPIRV_CROSS_ENABLE_TESTS` para não construir CLI/testes) — no
   binário; (b) casos `RenderShaderFormat::GLSL_ES` nos switch de runtime —
   `rt64_shader_library.cpp:705/741/776`, `rt64_raster_shader.cpp:101/140/418/425/432/499/505`
   (`RasterShader`, `RasterShaderUber`, shaders de post-blend) e `rt64_raster_shader_cache.cpp:109`
   (inicialização do cache do `re-spirv`); (c) medir o custo **no device** (M5).
6. Reprodução: `evidencias/tools/m1_3_stage1_specialize.sh` + artefatos de `m1_3_gles/stage1/`
   (6 `.opt.spv`, 6 `.opt.glsl`, `.respv.log`, `.glslang.log`, `.xc.err`).
   **Persistidos no repo** (regra `evidence-collection`): `evidencias/stage1_results_20261018.txt`
   (tabela RAW), `evidencias/m1_3_stage1/` (3 `.opt.glsl` representativos + 6 `.respv.log`) e
   `evidencias/linklibs_{before,gtk_fixed,portal}.txt` (linhas de link dos 3 estados).

## §4 Limitações do runner (para as próximas sessões)

1. **`run_commands` remove `$var` do comando antes de executar.** Sintomas observados nesta sessão:
   `mkdir -p ""` (script gerado por heredoc ficou com variáveis vazias) e `echo "=== ninja rc=$rc2 ==="`
   → `=== ninja rc= ===` (o `rc2=$?` foi escrito, mas a expansão foi apagada antes de rodar).
   Prova RAW: `cat -A m1_3_gles/stage1_specialize.sh | head -6` → `mkdir -p ""`.
   **Contorno adotado**: escrever scripts com o editor no repo (`evidencias/tools/*.sh`) e executar
   com `bash "/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/…/script.sh"`.
2. **A sessão de shell morre em ~30 s** → todo build longo com `setsid nohup <script> > log 2>&1 < /dev/null &`
   + polling com `tail`.
3. **`head`/truncamento em listagem grande gera falso negativo** (§2) — usar grep ancorado.
4. `cmake` re-executa os `add_custom_command` dos shaders a cada reconfiguração → recompila ~174
   objetos de blob (221-242 alvos) mesmo para mudanças puramente de link flags. Orçar ~3-5 min.

## §5 Handoff

- Estado da árvore `/root/bhrecomp`: `CMakeCache.txt` com `-U 'pkgcfg_lib_GTK3_*'` aplicado;
  `Toolchain-aarch64.cmake` com `set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--allow-shlib-undefined")`;
  **nenhuma fonte modificada** (md5 dos 3 CMakeLists em §1.3). Perfil canônico `NFD_PORTAL=OFF`.
- Artefatos no repo do port:
  `BodyHarvestRecompiled.m1_2_cmake_gtk_20261018` (md5 `b35315d93a86378c007999b99bb6cf5c`, 19.869.608 B)
  e `BodyHarvestRecompiled.m1_3_cmake_portal_20261018` (md5 `ee808314fdf7e45c0469c76df208452d`,
  19.921.696 B, NEEDED sem GTK).
- Pendências registradas: (1) **RUNPATH** aponta para `/root/sysroot64/usr/lib/aarch64-linux-gnu`
  (inócuo no device — diretório inexistente é ignorado pelo `ld.so`; o launcher usa `libs/`), decidir
  em M5 se vale `CMAKE_SKIP_RPATH`; (2) sysroot de distro ≠ device (§2.1); (3) `libgtkshim.so`
  aposentado — o launcher/binário não precisa dele.
- Próximo passo (M1.3 estágio 2): implementar (a)+(b) de §3.1-5 e rodar o aceite final de M1.3;
  depois M2 (`plume_gles`).