//
// RT64
//

#pragma once

#include "rt64_hlsl.h"

#ifdef HLSL_CPU
namespace interop {
#endif
    struct RDPParams {
        float4 primColor;
        float2 primLOD;
        float2 primDepth;
        float4 envColor;
        float4 fogColor;
        float4 blendColor;
        float3 keyCenter;
        float padding; // M1-GLES: keyScale @16
        float3 keyScale;
        int convertK[6];
        int padding2[3]; // M1-GLES: stride 144 (multiplo de 16)
    };
#ifdef HLSL_CPU
};
#endif