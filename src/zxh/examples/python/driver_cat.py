import zxhsim

n = 1000
shots = 1000

zxhsim.init()

sim = zxhsim.ZXH(n)
sim.H(0)
for i in range(1, n):
    sim.CX(0, i)

sim.execute()
res = sim.Sampling(shots)
zxhsim.PrintRes(res, n)

zxhsim.finalize()
