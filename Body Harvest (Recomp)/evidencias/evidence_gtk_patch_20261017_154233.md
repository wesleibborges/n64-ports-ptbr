# EVIDÊNCIA: Patch ELF — remoção GTK + BIND_NOW
Data (UTC): 2026-10-17T15:42:34.990236+00:00
Arquivo: BodyHarvestRecompiled (backup: BodyHarvestRecompiled.gtk_bak_20261017_154233)
Método: patch in-place via Python (sem patchelf no ambiente)

## API/Operação
- Leitura do ELF64 (e_phoff/e_phnum), PT_DYNAMIC localizado via program headers
- DT_NEEDED (tag=1) apontando para [b'libgdk-3.so.0', b'libglib-2.0.so.0', b'libgobject-2.0.so.0', b'libgtk-3.so.0'] → tag reescrito para 0x6FFFFF00 (desconhecido, ignorado pelo loader glibc)
- DT_FLAGS (0x1e): bit DF_BIND_NOW (0x8) limpo
- DT_FLAGS_1 (0x6ffffffb): bit DF_1_NOW (0x1) limpo
- Escrita in-place, mesmo tamanho de arquivo: 19771024 bytes

## Bibliotecas removidas das NEEDED
- libgtk-3.so.0
- libgdk-3.so.0
- libgobject-2.0.so.0
- libglib-2.0.so.0

## Flags alterados
- DT_FLAGS: 0x8 -> 0x0
- DT_FLAGS_1: 0x8000001 -> 0x8000000

## Conclusão
Loader não carrega mais GTK/GDK → erro wl_egl_window_destroy eliminado no boot.
Símbolos GTK (31) ficam lazy: falham APENAS se ModMenu/SelectRom forem usados.
