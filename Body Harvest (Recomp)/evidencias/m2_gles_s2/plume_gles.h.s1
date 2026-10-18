//
// plume_gles -- backend OpenGL ES 3.2 para o RT64 (porte R36S / Mali-G31).
//
// Copyright (c) 2024 renderbag and contributors. All rights reserved.
// Licensed under the MIT license. See LICENSE file for details.
//
// Este backend existe porque no firmware do R36S (dArkOS, kernel 4.4.189) NAO ha
// Vulkan apresentavel (nenhum ICD expoe VK_KHR_display -- ver
// evidencias/evidence_firmware_vulkan_audit_20261017.md). O unico caminho com
// aceleracao de hardware e OpenGL ES pelo blob ARM (libMali, EGL+GBM), e o modelo
// de entrada de funcoes segue a politica ja validada no M0:
//
//   * nenhum link contra libGLESv2/libEGL/widgets;
//   * todos os entry points vem de SDL_GL_GetProcAddress, via o carregador
//     auto-contido gerado em plume_gles_gl.{h,cpp}.
//
// Molde arquitetural: `plume_metal.cpp` (4.229 LOC), por ser o backend sem
// descriptor indexing real (como o GLES 3.2 do Mali-G31). Ver
// docs/PLANO_BACKEND_GLES_R36S.md, marco M2.
//
// IMPORTANTE (fronteira de dependencia): este header NAO inclui <SDL.h> nem
// headers de GLES. A janela entra como `void *` (SDL_Window*) e os tipos/constantes
// GL vem do carregador gerado. Isso mantem o backend compilavel e testavel no host
// x86_64 -- mesma disciplina usada em src/render/rt64_glsl_es.{h,cpp} no M1.3.
//

#pragma once

#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "plume_render_interface.h"
#include "plume_gles_gl.h"

namespace plume {
    // Os tipos e constantes de GLES vivem em plume::gl (carregador gerado
    // auto-contido) para nunca colidirem com os simbolos reais de libGLESv2.
    // Aqui eles sao reexportados explicitamente em plume, porque este backend
    // escreve `GLenum`/`GLuint`/etc. o tempo todo. Nao se usa
    // `using namespace gl;` para manter a superficie visivel estreita e greppavel.
    using gl::GLbitfield;
    using gl::GLboolean;
    using gl::GLbyte;
    using gl::GLchar;
    using gl::GLclampf;
    using gl::GLDEBUGPROC;
    using gl::GLenum;
    using gl::GLfixed;
    using gl::GLfloat;
    using gl::GLhalf;
    using gl::GLint;
    using gl::GLint64;
    using gl::GLintptr;
    using gl::GLshort;
    using gl::GLsizei;
    using gl::GLsizeiptr;
    using gl::GLsync;
    using gl::GLubyte;
    using gl::GLuint;
    using gl::GLuint64;
    using gl::GLushort;
    using gl::GLvoid;
    // Identificador opaco de objeto GL (nome de textura/buffer/programa/VAO/FBO...).
    typedef uint32_t GLObject;

    static constexpr uint32_t GLES_MAX_COLOR_ATTACHMENTS = 4;
    static constexpr uint32_t GLES_MAX_CLEAR_RECTS = 16;

    struct GLESInterface;
    struct GLESDevice;
    struct GLESCommandQueue;
    struct GLESSwapChain;
    struct GLESCommandList;
    struct GLESBuffer;
    struct GLESTexture;
    struct GLESSampler;
    struct GLESFramebuffer;
    struct GLESDescriptorSet;
    struct GLESPipelineLayout;
    struct GLESShader;

    // Ponteiro para o resolvedor de simbolos do contexto corrente
    // (na pratica SDL_GL_GetProcAddress). Passado pelo chamador para manter SDL
    // fora deste header.
    typedef void *(*GLESProcResolver)(const char *name);

