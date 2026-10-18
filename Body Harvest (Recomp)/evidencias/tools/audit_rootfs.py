#!/usr/bin/env python3
"""Auditoria da rootfs do dArkOS (device R36S) montada read-only em /opt/r36s/rootfs.
Foco: stack grafica (Vulkan ICDs, libmali, libgbm, libdrm, SDL2, modulos DRM).
Nenhum acesso a rede; somente leitura do filesystem montado.
"""
import os
import glob
import subprocess

BASE = "/opt/r36s/rootfs"
LIBDIRS = [
    "usr/lib/aarch64-linux-gnu",
    "lib/aarch64-linux-gnu",
    "usr/lib",
    "lib",
    "usr/lib/arm-linux-gnueabihf",
]
PATTERNS = ["libvulkan*", "libmali*", "libMali*", "libgbm*", "libdrm*",
            "libSDL2*", "libEGL*", "libGLESv2*", "libwayland*", "libxcb*"]

print("=" * 70)
print("1) /etc/os-release do DEVICE")
print("=" * 70)
for p in ["etc/os-release", "etc/lsb-release", "etc/armbian-release"]:
    fp = os.path.join(BASE, p)
    if os.path.exists(fp):
        print("--- %s" % p)
        try:
            print(open(fp, errors="replace").read().strip())
        except Exception as e:
            print("ERRO: %s" % e)

print()
print("=" * 70)
print("2) ICDs Vulkan (JSON) encontrados no DEVICE")
print("=" * 70)
icd_hits = []
for root in ["usr/share/vulkan", "etc/vulkan", "usr/local/share/vulkan"]:
    d = os.path.join(BASE, root)
    if os.path.isdir(d):
        for dp, dn, fn in os.walk(d):
            for f in fn:
                icd_hits.append(os.path.join(dp, f))
if not icd_hits:
    print("NENHUM arquivo em /usr/share/vulkan, /etc/vulkan ou /usr/local/share/vulkan")
for f in sorted(icd_hits):
    rel = f[len(BASE):]
    st = os.lstat(f)
    print("--- %s  (size=%d, symlink=%s)" % (rel, st.st_size, os.path.islink(f)))
    if os.path.islink(f):
        print("    -> %s" % os.readlink(f))
    if f.endswith(".json"):
        try:
            print(open(f, errors="replace").read())
        except Exception as e:
            print("    ERRO ao ler: %s" % e)

print()
print("=" * 70)
print("3) Bibliotecas graficas por diretorio do DEVICE")
print("=" * 70)
for ld in LIBDIRS:
    d = os.path.join(BASE, ld)
    if not os.path.isdir(d):
        continue
    files = []
    for pat in PATTERNS:
        files.extend(glob.glob(os.path.join(d, pat)))
    if not files:
        continue
    print("---- %s ----" % ld)
    for f in sorted(set(files)):
        st = os.lstat(f)
        extra = ""
        if os.path.islink(f):
            extra = " -> %s" % os.readlink(f)
        print("  %-40s %10d%s" % (os.path.basename(f), st.st_size, extra))

print()
print("=" * 70)
print("4) Busca global por libmali / libvulkan em TODO o filesystem do DEVICE")
print("=" * 70)
found = []
for pat in ["libmali*", "libvulkan*", "libliftoff*", "libv3dv*", "libvulkan_lvp*"]:
    for f in glob.glob(os.path.join(BASE, "**", pat), recursive=True):
        found.append(f)
for f in sorted(set(found)):
    rel = f[len(BASE):]
    isl = os.path.islink(f)
    tgt = os.readlink(f) if isl else ""
    exists = os.path.exists(f) if isl else True
    try:
        sz = os.lstat(f).st_size
    except Exception:
        sz = -1
    print("  %-70s size=%-9d link=%s tgt=%s ok=%s" % (rel, sz, isl, tgt, exists))
if not found:
    print("  NADA encontrado (nem libmali, nem libvulkan)")

print()
print("=" * 70)
print("5) Modulos de kernel (DRM/GPU) no DEVICE")
print("=" * 70)
kd = os.path.join(BASE, "lib/modules")
if os.path.isdir(kd):
    print("  diretorios de versao: %s" % sorted(os.listdir(kd)))
    for f in sorted(glob.glob(os.path.join(kd, "**", "*.ko*"), recursive=True)):
        b = os.path.basename(f)
        if any(k in b.lower() for k in ["mali", "drm", "gpu", "rockchip"]):
            print("  %s" % f[len(BASE):])
else:
    print("  /lib/modules NAO existe no device (kernel monolitico)")

print()
print("=" * 70)
print("6) Deteccao de links quebrados no diretorio de libs aarch64")
print("=" * 70)
d = os.path.join(BASE, "usr/lib/aarch64-linux-gnu")
if os.path.isdir(d):
    for f in sorted(os.listdir(d)):
        fp = os.path.join(d, f)
        if os.path.islink(fp) and not os.path.exists(fp):
            print("  QUEBRADO: %s -> %s" % (f, os.readlink(fp)))

print()
print("=" * 70)
print("7) /dev/dri e drm nodes (esperado ausente em imagem offline)")
print("=" * 70)
print("  entries em %s/dev/dri: %s" % (BASE, os.path.exists(os.path.join(BASE, "dev/dri"))))