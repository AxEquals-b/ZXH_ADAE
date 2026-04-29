#include "zxhsim/defs.h"
#include "zxhsim/runtime.h"

#include <algorithm>
#include <limits>

namespace ZXHSim
{

namespace
{

bool xor_bit(bool a, bool b)
{
    return a != b;
}

} // namespace

bitmat_t::bitmat_t(size_t N) : N_(N), m_(0), cols_()
{
}

size_t bitmat_t::N() const
{
    return N_;
}

size_t bitmat_t::m() const
{
    return m_;
}

void bitmat_t::row_xor(size_t dst, size_t src)
{
    if (dst >= N_ || src >= N_)
        abort("row_xor index out of range");

    for (size_t c = 0; c < m_; c++)
    {
        const bool v = xor_bit(cols_[c].get_bit(dst), cols_[c].get_bit(src));
        cols_[c].set_bit(dst, v);
    }
}

bool bitmat_t::solve(const vaddr_t &rhs, raddr_t &x) const
{
    if (m_ == 0)
    {
        for (size_t r = 0; r < N_; r++)
        {
            if (rhs.get_bit(r))
                return false;
        }
        x = 0;
        return true;
    }

    std::vector<bitvec_t> mat(N_, bitvec_t(m_, false));
    for (size_t c = 0; c < m_; c++)
    {
        for (size_t r = 0; r < N_; r++)
        {
            if (cols_[c].get_bit(r))
                mat[r].set_bit(c, true);
        }
    }
    bitvec_t bvec(N_, false);
    for (size_t r = 0; r < N_; r++)
        bvec.set_bit(r, rhs.get_bit(r));

    std::vector<ssvid_t> pivot_for_col(m_, -1);
    size_t row = 0;

    for (size_t col = 0; col < m_ && row < N_; col++)
    {
        size_t piv = row;
        while (piv < N_ && !mat[piv].get_bit(col))
            piv++;
        if (piv == N_)
            continue;

        if (piv != row)
        {
            std::swap(mat[piv], mat[row]);
            const bool tmp = bvec.get_bit(piv);
            bvec.set_bit(piv, bvec.get_bit(row));
            bvec.set_bit(row, tmp);
        }

        for (size_t r = 0; r < N_; r++)
        {
            if (r != row && mat[r].get_bit(col))
            {
                mat[r] = mat[r] ^ mat[row];
                bvec.set_bit(r, xor_bit(bvec.get_bit(r), bvec.get_bit(row)));
            }
        }

        pivot_for_col[col] = static_cast<ssvid_t>(row);
        row++;
    }

    for (size_t r = 0; r < N_; r++)
    {
        if (mat[r].all_zero() && bvec.get_bit(r))
            return false;
    }

    x = 0;
    for (size_t col = 0; col < m_; col++)
    {
        if (pivot_for_col[col] >= 0)
        {
            const size_t prow = static_cast<size_t>(pivot_for_col[col]);
            if (bvec.get_bit(prow))
                x |= (raddr_t(1) << col);
        }
    }

    return true;
}

bitvec_t bitmat_t::mul(raddr_t real) const
{
    constexpr size_t kRaddrBits = std::numeric_limits<raddr_t>::digits;
    if (m_ > kRaddrBits)
        abort("mul cannot decode real address wider than raddr_t");

    bitvec_t out(N_, false);
    for (size_t c = 0; c < m_; c++)
    {
        if (((real >> c) & 1ULL) != 0)
            out = out ^ cols_[c];
    }
    return out;
}

void bitmat_t::append_col(const bitvec_t &col)
{
    if (col.length() != N_)
        abort("append_col requires N-length column");
    cols_.push_back(col.copy());
    m_++;
}

raddr_t bitmat_t::get_row(size_t r) const
{
    if (r >= N_)
        abort("get_row index out of range");
    if (m_ > 64)
        abort("get_row cannot encode more than 64 columns");

    raddr_t row = 0;
    for (size_t c = 0; c < m_; c++)
    {
        if (cols_[c].get_bit(r))
            row |= (raddr_t(1) << c);
    }
    return row;
}

} // namespace ZXHSim
