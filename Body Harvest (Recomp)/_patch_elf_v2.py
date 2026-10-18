#!/usr/bin/env python3
"""_patch_elf_v2.py - Remocao do GTK in-place (SEM patchelf), mantendo BIND_NOW.

Diagnostico (17/10/2026):
  * Binario linkado com -z now: PT_GNU_RELRO cobre .data.rel.ro + .got
    (RELRO 0x101ad70..0x1036000; .got=0x1033ac8; DT_PLTGOT=0x1033ac8).
  * A v1 do patch limpava DT_FLAGS/FLAGS_1 (BIND_NOW) => glibc fez binding
    lazy e o _dl_runtime_resolve gravou em GOT read-only => SIGSEGV dentro do
    ld-linux-aarch64.so.1 (gdb: _start -> _dl_runtime_resolve). Ver _ldbind.log.
  * `patchelf --add-needed` reescreveu o .dynamic e DERRUBOU DT_VERSYM,
    DT_VERNEED, DT_VERNEEDNUM, DT_RELACOUNT, DT_FLAGS e FLAGS_1.

Correcao:
  1. DT_NEEDED "libgtk-3.so.0" -> "libgtkshim.so" (13 chars + NUL: in-place).
  2. DT_NEEDED gdk/gobject/glib -> tag 0x6FFFFF00 (desconhecida, ignorada).
  3. DT_VERSYM/DT_VERNEED/DT_VERNEEDNUM -> tag 0x6FFFFF01 (sem version check).
  4. DT_FLAGS (BIND_NOW) e DT_FLAGS_1 (NOW|PIE) PRESERVADOS => binding eager,
     GOT preenchido ANTES do mprotect do RELRO.

Uso: python3 _patch_elf_v2.py <origem_pristine> <destino>
"""
import shutil
import struct
import sys
from datetime import datetime, timezone

SRC = sys.argv[1] if len(sys.argv) > 1 else "BodyHarvestRecompiled.gtk_bak_20261017_154233"
DST = sys.argv[2] if len(sys.argv) > 2 else "BodyHarvestRecompiled"

DT_NEEDED = 1
DT_STRTAB, DT_STRSZ = 5, 10
DT_FLAGS, DT_FLAGS_1 = 0x1E, 0x6FFFFFFB
DT_VERSYM, DT_VERNEED, DT_VERNEEDNUM = 0x6FFFFFF0, 0x6FFFFFFE, 0x6FFFFFFF
DT_RELACOUNT = 0x6FFFFFF9
IGNORE_TAG = 0x6FFFFF00
IGNORE_VER_TAG = 0x6FFFFF01

RENAME = {b"libgtk-3.so.0": b"libgtkshim.so"}
DROP = {b"libgdk-3.so.0", b"libgobject-2.0.so.0", b"libglib-2.0.so.0"}

data = bytearray(open(SRC, "rb").read())
log = []


def note(msg):
    log.append(msg)
    print(msg)


assert data[:4] == b"\x7fELF" and data[4] == 2, "nao e' ELF64"
assert struct.unpack_from("<H", data, 0x12)[0] == 0xB7, "nao e' aarch64"
e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
e_phnum = struct.unpack_from("<H", data, 0x38)[0]

loads, dyn = [], None
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from("<I", data, off)[0]
    p_offset, p_vaddr, _p_paddr, p_filesz = struct.unpack_from("<QQQQ", data, off + 8)
    if p_type == 1:
        loads.append((p_vaddr, p_offset, p_filesz))
    elif p_type == 2:
        dyn = (p_offset, p_filesz)
assert dyn, "PT_DYNAMIC nao encontrado"
note(f"[*] {SRC}: {len(data)} bytes | PT_DYNAMIC off={dyn[0]:#x} size={dyn[1]:#x}")


def vaddr_to_off(v):
    for va, o, fs in loads:
        if va <= v < va + fs:
            return o + (v - va)
    raise ValueError(f"vaddr {v:#x} nao mapeado em PT_LOAD")


