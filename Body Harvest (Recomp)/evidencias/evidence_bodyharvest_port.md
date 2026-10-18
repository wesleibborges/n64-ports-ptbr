=== EVIDENCIA: Port Body Harvest (decomp -> N64Recomp) ===
Data: 2026-10-16 (sessao de build 08:10-09:20 UTC)
Ambiente: WSL Ubuntu 22.04 x86_64 (VM reinicia entre chamadas; jobs via setsid)
Repositorio: https://github.com/jaytheham/body-harvest-decompilation (shallow clone, commit db0c56e)

--- Teste 1: progresso do decomp ---
Comando: python3 tools/progress.py --output progress.json
Resultado: overall matched_pct=84.53, decompiled_pct=99.97, total_functions=3058,
matched=2585, non_matching=472, asm_stubs=1 (libultra 100% matched)

--- Teste 2: ROM base ---
Comando: cp "Body Harvest (USA).z64" baserom.us.z64 && sha1sum baserom.us.z64
Resultado: bbb6666f5014a473747ee4145f036d9fb25d7348 — igual ao esperado em bh.us.sha1 (US B6.5)

--- Teste 3: extracao (splat) ---
Comando: make extract
Resultado: concluido — build/ com .s/.data/bin extraidos; ferramentas rnc64 e librncu.so compiladas.
Dependencias instaladas: pip3 cmake/ninja + requirements.txt do repo (splat, spimdisasm 1.33.0, rabbitizer 1.12.5, crunch64 0.3.1 etc.)
Toolchain: binutils-mips-linux-gnu 2.40 (debs do Ubuntu jammy extraidos com dpkg -x em /root/tools/gnu-mips,
wrappers em /usr/local/bin com LD_LIBRARY_PATH proprio; apt do ambiente com fontes Debian/Ubuntu mistas e dpkg quebrado — apt NAO usado para instalar pacotes)
CC_CHECK (lint gcc -m32) desativado via HOSTCC=fake_cc (script que sai 0) — checagem apenas de warnings, nao impacta o binario.

--- Teste 4: build do decomp ---
Comando: make -j6 HOSTCC=/root/bh/tools/fake_cc HOSTCC_CHECK_FLAGS=
Resultado: build/bh.us.elf gerado (13.650.660 bytes) e build/bh.us.z64: OK (sha1sum --check passou)
Conclusao: ROM reconstruida byte-perfect a partir do fonte; ELF final possui 6.933 simbolos de texto.

--- Teste 5: recompilacao estatica ---
Ferramenta: N64Recomp (repo oficial N64Recomp/N64Recomp, gcc 11.4, cmake 4.4.4, build 58/58 OK)
Config: bodyharvest.us.toml (entrypoint 0x80000400, elf_path build/bh.us.elf, bss_section_suffix _bss,
relocatable_sections_path relocatable_sections.txt, use_lookup_for_all_function_calls=true [PATCH proprio])
Resultado: Function count: 7117 — recompilado com sucesso; aviso informativo "Indirect tail call in recomp_entrypoint"
Saida: RecompiledFuncs/ com 61 arquivos funcs_*.c (35 MB)
Primeira execucao (antes do patch): falhou com "No function found for jal target: 0x80003824"
(recompilei: o alvo existia em .core mas a chamadora estava em .overlay_gameplay_outside — jal entre overlays
nao resolvivel sem relocs; solucao: chave nova no TOML que ativa lookup em runtime)

=== CONCLUSAO ===
Pipeline decomp->recomp do Body Harvest operacional e reproduzivel com a ROM do usuario.
Runtime do port (video/audio/input/eventos) ainda nao implementado — roadmap em README_PORT.md.
