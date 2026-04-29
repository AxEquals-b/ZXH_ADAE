#include "zxhsim/zxh.h"
#include "zxhsim/runtime.h"

using ZXHSim::PrintRes;
using ZXHSim::ZXH;

int main(int argc, char **argv)
{
    ZXHSim::init(&argc, &argv);

    const int n = 1000;
    const int shots = 1000;

    {
        ZXH sim(n);
        sim.H(0);
        for (int i = 1; i < n; i++)
            sim.CX(0, i);

        sim.execute();
        auto res = sim.Sampling(shots);
        PrintRes(res, n);
    }

    ZXHSim::finalize();
    return 0;
}
