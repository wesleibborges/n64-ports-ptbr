//
// m2_hdr_coverage.cpp -- prova de cobertura da interface Plume pelo esqueleto
// plume_gles (M2, sessao 1).
//
// Por que existe: um backend que esquece de sobrescrever um metodo virtual puro
// nao gera erro de compilacao por si so -- a classe apenas permanece ABSTRATA. O
// erro so aparece no primeiro `new`/`make_unique`, muitas vezes tarde e no device.
// Estes static_asserts tornam a cobertura um erro de COMPILACAO, verificavel no
// host sem GPU, sem sysroot e sem libGLESv2.
//
// Regra: toda classe concreta do backend deve ser instanciavel (nao-abstrata);
// GLESPipeline, que e a base comum dos pipelines, deve permanecer abstrata.
//

#include "plume_gles.h"

#include <type_traits>

using namespace plume;

#define REQUIRE_CONCRETE(TYPE) \
    static_assert(!std::is_abstract_v<TYPE>, #TYPE " nao sobrescreveu todos os virtuais puros")

#define REQUIRE_ABSTRACT(TYPE) \
    static_assert(std::is_abstract_v<TYPE>, #TYPE " deveria permanecer abstrata")

// Recursos.
REQUIRE_CONCRETE(GLESBufferFormattedView);
REQUIRE_CONCRETE(GLESBuffer);
REQUIRE_CONCRETE(GLESTextureView);
REQUIRE_CONCRETE(GLESTexture);
REQUIRE_CONCRETE(GLESAccelerationStructure);
REQUIRE_CONCRETE(GLESShader);
REQUIRE_CONCRETE(GLESSampler);
REQUIRE_CONCRETE(GLESPipelineLayout);
REQUIRE_CONCRETE(GLESCommandFence);
REQUIRE_CONCRETE(GLESCommandSemaphore);
REQUIRE_CONCRETE(GLESDescriptorSet);
REQUIRE_CONCRETE(GLESFramebuffer);
REQUIRE_CONCRETE(GLESSwapChain);
REQUIRE_CONCRETE(GLESQueryPool);
REQUIRE_CONCRETE(GLESPool);

// Pipelines: a base e abstrata (nao implementa getProgram/setName); as concretas nao.
REQUIRE_ABSTRACT(GLESPipeline);
REQUIRE_CONCRETE(GLESComputePipeline);
REQUIRE_CONCRETE(GLESGraphicsPipeline);

// Agregados.
REQUIRE_CONCRETE(GLESCommandList);
REQUIRE_CONCRETE(GLESCommandQueue);
REQUIRE_CONCRETE(GLESDevice);
REQUIRE_CONCRETE(GLESInterface);

int main() {
    return 0;
}