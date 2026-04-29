OPENQASM 2.0;
include "qelib1.inc";

qreg q[1];
creg c[1];

u3(pi/2,0,0) q[0];
measure q -> c;
