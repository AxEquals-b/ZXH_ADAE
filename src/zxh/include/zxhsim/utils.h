#pragma once
#include "zxhsim/defs.h"
#include <vector>

namespace ZXHSim
{

#define ZXHSIM_INV_SQRT2 static_cast<float_t>(0.70710678118654752440L)

// unsafe for multithread
void SRand(unsigned int seed);
double RandD();

svid_t Vec2Idx(const std::vector<bool> vec);

// Shared math helpers used by multiple modules.
val_t Phase(float_t angle);
} // namespace ZXHSim