    // Shim de apresentacao. Existe para que este backend NAO inclua <SDL.h>: no GLES
    // a apresentacao e' sempre "swap do backbuffer da janela", e quem conhece a
    // janela e' o chamador (SDL2 no R36S). Manter isso fora do backend preserva a
    // compilacao/teste no host x86_64, que nao tem headers de SDL2 instalados.
    // Os membros podem ser nullptr: o swapchain degrada para glFinish() e reporta
    // tamanho/refresh vindos do GL em vez da janela.
    struct GLESSwapChainFunctions {
        // Equivalente a SDL_GL_SwapWindow(window).
        void (*swapWindow)(void *window) = nullptr;
        // Equivalente a SDL_GL_GetDrawableSize/SDL_GetWindowSize(window, w, h).
        void (*getWindowSize)(void *window, int *width, int *height) = nullptr;
        // Equivalente a SDL_GL_SetSwapInterval(interval).
        void (*setSwapInterval)(int interval) = nullptr;
        // Equivalente a SDL_GetWindowDisplayMode(...).refresh_rate; 0 = desconhecido.
        uint32_t (*getDisplayRefreshRate)(void *window) = nullptr;
    };

    // Cria o contexto GL (chamar com o SDL_Window* ja existente) e devolve a
    // interface. `window` tambem e usado para o swapchain. `procResolver` e'
    // usado para carregar os 358 entry points (na pratica SDL_GL_GetProcAddress).
    std::unique_ptr<RenderInterface> CreateGLESInterface(void *window,
                                                         GLESProcResolver procResolver,
                                                         GLESSwapChainFunctions swapFunctions);

    // Helpers de traducao GLES <-> Plume. Ficam expostos porque o M3/M4 (descriptors
    // e caminho de raster) precisam deles e porque assim podem ser testados no host.
    GLenum toGLESFormat(RenderFormat format);
    GLenum toGLESInternalFormat(RenderFormat format);
    GLenum toGLESType(RenderFormat format);
    GLenum toGLESBlendOp(RenderBlendOperation op);
    GLenum toGLESBlendFactor(RenderBlend factor);
    GLenum toGLESCompareOp(RenderComparisonFunction func);
    GLenum toGLESStencilOp(RenderStencilOp op);
    GLenum toGLESPrimitiveTopology(RenderPrimitiveTopology topology);
    GLenum toGLESIndexFormat(RenderFormat format);
    GLenum toGLESTextureTarget(const RenderTextureDesc &desc);
    GLenum toGLESWrapMode(RenderTextureAddressMode mode);
    GLenum toGLESFilter(RenderFilter filter);
    GLenum toGLESMipmapFilter(RenderMipmapMode filter);
    uint32_t toGLESSampleCount(RenderSampleCounts counts);
    uint32_t getGLESFormatComponentCount(RenderFormat format);

    // =========================================================================
    // Recursos simples
    // =========================================================================

    struct GLESBufferFormattedView : RenderBufferFormattedView {
        GLESBufferFormattedView() { }
    };

    struct GLESBuffer : RenderBuffer {
        GLESDevice *device = nullptr;
        GLObject buffer = 0;              // GL buffer name
        RenderBufferDesc desc;
        uint64_t size = 0;
        bool mapped = false;
        uint64_t mappedOffset = 0;
        uint64_t mappedSize = 0;

        GLESBuffer(GLESDevice *device, const RenderBufferDesc &desc);
        ~GLESBuffer() override;

        void *map(uint32_t subresource = 0, const RenderRange *readRange = nullptr) override;
        void unmap(uint32_t subresource = 0, const RenderRange *writtenRange = nullptr) override;
        std::unique_ptr<RenderBufferFormattedView> createBufferFormattedView(RenderFormat format) override;
        void setName(const std::string &name) override { this->name = name; }
        uint64_t getDeviceAddress() const override { return 0; }

        std::string name;
    };

    struct GLESTextureView : RenderTextureView {
        GLESTextureView() { }
    };

    struct GLESTexture : RenderTexture {
        GLESDevice *device = nullptr;
        GLObject texture = 0;             // GL texture name
        GLenum target = 0;                // GL_TEXTURE_2D, GL_TEXTURE_2D_MULTISAMPLE, ...
        RenderTextureDesc desc;
        uint32_t width = 0;
        uint32_t height = 0;
        uint32_t depth = 0;
        uint32_t mipLevels = 1;
        uint32_t layers = 1;
        bool isSwapChainTexture = false;  // textura "virtual": e o backbuffer default (FBO 0)
        bool owns = true;

