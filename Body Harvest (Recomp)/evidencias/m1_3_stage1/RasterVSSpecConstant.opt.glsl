#version 320 es

struct _13
{
    vec4 _m0;
    vec2 _m1;
    vec2 _m2;
    vec4 _m3;
    vec4 _m4;
    vec4 _m5;
    vec3 _m6;
    float _m7;
    vec3 _m8;
    int _m9[6];
    int _m10[3];
};

struct _16
{
    uint _m0;
    uint _m1;
    uint _m2;
    uint _m3;
    uint _m4;
};

layout(binding = 2, std430) readonly buffer _12_14
{
    _13 _m0[];
} _14;

layout(binding = 5, std430) readonly buffer _15_17
{
    _16 _m0[];
} _17;

layout(binding = 0, std140) uniform _18_19
{
    vec2 _m0;
    vec2 _m1;
    float _m2;
} _19;

struct _20
{
    uint _m0;
    uint _m1;
    uint _m2;
    uint _m3;
    uvec3 _m4;
    uint _m5;
    vec2 _m6;
    vec2 _m7;
};

uniform _20 _21;

layout(location = 0) in vec4 _3;
layout(location = 1) in vec2 _4;
layout(location = 2) in vec4 _5;
layout(location = 0) out vec2 _7;
layout(location = 1) out vec4 _8;

void main()
{
    vec2 _88 = fma(-_19._m0, vec2(0.5), _3.xy).xy / vec2(_19._m0.x * 0.5, _19._m0.y * (-0.5));
    vec3 _92 = vec4(_88.x, _88.y, _3.z, _3.w).xyz * _3.w;
    vec4 _94;
    _94 = vec4(_92.x, _92.y, _92.z, _3.w);
    vec2 _102 = fma(_94.xy, _21._m6, _21._m7 * _94.w);
    vec4 _120;
    _120 = vec4(_102.x, _102.y, _94.z, _94.w);
    vec4 _123 = _120;
    _123.y = -_120.y;
    gl_Position = _123;
    _7 = _4;
    _8 = _5;
}

