# EVIDENCIA: patch ELF v2 (GTK in-place, BIND_NOW preservado)

Data (UTC): 2026-10-17T16:26:07.706987+00:00
Origem: `BodyHarvestRecompiled.gtk_bak_20261017_154233` -> Destino: `BodyHarvestRecompiled` (backup do destino anterior: `BodyHarvestRecompiled.broken_patchelf_bak_20261017_162606`)
Operacao: edicao in-place de .dynamic/.dynstr via Python struct (SEM patchelf)

## Diagnostico que motivou a v2

| Evidencia | Resultado |
| :--- | :--- |
| `_ldbind.log` (LD_DEBUG=bindings) | ultimo evento: `binding ... to /lib/libc.so.6: __libc_start_main` seguido de SIGSEGV |
| `_qtrace.log` + gdb-multiarch | `_start -> 0x5502af614c -> 0x5502af40b4`, ambos em `ld-linux-aarch64.so.1` |
| `readelf -d` v1 (pos-patchelf) | sem DT_FLAGS/FLAGS_1/VERSYM/VERNEED/RELACOUNT; entrada NULL final com valor 0x8 |
| `readelf -l` | `GNU_RELRO 0x101ad70 (+0x1b290)` cobre `.got` (0x1033ac8) -> GOT read-only |

Conclusao: sem BIND_NOW, o `_dl_runtime_resolve` grava no GOT ja protegido pelo
RELRO => SIGSEGV antes de qualquer codigo do jogo.

## Alteracoes aplicadas

- DT_NEEDED renomeada: ['libgtk-3.so.0 -> libgtkshim.so (DT_NEEDED mantida)']
- DT_NEEDED neutralizadas (0x6FFFFF00): ['libgdk-3.so.0', 'libgobject-2.0.so.0', 'libglib-2.0.so.0']
- Tags de versionamento neutralizadas (0x6FFFFF01): ['0x6ffffffe', '0x6fffffff', '0x6ffffff0']
- NEEDED final: ['libSDL2-2.0.so.0', 'libfreetype.so.6', 'libgtkshim.so', 'libm.so.6', 'libgcc_s.so.1', 'libc.so.6', 'ld-linux-aarch64.so.1']
- Flags preservados: ['DT_FLAGS=0x8', 'DT_FLAGS_1=0x8000001', 'DT_RELACOUNT presente']

## Verificacoes automaticas (asserts)

- `libgtkshim.so` presente nas NEEDED: OK
- nenhuma NEEDED de GTK/GDK/GLib: OK
- DT_VERSYM/DT_VERNEED/DT_VERNEEDNUM ausentes: OK
- DT_FLAGS com BIND_NOW: OK
- numero de entradas .dynamic inalterado: OK (41)
- tamanho do arquivo inalterado: OK (19771024 bytes)
