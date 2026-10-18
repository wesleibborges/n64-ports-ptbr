#!/usr/bin/env python3
#
# M5-GLES -- selecao do backend OpenGL ES 3.2 pelo CONFIG (nao pelo RT64::UserConfiguration
# lido de rt64.json -- essa via nao existe neste port).
#
# Descoberta que define o escopo deste passo: a cadeia real de selecao de API neste port e'
#
#   graphics.json["api_option"]                 ("Auto" | "D3D12" | "Vulkan" | "Metal")
#     -> recomp::config::ConfigOptionEnum       (guarda a CHAVE textual + o valor uint32)
#     -> ultramodern::renderer::GraphicsApi     (enum em ultramodern/config.hpp)
#     -> switch em recompui/src/renderer/rt64_render_context.cpp
#     -> app->userConfig.graphicsAPI            (RT64::UserConfiguration::GraphicsAPI)
#
# e o rt64.json NAO participa: `appConfig.useConfigurationFile = false` no mesmo arquivo.
# Por isso o M2 deixou "graphicsAPI: GLES no rt64.json" como pre-condicao -- ela e' inutil
# aqui; o equivalente correto e' ligar GLES nas quatro pontas acima (mais o nome da API
# usado nas mensagens de erro, senao o usuario le "[Unknown graphics API]").
#
# A janela SDL continua sendo decidida ANTES da config (src/main/main.cpp / BH_GRAPHICS_API,
# feito no M2) -- os dois lados sao escritos pelo launcher a partir de um unico botao.
#
# Uso:
#   python3 m5_gles_api_select_apply.py check    # relata estado + contagem de ocorrencias
#   python3 m5_gles_api_select_apply.py apply    # aplica (backup + md5; idempotente)
#   python3 m5_gles_api_select_apply.py revert   # restaura os originais dos backups
#
# Disciplina (mesma dos scripts do M1/M2): cada substituicao tem que casar EXATAMENTE
# uma vez; qualquer ambiguidade ABORTA sem escrever nada. Backup e md5 antes/depois ficam
# em /root/bhrecomp/m5_gles_api_select_20261018/.
#
import hashlib
import json
import os
import shutil
import sys

ROOT = "/root/bhrecomp"
WORK = os.path.join(ROOT, "m5_gles_api_select_20261018")
BACKUP = os.path.join(WORK, "backups")
MANIFEST = os.path.join(WORK, "manifest.json")


def md5(path):
    with open(path, "rb") as handle:
        return hashlib.md5(handle.read()).hexdigest()


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def backup_path(rel):
    return os.path.join(BACKUP, rel.replace("/", "__"))


EDITS = []


def add(rel, tag, old, new):
    EDITS.append((rel, tag, old, new))


CONFIG_HPP = "lib/N64ModernRuntime/ultramodern/include/ultramodern/config.hpp"
RENDERER_CONTEXT_CPP = "lib/N64ModernRuntime/ultramodern/src/renderer_context.cpp"
UI_GRAPHICS_CPP = "lib/RecompFrontend/recompui/src/config/ui_config_tab_graphics.cpp"
RT64_RC_CPP = "lib/RecompFrontend/recompui/src/renderer/rt64_render_context.cpp"

# ---------------------------------------------------------------------------
# 1) config.hpp -- membro do enum GraphicsApi.
#
# GLES entra DEPOIS de Metal (valor 4; OptionCount 4->5). Renumerar Vulkan/Metal seria
# um bug silencioso: ConfigOptionEnumOption::value = static_cast<uint32_t>(enum) e esse
# uint32 e' comparado por find_option_from_value. Sob #ifdef para que o gate OFF continue
# produzindo binario SEM a string "GLES".
# ---------------------------------------------------------------------------
add(
    CONFIG_HPP,
    "config_hpp_enum",
    """        enum class GraphicsApi {
            Auto,
            D3D12,
            Vulkan,
            Metal,
            OptionCount
        };
""",
    """        enum class GraphicsApi {
            Auto,
            D3D12,
            Vulkan,
            Metal,
#ifdef RT64_GLES_BACKEND
            // M5-GLES -- OpenGL ES 3.2 (plume_gles) para o R36S/Mali-G31.
            // Inserido DEPOIS de Metal de proposito: Auto=0..Metal=3 ficam estaveis.
            // A chave textual ("GLES") e' o que vai para o graphics.json, mas o valor
            // numerico tambem trafega como uint32 (ConfigOptionEnumOption::value),
            // logo renumerar Vulkan/Metal quebraria configs ja salvas no device.
            GLES,
#endif
            OptionCount
        };
""",
)

