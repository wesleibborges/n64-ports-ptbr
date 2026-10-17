#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adaptar_ports_br.py — Preparação dos ports N64Recomp para uso de traduções PT-BR no R36S (dArkOS).

O que este script faz:
  1. Converte a ROM traduzida de Banjo-Kazooie (base PAL, formato .n64) para .z64
     (formato exigido pelo Torch/Lighthouse) e a posiciona no diretório do port.
  2. Instala os mods de tradução PT-BR (Ship of Harkinian / OoT e 2Ship2Harkinian / MM)
     nas pastas mods/ dos respectivos ports.
  3. Valida hashes (MD5 dos mods, SHA-1 das ROMs) e grava evidências RAW em Markdown.

IMPORTANTE (limitação técnica dos ports, não contornável por este script):
  - Ship of Harkinian (Shipwright) e 2Ship2Harkinian validam o SHA-1 da ROM contra uma
    lista de hashes oficiais na geração do .o2r. ROMs modificadas (traduções) são
    rejeitadas. Portanto a tradução PT-BR é aplicada como MOD, sobre o .o2r gerado
    a partir de uma ROM original.
  - Lighthouse extrai romhacks apenas com base Banjo-Kazooie US v1.0. A tradução BR
    do BK é baseada na ROM PAL (NBKP), logo a extração como romhack não é suportada.
