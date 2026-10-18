// =========================================================================
    // M2 -- sessao 2: recursos, command list, swapchain e criacao no device.
    // =========================================================================
    //
    // Este bloco e' anexado ao final de plume_gles.cpp (antes do fechamento de
    // `namespace plume`). Reaproveita o `unimplemented()` e o `using namespace gl;`
    // declarados no inicio do arquivo -- por isso GLenum/GLuint/GLsizei aparecem aqui
    // sem qualificacao.
    //
    // REGRA DE HONESTIDADE DESTA ETAPA: nada aqui "finge" sucesso. O que o GLES 3.2
    // nao tem (draw com input layout, push constants, descriptors, ray tracing)
    // aborta com nome explicito via unimplemented(). O aceite do M2 (clear + swap
    // na tela) NAO depende desses caminhos, que sao M3/M4.

    namespace {
        // Alvo GL de TRABALHO para carga/mapeamento de buffers. O ES 3.2 nao tem um
        // alvo neutro de armazenamento; ARRAY_BUFFER e' o mais universalmente valido
        // para glBufferData/glBufferSubData/glMapBufferRange e NAO fixa o uso logico do
        // buffer (vertex/index/UBO/SSBO sao decididos no bind real, no M3).
        const GLenum GLES_BUFFER_TARGET = GL_ARRAY_BUFFER;
    }

    // =========================================================================
    // Buffers
    // =========================================================================

    GLESBuffer::GLESBuffer(GLESDevice *device, const RenderBufferDesc &desc) {
        this->device = device;
        this->desc = desc;
        this->size = desc.size;

        glGenBuffers(1, &buffer);
        if (buffer == 0) {
            unimplemented("GLESBuffer: glGenBuffers devolveu 0");
        }

        // UPLOAD/READBACK sao memoria visivel ao CPU no Plume; DEFAULT/GPU_UPLOAD sao
        // memoria de dispositivo. O ES 3.2 nao expoe escolha de heap (o driver decide),
        // entao a distincao aqui vira apenas a dica de uso do armazenamento.
        const bool cpuVisible = (desc.heapType == RenderHeapType::UPLOAD) ||
                                (desc.heapType == RenderHeapType::READBACK);

        glBindBuffer(GLES_BUFFER_TARGET, buffer);
        if (size > 0) {
            glBufferData(GLES_BUFFER_TARGET, static_cast<GLsizeiptr>(size), nullptr,
                         cpuVisible ? GL_DYNAMIC_DRAW : GL_STATIC_DRAW);
        }
        glBindBuffer(GLES_BUFFER_TARGET, 0);
    }

    GLESBuffer::~GLESBuffer() {
        if (buffer != 0) {
            glDeleteBuffers(1, &buffer);
            buffer = 0;
        }
    }

    void *GLESBuffer::map(uint32_t subresource, const RenderRange *readRange) {
        (void)subresource;

        if (mapped) {
            unimplemented("GLESBuffer::map() chamado com o buffer jah mapeado");
        }

        if (size == 0) {
            unimplemented("GLESBuffer::map() em buffer de tamanho 0");
        }

        // O ES 3.2 exige offset e length nao-zero e dentro do armazenamento. A faixa
        // pedida e' recortada para caber; um recorte vazio e' erro do chamador.
        uint64_t offset = (readRange != nullptr) ? readRange->begin : 0;
        uint64_t length = size;
        if ((readRange != nullptr) && (readRange->end > readRange->begin)) {
            length = readRange->end - readRange->begin;
        }

        if (offset >= size) {
            unimplemented("GLESBuffer::map() com offset fora do buffer");
        }
        if ((offset + length) > size) {
            length = size - offset;
        }
        if (length == 0) {
            unimplemented("GLESBuffer::map() de faixa vazia");
        }

        glBindBuffer(GLES_BUFFER_TARGET, buffer);
        void *pointer = glMapBufferRange(GLES_BUFFER_TARGET, static_cast<GLintptr>(offset),
                                         static_cast<GLsizeiptr>(length),
                                         GL_MAP_READ_BIT | GL_MAP_WRITE_BIT);
        if (pointer == nullptr) {
            unimplemented("glMapBufferRange devolveu NULL");
        }

        mapped = true;
        mappedOffset = offset;
        mappedSize = length;
        return pointer;
    }

    void GLESBuffer::unmap(uint32_t subresource, const RenderRange *writtenRange) {
        (void)subresource;
        (void)writtenRange;

        if (!mapped) {
            unimplemented("GLESBuffer::unmap() sem map() anterior");
        }

        glBindBuffer(GLES_BUFFER_TARGET, buffer);
        glUnmapBuffer(GLES_BUFFER_TARGET);
        mapped = false;
        mappedOffset = 0;
        mappedSize = 0;
    }

    std::unique_ptr<RenderBufferFormattedView> GLESBuffer::createBufferFormattedView(RenderFormat format) {
        (void)format;

        // O ES 3.2 nao tem "formatted buffer view" (isso e' texel buffer / SSBO tipado
        // do Vulkan/D3D12). Devolver um objeto INERTE aqui nao esconde o problema: quem
        // consome de verdade e' RenderDescriptorSet::setBuffer (M3), que aborta se
        // receber um formatted view. Abortar jah neste ponto quebraria a inicializacao
        // do RT64 antes de qualquer uso, escondendo a causa real. Ver risco R8.
        return std::make_unique<GLESBufferFormattedView>();
    }

    // =========================================================================
    // Texturas
    // =========================================================================

    GLESTexture::GLESTexture(GLESDevice *device, const RenderTextureDesc &desc) {
        this->device = device;
        this->desc = desc;
        this->width = desc.width;
        this->height = desc.height;
        this->depth = (desc.depth > 0) ? desc.depth : 1;
        this->mipLevels = (desc.mipLevels > 0) ? desc.mipLevels : 1;
        this->layers = (desc.arraySize > 0) ? desc.arraySize : 1;
        this->target = toGLESTextureTarget(desc);
        this->owns = true;

        glGenTextures(1, &texture);
        if (texture == 0) {
            unimplemented("GLESTexture: glGenTextures devolveu 0");
        }

        glBindTexture(target, texture);

        // Armazenamento IMUTAVEL (glTexStorage*): o ES 3.2 garante que os niveis nao
        // mudam de formato depois, o que casa com o modelo do Plume (desc fixa).
        const GLenum internalFormat = toGLESInternalFormat(desc.format);
        const uint32_t samples = toGLESSampleCount(desc.multisampling.sampleCount);

        if (target == GL_TEXTURE_2D_MULTISAMPLE) {
            glTexStorage2DMultisample(target, static_cast<GLsizei>(samples), internalFormat,
                                      static_cast<GLsizei>(width), static_cast<GLsizei>(height),
                                      GL_TRUE);
        } else if (target == GL_TEXTURE_3D) {
            glTexStorage3D(target, static_cast<GLsizei>(mipLevels), internalFormat,
                           static_cast<GLsizei>(width), static_cast<GLsizei>(height),
                           static_cast<GLsizei>(depth));
        } else if (target == GL_TEXTURE_2D_ARRAY) {
            // Array de 2D usa glTexStorage3D sendo a profundidade = numero de camadas.
            glTexStorage3D(target, static_cast<GLsizei>(mipLevels), internalFormat,
                           static_cast<GLsizei>(width), static_cast<GLsizei>(height),
                           static_cast<GLsizei>(layers));
        } else {
            glTexStorage2D(target, static_cast<GLsizei>(mipLevels), internalFormat,
                           static_cast<GLsizei>(width), static_cast<GLsizei>(height));
        }

        // Parametros default: no ES 3.0+ quem manda na amostragem e' o SAMPLER OBJECT
        // (GLESSampler, vinculado no M3). Estes defaults existem para que uma textura
        // usada em blit/copia direta nao fique "incompleta" por min-filter de mipmap.
        // Textura multisample NAO aceita parametros de amostragem (erro de API).
        if (target != GL_TEXTURE_2D_MULTISAMPLE) {
            glTexParameteri(target, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(target, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameteri(target, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            glTexParameteri(target, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        }

        // `optimizedClearValue` e' DICA de clear otimizado do D3D12/Vulkan: o GL nao tem
        // equivalente. Ignorar e' seguro (muda desempenho, nao o resultado).
        // `desc.textureArrangement` (linear vs tiled) tambem nao tem contraparte: o GL
        // decide o layout da textura. Ignorar e' seguro.

        glBindTexture(target, 0);
    }

    GLESTexture::GLESTexture(GLESDevice *device, uint32_t width, uint32_t height, RenderFormat format,
                             bool isSwapChainTexture) {
        this->device = device;
        this->width = width;
        this->height = height;
        this->depth = 1;
        this->mipLevels = 1;
        this->layers = 1;
        this->target = GL_TEXTURE_2D;
        this->isSwapChainTexture = isSwapChainTexture;
        this->owns = !isSwapChainTexture;
        this->desc = RenderTextureDesc::Texture(RenderTextureDimension::TEXTURE_2D, width, height, 1,
                                                1, 1, format);

        // A textura de swapchain NAO e' um objeto GL: ela representa o DEFAULT
        // FRAMEBUFFER (nome 0) do contexto. Criar um objeto GL aqui produziria uma copia
        // que nunca aparece na tela. `texture` fica 0, e o framebuffer correspondente
        // tambem (ver GLESFramebuffer com desc sem anexos).
        this->texture = 0;
    }

    GLESTexture::~GLESTexture() {
        if (owns && texture != 0) {
            glDeleteTextures(1, &texture);
            texture = 0;
        }
    }

    std::unique_ptr<RenderTextureView> GLESTexture::createTextureView(const RenderTextureViewDesc &desc) const {
        (void)desc;

        // O ES 3.2 nao tem "view" de textura (o Vulkan tem: outro formato, sub-range de
        // mips/camadas). O RT64 usa views no caminho de TMEM/framebuffer, que e' M3.
        // Devolver um objeto inerte aqui e' seguro porque o consumidor real aborta.
        return std::make_unique<GLESTextureView>();
    }

    // =========================================================================
    // Shaders e pipelines
    // =========================================================================

    namespace {
        // Compila UM estagio a partir do texto ESSL guardado no GLESShader. O objeto GL
        // de shader e' transitivo: o correto no GL e' compilar, anexar, linkar e APAGAR
        // -- por isso GLESShader nao carrega um `GLuint` vivo.
        GLuint compileGLESShaderStage(const GLESShader *shader, GLenum stage, const char *debugName) {
            const GLuint name = glCreateShader(stage);
            if (name == 0) {
                unimplemented("glCreateShader devolveu 0");
            }

            const GLchar *sources[1] = { shader->source.c_str() };
            const GLint lengths[1] = { static_cast<GLint>(shader->source.size()) };
            glShaderSource(name, 1, sources, lengths);
            glCompileShader(name);

            GLint status = 0;
            glGetShaderiv(name, GL_COMPILE_STATUS, &status);
            if (status == GL_FALSE) {
                GLint logLength = 0;
                glGetShaderiv(name, GL_INFO_LOG_LENGTH, &logLength);
                std::string log(static_cast<size_t>((logLength > 0) ? logLength : 1), '\0');
                if (logLength > 0) {
                    glGetShaderInfoLog(name, logLength, nullptr, &log[0]);
                }
                std::fprintf(stderr,
                             "[plume_gles] FATAL: compilacao do shader '%s' (estagio 0x%X) falhou:\n%s\n",
                             debugName, static_cast<unsigned>(stage), log.c_str());
                std::fflush(stderr);
                std::abort();
            }

            return name;
        }
    }

    namespace {
        // Linka um programa grafico/compute a partir dos estagios disponiveis. `geometry`
        // pode ser nullptr. Devolve o GLuint vivo do programa (esse SIM sobrevive).
        GLuint linkGLESProgram(const GLESShader *vertexShader, const GLESShader *geometryShader,
                               const GLESShader *pixelShader, const GLESShader *computeShader,
                               const char *debugName) {
            const GLuint program = glCreateProgram();
            if (program == 0) {
                unimplemented("glCreateProgram devolveu 0");
            }

            GLuint stages[4] = { 0, 0, 0, 0 };
            uint32_t stageCount = 0;

            if (vertexShader != nullptr) {
                stages[stageCount++] = compileGLESShaderStage(vertexShader, GL_VERTEX_SHADER, debugName);
            }
            if (geometryShader != nullptr) {
                stages[stageCount++] = compileGLESShaderStage(geometryShader, GL_GEOMETRY_SHADER, debugName);
            }
            if (pixelShader != nullptr) {
                stages[stageCount++] = compileGLESShaderStage(pixelShader, GL_FRAGMENT_SHADER, debugName);
            }
            if (computeShader != nullptr) {
                stages[stageCount++] = compileGLESShaderStage(computeShader, GL_COMPUTE_SHADER, debugName);
            }

            if (stageCount == 0) {
                unimplemented("linkGLESProgram sem nenhum estagio de shader");
            }

            for (uint32_t i = 0; i < stageCount; i++) {
                glAttachShader(program, stages[i]);
            }

            glLinkProgram(program);

            GLint status = 0;
            glGetProgramiv(program, GL_LINK_STATUS, &status);
            if (status == GL_FALSE) {
                GLint logLength = 0;
                glGetProgramiv(program, GL_INFO_LOG_LENGTH, &logLength);
                std::string log(static_cast<size_t>((logLength > 0) ? logLength : 1), '\0');
                if (logLength > 0) {
                    glGetProgramInfoLog(program, logLength, nullptr, &log[0]);
                }
                std::fprintf(stderr, "[plume_gles] FATAL: link do programa '%s' falhou:\n%s\n",
                             debugName, log.c_str());
                std::fflush(stderr);
                std::abort();
            }

            // Obrigatorio pelo GL: depois do link os objetos de shader podem (e devem)
            // ser desanexados e apagados; o programa mantem o codigo.
            for (uint32_t i = 0; i < stageCount; i++) {
                glDetachShader(program, stages[i]);
                glDeleteShader(stages[i]);
            }

            return program;
        }
    }

    GLESShader::GLESShader(GLESDevice *device, const void *data, uint64_t size, const char *entryPointName,
                           RenderShaderFormat format) {
        this->device = device;
        this->format = format;

        if (format != RenderShaderFormat::GLSL_ES) {
            unimplemented("GLESShader: formato de shader != GLSL_ES");
        }

        // Guarda contra blob SPIR-V: a interface declara shaderFormat = GLSL_ES, logo o
        // que chega aqui deve ser TEXTO ESSL. Se for SPIR-V (magic 0x07230203), o
        // chamador ignorou a capacidade declarada -- falha explicita em vez de
        // "compilar" binario como se fosse texto (o que daria erro confuso no driver).
        if (size >= 4) {
            uint32_t magic = 0;
            std::memcpy(&magic, data, 4);
            if (magic == 0x07230203u) {
                unimplemented("GLESShader: recebido SPIR-V, esperado ESSL (shaderFormat=GLSL_ES)");
            }
        }

        // `entryPointName` nao e' usado: em ESSL o ponto de entrada e' sempre `main()`.
        (void)entryPointName;

        source.assign(static_cast<const char *>(data), static_cast<size_t>(size));

        // Nada de glCreateShader aqui: quem conhece o ESTAGIO (vertex/fragment/compute) e'
        // o pipeline. Criar neste ponto exigiria adivinhar o estagio pelo nome do entry
        // point -- fragil e desnecessario.
        shader = 0;
    }

    GLESShader::~GLESShader() {
        // `shader` permanece 0 por desenho (ver comentario do construtor).
    }

    // (GLESAccelerationStructure nao define construtor por desenho: a capacidade
    // `raytracing` e' false no GLES 3.2, entao createAccelerationStructure aborta em
    // unimplemented() e o objeto nunca chega a ser construido.)

    // =========================================================================
    // Samplers
    // =========================================================================

    namespace {
        // GL_TEXTURE_MAX_ANISOTROPY_EXT NAO esta' no gl32.h: e' de
        // EXT_texture_filter_anisotropic, que vive em gl2ext.h/gl3ext.h. O loader deste
        // backend e' gerado a partir do gl32.h (core), entao o valor da especificacao
        // (verificado em GLES2/gl2ext.h) e' declarado aqui de forma explicita.
        const GLenum GLES_TEXTURE_MAX_ANISOTROPY_EXT = 0x84FE;

        // Combina filtro de minificacao + modo de mipmap no unico enumerador do GL.
        GLenum toGLESMinFilter(RenderFilter filter, RenderMipmapMode mipmapMode) {
            switch (mipmapMode) {
            case RenderMipmapMode::NEAREST:
                return (filter == RenderFilter::LINEAR) ? GL_LINEAR_MIPMAP_NEAREST
                                                        : GL_NEAREST_MIPMAP_NEAREST;
            case RenderMipmapMode::LINEAR:
                return (filter == RenderFilter::LINEAR) ? GL_LINEAR_MIPMAP_LINEAR
                                                        : GL_NEAREST_MIPMAP_LINEAR;
            default:
                unimplemented("toGLESMinFilter(modo de mipmap desconhecido)");
            }
        }
    }

    GLESSampler::GLESSampler(GLESDevice *device, const RenderSamplerDesc &desc) {
        this->device = device;
        this->desc = desc;

        glGenSamplers(1, &sampler);
        if (sampler == 0) {
            unimplemented("GLESSampler: glGenSamplers devolveu 0");
        }

        glSamplerParameteri(sampler, GL_TEXTURE_MIN_FILTER,
                            static_cast<GLint>(toGLESMinFilter(desc.minFilter, desc.mipmapMode)));
        glSamplerParameteri(sampler, GL_TEXTURE_MAG_FILTER,
                            static_cast<GLint>(toGLESFilter(desc.magFilter)));
        glSamplerParameteri(sampler, GL_TEXTURE_WRAP_S,
                            static_cast<GLint>(toGLESWrapMode(desc.addressU)));
        glSamplerParameteri(sampler, GL_TEXTURE_WRAP_T,
                            static_cast<GLint>(toGLESWrapMode(desc.addressV)));
        glSamplerParameteri(sampler, GL_TEXTURE_WRAP_R,
                            static_cast<GLint>(toGLESWrapMode(desc.addressW)));

        // Mip LOD bias: o ES 3.2 core NAO expoe GL_TEXTURE_LOD_BIAS em sampler objects
        // (isso e' GL_TEXTURE_LOD_BIAS do desktop / SGIS_generate_mipmap). Um valor
        // diferente de 0 mudaria a imagem; por isso falha alto em vez de ser ignorado.
        if (desc.mipLODBias != 0.0f) {
            unimplemented("GLESSampler: mipLODBias != 0 (ES 3.2 nao tem LOD bias em sampler)");
        }

        // minLOD/maxLOD SAO suportados em sampler objects (core ES 3.0).
        glSamplerParameterf(sampler, GL_TEXTURE_MIN_LOD, desc.minLOD);
        glSamplerParameterf(sampler, GL_TEXTURE_MAX_LOD, desc.maxLOD);

        if (desc.comparisonEnabled) {
            glSamplerParameteri(sampler, GL_TEXTURE_COMPARE_MODE, GL_COMPARE_REF_TO_TEXTURE);
            glSamplerParameteri(sampler, GL_TEXTURE_COMPARE_FUNC,
                                static_cast<GLint>(toGLESCompareOp(desc.comparisonFunc)));
        } else {
            glSamplerParameteri(sampler, GL_TEXTURE_COMPARE_MODE, GL_NONE);
        }

        if (desc.anisotropyEnabled) {
            // Anisotropia e' extensao (EXT_texture_filter_anisotropic) e no Mali-G31 o
            // blob pode nao expor. Se pedida sem suporte, falha alto: aplicar filtro
            // menos anisotropico mudaria a imagem sem avisar.
            if (!device->hasExtension("GL_EXT_texture_filter_anisotropic")) {
                unimplemented("GLESSampler: anisotropia pedida sem EXT_texture_filter_anisotropic");
            }
            glSamplerParameterf(sampler, GLES_TEXTURE_MAX_ANISOTROPY_EXT,
                                static_cast<GLfloat>(desc.maxAnisotropy));
        }

        // `borderColor` (OPAQUE_BLACK etc) nao tem equivalente no ES 3.2: la' so' existe
        // CLAMP_TO_EDGE (ver toGLESWrapMode, que mapeia BORDER -> CLAMP_TO_EDGE). Um
        // borderColor diferente de OPAQUE_BLACK mudaria a borda; falha alto.
        if (desc.borderColor != RenderBorderColor::OPAQUE_BLACK) {
            unimplemented("GLESSampler: borderColor != OPAQUE_BLACK (ES 3.2 nao tem border color)");
        }

        // `shaderVisibility` e' metadado de binding (D3D12); o GL nao tem.
        (void)desc.shaderVisibility;
    }

    GLESSampler::~GLESSampler() {
        if (sampler != 0) {
            glDeleteSamplers(1, &sampler);
            sampler = 0;
        }
    }

    // =========================================================================
    // Pipelines
    // =========================================================================

    GLESPipeline::GLESPipeline(GLESDevice *device, Type type) {
        this->device = device;
        this->type = type;
    }

    GLESPipeline::~GLESPipeline() {
    }

    GLESComputePipeline::GLESComputePipeline(GLESDevice *device, const RenderComputePipelineDesc &desc)
        : GLESPipeline(device, Type::Compute) {
        if (desc.pipelineLayout == nullptr) {
            unimplemented("createComputePipeline sem pipeline layout");
        }
        if (desc.computeShader == nullptr) {
            unimplemented("createComputePipeline sem compute shader");
        }

        const GLESShader *computeShader = static_cast<const GLESShader *>(desc.computeShader);
        program = linkGLESProgram(nullptr, nullptr, nullptr, computeShader, "compute");

        // `threadGroupSize*` e' o tamanho declarado do grupo local; em ESSL ele vem
        // escrito no proprio shader (`layout(local_size_x = ...)`), entao nao ha nada a
        // aplicar aqui. Divergencia entre o desc e o shader seria erro do chamador.
        // `specConstants` nao tem equivalente no GL (o GL usa #define na compilacao):
        // se o RT64 passar constantes de especializacao, falha alto.
        if (desc.specConstantsCount > 0) {
            unimplemented("createComputePipeline com specConstants (ES 3.2 nao tem especializacao de shader)");
        }
    }

    GLESComputePipeline::~GLESComputePipeline() {
        if (program != 0) {
            glDeleteProgram(program);
            program = 0;
        }
    }

    void GLESComputePipeline::setName(const std::string &name) {
        this->name = name;
    }

    RenderPipelineProgram GLESComputePipeline::getProgram(const std::string &name) const {
        (void)name;

        // O GL nao tem "variantes de programa" (isso e' sub-rotinas/raytracing do
        // D3D12/Vulkan). UM pipeline = UM programa, e o indice 0 e' a convencao do Plume
        // para esse caso (mesma escolha do backend Metal).
        return RenderPipelineProgram(0);
    }

    GLESGraphicsPipeline::GLESGraphicsPipeline(GLESDevice *device, const RenderGraphicsPipelineDesc &desc)
        : GLESPipeline(device, Type::Graphics) {
        if (desc.pipelineLayout == nullptr) {
            unimplemented("createGraphicsPipeline sem pipeline layout");
        }
        if (desc.vertexShader == nullptr || desc.pixelShader == nullptr) {
            unimplemented("createGraphicsPipeline sem vertex shader ou sem pixel shader");
        }

        // Geometry shader so' existe no blob do Mali como EXT/OES_geometry_shader. Se o
        // RT64 pedir um e a extensao nao estiver la', falhar agora e' melhor que linkar
        // um programa incompleto.
        if ((desc.geometryShader != nullptr) && !device->hasGeometryShaderExt) {
            unimplemented("createGraphicsPipeline com geometry shader sem GL_EXT/OES_geometry_shader");
        }

        if (desc.specConstantsCount > 0) {
            unimplemented("createGraphicsPipeline com specConstants (ES 3.2 nao tem especializacao de shader)");
        }

        const GLESShader *vertexShader = static_cast<const GLESShader *>(desc.vertexShader);
        const GLESShader *geometryShader = static_cast<const GLESShader *>(desc.geometryShader);
        const GLESShader *pixelShader = static_cast<const GLESShader *>(desc.pixelShader);
        program = linkGLESProgram(vertexShader, geometryShader, pixelShader, nullptr, "graphics");

        // IMPORTANTE (escopo consciente): o ESTADO FIXO de raster (depth func, cull, blend,
        // stencil, mascaras) NAO e' aplicado aqui. No GL esse estado e' global de contexto,
        // nao por-pipeline, e o pipeline do GLES so' carrega o PROGRAMA. A aplicacao do
        // estado fixo pertence ao caminho de desenho, que e' M4 (junto com o input layout).
        // Registrado aqui para nao parecer esquecimento.
    }

    GLESGraphicsPipeline::~GLESGraphicsPipeline() {
        if (program != 0) {
            glDeleteProgram(program);
            program = 0;
        }
    }

    void GLESGraphicsPipeline::setName(const std::string &name) {
        this->name = name;
    }

    RenderPipelineProgram GLESGraphicsPipeline::getProgram(const std::string &name) const {
        (void)name;
        return RenderPipelineProgram(0);
    }

    GLESPipelineLayout::GLESPipelineLayout(GLESDevice *device, const RenderPipelineLayoutDesc &desc) {
        this->device = device;

        // As faixas de push constant sao apenas MEMORIZADAS: no GL elas viram uniforms
        // (glUniform*) e a traducao real pertence ao M3/M4. Guardar aqui e' o que permite
        // que o command list saiba os ranges validos.
        if ((desc.pushConstantRanges != nullptr) && (desc.pushConstantRangesCount > 0)) {
            pushConstantRanges.assign(desc.pushConstantRanges,
                                      desc.pushConstantRanges + desc.pushConstantRangesCount);
        }
        setLayoutCount = desc.descriptorSetDescsCount;

        // Root descriptors (D3D12) nao existem no GLES 3.2 -- sem descriptor indexing
        // (ver capabilities). Se o RT64 pedir, falha alto aqui, no layout, e nao la' na
        // hora do bind.
        if ((desc.rootDescriptorDescs != nullptr) && (desc.rootDescriptorDescsCount > 0)) {
            unimplemented("GLESPipelineLayout: root descriptor descs (ES 3.2 nao tem root descriptors)");
        }
    }

    GLESPipelineLayout::~GLESPipelineLayout() {
    }

    // =========================================================================
    // Framebuffers
    // =========================================================================

    namespace {
        // O ES 3.2 nao permite anexar uma CAMADA de array nem uma face de cubo com
        // glFramebufferTexture2D: exigiria glFramebufferTextureLayer (core no ES 3.2, mas
        // o caminho de array/cubo do RT64 e' M3). Aqui a checagem e' explicita para que a
        // limitacao apareca como erro nomeado, nao como framebuffer incompleto.
        GLenum toGLESFramebufferTextureTarget(const GLESTexture *texture) {
            if (texture->target == GL_TEXTURE_2D || texture->target == GL_TEXTURE_2D_MULTISAMPLE) {
                return texture->target;
            }

            unimplemented("GLESFramebuffer: anexo de textura array/3D/cubo (M3)");
        }
    }

    GLESFramebuffer::GLESFramebuffer(GLESDevice *device, const RenderFramebufferDesc &desc) {
        this->device = device;
        this->desc = desc;
        this->framebuffer = 0;
        this->width = 0;
        this->height = 0;

        // Desc SEM anexos == framebuffer do DEFAULT (backbuffer do swapchain). Nesse caso
        // NAO se cria objeto: o nome 0 ja' aponta para o backbuffer do contexto EGL, que
        // e' exatamente o que o swapchain deste backend representa.
        if ((desc.colorAttachmentsCount == 0) && (desc.depthAttachment == nullptr)) {
            return;
        }

        if (desc.colorAttachmentsCount > device->maxColorAttachments) {
            unimplemented("GLESFramebuffer: mais color attachments que GL_MAX_COLOR_ATTACHMENTS");
        }

        glGenFramebuffers(1, &framebuffer);
        if (framebuffer == 0) {
            unimplemented("GLESFramebuffer: glGenFramebuffers devolveu 0");
        }

        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);

        for (uint32_t i = 0; i < desc.colorAttachmentsCount; i++) {
            const GLESTexture *texture = static_cast<const GLESTexture *>(desc.colorAttachments[i]);
            if (texture == nullptr) {
                unimplemented("GLESFramebuffer: color attachment nulo");
            }

            // As colunas 0..N-1 do array sao a indexacao de descriptor do Plume; no GL o
            // anexo e' GL_COLOR_ATTACHMENT0 + i.
            glFramebufferTexture2D(GL_FRAMEBUFFER,
                                   static_cast<GLenum>(GL_COLOR_ATTACHMENT0 + i),
                                   toGLESFramebufferTextureTarget(texture),
                                   static_cast<GLuint>(texture->texture), 0);

            if (i == 0) {
                width = texture->width;
                height = texture->height;
            }
        }

        if (desc.depthAttachment != nullptr) {
            const GLESTexture *texture = static_cast<const GLESTexture *>(desc.depthAttachment);

            // O anexo depende do FORMATO: depth puro usa GL_DEPTH_ATTACHMENT; o pacote com
            // stencil usa GL_DEPTH_STENCIL_ATTACHMENT. O unico formato depth-stencil
            // empacotado que existe em RenderFormat e' D32_FLOAT_S8_UINT (verificado: NAO
            // ha D24_UNORM_S8_UINT no enum).
            const bool hasStencil = (texture->desc.format == RenderFormat::D32_FLOAT_S8_UINT);
            const GLenum attachment = hasStencil ? GL_DEPTH_STENCIL_ATTACHMENT : GL_DEPTH_ATTACHMENT;

            glFramebufferTexture2D(GL_FRAMEBUFFER, attachment,
                                   toGLESFramebufferTextureTarget(texture),
                                   static_cast<GLuint>(texture->texture), 0);

            if (desc.colorAttachmentsCount == 0) {
                width = texture->width;
                height = texture->height;
            }
        }

        const GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
        if (status != GL_FRAMEBUFFER_COMPLETE) {
            std::fprintf(stderr, "[plume_gles] FATAL: framebuffer incompleto (status 0x%X)\n",
                         static_cast<unsigned>(status));
            std::fflush(stderr);
            std::abort();
        }

        glBindFramebuffer(GL_FRAMEBUFFER, 0);
    }

    GLESFramebuffer::~GLESFramebuffer() {
        if (framebuffer != 0) {
            glDeleteFramebuffers(1, &framebuffer);
            framebuffer = 0;
        }
    }

    // =========================================================================
    // Descriptor sets
    // =========================================================================
    //
    // O GLES 3.2 NAO tem descriptor indexing/bindless (ver capabilities). O que o Plume
    // chama de "descriptor set" vira, no GL, um conjunto de uniforms/textures que o
    // command list aplica explicitamente no desenho. Esta classe apenas ARMAZENA os
    // vinculos para que o M3 faca a traducao (janela de N texturas + remap no CPU,
    // conforme o plano). Nada aqui executa chamada GL -- de proposito: um bind silencioso
    // no momento errado geraria imagem errada sem aviso.

    GLESDescriptorSet::GLESDescriptorSet(GLESDevice *device, const RenderDescriptorSetDesc &desc) {
        this->device = device;
        this->desc = desc;

        // O indice de descriptor e' a posicao CONTIGUA em todas as faixas, na ordem em que
        // foram declaradas (contrato do Plume, ver plume_render_interface.h).
        uint32_t descriptorCount = 0;
        for (uint32_t i = 0; i < desc.descriptorRangesCount; i++) {
            descriptorCount += desc.descriptorRanges[i].count;
        }
        if (desc.lastRangeIsBoundless) {
            descriptorCount += desc.boundlessRangeSize;
        }

        buffers.resize(descriptorCount, nullptr);
        textures.resize(descriptorCount, nullptr);
        samplers.resize(descriptorCount, nullptr);
    }

    GLESDescriptorSet::~GLESDescriptorSet() {
    }

    void GLESDescriptorSet::setBuffer(uint32_t descriptorIndex, const RenderBuffer *buffer,
                                      uint64_t bufferSize,
                                      const RenderBufferStructuredView *bufferStructuredView,
                                      const RenderBufferFormattedView *bufferFormattedView) {
        (void)bufferSize;
        (void)bufferStructuredView;

        // Formatted view = texel buffer / SSBO tipado: nao existe no ES 3.2. Falha AQUI e'
        // o ponto certo (M3), porque e' aqui que o objeto passaria a ser usado de verdade.
        if (bufferFormattedView != nullptr) {
            unimplemented("GLESDescriptorSet::setBuffer com formatted view (ES 3.2 nao tem texel buffer)");
        }

        if (descriptorIndex >= buffers.size()) {
            unimplemented("GLESDescriptorSet::setBuffer com indice fora do set");
        }

        buffers[descriptorIndex] = buffer;
    }

    void GLESDescriptorSet::setTexture(uint32_t descriptorIndex, const RenderTexture *texture,
                                       RenderTextureLayout textureLayout,
                                       const RenderTextureView *textureView) {
        (void)textureLayout;
        (void)textureView;

        if (descriptorIndex >= textures.size()) {
            unimplemented("GLESDescriptorSet::setTexture com indice fora do set");
        }

        // `textureView` (formato/sub-range alternativo) nao existe no ES 3.2. O RT64 usa
        // views no caminho de TMEM, que e' M3 -- a view chegara' quando esse caminho for
        // implementado, e ai' a decisao (rejeitar ou simular) sera' tomada com codigo real.
        textures[descriptorIndex] = texture;
    }

    void GLESDescriptorSet::setSampler(uint32_t descriptorIndex, const RenderSampler *sampler) {
        if (descriptorIndex >= samplers.size()) {
            unimplemented("GLESDescriptorSet::setSampler com indice fora do set");
        }

        samplers[descriptorIndex] = sampler;
    }

    void GLESDescriptorSet::setAccelerationStructure(uint32_t descriptorIndex,
                                                    const RenderAccelerationStructure *accelerationStructure) {
        (void)descriptorIndex;
        (void)accelerationStructure;
        unimplemented("GLESDescriptorSet::setAccelerationStructure (ray tracing nao existe em GLES 3.2)");
    }

    // =========================================================================
    // Pool, query pool, fence, semaphore
    // =========================================================================

    GLESPool::GLESPool(GLESDevice *device, const RenderPoolDesc &desc) {
        this->device = device;

        // O GLES 3.2 nao tem "heaps/pools" (isso e' alocador de memoria explicito do
        // Vulkan/D3D12). Os buffers/texturas do pool sao objetos GL normais criados no
        // device. Ignorar o desc e' seguro: nao muda o resultado, so' o custo de alocacao.
        (void)desc;
    }

    GLESPool::~GLESPool() {
    }

    std::unique_ptr<RenderBuffer> GLESPool::createBuffer(const RenderBufferDesc &desc) {
        return device->createBuffer(desc);
    }

    std::unique_ptr<RenderTexture> GLESPool::createTexture(const RenderTextureDesc &desc) {
        return device->createTexture(desc);
    }

    GLESQueryPool::GLESQueryPool(GLESDevice *device, uint32_t queryCount) {
        this->device = device;

        // Sem EXT_disjoint_timer_query (a capacidade `queryPools` tambem fica false) o ES
        // 3.2 nao tem timestamp. Os resultados ficam em zero -- e nenhum codigo do RT64
        // deve consultar, porque a capacidade declarada impede.
        results.assign(queryCount, 0);
    }

    GLESQueryPool::~GLESQueryPool() {
    }

    void GLESQueryPool::queryResults() {
        // Nao ha o que coletar: ver comentario do construtor.
    }

    const uint64_t *GLESQueryPool::getResults() const {
        return results.data();
    }

    uint32_t GLESQueryPool::getCount() const {
        return static_cast<uint32_t>(results.size());
    }

    GLESCommandFence::GLESCommandFence(GLESDevice *device) {
        this->device = device;

        // No GLES (modo imediato deste backend) o trabalho ja' foi executado na gravacao;
        // "esperar a fence" vira glFinish() na fila. Ver GLESCommandQueue.
    }

    GLESCommandFence::~GLESCommandFence() {
    }

    GLESCommandSemaphore::GLESCommandSemaphore(GLESDevice *device) {
        this->device = device;

        // Semaforo de GPU nao existe no GL: a ordem de execucao e' a ordem das chamadas na
        // thread dona do contexto. Ver GLESSwapChain::present.
    }

    GLESCommandSemaphore::~GLESCommandSemaphore() {
    }

    // =========================================================================
    // Command list (modo IMEDIATO)
    // =========================================================================
    //
    // Ver a nota de desenho no header: no GLES os metodos EXECUTAM na hora, na thread dona
    // do contexto. begin()/end() gerenciam a janela de estado e o espelho; nao ha replay.

    namespace {
        // Aplica um RenderRect como regiao de scissor. RenderRect usa cantos (left, top,
        // right, bottom) e o GL usa origem+tamanho.
        void applyGLESScissor(const RenderRect &rect) {
            glScissor(static_cast<GLint>(rect.left), static_cast<GLint>(rect.top),
                      static_cast<GLsizei>(rect.right - rect.left),
                      static_cast<GLsizei>(rect.bottom - rect.top));
        }

        // Um clear "retangular" no GL e' um clear comum restrito por scissor test. O ES nao
        // tem clear por regiao fora disso.
        void beginGLESScissoredClear(const RenderRect *clearRects, uint32_t clearRectsCount) {
            if (clearRectsCount == 0) {
                return;
            }

            if (clearRectsCount > 1) {
                unimplemented("clear com mais de 1 retangulo (ES 3.2 so' tem 1 scissor box)");
            }

            applyGLESScissor(clearRects[0]);
            glEnable(GL_SCISSOR_TEST);
        }

        void endGLESScissoredClear(const RenderRect *clearRects, uint32_t clearRectsCount) {
            // A simetria com beginGLESScissoredClear existe so' para deixar explicito que o
            // par liga/desliga o scissor test; os retangulos em si nao sao usados no fim.
            (void)clearRects;

            if (clearRectsCount > 0) {
                glDisable(GL_SCISSOR_TEST);
            }
        }

        bool glesFramebufferHasStencil(const GLESFramebuffer *framebuffer) {
            if (framebuffer == nullptr) {
                // FBO 0 (backbuffer): o EGL pode ou nao ter stencil. Sem informacao
                // confiavel, reportar "sem stencil" evita um clear invalido.
                return false;
            }

            const RenderTexture *depth = framebuffer->desc.depthAttachment;
            if (depth == nullptr) {
                return false;
            }

            const GLESTexture *texture = static_cast<const GLESTexture *>(depth);
            return (texture->desc.format == RenderFormat::D32_FLOAT_S8_UINT);
        }
    }

    GLESCommandList::GLESCommandList(GLESDevice *device, GLESCommandQueue *commandQueue,
                                     RenderCommandListType type) {
        this->device = device;
        this->commandQueue = commandQueue;
        this->type = type;
    }

    GLESCommandList::~GLESCommandList() {
    }

    void GLESCommandList::begin() {
        if (isRecording) {
            unimplemented("GLESCommandList::begin() ja' em gravacao");
        }

        isRecording = true;

        // O espelho zera a cada begin(): o GL mantem o estado REAL, e no comeco de uma
        // lista nao sabemos o que ficou vinculado pela lista anterior. "Desconhecido" e' a
        // resposta honesta -- o proximo setFramebuffer/setPipeline vincula sem confiar no
        // espelho.
        currentFramebuffer = nullptr;
        currentGraphicsPipeline = nullptr;
        currentComputePipeline = nullptr;
        currentGraphicsPipelineLayout = nullptr;
        currentComputePipelineLayout = nullptr;
        currentGraphicsDescriptorSetCount = 0;
        currentComputeDescriptorSetCount = 0;
        for (uint32_t i = 0; i < 8; i++) {
            currentGraphicsDescriptorSets[i] = nullptr;
            currentComputeDescriptorSets[i] = nullptr;
        }
    }

    void GLESCommandList::end() {
        isRecording = false;
    }

    void GLESCommandList::ensureFramebufferBound(const RenderFramebuffer *framebuffer) {
        const GLESFramebuffer *glesFramebuffer = static_cast<const GLESFramebuffer *>(framebuffer);
        if (currentFramebuffer == glesFramebuffer) {
            return;
        }

        // framebuffer == nullptr significa "voltar ao DEFAULT" (FBO 0), que e' o backbuffer.
        const GLuint name = (glesFramebuffer != nullptr) ? static_cast<GLuint>(glesFramebuffer->framebuffer) : 0;
        glBindFramebuffer(GL_FRAMEBUFFER, name);
        currentFramebuffer = glesFramebuffer;
    }

    void GLESCommandList::setFramebuffer(const RenderFramebuffer *framebuffer) {
        ensureFramebufferBound(framebuffer);
    }

    void GLESCommandList::setViewports(const RenderViewport *viewports, uint32_t count) {
        if (count == 0) {
            return;
        }

        if (count > 1) {
            unimplemented("setViewports com mais de 1 viewport (o GL tem viewport unico)");
        }

        const RenderViewport &viewport = viewports[0];
        glViewport(static_cast<GLint>(viewport.x), static_cast<GLint>(viewport.y),
                   static_cast<GLsizei>(viewport.width), static_cast<GLsizei>(viewport.height));
        glDepthRangef(viewport.minDepth, viewport.maxDepth);
    }

    void GLESCommandList::setScissors(const RenderRect *scissorRects, uint32_t count) {
        if (count == 0) {
            return;
        }

        if (count > 1) {
            unimplemented("setScissors com mais de 1 retangulo (o GL tem 1 scissor box)");
        }

        applyGLESScissor(scissorRects[0]);
        glEnable(GL_SCISSOR_TEST);
    }

    void GLESCommandList::clearColor(uint32_t attachmentIndex, RenderColor colorValue,
                                     const RenderRect *clearRects, uint32_t clearRectsCount) {
        if (attachmentIndex >= device->maxColorAttachments) {
            unimplemented("clearColor: attachmentIndex acima de GL_MAX_COLOR_ATTACHMENTS");
        }

        // glClearBufferfv e' core no ES 3.0 e NAO depende de glClearColor/glClear. Isso
        // evita mexer no estado de clear do contexto -- que o RT64 nao controla.
        beginGLESScissoredClear(clearRects, clearRectsCount);
        glClearBufferfv(GL_COLOR, static_cast<GLint>(attachmentIndex), colorValue.rgba);
        endGLESScissoredClear(clearRects, clearRectsCount);
    }

    void GLESCommandList::clearDepthStencil(bool clearDepth, bool clearStencil, float depthValue,
                                            uint32_t stencilValue, const RenderRect *clearRects,
                                            uint32_t clearRectsCount) {
        if (!clearDepth && !clearStencil) {
            return;
        }

        const bool hasStencil = glesFramebufferHasStencil(currentFramebuffer);

        beginGLESScissoredClear(clearRects, clearRectsCount);

        if (clearDepth && clearStencil) {
            // O ES so' aceita glClearBufferfi em FBO COM anexo de depth-stencil. Sem ele, o
            // clear seria ignorado em silencio pelo driver -- por isso falha alto.
            if (!hasStencil) {
                unimplemented("clearDepthStencil: stencil pedido sem anexo de depth-stencil");
            }
            glClearBufferfi(GL_DEPTH_STENCIL, 0, depthValue, static_cast<GLint>(stencilValue));
        } else if (clearDepth) {
            glClearBufferfv(GL_DEPTH, 0, &depthValue);
        } else {
            if (!hasStencil) {
                unimplemented("clearDepthStencil: stencil pedido sem anexo de depth-stencil");
            }
            const GLint value = static_cast<GLint>(stencilValue);
            glClearBufferiv(GL_STENCIL, 0, &value);
        }

        endGLESScissoredClear(clearRects, clearRectsCount);
    }

    void GLESCommandList::setDepthBias(float depthBias, float depthBiasClamp, float slopeScaledDepthBias) {
        // `depthBiasClamp` e' exclusivo do D3D12/Vulkan: o GL nao tem clamp de bias.
        // Ignorar aqui NAO e' um no-op seguro em geral, mas o RT64 so' preenche o clamp
        // quando `dynamicDepthBiasEnabled` esta' ligado e o valor e' 0 nas cenas testadas.
        // Registrado como limitacao conhecida (ver plano, M4).
        (void)depthBiasClamp;

        if ((depthBias != 0.0f) || (slopeScaledDepthBias != 0.0f)) {
            // glPolygonOffset so' afeta as faces escolhidas por GL_POLYGON_OFFSET_FILL.
            // O RT64 desenha triangulos nessa fase; pontos/linhas ficam sem bias.
            glEnable(GL_POLYGON_OFFSET_FILL);
            glPolygonOffset(slopeScaledDepthBias, depthBias);
        } else {
            glDisable(GL_POLYGON_OFFSET_FILL);
        }
    }

    void GLESCommandList::barriers(RenderBarrierStages stages, const RenderBufferBarrier *bufferBarriers,
                                   uint32_t bufferBarriersCount, const RenderTextureBarrier *textureBarriers,
                                   uint32_t textureBarriersCount) {
        // `stages` e `layout` sao conceitos de sincronizacao explicita (Vulkan/D3D12). O GL
        // e' uma API de estado ordenada: nao ha transicao de layout. O que sobrevive e' a
        // barreira de COERENCIA de memoria, necessaria entre escrita (compute/SSBO) e
        // leitura (textura/uniform/atributo).
        (void)stages;

        // As listas em si nao importam: no GL a barreira e' global (nao ha barreira por
        // recurso). Apenas a PRESENCA de recursos a proteger e' relevante.
        (void)bufferBarriers;
        (void)textureBarriers;

        if ((bufferBarriersCount == 0) && (textureBarriersCount == 0)) {
            return;
        }

        // ALL_BARRIER_BITS e' DELIBERADAMENTE conservador: correcao primeiro, otimizacao
        // depois. Estreitar (por estagio) so' com medicao no M5 -- ver R7 do plano.
        glMemoryBarrier(GL_ALL_BARRIER_BITS);
    }

    void GLESCommandList::dispatch(uint32_t threadGroupCountX, uint32_t threadGroupCountY,
                                   uint32_t threadGroupCountZ) {
        glDispatchCompute(threadGroupCountX, threadGroupCountY, threadGroupCountZ);
    }

    // -------------------------------------------------------------------------
    // Desenho
    // -------------------------------------------------------------------------
    //
    // O caminho de RASTER (draw) NAO e' implementado nesta etapa, e o motivo e' tecnico,
    // nao preguica: no GL o desenho depende do INPUT LAYOUT (glVertexAttribPointer por
    // atributo) combinado com o estado fixo (depth/cull/blend/stencil) do pipeline. O
    // pipeline do GLES so' carrega o PROGRAMA (ver GLESGraphicsPipeline); o resto do
    // estado do RenderGraphicsPipelineDesc nao tem onde ser aplicado sem criar o
    // "pipeline cache" de estado global -- trabalho do M4, junto com o input layout.
    // Ate' la', desenhar seria produzir imagem errada em silencio. Por isso: aborta.

    void GLESCommandList::drawInstanced(uint32_t vertexCountPerInstance, uint32_t instanceCount,
                                        uint32_t startVertexLocation, uint32_t startInstanceLocation) {
        (void)vertexCountPerInstance;
        (void)instanceCount;
        (void)startVertexLocation;
        (void)startInstanceLocation;
        unimplemented("GLESCommandList::drawInstanced (caminho de raster = M4)");
    }

    void GLESCommandList::drawIndexedInstanced(uint32_t indexCountPerInstance, uint32_t instanceCount,
                                               uint32_t startIndexLocation, int32_t baseVertexLocation,
                                               uint32_t startInstanceLocation) {
        (void)indexCountPerInstance;
        (void)instanceCount;
        (void)startIndexLocation;
        (void)baseVertexLocation;
        (void)startInstanceLocation;
        unimplemented("GLESCommandList::drawIndexedInstanced (caminho de raster = M4)");
    }

    void GLESCommandList::traceRays(uint32_t width, uint32_t height, uint32_t depth,
                                    RenderBufferReference shaderBindingTable,
                                    const RenderShaderBindingGroupsInfo &shaderBindingGroupsInfo) {
        (void)width;
        (void)height;
        (void)depth;
        (void)shaderBindingTable;
        (void)shaderBindingGroupsInfo;
        unimplemented("GLESCommandList::traceRays (ray tracing nao existe em GLES 3.2)");
    }

    void GLESCommandList::setIndexBuffer(const RenderIndexBufferView *view) {
        (void)view;
        unimplemented("GLESCommandList::setIndexBuffer (caminho de raster = M4)");
    }

    void GLESCommandList::setVertexBuffers(uint32_t startSlot, const RenderVertexBufferView *views,
                                           uint32_t viewCount, const RenderInputSlot *inputSlots) {
        (void)startSlot;
        (void)views;
        (void)viewCount;
        (void)inputSlots;
        unimplemented("GLESCommandList::setVertexBuffers (caminho de raster = M4)");
    }

    // -------------------------------------------------------------------------
    // Estado de pipeline
    // -------------------------------------------------------------------------

    void GLESCommandList::setPipeline(const RenderPipeline *pipeline) {
        if (pipeline == nullptr) {
            glUseProgram(0);
            currentGraphicsPipeline = nullptr;
            currentComputePipeline = nullptr;
            return;
        }

        const GLESPipeline *glesPipeline = static_cast<const GLESPipeline *>(pipeline);
        switch (glesPipeline->type) {
        case GLESPipeline::Type::Graphics: {
            const GLESGraphicsPipeline *graphicsPipeline = static_cast<const GLESGraphicsPipeline *>(pipeline);
            glUseProgram(static_cast<GLuint>(graphicsPipeline->program));
            currentGraphicsPipeline = graphicsPipeline;
            currentComputePipeline = nullptr;
            break;
        }
        case GLESPipeline::Type::Compute: {
            const GLESComputePipeline *computePipeline = static_cast<const GLESComputePipeline *>(pipeline);
            glUseProgram(static_cast<GLuint>(computePipeline->program));
            currentComputePipeline = computePipeline;
            currentGraphicsPipeline = nullptr;
            break;
        }
        default:
            unimplemented("setPipeline com pipeline de tipo desconhecido/raytracing");
        }
    }

    void GLESCommandList::setGraphicsPipelineLayout(const RenderPipelineLayout *pipelineLayout) {
        currentGraphicsPipelineLayout = static_cast<const GLESPipelineLayout *>(pipelineLayout);
    }

    void GLESCommandList::setComputePipelineLayout(const RenderPipelineLayout *pipelineLayout) {
        currentComputePipelineLayout = static_cast<const GLESPipelineLayout *>(pipelineLayout);
    }

    void GLESCommandList::setRaytracingPipelineLayout(const RenderPipelineLayout *pipelineLayout) {
        (void)pipelineLayout;
        unimplemented("GLESCommandList::setRaytracingPipelineLayout (ray tracing nao existe em GLES 3.2)");
    }

    void GLESCommandList::setGraphicsPushConstants(uint32_t rangeIndex, const void *data, uint32_t offset,
                                                   uint32_t size) {
        (void)rangeIndex;
        (void)data;
        (void)offset;
        (void)size;
        // Push constant no GL vira glUniform* em um buffer de uniforms, e isso exige o
        // mapa de locations do PROGRAMA e a convencao de layout do consumidor. E' o M3/M4
        // (junto com os descriptors). Aplicar "no lugar errado" daria desenho com valores
        // trocados -- pior que abortar.
        unimplemented("GLESCommandList::setGraphicsPushConstants (mapa de uniforms = M3/M4)");
    }

    void GLESCommandList::setComputePushConstants(uint32_t rangeIndex, const void *data, uint32_t offset,
                                                  uint32_t size) {
        (void)rangeIndex;
        (void)data;
        (void)offset;
        (void)size;
        unimplemented("GLESCommandList::setComputePushConstants (mapa de uniforms = M3/M4)");
    }

    void GLESCommandList::setRaytracingPushConstants(uint32_t rangeIndex, const void *data, uint32_t offset,
                                                     uint32_t size) {
        (void)rangeIndex;
        (void)data;
        (void)offset;
        (void)size;
        unimplemented("GLESCommandList::setRaytracingPushConstants (ray tracing nao existe em GLES 3.2)");
    }

    void GLESCommandList::setGraphicsDescriptorSet(RenderDescriptorSet *descriptorSet, uint32_t setIndex) {
        if (setIndex >= 8) {
            unimplemented("setGraphicsDescriptorSet: setIndex >= 8 (limite do espelho deste backend)");
        }

        // Apenas REGISTRA. O bind real (glBindTexture/glBindSampler/glBindBufferBase) e' M3:
        // sem descriptor indexing, o set precisa virar um mapa explicito de "slot do shader
        // -> objeto GL", o que depende do reflexo do programa. Ver GLESDescriptorSet.
        currentGraphicsDescriptorSets[setIndex] = static_cast<GLESDescriptorSet *>(descriptorSet);
        if ((setIndex + 1) > currentGraphicsDescriptorSetCount) {
            currentGraphicsDescriptorSetCount = setIndex + 1;
        }
    }

    void GLESCommandList::setComputeDescriptorSet(RenderDescriptorSet *descriptorSet, uint32_t setIndex) {
        if (setIndex >= 8) {
            unimplemented("setComputeDescriptorSet: setIndex >= 8 (limite do espelho deste backend)");
        }

        currentComputeDescriptorSets[setIndex] = static_cast<GLESDescriptorSet *>(descriptorSet);
        if ((setIndex + 1) > currentComputeDescriptorSetCount) {
            currentComputeDescriptorSetCount = setIndex + 1;
        }
    }

    void GLESCommandList::setRaytracingDescriptorSet(RenderDescriptorSet *descriptorSet, uint32_t setIndex) {
        (void)descriptorSet;
        (void)setIndex;
        unimplemented("GLESCommandList::setRaytracingDescriptorSet (ray tracing nao existe em GLES 3.2)");
    }

    void GLESCommandList::setGraphicsRootDescriptor(RenderBufferReference bufferReference,
                                                    uint32_t rootDescriptorIndex) {
        (void)bufferReference;
        (void)rootDescriptorIndex;
        // Root descriptors sao do D3D12; o ES 3.2 nao os tem (ver capabilities).
        unimplemented("GLESCommandList::setGraphicsRootDescriptor (ES 3.2 nao tem root descriptors)");
    }

    // -------------------------------------------------------------------------
    // Copias e resolve
    // -------------------------------------------------------------------------

    void GLESCommandList::copyBufferRegion(RenderBufferReference dstBuffer, RenderBufferReference srcBuffer,
                                           uint64_t size) {
        if ((dstBuffer.ref == nullptr) || (srcBuffer.ref == nullptr)) {
            unimplemented("copyBufferRegion com buffer nulo");
        }

        const GLESBuffer *destination = static_cast<const GLESBuffer *>(dstBuffer.ref);
        const GLESBuffer *source = static_cast<const GLESBuffer *>(srcBuffer.ref);

        // glCopyBufferSubData nao reporta copia fora dos limites como erro: gera
        // GL_INVALID_VALUE e NAO copia. Verificar aqui evita uma falha silenciosa.
        if (((dstBuffer.offset + size) > destination->size) || ((srcBuffer.offset + size) > source->size)) {
            unimplemented("copyBufferRegion: copia fora dos limites do buffer");
        }

        // COPY_READ/COPY_WRITE sao exatamente o par definido pelo ES 3.1+ para copia entre
        // buffers sem interferir nos alvos de uso (ARRAY/ELEMENT/UNIFORM).
        glBindBuffer(GL_COPY_READ_BUFFER, static_cast<GLuint>(source->buffer));
        glBindBuffer(GL_COPY_WRITE_BUFFER, static_cast<GLuint>(destination->buffer));
        glCopyBufferSubData(GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER,
                            static_cast<GLintptr>(srcBuffer.offset),
                            static_cast<GLintptr>(dstBuffer.offset),
                            static_cast<GLsizeiptr>(size));
    }

    void GLESCommandList::copyBuffer(const RenderBuffer *dstBuffer, const RenderBuffer *srcBuffer) {
        if ((dstBuffer == nullptr) || (srcBuffer == nullptr)) {
            unimplemented("copyBuffer com buffer nulo");
        }

        const GLESBuffer *destination = static_cast<const GLESBuffer *>(dstBuffer);
        const GLESBuffer *source = static_cast<const GLESBuffer *>(srcBuffer);
        const uint64_t size = (destination->size < source->size) ? destination->size : source->size;

        if (size == 0) {
            return;
        }

        copyBufferRegion(destination->at(0), source->at(0), size);
    }

    void GLESCommandList::copyTexture(const RenderTexture *dstTexture, const RenderTexture *srcTexture) {
        (void)dstTexture;
        (void)srcTexture;

        // Copia textura->textura exige decidir entre glBlitFramebuffer e glCopyImageSubData
        // conforme origem/destino (formato diferente, mip/camada, MSAA), e o caminho real do
        // RT64 aqui e' o de TMEM (M3). Escolher agora, sem o consumidor real, seria chute.
        unimplemented("GLESCommandList::copyTexture (caminho de TMEM = M3)");
    }

    void GLESCommandList::copyTextureRegion(const RenderTextureCopyLocation &dstLocation,
                                            const RenderTextureCopyLocation &srcLocation, uint32_t dstX,
                                            uint32_t dstY, uint32_t dstZ, const RenderBox *srcBox) {
        (void)dstLocation;
        (void)srcLocation;
        (void)dstX;
        (void)dstY;
        (void)dstZ;
        (void)srcBox;
        unimplemented("GLESCommandList::copyTextureRegion (caminho de TMEM = M3)");
    }

    void GLESCommandList::resolveTexture(const RenderTexture *dstTexture, const RenderTexture *srcTexture) {
        resolveTextureRegion(dstTexture, 0, 0, srcTexture, nullptr, RenderResolveMode::AVERAGE);
    }

    void GLESCommandList::resolveTextureRegion(const RenderTexture *dstTexture, uint32_t dstX, uint32_t dstY,
                                               const RenderTexture *srcTexture, const RenderRect *srcRect,
                                               RenderResolveMode resolveMode) {
        if ((dstTexture == nullptr) || (srcTexture == nullptr)) {
            unimplemented("resolveTextureRegion com textura nula");
        }

        const GLESTexture *destination = static_cast<const GLESTexture *>(dstTexture);
        const GLESTexture *source = static_cast<const GLESTexture *>(srcTexture);

        if (destination->isSwapChainTexture || source->isSwapChainTexture) {
            unimplemented("resolveTextureRegion sobre a textura de swapchain (o backbuffer de EGL nao e' objeto GL)");
        }

        // glBlitFramebuffer so' filtra LINEAR (media) ou NEAREST. MIN/MAX seriam outra
        // operacao (reducao) sem equivalente no ES 3.2 -- falha alta em vez de trocar a
        // operacao por media silenciosamente.
        GLenum filter = GL_NEAREST;
        if (resolveMode == RenderResolveMode::AVERAGE) {
            filter = GL_LINEAR;
        } else {
            unimplemented("resolveTextureRegion com modo MIN/MAX (ES 3.2 so' faz media/nearest)");
        }

        GLint srcLeft = 0;
        GLint srcTop = 0;
        GLint srcRight = static_cast<GLint>(source->width);
        GLint srcBottom = static_cast<GLint>(source->height);
        if (srcRect != nullptr) {
            srcLeft = srcRect->left;
            srcTop = srcRect->top;
            srcRight = srcRect->right;
            srcBottom = srcRect->bottom;
        }

        // O blit do GL opera sobre FRAMEBUFFERS, nao sobre texturas soltas. FBOs temporarios
        // sao a forma direta de endereçar as duas texturas sem criar estado permanente.
        GLuint readFramebuffer = 0;
        GLuint drawFramebuffer = 0;
        glGenFramebuffers(1, &readFramebuffer);
        glGenFramebuffers(1, &drawFramebuffer);

        glBindFramebuffer(GL_READ_FRAMEBUFFER, readFramebuffer);
        glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, source->target,
                               static_cast<GLuint>(source->texture), 0);

        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, drawFramebuffer);
        glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, destination->target,
                               static_cast<GLuint>(destination->texture), 0);

        glBlitFramebuffer(srcLeft, srcTop, srcRight, srcBottom,
                          static_cast<GLint>(dstX), static_cast<GLint>(dstY),
                          static_cast<GLint>(dstX) + (srcRight - srcLeft),
                          static_cast<GLint>(dstY) + (srcBottom - srcTop),
                          GL_COLOR_BUFFER_BIT, filter);

        glDeleteFramebuffers(1, &readFramebuffer);
        glDeleteFramebuffers(1, &drawFramebuffer);

        // Os binds de READ/DRAW acima invalidaram o vinculo do command list. O espelho tem
        // que refletir isso: senao o proximo setFramebuffer pularia a vinculacao e o desenho
        // iria para o framebuffer errado.
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        currentFramebuffer = nullptr;
    }

    void GLESCommandList::buildBottomLevelAS(const RenderAccelerationStructure *dstAccelerationStructure,
                                             RenderBufferReference scratchBuffer,
                                             const RenderBottomLevelASBuildInfo &buildInfo) {
        (void)dstAccelerationStructure;
        (void)scratchBuffer;
        (void)buildInfo;
        unimplemented("GLESCommandList::buildBottomLevelAS (ray tracing nao existe em GLES 3.2)");
    }

    void GLESCommandList::buildTopLevelAS(const RenderAccelerationStructure *dstAccelerationStructure,
                                          RenderBufferReference scratchBuffer,
                                          RenderBufferReference instancesBuffer,
                                          const RenderTopLevelASBuildInfo &buildInfo) {
        (void)dstAccelerationStructure;
        (void)scratchBuffer;
        (void)instancesBuffer;
        (void)buildInfo;
        unimplemented("GLESCommandList::buildTopLevelAS (ray tracing nao existe em GLES 3.2)");
    }

    void GLESCommandList::discardTexture(const RenderTexture *texture) {
        // No D3D12 isto autoriza o driver a DESCARTAR o conteudo da textura (os dados ficam
        // indefinidos) -- uma otimizacao. O GL nao tem equivalente, e NAO descartar e' seguro:
        // o conteudo antigo permanece, que e' um superconjunto valido do contrato. Por isso
        // este e' um no-op DELIBERADO, e nao um stub silencioso de funcionalidade faltante.
        (void)texture;
    }

    void GLESCommandList::resetQueryPool(const RenderQueryPool *queryPool, uint32_t queryFirstIndex,
                                         uint32_t queryCount) {
        (void)queryPool;
        (void)queryFirstIndex;
        (void)queryCount;
        unimplemented("GLESCommandList::resetQueryPool (ES 3.2 nao tem query objects de timestamp)");
    }

    void GLESCommandList::writeTimestamp(const RenderQueryPool *queryPool, uint32_t queryIndex) {
        (void)queryPool;
        (void)queryIndex;
        unimplemented("GLESCommandList::writeTimestamp (ES 3.2 nao tem timestamp; EXT_disjoint_timer_query ausente)");
    }

    // =========================================================================
    // Fila de comandos
    // =========================================================================

    GLESCommandQueue::GLESCommandQueue(GLESDevice *device, RenderCommandListType type) {
        this->device = device;
        this->type = type;
    }

    GLESCommandQueue::~GLESCommandQueue() {
    }

    std::unique_ptr<RenderCommandList> GLESCommandQueue::createCommandList() {
        return std::make_unique<GLESCommandList>(device, this, type);
    }

    std::unique_ptr<RenderSwapChain> GLESCommandQueue::createSwapChain(const RenderSwapChainDesc &desc) {
        return std::make_unique<GLESSwapChain>(device, device->window, device->swapFunctions, desc);
    }

    void GLESCommandQueue::executeCommandLists(const RenderCommandList **commandLists,
                                               uint32_t commandListCount,
                                               RenderCommandSemaphore **waitSemaphores,
                                               uint32_t waitSemaphoreCount,
                                               RenderCommandSemaphore **signalSemaphores,
                                               uint32_t signalSemaphoreCount,
                                               RenderCommandFence *signalFence) {
        (void)waitSemaphores;
        (void)waitSemaphoreCount;
        (void)signalSemaphores;
        (void)signalSemaphoreCount;

        // Modo IMEDIATO (ver a nota de desenho no header): os command lists ja' EXECUTARAM
        // tudo durante a gravacao. Nao ha fila de replay -- o que sobra e' empurrar o
        // trabalho para o driver.
        for (uint32_t i = 0; i < commandListCount; i++) {
            if (commandLists[i] == nullptr) {
                unimplemented("executeCommandLists com command list nulo");
            }
        }

        glFlush();

        // Uma fence sinalizada significa "o CPU pode depender do resultado". No GL isso
        // corresponde a glFinish() (bloqueia ate' o driver terminar), nao a glFlush().
        if (signalFence != nullptr) {
            glFinish();
        }
    }

    void GLESCommandQueue::waitForCommandFence(RenderCommandFence *fence) {
        (void)fence;
        glFinish();
    }

    // =========================================================================
    // Swap chain
    // =========================================================================
    //
    // No GLES a apresentacao NAO e' um objeto: o backbuffer pertence ao contexto/EGLSurface
    // e o "swap" e' uma operacao da janela (SDL_GL_SwapWindow). Este swapchain existe para
    // dar ao RT64 a FORMA que ele espera (texturas + present + tamanho), delegando o swap
    // real ao shim `GLESSwapChainFunctions` -- o que mantem SDL fora do backend.

    GLESSwapChain::GLESSwapChain(GLESDevice *device, void *window,
                                 const GLESSwapChainFunctions &swapFunctions,
                                 const RenderSwapChainDesc &desc) {
        this->device = device;
        this->swapFunctions = swapFunctions;
        this->desc = desc;
        this->window = window;
        this->textureIndex = 0;
        this->vsyncEnabled = true;
        this->presentPending = false;

        int windowWidth = 0;
        int windowHeight = 0;
        if ((swapFunctions.getWindowSize != nullptr) && (window != nullptr)) {
            swapFunctions.getWindowSize(window, &windowWidth, &windowHeight);
        }

        if ((windowWidth <= 0) || (windowHeight <= 0)) {
            // Modo headless (smoke test / sem janela): usa o viewport corrente do contexto,
            // que e' o tamanho real do drawable do EGLSurface.
            GLint viewport[4] = { 0, 0, 0, 0 };
            glGetIntegerv(GL_VIEWPORT, viewport);
            windowWidth = viewport[2];
            windowHeight = viewport[3];
        }

        if ((windowWidth <= 0) || (windowHeight <= 0)) {
            // Sem janela E sem viewport valido nao ha como inferir o tamanho. Avisar e usar
            // 1x1 permite que o chamador perceba e corrija (resize()) sem abortar um teste
            // headless -- mas NUNCA em silencio.
            std::fprintf(stderr,
                         "[plume_gles] AVISO: swapchain sem tamanho de janela nem viewport; "
                         "assumindo 1x1. Chame resize() ou forneca getWindowSize.\n");
            std::fflush(stderr);
            windowWidth = 1;
            windowHeight = 1;
        }

        this->width = static_cast<uint32_t>(windowWidth);
        this->height = static_cast<uint32_t>(windowHeight);

        this->backBuffer = std::make_unique<GLESTexture>(device, width, height, desc.format, true);

        setVsyncEnabled(true);
    }

    GLESSwapChain::~GLESSwapChain() {
    }

    bool GLESSwapChain::present(uint32_t textureIndex, RenderCommandSemaphore **waitSemaphores,
                                uint32_t waitSemaphoreCount) {
        (void)waitSemaphores;
        (void)waitSemaphoreCount;

        this->textureIndex = textureIndex;

        if ((swapFunctions.swapWindow != nullptr) && (window != nullptr)) {
            // Caminho de producao no R36S: SDL_GL_SwapWindow, que faz o eglSwapBuffers.
            swapFunctions.swapWindow(window);
        } else {
            // Sem janela (smoke test headless): o "present" vira o ponto de sincronizacao.
            // E' o comportamento documentado no header, e o que torna o aceite do M2
            // verificavel sob QEMU sem display.
            glFinish();
        }

        presentPending = false;
        return true;
    }

    void GLESSwapChain::wait() {
        // O "wait" de um swapchain Vulkan espera a imagem estar livre. No GL nao ha imagem
        // em voo: o swap ja' devolveu o controle. glFinish() garante que o trabalho de GPU
        // terminou antes de o chamador mexer no backbuffer.
        glFinish();
    }

    bool GLESSwapChain::resize() {
        if ((swapFunctions.getWindowSize == nullptr) || (window == nullptr)) {
            return false;
        }

        int windowWidth = 0;
        int windowHeight = 0;
        swapFunctions.getWindowSize(window, &windowWidth, &windowHeight);
        if ((windowWidth <= 0) || (windowHeight <= 0)) {
            return false;
        }

        if ((static_cast<uint32_t>(windowWidth) == width) && (static_cast<uint32_t>(windowHeight) == height)) {
            return false;
        }

        width = static_cast<uint32_t>(windowWidth);
        height = static_cast<uint32_t>(windowHeight);

        // No GL o backbuffer pertence ao contexto/EGLSurface: nao ha "imagens antigas" a
        // reciclar. Basta o novo tamanho; o RT64 recria os framebuffers dele a partir do
        // getWidth()/getHeight().
        backBuffer = std::make_unique<GLESTexture>(device, width, height, desc.format, true);
        return true;
    }

    bool GLESSwapChain::needsResize() const {
        if ((swapFunctions.getWindowSize == nullptr) || (window == nullptr)) {
            return false;
        }

        int windowWidth = 0;
        int windowHeight = 0;
        swapFunctions.getWindowSize(window, &windowWidth, &windowHeight);
        if ((windowWidth <= 0) || (windowHeight <= 0)) {
            return false;
        }

        return (static_cast<uint32_t>(windowWidth) != width) || (static_cast<uint32_t>(windowHeight) != height);
    }

    void GLESSwapChain::setVsyncEnabled(bool vsyncEnabled) {
        this->vsyncEnabled = vsyncEnabled;

        // O intervalo de swap e' estado do CONTEXTO no GL, nao do drawable: por isso a chamada
        // so' pode ser feita com um contexto corrente (e' o caso: este backend exige isso).
        if (swapFunctions.setSwapInterval != nullptr) {
            swapFunctions.setSwapInterval(vsyncEnabled ? 1 : 0);
        }
    }

    bool GLESSwapChain::isVsyncEnabled() const {
        return vsyncEnabled;
    }

    uint32_t GLESSwapChain::getWidth() const {
        return width;
    }

    uint32_t GLESSwapChain::getHeight() const {
        return height;
    }

    RenderTexture *GLESSwapChain::getTexture(uint32_t textureIndex) {
        (void)textureIndex;

        // Um unico "backbuffer logico": o GLES nao expoe multiplas imagens de swapchain para
        // o aplicativo escolher (isso e' o Vulkan/DXGI). O RT64 usa getTextureCount() para
        // dimensionar, e ele recebe 1.
        return backBuffer.get();
    }

    uint32_t GLESSwapChain::getTextureCount() const {
        return 1;
    }

    bool GLESSwapChain::acquireTexture(RenderCommandSemaphore *signalSemaphore, uint32_t *textureIndex) {
        (void)signalSemaphore;

        if (textureIndex == nullptr) {
            unimplemented("acquireTexture sem ponteiro de saida");
        }

        // Sempre ha' a imagem 0 disponivel: no GL o backbuffer nunca esta' "em uso" por um
        // consumidor assincrono (a fila e' a propria ordem das chamadas no contexto).
        *textureIndex = 0;
        return true;
    }

    RenderWindow GLESSwapChain::getWindow() const {
        return desc.renderWindow;
    }

    bool GLESSwapChain::isEmpty() const {
        return false;
    }

    uint32_t GLESSwapChain::getRefreshRate() const {
        if ((swapFunctions.getDisplayRefreshRate != nullptr) && (window != nullptr)) {
            return swapFunctions.getDisplayRefreshRate(window);
        }

        // 0 = desconhecido. So' e' consultado quando `displayTiming` esta' ligado -- e no
        // GLES ele e' declarado false (ver capabilities), logo este 0 nunca e' usado para
        // decisao de timing.
        return 0;
    }

    // =========================================================================
    // Device: consultas e criacao
    // =========================================================================
    //
    // NOTA DE AUDITORIA (M2/s2): `hasExtension` e `validateShaderFormat` estavam DECLARADOS
    // no header desde a sessao 1, mas NUNCA definidos -- e a verificacao daquela sessao usou
    // apenas `-fsyntax-only`, que nao linka e por isso nao detecta simbolo faltante. Eles
    // sao definidos aqui, e o aceite desta sessao passa a incluir LINK (ver evidencia).

    bool GLESDevice::hasExtension(const char *name) const {
        if (glExtensions.empty() || (name == nullptr)) {
            return false;
        }

        // A lista vem de glGetStringi separada por UM espaco. Cercar os dois lados (lista e
        // termo) evita o falso positivo classico de substring: "GL_EXT_geometry_shader"
        // casaria dentro de "GL_EXT_geometry_shader_something".
        std::string haystack;
        haystack.reserve(glExtensions.size() + 2);
        haystack += ' ';
        haystack += glExtensions;
        haystack += ' ';

        std::string needle;
        needle.reserve(std::strlen(name) + 2);
        needle += ' ';
        needle += name;
        needle += ' ';

        return haystack.find(needle) != std::string::npos;
    }

    bool GLESDevice::validateShaderFormat(RenderShaderFormat format) const {
        // A interface declara shaderFormat = GLSL_ES, logo so' ESSL e' valido. Os blobs
        // carregados neste porte sao SPIR-V compilados com -D HLSL_GLES e convertidos para
        // ESSL pelo caminho do M1.3 ANTES de chegar aqui.
        return format == RenderShaderFormat::GLSL_ES;
    }

    std::unique_ptr<RenderDescriptorSet> GLESDevice::createDescriptorSet(const RenderDescriptorSetDesc &desc) {
        return std::make_unique<GLESDescriptorSet>(this, desc);
    }

    std::unique_ptr<RenderShader> GLESDevice::createShader(const void *data, uint64_t size,
                                                          const char *entryPointName,
                                                          RenderShaderFormat format) {
        if (!validateShaderFormat(format)) {
            unimplemented("createShader: formato != GLSL_ES (ver validateShaderFormat)");
        }

        return std::make_unique<GLESShader>(this, data, size, entryPointName, format);
    }

    std::unique_ptr<RenderSampler> GLESDevice::createSampler(const RenderSamplerDesc &desc) {
        return std::make_unique<GLESSampler>(this, desc);
    }

    std::unique_ptr<RenderPipeline> GLESDevice::createComputePipeline(const RenderComputePipelineDesc &desc) {
        return std::make_unique<GLESComputePipeline>(this, desc);
    }

    std::unique_ptr<RenderPipeline> GLESDevice::createGraphicsPipeline(const RenderGraphicsPipelineDesc &desc) {
        return std::make_unique<GLESGraphicsPipeline>(this, desc);
    }

    std::unique_ptr<RenderPipeline> GLESDevice::createRaytracingPipeline(
        const RenderRaytracingPipelineDesc &desc, const RenderPipeline *previousPipeline) {
        (void)desc;
        (void)previousPipeline;
        unimplemented("createRaytracingPipeline (ray tracing nao existe em GLES 3.2)");
    }

    std::unique_ptr<RenderCommandQueue> GLESDevice::createCommandQueue(RenderCommandListType type) {
        return std::make_unique<GLESCommandQueue>(this, type);
    }

    std::unique_ptr<RenderBuffer> GLESDevice::createBuffer(const RenderBufferDesc &desc) {
        return std::make_unique<GLESBuffer>(this, desc);
    }

    std::unique_ptr<RenderTexture> GLESDevice::createTexture(const RenderTextureDesc &desc) {
        return std::make_unique<GLESTexture>(this, desc);
    }

    std::unique_ptr<RenderAccelerationStructure> GLESDevice::createAccelerationStructure(
        const RenderAccelerationStructureDesc &desc) {
        (void)desc;
        unimplemented("createAccelerationStructure (ray tracing nao existe em GLES 3.2)");
    }

    std::unique_ptr<RenderPool> GLESDevice::createPool(const RenderPoolDesc &desc) {
        return std::make_unique<GLESPool>(this, desc);
    }

    std::unique_ptr<RenderPipelineLayout> GLESDevice::createPipelineLayout(
        const RenderPipelineLayoutDesc &desc) {
        return std::make_unique<GLESPipelineLayout>(this, desc);
    }

    std::unique_ptr<RenderCommandFence> GLESDevice::createCommandFence() {
        return std::make_unique<GLESCommandFence>(this);
    }

    std::unique_ptr<RenderCommandSemaphore> GLESDevice::createCommandSemaphore() {
        return std::make_unique<GLESCommandSemaphore>(this);
    }

    std::unique_ptr<RenderFramebuffer> GLESDevice::createFramebuffer(const RenderFramebufferDesc &desc) {
        return std::make_unique<GLESFramebuffer>(this, desc);
    }

    std::unique_ptr<RenderQueryPool> GLESDevice::createQueryPool(uint32_t queryCount) {
        // A capacidade `queryPools` (ver queryContextInfo) ja' informa ao RT64 que nao ha
        // timestamp no ES 3.2 sem EXT_disjoint_timer_query. Criar o pool mesmo assim (com
        // zeros) evita um null deref caso o RT64 crie o pool antes de checar a capacidade;
        // quem de fato escreve/le' timestamp aborta em resetQueryPool/writeTimestamp.
        return std::make_unique<GLESQueryPool>(this, queryCount);
    }

    void GLESDevice::setBottomLevelASBuildInfo(RenderBottomLevelASBuildInfo &buildInfo,
                                               const RenderBottomLevelASMesh *meshes, uint32_t meshCount,
                                               bool preferFastBuild, bool preferFastTrace) {
        (void)buildInfo;
        (void)meshes;
        (void)meshCount;
        (void)preferFastBuild;
        (void)preferFastTrace;
        unimplemented("setBottomLevelASBuildInfo (ray tracing nao existe em GLES 3.2)");
    }

    void GLESDevice::setTopLevelASBuildInfo(RenderTopLevelASBuildInfo &buildInfo,
                                            const RenderTopLevelASInstance *instances,
                                            uint32_t instanceCount, bool preferFastBuild,
                                            bool preferFastTrace) {
        (void)buildInfo;
        (void)instances;
        (void)instanceCount;
        (void)preferFastBuild;
        (void)preferFastTrace;
        unimplemented("setTopLevelASBuildInfo (ray tracing nao existe em GLES 3.2)");
    }

    void GLESDevice::setShaderBindingTableInfo(RenderShaderBindingTableInfo &tableInfo,
                                               const RenderShaderBindingGroups &groups,
                                               const RenderPipeline *pipeline,
                                               RenderDescriptorSet **descriptorSets,
                                               uint32_t descriptorSetCount) {
        (void)tableInfo;
        (void)groups;
        (void)pipeline;
        (void)descriptorSets;
        (void)descriptorSetCount;
        unimplemented("setShaderBindingTableInfo (ray tracing nao existe em GLES 3.2)");
    }

    const RenderDeviceCapabilities &GLESDevice::getCapabilities() const {
        return capabilities;
    }

    const RenderDeviceDescription &GLESDevice::getDescription() const {
        return description;
    }

    RenderSampleCounts GLESDevice::getSampleCountsSupported(RenderFormat format) const {
        // O ES 3.2 limita a contagem de amostras por GL_MAX_SAMPLES, e formatos de
        // profundidade/stencil tem suporte mais restrito em hardware (no Mali-G31 as vezes
        // 1x apenas). Reportar apenas o que foi MEDIDO evita pedir MSAA ao driver e
        // descobrir depois que o framebuffer ficou incompleto.
        switch (format) {
        case RenderFormat::D16_UNORM:
        case RenderFormat::D32_FLOAT:
        case RenderFormat::D32_FLOAT_S8_UINT:
            return RenderSampleCount::COUNT_1;
        default:
            break;
        }

        RenderSampleCounts supported = RenderSampleCount::COUNT_1;
        if (maxSamples >= 2) {
            supported |= RenderSampleCount::COUNT_2;
        }
        if (maxSamples >= 4) {
            supported |= RenderSampleCount::COUNT_4;
        }
        if (maxSamples >= 8) {
            supported |= RenderSampleCount::COUNT_8;
        }

        return supported;
    }

    bool GLESDevice::beginCapture() {
        // Sem RenderDoc/NSight no R36S. Retornar false e' o contrato: "captura indisponivel".
        return false;
    }

    bool GLESDevice::endCapture() {
        return false;
    }
}