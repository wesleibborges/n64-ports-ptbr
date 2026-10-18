#!/bin/bash
sed -n '883p' /root/bhrecomp/build-aarch64/build.ninja | grep -oE '/root/sysroot64[^ ]*' | sort -u > /root/link_paths.txt
missing=0
while IFS= read -r p; do
  [ -e "$p" ] || { echo "MISSING:$p"; missing=$((missing+1)); }
done < /root/link_paths.txt
echo "TOTAL=$(wc -l < /root/link_paths.txt) MISSING=$missing"
