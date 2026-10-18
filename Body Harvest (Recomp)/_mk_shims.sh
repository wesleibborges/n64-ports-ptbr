#!/bin/bash
PC=/root/sysroot64/usr/lib/aarch64-linux-gnu/pkgconfig
for p in shared-mime-info libtiff-4 libb2 libzstd liblzma; do
  if [ ! -f "$PC/$p.pc" ]; then
    printf 'Name: %s\nDescription: shim\nVersion: 1.0\n' "$p" > "$PC/$p.pc"
    echo "created $p.pc"
  fi
done
echo SHIMS-OK
