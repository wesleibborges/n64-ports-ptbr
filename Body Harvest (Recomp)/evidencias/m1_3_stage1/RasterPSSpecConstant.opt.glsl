#version 320 es
precision mediump float;
precision highp int;

struct _16
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

struct _19
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

struct _22
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

struct _25
{
    uint _m0;
    uint _m1;
    uint _m2;
    uint _m3;
    uint _m4;
};

layout(binding = 1, std140) uniform _13_14
{
    uint _m0;
    uint _m1;
    highp float _m2;
} _14;

layout(binding = 2, std430) readonly buffer _15_17
{
    _16 _m0[];
} _17;

layout(binding = 3, std430) readonly buffer _18_20
{
    _19 _m0[];
} _20;

layout(binding = 4, std430) readonly buffer _21_23
{
    _22 _m0[];
} _23;

layout(binding = 5, std430) readonly buffer _24_26
{
    _25 _m0[];
} _26;

layout(binding = 0, std140) uniform _50_51
{
    highp vec2 _m0;
    highp vec2 _m1;
    highp float _m2;
} _51;

struct _52
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

uniform _52 _53;

uniform highp sampler2D SPIRV_Cross_Combined[8192];
uniform highp sampler2D SPIRV_Cross_Combined_1[8192];
uniform highp sampler2D SPIRV_Cross_Combined_2[8192];
uniform highp sampler2D SPIRV_Cross_Combined_3[8192];

layout(location = 0) in highp vec2 _4;
layout(location = 1) in highp vec4 _5;
layout(location = 0, index = 0) out highp vec4 _6;
layout(location = 0, index = 1) out highp vec4 _7;

vec4 _210;
float _211;
vec4 _243;

