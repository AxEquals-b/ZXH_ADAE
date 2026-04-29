#include "zxhsim/kernels.h"
#include "zxhsim/runtime.h"
#include "zxhsim/utils.h"

#include <algorithm>

namespace ZXHSim
{

namespace
{
constexpr raddr_t kDiagLaneMask = 0xffULL;

enum class selector_class_t
{
    low,
    high,
    cross,
};

struct diag1_desc_t
{
    selector_t sel;
    float_t theta;
};

struct diag2_desc_t
{
    selector_t sel0;
    selector_t sel1;
    float_t theta;
};

std::vector<diag1_desc_t> g_diag_p_l;
std::vector<diag1_desc_t> g_diag_p_h;
std::vector<diag1_desc_t> g_diag_p_x;
std::vector<diag2_desc_t> g_diag_cp_ll;
std::vector<diag2_desc_t> g_diag_cp_hh;
std::vector<diag2_desc_t> g_diag_cp_hl;

selector_class_t classify_selector(selector_t sel)
{
    const raddr_t alpha = sel.alpha();
    const raddr_t alpha_low = alpha & kDiagLaneMask;
    const raddr_t alpha_high = alpha >> 8;
    if (alpha_high == 0)
        return selector_class_t::low;
    if (alpha_low == 0)
        return selector_class_t::high;
    return selector_class_t::cross;
}

bool any_diag_pending()
{
    return !g_diag_p_l.empty() || !g_diag_p_h.empty() || !g_diag_p_x.empty() || !g_diag_cp_ll.empty() ||
           !g_diag_cp_hh.empty() || !g_diag_cp_hl.empty();
}

bool selector_eval_packed(uint64_t packed, uint64_t x)
{
    const uint64_t alpha = packed & ((uint64_t(1) << 63) - 1);
    const bool beta = ((packed >> 63) & 1ULL) != 0;
    const bool parity = (__builtin_popcountll(x & alpha) & 1ULL) != 0;
    return parity != beta;
}

val_t desc_entry(float_t re, float_t im)
{
    return val_t(re, im);
}

void apply_diag_window(val_t *ptr, size_t n)
{
    for (size_t off = 0; off < n; off++)
    {
        const raddr_t xr = static_cast<raddr_t>(off);
        const raddr_t lane = xr & kDiagLaneMask;
        const raddr_t slice = xr & ~kDiagLaneMask;
        float_t theta_sum = 0.0;
        for (const diag1_desc_t &g : g_diag_p_l)
        {
            if (g.sel.eval_u64(lane))
                theta_sum += g.theta;
        }
        for (const diag1_desc_t &g : g_diag_p_h)
        {
            if (g.sel.eval_u64(slice))
                theta_sum += g.theta;
        }
        for (const diag1_desc_t &g : g_diag_p_x)
        {
            if (g.sel.eval_u64(xr))
                theta_sum += g.theta;
        }
        for (const diag2_desc_t &g : g_diag_cp_ll)
        {
            if (g.sel0.eval_u64(lane) && g.sel1.eval_u64(lane))
                theta_sum += g.theta;
        }
        for (const diag2_desc_t &g : g_diag_cp_hh)
        {
            if (g.sel0.eval_u64(slice) && g.sel1.eval_u64(slice))
                theta_sum += g.theta;
        }
        for (const diag2_desc_t &g : g_diag_cp_hl)
        {
            if (g.sel0.eval_u64(lane) && g.sel1.eval_u64(slice))
                theta_sum += g.theta;
        }
        if (theta_sum != 0.0)
            ptr[off] *= Phase(theta_sum);
    }
}

} // namespace

void kernel_sync()
{
}

void u3_block_kernel(val_t *ptr1, size_t local_bits, raddr_t delta_so, selector_t S_block, val_t u00, val_t u01,
                     val_t u10, val_t u11)
{
    const size_t n = size_t(1) << local_bits;
    const size_t delta = static_cast<size_t>(delta_so);

    for (size_t i = 0; i < n; i++)
    {
        if (S_block.eval(i))
            continue;

        const size_t j = i ^ delta;
        if (j >= n)
            continue;

        const val_t even = ptr1[i];
        const val_t odd = ptr1[j];
        ptr1[i] = u00 * even + u01 * odd;
        ptr1[j] = u10 * even + u11 * odd;
    }
}

void x_block_kernel(val_t *ptr, size_t local_bits, raddr_t delta_so, selector_t S_q_block)
{
    const size_t n = size_t(1) << local_bits;
    const size_t delta = static_cast<size_t>(delta_so);
    for (size_t off = 0; off < n; off++)
    {
        if (S_q_block.eval(off))
            continue;
        const size_t peer = off ^ delta;
        if (peer >= n)
            continue;
        std::swap(ptr[off], ptr[peer]);
    }
}

void cx_block_kernel(val_t *ptr, size_t local_bits, raddr_t delta_so, selector_t S_cq_block, selector_t S_q_block)
{
    const size_t n = size_t(1) << local_bits;
    const size_t delta = static_cast<size_t>(delta_so);
    for (size_t off = 0; off < n; off++)
    {
        if (S_q_block.eval(off) || !S_cq_block.eval(off))
            continue;
        const size_t peer = off ^ delta;
        if (peer >= n)
            continue;
        std::swap(ptr[off], ptr[peer]);
    }
}

void u3_block_batch_kernel(val_t *ptr1, size_t local_bits, const std::vector<u3_batch_desc_t> &descs)
{
    if (descs.empty())
        return;

    const size_t n = size_t(1) << local_bits;
    for (const u3_batch_desc_t &desc : descs)
    {
        const size_t delta = static_cast<size_t>(desc.delta_so);
        const val_t u00 = desc_entry(desc.u00_re, desc.u00_im);
        const val_t u01 = desc_entry(desc.u01_re, desc.u01_im);
        const val_t u10 = desc_entry(desc.u10_re, desc.u10_im);
        const val_t u11 = desc_entry(desc.u11_re, desc.u11_im);

        for (size_t i = 0; i < n; i++)
        {
            if (selector_eval_packed(desc.packed_sel, static_cast<uint64_t>(i)))
                continue;

            const size_t j = i ^ delta;
            if (j >= n)
                continue;

            const val_t even = ptr1[i];
            const val_t odd = ptr1[j];
            ptr1[i] = u00 * even + u01 * odd;
            ptr1[j] = u10 * even + u11 * odd;
        }
    }
}

void u3_intra_kernel(val_t *ptr1, val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_k, val_t u00, val_t u01,
                     val_t u10, val_t u11)
{
    const size_t n = size_t(1) << I;
    const size_t delta = static_cast<size_t>(delta_o);

    for (size_t i = 0; i < n; i++)
    {
        const size_t j = i ^ delta;
        if (j >= n)
            continue;

        const bool first_is_even = !S_k.eval(i);
        const val_t even = first_is_even ? ptr1[i] : ptr2[j];
        const val_t odd = first_is_even ? ptr2[j] : ptr1[i];
        const val_t even_new = u00 * even + u01 * odd;
        const val_t odd_new = u10 * even + u11 * odd;

        if (first_is_even)
        {
            ptr1[i] = even_new;
            ptr2[j] = odd_new;
        }
        else
        {
            ptr2[j] = even_new;
            ptr1[i] = odd_new;
        }
    }
}

void u3_inter_kernel(val_t *ptr1, const val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_k, val_t u00, val_t u01,
                     val_t u10, val_t u11)
{
    const size_t n = size_t(1) << I;
    const size_t delta = static_cast<size_t>(delta_o);

    for (size_t i = 0; i < n; i++)
    {
        const size_t j = i ^ delta;
        if (j >= n)
            continue;

        const val_t local = ptr1[i];
        const val_t remote = ptr2[j];
        if (!S_k.eval(i))
            ptr1[i] = u00 * local + u01 * remote;
        else
            ptr1[i] = u10 * remote + u11 * local;
    }
}

void p_block_kernel(val_t *ptr, size_t local_bits, selector_t S_block, float_t theta)
{
    const size_t n = size_t(1) << local_bits;
    for (size_t off = 0; off < n; off++)
    {
        const raddr_t xr = static_cast<raddr_t>(off);
        if (S_block.eval(xr))
            ptr[off] *= Phase(theta);
    }
}

void p_block_batch_kernel(val_t *ptr, size_t local_bits, std::vector<selector_t> S_block, std::vector<float_t> theta)
{
    if (S_block.size() != theta.size())
        abort("p_block_batch_kernel selector/theta size mismatch");

    diag_pending_reset();
    for (size_t i = 0; i < S_block.size(); i++)
        diag_pending_push_p(S_block[i], theta[i]);
    diag_pending_flush(ptr, local_bits);
}

void diag_pending_reset()
{
    g_diag_p_l.clear();
    g_diag_p_h.clear();
    g_diag_p_x.clear();
    g_diag_cp_ll.clear();
    g_diag_cp_hh.clear();
    g_diag_cp_hl.clear();
}

void diag_pending_push_p(selector_t S_block, float_t theta)
{
    switch (classify_selector(S_block))
    {
    case selector_class_t::low:
        g_diag_p_l.push_back({S_block, theta});
        break;
    case selector_class_t::high:
        g_diag_p_h.push_back({S_block, theta});
        break;
    case selector_class_t::cross:
        g_diag_p_x.push_back({S_block, theta});
        break;
    }
}

bool diag_pending_try_push_cp(selector_t S_cq_block, selector_t S_q_block, float_t theta)
{
    const selector_class_t cq_class = classify_selector(S_cq_block);
    const selector_class_t q_class = classify_selector(S_q_block);

    if (cq_class == selector_class_t::low && q_class == selector_class_t::low)
    {
        g_diag_cp_ll.push_back({S_cq_block, S_q_block, theta});
        return true;
    }
    if (cq_class == selector_class_t::high && q_class == selector_class_t::high)
    {
        g_diag_cp_hh.push_back({S_cq_block, S_q_block, theta});
        return true;
    }
    if (cq_class == selector_class_t::low && q_class == selector_class_t::high)
    {
        g_diag_cp_hl.push_back({S_cq_block, S_q_block, theta});
        return true;
    }
    if (cq_class == selector_class_t::high && q_class == selector_class_t::low)
    {
        g_diag_cp_hl.push_back({S_q_block, S_cq_block, theta});
        return true;
    }
    return false;
}

bool diag_pending_empty()
{
    return !any_diag_pending();
}

void diag_pending_flush(val_t *ptr, size_t local_bits)
{
    if (!any_diag_pending())
        return;

    const size_t n = size_t(1) << local_bits;
    apply_diag_window(ptr, n);
    diag_pending_reset();
}

void cp_kernel(val_t *ptr, size_t local_bits, selector_t S_cq_block, selector_t S_q_block, float_t theta)
{
    const size_t n = size_t(1) << local_bits;
    for (size_t off = 0; off < n; off++)
    {
        const raddr_t xr = static_cast<raddr_t>(off);
        if (S_cq_block.eval(xr) && S_q_block.eval(xr))
            ptr[off] *= Phase(theta);
    }
}

} // namespace ZXHSim
