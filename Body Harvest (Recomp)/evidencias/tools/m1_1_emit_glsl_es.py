#!/usr/bin/env python3
"""M1.1 - Emite e valida o conjunto GLSL ES 3.20 (GLES) do RT64.

Pipeline por shader:
  1. DXC  (mesmo comando do build.ninja) + `-D HLSL_GLES`  -> <name>.hlsl.spv
  2. spirv-val --target-env vulkan1.0
  3. spirv-cross --es --version 320                        -> <name>.glsl
  4. sanitize() (artefatos do codegen ES)                  -> <name>.glsl (final)
  5. glslangValidator -S <stage>                           (aceite M1.1: rc=0)

Modos:
  gles      emite+valida o conjunto GLES (default)
  regress   recompila os 58 SEM HLSL_GLES e md5-compara com os blobs reais
            (prova de NAO-REGRESSO do caminho DX/VK/MSL)

Flags: --only a,b  --force  --workers N

Detecao de estagio: pelo entry point (`-E PSMain|VSMain|CSMain|GSMain`) do
comando DXC -- o regex por nome de arquivo usado antes era incorreto para os
variantes (RasterPSDynamic, RasterVSSpecConstant, ...) e classificava
vertex shaders como fragment.
"""
import concurrent.futures
import hashlib
import os
import re
import subprocess
import sys

NINJA = '/root/bhrecomp/build-aarch64/build.ninja'
BUILD = '/root/bhrecomp/build-aarch64'
OUT = '/root/bhrecomp/m1_1_gles'
GLSL = os.path.join(OUT, 'glsl')
SPVDIR = os.path.join(OUT, 'spv')
REGRESS = os.path.join(OUT, 'regress')

# Fora do conjunto GLES: ESSL 3.20 proibe `readonly image2D` com E sem format
# qualifier (provado por probe glslang). DebugPS e o shader de debug do caminho
# de ray tracing (RT64 RT), indisponivel em GLES -- usa apenas o caminho raster.
EXCLUDE = {
    'DebugPS.hlsl.spv':
        'usar readonly image2D (imagens de G-buffer do caminho RT); ESSL 3.20 '
        'rejeita image2D com e sem format qualifier -- caminho RT inexistente em GLES',
}

ENTRY_STAGE = {'PSMain': 'frag', 'VSMain': 'vert', 'CSMain': 'comp',
               'GSMain': 'geom', 'RayGenMain': 'rgen', 'RayMissMain': 'rmiss'}


def md5(path):
    with open(path, 'rb') as fh:
        return hashlib.md5(fh.read()).hexdigest()