void main()
{
    highp vec4 _12511;
    highp vec4 _12512;
    bool _12513;
    do
    {
        highp vec4 _262;
        _262 = _5;
        bool _531 = !((747626510u & 1u) != 0u);
        bool _535;
        _535 = !((3356565624u & 4u) == 4u);
        if (gl_FragCoord.z > (_535 ? 0.998046875 : 1.0))
        {
            _12511 = _243;
            _12512 = _243;
            _12513 = false;
            break;
        }
        highp vec2 _598 = dFdx(_4);
        highp vec2 _599 = dFdy(_4);
        highp vec2 _620;
        _620 = _4;
        int _697;
        int _698;
        _697 = 1;
        _698 = 0;
        uint _707 = _26._m0[_53._m0]._m2 + uint(_698);
        bool _758 = (_23._m0[_707]._m9 & 2u) != 0u;
        highp vec4 _5575;
        do
        {
            highp vec2 _770 = (mix(_620, _4, bvec2(_758)) * (((!((1584128u & 524288u) == 524288u)) ? _531 : false) ? 0.5 : 1.0)) * vec2(_20._m0[_707]._m7, _20._m0[_707]._m8);
            highp vec2 _777;
            if (!_758)
            {
                _777 = roundEven(_770 * 128.0) * vec2(0.0078125);
            }
            else
            {
                _777 = _770;
            }
            highp vec2 _783;
            if ((_23._m0[_707]._m9 & 32u) != 0u)
            {
                _783 = _777 + vec2(0.5);
            }
            else
            {
                _783 = _777;
            }
            highp vec2 _787 = fma(_783, _23._m0[_707]._m1, (vec2(_20._m0[_707]._m9, _20._m0[_707]._m10) * _23._m0[_707]._m0) * vec2(-0.25));
            bool _803;
            _803 = false;
            highp vec2 _810;
            if (_803 ? _758 : false)
            {
                _810 = roundEven(_787 * 8.0) * vec2(0.125);
            }
            else
            {
                _810 = _787;
            }
            bool _819 = (_23._m0[_707]._m9 & 16u) != 0u;
            highp float _887;
            uint _888;
            uint _889;
            if (_819)
            {
                highp vec2 _830 = _23._m0[_707]._m8.xy / _23._m0[_707]._m1;
                highp vec4 _871;
                do
                {
                    _871 = textureGrad(SPIRV_Cross_Combined[_23._m0[_707]._m4], _810 / _23._m0[_707]._m8.xy, _598 / _830, _599 / _830);
                    break;
                } while(false);
                _5575 = _871;
                break;
            }
            else
            {
                _887 = _211;
                _888 = 0u;
                _889 = 0u;
            }
            highp vec4 _3220;
            do
            {
                highp vec2 _897 = _810 / vec2(float(1u << (_889 & 31u)));
                ivec2 _900 = ivec2(floor(_897));
                highp vec4 _957;
                do
                {
                    _957 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_900) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1002;
                do
                {
                    _1002 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_900 + ivec2(0, 1)) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1045;
                do
                {
                    _1045 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_900 + ivec2(1, 0)) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1088;
                do
                {
                    _1088 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_900 + ivec2(1)) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _1089;
                highp vec4 _1090;
                highp vec4 _1091;
                _1089 = _1088;
                _1090 = _1045;
                _1091 = _1002;
                highp vec4 _3168;
                highp vec4 _3169;
                highp vec4 _3170;
                highp vec4 _3171;
                _3168 = _1089;
                _3169 = _1090;
                _3170 = _1091;
                _3171 = _957;
                highp vec2 _3176 = _897 - vec2(_900);
                highp float _3191 = _3176.x;
                highp float _3195 = _3176.y;
                _3220 = mix(mix(_3171, _3169, vec4(_3191)) + ((_3170 - _3171) * _3195), mix(_3168, _3170, vec4(1.0 - _3191)) + ((_3169 - _3168) * (1.0 - _3195)), vec4(step(1.0, _3191 + _3195)));
                break;
            } while(false);
            highp vec4 _5551;
            if ((_819 ? 2u : 1u) > 1u)
            {
                highp vec4 _5550;
                do
                {
                    highp vec2 _3230 = _810 / vec2(float(1u << (_888 & 31u)));
                    ivec2 _3233 = ivec2(floor(_3230));
                    highp vec4 _3287;
                    do
                    {
                        _3287 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_3233) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3332;
                    do
                    {
                        _3332 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_3233 + ivec2(0, 1)) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3375;
                    do
                    {
                        _3375 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_3233 + ivec2(1, 0)) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3418;
                    do
                    {
                        _3418 = textureLod(SPIRV_Cross_Combined_1[_23._m0[_707]._m4], (vec2(_3233 + ivec2(1)) + vec2(0.5)) / _23._m0[_707]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _3419;
                    highp vec4 _3420;
                    highp vec4 _3421;
                    _3419 = _3418;
                    _3420 = _3375;
                    _3421 = _3332;
                    highp vec4 _5498;
                    highp vec4 _5499;
                    highp vec4 _5500;
                    highp vec4 _5501;
                    _5498 = _3419;
                    _5499 = _3420;
                    _5500 = _3421;
                    _5501 = _3287;
                    highp vec2 _5506 = _3230 - vec2(_3233);
                    highp float _5521 = _5506.x;
                    highp float _5525 = _5506.y;
                    _5550 = mix(mix(_5501, _5499, vec4(_5521)) + ((_5500 - _5501) * _5525), mix(_5498, _5500, vec4(1.0 - _5521)) + ((_5499 - _5498) * (1.0 - _5525)), vec4(step(1.0, _5521 + _5525)));
                    break;
                } while(false);
                _5551 = _5550;
            }
            else
            {
                _5551 = _210;
            }
            highp vec4 _5559;
            if (!_819)
            {
                _5559 = _3220;
            }
            else
            {
                _5559 = mix(_3220, _5551, vec4(fract(_887)));
            }
            highp vec4 _5574;
            if ((_23._m0[_707]._m9 & 1u) != 0u)
            {
                highp float _5567 = roundEven(_5559.w * ((((747626510u >> 29u) & 1u) != 0u) ? 65535.0 : 255.0));
                highp vec4 _5573 = _5559;
                _5573.w = float((int(_5567 - 8.0 * trunc(_5567 / 8.0)) & 4) != 0);
                _5574 = _5573;
            }
            else
            {
                _5574 = _5559;
            }
            _5575 = _5574;
            break;
        } while(false);
        highp vec4 _5576;
        _5576 = _5575;
        uint _5588 = _26._m0[_53._m0]._m2 + uint(((1584128u & 3145728u) == 0u) ? _698 : _697);
        bool _5657 = (_23._m0[_5588]._m9 & 2u) != 0u;
        highp vec4 _10480;
        do
        {
            highp vec2 _5669 = (mix(_620, _4, bvec2(_5657)) * (((!((1584128u & 524288u) == 524288u)) ? _531 : false) ? 0.5 : 1.0)) * vec2(_20._m0[_5588]._m7, _20._m0[_5588]._m8);
            highp vec2 _5676;
            if (!_5657)
            {
                _5676 = roundEven(_5669 * 128.0) * vec2(0.0078125);
            }
            else
            {
                _5676 = _5669;
            }
            highp vec2 _5683;
            _5683 = _5676;
            highp vec2 _5689;
            if ((_23._m0[_5588]._m9 & 32u) != 0u)
            {
                _5689 = _5683 + vec2(0.5);
            }
            else
            {
                _5689 = _5683;
            }
            highp vec2 _5693 = fma(_5689, _23._m0[_5588]._m1, (vec2(_20._m0[_5588]._m9, _20._m0[_5588]._m10) * _23._m0[_5588]._m0) * vec2(-0.25));
            bool _5708;
            _5708 = false;
            highp vec2 _5715;
            if (_5708 ? _5657 : false)
            {
                _5715 = roundEven(_5693 * 8.0) * vec2(0.125);
            }
            else
            {
                _5715 = _5693;
            }
            bool _5724 = (_23._m0[_5588]._m9 & 16u) != 0u;
            highp float _5792;
            uint _5793;
            uint _5794;
            if (_5724)
            {
                highp vec2 _5735 = _23._m0[_5588]._m8.xy / _23._m0[_5588]._m1;
                highp vec4 _5776;
                do
                {
                    _5776 = textureGrad(SPIRV_Cross_Combined_2[_23._m0[_5588]._m4], _5715 / _23._m0[_5588]._m8.xy, _598 / _5735, _599 / _5735);
                    break;
                } while(false);
                _10480 = _5776;
                break;
            }
            else
            {
                _5792 = _211;
                _5793 = 0u;
                _5794 = 0u;
            }
            highp vec4 _8125;
            do
            {
                highp vec2 _5802 = _5715 / vec2(float(1u << (_5794 & 31u)));
                ivec2 _5805 = ivec2(floor(_5802));
                highp vec4 _5862;
                do
                {
                    _5862 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_5805) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _5907;
                do
                {
                    _5907 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_5805 + ivec2(0, 1)) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _5950;
                do
                {
                    _5950 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_5805 + ivec2(1, 0)) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _5993;
                do
                {
                    _5993 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_5805 + ivec2(1)) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                    break;
                } while(false);
                highp vec4 _5994;
                highp vec4 _5995;
                highp vec4 _5996;
                _5994 = _5993;
                _5995 = _5950;
                _5996 = _5907;
                highp vec4 _8073;
                highp vec4 _8074;
                highp vec4 _8075;
                highp vec4 _8076;
                _8073 = _5994;
                _8074 = _5995;
                _8075 = _5996;
                _8076 = _5862;
                highp vec2 _8081 = _5802 - vec2(_5805);
                highp float _8096 = _8081.x;
                highp float _8100 = _8081.y;
                _8125 = mix(mix(_8076, _8074, vec4(_8096)) + ((_8075 - _8076) * _8100), mix(_8073, _8075, vec4(1.0 - _8096)) + ((_8074 - _8073) * (1.0 - _8100)), vec4(step(1.0, _8096 + _8100)));
                break;
            } while(false);
            highp vec4 _10456;
            if ((_5724 ? 2u : 1u) > 1u)
            {
                highp vec4 _10455;
                do
                {
                    highp vec2 _8135 = _5715 / vec2(float(1u << (_5793 & 31u)));
                    ivec2 _8138 = ivec2(floor(_8135));
                    highp vec4 _8192;
                    do
                    {
                        _8192 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_8138) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8237;
                    do
                    {
                        _8237 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_8138 + ivec2(0, 1)) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8280;
                    do
                    {
                        _8280 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_8138 + ivec2(1, 0)) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8323;
                    do
                    {
                        _8323 = textureLod(SPIRV_Cross_Combined_3[_23._m0[_5588]._m4], (vec2(_8138 + ivec2(1)) + vec2(0.5)) / _23._m0[_5588]._m8.xy, 0.0);
                        break;
                    } while(false);
                    highp vec4 _8324;
                    highp vec4 _8325;
                    highp vec4 _8326;
                    _8324 = _8323;
                    _8325 = _8280;
                    _8326 = _8237;
                    highp vec4 _10403;
                    highp vec4 _10404;
                    highp vec4 _10405;
                    highp vec4 _10406;
                    _10403 = _8324;
                    _10404 = _8325;
                    _10405 = _8326;
                    _10406 = _8192;
                    highp vec2 _10411 = _8135 - vec2(_8138);
                    highp float _10426 = _10411.x;
                    highp float _10430 = _10411.y;
                    _10455 = mix(mix(_10406, _10404, vec4(_10426)) + ((_10405 - _10406) * _10430), mix(_10403, _10405, vec4(1.0 - _10426)) + ((_10404 - _10403) * (1.0 - _10430)), vec4(step(1.0, _10426 + _10430)));
                    break;
                } while(false);
                _10456 = _10455;
            }
            else
            {
                _10456 = _210;
            }
            highp vec4 _10464;
            if (!_5724)
            {
                _10464 = _8125;
            }
            else
            {
                _10464 = mix(_8125, _10456, vec4(fract(_5792)));
            }
            highp vec4 _10479;
            if ((_23._m0[_5588]._m9 & 1u) != 0u)
            {
                highp float _10472 = roundEven(_10464.w * ((((747626510u >> 29u) & 1u) != 0u) ? 65535.0 : 255.0));
                highp vec4 _10478 = _10464;
                _10478.w = float((int(_10472 - 8.0 * trunc(_10472 / 8.0)) & 4) != 0);
                _10479 = _10478;
            }
            else
            {
                _10479 = _10464;
            }
            _10480 = _10479;
            break;
        } while(false);
        highp vec4 _10481;
        _10481 = _10480;
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
        highp vec4 _10739;
        _10739 = vec4(0.0);
        highp vec4 _10783;
        _10783 = _10739;
        highp vec3 _10850;
        do
        {
            highp vec3 _10842;
            _10842 = _10481.xyz;
            _10850 = _10842;
            break;
        } while(false);
        highp vec3 _10917;
        do
        {
            _10917 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _10985;
        do
        {
            highp vec3 _10983;
            _10983 = _5576.xyz;
            _10985 = _10983;
            break;
        } while(false);
        highp vec3 _11052;
        do
        {
            _11052 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11053 = fma(_10850 - _10917, _10985, _11052);
        highp float _11083;
        do
        {
            highp float _11076;
            _11076 = _10481.w;
            _11083 = _11076;
            break;
        } while(false);
        highp float _11111;
        do
        {
            highp float _11110;
            _11110 = _5576.w;
            _11111 = _11110;
            break;
        } while(false);
        highp float _11140;
        do
        {
            _11140 = _17._m0[_26._m0[_53._m0]._m0]._m1.x;
            break;
        } while(false);
        highp float _11168;
        do
        {
            highp float _11167;
            _11167 = _5576.w;
            _11168 = _11167;
            break;
        } while(false);
        highp vec4 _11170 = vec4(_11053.x, _11053.y, _11053.z, _10783.w);
        _11170.w = fma(_11083 - _11111, _11140, _11168);
        highp vec4 _11171;
        _11171 = _11170;
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
        highp float _11342 = fma(2.0078432559967041015625, step(_11171.w, -0.503921568393707275390625), _11171.w);
        highp vec4 _11345 = _11171;
        _11345.w = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11342), _11342);
        highp vec4 _11351;
        _11351 = _11345;
        highp vec4 _11352;
        _11352 = _11351;
        highp float _11361 = fma(2.0078432559967041015625, step(_11352.x, -0.503921568393707275390625), _11352.x);
        highp vec4 _11364 = _11352;
        _11364.x = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11361), _11361);
        highp float _11367 = fma(2.0078432559967041015625, step(_11352.y, -0.503921568393707275390625), _11352.y);
        highp vec4 _11370 = _11364;
        _11370.y = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11367), _11367);
        highp float _11373 = fma(2.0078432559967041015625, step(_11352.z, -0.503921568393707275390625), _11352.z);
        highp vec4 _11376 = _11370;
        _11376.z = fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11373), _11373);
        highp vec4 _11395;
        _11395 = _11376;
        highp vec4 _11396;
        _11396 = _11395;
        highp vec3 _11463;
        do
        {
            _11463 = _11396.xyz;
            break;
        } while(false);
        highp vec3 _11530;
        do
        {
            _11530 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11598;
        do
        {
            _11598 = _262.xyz;
            break;
        } while(false);
        highp vec3 _11665;
        do
        {
            _11665 = vec3(0.0);
            break;
        } while(false);
        highp vec3 _11666 = fma(_11463 - _11530, _11598, _11665);
        highp float _11696;
        do
        {
            _11696 = _11396.w;
            break;
        } while(false);
        highp float _11724;
        do
        {
            _11724 = 0.0;
            break;
        } while(false);
        highp float _11753;
        do
        {
            _11753 = _17._m0[_26._m0[_53._m0]._m0]._m0.w;
            break;
        } while(false);
        highp float _11781;
        do
        {
            _11781 = 0.0;
            break;
        } while(false);
        highp vec4 _11783 = vec4(_11666.x, _11666.y, _11666.z, _11396.w);
        _11783.w = fma(_11696 - _11724, _11753, _11781);
        highp vec4 _11784;
        _11784 = _11783;
        highp float _11787 = fma(2.0078432559967041015625, step(_11784.x, -0.503921568393707275390625), _11784.x);
        highp float _11793 = fma(2.0078432559967041015625, step(_11784.y, -0.503921568393707275390625), _11784.y);
        highp float _11799 = fma(2.0078432559967041015625, step(_11784.z, -0.503921568393707275390625), _11784.z);
        highp float _11805 = fma(2.0078432559967041015625, step(_11784.w, -0.503921568393707275390625), _11784.w);
        highp float _11809 = clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11805), _11805), 0.0, 1.0);
        highp vec4 _11810 = vec4(clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11787), _11787), 0.0, 1.0), clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11793), _11793), 0.0, 1.0), clamp(fma(-2.0078432559967041015625, step(1.50392162799835205078125, _11799), _11799), 0.0, 1.0), _11805);
        _11810.w = _11809;
        highp float _11840 = (((747626510u >> 29u) & 1u) != 0u) ? 65535.0 : 255.0;
        highp float _11845 = (8.0 / _11840) * (((3356565624u & 4096u) != 0u) ? _11809 : 1.0);
        if (_11845 < (1.0 / _11840))
        {
            _12511 = _243;
            _12512 = _243;
            _12513 = false;
            break;
        }
        highp vec4 _12342;
        do
        {
            do
            {
                break;
            } while(false);
            highp vec3 _12128;
            bool _12130;
            do
            {
                highp float _12009;
                do
                {
                    _12009 = _262.w;
                    break;
                } while(false);
                highp float _12017;
                do
                {
                    _12017 = 1.0 - _12009;
                    break;
                } while(false);
                highp vec3 _12025;
                do
                {
                    _12025 = _17._m0[_26._m0[_53._m0]._m0]._m4.xyz;
                    break;
                } while(false);
                highp vec3 _12034;
                do
                {
                    _12034 = _11810.xyz;
                    break;
                } while(false);
                highp vec3 _12036 = (_12025 * _12009) + (_12034 * _12017);
                highp float _12038 = _12009 + _12017;
                highp vec3 _12088;
                _12088 = (_12036 - vec3(1.031372547149658203125) * trunc(_12036 / vec3(1.031372547149658203125))) / vec3(isnan(0.0039215688593685626983642578125) ? _12038 : (isnan(_12038) ? 0.0039215688593685626983642578125 : max(_12038, 0.0039215688593685626983642578125)));
                highp vec3 _12124;
                bool _12126;
                _12124 = _12088;
                _12126 = false;
                _12128 = _12124;
                _12130 = _12126;
                break;
            } while(false);
            highp float _12334;
            highp vec3 _12335;
            do
            {
                highp vec3 _12148;
                if (!_12130)
                {
                    _12148 = _12128;
                }
                else
                {
                    _12148 = _11810.xyz;
                }
                highp vec3 _12156;
                do
                {
                    _12156 = _12148;
                    break;
                } while(false);
                highp vec3 _12157;
                _12157 = _12156;
                _12334 = ((int((((3356565624u >> 16u) & 65535u) >> 12u) & 3u)) == 1) ? 0.0 : 1.0;
                _12335 = _12157;
                break;
            } while(false);
            highp float _12336;
            highp vec3 _12337;
            _12336 = _12334;
            _12337 = _12335;
            _12342 = vec4(_12337, _12336);
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
        highp vec4 _12462;
        _12462 = vec4(1.0);
        highp float _12477 = 7.0 / _11840;
        highp vec4 _12479 = _12342;
        _12479.w = isnan(_12477) ? _11845 : (isnan(_11845) ? _12477 : min(_11845, _12477));
        highp vec4 _12480;
        _12480 = _12479;
        highp vec4 _12483;
        _12483 = _12480;
        highp vec4 _12485;
        _12485 = _12483;
        highp vec4 _12510;
        if (_26._m0[_53._m0]._m4 > 0u)
        {
            highp float _12506 = float((_26._m0[_53._m0]._m4 >> 0u) & 255u) * 0.0039215688593685626983642578125;
            _12510 = mix(_12485, vec4(float((_26._m0[_53._m0]._m4 >> 24u) & 255u) * 0.0039215688593685626983642578125, float((_26._m0[_53._m0]._m4 >> 16u) & 255u) * 0.0039215688593685626983642578125, float((_26._m0[_53._m0]._m4 >> 8u) & 255u) * 0.0039215688593685626983642578125, _12506), vec4(_12506));
        }
        else
        {
            _12510 = _12485;
        }
        _12511 = _12462;
        _12512 = _12510;
        _12513 = true;
        break;
    } while(false);
    if (!_12513)
    {
        discard;
    }
    _6 = _12512;
    _7 = _12511;
}

