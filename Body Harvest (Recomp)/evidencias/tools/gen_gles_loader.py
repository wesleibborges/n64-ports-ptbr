#!/usr/bin/env python3
"""gen_gles_loader.py - gera um carregador OpenGL ES 3.2 auto-contido (padrao volk).

Por que existe
--------------
O backend `plume_gles` (M2 do porte R36S) precisa chamar ~358 entry points de GLES
sem linkar contra `libGLESv2`/`libEGL` (politica do `vkprobe`/`glesprobe`: todas as
funcoes vem de `SDL_GL_GetProcAddress`). O precedente no proprio repositorio e o
`volk` (`src/contrib/plume/contrib/volk/generate.py`), que faz isso para Vulkan.

Em vez de `#include <GLES3/gl32.h>` (que emitiria os PROTOTIPOS e impediria a
tabela de ponteiros homonima, alem de criar dependencia de header do sysroot),
este gerador emite um header AUTOCONTIDO com:

  * os tipos base derivados de `khronos_*` (resolvidos p/ <cstdint>/<cstddef>);
  * as 1007 constantes `#define GL_*` do gl32.h;
  * `typedef <ret> (*PFN_glXxx)(args);` + `extern PFN_glXxx glXxx;` para cada
    entry point;
  * a lista X-macro `PLUME_GL_FUNCTIONS(X)` usada para declarar/carregar tudo
    de uma vez.

Todos os simbolos ficam em `namespace plume::gl`, de modo que nunca colidem com
os simbolos reais de libGLESv2 caso alguem linke as duas coisas.

Formato de entrada comprovado (gl32.h do Khronos, gerado do XML registry):
  * 358 prototipos, todos em UMA linha e terminando em `;`
  * 0 prototipos com parametro de tipo function-pointer (`(*`)  -> parser trivial
  * 1007 constantes, todas `0x...` ou decimal

Uso:
  python3 gen_gles_loader.py <gl32.h> <out_dir> [nome_base]
      nome_base default: plume_gles_gl
Gera <out_dir>/<nome_base>.h e <out_dir>/<nome_base>.cpp
"""

import os
import re
import sys

SRC_DEFAULT = "/opt/r36s/rootfs/usr/include/GLES3/gl32.h"

# Tipos base khronos_* -> tipo C++ padrao equivalente (64-bit Linux, o alvo R36S).
KHRONOS_MAP = {
    "khronos_int8_t": "int8_t",
    "khronos_uint8_t": "uint8_t",
    "khronos_int16_t": "int16_t",
    "khronos_uint16_t": "uint16_t",
    "khronos_int32_t": "int32_t",
    "khronos_uint32_t": "uint32_t",
    "khronos_int64_t": "int64_t",
    "khronos_uint64_t": "uint64_t",
    "khronos_intptr_t": "intptr_t",
    "khronos_uintptr_t": "uintptr_t",
    "khronos_ssize_t": "ptrdiff_t",
    "khronos_usize_t": "size_t",
    "khronos_float_t": "float",
    "khronos_boolean_enum_t": "uint32_t",
}

RE_TYPEDEF = re.compile(r"^typedef\s+(.+?)\s*(GL\w+)\s*;\s*$")
# typedef de ponteiro de funcao, ex.: `typedef void (GL_APIENTRYP GLDEBUGPROC)(...)`
RE_TYPEDEF_FPTR = re.compile(
    r"^typedef\s+(.+?)\s*\(\s*GL_APIENTRYP?\s*\*?\s*(GL\w+)\s*\)\s*\(([^;]*)\)\s*;\s*$"
)
RE_CONST = re.compile(r"^#define\s+(GL_[A-Za-z0-9_]+)\s+(.+?)\s*$")
RE_FUNC = re.compile(
    r"^GL_APICALL\s+(.+?)\s*GL_APIENTRY\s+(gl\w+)\s*\(([^;]*)\)\s*;\s*$"
)


