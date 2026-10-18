=== EVIDENCIA: Reparo das fontes do apt (Ubuntu jammy) ===
Data: 2026-10-16 09:25-09:45 UTC

--- Diagnostico 1: fontes ---
/etc/apt/sources.list: apenas Ubuntu jammy (main/restricted/universe/multiverse + security + backports)
/etc/apt/sources.list.d/arm64.list: 'deb [arch=amd64,arm64] http://deb.debian.org/debian bookworm main' — FONTE DEBIAN com arch amd64 (causa da contaminacao)
Efeito: libc6/libc-dev-bin/locales 2.36-9+deb12u14 (Debian) desempacotados por cima da 2.35-0ubuntu3.15 (estado dpkg iU; libc em disco = Debian 2.36)

--- Correcao 1: fontes ---
cp arm64.list -> /root/backup_arm64.list; rm arm64.list
dpkg --remove-architecture arm64 (sem pacotes arm64 instalados — verificado com dpkg -l | grep :arm64 = vazio)
apt-get update: rc=0, 48 indexes, sem erros

--- Correcao 2: glibc ---
dpkg --purge libc-l10n (pacote Debian-only)
apt-get install -y --allow-downgrades libc6=2.35-0ubuntu3.15 libc-bin=2.35-0ubuntu3.15 libc-dev-bin=2.35-0ubuntu3.15 locales=2.35-0ubuntu3.15
dpkg --configure -a && apt-get check -> rc=0
Verificacao: /lib/x86_64-linux-gnu/libc.so.6 -> 'GNU C Library (Ubuntu GLIBC 2.35-0ubuntu3.15)'

--- Correcao 3: toolchain ---
apt-get install -y gcc-multilib clang -> rc=0 (clang 14.0.0; gcc -m32 com headers funcionando)
gcc-mips-linux-gnu NAO instalavel no jammy: metapacote depende gcc-10-mips-linux-gnu, que conflita com gcc-multilib
  -> mantido o plano alternativo: binutils-mips 2.40 (dpkg -x) para as/ld/objcopy + DCC com fallback IDO (build byte-perfect ja provado)
Docker CE 29.9.1 instalado do repo oficial download.docker.com (systemd=true no wsl.conf); docker run hello-world OK; systemctl is-active docker = active

=== CONCLUSAO ===
apt 100% Ubuntu novamente, dpkg consistente (audit vazio), glibc 2.35 restaurada, clang/gcc-multilib/m32 OK, Docker operacional no WSL.

=== EVIDENCIA: Validacao do fluxo Docker (Dockerfile oficial do decomp) ===
Data: 2026-10-16 09:39-09:55 UTC
Comando 1: docker build -q -t bh-local /root/bh   (Dockerfile do repo: ubuntu:22.04 + packages.txt + requirements.txt)
Resultado: BUILD_RC=0, imagem bh-local:latest (278 MB), sha256:263bbb997491...
Comando 2: docker run --rm -v /root/bh:/bh bh-local bash -c "make --jobs > /tmp/inner.log 2>&1 && tail -1 /tmp/inner.log"
Resultado: build/bh.us.z64: OK  (ROM reconstruida byte-perfect DENTRO do container, montando o mesmo diretorio em /bh)
Observacao: dentro da imagem o gcc-mips-linux-gnu instala sem conflito (nao ha gcc-multilib no packages.txt),
confirmando que o container elimina os conflitos de toolchain observados no host.
