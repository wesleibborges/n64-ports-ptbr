#version 320 es
precision mediump float;
precision highp int;

struct _17
{
    highp vec4 _m0;
    highp vec2 _m1;
    highp vec2 _m2;
    highp vec4 _m3;
    highp vec4 _m4;
    highp vec4 _m5;
    highp vec3 _m6;
    highp float _m7;
    highp vec3 _m8;
    int _m9[6];
    int _m10[3];
};

struct _20
{
    int _m0;
    int _m1;
    int _m2;
    int _m3;
    int _m4;
    int _m5;
    int _m6;
    highp float _m7;
    highp float _m8;
    highp float _m9;
    highp float _m10;
    highp float _m11;
    highp float _m12;
    int _m13;
    int _m14;
    uint _m15;
};

struct _23
{
    highp vec2 _m0;
    highp vec2 _m1;
    uvec2 _m2;
    uvec2 _m3;
    uint _m4;
    uint _m5;
    uint _m6;
    uint _m7;
    highp vec3 _m8;
    uint _m9;
};

struct _26
{
    uint _m0;
    uint _m1;
    uint _m2;
    uint _m3;
    uint _m4;
};

layout(binding = 1, std140) uniform _14_15
{
    uint _m0;
    uint _m1;
    highp float _m2;
} _15;

layout(binding = 2, std430) readonly buffer _16_18
{
    _17 _m0[];
} _18;

layout(binding = 3, std430) readonly buffer _19_21
{
    _20 _m0[];
} _21;

layout(binding = 4, std430) readonly buffer _22_24
{
    _23 _m0[];
} _24;

layout(binding = 5, std430) readonly buffer _25_27
{
    _26 _m0[];
} _27;

layout(binding = 0, std140) uniform _51_52
{
    highp vec2 _m0;
    highp vec2 _m1;
    highp float _m2;
} _52;

struct _53
{
    uint _m0;
    uint _m1;
    uint _m2;
    uint _m3;
    uvec3 _m4;
    uint _m5;
    highp vec2 _m6;
    highp vec2 _m7;
};

uniform _53 _54;

uniform highp sampler2D SPIRV_Cross_Combined[8192];
uniform highp sampler2D SPIRV_Cross_Combined_1[8192];
uniform highp sampler2D SPIRV_Cross_Combined_2[8192];
uniform highp sampler2D SPIRV_Cross_Combined_3[8192];

layout(location = 0) in highp vec2 _4;
layout(location = 1) in highp vec4 _5;
layout(location = 2) flat in highp vec4 _6;
layout(location = 0, index = 0) out highp vec4 _7;
layout(location = 0, index = 1) out highp vec4 _8;

vec4 _214;
float _215;
vec4 _247;

