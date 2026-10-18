#!/usr/bin/env python3
"""M1.1 - Aplica (ou reverte) as adaptacoes de fonte gated por `HLSL_GLES`.

Principio: o caminho DX/VK/MSL (compilado SEM `-D HLSL_GLES`) deve permanecer
BYTE-IDENTICO. Para isso as abstracoes sao macros (#define) e os `#ifdef
HLSL_GLES` apenas trocam o tipo/caminho; nada e reescrito fora do gate.

Adaptacoes:
  1. shared/rt64_hlsl.h        -> TMEMTexture + tmemLoadTMEM + NonUniformResourceIndex
  2. FbRendererCommon.hlsli    -> gTMEM[8192] usa TMEMTexture
  3. TextureDecoder.hlsli      -> implLoadTMEM/sampleTMEM usam TMEMTexture
                                  + loadTLUT com branch GLES
  4. FbReinterpretCS.hlsl      -> gInputTLUT/TMEM locais usam TMEMTexture
  5. TextureDecodeCS.hlsl      -> TMEM usa TMEMTexture

Motivos (medidos, vide m1_1_probe e evidence_m1_layout_matrix_20261018.md):
  - ESSL 3.20 NAO possui texturas 1D (usampler1D e palavra reservada).
  - ESSL 3.20 NAO possui descriptor indexing -> NonUniformResourceIndex e
    identidade; remover o uso elimina a capability ShaderNonUniformEXT e, com
    ela, o `#extension GL_NV_gpu_shader5 : require` espurio emitido pelo
    spirv-cross (causa dos 6 RasterPS*).

Uso:
  python3 m1_1_apply_gles_macros.py apply    # backup + aplica
  python3 m1_1_apply_gles_macros.py revert   # restaura do backup
  python3 m1_1_apply_gles_macros.py check    # mostra marcadores presentes
"""
import hashlib
import os
import shutil
import sys

SRC = '/root/bhrecomp/lib/rt64/src'
OUT = '/root/bhrecomp/m1_1_gles'
BACKUP = os.path.join(OUT, 'backup_src')

F_HSL_HLSL = os.path.join(SRC, 'shared', 'rt64_hlsl.h')
F_FBRENDER = os.path.join(SRC, 'shaders', 'FbRendererCommon.hlsli')
F_DECODER = os.path.join(SRC, 'shaders', 'TextureDecoder.hlsli')
F_REINTERP = os.path.join(SRC, 'shaders', 'FbReinterpretCS.hlsl')
F_DECODECS = os.path.join(SRC, 'shaders', 'TextureDecodeCS.hlsl')

MARKER = 'HLSL_GLES'

# ---------------------------------------------------------------- blocos novos
HLSL_H_OLD = """int select_int(bool cond, int val1, int val2) {
    return select(cond, val1, val2);
}

#endif"""

HLSL_H_NEW = """int select_int(bool cond, int val1, int val2) {
    return select(cond, val1, val2);
}

// M1-GLES -- adaptacoes para o alvo OpenGL ES (ESSL 3.20).
// Ativas apenas com `-D HLSL_GLES`; sem a macro nada muda para DX/VK/MSL.
#ifdef HLSL_GLES
// ESSL 3.20 nao possui texturas 1D nem descriptor indexing. O array de palavras
// de TMEM (1D de uint32) passa a ser ligado como textura 2D de altura 1, e o
// NonUniformResourceIndex passa a ser identidade (elimina a capability
// ShaderNonUniformEXT e a `#extension GL_NV_gpu_shader5` espuria).
#define TMEMTexture Texture2D<uint>
#define tmemLoadTMEM(textureObject, wordIndex) (textureObject).Load(int3(int(wordIndex), 0, 0))
#define NonUniformResourceIndex(index) (index)
#else
#define TMEMTexture Texture1D<uint>
#endif

#endif"""

FBRENDER_OLD = """// Set 2 - TMEM texture cache.
Texture1D<uint> gTMEM[8192] : register(t0, space2);"""

FBRENDER_NEW = """// Set 2 - TMEM texture cache.
TMEMTexture gTMEM[8192] : register(t0, space2);"""

DECODER_OLD_SIG1 = "uint rowSize, Texture1D<uint> TMEM) {"
DECODER_NEW_SIG1 = "uint rowSize, TMEMTexture TMEM) {"

DECODER_OLD_LOAD = "    return TMEM.Load(int2(((finalAddress & maskAddress) | orAddress) & RDP_TMEM_MASK8, 0));"

DECODER_NEW_LOAD = """#ifdef HLSL_GLES
    return tmemLoadTMEM(TMEM, ((finalAddress & maskAddress) | orAddress) & RDP_TMEM_MASK8);
#else
    return TMEM.Load(int2(((finalAddress & maskAddress) | orAddress) & RDP_TMEM_MASK8, 0));
#endif"""

