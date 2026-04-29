#include "pybind11/complex.h"
#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "zxhsim/zxh.h"
#include "zxhsim/runtime.h"

#include <map>
#include <string>

#define STRINGIFY_IMPL(x) #x
#define STRINGIFY(x) STRINGIFY_IMPL(x)

#ifndef VERSION_INFO
#define VERSION_INFO dev
#endif

namespace py = pybind11;

namespace ZXHSim
{

std::vector<std::vector<bool>> SamplingBool(ZXH &sim, size_t shots)
{
    std::vector<res_t> raw = sim.Sampling(shots);
    const size_t n = sim.num_qubits();

    std::vector<std::vector<bool>> out(raw.size(), std::vector<bool>(n, false));
    for (size_t i = 0; i < raw.size(); i++)
    {
        for (size_t q = 0; q < n; q++)
            out[i][q] = raw[i].get_bit(q);
    }
    return out;
}

std::map<std::string, size_t> SampleCounts(ZXH &sim, size_t shots)
{
    std::vector<res_t> raw = sim.Sampling(shots);
    const size_t n = sim.num_qubits();

    std::map<std::string, size_t> counts;
    for (const auto &row : raw)
    {
        std::string bitstring;
        bitstring.reserve(n);
        for (size_t offset = 0; offset < n; offset++)
        {
            const size_t q = n - offset - 1;
            bitstring.push_back(row.get_bit(q) ? '1' : '0');
        }
        counts[bitstring]++;
    }
    return counts;
}

void MeasureDevice(ZXH &sim, size_t shots)
{
    sim.measure(shots);
}

std::vector<std::vector<bool>> GetResultsBool(ZXH &sim)
{
    const size_t shots = sim.measured_count();
    std::vector<res_t> raw(shots, res_t(sim.num_qubits(), false));
    sim.get_results(raw.data(), shots);

    const size_t n = sim.num_qubits();
    std::vector<std::vector<bool>> out(raw.size(), std::vector<bool>(n, false));
    for (size_t i = 0; i < raw.size(); i++)
    {
        for (size_t q = 0; q < n; q++)
            out[i][q] = raw[i].get_bit(q);
    }
    return out;
}

} // namespace ZXHSim

PYBIND11_MODULE(_core, m)
{
    using namespace ZXHSim;

    m.attr("__version__") = STRINGIFY(VERSION_INFO);

    m.def("PrintRes", py::overload_cast<const std::vector<std::vector<bool>> &, int>(&PrintRes), "Print Sample Results");
    m.def("init", []() { init(nullptr, nullptr); });
    m.def("finalize", &finalize);
    m.def("active", &active);
    m.def("rank", &rank);
    m.def("nprocs", &nprocs);

    py::class_<ZXH>(m, "ZXH")
        .def(py::init<size_t, bool, bool>(), py::arg("n"), py::arg("disable_x") = false,
             py::arg("eager_expand_all") = false)
        .def("set_seed", &ZXH::set_seed)
        .def("clear_seed", &ZXH::clear_seed)
        .def("clear_gates", &ZXH::clear_gates)
        .def("Barrier", &ZXH::Barrier)
        .def("Rz", &ZXH::Rz)
        .def("CRz", &ZXH::CRz)
        .def("CP", &ZXH::CP)
        .def("P", &ZXH::P)
        .def("Z", &ZXH::Z)
        .def("X", &ZXH::X)
        .def("CX", &ZXH::CX)
        .def("H", &ZXH::H)
        .def("U3", &ZXH::U3)
        .def("Rx", &ZXH::Rx)
        .def("execute", &ZXH::execute)
        .def("measure", &MeasureDevice)
        .def("get_results", &GetResultsBool)
        .def("measured_count", &ZXH::measured_count)
        .def("Sampling", &SamplingBool)
        .def("sample_counts", &SampleCounts)
        .def("get_state", &ZXH::get_state)
        .def("required_M", &ZXH::required_M)
        .def("num_qubits", &ZXH::num_qubits);
}
