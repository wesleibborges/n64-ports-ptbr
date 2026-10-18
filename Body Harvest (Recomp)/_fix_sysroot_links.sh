#!/bin/bash
# Conserta todos os symlinks quebrados do sysroot arm64
# Para cada symlink quebrado, procura o arquivo real no sysroot e re-aponta.
cd /root/sysroot64 || exit 1
fixed=0
broken=0
while IFS= read -r link; do
  tgt=$(readlink -f "$link")
  if [ ! -e "$tgt" ]; then
    base=$(basename "$link")
    # procurar um real com o mesmo prefixo (ex: libz.so -> libz.so.1.2.11)
    prefix=${base%%.*}
    real=$(find /root/sysroot64 -name "${base}.*" -not -type l 2>/dev/null | head -1)
    if [ -z "$real" ]; then
      real=$(find /root/sysroot64 -name "${prefix}*.so*" -not -type l 2>/dev/null | head -1)
    fi
    if [ -n "$real" ]; then
      ln -sf "$real" "$link"
      fixed=$((fixed+1))
    else
      echo "NO-REAL-FOR:$link"
      broken=$((broken+1))
    fi
  fi
done < <(find /root/sysroot64 -type l ! -exec test -e {} \; -print 2>/dev/null)
echo "FIXED=$fixed STILL_BROKEN=$broken"
