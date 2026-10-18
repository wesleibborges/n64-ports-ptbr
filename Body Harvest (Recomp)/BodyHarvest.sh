#!/bin/bash
# PortMaster launcher - Body Harvest (Recomp)
# Log desde a primeira linha: qualquer falha fica registrada.

# Resolve o diretorio absoluto do script (evita caminhos relativos como 'roms2')
SCRIPT_PATH=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
port_dir=$(dirname "$SCRIPT_PATH")
cd "$port_dir" || exit 1

exec > >(tee "$port_dir/log.txt") 2>&1
echo "=== Body Harvest port boot $(date) ==="
echo "SCRIPT_PATH: $SCRIPT_PATH"
echo "PWD: $(pwd)"
uname -a

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

# PortMaster controls (opcional - falha nao interrompe)
if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
fi
echo "controlfolder: $controlfolder"
if [ -n "$controlfolder" ] && [ -f "$controlfolder/control.txt" ]; then
  source "$controlfolder/control.txt" || echo "WARN: control.txt source falhou"
  [ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
  type get_controls >/dev/null 2>&1 && get_controls
fi

# SDL2 2.30 bundled (device tem 2.0.20 sem Vulkan; port precisa de SDL_GetWindowSizeInPixels)
# FAT/exFAT nao preserva symlinks: garante o nome sem versao que o loader procura
if [ ! -e "$port_dir/libs/libSDL2-2.0.so.0" ]; then
  sdlver=$(ls "$port_dir/libs/" 2>/dev/null | grep '^libSDL2-2\.0\.so\.0\.' | head -1)
  if [ -n "$sdlver" ]; then
    ln -s "$sdlver" "$port_dir/libs/libSDL2-2.0.so.0" 2>/dev/null \
      || cp -f "$port_dir/libs/$sdlver" "$port_dir/libs/libSDL2-2.0.so.0"
  fi
fi
export LD_LIBRARY_PATH="$port_dir/libs:$LD_LIBRARY_PATH"
export SDL_GAMECONTROLLERCONFIG="${sdl_controllerconfig:-}"

# resolucao 640x480 (native R36S)
export SDL_VIDEO_WINDOW_POS=0,0

# Vulkan: tenta panvk (kernel 5.x) e cai para lavapipe (software)
export PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1
if [ -z "$VK_ICD_FILENAMES" ] && [ -f "/usr/share/vulkan/icd.d/lvp_icd.json" ]; then
  export VK_ICD_FILENAMES="/usr/share/vulkan/icd.d/lvp_icd.json"
fi
echo "VK_ICD_FILENAMES=$VK_ICD_FILENAMES"

# --- diagnostico de video/vulkan (indispensavel para escolher o backend) ---
echo "--- /dev/dri ---"
ls -l /dev/dri 2>/dev/null || echo "sem /dev/dri"
echo "--- ICDs vulkan ---"
ls -l /usr/share/vulkan/icd.d/ 2>/dev/null || echo "sem /usr/share/vulkan/icd.d"
if [ -d /usr/share/vulkan/icd.d ]; then
  for j in /usr/share/vulkan/icd.d/*.json; do
    [ -f "$j" ] && { echo "[$j]"; cat "$j"; echo; }
  done
fi
if [ -x "$port_dir/vkprobe" ]; then
  VKTO=""
  command -v timeout >/dev/null 2>&1 && VKTO="timeout 5"
  echo "--- vkprobe (ICD herdado do ambiente) ---"
  $VKTO "$port_dir/vkprobe" 2>&1 | grep -E 'VK_ICD|VK_KHR_display|dev\[|physical devices|dlopen|vkCreateInstance'
  if [ -d /usr/share/vulkan/icd.d ]; then
    for j in /usr/share/vulkan/icd.d/*.json; do
      [ -f "$j" ] || continue
      echo "--- vkprobe ICD=$j ---"
      VK_ICD_FILENAMES="$j" $VKTO "$port_dir/vkprobe" 2>&1 | grep -E 'VK_KHR_display|dev\[|physical devices|dlopen|vkCreateInstance'
    done
    # escolhe automaticamente um ICD que suporte VK_KHR_display E exponha device
    icd_display_ok=""
    for j in /usr/share/vulkan/icd.d/*.json; do
      [ -f "$j" ] || continue
      out=$(VK_ICD_FILENAMES="$j" $VKTO "$port_dir/vkprobe" 2>/dev/null)
      if echo "$out" | grep -q 'VK_KHR_display: SIM' && echo "$out" | grep -q 'dev\[0\]'; then
        export VK_ICD_FILENAMES="$j"
        icd_display_ok="$j"
        echo "ICD com VK_KHR_display selecionado: $j"
        break
      fi
    done
    if [ -z "$icd_display_ok" ]; then
      echo "=== DIAGNOSTICO: nenhum ICD expoe VK_KHR_display + device ==="
      echo "O SDL2 no driver KMSDRM usa EXCLUSIVAMENTE VK_KHR_display"
      echo "(vkCreateDisplayPlaneSurfaceKHR). Sem essa extensao a janela Vulkan nao pode"
      echo "ser criada - a falha e do driver, nao do SDL nem do launcher."
      echo "Dados do firmware auditado (dArkOSen 09302026, kernel 4.4.189):"
      echo "  lvp (lavapipe)     : VK_KHR_display NAO / WSI wayland+xcb+xlib+headless"
      echo "  mali (blob ARM)    : VK_KHR_display NAO / WSI nenhum (Vulkan 1.0.x)"
      echo "  panfrost (panvk)   : VK_KHR_display NAO / requer kernel mainline"
      echo "Ref.: evidencias/evidence_firmware_vulkan_audit_20261017.md"
    fi
  fi
fi
# --- recon OpenGL ES: unico caminho com aceleracao de HW neste device ---
# (desligar com BH_NO_GLES_RECON=1)
if [ -x "$port_dir/glesprobe" ] && [ -z "$BH_NO_GLES_RECON" ]; then
  echo "--- glesprobe (SDL KMSDRM + OpenGL ES) ---"
  GLTO=""
  command -v timeout >/dev/null 2>&1 && GLTO="timeout 8"
  SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}" $GLTO "$port_dir/glesprobe" 2>&1 \
    | grep -E 'driver de video ativo|video drivers|contexto GL|GL_VERSION|GL_RENDERER|GL_SHADING_LANGUAGE|GL_MAX_TEXTURE_SIZE|GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS|GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS|extensoes uteis|frames apresentados|RESULTADO|FALHA' \
    || echo "(glesprobe sem saida)"
fi

echo "--- libs vulkan/gbm/drm/mali ---"
ldconfig -p 2>/dev/null | grep -E 'libvulkan|libgbm|libdrm|mali|panfrost' | head -20 || true
echo "--- SDL efetivo ---"
ldd "$port_dir/BodyHarvestRecompiled" 2>/dev/null | grep -E 'SDL2|gtkshim' || true

# pre-flight: verificacao de libs
echo "--- ldd do binario ---"
ldd "$port_dir/BodyHarvestRecompiled" 2>&1 | grep -E 'not found|=>' | head -40 || true
echo "--- fim ldd ---"

savdir="$XDG_DATA_HOME/BodyHarvestRecompiled"
mkdir -p "$savdir/gamedata"
cp -f "$port_dir/gamedata/bodyharvest.us.toml" "$savdir/gamedata/" 2>/dev/null

# --- backend grafico: OpenGL ES 3.2 (M5) ---------------------------------------
# Um unico botao (BH_GLES=1) liga o backend GLES, porque a escolha da API tem DUAS
# pontas que precisam CONCORDAR:
#   (1) a flag da JANELA SDL -> src/main/main.cpp, lida de BH_GRAPHICS_API ANTES de
#       qualquer config (o SDL2 aceita so' uma entre OPENGL/VULKAN/METAL por janela,
#       e esta janela e' criada antes de o RT64 existir);
#   (2) api_option no graphics.json -> recompui/src/renderer/rt64_render_context.cpp,
#       lida DEPOIS que a janela ja' existe.
# Ligar so' uma das duas falha de forma explicita (interface Vulkan sobre janela GL, ou
# SDL_GL_CreateContext falhando) -- e' a pre-condicao registrada no M2 e o risco R11 do
# docs/PLANO_BACKEND_GLES_R36S.md.
#
# Onde vive o graphics.json: o recompui le de get_app_folder_path(), que no device e'
#   $HOME/.config/<program_id>  =  $HOME/.config/bhrecomp
# (program_id = "bhrecomp", em include/bh_config.h; a rota portable.txt/APP_FOLDER_PATH
# nao e' usada aqui). A copia em $port_dir e' mantida em sincronia como referencia.
echo "--- backend grafico (M5) ---"
bh_cfgdir="$HOME/.config/bhrecomp"

bh_set_api() {
  # $1 = "GLES" (teste) ou "Auto" (revert). Template ausente NAO interrompe o boot.
  tmpl="$port_dir/graphics.json.gles"
  if [ "$1" = "Auto" ]; then
    tmpl="$port_dir/graphics.json.auto"
  fi
  if [ ! -f "$tmpl" ]; then
    echo "AVISO: template ausente ($tmpl) -- api_option NAO foi alterada"
    return 1
  fi
  mkdir -p "$bh_cfgdir"
  for d in "$bh_cfgdir" "$port_dir"; do
    cp -f "$tmpl" "$d/graphics.json"
    echo "api_option[$d/graphics.json] = $(grep -o '\"api_option\":[^,]*' "$d/graphics.json" 2>/dev/null)"
  done
}

if [ "$BH_GLES" = "1" ]; then
  export BH_GRAPHICS_API=gles
  echo "backend grafico: OpenGL ES 3.2 (BH_GLES=1) / BH_GRAPHICS_API=$BH_GRAPHICS_API"
  bh_set_api GLES
else
  if [ -n "$BH_GRAPHICS_API" ] && [ "$BH_GRAPHICS_API" != "vulkan" ]; then
    echo "AVISO: BH_GRAPHICS_API='$BH_GRAPHICS_API' sem BH_GLES=1 -- ignorado (use BH_GLES=1)"
  fi
  # Uma execucao GLES anterior deixou api_option=GLES no arquivo. Sem BH_GLES=1 a janela
  # nasce Vulkan, logo esse config derrubaria o boot: reverte para o template Auto.
  if grep -q '"GLES"' "$bh_cfgdir/graphics.json" 2>/dev/null || grep -q '"GLES"' "$port_dir/graphics.json" 2>/dev/null; then
    echo "backend grafico: vulkan/auto (revertendo api_option=GLES de execucao anterior)"
    bh_set_api Auto
  else
    echo "backend grafico: vulkan/auto"
  fi
  unset BH_GRAPHICS_API
fi

chmod +x "$port_dir/BodyHarvestRecompiled" "$port_dir/vkprobe" 2>/dev/null
echo "=== executando ==="
"$port_dir/BodyHarvestRecompiled"
echo "=== EXIT=$? ==="