        GLESTexture(GLESDevice *device, const RenderTextureDesc &desc);
        GLESTexture(GLESDevice *device, uint32_t width, uint32_t height, RenderFormat format,
                    bool isSwapChainTexture);
        ~GLESTexture() override;

        std::unique_ptr<RenderTextureView> createTextureView(const RenderTextureViewDesc &desc) const override;
        void setName(const std::string &name) override { this->name = name; }

        std::string name;
    };

    struct GLESAccelerationStructure : RenderAccelerationStructure {
        // GLES 3.2 nao tem ray tracing: capacidade `raytracing` e sempre false,
        // logo nenhum codigo do RT64 deve chegar aqui.
    };

    struct GLESShader : RenderShader {
        GLESDevice *device = nullptr;
        GLObject shader = 0;              // GL shader name
        RenderShaderFormat format = RenderShaderFormat::UNKNOWN;

        GLESShader(GLESDevice *device, const void *data, uint64_t size, const char *entryPointName,
                   RenderShaderFormat format);
        ~GLESShader() override;

        void setName(const std::string &name) override { this->name = name; }

        std::string name;
    };

    struct GLESSampler : RenderSampler {
        GLESDevice *device = nullptr;
        RenderSamplerDesc desc;
        // GLES nao tem objeto sampler em versoes antigas; GLES 3.0+ tem
        // glGenSamplers. O Mali-G31 expoe GLES 3.2, logo usamos o objeto real.
        GLObject sampler = 0;

        GLESSampler(GLESDevice *device, const RenderSamplerDesc &desc);
        ~GLESSampler() override;
    };

    struct GLESPipeline : RenderPipeline {
        enum class Type {
            Unknown,
            Compute,
            Graphics,
            Raytracing
        };

        GLESDevice *device = nullptr;
        Type type = Type::Unknown;

        GLESPipeline(GLESDevice *device, Type type);
        ~GLESPipeline() override;
    };

    struct GLESComputePipeline : GLESPipeline {
        GLObject program = 0;

        GLESComputePipeline(GLESDevice *device, const RenderComputePipelineDesc &desc);
        ~GLESComputePipeline() override;
        void setName(const std::string &name) override;
        RenderPipelineProgram getProgram(const std::string &name) const override;

        std::string name;
    };

    struct GLESGraphicsPipeline : GLESPipeline {
        GLObject program = 0;

        GLESGraphicsPipeline(GLESDevice *device, const RenderGraphicsPipelineDesc &desc);
        ~GLESGraphicsPipeline() override;
        void setName(const std::string &name) override;
        RenderPipelineProgram getProgram(const std::string &name) const override;

        std::string name;
    };

    struct GLESPipelineLayout : RenderPipelineLayout {
        GLESDevice *device = nullptr;
        std::vector<RenderPushConstantRange> pushConstantRanges;
        uint32_t setLayoutCount = 0;

        GLESPipelineLayout(GLESDevice *device, const RenderPipelineLayoutDesc &desc);
        ~GLESPipelineLayout() override;
    };

    // =========================================================================
    // Command list
    // =========================================================================
    //
    // DECISAO DE DESENHO (M2, sessao 1) -- gravar-para-depois (deferred) fica para
    // o M3/M4. O GL e uma API de estado IMEDIATA: um "command list" do GLES nao tem
    // equivalente direto ao command buffer do Vulkan/Metal. Aqui os metodos de
    // estado/desenho EXECUTAM as chamadas GL na hora (na thread dona do contexto) e
    // begin()/end() apenas gerenciam a janela de estado. Nao ha reordenacao: a ordem
    // de gravacao do RT64 e preservada, porque ele grava e submete um command list
    // por vez. `executeCommandLists()` vira um ponto de sincronizacao (glFlush), nao
    // uma fila de replay.
    //
    // Este atalho e suficiente e comprovavel para o aceite do M2 (clear + swap) e
    // sera reavaliado no M3, quando os pipelines/bindings reais entram.

    struct GLESCommandList : RenderCommandList {
        GLESDevice *device = nullptr;
        GLESCommandQueue *commandQueue = nullptr;
        RenderCommandListType type = RenderCommandListType::DIRECT;
        bool isRecording = false;

