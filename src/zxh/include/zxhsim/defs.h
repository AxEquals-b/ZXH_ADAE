#pragma once

#include "zxhsim/types.h"

#include <cstdint>
#include <vector>

namespace ZXHSim
{

using svid_t = uint64_t;
using ssvid_t = int64_t;
using raddr_t = uint64_t;
using qid_t = uint32_t;
using qsize_t = qid_t;

raddr_t raddr_e_i(size_t i);
raddr_t raddr_lower_bits(raddr_t x, size_t n);
raddr_t raddr_higher_bits(raddr_t x, size_t n);

using vaddr_t = bitvec_t;

class selector_t
{
  public:
    selector_t();
    selector_t(raddr_t alpha, bool beta);

    bool eval(raddr_t real) const;
    bool eval_u64(raddr_t real) const;

    raddr_t alpha() const;
    bool beta() const;

  private:
    uint64_t packed_;
};

class bitmat_t
{
  public:
    explicit bitmat_t(size_t N = 0);

    size_t N() const;
    size_t m() const;

    void row_xor(size_t dst, size_t src);
    bool solve(const vaddr_t &rhs, raddr_t &x) const;
    bitvec_t mul(raddr_t real) const;
    void append_col(const bitvec_t &col);

    raddr_t get_row(size_t r) const;

  private:
    size_t N_;
    size_t m_;
    std::vector<bitvec_t> cols_;
};

enum class gate_type_t
{
    None,
    Barrier,
    Z,
    Rz,
    P,
    CRz,
    CP,
    X,
    CX,
    H,
    U3,
};

struct gate_t
{
    gate_type_t type = gate_type_t::None;
    size_t cq = 0;
    size_t q = 0;
    float_t theta = 0.0;
    float_t lambda = 0.0;
    float_t phi = 0.0;
};

struct u3_batch_desc_t
{
    uint64_t packed_sel = 0;
    raddr_t delta_so = 0;

    float_t u00_re = 0.0;
    float_t u00_im = 0.0;
    float_t u01_re = 0.0;
    float_t u01_im = 0.0;
    float_t u10_re = 0.0;
    float_t u10_im = 0.0;
    float_t u11_re = 0.0;
    float_t u11_im = 0.0;
};

} // namespace ZXHSim
