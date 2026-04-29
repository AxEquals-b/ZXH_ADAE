#include "zxhsim/utils.h"

#include <cmath>
#include <complex>
#include <limits>
#include <random>
#include <stdexcept>

namespace ZXHSim
{

typedef std::mt19937 mt;

mt &gen()
{
    static mt g{std::random_device{}()};
    return g;
}

void SRand(unsigned int seed)
{
    gen().seed(seed);
}

double RandD()
{
    static std::uniform_real_distribution<double> dis(0.0, 1.0);
    return dis(gen());
}

svid_t Vec2Idx(const std::vector<bool> vec)
{
    svid_t idx = 0;
    for (qid_t q = 0; q < vec.size(); q++)
    {
        if (vec[q])
            idx |= 1 << q;
    }
    return idx;
}

val_t Phase(float_t angle)
{
    return std::exp(val_t(0.0, angle));
}

} // namespace ZXHSim