entries = []
for i in range(dyn[1] // 16):
    o = dyn[0] + i * 16
    tag, val = struct.unpack_from("<QQ", data, o)
    entries.append((o, tag, val))

strtab_va = next(v for _, t, v in entries if t == DT_STRTAB)
strsz = next(v for _, t, v in entries if t == DT_STRSZ)
strtab_off = vaddr_to_off(strtab_va)


def get_str(off):
    end = data.index(b"\0", strtab_off + off)
    return bytes(data[strtab_off + off:end])


before_needed = [get_str(v).decode() for _, t, v in entries if t == DT_NEEDED]
note(f"[*] NEEDED antes: {before_needed}")

# ---------- 1/2. NEEDED ----------
renamed, dropped = [], []
for o, tag, val in entries:
    if tag != DT_NEEDED:
        continue
    name = get_str(val)
    if name in RENAME:
        new = RENAME[name]
        assert len(new) == len(name), "renomeacao exigiria mover o .dynstr"
        data[strtab_off + val:strtab_off + val + len(new) + 1] = new + b"\0"
        renamed.append(f"{name.decode()} -> {new.decode()} (DT_NEEDED mantida)")
    elif name in DROP:
        struct.pack_into("<Q", data, o, IGNORE_TAG)
        dropped.append(name.decode())

# ---------- 3. versionamento ----------
ver_tags = []
for o, tag, val in entries:
    if tag in (DT_VERSYM, DT_VERNEED, DT_VERNEEDNUM):
        struct.pack_into("<Q", data, o, IGNORE_VER_TAG)
        ver_tags.append(hex(tag))

# ---------- 4. flags preservados ----------
flags_now = []
for _, tag, val in entries:
    if tag == DT_FLAGS:
        flags_now.append(f"DT_FLAGS={val:#x}")
        assert val & 0x8, "DT_FLAGS sem BIND_NOW - inconsistente com RELRO"
    if tag == DT_FLAGS_1:
        flags_now.append(f"DT_FLAGS_1={val:#x}")
for _, tag, _ in entries:
    if tag == DT_RELACOUNT:
        flags_now.append("DT_RELACOUNT presente")

# ---------- verificacao pos-edicao ----------
after = []
for i in range(dyn[1] // 16):
    tag, val = struct.unpack_from("<QQ", data, dyn[0] + i * 16)
    after.append((tag, val))
after_needed = [get_str(v).decode() for t, v in after if t == DT_NEEDED]

assert "libgtkshim.so" in after_needed, "libgtkshim.so nao entrou nas NEEDED"
assert not any(x in after_needed for x in
               ("libgtk-3.so.0", "libgdk-3.so.0",
                "libgobject-2.0.so.0", "libglib-2.0.so.0")), \
    "sobrou NEEDED de GTK/GLib"
assert not any(t in (DT_VERSYM, DT_VERNEED, DT_VERNEEDNUM) for t, _ in after), \
    "versionamento ainda presente"
assert any(t == DT_FLAGS and v & 0x8 for t, v in after), "BIND_NOW perdido"
assert len(after) == len(entries), "numero de entradas .dynamic mudou"

# ---------- backup + escrita ----------
ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
bak = f"{DST}.broken_patchelf_bak_{ts}"
shutil.copy2(DST, bak)
open(DST, "wb").write(data)
note(f"[*] Backup do destino anterior: {bak}")
note(f"[*] NEEDED depois: {after_needed}")
note(f"[*] Renomeadas: {renamed}")
note(f"[*] Neutralizadas: {dropped}")
note(f"[*] Versionamento removido (tags {ver_tags})")
note(f"[*] Flags: {flags_now}")
note(f"[+] {DST} gravado ({len(data)} bytes, tamanho inalterado)")

ev = f"""# EVIDENCIA: patch ELF v2 (GTK in-place, BIND_NOW preservado)

Data (UTC): {datetime.now(timezone.utc).isoformat()}
Origem: `{SRC}` -> Destino: `{DST}` (backup do destino anterior: `{bak}`)
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

- DT_NEEDED renomeada: {renamed}
- DT_NEEDED neutralizadas (0x6FFFFF00): {dropped}
- Tags de versionamento neutralizadas (0x6FFFFF01): {ver_tags}
- NEEDED final: {after_needed}
- Flags preservados: {flags_now}

## Verificacoes automaticas (asserts)

- `libgtkshim.so` presente nas NEEDED: OK
- nenhuma NEEDED de GTK/GDK/GLib: OK
- DT_VERSYM/DT_VERNEED/DT_VERNEEDNUM ausentes: OK
- DT_FLAGS com BIND_NOW: OK
- numero de entradas .dynamic inalterado: OK ({len(after)})
- tamanho do arquivo inalterado: OK ({len(data)} bytes)
"""
evpath = f"evidencias/evidence_gtk_patch_v2_{ts}.md"
open(evpath, "w", encoding="utf-8").write(ev)
note(f"[+] Evidencia: {evpath}")