# ---------------------------------------------------------------------------
# 2) config.hpp -- par chave/valor do nlohmann.
#
# O bloco e' DUPLICADO sob #ifdef/#else porque NLOHMANN_JSON_SERIALIZE_ENUM e' um MACRO:
# diretiva de pre-processador na lista de argumentos de macro e' comportamento indefinido
# ([cpp] "would otherwise act as preprocessing directives"), logo nao da' para colocar um
# #ifdef so' na linha do GLES.
#
# Neste consumidor do enum o json passa pela rota ConfigOptionEnum (chave textual), nao
# pelo to_json/from_json direto; a duplicacao existe para (a) manter a serializacao
# coerente caso alguem grave GraphicsApi direto e (b) garantir que o gate OFF nao injete
# a string "GLES" no binario.
# ---------------------------------------------------------------------------
add(
    CONFIG_HPP,
    "config_hpp_json",
    """        NLOHMANN_JSON_SERIALIZE_ENUM(ultramodern::renderer::GraphicsApi, {
            {ultramodern::renderer::GraphicsApi::Auto, "Auto"},
            {ultramodern::renderer::GraphicsApi::D3D12, "D3D12"},
            {ultramodern::renderer::GraphicsApi::Vulkan, "Vulkan"},
            {ultramodern::renderer::GraphicsApi::Metal, "Metal"},
        });
""",
    """        // M5-GLES -- bloco duplicado sob #ifdef/#else: com o gate ON entra o par
        // "GLES"; com o gate OFF o bloco original fica byte-identico.
#ifdef RT64_GLES_BACKEND
        NLOHMANN_JSON_SERIALIZE_ENUM(ultramodern::renderer::GraphicsApi, {
            {ultramodern::renderer::GraphicsApi::Auto, "Auto"},
            {ultramodern::renderer::GraphicsApi::D3D12, "D3D12"},
            {ultramodern::renderer::GraphicsApi::Vulkan, "Vulkan"},
            {ultramodern::renderer::GraphicsApi::Metal, "Metal"},
            {ultramodern::renderer::GraphicsApi::GLES, "GLES"},
        });
#else
        NLOHMANN_JSON_SERIALIZE_ENUM(ultramodern::renderer::GraphicsApi, {
            {ultramodern::renderer::GraphicsApi::Auto, "Auto"},
            {ultramodern::renderer::GraphicsApi::D3D12, "D3D12"},
            {ultramodern::renderer::GraphicsApi::Vulkan, "Vulkan"},
            {ultramodern::renderer::GraphicsApi::Metal, "Metal"},
        });
#endif
""",
)

# ---------------------------------------------------------------------------
# 3) renderer_context.cpp -- nome humano da API (usado nas mensagens de erro de
#    events.cpp: "(...) is not supported on this platform" / "Unable to initialize (...)").
#    Sem este case o usuario leria "[Unknown graphics API]" -- a falha nomeada do M2
#    viraria ruido justamente quando mais importa (device, primeira execucao).
# ---------------------------------------------------------------------------
add(
    RENDERER_CONTEXT_CPP,
    "renderer_context_name",
    """    case ultramodern::renderer::GraphicsApi::Metal:
        return "Metal";
    default:
        return "[Unknown graphics API]";
""",
    """    case ultramodern::renderer::GraphicsApi::Metal:
        return "Metal";
#ifdef RT64_GLES_BACKEND
    case ultramodern::renderer::GraphicsApi::GLES:
        return "GLES";
#endif
    default:
        return "[Unknown graphics API]";
""",
)

# ---------------------------------------------------------------------------
# 4) ui_config_tab_graphics.cpp -- macro que habilita a opcao no seletor da UI.
#    Mesmo padrao dos ALLOW_D3D12/ALLOW_VULKAN/ALLOW_METAL ja existentes (mais abaixo,
#    o vetor graphics_api_options usa exatamente esses #ifdef).
# ---------------------------------------------------------------------------
add(
    UI_GRAPHICS_CPP,
    "ui_graphics_allow_gles",
    """        #if defined(__APPLE__)
        #define ALLOW_METAL
        #endif
""",
    """        #if defined(__APPLE__)
        #define ALLOW_METAL
        #endif
        // M5-GLES -- a opcao so' aparece no seletor quando o backend esta compilado
        // (gate RT64_GLES_BACKEND) E o alvo e' Linux (R36S via KMSDRM/EGL/GBM).
        #if defined(__linux__) && defined(RT64_GLES_BACKEND)
        #define ALLOW_GLES
        #endif
""",
)

