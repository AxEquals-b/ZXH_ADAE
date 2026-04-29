#include "zxhsim/types.h"
#include "zxhsim/runtime.h"

#include <algorithm>

namespace ZXHSim
{

namespace
{
constexpr size_t kWordBits = 64;

size_t word_count(size_t nbits)
{
    return (nbits + kWordBits - 1) / kWordBits;
}

} // namespace

bitvec_t::bitvec_t() : nbits_(0), words_()
{
}

bitvec_t::bitvec_t(size_t nbits, bool value) : nbits_(nbits), words_(word_count(nbits), value ? ~uint64_t(0) : 0)
{
    mask_unused_bits();
}

bitvec_t bitvec_t::from_uint64(size_t nbits, uint64_t value)
{
    bitvec_t out(nbits, false);
    if (!out.words_.empty())
        out.words_[0] = value;
    out.mask_unused_bits();
    return out;
}

bitvec_t bitvec_t::from_words(size_t nbits, const uint64_t *words, size_t word_count)
{
    bitvec_t out(nbits, false);
    if (words == nullptr && word_count != 0)
        abort("bitvec_t::from_words words is null");

    const size_t copy_words = std::min(out.words_.size(), word_count);
    for (size_t i = 0; i < copy_words; i++)
        out.words_[i] = words[i];
    out.mask_unused_bits();
    return out;
}

size_t bitvec_t::length() const
{
    return nbits_;
}

bool bitvec_t::get_bit(size_t i) const
{
    if (i >= nbits_)
        return false;
    const size_t wi = i / kWordBits;
    const size_t bi = i % kWordBits;
    return ((words_[wi] >> bi) & 1ULL) != 0;
}

bool bitvec_t::test_bit(size_t i) const
{
    return get_bit(i);
}

void bitvec_t::set_bit(size_t i, bool value)
{
    if (i >= nbits_)
        abort("bit index out of range");

    const size_t wi = i / kWordBits;
    const size_t bi = i % kWordBits;
    const uint64_t mask = 1ULL << bi;
    if (value)
        words_[wi] |= mask;
    else
        words_[wi] &= ~mask;
}

void bitvec_t::push_back(bool value)
{
    const size_t new_nbits = nbits_ + 1;
    if (word_count(new_nbits) > words_.size())
        words_.push_back(0);

    nbits_ = new_nbits;
    set_bit(nbits_ - 1, value);
}

bitvec_t bitvec_t::copy() const
{
    return *this;
}

bool bitvec_t::equal(const bitvec_t &other) const
{
    if (nbits_ != other.nbits_)
        return false;
    return words_ == other.words_;
}

bool bitvec_t::all_zero() const
{
    for (uint64_t w : words_)
    {
        if (w != 0)
            return false;
    }
    return true;
}

bitvec_t bitvec_t::operator^(const bitvec_t &rhs) const
{
    const size_t out_nbits = std::max(nbits_, rhs.nbits_);
    bitvec_t out(out_nbits, false);
    const size_t out_words = out.words_.size();
    for (size_t i = 0; i < out_words; i++)
    {
        const uint64_t lw = (i < words_.size()) ? words_[i] : 0;
        const uint64_t rw = (i < rhs.words_.size()) ? rhs.words_[i] : 0;
        out.words_[i] = lw ^ rw;
    }
    out.mask_unused_bits();
    return out;
}

bool bitvec_t::dot(const bitvec_t &rhs) const
{
    const size_t nw = std::min(words_.size(), rhs.words_.size());
    uint32_t parity = 0;
    for (size_t i = 0; i < nw; i++)
    {
        parity ^= static_cast<uint32_t>(__builtin_popcountll(words_[i] & rhs.words_[i]) & 1ULL);
    }
    return parity != 0;
}

bitvec_t bitvec_t::e_i(size_t nbits, size_t i)
{
    if (i >= nbits)
        abort("bitvec_t::e_i index out of range");

    bitvec_t bits(nbits, false);
    bits.set_bit(i, true);
    return bits;
}

bitvec_t bitvec_t::lower_bits(size_t n) const
{
    bitvec_t out(n, false);
    const size_t copy_n = std::min(n, nbits_);
    for (size_t i = 0; i < copy_n; i++)
        out.set_bit(i, get_bit(i));
    return out;
}

bitvec_t bitvec_t::higher_bits(size_t n) const
{
    bitvec_t out(n, false);
    if (n == 0)
        return out;

    const size_t start = (nbits_ > n) ? (nbits_ - n) : 0;
    for (size_t i = 0; i < n; i++)
    {
        const size_t src = start + i;
        if (src < nbits_)
            out.set_bit(i, get_bit(src));
    }
    return out;
}

uint64_t bitvec_t::to_uint64() const
{
    if (words_.empty())
        return 0;
    return words_[0];
}

void bitvec_t::mask_unused_bits()
{
    if (words_.empty())
        return;

    const size_t rem = nbits_ % kWordBits;
    if (rem == 0)
        return;

    const uint64_t mask = (uint64_t(1) << rem) - 1;
    words_.back() &= mask;
}

} // namespace ZXHSim