def parse(path):
    types, consts, funcs = [], [], []
    seen_types, seen_consts, seen_funcs = set(), set(), set()

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")

            m = RE_FUNC.match(line)
            if m:
                ret, name, args = m.group(1), m.group(2), m.group(3)
                if name not in seen_funcs:
                    seen_funcs.add(name)
                    funcs.append((ret.strip(), name, args.strip()))
                continue

            if line.startswith("#define GL_"):
                m = RE_CONST.match(line)
                if m:
                    name, value = m.group(1), m.group(2)
                    # `GL_APIENTRYP GL_APIENTRY*` nao e constante: e o macro que
                    # define o tipo "ponteiro para APIENTRY". Nao pertence aqui.
                    if "APIENTRY" in value or "APIENTRYP" in name:
                        continue
                    if name not in seen_consts:
                        seen_consts.add(name)
                        consts.append((name, value))
                continue

            if line.startswith("typedef ") and line.endswith(";"):
                # Primeiro os typedefs de ponteiro de funcao (ex.: GLDEBUGPROC),
                # que tem sintaxe propria e nao casam com o padrao simples.
                m = RE_TYPEDEF_FPTR.match(line)
                if m:
                    ret, name, args = m.group(1), m.group(2), m.group(3)
                    if name not in seen_types:
                        seen_types.add(name)
                        types.append(("__fptr__",
                                      "typedef %s (*%s)(%s);" % (ret.strip(), name,
                                                                 args.strip())))
                    continue

                m = RE_TYPEDEF.match(line)
                if m:
                    base, name = m.group(1), m.group(2)
                    if name not in seen_types:
                        seen_types.add(name)
                        types.append((base, name))

    return types, consts, funcs


def render_base_types(types):
    """Resolve os typedefs GL* em tipos C++ padrao (sem depender de khrplatform.h)."""
    out = []
    for base, name in types:
        if base == "__fptr__":
            # Ja vem renderizado pelo parser (typedef de ponteiro de funcao).
            out.append(name)
        elif base in KHRONOS_MAP:
            out.append("typedef %s %s;" % (KHRONOS_MAP[base], name))
        else:
            # Ja e um tipo concreto: `unsigned int`, `char`, `int`, `void`,
            # `struct __GLsync *`, etc. Emitido verbatim.
            out.append("typedef %s %s;" % (base, name))
    return out


