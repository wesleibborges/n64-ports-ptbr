#!/bin/bash
# M1.3 - Estagio 1 (prova host-side do pipeline de runtime):
#   SPIR-V GLES (build M1.2) -> re-spirv (especializa 5 spec constants) -> spirv-cross --es --version 320
# Mede: tamanho SPIR-V in/out, ESSL nao-especializado vs especializado, tempo de
# re-spirv (reportado pelo CLI) e tempo de spirv-cross (wall clock), validade ESSL 3.20.
# Nao altera nenhuma fonte; so consome artefatos de build.
RS=/root/bhrecomp/build-cmake/re-spirv-cli
SPV=/root/bhrecomp/build-aarch64/src/shaders
OUT=/root/bhrecomp/m1_3_gles/stage1
mkdir -p "$OUT"
printf '%-32s %8s %8s %9s %9s %8s %7s %8s\n' SHADER SPV_IN SPV_OPT ESSL_ORIG ESSL_OPT RESP_ms XCO_ms VALID
for s in RasterPSSpecConstant RasterPSSpecConstantFlat RasterPSSpecConstantMS RasterPSSpecConstantFlatMS RasterVSSpecConstant RasterVSSpecConstantFlat; do
  in="$SPV/$s.hlsl.glsl_es.spv"
  origes="$SPV/$s.hlsl.glsl_es"
  opt="$OUT/$s.opt.spv"
  glsl="$OUT/$s.opt.glsl"
  "$RS" "$in" "$opt" >"$OUT/$s.respv.log" 2>&1
  rms=$(awk '/Optimization time/{print $3}' "$OUT/$s.respv.log")
  st=frag
  case "$s" in
    *VS*) st=vert ;;
  esac
  t0=$(date +%s%N)
  spirv-cross --es --version 320 "$opt" --output "$glsl" 2>"$OUT/$s.xc.err"
  xc_rc=$?
  t1=$(date +%s%N)
  xms=$(( (t1 - t0) / 1000000 ))
  valid=ok
  if [ "$xc_rc" != "0" ]; then
    valid=xC-fail
  else
    glslangValidator -S "$st" "$glsl" >"$OUT/$s.glslang.log" 2>&1
    if [ "$?" != "0" ]; then valid=GLSL-FAIL; fi
  fi
  spv_size=$(stat -c%s "$in")
  opt_size=$(stat -c%s "$opt" 2>/dev/null || echo 0)
  orig_es=$(stat -c%s "$origes" 2>/dev/null || echo 0)
  opt_es=$(stat -c%s "$glsl" 2>/dev/null || echo 0)
  printf '%-32s %8s %8s %9s %9s %8s %7s %8s\n' "$s" "$spv_size" "$opt_size" "$orig_es" "$opt_es" "$rms" "$xms" "$valid"
done
echo "--- arquivos gerados em $OUT ---"
ls -la "$OUT"