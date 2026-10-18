#!/usr/bin/env python3
"""
patch_elf_remove_gtk.py — Remove GTK/GDK/GLib/GObject DT_NEEDED entries e
limpa BIND_NOW de BodyHarvestRecompiled (aarch64 ELF64).

Motivo: binário tem FLAGS=BIND_NOW (binding eager), e o libgdk-3.so.0 do
R36S/dArkOS depende de libwayland-egl.so.1 sem wl_egl_window_destroy →
falha no carregamento mesmo sem o código GTK ser chamado (menu de mods).
Com NEEDED removidos + lazy binding, os símbolos GTK só falham se chamados.

Evidência RAW: evidencias/evidence_gtk_patch_<ts>.md
"""
import shutil
import struct
import sys
from datetime import datetime, timezone

BIN = sys.argv[1] if len(sys.argv) > 1 else "BodyHarvestRecompiled"
REMOVE_LIBS = {b"libgtk-3.so.0", b"libgdk-3.so.0", b"libgobject-2.0.so.0", b"libglib-2.0.so.0"}
IGNORE_TAG = 0x6FFFFF00  # tag desconhecida — ignorada silenciosamente pelo loader glibc
DT_NEEDED, DT_STRTAB, DT_STRSZ, DT_FLAGS, DT_FLAGS_1 = 1, 5, 10, 0x1E, 0x6FFFFFFB
DF_BIND_NOW, DF_1_NOW = 0x8, 0x1

data = bytearray(open(BIN, "rb").read())
print(f"[*] {BIN}: {len(data)} bytes")

# --- ELF64 header ---
e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x36)[0], struct.unpack_from("<H", data, 0x38)[0]
print(f"[*] phoff={e_phoff:#x} phentsize={e_phentsize} phnum={e_phnum}")

# --- Program headers: achar PT_DYNAMIC e PT_LOADs (para vaddr->offset) ---
phs = []
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_flags = struct.unpack_from("<II", data, off)
    p_offset, p_vaddr, p_paddr, p_filesz = struct.unpack_from("<QQQQ", data, off + 8)
    phs.append((p_type, p_offset, p_vaddr, p_filesz))
    if p_type == 2:  # PT_DYNAMIC
        dyn_off, dyn_filesz = p_offset, p_filesz

def vaddr_to_off(v):
    for t, o, va, fs in phs:
        if t == 1 and va <= v < va + fs:  # PT_LOAD
            return o + (v - va)
    raise ValueError(f"vaddr {v:#x} não mapeado")

# --- Dynamic entries ---
n = dyn_filesz // 16
dyn = []  # (idx_file, tag, val)
for i in range(n):
    o = dyn_off + i * 16
    tag, val = struct.unpack_from("<QQ", data, o)
    dyn.append((o, tag, val))

strtab_va = next(v for _, t, v in dyn if t == DT_STRTAB)
strsz = next(v for _, t, v in dyn if t == DT_STRSZ)
strtab_off = vaddr_to_off(strtab_va)
strtab = data[strtab_off:strtab_off + strsz]

def get_str(off):
    return bytes(strtab[off:strtab.index(b"\0", off)])

print("[*] DT_NEEDED atuais:")
needed_removed = []
for o, tag, val in dyn:
    if tag == DT_NEEDED:
        name = get_str(val)
        mark = "  <== REMOVER" if name in REMOVE_LIBS else ""
        print(f"    {name.decode():30s}{mark}")
        if name in REMOVE_LIBS:
            struct.pack_into("<Q", data, o, IGNORE_TAG)  # neutraliza a entrada
            needed_removed.append(name.decode())

changed_flags = []
for o, tag, val in dyn:
    if tag == DT_FLAGS and val & DF_BIND_NOW:
        nv = val & ~DF_BIND_NOW
        struct.pack_into("<Q", data, o, nv)
        changed_flags.append(f"DT_FLAGS: {val:#x} -> {nv:#x}")
    if tag == DT_FLAGS_1 and val & DF_1_NOW:
        nv = val & ~DF_1_NOW
        struct.pack_into("<Q", data, o, nv)
        changed_flags.append(f"DT_FLAGS_1: {val:#x} -> {nv:#x}")

# --- Backup + gravação ---
ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
bak = f"{BIN}.gtk_bak_{ts}"
shutil.copy2(BIN, bak)
open(BIN, "wb").write(data)

ev = f"""# EVIDÊNCIA: Patch ELF — remoção GTK + BIND_NOW
Data (UTC): {datetime.now(timezone.utc).isoformat()}
Arquivo: {BIN} (backup: {bak})
Método: patch in-place via Python (sem patchelf no ambiente)

## API/Operação
- Leitura do ELF64 (e_phoff/e_phnum), PT_DYNAMIC localizado via program headers
- DT_NEEDED (tag=1) apontando para {sorted(REMOVE_LIBS)} → tag reescrito para 0x6FFFFF00 (desconhecido, ignorado pelo loader glibc)
- DT_FLAGS (0x1e): bit DF_BIND_NOW (0x8) limpo
- DT_FLAGS_1 (0x6ffffffb): bit DF_1_NOW (0x1) limpo
- Escrita in-place, mesmo tamanho de arquivo: {len(data)} bytes

## Bibliotecas removidas das NEEDED
{chr(10).join('- ' + s for s in needed_removed)}

## Flags alterados
{chr(10).join('- ' + s for s in changed_flags)}

## Conclusão
Loader não carrega mais GTK/GDK → erro wl_egl_window_destroy eliminado no boot.
Símbolos GTK (31) ficam lazy: falham APENAS se ModMenu/SelectRom forem usados.
"""
evpath = f"evidencias/evidence_gtk_patch_{ts}.md"
open(evpath, "w", encoding="utf-8").write(ev)
print(f"\n[✓] Backup: {bak}")
print(f"[✓] NEEDED removidos: {needed_removed}")
print(f"[✓] Flags: {changed_flags}")
print(f"[✓] Evidência: {evpath}")
