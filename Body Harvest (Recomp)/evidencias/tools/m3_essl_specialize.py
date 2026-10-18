#!/usr/bin/env python3
"""M3 -- prototipo DETERMINISTICO da especializacao do ESSL de producao do raster PS do RT64.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Medido em 2026-10-18 (`evidencias/m1_3_stage2/essl/RasterPSDynamic.essl`): o ESSL que o M1.3
gera para os raster PS declara

    20 arrays de `sampler2D[8192]`  (18 combos de gTextures + 1 dummy + gTMEM/usampler2D)

porque o `spirv-cross` materializa UMA array por par (imagem x sampler) numa unica array logica
(`SPIRV_Cross_CombinedgTexturesg<Filtro><WrapU><WrapV>Sampler[8192]`), e todas sao indexadas por
`GPUTiles._m0[..].textureIndex` (indice DINAMICO, por-fragmento).

Um driver ES 3.2 CONFORMANTE conta o TAMANHO INTEIRO de cada array indexada dinamicamente contra
`GL_MAX_TEXTURE_IMAGE_UNITS` (llvmpipe: 32). Logo o orcamento e' MULTIPLICATIVO:

    n_arrays_dinamicas x N  <=  GL_MAX_TEXTURE_IMAGE_UNITS

20 x 8192 = 163.840 samplers >> 32 -> `error: Too many fragment shader texture samplers` no LINK
(nao na compilacao: e' por isso que o `glslangValidator` do M1.3 devolvia rc=0 e o aceite
"57/57 ESSL" nao provava nada).

O QUE ESTA FERRAMENTA FAZ
-------------------------
Materializa, por transformacao TEXTUAL deterministica, a forma que o M3 tem de gerar em runtime:
(a) COLAPSAR os combos de sampler de uma mesma imagem em UMA array (`--collapse-samplers`), que e'
    exatamente o resultado de se especializar o shader pelo combo que o DRAW usa; e
(b) aplicar a JANELA `N` do M3 (`--window N`), trocando `[8192]` por `[N]`.

LIMITE DECLARADO (honestidade do escopo): e' uma transformacao de FORMA, nao de semantica. Ela nao
faz o remap de `textureIndex` para dentro da janela N (isso e' trabalho de CPU do M3): o objetivo
aqui e' medir COMPILE+LINK do artefato REAL no driver -- render (o "gate visual") e' o M4.

Uso:
  m3_essl_specialize.py --in PS.essl --out PS.spec.essl --window 16 --collapse-samplers
  m3_essl_specialize.py --in PS.essl --out PS.asis.essl            # copia (controle "as-is")

Saida: arquivo transformado + linhas `transform_<campo>=<valor>` (estaveis, para grep).
"""

import argparse
import os
import re
import sys

# `uniform highp sampler2D NOME[8192];` -- so' declaracoes de sampler COM janela entram.
DECL_RE = re.compile(
    r"^\s*uniform\s+(?:(?P<prec>lowp|mediump|highp)\s+)?"
    r"(?P<type>\w*[sS]ampler\w*)\s+(?P<name>\w+)\s*\[\s*(?P<size>\d+)\s*\]\s*;\s*$"
)

# Prefixos de imagem que o M3 colapsa (uma array por IMAGEM, nao por combo imagem x sampler).
DEFAULT_PREFIXES = ("SPIRV_Cross_CombinedgTextures", "SPIRV_Cross_CombinedgTMEM")


def canonical_name(prefix, type_name):
    """Nome deterministico da array unica daquela imagem (sufixo _U/_I para sampler inteiro)."""
    suffix = ""
    if type_name.startswith("u"):
        suffix = "_U"
    elif type_name.startswith("i"):
        suffix = "_I"
    return prefix + "Sampler" + suffix


def parse_declarations(text, prefixes):
    """Devolve [(line_index, prec, type, name, size)] das declaracoes de sampler com janela."""
    found = []
    for index, line in enumerate(text.splitlines()):
        match = DECL_RE.match(line)
        if not match:
            continue
        name = match.group("name")
        if prefixes and not name.startswith(tuple(prefixes)):
            continue
        found.append(
            (index, match.group("prec") or "", match.group("type"), name, int(match.group("size")))
        )
    return found


def flat_locations(text):
    """Locations que o FRAGMENT declara com `flat in` (o vertex tem de declarar `flat out`)."""
    locations = set()
    pattern = re.compile(r"^\s*layout\s*\(\s*location\s*=\s*(\d+)[^)]*\)\s*flat\s+in\b")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            locations.add(int(match.group(1)))
    return locations


def match_flat_interpolation(text, locations):
    """Marca `flat` nos `out` do VERTEX que o fragment le como `flat in` (mesma location).

    ACHADO 2026-10-18 (medido em driver ES 3.2 conformante, llvmpipe): o codegen emite `flat in`
    no PS mas deixa o `out` do VS sem qualificador de interpolacao, e o LINK recusa:
      `error: vertex shader output 'out_var_COLOR1' specifies no interpolation qualifier, but
       fragment shader input specifies flat interpolation qualifier`
    """
    changed = 0
    lines_out = []
    pattern = re.compile(r"^(layout\s*\(\s*location\s*=\s*(\d+)[^)]*\)\s*)(?!flat\b)(out\b)")
    for line in text.splitlines():
        match = pattern.match(line)
        if match and int(match.group(2)) in locations:
            line = match.group(1) + "flat " + line[match.start(3):]
            changed += 1
        lines_out.append(line)
    out = "\n".join(lines_out)
    if text.endswith("\n"):
        out += "\n"
    return out, changed


