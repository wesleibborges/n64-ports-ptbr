#!/usr/bin/env python3
"""M1 - Regenera os 58 blobs SPIR-V do RT64 executando os comandos DXC EXATOS do
build.ninja (a forma autoritativa, com `/Fo <path>` em dois tokens).

Motivacao: o `lib/rt64/CMakeLists.txt` declara apenas `DEPENDS ${FILENAME}` (.hlsl)
nos add_custom_command do DXC. Os headers inclusos via `-I` NAO entram nas
dependencias do ninja, portanto alterar os headers de layout NAO dispara o DXC.
Por isso os 58 blobs foram invalidados e sao regenerados aqui, sem depender do
build C++ (que reconstroi o restante do binario em paralelo).

Retomavel: blobs ja gerados (nao-vazios) sao pulados.

Uso: python3 m1_regen_blobs.py [workers=6]
"""
import concurrent.futures
import os
import subprocess
import sys
import time

NINJA = '/root/bhrecomp/build-aarch64/build.ninja'
OUT = '/root/bhrecomp/m1_apply_20261018'
LOG = os.path.join(OUT, 'dxc_regen.log')
BUILD = '/root/bhrecomp/build-aarch64'

WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 6


def collect():
    cmds = []
    with open(NINJA, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if 'COMMAND = cd ' in line and 'dxc-linux' in line and ' /Fo ' in line:
                c = line.split('COMMAND = ', 1)[1].rstrip('\n').replace('\\', '')
                spv = c.rsplit(' /Fo ', 1)[1].strip()
                cmds.append((spv, c))
    return cmds


def run(item):
    spv, cmd = item
    if os.path.exists(spv) and os.path.getsize(spv) > 0:
        return ('skip', spv, '')
    t0 = time.time()
    proc = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
    dt = time.time() - t0
    ok = os.path.exists(spv) and os.path.getsize(spv) > 0 and proc.returncode == 0
    err = (proc.stderr or proc.stdout or '').strip()[:400]
    return ('ok' if ok else 'FAIL', spv, '%s (%.1fs rc=%d)' % (err, dt, proc.returncode))


def main():
    os.makedirs(OUT, exist_ok=True)
    cmds = collect()
    print('comandos DXC encontrados no build.ninja: %d' % len(cmds))
    if not cmds:
        return 1

    done = {'skip': 0, 'ok': 0, 'FAIL': 0}
    fails = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for status, spv, info in ex.map(run, cmds):
            done[status] += 1
            name = os.path.basename(spv)
            print('%-5s %s %s' % (status, name, '' if status != 'FAIL' else info))
            if status == 'FAIL':
                fails.append((name, info))

    total = len([1 for s, _ in cmds]) if False else len(cmds)
    present = sum(1 for spv, _ in cmds
                  if os.path.exists(spv) and os.path.getsize(spv) > 0)
    print()
    print('gerados agora: %d | ja existiam: %d | falhas: %d'
          % (done['ok'], done['skip'], done['FAIL']))
    print('blobs presentes: %d / %d' % (present, total))
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write('# execucao %s — ok=%d skip=%d fail=%d presentes=%d/%d\n'
                 % (time.strftime('%Y-%m-%dT%H:%M:%S'), done['ok'], done['skip'],
                    done['FAIL'], present, total))
        for name, info in fails:
            fh.write('FAIL %s %s\n' % (name, info))
    return 0 if done['FAIL'] == 0 and present == total else 1


if __name__ == '__main__':
    sys.exit(main())