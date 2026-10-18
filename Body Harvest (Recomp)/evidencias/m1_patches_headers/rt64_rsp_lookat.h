//
// RT64
//

#pragma once

#include "shared/rt64_hlsl.h"

#define RSP_LOOKAT_INDEX_ENABLED 0x1
#define RSP_LOOKAT_INDEX_LINEAR 0x2
#define RSP_LOOKAT_INDEX_SHIFT 2

#ifdef HLSL_CPU
namespace interop {
#endif
    struct RSPLookAt {
        float3 x;
        float padding; // M1-GLES: y @16
        float3 y;
        float padding2; // M1-GLES: stride 32
    };
#ifdef HLSL_CPU
};
#endif