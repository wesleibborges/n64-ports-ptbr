=== EVIDENCIA: Fix do ucode de audio aspMain (RSPRecomp) ===
Data: 2026-10-16T17:05Z | Ambiente: WSL Ubuntu 22.04 (/root/bh, /root/n64recomp, /root/bhrecomp)

--- Diagnostico ---
Sintoma: RSPRecomp gerava 'goto L_004C ... L_1000' sem labels ('label used but not defined').
TOML antigo: text_size = 0x1E10 + extra_indirect_branch_targets RELATIVOS (0x004C..0x1000).

API Call: python3 leitura RAW da ROM (baserom.us.z64, sha1 bbb6666f5014a473747ee4145f036d9fb25d7348)
1) rspboot (ROM 0x2EA10, 0xD0 bytes) desmontado (rabbitizer):
   addi , , 0xFC0 / lw , 0x10() (t.ucode) /
   addi , , 0xF7F  <-- TAMANHO DE DMA HARDCODED (0xF80 bytes)
   addi , , 0x1080 (IMEM dest) -> mtc0 ... DMA
   Conclusao: apenas blob[0..0xF80] executa em IMEM 0x1080..0x1FFF (nao cruza 0x2000).
2) ucode_data (ROM 0x3FC60, 0x800 bytes, u64 D_8003F060_3FC60 em src.us/core/1050.c:322):
   halfwords BE @ blob 0x10..0x1F (DMEM 0x10): 1118 1470 11DC 1B38 1214 187C 1254 12D0
   = tabela de dispatch de comandos ('lh v0,0x10(v0); jr v0' @ IMEM 0x110C, index=(k0>>23)&0xFE)
   Blob 0x20 (DMEM 0x20) contem 0x1E24 (fora do IMEM executado) -> dados, nao tabela.
   Offsets 0x76/0xB8/0xC0/0x106 = coeficientes de resampler (dados).
3) jr sites com base em dados (IMEM 0x1FA8/0x2134/0x23C0/0x256C): caminhos mortos
   para o audio (heranca L3DEX) -> fallback de runtime do RSPRecomp (UnhandledJumpTarget).

--- Correcoes aplicadas ---
1) /root/bh/bh_aspMain.toml: text_size 0x1E10 -> 0x1018 (cobre 0x1080..0x2098 para
   labels das branches mortas de cauda 0x204C/0x208C); extra_indirect_branch_targets
   = 8 enderecos IMEM ABSOLUTOS da tabela DMEM 0x10.
2) Patch /root/n64recomp/RSPRecomp/src/rsp_recomp.cpp (3 marcados '// BH-patch'):
   mascarar instr_vram (labels), resume targets e return targets de jal com rsp_mem_mask
   (0x1FFF) para consistencia com o switch ((jump_target|0x1000)&0x1FFF). Backup: rsp_recomp.cpp.bak_orig.
3) /root/bhrecomp/src/main/main.cpp:388 set_program_id(std::u8string...)
4) /root/bhrecomp/src/main/recomp_data_api.cpp: copiado do modelo BanjoRecomp (727 linhas, 36 exports)
5) /root/bhrecomp/CMakeLists.txt: + recomp_data_api.cpp em SOURCES; ordem de link
   recompinput ANTES de recompui (resolucao de controls_page/force_update).

--- Verificacao ---
RSPRecomp: EXIT=0. Gotos sem label: 0 (comm de /tmp/g vs /tmp/l vazio).
aspMain.cpp novo: 79.5 KB (antes 158 KB com casos invalidos), compilado pelo ninja OK.
Link BodyHarvestRecompiled: OK (21.540.696 bytes, Oct 16 17:05).
Execucao: 'Failed to load controller mappings: Invalid RWops'/'Failed to create window:
Failed loading libvulkan.so.1' -> falha unica no estagio GPU/window (esperado em WSL headless);
init SDL/audio e carregamento do binario OK.
=== CONCLUSAO ===
aspMain recompilado corretamente; bloqueio removido. Proximo passo: ambiente com Vulkan/RT64
para o runtime de video.

=== EVIDENCIA (adicional): Smoke test Vulkan por software (lavapipe) — 2026-10-16 17:56 UTC ===
Objetivo: validar se o RT64 roda sobre um driver Vulkan 1.3 spec-compliant sem hardware
(relevante para panvk/Bifrost-G31 no R36S).
API Call: apt-get install mesa-vulkan-drivers (Mesa 23.2 lavapipe, Vulkan 1.3.255, conformance 1.3.1.1)
Execucao: ./BodyHarvestRecompiled (WSLg, X11 via XWayland)
Correcoes previas necessarias no port: bh::init_config() criado (modelo banjo init_config,
com create_general/graphics/controls/sound/mods tabs + finalize), set_program_id(bh::program_id),
assets copiados para o diretorio de execucao.
Resultado (log /tmp/bh_run.log):
- RmlUI/SVG inicializados; fontes carregadas;
- Janela 'Body Harvest: Recompiled' criada 1600x900 (xwininfo 0x600002) — RT64 renderizou via llvmpipe;
- screenshot: evidencias/bh_shot_lavapipe.png
CONCLUSAO: nenhuma extensao vendor-specific bloqueou a criacao de device no boot.
Viabilidade do panvk (G31, Vulkan 1.3 experimental) aumentada; proximo teste no hardware
do R36S com PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1.


## Build recovery 2026-10-16 20:03Z (RAW)
ninja BodyHarvestRecompiled => [1/2] main.cpp.o OK | [2/2] Linking BodyHarvestRecompiled OK (21570224 bytes)
Run => RmlUi fonts OK, SDL Video Driver: x11, Device: llvmpipe (LLVM 15.0.7) Vulkan 1.3.255, RT64 init OK.
Window: 640x480 (SDL_CreateWindow main.cpp:151). Process survived past timeout; killed via pkill regex trick.
Artifacts persisted: /mnt/c/e-core/{BodyHarvestRecompiled,bh_aspMain.toml,bh_aspMain_generated.cpp,bh_main.cpp,bh_run_test_640x480.log,bh_shot_640x480.png}
