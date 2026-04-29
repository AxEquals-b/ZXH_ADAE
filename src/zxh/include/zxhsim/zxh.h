#pragma once

#include "zxhsim/types.h"

#include <memory>
#include <vector>

namespace ZXHSim
{

class ZXH
{
  public:
    explicit ZXH(size_t N, bool disable_x = false, bool eager_expand_all = false);
    ~ZXH();

    ZXH(const ZXH &) = delete;
    ZXH &operator=(const ZXH &) = delete;
    ZXH(ZXH &&) = delete;
    ZXH &operator=(ZXH &&) = delete;

    // Set the seed used by subsequent measure/Sampling calls.
    void set_seed(uint64_t seed);
    void clear_seed();
    void clear_gates();

    void Barrier();
    void Rz(size_t q, float_t theta);
    void CRz(size_t cq, size_t q, float_t theta);
    void CP(size_t cq, size_t q, float_t theta);
    void P(size_t q, float_t theta);
    void Z(size_t q);
    void X(size_t q);
    void CX(size_t cq, size_t q);
    void H(size_t q);
    void U3(size_t q, float_t theta, float_t lambda, float_t phi);
    void Rx(size_t q, float_t theta);

    void execute();
    void measure(size_t cnt);
    void get_results(res_t *results, size_t cnt) const;
    size_t measured_count() const;

    std::vector<res_t> Sampling(size_t shots);
    std::vector<val_t> get_state() const;
    size_t required_M() const;
    size_t num_qubits() const;

  private:
    struct impl_t;
    val_t global_phase;
    std::unique_ptr<impl_t> impl_;
};

void PrintRes(const std::vector<res_t> &res, int n);
void PrintRes(const std::vector<std::vector<bool>> &res, int n);

} // namespace ZXHSim
