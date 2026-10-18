================================================================================
 GLES DEVICE PROBE -- R36S / Mali-G31 (pre-validacao do M3)
================================================================================

O QUE E ISTO
------------
Duas sondas aarch64 que respondem, NO PROPRIO R36S, as perguntas que decidem o
andamento do backend OpenGL ES do port do Body Harvest:

  * o EGL + GLES 3.2 do blob Mali consegue criar contexto real?
  * quais extensoes e limites o driver expoe (BGRA? 16-bit UNORM? MSAA?
    framebuffer fetch? SSBO/UBO? texture units?) -- os numeros que o M3 e o M4
    do plano precisam;
  * o backend plume_gles do port (ja escrito, provado no host com 15/15) roda
    sobre o driver REAL em vez de sobre o llvmpipe do PC?
  * (secao [9] -- a MEDICAO do M3) o compilador do Mali aceita a forma de
    shader que o port gera hoje? Esta e' a pergunta que decide a estrategia do
    M3 "descriptors sem bindless"; o PC nao pode responde-la porque o
    glslangValidator do host e' permissivo (aceita indice dinamico de sampler
    e da' rc=0 ate' sem extensao).

NAO precisa do port, nem de SDL, nem da pasta libs/. Sao binarios estaticos em
relacao a EGL/GLES: resolvem tudo por dlopen em runtime.

CONTEUDO
--------
  gles_device_probe_aarch64  sonda EGL/GLES/GBM, extensoes, limites e readback
  gles_smoke_aarch64         o smoke do backend plume_gles (15 checagens)
  shader_cases/              pares VS+PS em ESSL 3.20 gerados a partir do ESSL
                             DE PRODUCAO do port (secao [9c] da sonda)
  run_gles_probe.sh          runner que executa as duas e gera gles_probe_log.txt
  README.txt                 este arquivo

COMO RODAR (no R36S)
--------------------
  1) copie esta pasta para o cartao SD (por exemplo em /roms/ports/glesprobe/)
  2) sai do EmulationStation (ou pare ele): o probe abre /dev/dri/card0 e o ES
     pode estar segurando o DRM master
  3) por SSH ou no console:
        cd /roms/ports/glesprobe
        sh run_gles_probe.sh
  4) o resultado fica em gles_probe_log.txt -- anexe esse arquivo na evidencia

Se `open_dri_card0` falhar, verifique /dev/dri e se voce e' root; se
`gbm_device` falhar, o ES provavelmente ainda tem o DRM master.

