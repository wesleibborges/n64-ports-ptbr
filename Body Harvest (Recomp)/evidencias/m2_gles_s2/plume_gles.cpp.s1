//
// plume_gles -- implementacao do backend OpenGL ES 3.2 (ver plume_gles.h).
//
// Copyright (c) 2024 renderbag and contributors. All rights reserved.
// Licensed under the MIT license. See LICENSE file for details.
//
// Escopo desta etapa (M2, sessao 1): infraestrutura + apresentacao. O caminho
// completo de raster (pipelines, descriptors, TMEM, framebuffer fetch) e' M3/M4.
// Tudo que ainda nao existe responde por `unimplemented()`, que ABORTA com
// mensagem -- nunca falha em silencio. Ver docs/PLANO_BACKEND_GLES_R36S.md.
//
// Nao inclui <SDL.h>: janela e apresentacao entram por GLESSwapChainFunctions.
// Isso mantem este arquivo compilavel no host x86_64 (sem sysroot, sem SDL2).
//

#include "plume_gles.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace plume {
    // Entry points de GLES. Os PONTEIROS vivem em plume::gl (carregados por
    // gl::load() com SDL_GL_GetProcAddress) e os tipos foram reexportados em plume
    // pelo header. Este using-directive vale apenas para este TU e permite escrever
    // `glClearColor(...)` como na documentacao oficial da API.
    using namespace gl;

    namespace {
        // Ponto unico de "isso ainda nao existe". Falha de forma barulhenta porque um
        // backend que ignora silenciosamente um comando produz corrupcao de imagem
        // dificil de rastrear -- e, no M2, um stub silencioso esconderia que o
        // caminho testado nao e' o caminho real.
        [[noreturn]] void unimplemented(const char *what) {
            std::fprintf(stderr,
                         "[plume_gles] FATAL: '%s' ainda nao implementado nesta etapa "
                         "(M2 sessao 1). Ver docs/PLANO_BACKEND_GLES_R36S.md.\n", what);
            std::fflush(stderr);
            std::abort();
        }
    }

    // =========================================================================
    // Traducao de enums Plume -> GLES
    // =========================================================================
    //
    // Os casos nao mapeados caem em `unimplemented()` de proposito: um mapeamento
    // adivinhado geraria estado GL errado sem aviso. O conjunto mapeado aqui e' o
    // que os shaders/passes do RT64 realmente usam (8/16/32 bits por componente).

    GLenum toGLESFilter(RenderFilter filter) {
        switch (filter) {
        case RenderFilter::NEAREST: return GL_NEAREST;
        case RenderFilter::LINEAR: return GL_LINEAR;
        default: unimplemented("toGLESFilter(UNKNOWN)");
        }
    }

    GLenum toGLESMipmapFilter(RenderMipmapMode filter) {
        switch (filter) {
        case RenderMipmapMode::NEAREST: return GL_NEAREST_MIPMAP_NEAREST;
        case RenderMipmapMode::LINEAR: return GL_LINEAR_MIPMAP_LINEAR;
        default: unimplemented("toGLESMipmapFilter(UNKNOWN)");
        }
    }

    GLenum toGLESWrapMode(RenderTextureAddressMode mode) {
        switch (mode) {
        case RenderTextureAddressMode::WRAP: return GL_REPEAT;
        case RenderTextureAddressMode::MIRROR: return GL_MIRRORED_REPEAT;
        case RenderTextureAddressMode::CLAMP: return GL_CLAMP_TO_EDGE;
        case RenderTextureAddressMode::BORDER: return GL_CLAMP_TO_EDGE;
        // ATENCAO: GLES 3.2 NAO tem GL_MIRROR_CLAMP_TO_EDGE (isso e' o
        // `samplerMirrorClampToEdge` do Vulkan, que fica false em getCapabilities).
        // M3 deve tratar MIRROR_ONCE com fallback explicito; por ora falha alto.
        default: unimplemented("toGLESWrapMode(MIRROR_ONCE)");
        }
    }

    GLenum toGLESCompareOp(RenderComparisonFunction func) {
        switch (func) {
        case RenderComparisonFunction::NEVER: return GL_NEVER;
        case RenderComparisonFunction::LESS: return GL_LESS;
        case RenderComparisonFunction::EQUAL: return GL_EQUAL;
        case RenderComparisonFunction::LESS_EQUAL: return GL_LEQUAL;
        case RenderComparisonFunction::GREATER: return GL_GREATER;
        case RenderComparisonFunction::NOT_EQUAL: return GL_NOTEQUAL;
        case RenderComparisonFunction::GREATER_EQUAL: return GL_GEQUAL;
        case RenderComparisonFunction::ALWAYS: return GL_ALWAYS;
        default: unimplemented("toGLESCompareOp(UNKNOWN)");
        }
    }

    GLenum toGLESBlendOp(RenderBlendOperation op) {
        switch (op) {
        case RenderBlendOperation::ADD: return GL_FUNC_ADD;
        case RenderBlendOperation::SUBTRACT: return GL_FUNC_SUBTRACT;
        case RenderBlendOperation::REV_SUBTRACT: return GL_FUNC_REVERSE_SUBTRACT;
        case RenderBlendOperation::MIN: return GL_MIN;
        case RenderBlendOperation::MAX: return GL_MAX;
        default: unimplemented("toGLESBlendOp(UNKNOWN)");
        }
    }

    GLenum toGLESBlendFactor(RenderBlend factor) {
        switch (factor) {
        case RenderBlend::ZERO: return GL_ZERO;
        case RenderBlend::ONE: return GL_ONE;
        case RenderBlend::SRC_COLOR: return GL_SRC_COLOR;
        case RenderBlend::INV_SRC_COLOR: return GL_ONE_MINUS_SRC_COLOR;
        case RenderBlend::SRC_ALPHA: return GL_SRC_ALPHA;
        case RenderBlend::INV_SRC_ALPHA: return GL_ONE_MINUS_SRC_ALPHA;
        case RenderBlend::DEST_ALPHA: return GL_DST_ALPHA;
        case RenderBlend::INV_DEST_ALPHA: return GL_ONE_MINUS_DST_ALPHA;
        case RenderBlend::DEST_COLOR: return GL_DST_COLOR;
        case RenderBlend::INV_DEST_COLOR: return GL_ONE_MINUS_DST_COLOR;
        case RenderBlend::SRC_ALPHA_SAT: return GL_SRC_ALPHA_SATURATE;
        default: unimplemented("toGLESBlendFactor(UNKNOWN)");
        }
    }

    GLenum toGLESStencilOp(RenderStencilOp op) {
        switch (op) {
        case RenderStencilOp::KEEP: return GL_KEEP;
        case RenderStencilOp::ZERO: return GL_ZERO;
        case RenderStencilOp::REPLACE: return GL_REPLACE;
        case RenderStencilOp::INCREMENT_AND_CLAMP: return GL_INCR;
        case RenderStencilOp::DECREMENT_AND_CLAMP: return GL_DECR;
        case RenderStencilOp::INVERT: return GL_INVERT;
        case RenderStencilOp::INCREMENT_AND_WRAP: return GL_INCR_WRAP;
        case RenderStencilOp::DECREMENT_AND_WRAP: return GL_DECR_WRAP;
        default: unimplemented("toGLESStencilOp(UNKNOWN)");
        }
    }

    GLenum toGLESPrimitiveTopology(RenderPrimitiveTopology topology) {
        switch (topology) {
        case RenderPrimitiveTopology::POINT_LIST: return GL_POINTS;
        case RenderPrimitiveTopology::LINE_LIST: return GL_LINES;
        case RenderPrimitiveTopology::LINE_STRIP: return GL_LINE_STRIP;
        case RenderPrimitiveTopology::TRIANGLE_LIST: return GL_TRIANGLES;
        case RenderPrimitiveTopology::TRIANGLE_STRIP: return GL_TRIANGLE_STRIP;
        case RenderPrimitiveTopology::TRIANGLE_FAN: return GL_TRIANGLE_FAN;
        default: unimplemented("toGLESPrimitiveTopology(UNKNOWN)");
        }
    }

    GLenum toGLESIndexFormat(RenderFormat format) {
        switch (format) {
        case RenderFormat::R16_UNORM: return GL_UNSIGNED_SHORT;
        case RenderFormat::R32_UINT: return GL_UNSIGNED_INT;
        default: unimplemented("toGLESIndexFormat(formato nao-index)");
        }
    }

    uint32_t toGLESSampleCount(RenderSampleCounts counts) {
        // RenderSampleCounts e' um bitmask cujo valor ja e' o numero de amostras
        // (COUNT_1=0x1, COUNT_2=0x2, COUNT_4=0x4, ...). Aqui apenas validamos que a
        // capacidade esta entre as suportadas pelo ES 3.2.
        switch (counts) {
        case RenderSampleCount::COUNT_1:
        case RenderSampleCount::COUNT_2:
        case RenderSampleCount::COUNT_4:
        case RenderSampleCount::COUNT_8:
            return counts;
        default:
            unimplemented("toGLESSampleCount(>8 amostras)");
        }
    }

    uint32_t getGLESFormatComponentCount(RenderFormat format) {
        switch (format) {
        case RenderFormat::R8G8B8A8_UNORM:
        case RenderFormat::R8G8B8A8_SNORM:
        case RenderFormat::R8G8B8A8_UINT:
        case RenderFormat::R8G8B8A8_SINT:
        case RenderFormat::B8G8R8A8_UNORM:
        case RenderFormat::R16G16B16A16_FLOAT:
        case RenderFormat::R16G16B16A16_UNORM:
        case RenderFormat::R16G16B16A16_SNORM:
        case RenderFormat::R32G32B32A32_FLOAT:
            return 4;
        case RenderFormat::R8G8_UNORM:
        case RenderFormat::R8G8_SNORM:
        case RenderFormat::R16G16_FLOAT:
        case RenderFormat::R16G16_UNORM:
        case RenderFormat::R32G32_FLOAT:
            return 2;
        case RenderFormat::R8_UNORM:
        case RenderFormat::R8_SNORM:
        case RenderFormat::R16_FLOAT:
        case RenderFormat::R16_UNORM:
        case RenderFormat::R32_FLOAT:
        case RenderFormat::D32_FLOAT:
        case RenderFormat::D16_UNORM:
            return 1;
        default:
            unimplemented("getGLESFormatComponentCount(formato nao mapeado)");
        }
    }

    namespace {
        // Tabela unica de mapeamento RenderFormat -> (formato externo, interno, tipo).
        // Mantida num so' lugar para que toGLESFormat/InternalFormat/Type nunca
        // divirjam entre si -- divergencia aqui gera erro de glTexImage2D silencioso.
        struct FormatMapping {
            RenderFormat format;
            GLenum external;
            GLenum internal;
            GLenum type;
        };

        const FormatMapping FORMAT_MAPPINGS[] = {
            { RenderFormat::R8G8B8A8_UNORM,      GL_RGBA,            GL_RGBA8,              GL_UNSIGNED_BYTE },
            { RenderFormat::R8G8B8A8_SNORM,      GL_RGBA,            GL_RGBA8_SNORM,        GL_BYTE },
            { RenderFormat::R8G8B8A8_UINT,       GL_RGBA_INTEGER,    GL_RGBA8UI,            GL_UNSIGNED_BYTE },
            { RenderFormat::R8G8B8A8_SINT,       GL_RGBA_INTEGER,    GL_RGBA8I,             GL_BYTE },
            { RenderFormat::R8G8_UNORM,          GL_RG,              GL_RG8,                GL_UNSIGNED_BYTE },
            { RenderFormat::R8G8_SNORM,          GL_RG,              GL_RG8_SNORM,          GL_BYTE },
            { RenderFormat::R8_UNORM,            GL_RED,             GL_R8,                 GL_UNSIGNED_BYTE },
            { RenderFormat::R8_SNORM,            GL_RED,             GL_R8_SNORM,           GL_BYTE },
            { RenderFormat::R16G16B16A16_FLOAT,  GL_RGBA,            GL_RGBA16F,            GL_HALF_FLOAT },
            { RenderFormat::R16G16_FLOAT,        GL_RG,              GL_RG16F,              GL_HALF_FLOAT },
            { RenderFormat::R16_FLOAT,           GL_RED,             GL_R16F,               GL_HALF_FLOAT },
            { RenderFormat::R32G32B32A32_FLOAT,  GL_RGBA,            GL_RGBA32F,            GL_FLOAT },
            { RenderFormat::R32G32_FLOAT,        GL_RG,              GL_RG32F,              GL_FLOAT },
            { RenderFormat::R32_FLOAT,           GL_RED,             GL_R32F,               GL_FLOAT },
            { RenderFormat::R32_UINT,            GL_RED_INTEGER,     GL_R32UI,              GL_UNSIGNED_INT },
            { RenderFormat::R32_SINT,            GL_RED_INTEGER,     GL_R32I,               GL_INT },
            { RenderFormat::D16_UNORM,           GL_DEPTH_COMPONENT, GL_DEPTH_COMPONENT16,  GL_UNSIGNED_SHORT },
            { RenderFormat::D32_FLOAT,           GL_DEPTH_COMPONENT, GL_DEPTH_COMPONENT32F, GL_FLOAT },
            { RenderFormat::D32_FLOAT_S8_UINT,   GL_DEPTH_STENCIL,   GL_DEPTH32F_STENCIL8,
              GL_FLOAT_32_UNSIGNED_INT_24_8_REV },
        };

        // AUSENTES de proposito (verificado: as constantes NAO existem em GLES3/gl32.h,
        // logo o ES 3.2 core nao os tem):
        //   B8G8R8A8_UNORM            -> sem GL_BGRA em core; exigiria swizzle de textura
        //   R16G16B16A16_UNORM/_SNORM -> sem GL_RGBA16 / GL_RGBA16_SNORM
        //   R16G16_UNORM, R16_UNORM   -> sem GL_RG16 / GL_R16
        // O RT64 usa esses formatos em caminhos de TMEM/framebuffer; o M3/M4 devera'
        // resolve-los com GL_EXT_texture_norm16 (se disponivel no blob) ou downgrade
        // explicito. Ate' lah, caem em unimplemented() -- falha alta, nunca silenciosa.

        const FormatMapping *findFormatMapping(RenderFormat format) {
            for (const FormatMapping &mapping : FORMAT_MAPPINGS) {
                if (mapping.format == format) {
                    return &mapping;
                }
            }

            return nullptr;
        }
    }

    GLenum toGLESFormat(RenderFormat format) {
        const FormatMapping *mapping = findFormatMapping(format);
        if (mapping == nullptr) {
            unimplemented("toGLESFormat(formato nao mapeado)");
        }

        return mapping->external;
    }

    GLenum toGLESInternalFormat(RenderFormat format) {
        const FormatMapping *mapping = findFormatMapping(format);
        if (mapping == nullptr) {
            unimplemented("toGLESInternalFormat(formato nao mapeado)");
        }

        return mapping->internal;
    }

    GLenum toGLESType(RenderFormat format) {
        const FormatMapping *mapping = findFormatMapping(format);
        if (mapping == nullptr) {
            unimplemented("toGLESType(formato nao mapeado)");
        }

        return mapping->type;
    }

    GLenum toGLESTextureTarget(const RenderTextureDesc &desc) {
        // GLES 3.2 nao tem array de textura 1D util para o RT64; o caso 1D do RT64
        // aparece no hardware-resolve (ver rt64_shader_library.cpp, blobs GLES
        // proprios do M1.3). Aqui o mapeamento e' conservador e explicito.
        const RenderSampleCounts sampleCount = desc.multisampling.sampleCount;

        if (sampleCount > RenderSampleCount::COUNT_1 && desc.depth > 1) {
            unimplemented("toGLESTextureTarget(MSAA 3D)");
        }

        if (sampleCount > RenderSampleCount::COUNT_1) {
            return GL_TEXTURE_2D_MULTISAMPLE;
        }

        switch (desc.dimension) {
        case RenderTextureDimension::TEXTURE_2D:
            return (desc.arraySize > 1) ? GL_TEXTURE_2D_ARRAY : GL_TEXTURE_2D;
        case RenderTextureDimension::TEXTURE_3D:
            return GL_TEXTURE_3D;
        default:
            unimplemented("toGLESTextureTarget(TEXTURE_1D/UNKNOWN)");
        }
    }

    // =========================================================================
    // Interface
    // =========================================================================

    GLESInterface::GLESInterface(void *window, GLESProcResolver procResolver,
                                 GLESSwapChainFunctions swapFunctions) {
        this->window = window;
        this->procResolver = procResolver;
        this->swapFunctions = swapFunctions;

        // O RT64 so' deve escolher este backend se o formato declarado for o que os
        // blobs realmente contem (SPIR-V com -D HLSL_GLES, convertidos em runtime).
        // Ver RenderInterfaceCapabilities / CREATE_SHADER_INPUTS.
        capabilities.shaderFormat = RenderShaderFormat::GLSL_ES;

        deviceNames.push_back("OpenGL ES 3.2 (libMali blob / EGL+GBM)");
    }

    GLESInterface::~GLESInterface() {
    }

    std::unique_ptr<RenderDevice> GLESInterface::createDevice(
        const std::string &preferredDeviceName) {
        (void)preferredDeviceName;

        return std::make_unique<GLESDevice>(procResolver, this, window, swapFunctions);
    }

    const std::vector<std::string> &GLESInterface::getDeviceNames() const {
        return deviceNames;
    }

    const RenderInterfaceCapabilities &GLESInterface::getCapabilities() const {
        return capabilities;
    }

    std::unique_ptr<RenderInterface> CreateGLESInterface(void *window,
                                                         GLESProcResolver procResolver,
                                                         GLESSwapChainFunctions swapFunctions) {
        return std::make_unique<GLESInterface>(window, procResolver, swapFunctions);
    }

    // =========================================================================
    // Device
    // =========================================================================

    GLESDevice::GLESDevice(GLESProcResolver procResolver, GLESInterface *renderInterface,
                           void *window, const GLESSwapChainFunctions &swapFunctions) {
        this->procResolver = procResolver;
        this->renderInterface = renderInterface;
        this->window = window;
        this->swapFunctions = swapFunctions;

        // Carrega os 358 entry points do contexto JAH CORRENTE. Falha aqui e' fatal e
        // explicita: sem os simbolos nao ha backend, e um contexto sem entry point
        // core do ES 3.2 indica driver inesperado (nao um caso a tratar em silencio).
        if (!gl::load(procResolver)) {
            const std::vector<std::string> &absent = gl::missing();
            std::fprintf(stderr, "[plume_gles] FATAL: %zu entry points de GLES nao "
                                 "resolvidos pelo contexto corrente.\n", absent.size());
            const size_t limit = (absent.size() < 16) ? absent.size() : 16;
            for (size_t i = 0; i < limit; i++) {
                std::fprintf(stderr, "[plume_gles]   ausente: %s\n", absent[i].c_str());
            }
            std::fflush(stderr);
            std::abort();
        }

        queryContextInfo();
    }

    GLESDevice::~GLESDevice() {
    }

    void GLESDevice::queryContextInfo() {
        const GLubyte *version = glGetString(GL_VERSION);
        const GLubyte *vendor = glGetString(GL_VENDOR);
        const GLubyte *renderer = glGetString(GL_RENDERER);
        const GLubyte *shading = glGetString(GL_SHADING_LANGUAGE_VERSION);

        glVersion = version ? reinterpret_cast<const char *>(version) : "?";
        glVendor = vendor ? reinterpret_cast<const char *>(vendor) : "?";
        glRenderer = renderer ? reinterpret_cast<const char *>(renderer) : "?";
        glShadingLanguageVersion = shading ? reinterpret_cast<const char *>(shading) : "?";

        // Lista de extensoes: ES 3.0+ tem glGetStringi. Alimenta hasExtension() e,
        // por consequencia, as capacidades calculadas abaixo.
        GLint extensionCount = 0;
        glGetIntegerv(GL_NUM_EXTENSIONS, &extensionCount);
        glExtensions.clear();
        for (GLint i = 0; i < extensionCount; i++) {
            const GLubyte *extension = glGetStringi(GL_EXTENSIONS, static_cast<GLuint>(i));
            if (extension != nullptr) {
                if (!glExtensions.empty()) {
                    glExtensions += ' ';
                }
                glExtensions += reinterpret_cast<const char *>(extension);
            }
        }

        GLint value = 0;
        glGetIntegerv(GL_MAX_TEXTURE_SIZE, &value);
        maxTextureSize = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_COLOR_ATTACHMENTS, &value);
        maxColorAttachments = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_SAMPLES, &value);
        maxSamples = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS, &value);
        maxTextureImageUnits = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS, &value);
        maxVertexTextureImageUnits = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_UNIFORM_BUFFER_BINDINGS, &value);
        maxUniformBufferBindings = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_SHADER_STORAGE_BUFFER_BINDINGS, &value);
        maxShaderStorageBufferBindings = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_COMPUTE_WORK_GROUP_INVOCATIONS, &value);
        maxComputeWorkGroupInvocations = static_cast<uint32_t>(value);
        value = 0;
        glGetIntegerv(GL_MAX_VERTEX_ATTRIBS, &value);
        maxVertexAttribs = static_cast<uint32_t>(value);

        hasGeometryShaderExt = hasExtension("GL_EXT_geometry_shader") ||
                               hasExtension("GL_OES_geometry_shader");
        hasKHRDebugExt = hasExtension("GL_KHR_debug");

        // ---- Capacidades declaradas ao RT64 (decidem o caminho de renderizacao) ----
        // Derivadas por MEDICAO no M0 (evidence_gles_backend_recon_20261017.md §2) e
        // pelo plano: sem descriptor indexing/bindless, sem ray tracing, geometry
        // shader por extensao, triangle fan em core, UMA (Mali integrado).
        capabilities = RenderDeviceCapabilities();
        capabilities.geometryShader = hasGeometryShaderExt;
        capabilities.raytracing = false;                // ES 3.2 nao tem RT
        capabilities.raytracingStateUpdate = false;
        capabilities.sampleLocations = false;           // sem EXT_sample_locations
        capabilities.resolveRegion = true;              // glBlitFramebuffer (core ES 3.0)
        capabilities.resolveModes = true;               // blit com filtro LINEAR
        capabilities.descriptorIndexing = false;        // <== restricao central do M3
        capabilities.scalarBlockLayout = hasExtension("GL_EXT_scalar_block_layout");
        capabilities.bufferDeviceAddress = false;       // ES nao tem BDA
        capabilities.samplerMirrorClampToEdge = false;  // ES nao tem MIRROR_CLAMP_TO_EDGE
        capabilities.presentWait = false;               // apresentacao via swapWindow
        capabilities.displayTiming = false;
        capabilities.maxTextureSize = maxTextureSize;
        capabilities.preferHDR = false;
        capabilities.triangleFan = true;                // core no ES
        capabilities.dynamicDepthBias = true;           // glPolygonOffset e' core
        capabilities.uma = true;                        // Mali-G31 e' unificado
        capabilities.gpuUploadHeap = true;
        capabilities.queryPools = hasExtension("GL_EXT_disjoint_timer_query");

        description.name = glRenderer;
        description.type = RenderDeviceType::INTEGRATED;
        // ATENCAO: o enum RenderDeviceVendor do Plume nao tem ARM (so' AMD/NVIDIA/
        // INTEL/APPLE). Reportar UNKNOWN e' o correto -- inventar um valor quebraria
        // qualquer `switch` do RT64 que trate vendor. O nome real do GPU segue em
        // description.name (glRenderer) e em glVendor.
        description.vendor = RenderDeviceVendor::UNKNOWN;
        description.driverVersion = 0;
        description.dedicatedVideoMemory = 0;           // UMA: sem VRAM dedicada
    }
}