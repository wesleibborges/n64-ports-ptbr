#!/bin/bash
SRC=/root/sysroot64/usr/lib/aarch64-linux-gnu
DST=/usr/aarch64-linux-gnu/lib
mkdir -p "$DST"
count=0
for f in "$SRC"/lib*.so*; do
  [ -e "$f" ] || continue
  real=$(readlink -f "$f")
  [ -e "$real" ] || continue
  b=$(basename "$f")
  ln -sf "$real" "$DST/$b"
  count=$((count+1))
done
# e os .so sem-versao apontando direto pro real
for f in "$SRC"/*.so; do
  [ -L "$f" ] || continue
  real=$(readlink -f "$f")
  [ -e "$real" ] || continue
  b=$(basename "$f")
  ln -sf "$real" "$DST/$b"
  count=$((count+1))
done
echo "LINKED=$count"
