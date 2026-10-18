//
// plume_gles -- implementacao do carregador gerado (ver plume_gles_gl.h).
//
// *****************************************************************************
// ARQUIVO GERADO -- NAO EDITE A MAO (evidencias/tools/gen_gles_loader.py).
// *****************************************************************************

#include "plume_gles_gl.h"

namespace plume {
namespace gl {

#define PLUME_GL_DEFINE_PTR(name) PFN_##name name = nullptr;
PLUME_GL_FUNCTIONS(PLUME_GL_DEFINE_PTR)
#undef PLUME_GL_DEFINE_PTR

static std::vector<std::string> g_missing;

const std::vector<std::string> &missing() {
    return g_missing;
}

bool load(PlumeGLProcResolver resolver) {
    g_missing.clear();

    if (resolver == nullptr) {
        g_missing.push_back("<null resolver>");
        return false;
    }

#define PLUME_GL_LOAD_PTR(name) \
    name = reinterpret_cast<PFN_##name>(resolver(#name)); \
    if (name == nullptr) { g_missing.push_back(#name); }
    PLUME_GL_FUNCTIONS(PLUME_GL_LOAD_PTR)
#undef PLUME_GL_LOAD_PTR

    return g_missing.empty();
}

} // namespace gl
} // namespace plume
