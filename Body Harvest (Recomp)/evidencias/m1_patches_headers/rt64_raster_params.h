//
// RT64
//

#pragma once

#include "shared/rt64_hlsl.h"

#ifdef HLSL_CPU
namespace interop {
#endif
    struct RasterParams {
        uint renderIndex;
        uint padding0; // M1-GLES: padding (uint3) @16
        uint padding1;
        uint padding2;
        uint3 padding;
        uint padding3; // M1-GLES: screenScale (vec2) @32
        float2 screenScale;
        float2 screenOffset;
    };
#ifdef HLSL_CPU
};
#endif