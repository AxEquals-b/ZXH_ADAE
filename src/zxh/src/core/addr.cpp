#include "zxhsim/defs.h"
#include "zxhsim/runtime.h"

#include <limits>

namespace ZXHSim
{

raddr_t raddr_e_i(size_t i)
{
    if (i >= std::numeric_limits<raddr_t>::digits)
        abort("raddr_e_i shift out of range");
    return raddr_t(1) << i;
}

raddr_t raddr_lower_bits(raddr_t x, size_t n)
{
    if (n == 0)
        return 0;
    if (n >= std::numeric_limits<raddr_t>::digits)
        return x;
    return x & ((raddr_t(1) << n) - 1);
}

raddr_t raddr_higher_bits(raddr_t x, size_t n)
{
    if (n >= std::numeric_limits<raddr_t>::digits)
        return 0;
    return x >> n;
}

} // namespace ZXHSim
