#!/usr/bin/env python3
"""Auditoria offline da stack Vulkan do R36S (rootfs dArkOS montada em /opt/r36s/rootfs).

Objetivo: descobrir, SEM o device, se existe ICD aarch64 que exponha VK_KHR_display
(o SDL2 KMSDRM usa exclusivamente vkCreateDisplayPlaneSurfaceKHR).

Metodo:
  1. resolver a cadeia de symlinks de libmali.so / libMali.so (aarch64) e libvulkan*.
  2. ler os bytes do binario resolvido e procurar as strings de extensao/entrypoint.
     (uma extensao implementada aparece como string literal no codigo do driver)
"""
import os
import re

BASE = "/opt/r36s/rootfs"
A64 = os.path.join(BASE, "usr/lib/aarch64-linux-gnu")

# strings decisivas
KEYS = [
    b"VK_KHR_display",
    b"vkCreateDisplayPlaneSurfaceKHR",
    b"vkGetPhysicalDeviceDisplayPropertiesKHR",
    b"vkGetDisplayPlaneCapabilitiesKHR",
    b"VK_KHR_wayland_surface",
    b"VK_KHR_xcb_surface",
    b"VK_KHR_xlib_surface",
    b"VK_EXT_headless_surface",
    b"VK_KHR_surface",
    b"VK_KHR_swapchain",
    b"VK_KHR_dynamic_rendering",
    b"VK_KHR_synchronization2",
    b"VK_KHR_copy_commands2",
    b"VK_EXT_descriptor_indexing",
    b"VK_KHR_timeline_semaphore",
    b"VK_KHR_present_id",
    b"VK_KHR_present_wait",
    b"VK_KHR_push_descriptor",
    b"VK_KHR_buffer_device_address",
    b"VK_KHR_shader_float_controls",
    b"VK_KHR_depth_stencil_resolve",
    b"VK_KHR_imageless_framebuffer",
    b"VK_KHR_separate_depth_stencil_layouts",
]


def resolve(path):
    """Resolve a cadeia completa de symlinks, retorna (final, cadeia)."""
    chain = []
    cur = path
    for _ in range(20):
        if not os.path.islink(cur):
            break
        tgt = os.readlink(cur)
        chain.append("%s -> %s" % (cur[len(BASE):], tgt))
        if not os.path.isabs(tgt):
            tgt = os.path.join(os.path.dirname(cur), tgt)
        cur = os.path.normpath(tgt)
        if not os.path.exists(cur):
            return None, chain + ["[QUEBRADO: %s]" % cur]
    return cur, chain


def scan(path, label):
    st = os.stat(path)
    with open(path, "rb") as fh:
        data = fh.read()
    print("  arquivo : %s (%d bytes)" % (path[len(BASE):], st.st_size))
    hits = {}
    for k in KEYS:
        hits[k.decode()] = data.count(k)
    # ATENCAO: presenca da string NAO prova suporte (tabelas de nomes de extensao do
    # Mesa listam TODAS as extensoes conhecidas). Serve apenas como indicio/vestigio.
    # A prova de suporte e a enumeracao real via loader (ver vkprobe).
    all_ext = sorted(set(re.findall(rb"VK_[A-Za-z0-9_]{4,60}", data)))
    print("  extensoes VK_* citadas no binario: %d" % len(all_ext))
    print("  (indicador fraco: nomes citados != extensoes suportadas)")
    for k in ["VK_KHR_display", "vkCreateDisplayPlaneSurfaceKHR",
              "vkGetPhysicalDeviceDisplayPropertiesKHR",
              "VK_EXT_headless_surface", "VK_KHR_wayland_surface",
              "VK_KHR_surface", "VK_KHR_swapchain"]:
        n = hits.get(k, 0)
        print("    %-45s %s (count=%d)" % (k, "citado" if n else "ausente", n))
    print("  --- todas as extensoes encontradas (amostra ordenada) ---")
    txt = [e.decode() for e in all_ext]
    for i in range(0, len(txt), 4):
        print("    " + "  ".join(txt[i:i + 4]))
    return hits


print("=" * 74)
print("A) Cadeia de symlinks dos Vulkan/Mali aarch64")
print("=" * 74)
targets = [
    os.path.join(A64, "libmali.so"),
    os.path.join(A64, "libMali.so"),
    os.path.join(A64, "libmali.so.1"),
    os.path.join(A64, "libvulkan.so.1"),
    os.path.join(A64, "libvulkan_lvp.so"),
    os.path.join(A64, "libvulkan_panfrost.so"),
    os.path.join(A64, "libgbm.so.1"),
    os.path.join(A64, "libEGL.so.1"),
]
for t in targets:
    if not os.path.lexists(t):
        print("  [ausente] %s" % t[len(BASE):])
        continue
    fin, chain = resolve(t)
    st = os.lstat(t)
    print("  %-45s size=%-10d" % (t[len(BASE):], st.st_size))
    for c in chain:
        print("      %s" % c)
    print("      FINAL: %s" % (fin[len(BASE):] if fin else "??"))

print()
print("=" * 74)
print("B) Lista completa de arquivos mali/vulkan/EGL/GLES/GBM no dir aarch64")
print("=" * 74)
if os.path.isdir(A64):
    for f in sorted(os.listdir(A64)):
        if re.search(r"mali|vulkan|EGL|GLES|gbm|Mali", f, re.I):
            fp = os.path.join(A64, f)
            isl = os.path.islink(fp)
            tgt = os.readlink(fp) if isl else ""
            sz = os.lstat(fp).st_size
            ok = "" if not isl else ("ok" if os.path.exists(fp) else "QUEBRADO")
            print("  %-45s %10d %s %s" % (f, sz, ("-> " + tgt) if isl else "", ok))

print()
print("=" * 74)
print("C) Varredura de strings nos binarios Vulkan (aarch64)")
print("=" * 74)
for cand in ["libvulkan_lvp.so", "libvulkan_panfrost.so"]:
    p = os.path.join(A64, cand)
    if os.path.exists(p):
        print("--- %s ---" % cand)
        scan(p, cand)
        print()
fin, _ = resolve(os.path.join(A64, "libmali.so"))
if fin and os.path.exists(fin):
    print("--- libmali.so (blob ARM) ---")
    scan(fin, "libmali")
else:
    print("--- libmali.so NAO resolvivel ---")