def collect():
    """Le do build.ninja os comandos DXC (mesma logica do m1_regen_blobs.py)."""
    cmds = []
    with open(NINJA, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if 'COMMAND = cd ' in line and 'dxc-linux' in line and ' /Fo ' in line:
                c = line.split('COMMAND = ', 1)[1].rstrip('\n').replace('\\', '')
                spv = c.rsplit(' /Fo ', 1)[1].strip()
                cmds.append((os.path.basename(spv), c))
    return cmds


def stage_of(cmd):
    m = re.search(r'-E (\w+)', cmd)
    return ENTRY_STAGE.get(m.group(1), 'frag') if m else 'frag'


def sanitize(text, stage):
    """Corrige artefatos do codegen `spirv-cross --es` (nao ha opcao upstream)."""
    actions = []
    if 'GL_NV_gpu_shader5' in text:
        lines = [ln for ln in text.splitlines()
                 if not ln.strip().startswith('#extension GL_NV_gpu_shader5')]
        text = '\n'.join(lines) + '\n'
        actions.append('nv-ext-stripped')
    if 'index = 1' in text and 'GL_EXT_blend_func_extended' not in text:
        # ACHADO 2026-10-18 (medido em driver ES 3.2 conformante, llvmpipe): os raster PS do RT64
        # escrevem DOIS alvos (SV_TARGET0 + SV_TARGET1) para emular o blender do RDP, e o codegen
        # emite `layout(location = 0, index = 1) out ...` -- qualificador que em GLSL ES **exige**
        # a extensao habilitada. Sem ela o driver recusa: (medido)
        #   `0:166(30): error: index layout qualifier requires EXT_blend_func_extended`
        # O `glslangValidator` NAO pega isso (mesma permissividade que escondeu o orcamento de
        # samplers do M3), logo este `#extension` tem de vir do sanitizador, nao do validador.
        text = text.replace('#version 320 es',
                            '#version 320 es\n#extension GL_EXT_blend_func_extended : require', 1)
        actions.append('blend-func-extended-required')
    if 'noperspective' in text:
        # ESSL nao possui `noperspective`; a interpolacao passa a `smooth`
        # (apenas Im3DVS/overlay de debug do im3d -- impacto cosmetico).
        text = text.replace('noperspective ', '')
        actions.append('noperspective-removed')
    if 'precision mediump float;' in text:
        # RT64 assume fp32 no raster; mediump (fp16 no Mali-G31) degradaria
        # coordenadas de textura e depth.
        text = text.replace('precision mediump float;', 'precision highp float;')
        actions.append('precision-mediump->highp')
    if stage == 'frag' and 'precision ' not in text:
        text = text.replace('#version 320 es', '#version 320 es\nprecision highp float;', 1)
        actions.append('precision-preamble-added')
    return text, actions


def run(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def dxc_for(name, cmd, dst, gles):
    """Reescreve o comando DXC para gravar em `dst` (e opcionalmente -D HLSL_GLES)."""
    c = re.sub(r' /Fo \S+$', '', cmd).strip()
    if gles:
        c += ' -D HLSL_GLES'
    c += ' /Fo ' + dst
    return c


def work_gles(name, cmd, force):
    stage = stage_of(cmd)
    res = {'name': name, 'stage': stage, 'excluded': False, 'dxc': 0, 'val': 0,
           'xc': 0, 'glslang': 0, 'actions': [], 'msg': ''}
    if name in EXCLUDE:
        res['excluded'] = True
        res['msg'] = EXCLUDE[name]
        return res

    spv = os.path.join(SPVDIR, name)
    glsl = os.path.join(GLSL, name[:-len('.spv')] + '.glsl')
    tmpx = glsl + '.raw'

    if force or not (os.path.exists(spv) and os.path.getsize(spv) > 0):
        rc, out = run(['bash', '-c', dxc_for(name, cmd, spv, True)])
        res['dxc'] = rc
        if rc != 0 or not os.path.exists(spv) or os.path.getsize(spv) == 0:
            res['msg'] = 'DXC: ' + out.strip()[:200]
            return res

    rc, out = run(['spirv-val', '--target-env', 'vulkan1.0', spv])
    res['val'] = rc
    if rc != 0:
        res['msg'] = 'spirv-val: ' + out.strip()[:200]
        return res

    if force or not (os.path.exists(glsl) and os.path.getsize(glsl) > 0):
        rc, out = run(['spirv-cross', '--es', '--version', '320', spv,
                       '--output', tmpx])
        res['xc'] = rc
        if rc != 0:
            res['msg'] = 'spirv-cross: ' + out.strip()[:200]
            return res
        with open(tmpx, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        text, actions = sanitize(text, stage)
        res['actions'] = actions
        with open(glsl, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)

    rc, out = run(['glslangValidator', '-S', stage, glsl])
    res['glslang'] = rc
    if rc != 0:
        res['msg'] = out.strip().splitlines()[0][:160] if out.strip() else ''
    return res


def work_regress(name, cmd):
    real = cmd.rsplit(' /Fo ', 1)[1].strip()
    dst = os.path.join(REGRESS, name)
    rc, out = run(['bash', '-c', dxc_for(name, cmd, dst, False)])
    if rc != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
        return (name, 'FAIL', 'DXC: ' + out.strip()[:160])
    a = md5(dst)
    b = md5(real) if os.path.exists(real) else 'ausente'
    return (name, 'SAME' if a == b else 'DIFF', '%s vs %s' % (a, b))


def main():
    argv = sys.argv[1:]
    mode = 'regress' if 'regress' in argv else 'gles'
    force = '--force' in argv
    only = None
    workers = 6
    for i, a in enumerate(argv):
        if a.startswith('--only'):
            only = set(argv[i + 1].split(','))
        elif a.startswith('--workers'):
            workers = int(argv[i + 1])
    for d in (OUT, GLSL, SPVDIR, REGRESS):
        os.makedirs(d, exist_ok=True)

    cmds = collect()
    if only:
        cmds = [c for c in cmds if c[0][:-len('.spv')] in only or c[0] in only]
    print('comandos DXC no build.ninja: %d | processando: %d | modo=%s'
          % (len(collect()), len(cmds), mode))

    if mode == 'regress':
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda it: work_regress(*it), cmds))
        same = [r for r in results if r[1] == 'SAME']
        diff = [r for r in results if r[1] == 'DIFF']
        fail = [r for r in results if r[1] == 'FAIL']
        with open(os.path.join(OUT, 'regress_dx.tsv'), 'w', encoding='utf-8') as fh:
            fh.write('shader\tstatus\tmd5\n')
            for n, s, i in results:
                fh.write('%s\t%s\t%s\n' % (n, s, i))
        for n, s, i in results:
            if s != 'SAME':
                print('%-5s %-38s %s' % (s, n, i))
        print('RESUMO REGRESS: identicos=%d divergentes=%d falhas=%d'
              % (len(same), len(diff), len(fail)))
        return 1 if (diff or fail) else 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(lambda it: work_gles(it[0], it[1], force), cmds))

    print()
    print('%-32s %-5s %4s %4s %7s %s' % ('shader', 'stage', 'dxc', 'val', 'glslang', 'sanitize'))
    print('-' * 78)
    for r in res:
        if r['excluded']:
            print('%-32s %-5s  EXCLUIDO  %s' % (r['name'], r['stage'], r['msg'][:60]))
            continue
        print('%-32s %-5s %4d %4d %7d %s'
              % (r['name'], r['stage'], r['dxc'], r['val'], r['glslang'],
                 ','.join(r['actions']) or '-'))
        if r['glslang'] != 0:
            print('       ^ %s' % r['msg'])

    act = [r for r in res if not r['excluded']]
    nex = [r for r in res if r['excluded']]
    bad = [r for r in act if r['glslang'] != 0]
    print()
    print('RESUMO M1.1: shaders=%d | excluidos=%d | glslang OK=%d | glslang FALHAS=%d'
          % (len(act), len(nex), len(act) - len(bad), len(bad)))
    if bad:
        for r in bad:
            print('  FALHA %s: %s' % (r['name'], r['msg']))
    if nex:
        for r in nex:
            print('  EXCLUIDO %s: %s' % (r['name'], r['msg']))

    tsv = os.path.join(OUT, 'validacao_gles.tsv')
    with open(tsv, 'w', encoding='utf-8') as fh:
        fh.write('shader\tstage\tdxc\tspirv_val\tglslang\tsanitize_acoes\n')
        for r in res:
            fh.write('%s\t%s\t%s\t%s\t%s\t%s\n'
                     % (r['name'], r['stage'], 'EXCLUIDO' if r['excluded'] else r['dxc'],
                        '-' if r['excluded'] else r['val'],
                        '-' if r['excluded'] else r['glslang'],
                        ','.join(r['actions']) or ('-' if not r['excluded'] else 'excluido')))
    print('tabela: %s' % tsv)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())