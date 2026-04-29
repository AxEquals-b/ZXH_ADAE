#pragma once

#include <complex>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace ZXHSim
{

using float_t = double;
using val_t = std::complex<float_t>;
using std::size_t;

class bitvec_t
{
  public:
    bitvec_t();
    explicit bitvec_t(size_t nbits, bool value = false);

    static bitvec_t from_uint64(size_t nbits, uint64_t value);
    static bitvec_t from_words(size_t nbits, const uint64_t *words, size_t word_count);

    size_t length() const;
    bool get_bit(size_t i) const;
    bool test_bit(size_t i) const;
    void set_bit(size_t i, bool value);
    void push_back(bool value);

    bitvec_t copy() const;
    bool equal(const bitvec_t &other) const;
    bool all_zero() const;

    bitvec_t operator^(const bitvec_t &rhs) const;
    bool dot(const bitvec_t &rhs) const;

    static bitvec_t e_i(size_t nbits, size_t i);

    bitvec_t lower_bits(size_t n) const;
    bitvec_t higher_bits(size_t n) const;

    uint64_t to_uint64() const;

  protected:
    size_t nbits_;
    std::vector<uint64_t> words_;

  private:
    void mask_unused_bits();
};

using res_t = bitvec_t;

} // namespace ZXHSim