        // Estado corrente (espelha o estado GL para evitar chamadas redundantes e
        // para o M3 saber o que ja esta vinculado).
        const GLESFramebuffer *currentFramebuffer = nullptr;
        const GLESGraphicsPipeline *currentGraphicsPipeline = nullptr;
        const GLESComputePipeline *currentComputePipeline = nullptr;
        const GLESPipelineLayout *currentGraphicsPipelineLayout = nullptr;
        const GLESPipelineLayout *currentComputePipelineLayout = nullptr;
        GLESDescriptorSet *currentGraphicsDescriptorSets[8] = {};
        GLESDescriptorSet *currentComputeDescriptorSets[8] = {};
        uint32_t currentGraphicsDescriptorSetCount = 0;
        uint32_t currentComputeDescriptorSetCount = 0;

        GLESCommandList(GLESDevice *device, GLESCommandQueue *commandQueue,
                        RenderCommandListType type);
        ~GLESCommandList() override;

        void begin() override;
        void end() override;
        void barriers(RenderBarrierStages stages, const RenderBufferBarrier *bufferBarriers,
                      uint32_t bufferBarriersCount, const RenderTextureBarrier *textureBarriers,
                      uint32_t textureBarriersCount) override;
        void dispatch(uint32_t threadGroupCountX, uint32_t threadGroupCountY,
                      uint32_t threadGroupCountZ) override;
        void traceRays(uint32_t width, uint32_t height, uint32_t depth,
                       RenderBufferReference shaderBindingTable,
                       const RenderShaderBindingGroupsInfo &shaderBindingGroupsInfo) override;
        void drawInstanced(uint32_t vertexCountPerInstance, uint32_t instanceCount,
                           uint32_t startVertexLocation, uint32_t startInstanceLocation) override;
        void drawIndexedInstanced(uint32_t indexCountPerInstance, uint32_t instanceCount,
                                  uint32_t startIndexLocation, int32_t baseVertexLocation,
                                  uint32_t startInstanceLocation) override;
        void setPipeline(const RenderPipeline *pipeline) override;
        void setComputePipelineLayout(const RenderPipelineLayout *pipelineLayout) override;
        void setComputePushConstants(uint32_t rangeIndex, const void *data, uint32_t offset = 0,
                                     uint32_t size = 0) override;
        void setComputeDescriptorSet(RenderDescriptorSet *descriptorSet, uint32_t setIndex) override;
        void setGraphicsPipelineLayout(const RenderPipelineLayout *pipelineLayout) override;
        void setGraphicsPushConstants(uint32_t rangeIndex, const void *data, uint32_t offset = 0,
                                      uint32_t size = 0) override;
        void setGraphicsDescriptorSet(RenderDescriptorSet *descriptorSet, uint32_t setIndex) override;
        void setGraphicsRootDescriptor(RenderBufferReference bufferReference,
                                       uint32_t rootDescriptorIndex) override;
        void setRaytracingPipelineLayout(const RenderPipelineLayout *pipelineLayout) override;
        void setRaytracingPushConstants(uint32_t rangeIndex, const void *data, uint32_t offset = 0,
                                        uint32_t size = 0) override;
        void setRaytracingDescriptorSet(RenderDescriptorSet *descriptorSet,
                                        uint32_t setIndex) override;
        void setIndexBuffer(const RenderIndexBufferView *view) override;
        void setVertexBuffers(uint32_t startSlot, const RenderVertexBufferView *views,
                              uint32_t viewCount, const RenderInputSlot *inputSlots) override;
        void setViewports(const RenderViewport *viewports, uint32_t count) override;
        void setScissors(const RenderRect *scissorRects, uint32_t count) override;
        void setFramebuffer(const RenderFramebuffer *framebuffer) override;
        void setDepthBias(float depthBias, float depthBiasClamp, float slopeScaledDepthBias) override;
        void clearColor(uint32_t attachmentIndex = 0, RenderColor colorValue = RenderColor(),
                        const RenderRect *clearRects = nullptr,
                        uint32_t clearRectsCount = 0) override;
        void clearDepthStencil(bool clearDepth = true, bool clearStencil = true,
                               float depthValue = 1.0f, uint32_t stencilValue = 0,
                               const RenderRect *clearRects = nullptr,
                               uint32_t clearRectsCount = 0) override;
        void copyBufferRegion(RenderBufferReference dstBuffer, RenderBufferReference srcBuffer,
                              uint64_t size) override;
        void copyTextureRegion(const RenderTextureCopyLocation &dstLocation,
                               const RenderTextureCopyLocation &srcLocation, uint32_t dstX = 0,
                               uint32_t dstY = 0, uint32_t dstZ = 0,
                               const RenderBox *srcBox = nullptr) override;
        void copyBuffer(const RenderBuffer *dstBuffer, const RenderBuffer *srcBuffer) override;
        void copyTexture(const RenderTexture *dstTexture, const RenderTexture *srcTexture) override;
        void resolveTexture(const RenderTexture *dstTexture,
                            const RenderTexture *srcTexture) override;
        void resolveTextureRegion(const RenderTexture *dstTexture, uint32_t dstX, uint32_t dstY,
                                  const RenderTexture *srcTexture,
                                  const RenderRect *srcRect = nullptr,
                                  RenderResolveMode resolveMode = RenderResolveMode::AVERAGE) override;
        void buildBottomLevelAS(const RenderAccelerationStructure *dstAccelerationStructure,
                                RenderBufferReference scratchBuffer,
                                const RenderBottomLevelASBuildInfo &buildInfo) override;
        void buildTopLevelAS(const RenderAccelerationStructure *dstAccelerationStructure,
                             RenderBufferReference scratchBuffer,
                             RenderBufferReference instancesBuffer,
                             const RenderTopLevelASBuildInfo &buildInfo) override;
        void discardTexture(const RenderTexture *texture) override;
        void resetQueryPool(const RenderQueryPool *queryPool, uint32_t queryFirstIndex,
                            uint32_t queryCount) override;
        void writeTimestamp(const RenderQueryPool *queryPool, uint32_t queryIndex) override;

