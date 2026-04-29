#include "zxhsim/sv.h"
#include "zxhsim/mem.h"
#include "sv_internal.h"

#include "zxhsim/comm.h"

#include <algorithm>
#include <array>
#include <cstdlib>

namespace ZXHSim
{

namespace
{
constexpr size_t MAX_M_BITS = 63;
constexpr size_t kDefaultMinI = 18;
constexpr size_t kDefaultMaxI = 22;
constexpr size_t kDefaultMinJ = 7;
constexpr size_t kDefaultTargetSegmentBytes = size_t(16) << 20;

struct sv_layout_t
{
    size_t I = 0;
    size_t J = 0;
    size_t K = 0;
};

size_t calc_segment_len(size_t I)
{
    return size_t(1ULL) << I;
}

size_t floor_log2(size_t x)
{
    size_t k = 0;
    while ((size_t(1) << (k + 1)) <= x)
        k++;
    return k;
}

size_t segment_owner(const sv_t &sv, raddr_t seg_base)
{
    if (sv.K == 0)
        return rank();
    return static_cast<size_t>(seg_base >> (sv.I + sv.J));
}

size_t parse_env_size_t(const char *name, size_t default_value)
{
    const char *env = std::getenv(name);
    if (env == nullptr || *env == '\0')
        return default_value;

    char *end = nullptr;
    const unsigned long long parsed = std::strtoull(env, &end, 10);
    if (end == env || (end != nullptr && *end != '\0') || parsed == 0)
        return default_value;
    return static_cast<size_t>(parsed);
}

size_t runtime_min_i()
{
    static const size_t value = parse_env_size_t("ZXHSIM_SEG_MIN_I", kDefaultMinI);
    return value;
}

size_t runtime_max_i()
{
    static const size_t value = parse_env_size_t("ZXHSIM_SEG_MAX_I", kDefaultMaxI);
    return value;
}

size_t runtime_min_j()
{
    static const size_t value = parse_env_size_t("ZXHSIM_SEG_MIN_J", kDefaultMinJ);
    return value;
}

size_t runtime_target_segment_bytes()
{
    static const size_t value =
        parse_env_size_t("ZXHSIM_SEG_TARGET_BYTES", kDefaultTargetSegmentBytes);
    return value;
}

sv_layout_t choose_layout(size_t M, size_t nprocs)
{
    const size_t min_i = runtime_min_i();
    const size_t max_i = std::max(min_i, runtime_max_i());
    const size_t min_j = runtime_min_j();
    const size_t target_bytes = runtime_target_segment_bytes();

    const size_t max_k = floor_log2(nprocs);
    if (nprocs <= 1)
    {
        if (M <= min_i)
            return {M, 0, 0};
        return {min_i, M - min_i, 0};
    }

    const size_t K = (M > min_i) ? std::min(max_k, M - min_i) : 0;
    const size_t local_bits = M - K;
    if (local_bits <= min_i)
        return {local_bits, 0, K};

    size_t target_i = min_i;
    if (target_bytes > sizeof(val_t))
        target_i = std::max(min_i, floor_log2(target_bytes / sizeof(val_t)));

    size_t I = std::min(max_i, std::min(local_bits, target_i));
    if (local_bits > min_j)
        I = std::min(I, local_bits - min_j);

    if (I < min_i)
        I = std::min(local_bits, min_i);

    return {I, local_bits - I, K};
}

} // namespace

class slot_pool_t
{
  public:
    static constexpr size_t kSlotCount = 2;

    slot_pool_t() = default;

    void configure(size_t segment_len)
    {
        reset();
        if (segment_len_ == segment_len)
            return;

        segment_len_ = segment_len;
        for (auto &slot : slots_)
            slot.configure(segment_len_);
    }

    void reset()
    {
        for (size_t idx = 0; idx < kSlotCount; idx++)
        {
            slots_[idx].release();
            in_use_[idx] = false;
        }
    }

    size_t acquire()
    {
        for (size_t idx = 0; idx < kSlotCount; idx++)
        {
            if (!in_use_[idx])
            {
                in_use_[idx] = true;
                return idx;
            }
        }
        abort("slot_pool_t::acquire failed: no free slot");
        return 0;
    }

    worker_slot_t &slot(size_t idx)
    {
        if (idx >= kSlotCount)
            abort("slot_pool_t::slot index out of range");
        return slots_[idx];
    }

    void release(size_t idx)
    {
        if (idx >= kSlotCount)
            abort("slot_pool_t::release index out of range");
        slots_[idx].release();
        in_use_[idx] = false;
    }