def render(types, consts, funcs, src, name_base):
    L = []
    a = L.append

    a("//")
    a("// plume_gles -- carregador de entry points OpenGL ES 3.2 (auto-contido).")
    a("//")
    a("// *****************************************************************************")
    a("// ARQUIVO GERADO -- NAO EDITE A MAO.")
    a("//   fonte    : %s" % src)
    a("//   gerador  : evidencias/tools/gen_gles_loader.py")
    a("//   contagens: %d tipos, %d constantes, %d entry points"
      % (len(types), len(consts), len(funcs)))
    a("// *****************************************************************************")
    a("//")
    a("// Espelha a politica do probe do M0 (evidencias/tools/gles_probe.c): nenhum")
    a("// link contra libGLESv2/libEGL. Todos os ponteiros sao preenchidos em runtime")
    a("// por plume::gl::load(), tipicamente com SDL_GL_GetProcAddress.")
    a("//")
    a("// Os simbolos vivem em plume::gl (nunca no escopo global), portanto NAO")
    a("// colidem com os simbolos reais de libGLESv2 se o binario linkar os dois.")
    a("")
    a("#pragma once")
    a("")
    a("#include <cstddef>")
    a("#include <cstdint>")
    a("#include <string>")
    a("#include <vector>")
    a("")
    a("namespace plume {")
    a("namespace gl {")
    a("")
    a("// ---------------------------------------------------------------- tipos base")
    for t in render_base_types(types):
        a(t)
    a("")
    a("// ------------------------------------------------------------- constantes GL")
    for name, value in consts:
        a("#define %-48s %s" % (name, value))
    a("")
    a("// -------------------------------------------------------------- entry points")
    a("// Ponteiro + tipo PFN_<nome> para cada funcao de gl32.h.")
    for ret, name, args in funcs:
        a("typedef %s (*PFN_%s)(%s);" % (ret, name, args if args else "void"))
    a("")
    a("// Lista X-macro: a declaracao (header), a definicao e a carga (.cpp) usam a")
    a("// MESMA lista, o que torna impossivel esquecer de carregar um ponteiro.")
    a("#define PLUME_GL_FUNCTIONS(X) \\")
    for i, (_ret, name, _args) in enumerate(funcs):
        tail = "" if i == len(funcs) - 1 else " \\"
        a("    X(%s)%s" % (name, tail))
    a("")
    a("// Globais (definidos em %s.cpp)." % name_base)
    a("#define PLUME_GL_DECLARE_PTR(name) extern PFN_##name name;")
    a("PLUME_GL_FUNCTIONS(PLUME_GL_DECLARE_PTR)")
    a("#undef PLUME_GL_DECLARE_PTR")
    a("")
    a("// Resolve TODOS os %d entry points. Retorna false se qualquer um faltar."
      % len(funcs))
    a("// Os nomes ausentes ficam disponiveis em missing(), para o chamador decidir")
    a("// se a ausencia e fatal. Nao depende de SDL: o chamador passa o resolvedor.")
    a("typedef void *(*PlumeGLProcResolver)(const char *name);")
    a("bool load(PlumeGLProcResolver resolver);")
    a("const std::vector<std::string> &missing();")
    a("")
    a("// Quantidade de entry points desta lista (util para log/evidencia).")
    a("constexpr uint32_t FUNCTION_COUNT = %d;" % len(funcs))
    a("")
    a("} // namespace gl")
    a("} // namespace plume")
    a("")

    cpp = []
    c = cpp.append
    c("//")
    c("// plume_gles -- implementacao do carregador gerado (ver %s.h)." % name_base)
    c("//")
    c("// *****************************************************************************")
    c("// ARQUIVO GERADO -- NAO EDITE A MAO (evidencias/tools/gen_gles_loader.py).")
    c("// *****************************************************************************")
    c("")
    c('#include "%s.h"' % name_base)
    c("")
    c("namespace plume {")
    c("namespace gl {")
    c("")
    c("#define PLUME_GL_DEFINE_PTR(name) PFN_##name name = nullptr;")
    c("PLUME_GL_FUNCTIONS(PLUME_GL_DEFINE_PTR)")
    c("#undef PLUME_GL_DEFINE_PTR")
    c("")
    c("static std::vector<std::string> g_missing;")
    c("")
    c("const std::vector<std::string> &missing() {")
    c("    return g_missing;")
    c("}")
    c("")
    c("bool load(PlumeGLProcResolver resolver) {")
    c("    g_missing.clear();")
    c("")
    c("    if (resolver == nullptr) {")
    c("        g_missing.push_back(\"<null resolver>\");")
    c("        return false;")
    c("    }")
    c("")
    c("#define PLUME_GL_LOAD_PTR(name) \\")
    c("    name = reinterpret_cast<PFN_##name>(resolver(#name)); \\")
    c("    if (name == nullptr) { g_missing.push_back(#name); }")
    c("    PLUME_GL_FUNCTIONS(PLUME_GL_LOAD_PTR)")
    c("#undef PLUME_GL_LOAD_PTR")
    c("")
    c("    return g_missing.empty();")
    c("}")
    c("")
    c("} // namespace gl")
    c("} // namespace plume")
    c("")

    return "\n".join(L), "\n".join(cpp)


def main(argv):
    src = argv[1] if len(argv) > 1 else SRC_DEFAULT
    out_dir = argv[2] if len(argv) > 2 else "."
    name_base = argv[3] if len(argv) > 3 else "plume_gles_gl"

    if not os.path.isfile(src):
        print("gen_gles_loader: fonte nao encontrada: %s" % src, file=sys.stderr)
        return 2
    if not os.path.isdir(out_dir):
        print("gen_gles_loader: diretorio de saida nao existe: %s" % out_dir,
              file=sys.stderr)
        return 2

    types, consts, funcs = parse(src)
    if len(funcs) == 0:
        print("gen_gles_loader: nenhum entry point parseado (formato inesperado)",
              file=sys.stderr)
        return 3

    header, cpp = render(types, consts, funcs, src, name_base)

    h_path = os.path.join(out_dir, name_base + ".h")
    c_path = os.path.join(out_dir, name_base + ".cpp")
    with open(h_path, "w", encoding="utf-8") as fh:
        fh.write(header)
    with open(c_path, "w", encoding="utf-8") as fh:
        fh.write(cpp)

    print("gen_gles_loader: fonte=%s" % src)
    print("  -> %s (%d linhas)" % (h_path, header.count("\n") + 1))
    print("  -> %s (%d linhas)" % (c_path, cpp.count("\n") + 1))
    print("  tipos=%d constantes=%d entry_points=%d"
          % (len(types), len(consts), len(funcs)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))