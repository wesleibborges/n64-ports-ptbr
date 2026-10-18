#!/usr/bin/env python3
"""M2/sessao 2 -- aplica o incremento de stage 2 em plume_gles.{h,cpp}.

Deterministico e idempotente-ish: aborta se o header ja' tiver o membro `source`
ou se o .cpp ja' contiver o marcador de sessao 2.
"""
import os
import sys

PLUME_DIR = "/root/bhrecomp/lib/rt64/src/contrib/plume"
STAGED_DIR = "/root/bhrecomp/m2_gles/staged"

HEADER = os.path.join(PLUME_DIR, "plume_gles.h")
SOURCE = os.path.join(PLUME_DIR, "plume_gles.cpp")
INCREMENT = os.path.join(STAGED_DIR, "plume_gles_s2_inc.inc")

S2_MARKER = "M2 -- sessao 2: recursos, command list, swapchain e criacao no device."

HEADER_ANCHOR = "        RenderShaderFormat format = RenderShaderFormat::UNKNOWN;\n"
HEADER_ADDITION = (
    "        // Texto ESSL do shader (ver plume_gles.cpp, sessao 2). O GLES 3.2 nao aceita\n"
    "        // binario de shader: o que chega por createShader(...GLSL_ES) e' a FONTE, e o\n"
    "        // objeto GL (glCreateShader) e' criado no PIPELINE, que e' quem conhece o\n"
    "        // ESTAGIO (vertex/fragment/compute).\n"
    "        std::string source;\n"
)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def patch_header():
    header = read_text(HEADER)

    if "std::string source;" in header:
        print("[apply_s2] header: membro `source` ja' presente, nada a fazer")
        return False

    if header.count(HEADER_ANCHOR) != 1:
        print("[apply_s2] ERRO: ancora do header nao e' unica (count=%d)"
              % header.count(HEADER_ANCHOR))
        sys.exit(1)

    header = header.replace(HEADER_ANCHOR, HEADER_ANCHOR + HEADER_ADDITION, 1)
    write_text(HEADER, header)
    print("[apply_s2] header: membro `source` adicionado a GLESShader")
    return True


def splice_source():
    body = read_text(SOURCE)

    if S2_MARKER in body:
        print("[apply_s2] cpp: sessao 2 ja' emendada, nada a fazer")
        return False

    increment = read_text(INCREMENT).strip("\n")
    increment_lines = increment.split("\n")

    if increment_lines[-1].strip() != "}":
        print("[apply_s2] ERRO: incremento nao termina com a chave de namespace")
        sys.exit(1)

    # O incremento fecha `namespace plume`; o fechamento original e' substituido por ele.
    stripped = body.rstrip()
    if not stripped.endswith("}"):
        print("[apply_s2] ERRO: cpp nao termina com chave de fechamento")
        sys.exit(1)

    close_index = stripped.rfind("\n}")
    if close_index == -1:
        print("[apply_s2] ERRO: nao achei o fechamento de namespace")
        sys.exit(1)

    head = stripped[:close_index]

    # Reindenta por 4 espacos tudo menos a chave final, para casar com o estilo do arquivo.
    indented = [
        ("    " + line) if line.strip() else line
        for line in increment_lines[:-1]
    ]

    merged = head + "\n\n" + "\n".join(indented) + "\n" + increment_lines[-1] + "\n"
    write_text(SOURCE, merged)
    print("[apply_s2] cpp: sessao 2 emendada (%d -> %d linhas)"
          % (len(body.split("\n")), len(merged.split("\n"))))
    return True


def main():
    header_changed = patch_header()
    source_changed = splice_source()

    if not header_changed and not source_changed:
        print("[apply_s2] nada mudou")
        return

    for name in ("plume_gles.h", "plume_gles.cpp"):
        path = os.path.join(PLUME_DIR, name)
        print("[apply_s2] %s = %d linhas" % (name, len(read_text(path).split("\n"))))


if __name__ == "__main__":
    main()