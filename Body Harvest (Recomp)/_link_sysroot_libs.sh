#!/bin/bash
SRC=/root/sysroot64/usr/lib/aarch64-linux-gnu
DST=/usr/lib/aarch64-linux-gnu
mkdir -p "$DST"
count=0
for f in "$SRC"/lib*.so*; do
  [ -e "$f" ] || continue
  b=$(basename "$f")
  ln -sf "$SRC/$b" "$DST/$b"
  count=$((count+1))
done
echo "LINKED=$count"
ls "$DST" | grep -E 'SDL2|freetype|vulkan' | head -5