DECODER_OLD_TLUT = "#define loadTLUT(paletteAddress) TMEM.Load(uint2((paletteAddress) & RDP_TMEM_MASK8, 0))"

DECODER_NEW_TLUT = """#ifdef HLSL_GLES
#define loadTLUT(paletteAddress) tmemLoadTMEM(TMEM, (paletteAddress) & RDP_TMEM_MASK8)
#else
#define loadTLUT(paletteAddress) TMEM.Load(uint2((paletteAddress) & RDP_TMEM_MASK8, 0))
#endif"""

DECODER_OLD_SIG2 = "uint tlut, uint palette, Texture1D<uint> TMEM) {"
DECODER_NEW_SIG2 = "uint tlut, uint palette, TMEMTexture TMEM) {"

REINTERP_OLD_DECL = "Texture1D<uint> gInputTLUT : register(t2);"
REINTERP_NEW_DECL = "TMEMTexture gInputTLUT : register(t2);"
REINTERP_OLD_LOCAL = "    Texture1D<uint> TMEM = gInputTLUT;"
REINTERP_NEW_LOCAL = "    TMEMTexture TMEM = gInputTLUT;"

DECODECS_OLD = "Texture1D<uint> TMEM : register(t1);"
DECODECS_NEW = "TMEMTexture TMEM : register(t1);"

# (arquivo, texto_antigo, texto_novo)
EDITS = [
    (F_HSL_HLSL, HLSL_H_OLD, HLSL_H_NEW),
    (F_FBRENDER, FBRENDER_OLD, FBRENDER_NEW),
    (F_DECODER, DECODER_OLD_SIG1, DECODER_NEW_SIG1),
    (F_DECODER, DECODER_OLD_LOAD, DECODER_NEW_LOAD),
    (F_DECODER, DECODER_OLD_TLUT, DECODER_NEW_TLUT),
    (F_DECODER, DECODER_OLD_SIG2, DECODER_NEW_SIG2),
    (F_REINTERP, REINTERP_OLD_DECL, REINTERP_NEW_DECL),
    (F_REINTERP, REINTERP_OLD_LOCAL, REINTERP_NEW_LOCAL),
    (F_DECODECS, DECODECS_OLD, DECODECS_NEW),
]


def md5(path):
    with open(path, 'rb') as fh:
        return hashlib.md5(fh.read()).hexdigest()


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def do_backup(files):
    os.makedirs(BACKUP, exist_ok=True)
    md5s = []
    for f in files:
        dst = os.path.join(BACKUP, os.path.basename(f))
        if not os.path.exists(dst):
            shutil.copy2(f, dst)
        md5s.append('%s  %s' % (md5(dst), os.path.basename(dst)))
    with open(os.path.join(OUT, 'md5_src_backup.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md5s) + '\n')
    return md5s


def apply():
    files = sorted({f for f, _, _ in EDITS})
    os.makedirs(OUT, exist_ok=True)
    before = {f: md5(f) for f in files}
    backup = do_backup(files)
    print('backup dos fontes: %s' % BACKUP)
    for line in backup:
        print('  %s' % line)

    per_file = {}
    for f, old, new in EDITS:
        per_file.setdefault(f, []).append((old, new))

    ok = True
    for f, edits in per_file.items():
        text = read(f)
        if MARKER in text:
            print('JA APLICADO: %s' % os.path.basename(f))
            continue
        for old, new in edits:
            n = text.count(old)
            if n != 1:
                print('ERRO: %s -> ocorrencias=%d (esperado 1) em %r'
                      % (os.path.basename(f), n, old[:60]))
                ok = False
                continue
            text = text.replace(old, new, 1)
        if ok:
            write(f, text)
            print('OK  %s  %s -> %s' % (os.path.basename(f), before[f], md5(f)))

    after = {f: md5(f) for f in files}
    with open(os.path.join(OUT, 'md5_src_after.txt'), 'w', encoding='utf-8') as fh:
        for f in files:
            fh.write('%s  %s\n' % (after[f], os.path.relpath(f, SRC)))
    print('md5 pos-aplicacao: %s' % os.path.join(OUT, 'md5_src_after.txt'))
    return 0 if ok else 1


def revert():
    files = sorted({f for f, _, _ in EDITS})
    n = 0
    for f in files:
        bak = os.path.join(BACKUP, os.path.basename(f))
        if os.path.exists(bak):
            shutil.copy2(bak, f)
            n += 1
            print('restaurado %s' % f)
    print('%d arquivos restaurados' % n)
    return 0


def check():
    files = sorted({f for f, _, _ in EDITS})
    for f in files:
        text = read(f)
        print('%-28s HLSL_GLES=%d TMEMTexture=%d'
              % (os.path.basename(f), text.count(MARKER), text.count('TMEMTexture')))
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    sys.exit({'apply': apply, 'revert': revert, 'check': check}.get(mode, check)())