# ---------------------------------------------------------------------------
# 5) ui_config_tab_graphics.cpp -- entrada no vetor de opcoes. O que o graphics.json
#    guarda e' a CHAVE ("GLES"); `get_graphics_enum_value<GraphicsApi>(api_option)`
#    resolve chave -> valor via ConfigOptionEnum::find_option_from_string.
# ---------------------------------------------------------------------------
add(
    UI_GRAPHICS_CPP,
    "ui_graphics_option_entry",
    """        #ifdef ALLOW_METAL
            {ultramodern::renderer::GraphicsApi::Metal, "Metal"},
        #endif
        };
""",
    """        #ifdef ALLOW_METAL
            {ultramodern::renderer::GraphicsApi::Metal, "Metal"},
        #endif
        #ifdef ALLOW_GLES
            {ultramodern::renderer::GraphicsApi::GLES, "GLES"},
        #endif
        };
""",
)

# ---------------------------------------------------------------------------
# 6) rt64_render_context.cpp -- o consumer final: traduz a opcao do graphics.json
#    (ultramodern::renderer::GraphicsApi) para a API do RT64. Sem este case uma
#    api_option="GLES" cairia no `default:` -> Automatic -> Vulkan sobre uma janela
#    GL (exatamente a falha "a sem b" documentada na pre-condicao do M2).
# ---------------------------------------------------------------------------
add(
    RT64_RC_CPP,
    "rt64_rc_switch",
    """        case ultramodern::renderer::GraphicsApi::Metal:
            app->userConfig.graphicsAPI = RT64::UserConfiguration::GraphicsAPI::Metal;
            break;
        case ultramodern::renderer::GraphicsApi::Auto:
        default:
""",
    """        case ultramodern::renderer::GraphicsApi::Metal:
            app->userConfig.graphicsAPI = RT64::UserConfiguration::GraphicsAPI::Metal;
            break;
#ifdef RT64_GLES_BACKEND
        case ultramodern::renderer::GraphicsApi::GLES:
            app->userConfig.graphicsAPI = RT64::UserConfiguration::GraphicsAPI::GLES;
            break;
#endif
        case ultramodern::renderer::GraphicsApi::Auto:
        default:
""",
)

# ---------------------------------------------------------------------------
# 7) rt64_render_context.cpp -- map_graphics_api: sentido inverso (a API que o RT64
#    REALMENTE escolheu -> enum do ultramodern). Sem o case o programa imprime
#    "Unhandled `RT64::UserConfiguration::GraphicsAPI` ?" e aborta (assert/exit) ao
#    ler chosenGraphicsAPI -- ou seja, o GLES funcionaria e o port morreria no log.
# ---------------------------------------------------------------------------
add(
    RT64_RC_CPP,
    "rt64_rc_map",
    """        case RT64::UserConfiguration::GraphicsAPI::Metal:
            return ultramodern::renderer::GraphicsApi::Metal;
        case RT64::UserConfiguration::GraphicsAPI::Automatic:
            return ultramodern::renderer::GraphicsApi::Auto;
        default:
            break;
""",
    """        case RT64::UserConfiguration::GraphicsAPI::Metal:
            return ultramodern::renderer::GraphicsApi::Metal;
#ifdef RT64_GLES_BACKEND
        case RT64::UserConfiguration::GraphicsAPI::GLES:
            return ultramodern::renderer::GraphicsApi::GLES;
#endif
        case RT64::UserConfiguration::GraphicsAPI::Automatic:
            return ultramodern::renderer::GraphicsApi::Auto;
        default:
            break;
""",
)

# ---------------------------------------------------------------------------
# Sondas de idempotencia.
#
# Em 5 destes 7 edits o texto novo CONTEM o antigo como substring (o enum ganha uma
# linha antes de OptionCount; o bloco #else repete o original; o case #endif fica no meio
# de um trecho preservado). Logo `old not in text` NAO significa "pendente". Cada sonda
# abaixo existe APENAS no texto aplicado e nunca no pristino.
#
# ATENCAO: a sonda de config_hpp_enum casa tambem dentro de config_hpp_json? Nao -- sao
# strings diferentes. A sonda e' sempre verificada no arquivo do proprio edit.
# ---------------------------------------------------------------------------
PROBES = {
    "config_hpp_enum": r"// M5-GLES -- OpenGL ES 3.2 (plume_gles) para o R36S/Mali-G31.",
    "config_hpp_json": r'{ultramodern::renderer::GraphicsApi::GLES, "GLES"},',
    "renderer_context_name": "    case ultramodern::renderer::GraphicsApi::GLES:\n        return \"GLES\";",
    "ui_graphics_allow_gles": r"#define ALLOW_GLES",
    "ui_graphics_option_entry": "        #ifdef ALLOW_GLES\n            {ultramodern::renderer::GraphicsApi::GLES, \"GLES\"},",
    "rt64_rc_switch": r"app->userConfig.graphicsAPI = RT64::UserConfiguration::GraphicsAPI::GLES;",
    "rt64_rc_map": r"return ultramodern::renderer::GraphicsApi::GLES;",
}