"""
import hashlib, os, glob, struct, zipfile, shutil, datetime, sys

PORTS = "/mnt/c/Users/wesle/dev/ports"
EVID_DIR = os.path.join(PORTS, "evidencias")
os.makedirs(EVID_DIR, exist_ok=True)

def now():
    return datetime.datetime.now().isoformat()

def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def n64_para_z64(data):
    """Converte .n64 (byte-swapped) para .z64 (big-endian) — troca pares de bytes (equivale a dd conv=swab)."""
    d = bytearray(len(data))
    d[0::4], d[1::4], d[2::4], d[3::4] = data[1::4], data[0::4], data[3::4], data[2::4]
    return bytes(d)

evidencia = []

# ----------------------------------------------------------------------------
# 1. Conversao BK .n64 -> .z64
# ----------------------------------------------------------------------------
src_bk = os.path.join(PORTS, "Banjo-Kazooie (BR)", "Banjo-Kazooie (BR) (www.romsportugues.com).n64")
dst_bk = os.path.join(PORTS, "Banjo-Kazooie (BR)", "lighthouse", "Banjo-Kazooie (BR).z64")

evidencia.append("=== EVIDENCIA: Conversao .n64 -> .z64 (Banjo-Kazooie BR) ===")
evidencia.append(f"Data: {now()}")
if os.path.exists(src_bk):
    with open(src_bk, "rb") as f:
        data = f.read()
    conv = n64_para_z64(data)
    ok_magic = conv[:4] == b"\x80\x37\x12\x40"
    if ok_magic:
        with open(dst_bk, "wb") as f:
            f.write(conv)
    evidencia.append(f"Operacao: conversao em memoria de '{os.path.basename(src_bk)}' ({len(data):,} bytes)")
    evidencia.append(f"Magic convertido: {conv[:4].hex()} (esperado 80371240) -> {'OK' if ok_magic else 'FALHA'}")
    evidencia.append(f"SHA-1 do arquivo convertido: {hashlib.sha1(conv).hexdigest().upper()}")
    evidencia.append(f"Gravado em: {dst_bk}" if ok_magic else "Arquivo convertido NAO gravado (magic invalido)")
    evidencia.append("Conclusao: ROM BR de BK e base PAL (game code NBKP, 16 MB); convertida para .z64 para o file picker do menu Romhacks/idiomas do Lighthouse.")
else:
    evidencia.append("AVISO: ROM BK nao encontrada.")
evidencia.append("")

# ----------------------------------------------------------------------------
# 2. Instalacao dos mods de traducao PT-BR
# ----------------------------------------------------------------------------
MODS = [
    ("traducaoptbr_soh.zip", "zeldaocarina/soh/mods", "569c20ae492395b96de88f87a0d8ec3c",
     "https://gamebanana.com/mods/473895 (PT-BR Translation Mod for Ship of Harkinian)"),
    ("traducao_ptbr_2s2h_r13.zip", "zeldamajora/soh2/mods", "9c12bb5f5fffd7c3d4282ff03071bc51",
     "https://gamebanana.com/mods/542278 (Brazilian Portuguese translation mod for 2Ship2Harkinian, R1.3)"),
]

evidencia.append("=== EVIDENCIA: Instalacao dos mods PT-BR ===")
evidencia.append(f"Data: {now()}")
for zip_name, mods_rel, md5_esperado, origem in MODS:
    zip_path = os.path.join(PORTS, "_downloads", zip_name)
    mods_dir = os.path.join(PORTS, mods_rel)
    evidencia.append(f"--- {zip_name} ---")
    if not os.path.exists(zip_path):
        evidencia.append("STATUS: zip NAO presente em _downloads/ (download pendente) — instalacao adiada.")
        continue
    md5_real = md5(zip_path)
    evidencia.append(f"MD5 real: {md5_real} | esperado: {md5_esperado} | {'CONFERE' if md5_real == md5_esperado else 'DIVERGE'}")
    evidencia.append(f"Origem: {origem}")
    if md5_real != md5_esperado:
        evidencia.append("STATUS: NAO instalado (integridade divergente).")
        continue
    os.makedirs(mods_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        evidencia.append(f"Conteudo do zip ({len(names)} entradas): {names[:12]}{' ...' if len(names) > 12 else ''}")
        z.extractall(mods_dir)
    evidencia.append(f"STATUS: extraido em {mods_dir}")
evidencia.append("")

# ----------------------------------------------------------------------------
# 3. Verificacao de compatibilidade das ROMs PT-BR com os hashes exigidos
# ----------------------------------------------------------------------------
HASHES_PORT = {
    "soh (oot.o2r)": [
        ("NTSC 1.0 (US)", "AD69C91157F6705E8AB06C79FE08AAD47BB57BA7"),
        ("NTSC 1.1 (US)", "D3ECB253776CD847A5AA63D859D8C89A2F37B364"),
        ("NTSC 1.2 (US)", "41B3BDC48D98C48529219919015A1AF22F5057C2"),
        ("PAL 1.0", "328A1F1BEBA30CE5E178F031662019EB32C5F3B5"),
        ("PAL 1.1", "CFBB98D392E4A9D39DA8285D10CBEF3974C2F012"),
    ],
    "soh2 (mm.o2r)": [
        ("N64 US", "D6133ACE5AFAA0882CF214CF88DABA39E266C078"),
        ("GC US", "9743AA026E9269B339EB0E3044CD5830A440C1FD"),
    ],
    "lighthouse (bk.o2r)": [
        ("USA Rev 0", "1FE1632098865F639E22C11B9A81EE8F29C75D7A"),
        ("USA Rev 1", "DED6EE166E740AD1BC810FD678A84B48E245AB80"),
        ("PAL", "BB359A75941DF74BF7290212C89FBC6E2C5601FE"),
        ("JP", "90726D7E7CD5BF6CDFD38F45C9ACBF4D45BD9FD8"),
    ],
}

evidencia.append("=== EVIDENCIA: Conferencia de compatibilidade das ROMs PT-BR com os ports ===")
evidencia.append(f"Data: {now()}")
romas = {
    "OoT PT-BR": os.path.join(PORTS, "zeldaocarina", "The legend of Zelda Ocarina of Time (em portugues).z64"),
    "MM PT-BR": os.path.join(PORTS, "zeldamajora", "The Legend of Zelda - Majora's Mask (E) [PT-BR].n64"),
    "BK BR": os.path.join(PORTS, "Banjo-Kazooie (BR)", "Banjo-Kazooie (BR) (www.romsportugues.com).n64"),
}
for rotulo, port in (("OoT PT-BR", "soh (oot.o2r)"), ("MM PT-BR", "soh2 (mm.o2r)"), ("BK BR", "lighthouse (bk.o2r)")):
    p = romas[rotulo]
    with open(p, "rb") as fh:
        raw = fh.read()
    z64 = n64_para_z64(raw) if raw[:4] != b"\x80\x37\x12\x40" else raw
    h = hashlib.sha1(z64).hexdigest().upper()
    aceitos = [n for n, hh in HASHES_PORT[port] if hh == h]
    evidencia.append(f"{rotulo}: SHA-1(.z64 equivalente) = {h}")
    evidencia.append(f"  Hash aceito por {port}? {'SIM -> ' + aceitos[0] if aceitos else 'NAO (ROM modificada; usar ROM original para gerar o .o2r)'}")
evidencia.append("")

out = os.path.join(EVID_DIR, "evidence_adaptacao_ports_br.md")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(evidencia) + "\n")
print("\n".join(evidencia))
print(f"\nEvidencia salva em: {out}")