O QUE ESPERAR
-------------
  * `PROBE result=PASS` com `gl_version=OpenGL ES 3.2 ...`  -> EGL/GLES 3.2
    funcionam no device: o M2 esta' satisfeito em hardware e o M3 pode comecar
    com numeros reais.
  * `[8] GBM window surface ... ok` -> a rota exata do SDL/KMSDRM (gbm_surface +
    eglCreateWindowSurface + eglSwapBuffers) funciona; e' o caminho que o port usa.
  * AUSENTE em GL_EXT_texture_norm16 e' o esperado (risco R8 ja' registrado no
    plano). PRESENTE em GL_EXT_texture_format_BGRA8888 muda a leitura do R8.
  * `gl_extensions` e a lista completa do que o driver entrega.
  * SECAO [9] -- a MEDICAO DO M3, o item mais importante deste pacote. O probe
    COMPILA e LINKA, no driver REAL, 10 shaders que reproduzem a forma que o
    port gera hoje e a janela que o M3 quer. Leia a tabela
    "PROBE m3_shader_measurement" e as linhas "compile=... link=...":
      arr8192       a forma ATUAL do M1.3 (sampler2D[8192] indexado por
                    variavel). Se der link=FALHOU, o ESSL do port NAO linka no
                    Mali -- e' exatamente o que o M3 tem de resolver.
      win16         a JANELA desejada (16 samplers) com indice dinamico.
      win16_vary    idem com indice NAO-UNIFORME (por fragmento, o caso real).
      arr16_2x     2 arrays de [16] = 32 samplers (no limite).
      arr16_3x     3 arrays de [16] = 48 samplers -> mostra que o orcamento e'
                   MULTIPLICATIVO (nao basta reduzir N de um array so').
      const_idx_8192 [8192] com indice CONSTANTE: se ISTO linka enquanto
                   arr8192 nao linka, a saida do M3 e' SPECIALIZAR o shader
                   (resolver o indice na compilacao) em vez de indexar em
                   runtime.
      win16_20x     a forma-alvo "20 arrays de [16]" = 320 samplers.
    Referencia medida no PC (llvmpipe/ES 3.2, driver conformante): arr8192,
    arr16_3x, win16_20x e arr8192_20x FALHAM no link ("Too many fragment shader
    texture samplers"); win16, win16_vary, arr16_2x e const_idx_8192 passam.
    Se o Mali divergir disso, a evidencia do M3 registra a divergencia.
  * SECAO [9c] -- o ESSL DE PRODUCAO no compilador do Mali. Em vez de formas
    sinteticas, a sonda compila e LINKA os pares VS+PS reais de `shader_cases/`
    (o mesmo ESSL 3.20 que o build do port gera para o raster PS). Leia
    "PROBE file_shader_measurement" e as linhas "PROBE   prod_...":
      prod_asis          a forma do port hoje (20 arrays de sampler2D[8192]):
                         no PC COMPILA e FALHA no link -- "Too many fragment
                         shader texture samplers";
      prod_spec1x_n8192  os 18 combos de sampler colapsados em 1 array por
                         imagem, janela mantida em 8192;
      prod_spec1x_n32/16/15/8/4
                         idem com a JANELA do M3. No PC (32 texture units) o
                         limite medido foi exatamente N=15: 2 x 15 + 1 sampler
                         escalar = 31 (linka) contra 2 x 16 + 1 = 33 (falha).
                         Ou seja, a regra do M3 e'
                             n_arrays_com_janela x N + n_samplers_escalares
                                 <= GL_MAX_TEXTURE_IMAGE_UNITS
                         e o shader real tem 1 sampler escalar (gBackgroundDepth)
                         alem das 2 arrays, logo a conta NAO e' 2 x N.
    Se o Mali responder compila=FALHOU com "extension not supported", veja a
    extensao abaixo: e' o duplo problema que a secao [9c] expos (o PS escreve 2
    alvos e o GLSL ES exige #extension habilitada).
  * GL_EXT_blend_func_extended -- a extensao que os raster PS do port precisam
    SO' para COMPILAR (eles escrevem `layout(location = 0, index = 1) out`,
    dual-source, para emular o blender do RDP). Medido: o llvmpipe TEM; as
    strings do blob Mali NAO citam. Este run da' a resposta autoritativa. Se o
    Mali nao tiver, o caminho do blender do RDP muda no M4 (nao e' um ajuste de
    shader).

AVISOS IMPORTANTES
------------------
1) NAO existe -- e NAO deve existir -- nenhum libEGL.so* nesta pasta. O stub
   libEGL.so.1 usado apenas durante a COMPILACAO (no PC) fica em
   /root/bhrecomp/m3_gles_probe/stub e nunca e' publicado.
   Se aparecer no device a mensagem
       "*** AVISO: libEGL STUB DE LINK-TIME foi carregada. ***"
   o problema e' o empacotamento / LD_LIBRARY_PATH, nao o backend.
2) O runner zera o LD_LIBRARY_PATH de proposito, justamente para nao herdar o
   `libs/` do port.
3) Estes binarios NAO sao o port: nenhum deles desenha imagem no framebuffer de
   forma visivel (o probe usa pbuffer; o smoke nao tem swap). Rodar o port em si
   e' outro passo (BH_GLES=1 ./BodyHarvest.sh).
4) Se o caminho GBM nao abrir display, o runner repete a sonda SOZINHO com
   --no-gbm (EGL_DEFAULT_DISPLAY puro) e registra um bloco "[1b]" no log.
   Voce pode forcar isso a mao:  ./gles_device_probe_aarch64 --no-gbm
   (ou PROBE_NO_GBM=1 no ambiente).
5) A secao [9] roda sob `timeout 180`: ela manda o compilador do Mali linkar
   shaders de ate' 163.840 samplers -- justamente a forma que o port gera hoje.
   Se o driver travar nisso, o timeout corta e todo o resto do log continua
   valido (e o proprio travamento vira evidencia contra a forma atual).

REPRODUCAO / PROVENIENCIA
-------------------------
  fontes:      evidencias/tools/gles_device_probe.cpp
               evidencias/tools/gles_egl_stub.c
  build:       bash evidencias/tools/m3_build_gles_probe.sh
  empacotar:   bash evidencias/tools/m3_package_gles_probe.sh
  evidencia:   evidencias/evidence_m3_gles_device_probe_20261018.md