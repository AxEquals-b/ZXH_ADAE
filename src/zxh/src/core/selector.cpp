#include "zxhsim/defs.h"

namespace ZXHSim
{

namespace
{

bool xor_bit(bool a, bool b)
{
    return a != b;
}

} // namespace

selector_t::selector_t() : packed_(0)
{
}

selector_t::selector_t(raddr_t alpha, bool beta) : packed_(0)
{
    constexpr raddr_t kAlphaMask = (raddr_t(1) << 63) - 1;
    packed_ = (alpha & kAlphaMask) | (beta ? (raddr_t(1) << 63) : 0);
}

bool selector_t::eval(raddr_t real) const
{
    constexpr raddr_t kAlphaMask = (raddr_t(1) << 63) - 1;
    const raddr_t alpha = packed_ & kAlphaMask;
    const bool beta = ((packed_ >> 63) & 1ULL) != 0;
    const bool parity = (__builtin_popcountll(real & alpha) & 1ULL) != 0;
    return xor_bit(parity, beta);
}

bool selector_t::eval_u64(raddr_t real) const
{
    return eval(real);
}

raddr_t selector_t::alpha() const
{
    constexpr raddr_t kAlphaMask = (raddr_t(1) << 63) - 1;
    return packed_ & kAlphaMask;
}

bool selector_t::beta() const
{
    return ((packed_ >> 63) & 1ULL) != 0;
}

} // namespace ZXHSim