def probe_for(tag):
    if tag not in PROBES:
        raise KeyError("tag sem sonda de idempotencia: %s" % tag)
    return PROBES[tag]


# ---------------------------------------------------------------------------
# Driver: check / apply / revert
# ---------------------------------------------------------------------------
def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {"edits": {}}


def save_manifest(manifest):
    os.makedirs(WORK, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)


def cmd_check():
    applied = 0
    for rel, tag, old, new in EDITS:
        path = os.path.join(ROOT, rel)
        text = read(path)
        probe = probe_for(tag)
        occurrences = text.count(old)
        if probe in text:
            state = "APLICADO"
            applied += 1
        elif occurrences == 1:
            state = "PENDENTE"
        else:
            state = "AMBIGUO"
        print("[%s] %s :: %s (alvo x%d)" % (state.ljust(8), rel, tag, occurrences))

    print("RESUMO CHECK: aplicados=%d/%d" % (applied, len(EDITS)))
    # 0 = tudo aplicado ou tudo pendente; 1 = estado misto/ambiguo (exige atencao).
    return 0 if applied in (0, len(EDITS)) else 1


def cmd_apply():
    manifest = load_manifest()
    manifest.setdefault("files", {})
    manifest.setdefault("edits", {})
    os.makedirs(BACKUP, exist_ok=True)
    changed = 0
    skipped = 0

    for rel, tag, old, new in EDITS:
        path = os.path.join(ROOT, rel)
        text = read(path)
        key = "%s::%s" % (rel, tag)
        probe = probe_for(tag)

        if probe in text:
            print("[SKIP    ] ja aplicado: %s" % key)
            skipped += 1
            continue

        occurrences = text.count(old)
        if occurrences != 1:
            print("[FALHA   ] %s: texto-alvo ocorre %d vezes (esperado 1). Nada foi escrito." % (key, occurrences))
            return 2

        before = md5(path)
        dst = backup_path(rel)
        # O backup e' do estado PRISTINO: so' grava na primeira vez que este arquivo
        # e' tocado (em qualquer execucao). Assim um arquivo com varios edits guarda
        # uma unica copia original e o revert e' sempre fiel.
        if not os.path.exists(dst):
            shutil.copy2(path, dst)
            manifest["files"][rel] = {"backup": os.path.relpath(dst, ROOT), "pristine_md5": before}
        elif rel not in manifest["files"]:
            # Backup de execucao anterior sem manifest: a propria copia e' a fonte
            # de verdade do md5 pristino.
            manifest["files"][rel] = {"backup": os.path.relpath(dst, ROOT), "pristine_md5": md5(dst)}

        write(path, text.replace(old, new, 1))

        # Pos-condicao: a sonda tem que existir agora. Se nao existir, aborta ALTO
        # em vez de deixar um estado meio-aplicado silencioso.
        if probe not in read(path):
            print("[FALHA   ] %s: pos-condicao falhou (sonda ausente apos aplicar)." % key)
            return 2

        after = md5(path)
        manifest["edits"][key] = {"file": rel, "md5_before": before, "md5_after": after}
        print("[APLICA  ] %s md5 %s -> %s" % (key, before, after))
        changed += 1

    save_manifest(manifest)
    print("RESUMO APPLY: alterados=%d ja_aplicados=%d total=%d" % (changed, skipped, len(EDITS)))
    return 0


def cmd_revert():
    manifest = load_manifest()
    files = manifest.get("files", {})
    if not files:
        print("[FALHA   ] manifest sem arquivos: nada para reverter (%s)" % MANIFEST)
        return 2

    failed = 0
    for rel in sorted(files):
        info = files[rel]
        src = os.path.join(ROOT, info["backup"])
        dst = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print("[FALHA   ] backup ausente para %s: %s" % (rel, src))
            failed += 1
            continue
        shutil.copy2(src, dst)
        now = md5(dst)
        status = "OK" if now == info["pristine_md5"] else "DIVERGENTE"
        print("[REVERT  ] %s md5=%s pristino=%s %s" % (rel, now, info["pristine_md5"], status))
        if status != "OK":
            failed += 1

    print("RESUMO REVERT: arquivos=%d falhas=%d" % (len(files), failed))
    return 0 if failed == 0 else 2


def main():
    if (len(sys.argv) != 2) or (sys.argv[1] not in ("check", "apply", "revert")):
        print("uso: m5_gles_api_select_apply.py check|apply|revert")
        return 1

    return {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())