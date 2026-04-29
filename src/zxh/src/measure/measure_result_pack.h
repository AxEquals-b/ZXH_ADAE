#pragma once

#include "zxhsim/defs.h"

#include <algorithm>
#include <cstdint>
#include <vector>

namespace ZXHSim
{
namespace detail
{

inline size_t result_word_count(size_t nbits)
{
    return (nbits + 63) / 64;
}

inline bool packed_bit(const uint64_t *words, size_t bit)
{
    return ((words[bit >> 6] >> (bit & 63)) & 1ULL) != 0;
}

inline void pack_virtual_results_host(const raddr_t *real_results, size_t count,
                                      const bitmat_t &A, const bitvec_t &b,
                                      size_t nbits, std::vector<uint64_t> &packed)
{
    const size_t word_count = result_word_count(nbits);
    packed.resize(count * word_count);
    std::fill(packed.begin(), packed.end(), 0ULL);

    for (size_t i = 0; i < count; i++)
    {
        const raddr_t real = real_results[i];
        uint64_t *dst = packed.data() + i * word_count;
        for (size_t q = 0; q < nbits; q++)
        {
            const bool bit = ((__builtin_popcountll(real & A.get_row(q)) & 1U) != 0U) ^
                             b.get_bit(q);
            if (bit)
                dst[q >> 6] |= (1ULL << (q & 63));
        }
    }
}

inline void unpack_virtual_results_host(const uint64_t *packed, size_t count,
                                        size_t nbits, res_t *results)
{
    const size_t word_count = result_word_count(nbits);
    for (size_t i = 0; i < count; i++)
        results[i] = bitvec_t::from_words(nbits, packed + i * word_count, word_count);
}

} // namespace detail
} // namespace ZXHSim