        // Vincula o FBO correto (default para a textura de swapchain, nome GL caso
        // contrario) antes de qualquer desenho/clear.
        void ensureFramebufferBound(const RenderFramebuffer *framebuffer);
    };
struct GLESCommandQueue : RenderCommandQueue {
        GLESDevice *device = nullptr;
        RenderCommandListType type = RenderCommandListType::DIRECT;

        GLESCommandQueue(GLESDevice *device, RenderCommandListType type);
        ~GLESCommandQueue() override;

        std::unique_ptr<RenderCommandList> createCommandList() override;
        std::unique_ptr<RenderSwapChain> createSwapChain(const RenderSwapChainDesc &desc) override;
        void executeCommandLists(const RenderCommandList **commandLists, uint32_t commandListCount,
                                 RenderCommandSemaphore **waitSemaphores = nullptr,
                                 uint32_t waitSemaphoreCount = 0,
                                 RenderCommandSemaphore **signalSemaphores = nullptr,
                                 uint32_t signalSemaphoreCount = 0,
                                 RenderCommandFence *signalFence = nullptr) override;
        void waitForCommandFence(RenderCommandFence *fence) override;
    };

    struct GLESPool : RenderPool {
        GLESDevice *device = nullptr;

        GLESPool(GLESDevice *device, const RenderPoolDesc &desc);
        ~GLESPool() override;

        std::unique_ptr<RenderBuffer> createBuffer(const RenderBufferDesc &desc) override;
        std::unique_ptr<RenderTexture> createTexture(const RenderTextureDesc &desc) override;
    };

    struct GLESQueryPool : RenderQueryPool {
        GLESDevice *device = nullptr;
        std::vector<uint64_t> results;

        GLESQueryPool(GLESDevice *device, uint32_t queryCount);
        ~GLESQueryPool() override;

        void queryResults() override;
        const uint64_t *getResults() const override;
        uint32_t getCount() const override;
    };

    // =========================================================================
    // Device
    // =========================================================================

    struct GLESDevice : RenderDevice {
        GLESProcResolver procResolver = nullptr;
        GLESInterface *renderInterface = nullptr;
        GLESSwapChainFunctions swapFunctions;
        void *window = nullptr;                     // SDL_Window*
        RenderDeviceCapabilities capabilities;
        RenderDeviceDescription description;