  private:
    size_t segment_len_ = 0;
    std::array<worker_slot_t, kSlotCount> slots_;
    std::array<bool, kSlotCount> in_use_ = {false, false};
};

neighbor_stream_t::neighbor_stream_t(sv_t &sv, raddr_t delta_bs)
    : sv_(sv), delta_bs_(delta_bs), step_(calc_segment_len(sv.I)), next_seg_(sv.block_start)
{
    if (sv_.slot_pool_ == nullptr)
        abort("neighbor_stream_t requires sv slot_pool_");
    sv_.slot_pool_->reset();
    prefetch_next();
}

neighbor_stream_t::~neighbor_stream_t()
{
    sv_.slot_pool_->reset();
    prefetched_ = false;
    acquired_ = false;
    prefetched_slot_ = kInvalidSlot;
    acquired_slot_ = kInvalidSlot;
    acquired_remote_ = nullptr;
}

void neighbor_stream_t::prefetch_next()
{
    if (prefetched_ || next_seg_ >= sv_.block_end)
        return;

    const raddr_t seg = next_seg_;
    next_seg_ += step_;

    const raddr_t neighbor_seg = seg ^ delta_bs_;
    const size_t peer = segment_owner(sv_, neighbor_seg);
    const size_t slot_idx = sv_.slot_pool_->acquire();
    sv_.slot_pool_->slot(slot_idx).pre_exchange(sv_.segment_ptr(seg), peer);

    prefetched_ = true;
    prefetched_seg_ = seg;
    prefetched_slot_ = slot_idx;
}

bool neighbor_stream_t::acquire(neighbor_t &neighbor)
{
    if (acquired_)
        abort("neighbor_stream_t::acquire requires release of the previous neighbor");
    if (!prefetched_)
        return false;

    acquired_ = true;
    acquired_seg_ = prefetched_seg_;
    acquired_slot_ = prefetched_slot_;
    acquired_remote_ = sv_.slot_pool_->slot(acquired_slot_).wait_exchange();

    prefetched_ = false;
    prefetched_slot_ = kInvalidSlot;
    prefetch_next();

    neighbor.seg = acquired_seg_;
    neighbor.local = sv_.segment_ptr(acquired_seg_);
    neighbor.remote = acquired_remote_;
    return true;
}

void neighbor_stream_t::release()
{
    if (!acquired_)
        abort("neighbor_stream_t::release without acquire");

    sv_.slot_pool_->release(acquired_slot_);
    acquired_ = false;
    acquired_seg_ = 0;
    acquired_slot_ = kInvalidSlot;
    acquired_remote_ = nullptr;
}

sv_t::sv_t()
    : C_(0), M_(0), m_(0), alloc_elems_(1), data_(worker_alloc(1)), slot_pool_(std::make_unique<slot_pool_t>())
{
    reset();
    slot_pool_->configure(calc_segment_len(I));
}

sv_t::~sv_t()
{
    slot_pool_.reset();
    worker_free(data_);
    data_ = nullptr;
    alloc_elems_ = 0;
}

size_t sv_t::used_bits() const
{
    return m_;
}

size_t sv_t::rank() const
{
    return ZXHSim::rank();
}

size_t sv_t::nprocs() const
{
    return ZXHSim::nprocs();
}

void sv_t::reset()
{
    m_ = 0;
    if (slot_pool_ != nullptr)
        slot_pool_->reset();
    worker_set_zero(data_, 0, alloc_elems_);
    if (rank() == 0)
        worker_mem_set(data_, val_t(1.0, 0.0));
    block_end = rank() == 0 ? block_start + 1 : block_start;
}

void sv_t::resize(size_t M_new)
{
    if (M_new > MAX_M_BITS)
        abort("sv_t::resize requires M_new <= 63");

    M_ = M_new;
    const sv_layout_t layout = choose_layout(M_, nprocs());
    I = layout.I;
    J = layout.J;
    K = layout.K;

    const size_t local_bits = I + J;
    if (local_bits >= sizeof(size_t) * 8)
        abort("sv_t::resize local block size exceeds size_t width");

    const size_t local_cap = size_t(1ULL) << local_bits;
    if (alloc_elems_ < local_cap)
    {
        data_ = worker_realloc(data_, alloc_elems_, local_cap);
        alloc_elems_ = local_cap;
    }
    if (data_ == nullptr || alloc_elems_ == 0)
    {
        alloc_elems_ = std::max<size_t>(size_t(1), local_cap);
        data_ = worker_alloc(alloc_elems_);
    }

    C_ = M_new;
    block_start = static_cast<raddr_t>(rank() << (I + J));
    block_end = block_start;
    slot_pool_->configure(calc_segment_len(I));
}

void sv_t::expand()
{
    if (m_ >= M_)
        abort("expand exceeds max_bits");

    m_++;

    size_t len = 0;
    const size_t worker_id = rank();
    if (m_ <= I)
        len = (worker_id == 0) ? (size_t(1) << m_) : 0;
    else if (m_ <= I + K)
        len = (worker_id < (size_t(1) << (m_ - I))) ? (size_t(1) << I) : 0;
    else
        len = size_t(1) << (m_ - K);

    if (len > alloc_elems_)
        abort("expand exceeds allocated local block capacity");
    block_end = block_start + len;
}

val_t *sv_t::segment_ptr(raddr_t seg)
{
    if (seg < block_start)
        abort("segment_ptr below local block_start");
    const size_t idx = static_cast<size_t>(seg - block_start);
    if (idx >= alloc_elems_)
        abort("segment_ptr exceeds local block capacity");
    return data_ + idx;
}

const val_t *sv_t::raw_data() const
{
    return data_;
}

} // namespace ZXHSim
