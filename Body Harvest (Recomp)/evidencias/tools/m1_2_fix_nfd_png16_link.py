#!/usr/bin/env python3
"""M1.2 - Ordena libpng16 no link do nfd (cadeia GTK/cairo).

Problema: o `pkg_check_modules(GTK3 gtk+-3.0)` do nfd exporta a cadeia GTK, mas
NAO libpng16 - exigida pela `libcairo.a` estatica (cairo-png.o: png_read_end).
Com `--as-needed` (default), uma DSO que aparece ANTES de quem a consome e
descartada, resultando em:

    ld: libcairo.a(cairo-png.o): undefined reference to symbol 'png_read_end@@PNG16_0'
    ld: libpng16.so: error adding symbols: DSO missing from command line

Correcao: adicionar libpng16 ao MESMO target, imediatamente APOS a linha do
`PRIVATE ${GTK3_LINK_LIBRARIES})`, preservando o estilo de fim de linha do arquivo.

Uso:
  python3 m1_2_fix_nfd_png16_link.py apply
  python3 m1_2_fix_nfd_png16_link.py revert
"""
import os
import shutil
import sys

F = '/root/bhrecomp/lib/rt64/src/contrib/nativefiledialog-extended/src/CMakeLists.txt'
BACKUP = '/root/bhrecomp/m1_2_gles/nfd_src_CMakeLists.bak'
MARKER = 'M1.2 (fix de ambiente'

BLOCK = """    # M1.2 (fix de ambiente, ver evidence_m1_2_gles_channel_20261018.md): o pkg-config do
    # gtk+-3.0 nao expoe libpng16, exigida pela libcairo.a estatica (cairo-png.o:
    # png_read_end). Precisa vir DEPOIS da cadeia GTK: com --as-needed (default) uma DSO
    # vista antes do consumidor e descartada -> "libpng16.so.16: DSO missing from command line".
    if (EXISTS "/root/sysroot64/usr/lib/aarch64-linux-gnu/libpng16.so")
        target_link_libraries(${TARGET_NAME} PRIVATE /root/sysroot64/usr/lib/aarch64-linux-gnu/libpng16.so)
    endif()
"""

ANCHOR = '      PRIVATE ${GTK3_LINK_LIBRARIES})'


def apply():
    with open(F, 'r', newline='') as fh:
        lines = fh.readlines()
    if any(MARKER in l for l in lines):
        print('ja aplicado')
        return
    idx = [i for i, l in enumerate(lines) if l.strip() == ANCHOR.strip()]
    if len(idx) != 1:
        raise SystemExit('ERRO: ancora GTK3_LINK_LIBRARIES nao unica (%d)' % len(idx))
    eol = '\r\n' if lines[idx[0]].endswith('\r\n') else '\n'
    blk = [l + eol for l in BLOCK.splitlines()]
    out = lines[:idx[0] + 1] + blk + lines[idx[0] + 1:]
    if not os.path.exists(BACKUP):
        shutil.copy2(F, BACKUP)
    with open(F, 'w', newline='') as fh:
        fh.writelines(out)
    print('ok: png16 adicionado apos a linha %d (eol=%r)' % (idx[0] + 1, eol))


def revert():
    shutil.copy2(BACKUP, F)
    print('revertido de ' + BACKUP)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'apply'
    if cmd == 'apply':
        apply()
    elif cmd == 'revert':
        revert()
    else:
        raise SystemExit(__doc__)