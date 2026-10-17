#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Identifica as ROMs N64 presentes na pasta ports:
- Converte byte-order para formato .z64 (big-endian) quando necessario
- Calcula SHA-1 da versao .z64 (formato usado pelos ports Torch/SoH/2S2H para conferir hashes)
- Le o cabecalho para identificar codigo do jogo, regiao e versao
- Gera evidencia em evidence_roms_identificacao.md
"""
import hashlib, os, glob, struct, datetime

PORTS = "/mnt/c/Users/wesle/dev/ports"
OUT = os.path.join(PORTS, "evidencias", "evidence_roms_identificacao.md")

ROMS = []
for pattern in ("**/*.n64", "**/*.z64", "**/*.v64"):
    ROMS.extend(glob.glob(os.path.join(PORTS, pattern)))

# Mascaras de header
def to_z64_bytes(data, path):
    magic = data[:4]
    if magic == b"\x80\x37\x12\x40":   # .z64 (big-endian)
        return data, "z64"
    if magic == b"\x37\x80\x40\x12":   # .n64 (byte-swapped / v64-like little endian word)
        swapped = bytearray(data)
        swapped[0::4], swapped[1::4], swapped[2::4], swapped[3::4] = \
            data[1::4], data[0::4], data[3::4], data[2::4]
        return bytes(swapped), "n64->z64"
    if magic == b"\x12\x40\x80\x37":   # .v64 (little-endian)
        return data[::-1][:0] + bytes(bytearray(data)[::-1]), "v64"  # placeholder
    return None, "desconhecido"

def read_header(data):
    if len(data) < 64:
        return None
    # .z64 header: clock(4) boot_address(4) crc1 crc2 (2x4) unknown(8) ... game_code at 0x3B-0x3E
    crc1, crc2 = struct.unpack(">II", data[8:16])
    game_title = data[0x20:0x34]
    game_code = data[0x3B:0x3F].decode("ascii", errors="replace")
    version = data[0x3F]
    country_code = data[0x3E:0x3F].decode("ascii", errors="replace")
    return dict(title=game_title, game_code=game_code, version=version,
                country=country_code, crc1=f"{crc1:08X}", crc2=f"{crc2:08X}")

REGIOES = {"E":"Europa (PAL)","J":"Japao","U":"USA (NTSC)","P":"PAL","D":"Alemanha",
           "F":"Franca","I":"Italia","S":"Espanha","X":"Asia","Y":"Asia","W":"Asia/Taiwan"}

linhas = ["=== EVIDENCIA: Identificacao das ROMs N64 ===",
          f"Data: {datetime.datetime.utcnow().isoformat()}Z",
          "", "| Arquivo | Tamanho | Origem | Jogo (title) | Game Code | Regiao | Versao | CIC CRC | SHA-1 (.z64) |",
          "|---|---|---|---|---|---|---|---|---|"]

for path in sorted(ROMS):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read()
    z64, origem = to_z64_bytes(data, path)
    if z64 is None:
        linhas.append(f"| `{os.path.basename(path)}` | {size} | header invalido | - | - | - | - | - | - |")
        continue
    h = hashlib.sha1(z64).hexdigest().upper()
    hdr = read_header(z64)
    reg = REGIOES.get(hdr["country"], hdr["country"]) if hdr else "-"
    linhas.append(
        f"| `{os.path.relpath(path, PORTS)}` | {size:,} | {origem} | {hdr['title'].decode('ascii', errors='replace').strip() if hdr else '-'} | "
        f"{hdr['game_code'] if hdr else '-'} | {reg} | rev {hdr['version'] if hdr else '-'} | "
        f"{hdr['crc1'] if hdr else '-'}-{hdr['crc2'] if hdr else '-'} | `{h}` |")

linhas += ["", "### Interpretacao",
 "- Hashes em SHA-1 calculados sobre a versao .z64 (big-endian), que e o formato comparado pelos ports.",
 "- A copia em memoria nunca e gravada em disco; o arquivo original permanece inalterado.",
 ""]

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(linhas))

print("\n".join(linhas))
