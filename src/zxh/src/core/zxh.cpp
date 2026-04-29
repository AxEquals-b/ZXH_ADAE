#include "zxhsim/zxh.h"

#include "zxhsim/comm.h"
#include "zxhsim/defs.h"
#include "zxhsim/kernels.h"
#include "zxhsim/mem.h"
#include "zxhsim/measure.h"
#include "zxhsim/runtime.h"
#include "zxhsim/sv.h"

#include "../sv/sv_internal.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <map>
#include <memory>
#include <string>

namespace ZXHSim
{

namespace
{
constexpr float_t PI = 3.14159265358979323846;
constexpr float_t H_U3_THETA = PI / 2.0;
constexpr float_t H_U3_LAMBDA = PI;
constexpr float_t H_U3_PHI = 0.0;
constexpr float_t kU3BatchEps = 1e-5f;

std::complex<float_t> phase(float_t angle)
{
    return std::exp(std::complex<float_t>(0.0, angle));
}

raddr_t low_bits_mask(size_t nbits)
{
    if (nbits == 0)
        return 0;
    if (nbits >= sizeof(raddr_t) * 8)
        return ~raddr_t(0);
    return (raddr_t(1) << nbits) - 1;
}

raddr_t reverse_n_bits(raddr_t value, size_t nbits)
{
    raddr_t out = 0;
    for (size_t i = 0; i < nbits; i++)
    {
        out = (out << 1) | ((value >> i) & raddr_t(1));
    }
    return out;
}

selector_t make_local_selector(const selector_t &global_selector, raddr_t local_base, size_t local_bits)
{
    const raddr_t alpha_low = global_selector.alpha() & low_bits_mask(local_bits);
    const bool beta_local = global_selector.eval(local_base);
    return selector_t(alpha_low, beta_local);
}

float_t z_gate_theta(const gate_t &g)
{
    return (g.type == gate_type_t::Z) ? PI : g.theta;
}

size_t active_local_len(const sv_t &sv)
{
    return static_cast<size_t>(sv.block_end - sv.block_start);
}

size_t active_local_bits(const sv_t &sv)
{
    size_t len = active_local_len(sv);
    size_t bits = 0;
    while (len > 1)
    {
        len >>= 1;
        bits++;
    }
    return bits;
}

size_t checked_state_span(size_t nbits, const char *what)
{
    if (nbits >= 64)
        abort(std::string(what) + " requires fewer than 64 qubits");
    return size_t(1ULL) << nbits;
}

bool is_u3_gate(const gate_t &g)
{
    return g.type == gate_type_t::H || g.type == gate_type_t::U3;
}

uint64_t pack_selector(const selector_t &sel)
{
    return sel.alpha() | (sel.beta() ? (uint64_t(1) << 63) : 0ULL);
}

void build_u3_matrix(float_t theta, float_t lambda, float_t phi, val_t &u00, val_t &u01, val_t &u10, val_t &u11)
{
    const float_t c = std::cos(theta / 2.0);
    const float_t s = std::sin(theta / 2.0);
    const val_t e_lambda = phase(lambda);
    const val_t e_phi = phase(phi);
    const val_t e_phi_lambda = phase(phi + lambda);

    u00 = val_t(c, 0.0);
    u01 = -e_lambda * s;
    u10 = e_phi * s;
    u11 = e_phi_lambda * c;
}

bool close_val(val_t a, val_t b)
{
    return std::abs(a - b) <= kU3BatchEps;
}

struct u3_accum_t
{
    bool active = false;
    val_t u00 = val_t(1.0, 0.0);
    val_t u01 = val_t(0.0, 0.0);
    val_t u10 = val_t(0.0, 0.0);
    val_t u11 = val_t(1.0, 0.0);
};

bool is_identity_u3(const u3_accum_t &acc)
{
    return close_val(acc.u00, val_t(1.0, 0.0)) && close_val(acc.u01, val_t(0.0, 0.0)) &&
           close_val(acc.u10, val_t(0.0, 0.0)) && close_val(acc.u11, val_t(1.0, 0.0));
}

void reset_u3_accum(u3_accum_t &acc)
{
    acc.active = false;
    acc.u00 = val_t(1.0, 0.0);
    acc.u01 = val_t(0.0, 0.0);
    acc.u10 = val_t(0.0, 0.0);
    acc.u11 = val_t(1.0, 0.0);
}

void left_multiply_u3(u3_accum_t &acc, val_t n00, val_t n01, val_t n10, val_t n11)
{
    const val_t o00 = acc.u00;
    const val_t o01 = acc.u01;
    const val_t o10 = acc.u10;
    const val_t o11 = acc.u11;

    acc.u00 = n00 * o00 + n01 * o10;
    acc.u01 = n00 * o01 + n01 * o11;
    acc.u10 = n10 * o00 + n11 * o10;
    acc.u11 = n10 * o01 + n11 * o11;
    acc.active = !is_identity_u3(acc);
}

u3_batch_desc_t make_u3_batch_desc(const selector_t &sel, raddr_t delta_so, const u3_accum_t &acc)
{
    u3_batch_desc_t desc;
    desc.packed_sel = pack_selector(sel);
    desc.delta_so = delta_so;
    desc.u00_re = acc.u00.real();
    desc.u00_im = acc.u00.imag();
    desc.u01_re = acc.u01.real();
    desc.u01_im = acc.u01.imag();
    desc.u10_re = acc.u10.real();
    desc.u10_im = acc.u10.imag();
    desc.u11_re = acc.u11.real();
    desc.u11_im = acc.u11.imag();
    return desc;
}

} // namespace

struct ZXH::impl_t
{
    explicit impl_t(size_t n, bool disable_x_in, bool eager_expand_all_in)
        : N(n), sv(), A(n), b(n, false), gates(), use_seed(false), seed(0),
          measure_cache(n), disable_x_transport(disable_x_in), eager_expand_all(eager_expand_all_in)
    {
    }