        // Identificacao do contexto (para evidencia e para o log do device).
        std::string glVersion;
        std::string glVendor;
        std::string glRenderer;
        std::string glShadingLanguageVersion;
        std::string glExtensions;                   // lista separada por espacos
        bool hasGeometryShaderExt = false;
        bool hasKHRDebugExt = false;
        uint32_t maxTextureSize = 0;
        uint32_t maxColorAttachments = 0;
        uint32_t maxSamples = 0;
        uint32_t maxTextureImageUnits = 0;
        uint32_t maxVertexTextureImageUnits = 0;
        uint32_t maxUniformBufferBindings = 0;
        uint32_t maxShaderStorageBufferBindings = 0;
        uint32_t maxComputeWorkGroupInvocations = 0;
        uint32_t maxVertexAttribs = 0;

        GLESDevice(GLESProcResolver procResolver, GLESInterface *renderInterface, void *window,
                   const GLESSwapChainFunctions &swapFunctions);
        ~GLESDevice() override;

        std::unique_ptr<RenderDescriptorSet> createDescriptorSet(
            const RenderDescriptorSetDesc &desc) override;
        std::unique_ptr<RenderShader> createShader(const void *data, uint64_t size,
                                                   const char *entryPointName,
                                                   RenderShaderFormat format) override;
        std::unique_ptr<RenderSampler> createSampler(const RenderSamplerDesc &desc) override;
        std::unique_ptr<RenderPipeline> createComputePipeline(
            const RenderComputePipelineDesc &desc) override;
        std::unique_ptr<RenderPipeline> createGraphicsPipeline(
            const RenderGraphicsPipelineDesc &desc) override;
        std::unique_ptr<RenderPipeline> createRaytracingPipeline(
            const RenderRaytracingPipelineDesc &desc,
            const RenderPipeline *previousPipeline = nullptr) override;
        std::unique_ptr<RenderCommandQueue> createCommandQueue(RenderCommandListType type) override;
        std::unique_ptr<RenderBuffer> createBuffer(const RenderBufferDesc &desc) override;
        std::unique_ptr<RenderTexture> createTexture(const RenderTextureDesc &desc) override;
        std::unique_ptr<RenderAccelerationStructure> createAccelerationStructure(
            const RenderAccelerationStructureDesc &desc) override;
        std::unique_ptr<RenderPool> createPool(const RenderPoolDesc &desc) override;
        std::unique_ptr<RenderPipelineLayout> createPipelineLayout(
            const RenderPipelineLayoutDesc &desc) override;
        std::unique_ptr<RenderCommandFence> createCommandFence() override;
        std::unique_ptr<RenderCommandSemaphore> createCommandSemaphore() override;
        std::unique_ptr<RenderFramebuffer> createFramebuffer(
            const RenderFramebufferDesc &desc) override;
        std::unique_ptr<RenderQueryPool> createQueryPool(uint32_t queryCount) override;
        void setBottomLevelASBuildInfo(RenderBottomLevelASBuildInfo &buildInfo,
                                       const RenderBottomLevelASMesh *meshes, uint32_t meshCount,
                                       bool preferFastBuild = true,
                                       bool preferFastTrace = false) override;
        void setTopLevelASBuildInfo(RenderTopLevelASBuildInfo &buildInfo,
                                    const RenderTopLevelASInstance *instances,
                                    uint32_t instanceCount, bool preferFastBuild = true,
                                    bool preferFastTrace = false) override;
        void setShaderBindingTableInfo(RenderShaderBindingTableInfo &tableInfo,
                                       const RenderShaderBindingGroups &groups,
                                       const RenderPipeline *pipeline,
                                       RenderDescriptorSet **descriptorSets,
                                       uint32_t descriptorSetCount) override;
        const RenderDeviceCapabilities &getCapabilities() const override;
        const RenderDeviceDescription &getDescription() const override;
        RenderSampleCounts getSampleCountsSupported(RenderFormat format) const override;
        bool beginCapture() override;
        bool endCapture() override;

        // Consultas de contexto usadas na inicializacao e pelo smoke test.
        void queryContextInfo();
        bool hasExtension(const char *name) const;
        bool validateShaderFormat(RenderShaderFormat format) const;
    };

    // =========================================================================
    // Interface
    // =========================================================================

