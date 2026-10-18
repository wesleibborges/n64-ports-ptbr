# EVIDENCIA: boot aarch64 sob qemu — patch ELF v2 (GTK removido, BIND_NOW)

Data (UTC): 2026-10-17T16:30Z
Ambiente: WSL Ubuntu 22.04 (host x86_64), `qemu-aarch64-static 6.2.0`,
`gdb-multiarch`, sysroot guest `-L /usr/aarch64-linux-gnu`
Arquivos: `/mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/`
Conta AWS: nao aplicavel (sem operacao AWS nesta sessao)

---

## 1. Diagnostico do SIGSEGV (antes da correcao)

### 1.1 LD_DEBUG=bindings (`_ldbind.log`)

```
calling init: /mnt/c/Users/wesle/dev/ports/Body Harvest (Recomp)/libs/libgtk_shim.so
binding file ./BodyHarvestRecompiled [0] to /lib/libc.so.6 [0]: normal symbol `__libc_start_main'
qemu: uncaught target signal 11 (Segmentation fault) - core dumped
```

### 1.2 gdb-multiarch via gdbstub (`qemu-aarch64-static -g 12345`)

```
Program received signal SIGSEGV, Segmentation fault.
0x0000005502af40b4 in ?? () from /usr/aarch64-linux-gnu/lib/ld-linux-aarch64.so.1
#0  0x0000005502af40b4 in ?? () from /usr/aarch64-linux-gnu/lib/ld-linux-aarch64.so.1
#1  0x0000005502af614c in ?? () from /usr/aarch64-linux-gnu/lib/ld-linux-aarch64.so.1
#2  0x000000550008d230 in _start ()
```

Conclusao: crash na resolucao LAZY de `__libc_start_main` dentro do ld.so.

### 1.3 Layout RELRO (binario pristine `gtk_bak_20261017_154233`)

```
LOAD   0x100ad70 0x000000000101ad70 0x02bcf0 0x045118 RW  0x10000
GNU_RELRO 0x100ad70 0x000000000101ad70 0x01b290 0x01b290 R
[19] .got   PROGBITS 0000000001033ac8 1023ac8 002530 08 WA
DT_PLTGOT 0x1033ac8
```

RELRO = 0x101ad70..0x1036000 -> cobre `.data.rel.ro` + `.got` (inclui `.got.plt`).
Com BIND_NOW removido, o resolver grava no GOT read-only => SIGSEGV.

### 1.4 Artefatos do `patchelf` no binario v1

`readelf -d` do binario v1 nao tinha `DT_FLAGS`, `FLAGS_1`, `VERSYM`, `VERNEED`,
`VERNEEDNUM` nem `RELACOUNT`; entrada `NULL` final com valor `0x8`
(`.dynamic` reescrito por `patchelf --add-needed`).

---

## 2. Correcao aplicada

```
$ python3 _patch_elf_v2.py BodyHarvestRecompiled.gtk_bak_20261017_154233 BodyHarvestRecompiled
[*] BodyHarvestRecompiled.gtk_bak_20261017_154233: 19771024 bytes | PT_DYNAMIC off=0x1023838 size=0x290
[*] NEEDED antes: ['libSDL2-2.0.so.0', 'libfreetype.so.6', 'libgtk-3.so.0', 'libgdk-3.so.0',
    'libgobject-2.0.so.0', 'libglib-2.0.so.0', 'libm.so.6', 'libgcc_s.so.1', 'libc.so.6',
    'ld-linux-aarch64.so.1']
[*] Backup do destino anterior: BodyHarvestRecompiled.broken_patchelf_bak_20261017_162606
[*] NEEDED depois: ['libSDL2-2.0.so.0', 'libfreetype.so.6', 'libgtkshim.so', 'libm.so.6',
    'libgcc_s.so.1', 'libc.so.6', 'ld-linux-aarch64.so.1']
[*] Renomeadas: ['libgtk-3.so.0 -> libgtkshim.so (DT_NEEDED mantida)']
[*] Neutralizadas: ['libgdk-3.so.0', 'libgobject-2.0.so.0', 'libglib-2.0.so.0']
[*] Versionamento removido (tags ['0x6ffffffe', '0x6fffffff', '0x6ffffff0'])
[*] Flags: ['DT_FLAGS=0x8', 'DT_FLAGS_1=0x8000001', 'DT_RELACOUNT presente']
[+] BodyHarvestRecompiled gravado (19771024 bytes, tamanho inalterado)
```

`readelf -dW BodyHarvestRecompiled | grep -E 'NEEDED|FLAGS|VERSYM|VERNEED|NULL'`

```
 (NEEDED)  Shared library: [libSDL2-2.0.so.0]
 (NEEDED)  Shared library: [libfreetype.so.6]
 (NEEDED)  Shared library: [libgtkshim.so]
 (NEEDED)  Shared library: [libm.so.6]
 (NEEDED)  Shared library: [libgcc_s.so.1]
 (NEEDED)  Shared library: [libc.so.6]
 (NEEDED)  Shared library: [ld-linux-aarch64.so.1]
 (FLAGS)   BIND_NOW
 (FLAGS_1) Flags: NOW PIE
 (NULL)    0x0
```

---

## 3. Cobertura de simbolos

```
$ comm -23 _und.txt _shim.txt | grep -E '^(gtk_|gdk_|g_)'   # _und.txt=411 UND, _shim.txt=39 FUNC
(vazio)
```

39/39 simbolos `gtk_/gdk_/g_` UND definidos por `libs/libgtkshim.so`
(`readelf -hW`: ELF64 / AArch64; SONAME `libgtkshim.so`; NEEDED `libc.so.6`).

---

## 4. Execucao final (`_run_v2_final.log`)

```
$ LD_LIBRARY_PATH='<port>/libs' SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  timeout 15 qemu-aarch64-static -L /usr/aarch64-linux-gnu ./BodyHarvestRecompiled
Failed to create window: Vulkan support is either not configured in SDL or not available
in current SDL video driver (dummy) or platform
Exiting with exit status '1'. Function exit_error, at file /root/bhrecomp/src/main/main.cpp:61
EXIT=0
```

Sem SIGSEGV, sem `undefined symbol`: loader, relocacao e shims corretos; o processo
chega ao `main()` e so falha na criacao da janela Vulkan (driver `dummy`).

## 5. Hashes

```
dbc386ba918d898a01038d7ff943768a  BodyHarvestRecompiled
9f22de1ea44a68f46bde075aab232616  libs/libgtkshim.so
```

## Conclusao

Binario aarch64 consistente para deploy no R36S: sem NEEDED de GTK/GDK/GLib,
BIND_NOW preservado (obrigatorio pelo RELRO que cobre o GOT) e todos os simbolos
GTK/GLib resolvidos por `libgtkshim.so`.