void main()
{
    highp vec4 _12556;
    highp vec4 _12557;
    bool _12558;
    do
    {
        highp vec4 _270;
        _270 = _5;
        bool _539 = !((747626510u & 1u) != 0u);
        bool _543;
        _543 = !((3356565624u & 4u) == 4u);
        if (gl_FragCoord.z > (_543 ? 0.998046875 : 1.0))
        {
            _12556 = _247;
            _12557 = _247;
            _12558 = false;
            break;
        }
        highp vec2 _643 = dFdx(_4);
        highp vec2 _644 = dFdy(_4);
        highp vec2 _665;
        _665 = _4;
        int _742;
        int _743;
        _742 = 1;
        _743 = 0;
        uint _752 = _27._m0[_54._m0]._m2 + uint(_743);
        bool _803 = (_24._m0[_752]._m9 & 2u) != 0u;
        highp vec4 _5620;
        do
        {
            highp vec2 _815 = (mix(_665, _4, bvec2(_803)) * (((!((1584128u & 524288u) == 524288u)) ? _539 : false) ? 0.5 : 1.0)) * vec2(_21._m0[_752]._m7, _21._m0[_752]._m8);
            highp vec2 _822;
            if (!_803)
            {
                _822 = roundEven(_815 * 128.0) * vec2(0.0078125);
            }
            else
            {
                _822 = _815;
            }
            highp vec2 _828;
            if ((_24._m0[_752]._m9 & 32u) != 0u)
            {
                _828 = _822 + vec2(0.5);
            }
            else
            {
                _828 = _822;
            }
            highp vec2 _832 = fma(_828, _24._m0[_752]._m1, (vec2(_21._m0[_752]._m9, _21._m0[_752]._m10) * _24._m0[_752]._m0) * vec2(-0.25));
            bool _848;
            _848 = false;
            highp vec2 _855;
            if (_848 ? _803 : false)
            {
                _855 = roundEven(_832 * 8.0) * vec2(0.125);
            }
            else
            {
                _855 = _832;
            }
            bool _864 = (_24._m0[_752]._m9 & 16u) != 0u;
            highp float _932;
            uint _933;
            uint _934;
            if (_864)
            {
                highp vec2 _875 = _24._m0[_752]._m8.xy / _24._m0[_752]._m1;
                highp vec4 _916;
                do
                {
                    _916 = textureGrad(SPIRV_Cross_Combined[_24._m0[_752]._m4], _855 / _24._m0[_752]._m8.xy, _643 / _875, _644 / _875);
                    break;
                } while(false);
                _5620 = _916;
                break;
            }
            else
            {
                _932 = _215;
                _933 = 0u;
                _934 = 0u;
            }
            highp vec4 _3265;
            do
            {
                highp vec2 _942 = _855 / vec2(float(1u << (_934 & 31u)));
                ivec2 _945 = ivec2(floor(_942));
                highp vec4 _1002;
                do
                {
                    _1002 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_945) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1047;
                do
                {
                    _1047 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_945 + ivec2(0, 1)) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1090;
                do
                {
                    _1090 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_945 + ivec2(1, 0)) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1133;
                do
                {
                    _1133 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_945 + ivec2(1)) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1134;
                highp vec4 _1135;
                highp vec4 _1136;
                _1134 = _1133;
                _1135 = _1090;
                _1136 = _1047;
                highp vec4 _3213;
                highp vec4 _3214;
                highp vec4 _3215;
                highp vec4 _3216;
                _3213 = _1134;
                _3214 = _1135;
                _3215 = _1136;
                _3216 = _1002;
                highp vec2 _3221 = _942 - vec2(_945);
                highp float _3236 = _3221.x;
                highp float _3240 = _3221.y;
                _3265 = mix(mix(_3216, _3214, vec4(_3236)) + ((_3215 - _3216) * _3240), mix(_3213, _3215, vec4(1.0 - _3236)) + ((_3214 - _3213) * (1.0 - _3240)), vec4(step(1.0, _3236 + _3240)));
                break;
            } while(false);
            highp vec4 _5596;
            if ((_864 ? 2u : 1u) > 1u)
            {
                highp vec4 _5595;
                do
                {
                    highp vec2 _3275 = _855 / vec2(float(1u << (_933 & 31u)));
                    ivec2 _3278 = ivec2(floor(_3275));
                    highp vec4 _3332;
                    do
                    {
                        _3332 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_3278) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3377;
                    do
                    {
                        _3377 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_3278 + ivec2(0, 1)) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3420;
                    do
                    {
                        _3420 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_3278 + ivec2(1, 0)) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3463;
                    do
                    {
                        _3463 = textureLod(SPIRV_Cross_Combined_1[_24._m0[_752]._m4], (vec2(_3278 + ivec2(1)) + vec2(0.5)) / _24._m0[_752]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3464;
                    highp vec4 _3465;
                    highp vec4 _3466;
                    _3464 = _3463;
                    _3465 = _3420;
                    _3466 = _3377;
                    highp vec4 _5543;
                    highp vec4 _5544;
                    highp vec4 _5545;
                    highp vec4 _5546;
                    _5543 = _3464;
                    _5544 = _3465;
                    _5545 = _3466;
                    _5546 = _3332;
                    highp vec2 _5551 = _3275 - vec2(_3278);
                    highp float _5566 = _5551.x;
                    highp float _5570 = _5551.y;
                    _5595 = mix(mix(_5546, _5544, vec4(_5566)) + ((_5545 - _5546) * _5570), mix(_5543, _5545, vec4(1.0 - _5566)) + ((_5544 - _5543) * (1.0 - _5570)), vec4(step(1.0, _5566 + _5570)));
                    break;
                } while(false);
                _5596 = _5595;
            }
            else
            {
                _5596 = _214;
            }
            highp vec4 _5604;
            if (!_864)
            {
                _5604 = _3265;
            }
            else
            {
                _5604 = mix(_3265, _5596, vec4(fract(_932)));
            }
            highp vec4 _5619;
            if ((_24._m0[_752]._m9 & 1u) != 0u)
            {
                highp float _5612 = roundEven(_5604.w * ((((747626510u >> 29u) & 1u) != 0u) ? 65535.0 : 255.0));
                highp vec4 _5618 = _5604;
                _5618.w = float((int(_5612 - 8.0 * trunc(_5612 / 8.0)) & 4) != 0);
                _5619 = _5618;
            }
            else
            {
                _5619 = _5604;
            }
            _5620 = _5619;
            break;
        } while(false);
        highp vec4 _5621;
        _5621 = _5620;
        uint _5633 = _27._m0[_54._m0]._m2 + uint(((1584128u & 3145728u) == 0u) ? _743 : _742);
        bool _5702 = (_24._m0[_5633]._m9 & 2u) != 0u;
        highp vec4 _10525;
        do
        {
            highp vec2 _5714 = (mix(_665, _4, bvec2(_5702)) * (((!((1584128u & 524288u) == 524288u)) ? _539 : false) ? 0.5 : 1.0)) * vec2(_21._m0[_5633]._m7, _21._m0[_5633]._m8);
            highp vec2 _5721;
            if (!_5702)
            {
                _5721 = roundEven(_5714 * 128.0) * vec2(0.0078125);
            }
            else
            {
                _5721 = _5714;
            }
            highp vec2 _5728;
            _5728 = _5721;
            highp vec2 _5734;
            if ((_24._m0[_5633]._m9 & 32u) != 0u)
            {
                _5734 = _5728 + vec2(0.5);
            }
            else
            {
                _5734 = _5728;
            }
            highp vec2 _5738 = fma(_5734, _24._m0[_5633]._m1, (vec2(_21._m0[_5633]._m9, _21._m0[_5633]._m10) * _24._m0[_5633]._m0) * vec2(-0.25));
            bool _5753;
            _5753 = false;
            highp vec2 _5760;
            if (_5753 ? _5702 : false)
            {
                _5760 = roundEven(_5738 * 8.0) * vec2(0.125);
            }
            else
            {
                _5760 = _5738;
            }
            bool _5769 = (_24._m0[_5633]._m9 & 16u) != 0u;
            highp float _5837;
            uint _5838;
            uint _5839;
            if (_5769)
            {
                highp vec2 _5780 = _24._m0[_5633]._m8.xy / _24._m0[_5633]._m1;
                highp vec4 _5821;
                do
                {
                    _5821 = textureGrad(SPIRV_Cross_Combined_2[_24._m0[_5633]._m4], _5760 / _24._m0[_5633]._m8.xy, _643 / _5780, _644 / _5780);
                    break;
                } while(false);
                _10525 = _5821;
                break;
            }
            else
            {
                _5837 = _215;
                _5838 = 0u;
                _5839 = 0u;
            }
            highp vec4 _8170;
            do
            {
                highp vec2 _5847 = _5760 / vec2(float(1u << (_5839 & 31u)));
                ivec2 _5850 = ivec2(floor(_5847));
                highp vec4 _5907;
                do
                {
                    _5907 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_5850) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _5952;
                do
                {
                    _5952 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_5850 + ivec2(0, 1)) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _5995;
                do
                {
                    _5995 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_5850 + ivec2(1, 0)) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _6038;
                do
                {
                    _6038 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_5850 + ivec2(1)) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _6039;
                highp vec4 _6040;
                highp vec4 _6041;
                _6039 = _6038;
                _6040 = _5995;
                _6041 = _5952;
                highp vec4 _8118;
                highp vec4 _8119;
                highp vec4 _8120;
                highp vec4 _8121;
                _8118 = _6039;
                _8119 = _6040;
                _8120 = _6041;
                _8121 = _5907;
                highp vec2 _8126 = _5847 - vec2(_5850);
                highp float _8141 = _8126.x;
                highp float _8145 = _8126.y;
                _8170 = mix(mix(_8121, _8119, vec4(_8141)) + ((_8120 - _8121) * _8145), mix(_8118, _8120, vec4(1.0 - _8141)) + ((_8119 - _8118) * (1.0 - _8145)), vec4(step(1.0, _8141 + _8145)));
                break;
            } while(false);
            highp vec4 _10501;
            if ((_5769 ? 2u : 1u) > 1u)
            {
                highp vec4 _10500;
                do
                {
                    highp vec2 _8180 = _5760 / vec2(float(1u << (_5838 & 31u)));
                    ivec2 _8183 = ivec2(floor(_8180));
                    highp vec4 _8237;
                    do
                    {
                        _8237 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_8183) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8282;
                    do
                    {
                        _8282 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_8183 + ivec2(0, 1)) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8325;
                    do
                    {
                        _8325 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_8183 + ivec2(1, 0)) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8368;
                    do
                    {
                        _8368 = textureLod(SPIRV_Cross_Combined_3[_24._m0[_5633]._m4], (vec2(_8183 + ivec2(1)) + vec2(0.5)) / _24._m0[_5633]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8369;
                    highp vec4 _8370;
                    highp vec4 _8371;
                    _8369 = _8368;
                    _8370 = _8325;
                    _8371 = _8282;
                    highp vec4 _10448;
                    highp vec4 _10449;
                    highp vec4 _10450;
                    highp vec4 _10451;
                    _10448 = _8369;
                    _10449 = _8370;
                    _10450 = _8371;
                    _10451 = _8237;
                    highp vec2 _10456 = _8180 - vec2(_8183);
                    highp float _10471 = _10456.x;
                    highp float _10475 = _10456.y;
                    _10500 = mix(mix(_10451, _10449, vec4(_10471)) + ((_10450 - _10451) * _10475), mix(_10448, _10450, vec4(1.0 - _10471)) + ((_10449 - _10448) * (1.0 - _10475)), vec4(step(1.0, _10471 + _10475)));
                    break;
                } while(false);
                _10501 = _10500;
            }
            else
            {
                _10501 = _214;
            }
            highp vec4 _10509;
            if (!_5769)
            {
                _10509 = _8170;
            }
            else
            {
                _10509 = mix(_8170, _10501, vec4(fract(_5837)));
            }
            highp vec4 _10524;
            if ((_24._m0[_5633]._m9 & 1u) != 0u)
            {
                highp float _10517 = roundEven(_10509.w * ((((747626510u >> 29u) & 1u) != 0u) ? 65535.0 : 255.0));
                highp vec4 _10523 = _10509;
                _10523.w = float((int(_10517 - 8.0 * trunc(_10517 / 8.0)) & 4) != 0);
                _10524 = _10523;
            }
            else
            {
                _10524 = _10509;
            }
            _10525 = _10524;
            break;
        } while(false);
        highp vec4 _10526;
        _10526 = _10525;
        do
        {
            do
            {
                do
                {
                    break;
                } while(false);
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            do
            {
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            do
            {
                do
                {
                    break;
                } while(false);
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            do
            {
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        highp vec4 _10784;
        _10784 = vec4(0.0);
        highp vec4 _10828;
        _10828 = _10784;
        highp vec3 _10895;
        do
        {
            highp vec3 _10887;
            _10887 = _10526.xyz;
            _10895 = _10887;
            break;
        } while(false);
        highp vec3 _10962;
        do
        {
            _10962 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11030;
        do
        {
            highp vec3 _11028;
            _11028 = _5621.xyz;
            _11030 = _11028;
            break;
        } while(false);
        highp vec3 _11097;
        do
        {
            _11097 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11098 = fma(_10895 - _10962, _11030, _11097);
        highp float _11128;
        do
        {
            highp float _11121;
            _11121 = _10526.w;
            _11128 = _11121;
            break;
        } while(false);
        highp float _11156;
        do
        {
            highp float _11155;
            _11155 = _5621.w;
            _11156 = _11155;
            break;
        } while(false);
        highp float _11185;
        do
        {
            _11185 = _18._m0[_27._m0[_54._m0]._m0]._m1.x;
            break;
        } while(false);
        highp float _11213;
        do
        {
            highp float _11212;
            _11212 = _5621.w;
            _11213 = _11212;
            break;
        } while(false);
        highp vec4 _11215 = vec4(_11098.x, _11098.y, _11098.z, _10828.w);
        _11215.w = fma(_11128 - _11156, _11185, _11213);
        highp vec4 _11216;
        _11216 = _11215;
        do
        {
            do
            {
                do
                {
                    break;
                } while(false);
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            do
            {
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            do
            {
                do
                {
                    break;
                } while(false);
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            do
            {
                break;
            } while(false);
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        do
        {
            break;
        } while(false);
        highp float _11387 = fma(2.0078432559967041015625, step(_11216.w, -0.503921568393707275390625), _11216.w);
        highp vec4 _11390 = _11216;
        _11390.w = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11387), _11387);
        highp vec4 _11396;
        _11396 = _11390;
        highp vec4 _11397;
        _11397 = _11396;
        highp float _11406 = fma(2.0078432559967041015625, step(_11397.x, -0.503921568393707275390625), _11397.x);
        highp vec4 _11409 = _11397;
        _11409.x = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11406), _11406);
        highp float _11412 = fma(2.0078432559967041015625, step(_11397.y, -0.503921568393707275390625), _11397.y);
        highp vec4 _11415 = _11409;
        _11415.y = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11412), _11412);
        highp float _11418 = fma(2.0078432559967041015625, step(_11397.z, -0.503921568393707275390625), _11397.z);
        highp vec4 _11421 = _11415;
        _11421.z = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11418), _11418);
        highp vec4 _11440;
        _11440 = _11421;
        highp vec4 _11441;
        _11441 = _11440;
        highp vec3 _11508;
        do
        {
            _11508 = _11441.xyz;
            break;
        } while(false);
        highp vec3 _11575;
        do
        {
            _11575 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11643;
        do
        {
            _11643 = _270.xyz;
            break;
        } while(false);
        highp vec3 _11710;
        do
        {
            _11710 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11711 = fma(_11508 - _11575, _11643, _11710);
        highp float _11741;
        do
        {
            _11741 = _11441.w;
            break;
        } while(false);
        highp float _11769;
        do
        {
            _11769 = 0.0;
            break;
        } while(false);
        highp float _11798;
        do
        {
            _11798 = _18._m0[_27._m0[_54._m0]._m0]._m0.w;
            break;
        } while(false);
        highp float _11826;
        do
        {
            _11826 = 0.0;
            break;
        } while(false);
        highp vec4 _11828 = vec4(_11711.x, _11711.y, _11711.z, _11441.w);
        _11828.w = fma(_11741 - _11769, _11798, _11826);
        highp vec4 _11829;
        _11829 = _11828;
        highp float _11832 = fma(2.0078432559967041015625, step(_11829.x, -0.503921568393707275390625), _11829.x);
        highp float _11838 = fma(2.0078432559967041015625, step(_11829.y, -0.503921568393707275390625), _11829.y);
        highp float _11844 = fma(2.0078432559967041015625, step(_11829.z, -0.503921568393707275390625), _11829.z);
        highp float _11850 = fma(2.0078432559967041015625, step(_11829.w, -0.503921568393707275390625), _11829.w);
        highp float _11854 = clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11850), _11850), 0.0, 1.0);
        highp vec4 _11855 = vec4(clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11832), _11832), 0.0, 1.0), clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11838), _11838), 0.0, 1.0), clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11844), _11844), 0.0, 1.0), _11850);
        _11855.w = _11854;
        highp float _11885 = (((747626510u >> 29u) & 1u) != 0u) ? 65535.0 : 255.0;
        highp float _11890 = (8.0 / _11885) * (((3356565624u & 4096u) != 0u) ? _11854 : 1.0);
        if (_11890 < (1.0 / _11885))
        {
            _12556 = _247;
            _12557 = _247;
            _12558 = false;
            break;
        }
        highp vec4 _12387;
        do
        {
            do
            {
                break;
            } while(false);
            highp vec3 _12173;
            bool _12175;
            do
            {
                highp float _12054;
                do
                {
                    _12054 = _270.w;
                    break;
                } while(false);
                highp float _12062;
                do
                {
                    _12062 = 1.0 - _12054;
                    break;
                } while(false);
                highp vec3 _12070;
                do
                {
                    _12070 = _18._m0[_27._m0[_54._m0]._m0]._m4.xyz;
                    break;
                } while(false);
                highp vec3 _12079;
                do
                {
                    _12079 = _11855.xyz;
                    break;
                } while(false);
                highp vec3 _12081 = (_12070 * _12054) + (_12079 * _12062);
                highp float _12083 = _12054 + _12062;
                highp vec3 _12133;
                _12133 = (_12081 - vec3(1.031372547149658203125) * trunc(_12081 / vec3(1.031372547149658203125))) / vec3(isnan(0.0039215688593685626983642578125) ? _12083 : (isnan(_12083) ? 0.0039215688593685626983642578125 : max(_12083, 0.0039215688593685626983642578125)));
                highp vec3 _12169;
                bool _12171;
                _12169 = _12133;
                _12171 = false;
                _12173 = _12169;
                _12175 = _12171;
                break;
            } while(false);
            highp float _12379;
            highp vec3 _12380;
            do
            {
                highp vec3 _12193;
                if (!_12175)
                {
                    _12193 = _12173;
                }
                else
                {
                    _12193 = _11855.xyz;
                }
                highp vec3 _12201;
                do
                {
                    _12201 = _12193;
                    break;
                } while(false);
                highp vec3 _12202;
                _12202 = _12201;
                _12379 = ((int((((3356565624u >> 16u) & 65535u) >> 12u) & 3u)) == 1) ? 0.0 : 1.0;
                _12380 = _12202;
                break;
            } while(false);
            highp float _12381;
            highp vec3 _12382;
            _12381 = _12379;
            _12382 = _12380;
            _12387 = vec4(_12382, _12381);
            break;
        } while(false);
        do
        {
            do
            {
                break;
            } while(false);
            do
            {
                break;
            } while(false);
            do
            {
                break;
            } while(false);
            break;
        } while(false);
        highp vec4 _12507;
        _12507 = vec4(1.0);
        highp float _12522 = 7.0 / _11885;
        highp vec4 _12524 = _12387;
        _12524.w = isnan(_12522) ? _11890 : (isnan(_11890) ? _12522 : min(_11890, _12522));
        highp vec4 _12525;
        _12525 = _12524;
        highp vec4 _12528;
        _12528 = _12525;
        highp vec4 _12530;
        _12530 = _12528;
        highp vec4 _12555;
        if (_27._m0[_54._m0]._m4 > 0u)
        {
            highp float _12551 = float((_27._m0[_54._m0]._m4 >> 0u) & 255u) * 0.0039215688593685626983642578125;
            _12555 = mix(_12530, vec4(float((_27._m0[_54._m0]._m4 >> 24u) & 255u) * 0.0039215688593685626983642578125, float((_27._m0[_54._m0]._m4 >> 16u) & 255u) * 0.0039215688593685626983642578125, float((_27._m0[_54._m0]._m4 >> 8u) & 255u) * 0.0039215688593685626983642578125, _12551), vec4(_12551));
        }
        else
        {
            _12555 = _12530;
        }
        _12556 = _12507;
        _12557 = _12555;
        _12558 = true;
        break;
    } while(false);
    if (!_12558)
    {
        discard;
    }
    _7 = _12557;
    _8 = _12556;
}