    struct GLESInterface : RenderInterface {
        GLESInterface(void *window, GLESProcResolver procResolver,
                      GLESSwapChainFunctions swapFunctions);
        ~GLESInterface() override;

        std::unique_ptr<RenderDevice> createDevice(
            const std::string &preferredDeviceName = "") override;
        const std::vector<std::string> &getDeviceNames() const override;
        const RenderInterfaceCapabilities &getCapabilities() const override;

        void *window = nullptr;                     // SDL_Window*
        GLESProcResolver procResolver = nullptr;
        GLESSwapChainFunctions swapFunctions;
        std::vector<std::string> deviceNames;
        RenderInterfaceCapabilities capabilities;
    };

    struct GLESCommandFence : RenderCommandFence {
        GLESDevice *device = nullptr;

        GLESCommandFence(GLESDevice *device);
        ~GLESCommandFence() override;
    };

    struct GLESCommandSemaphore : RenderCommandSemaphore {
        GLESDevice *device = nullptr;

        GLESCommandSemaphore(GLESDevice *device);
        ~GLESCommandSemaphore() override;
    };

    struct GLESDescriptorSet : RenderDescriptorSet {
        GLESDevice *device = nullptr;
        RenderDescriptorSetDesc desc;
        // M3 substitui isto pela janela de N texturas + remap no CPU.
        std::vector<const RenderBuffer *> buffers;
        std::vector<const RenderTexture *> textures;
        std::vector<const RenderSampler *> samplers;

        GLESDescriptorSet(GLESDevice *device, const RenderDescriptorSetDesc &desc);
        ~GLESDescriptorSet() override;

        void setBuffer(uint32_t descriptorIndex, const RenderBuffer *buffer, uint64_t bufferSize = 0,
                       const RenderBufferStructuredView *bufferStructuredView = nullptr,
                       const RenderBufferFormattedView *bufferFormattedView = nullptr) override;
        void setTexture(uint32_t descriptorIndex, const RenderTexture *texture,
                        RenderTextureLayout textureLayout,
                        const RenderTextureView *textureView = nullptr) override;
        void setSampler(uint32_t descriptorIndex, const RenderSampler *sampler) override;
        void setAccelerationStructure(uint32_t descriptorIndex,
                                      const RenderAccelerationStructure *accelerationStructure) override;
    };

    struct GLESFramebuffer : RenderFramebuffer {
        GLESDevice *device = nullptr;
        RenderFramebufferDesc desc;
        GLObject framebuffer = 0;         // GL framebuffer name (0 = default/backbuffer)
        uint32_t width = 0;
        uint32_t height = 0;

        GLESFramebuffer(GLESDevice *device, const RenderFramebufferDesc &desc);
        ~GLESFramebuffer() override;

        uint32_t getWidth() const override { return width; }
        uint32_t getHeight() const override { return height; }
    };

    struct GLESSwapChain : RenderSwapChain {
        GLESDevice *device = nullptr;
        GLESSwapChainFunctions swapFunctions;
        RenderSwapChainDesc desc;
        void *window = nullptr;           // SDL_Window*
        uint32_t width = 0;
        uint32_t height = 0;
        uint32_t textureIndex = 0;
        bool vsyncEnabled = true;
        bool presentPending = false;
        std::unique_ptr<GLESTexture> backBuffer;   // textura "virtual" do default FB

        GLESSwapChain(GLESDevice *device, void *window, const GLESSwapChainFunctions &swapFunctions,
                      const RenderSwapChainDesc &desc);
        ~GLESSwapChain() override;

        bool present(uint32_t textureIndex, RenderCommandSemaphore **waitSemaphores,
                     uint32_t waitSemaphoreCount) override;
        void wait() override;
        bool resize() override;
        bool needsResize() const override;
        void setVsyncEnabled(bool vsyncEnabled) override;
        bool isVsyncEnabled() const override;
        uint32_t getWidth() const override;
        uint32_t getHeight() const override;
        RenderTexture *getTexture(uint32_t textureIndex) override;
        uint32_t getTextureCount() const override;
        bool acquireTexture(RenderCommandSemaphore *signalSemaphore, uint32_t *textureIndex) override;
        RenderWindow getWindow() const override;
        bool isEmpty() const override;
        uint32_t getRefreshRate() const override;
    };
};