def inject_extensions(text, extensions):
    """Insere `#extension <X> : enable` logo apos o `#version` (protótipo da correção do M1.1)."""
    added = []
    for extension in extensions:
        directive = "#extension %s : enable" % extension
        if directive in text:
            continue
        text = text.replace("#version 320 es", "#version 320 es\n" + directive, 1)
        added.append(extension)
    return text, added


def transform(text, window, collapse, prefixes, enable_extensions=(), flat_in_locations=None):
    """Aplica janela e/ou colapso. Devolve (novo_texto, relatorio)."""
    text, extensions_added = inject_extensions(text, enable_extensions)
    declarations = parse_declarations(text, prefixes)

    name_map = {}          # nome antigo -> nome canonico (so' quando ha' colapso)
    kept_lines = set()     # declaracoes que sobrevivem
    new_size = {}          # nome -> janela final
    report = {
        "decls_before": len(declarations),
        "budget_before": sum(d[4] for d in declarations),
        "images": {},
        "extensions_added": extensions_added,
    }

    if collapse:
        canonical_of_group = {}
        for index, _prec, type_name, name, _size in declarations:
            prefix = next((p for p in prefixes if name.startswith(p)), name)
            group = (prefix, type_name)
            if group not in canonical_of_group:
                canonical_of_group[group] = canonical_name(prefix, type_name)
                kept_lines.add(index)
                report["images"][prefix + "_" + type_name] = 0
            name_map[name] = canonical_of_group[group]
            report["images"][prefix + "_" + type_name] += 1
    else:
        kept_lines = set(d[0] for d in declarations)

    for _index, _prec, _type_name, name, size in declarations:
        new_size[name] = window if window else size

    lines_out = []
    for index, line in enumerate(text.splitlines()):
        match = DECL_RE.match(line)
        if match and match.group("name").startswith(tuple(prefixes)):
            old_name = match.group("name")
            if index not in kept_lines:
                continue  # declaracao duplicada do mesmo grupo: o colapso a remove
            final_name = name_map.get(old_name, old_name)
            final_size = new_size.get(old_name, int(match.group("size")))
            prec = match.group("prec")
            lines_out.append(
                "uniform %s%s %s[%d];"
                % (prec + " " if prec else "", match.group("type"), final_name, final_size)
            )
            continue
        if name_map:
            for old_name, final_name in name_map.items():
                if old_name != final_name and old_name in line:
                    line = re.sub(r"\b%s\b" % re.escape(old_name), final_name, line)
        lines_out.append(line)

    out = "\n".join(lines_out)
    if text.endswith("\n"):
        out += "\n"

    flat_matched = 0
    if flat_in_locations:
        out, flat_matched = match_flat_interpolation(out, flat_in_locations)

    after = parse_declarations(out, None)
    report["decls_after"] = len(after)
    report["budget_after"] = sum(d[4] for d in after)
    report["removed_decls"] = report["decls_before"] - report["decls_after"]
    report["flat_outputs_matched"] = flat_matched
    return out, report


def main(argv):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--in", dest="source", required=True, help="ESSL de entrada")
    parser.add_argument("--out", dest="target", required=True, help="ESSL de saida")
    parser.add_argument(
        "--window", type=int, default=0, help="janela N do M3 (`[8192]` -> `[N]`); 0 = manter"
    )
    parser.add_argument(
        "--collapse-samplers",
        action="store_true",
        help="colapsa os combos de sampler de cada imagem em UMA array",
    )
    parser.add_argument(
        "--collapse-prefix",
        action="append",
        default=None,
        help="prefixo de imagem a colapsar (repetivel; default: gTextures e gTMEM)",
    )
    parser.add_argument(
        "--enable-extension",
        action="append",
        default=None,
        help="insere `#extension X : enable` apos o #version (repetivel)",
    )
    parser.add_argument(
        "--flat-from-ps",
        dest="flat_from_ps",
        default=None,
        help="PS de referencia: marca `flat` nos `out` do VS nas locations que ele le `flat in`",
    )
    args = parser.parse_args(argv)

    prefixes = tuple(args.collapse_prefix) if args.collapse_prefix else DEFAULT_PREFIXES
    enable_extensions = tuple(args.enable_extension) if args.enable_extension else ()

    flat_in_locations = None
    if args.flat_from_ps:
        with open(args.flat_from_ps, "r", encoding="utf-8") as handle:
            flat_in_locations = flat_locations(handle.read())

    with open(args.source, "r", encoding="utf-8") as handle:
        text = handle.read()

    out, report = transform(text, args.window, args.collapse_samplers, prefixes, enable_extensions,
                            flat_in_locations)

    with open(args.target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(out)

    print("transform_in=%s" % os.path.basename(args.source))
    print("transform_out=%s" % os.path.basename(args.target))
    print("transform_window=%d" % (args.window if args.window else 0))
    print("transform_collapse=%d" % (1 if args.collapse_samplers else 0))
    print("transform_collapse_prefixes=%s" % ",".join(prefixes))
    print("transform_decls_before=%d" % report["decls_before"])
    print("transform_decls_after=%d" % report["decls_after"])
    print("transform_removed_decls=%d" % report["removed_decls"])
    print("transform_sampler_budget_before=%d" % report["budget_before"])
    print("transform_sampler_budget_after=%d" % report["budget_after"])
    print("transform_flat_outputs_matched=%d" % report["flat_outputs_matched"])
    print("transform_extensions_added=%s" % (",".join(report["extensions_added"]) or "(nenhuma)"))
    for key in sorted(report["images"]):
        print("transform_image_%s=%d" % (key, report["images"][key]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))