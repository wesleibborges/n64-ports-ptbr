#!/bin/bash
# Baixa e extrai closure dev do GTK3 para o sysroot arm64
set -x
cd /root/debs64 || exit 1
PKGS="libgtk-3-dev libglib2.0-dev libgdk-pixbuf-2.0-dev libpango1.0-dev libatk1.0-dev libcairo2-dev libharfbuzz-dev libx11-dev libxext-dev libxrender-dev libxi-dev libxrandr-dev libxfixes-dev libxcursor-dev libxinerama-dev libwayland-dev libxkbcommon-dev libfontconfig1-dev libpng-dev libpixman-1-dev libffi-dev libmount-dev libselinux1-dev libsepol-dev libexpat1-dev libbrotli-dev libdbus-1-dev libudev-dev libpcre2-dev libsysprof-capture-4-dev libgraphite2-dev libfribidi-dev libthai-dev libdatrie-dev libxml2-dev libzstd-dev liblzma-dev libbz2-dev libb2-dev"
apt-get download $PKGS >> /root/gtkdl.log 2>&1
echo "DOWNLOAD_RC=$?" >> /root/gtkdl.log
find /root/debs64 -name '*.deb' > /root/deblist.txt
wc -l /root/deblist.txt >> /root/gtkdl.log
mkdir -p /root/sysroot64
find /root/debs64 -name '*.deb' -exec dpkg-deb -x {} /root/sysroot64/ \;
echo "PC_FILES:" >> /root/gtkdl.log
find /root/sysroot64 -name 'gtk+-3.0.pc' >> /root/gtkdl.log
find /root/sysroot64 -name '*.pc' | wc -l >> /root/gtkdl.log
echo DONE >> /root/gtkdl.log