    size_t calc_mem(const std::vector<gate_t> &gates_in) const;
    selector_t make_selector(size_t k) const;
    bool probe_u3_delta(size_t q, raddr_t &delta) const;
    raddr_t solve_expand(size_t k);
    void expand_all();

    void apply_x(size_t q);
    void apply_cx(size_t cq, size_t q);
    void apply_x_explicit(size_t q);
    void apply_cx_explicit(size_t cq, size_t q);
    void apply_u3(size_t q, float_t theta, float_t lambda, float_t phi);
    void apply_cp(const gate_t &g);

    size_t N;
    sv_t sv;
    bitmat_t A;
    bitvec_t b;
    std::vector<gate_t> gates;
    bool use_seed;
    uint64_t seed;
    measure_cache_t measure_cache;
    bool disable_x_transport;
    bool eager_expand_all;
};

ZXH::ZXH(size_t N, bool disable_x, bool eager_expand_all)
    : global_phase(1.0, 0.0), impl_(std::make_unique<impl_t>(N, disable_x, eager_expand_all))
{
}

ZXH::~ZXH() = default;

void ZXH::set_seed(uint64_t seed)
{
    impl_->use_seed = true;
    impl_->seed = seed;
}

void ZXH::clear_seed()
{
    impl_->use_seed = false;
    impl_->seed = 0;
}

void ZXH::clear_gates()
{
    impl_->gates.clear();
    global_phase = val_t(1.0, 0.0);
}

void ZXH::Barrier()
{
    impl_->gates.push_back({gate_type_t::Barrier, 0, 0, 0.0, 0.0, 0.0});
}

void ZXH::Rz(size_t q, float_t theta)
{
    if (q >= impl_->N)
        abort("Rz target qubit out of range");
    impl_->gates.push_back({gate_type_t::Rz, 0, q, theta, 0.0, 0.0});
}

void ZXH::CRz(size_t cq, size_t q, float_t theta)
{
    if (cq >= impl_->N || q >= impl_->N)
        abort("CRz qubit out of range");
    impl_->gates.push_back({gate_type_t::P, 0, cq, float_t(-0.5) * theta, 0.0, 0.0});
    impl_->gates.push_back({gate_type_t::CP, cq, q, theta, 0.0, 0.0});
}

void ZXH::CP(size_t cq, size_t q, float_t theta)
{
    if (cq >= impl_->N || q >= impl_->N)
        abort("CP qubit out of range");
    impl_->gates.push_back({gate_type_t::CP, cq, q, theta, 0.0, 0.0});
}

void ZXH::P(size_t q, float_t theta)
{
    if (q >= impl_->N)
        abort("P target qubit out of range");
    impl_->gates.push_back({gate_type_t::P, 0, q, theta, 0.0, 0.0});
}

void ZXH::Z(size_t q)
{
    if (q >= impl_->N)
        abort("Z target qubit out of range");
    impl_->gates.push_back({gate_type_t::Z, 0, q, 0.0, 0.0, 0.0});
}

void ZXH::X(size_t q)
{
    if (q >= impl_->N)
        abort("X target qubit out of range");
    impl_->gates.push_back({gate_type_t::X, 0, q, 0.0, 0.0, 0.0});
}

void ZXH::CX(size_t cq, size_t q)
{
    if (cq >= impl_->N || q >= impl_->N)
        abort("CX qubit out of range");
    impl_->gates.push_back({gate_type_t::CX, cq, q, 0.0, 0.0, 0.0});
}

void ZXH::H(size_t q)
{
    if (q >= impl_->N)
        abort("H target qubit out of range");
    impl_->gates.push_back({gate_type_t::H, 0, q, 0.0, 0.0, 0.0});
}

void ZXH::U3(size_t q, float_t theta, float_t lambda, float_t phi)
{
    if (q >= impl_->N)
        abort("U3 target qubit out of range");
    impl_->gates.push_back({gate_type_t::U3, 0, q, theta, lambda, phi});
}

void ZXH::Rx(size_t q, float_t theta)
{
    if (q >= impl_->N)
        abort("Rx target qubit out of range");
    // Qiskit U3(theta, phi, lambda) realizes Rx(theta) when
    // phi = -pi/2 and lambda = pi/2. ZXH::U3 stores (theta, lambda, phi).
    impl_->gates.push_back({gate_type_t::U3, 0, q, theta, PI / 2.0, -PI / 2.0});
}

void ZXH::execute()
{
    std::vector<gate_t> gates_exec;
    size_t gate_count = 0;

    // TODO: circuit optimization
    if (rank() == 0)
    {
        gates_exec = impl_->gates;
        gate_count = gates_exec.size();
    }

    host_broadcast(&gate_count, sizeof(size_t), 0);
    if (rank() != 0)
        gates_exec.resize(gate_count);
    host_broadcast(gates_exec.data(), gate_count * sizeof(gate_t), 0);

    const size_t target_M = impl_->eager_expand_all ? impl_->N : impl_->calc_mem(gates_exec);
    impl_->sv.resize(target_M);
    impl_->sv.reset();
    global_phase = val_t(1.0, 0.0);

    impl_->A = bitmat_t(impl_->N);
    impl_->b = bitvec_t(impl_->N, false);
    if (impl_->eager_expand_all)
        impl_->expand_all();

    diag_pending_reset();
    std::vector<u3_accum_t> pending_u3(impl_->N);
    size_t pending_u3_count = 0;

    auto flush_pending = [&]() {
        if (diag_pending_empty())
            return;
        const size_t local_len = active_local_len(impl_->sv);
        if (local_len == 0)
        {
            diag_pending_reset();
            return;
        }
        const size_t local_bits = active_local_bits(impl_->sv);
        val_t *block_ptr = impl_->sv.segment_ptr(impl_->sv.block_start);
        diag_pending_flush(block_ptr, local_bits);
    };

    auto clear_u3_batch = [&]() {
        for (u3_accum_t &acc : pending_u3)
            reset_u3_accum(acc);
        pending_u3_count = 0;
    };

    auto absorb_u3_gate = [&](const gate_t &g) {
        val_t u00;
        val_t u01;
        val_t u10;
        val_t u11;
        if (g.type == gate_type_t::H)
            build_u3_matrix(H_U3_THETA, H_U3_LAMBDA, H_U3_PHI, u00, u01, u10, u11);
        else
            build_u3_matrix(g.theta, g.lambda, g.phi, u00, u01, u10, u11);

        u3_accum_t &acc = pending_u3[g.q];
        const bool was_active = acc.active;
        if (!was_active)
        {
            acc.active = true;
            acc.u00 = val_t(1.0, 0.0);
            acc.u01 = val_t(0.0, 0.0);
            acc.u10 = val_t(0.0, 0.0);
            acc.u11 = val_t(1.0, 0.0);
        }
        left_multiply_u3(acc, u00, u01, u10, u11);
        if (!was_active && acc.active)
            pending_u3_count++;
        else if (was_active && !acc.active)
            pending_u3_count--;
    };

    auto flush_u3_batch = [&]() {
        if (pending_u3_count == 0)
            return;

        const size_t local_len = active_local_len(impl_->sv);
        if (local_len == 0)
        {
            clear_u3_batch();
            return;
        }

        const size_t local_bits = active_local_bits(impl_->sv);
        val_t *block_ptr = impl_->sv.segment_ptr(impl_->sv.block_start);
        std::vector<u3_batch_desc_t> descs;
        descs.reserve(impl_->N);

        for (size_t q = 0; q < impl_->N; q++)
        {
            const u3_accum_t &acc = pending_u3[q];
            if (!acc.active)
                continue;

            raddr_t delta = 0;
            if (!impl_->probe_u3_delta(q, delta))
                abort("flush_u3_batch requires no-expand U3 descriptors");

            const raddr_t delta_b = (impl_->sv.K == 0) ? 0 : ((delta >> (impl_->sv.I + impl_->sv.J)) & low_bits_mask(impl_->sv.K));
            if (delta_b != 0)
                abort("flush_u3_batch requires local-only U3 descriptors");

            const selector_t S_q = impl_->make_selector(q);
            const selector_t S_block = make_local_selector(S_q, impl_->sv.block_start, local_bits);
            descs.push_back(make_u3_batch_desc(S_block, delta & low_bits_mask(local_bits), acc));
        }

        clear_u3_batch();
        if (!descs.empty())
            u3_block_batch_kernel(block_ptr, local_bits, descs);
    };

    auto apply_u3_eager = [&](const gate_t &g) {
        if (g.type == gate_type_t::H)
            impl_->apply_u3(g.q, H_U3_THETA, H_U3_LAMBDA, H_U3_PHI);
        else
            impl_->apply_u3(g.q, g.theta, g.lambda, g.phi);
    };

    for (size_t gate_idx = 0; gate_idx < gates_exec.size();)
    {
        const gate_t &g = gates_exec[gate_idx];
        if (is_u3_gate(g))
        {
            flush_pending();
            while (gate_idx < gates_exec.size() && is_u3_gate(gates_exec[gate_idx]))
            {
                const gate_t &u3_gate = gates_exec[gate_idx];
                raddr_t delta = 0;
                if (!impl_->probe_u3_delta(u3_gate.q, delta))
                {
                    flush_u3_batch();
                    apply_u3_eager(u3_gate);
                    gate_idx++;
                    continue;
                }

                const raddr_t delta_b =
                    (impl_->sv.K == 0) ? 0 : ((delta >> (impl_->sv.I + impl_->sv.J)) & low_bits_mask(impl_->sv.K));
                if (delta_b != 0)
                {
                    flush_u3_batch();
                    apply_u3_eager(u3_gate);
                    gate_idx++;
                    continue;
                }

                absorb_u3_gate(u3_gate);
                gate_idx++;
            }
            flush_u3_batch();
            continue;
        }

        switch (g.type)
        {
        case gate_type_t::Barrier:
            flush_pending();
            break;
        case gate_type_t::Z:
        case gate_type_t::Rz: {
            const size_t local_len = active_local_len(impl_->sv);
            if (local_len == 0)
            {
                const float_t theta = z_gate_theta(g);
                global_phase *= phase(-0.5 * theta);
                break;
            }
            const size_t local_bits = active_local_bits(impl_->sv);
            const selector_t S_q = impl_->make_selector(g.q);
            const selector_t S_q_block = make_local_selector(S_q, impl_->sv.block_start, local_bits);
            const float_t theta = z_gate_theta(g);
            diag_pending_push_p(S_q_block, theta);
            global_phase *= phase(-0.5 * theta);
            break;
        }
        case gate_type_t::P: {
            const size_t local_len = active_local_len(impl_->sv);
            if (local_len == 0)
                break;
            const size_t local_bits = active_local_bits(impl_->sv);
            const selector_t S_q = impl_->make_selector(g.q);
            const selector_t S_q_block = make_local_selector(S_q, impl_->sv.block_start, local_bits);
            diag_pending_push_p(S_q_block, g.theta);
            break;
        }
        case gate_type_t::X:
            if (impl_->disable_x_transport)
            {
                flush_pending();
                impl_->apply_x_explicit(g.q);
            }
            else
            {
                impl_->apply_x(g.q);
            }
            break;
        case gate_type_t::CX:
            if (impl_->disable_x_transport)
            {
                flush_pending();
                impl_->apply_cx_explicit(g.cq, g.q);
            }
            else
            {
                impl_->apply_cx(g.cq, g.q);
            }
            break;
        case gate_type_t::CP: {
            const size_t local_len = active_local_len(impl_->sv);
            if (local_len == 0)
                break;
            const size_t local_bits = active_local_bits(impl_->sv);
            const selector_t S_cq = impl_->make_selector(g.cq);
            const selector_t S_q = impl_->make_selector(g.q);
            const selector_t S_cq_block = make_local_selector(S_cq, impl_->sv.block_start, local_bits);
            const selector_t S_q_block = make_local_selector(S_q, impl_->sv.block_start, local_bits);
            if (!diag_pending_try_push_cp(S_cq_block, S_q_block, g.theta))
            {
                flush_pending();
                impl_->apply_cp(g);
            }
            break;
        }
        default:
            break;
        }
        gate_idx++;
    }

    flush_pending();

    // Keep execute/sample timing boundary stable: synchronize once after all gates.
    kernel_sync();
    impl_->measure_cache.invalidate_mapping();
}

void ZXH::measure(size_t cnt)
{
    ::ZXHSim::measure(impl_->sv, impl_->A, impl_->b, impl_->measure_cache, cnt,
                      impl_->use_seed, impl_->seed);
}

void ZXH::get_results(res_t *results, size_t cnt) const
{
    ::ZXHSim::get_results(impl_->measure_cache, results, cnt);
}

size_t ZXH::measured_count() const
{
    return impl_->measure_cache.result_count();
}

std::vector<res_t> ZXH::Sampling(size_t shots)
{
    std::vector<res_t> out(shots, res_t(impl_->N, false));
    measure(shots);
    get_results(out.data(), shots);
    return out;
}

std::vector<val_t> ZXH::get_state() const
{
    if (impl_->sv.raw_data() == nullptr)
        abort("get_state requires execute() to be called first");

    const size_t M = impl_->A.m();
    const size_t real_size = checked_state_span(M, "get_state physical support export");
    const size_t virtual_size = checked_state_span(impl_->N, "get_state full state export");
    const size_t local_size = active_local_len(impl_->sv);

    std::vector<val_t> local_state(local_size, val_t(0.0, 0.0));
    worker_copy_to_host(local_state.data(), impl_->sv.raw_data(), local_size);

    std::vector<val_t> real_state(real_size, val_t(0.0, 0.0));
    if (nprocs() == 1)
    {
        std::copy(local_state.begin(), local_state.end(), real_state.begin());
    }
    else
    {
        const size_t local_bytes = local_size * sizeof(val_t);
        std::vector<size_t> recv_bytes;
        std::vector<size_t> recv_displs;

        if (rank() == 0)
            recv_bytes.resize(nprocs(), 0);
        host_gather_size(local_bytes, rank() == 0 ? recv_bytes.data() : nullptr, 0);

        if (rank() == 0)
        {
            recv_displs.resize(nprocs(), 0);
            size_t total_bytes = 0;
            for (size_t i = 0; i < recv_bytes.size(); i++)
            {
                recv_displs[i] = total_bytes;
                total_bytes += recv_bytes[i];
            }
            if (total_bytes != real_size * sizeof(val_t))
                abort("get_state gathered physical state size mismatch");
        }

        host_gatherv(local_size == 0 ? nullptr : local_state.data(), local_bytes,
                     rank() == 0 ? real_state.data() : nullptr,
                     rank() == 0 ? recv_bytes.data() : nullptr,
                     rank() == 0 ? recv_displs.data() : nullptr, 0);
        host_broadcast(real_state.data(), real_size * sizeof(val_t), 0);
    }

    std::vector<val_t> state(virtual_size, val_t(0.0, 0.0));
    for (size_t real = 0; real < real_size; real++)
    {
        const bitvec_t virt_bits = impl_->A.mul(static_cast<raddr_t>(real)) ^ impl_->b;
        const raddr_t virt_qiskit = virt_bits.to_uint64();
        const size_t virt_cudaq = static_cast<size_t>(reverse_n_bits(virt_qiskit, impl_->N));
        state[virt_cudaq] = real_state[real] * global_phase;
    }
    return state;
}

size_t ZXH::required_M() const
{
    return impl_->calc_mem(impl_->gates);
}

size_t ZXH::num_qubits() const
{
    return impl_->N;
}

size_t ZXH::impl_t::calc_mem(const std::vector<gate_t> &gates_in) const
{
    bitmat_t A_tmp(N);
    for (const gate_t &g : gates_in)
    {
        switch (g.type)
        {
        case gate_type_t::X:
        case gate_type_t::CX:
            if (!disable_x_transport)
            {
                if (g.type == gate_type_t::CX)
                    A_tmp.row_xor(g.q, g.cq);
                break;
            }
            [[fallthrough]];
        case gate_type_t::H:
        case gate_type_t::U3: {
            const vaddr_t rhs = bitvec_t::e_i(N, g.q);
            raddr_t delta = 0;
            if (!A_tmp.solve(rhs, delta))
            {
                bitvec_t col(N, false);
                col.set_bit(g.q, true);
                A_tmp.append_col(col);
            }
            break;
        }
        default:
            break;
        }
    }
    return A_tmp.m();
}

selector_t ZXH::impl_t::make_selector(size_t k) const
{
    if (k >= N)
        abort("selector qubit out of range");

    const raddr_t alpha = A.get_row(k);
    const bool beta = b.get_bit(k);
    return selector_t(alpha, beta);
}

bool ZXH::impl_t::probe_u3_delta(size_t q, raddr_t &delta) const
{
    if (q >= N)
        abort("probe_u3_delta qubit out of range");
    const vaddr_t rhs = bitvec_t::e_i(N, q);
    return A.solve(rhs, delta);
}

raddr_t ZXH::impl_t::solve_expand(size_t k)
{
    if (k >= N)
        abort("solve_expand qubit out of range");

    const vaddr_t rhs = bitvec_t::e_i(N, k);

    raddr_t delta = 0;
    if (!A.solve(rhs, delta))
    {
        sv.expand();

        bitvec_t col = bitvec_t::e_i(N, k);
        A.append_col(col);
        delta = raddr_t(1) << (A.m() - 1);
    }

    return delta;
}

void ZXH::impl_t::expand_all()
{
    while (sv.used_bits() < N)
        sv.expand();
    A = bitmat_t(N);
    for (size_t q = 0; q < N; q++)
        A.append_col(bitvec_t::e_i(N, q));
    b = bitvec_t(N, false);
}

void ZXH::impl_t::apply_x(size_t q)
{
    b.set_bit(q, !b.get_bit(q));
}

void ZXH::impl_t::apply_cx(size_t cq, size_t q)
{
    A.row_xor(q, cq);
    b.set_bit(q, b.get_bit(q) != b.get_bit(cq));
}

void ZXH::impl_t::apply_x_explicit(size_t q)
{
    const raddr_t delta = solve_expand(q);
    const size_t local_len = active_local_len(sv);
    const size_t local_bits = active_local_bits(sv);
    const raddr_t mask_IJ = low_bits_mask(sv.I + sv.J);
    const raddr_t delta_so = delta & mask_IJ;
    const raddr_t delta_b = (sv.K == 0) ? 0 : ((delta >> (sv.I + sv.J)) & low_bits_mask(sv.K));

    if (delta_b != 0)
        abort("disable_x ablation does not support inter-worker X");
    if (local_len == 0)
        return;

    const selector_t S_q = make_selector(q);
    const selector_t S_q_block = make_local_selector(S_q, sv.block_start, local_bits);
    x_block_kernel(sv.segment_ptr(sv.block_start), local_bits, delta_so, S_q_block);
}

void ZXH::impl_t::apply_cx_explicit(size_t cq, size_t q)
{
    const raddr_t delta = solve_expand(q);
    const size_t local_len = active_local_len(sv);
    const size_t local_bits = active_local_bits(sv);
    const raddr_t mask_IJ = low_bits_mask(sv.I + sv.J);
    const raddr_t delta_so = delta & mask_IJ;
    const raddr_t delta_b = (sv.K == 0) ? 0 : ((delta >> (sv.I + sv.J)) & low_bits_mask(sv.K));

    if (delta_b != 0)
        abort("disable_x ablation does not support inter-worker CX");
    if (local_len == 0)
        return;

    const selector_t S_cq = make_selector(cq);
    const selector_t S_q = make_selector(q);
    const selector_t S_cq_block = make_local_selector(S_cq, sv.block_start, local_bits);
    const selector_t S_q_block = make_local_selector(S_q, sv.block_start, local_bits);
    cx_block_kernel(sv.segment_ptr(sv.block_start), local_bits, delta_so, S_cq_block, S_q_block);
}

void ZXH::impl_t::apply_u3(size_t q, float_t theta, float_t lambda, float_t phi)
{
    const raddr_t delta = solve_expand(q);
    const selector_t S_q = make_selector(q);
    const size_t local_len = active_local_len(sv);
    const size_t local_bits = active_local_bits(sv);
    if (local_len == 0)
        return;

    const raddr_t mask_I = low_bits_mask(sv.I);
    const raddr_t mask_IJ = low_bits_mask(sv.I + sv.J);
    const raddr_t delta_o = delta & mask_I;
    const raddr_t delta_so = delta & mask_IJ;
    const raddr_t delta_bs = delta & (~mask_I);
    const raddr_t delta_b = (sv.K == 0) ? 0 : ((delta >> (sv.I + sv.J)) & low_bits_mask(sv.K));

    const float_t c = std::cos(theta / 2.0);
    const float_t s = std::sin(theta / 2.0);
    const val_t e_lambda = phase(lambda);
    const val_t e_phi = phase(phi);
    const val_t e_phi_lambda = phase(phi + lambda);

    const val_t u00(c, 0.0);
    const val_t u01 = -e_lambda * s;
    const val_t u10 = e_phi * s;
    const val_t u11 = e_phi_lambda * c;

    if (delta_b == 0)
    {
        const selector_t S_block = make_local_selector(S_q, sv.block_start, local_bits);
        u3_block_kernel(sv.segment_ptr(sv.block_start), local_bits, delta_so, S_block, u00, u01, u10, u11);
    }
    else
    {
        neighbor_stream_t stream(sv, delta_bs);
        neighbor_t neighbor;
        while (stream.acquire(neighbor))
        {
            const selector_t S_seg = make_local_selector(S_q, neighbor.seg, sv.I);
            u3_inter_kernel(neighbor.local, neighbor.remote, sv.I, delta_o, S_seg, u00, u01, u10, u11);
            stream.release();
        }
    }
}

void ZXH::impl_t::apply_cp(const gate_t &g)
{
    const size_t local_len = active_local_len(sv);
    if (local_len == 0)
        return;
    const size_t local_bits = active_local_bits(sv);
    val_t *block_ptr = sv.segment_ptr(sv.block_start);

    const selector_t S_cq = make_selector(g.cq);
    const selector_t S_q = make_selector(g.q);
    const selector_t S_cq_block = make_local_selector(S_cq, sv.block_start, local_bits);
    const selector_t S_q_block = make_local_selector(S_q, sv.block_start, local_bits);
    cp_kernel(block_ptr, local_bits, S_cq_block, S_q_block, g.theta);
}

void PrintRes(const std::vector<res_t> &res, int n)
{
    std::map<std::string, size_t> counts;
    for (const auto &item : res)
    {
        std::string s;
        s.reserve(static_cast<size_t>(n));
        for (int i = n - 1; i >= 0; i--)
            s.push_back(item.get_bit(static_cast<size_t>(i)) ? '1' : '0');
        counts[s]++;
    }

    for (const auto &[k, v] : counts)
        log(k + ": " + std::to_string(v));
}

void PrintRes(const std::vector<std::vector<bool>> &res, int n)
{
    std::vector<res_t> packed;
    packed.reserve(res.size());
    for (const auto &vec : res)
    {
        bitvec_t bits(static_cast<size_t>(n), false);
        const size_t lim = std::min(vec.size(), static_cast<size_t>(n));
        for (size_t i = 0; i < lim; i++)
            bits.set_bit(i, vec[i]);
        packed.push_back(bits);
    }
    PrintRes(packed, n);
}

} // namespace ZXHSim
