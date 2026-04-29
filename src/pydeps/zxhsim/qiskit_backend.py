from __future__ import annotations

import secrets
import time
import uuid
from collections.abc import Iterable

from qiskit.circuit import Barrier, Measure, Parameter, QuantumCircuit, Reset
from qiskit.circuit.library import (
    CCXGate,
    CCZGate,
    CPhaseGate,
    CRZGate,
    CXGate,
    CZGate,
    HGate,
    IGate,
    PhaseGate,
    RXGate,
    RYGate,
    RZGate,
    RZZGate,
    SGate,
    SdgGate,
    SwapGate,
    TdgGate,
    TGate,
    U1Gate,
    U2Gate,
    U3Gate,
    UGate,
    XGate,
    ZGate,
)
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.providers import BackendV2, JobError, JobStatus, JobV1, Options
from qiskit.result import Result
from qiskit.result.models import ExperimentResult, ExperimentResultData
from qiskit.transpiler import PassManager, Target
from qiskit.transpiler.basepasses import TransformationPass
from qiskit.transpiler.preset_passmanagers.plugin import (
    PassManagerStagePlugin,
    PassManagerStagePluginManager,
)

from . import _core
from .circ_optimizer import optimize_circuit
from .qasm import _ZXH_SUPPORTED_GATES, load_circuit_transpiled


ZXH_SCHEDULING_PLUGIN_NAME = "zxh_post"

_THETA = Parameter("theta")
_PHI = Parameter("phi")
_LAM = Parameter("lam")

_INSTRUCTION_FACTORIES = {
    "barrier": lambda: Barrier(1),
    "measure": Measure,
    "reset": Reset,
    "id": IGate,
    "x": XGate,
    "cx": CXGate,
    "swap": SwapGate,
    "h": HGate,
    "z": ZGate,
    "cz": CZGate,
    "rz": lambda: RZGate(_THETA),
    "rx": lambda: RXGate(_THETA),
    "ry": lambda: RYGate(_THETA),
    "p": lambda: PhaseGate(_THETA),
    "u1": lambda: U1Gate(_THETA),
    "u2": lambda: U2Gate(_PHI, _LAM),
    "s": SGate,
    "sdg": SdgGate,
    "t": TGate,
    "tdg": TdgGate,
    "u": lambda: UGate(_THETA, _PHI, _LAM),
    "u3": lambda: U3Gate(_THETA, _PHI, _LAM),
    "rzz": lambda: RZZGate(_THETA),
    "cp": lambda: CPhaseGate(_THETA),
    "crz": lambda: CRZGate(_THETA),
    "ccz": CCZGate,
    "ccx": CCXGate,
}


def _build_target() -> Target:
    target = Target(num_qubits=None)
    for gate_name in _ZXH_SUPPORTED_GATES:
        factory = _INSTRUCTION_FACTORIES.get(gate_name)
        if factory is None:
            continue
        instruction = factory()
        if instruction.name in target.operation_names:
            continue
        target.add_instruction(instruction)
    return target


def _normalize_circuit(circuit: QuantumCircuit) -> QuantumCircuit:
    if circuit.qregs and (circuit.num_clbits == 0 or circuit.cregs):
        return circuit

    normalized = QuantumCircuit(circuit.num_qubits, circuit.num_clbits, name=circuit.name)
    normalized.global_phase = circuit.global_phase
    normalized.metadata = dict(circuit.metadata or {})

    qubit_index = {bit: i for i, bit in enumerate(circuit.qubits)}
    clbit_index = {bit: i for i, bit in enumerate(circuit.clbits)}

    for instruction in circuit.data:
        normalized.append(
            instruction.operation,
            [normalized.qubits[qubit_index[bit]] for bit in instruction.qubits],
            [normalized.clbits[clbit_index[bit]] for bit in instruction.clbits],
        )
    return normalized


class ZXHOptimizePass(TransformationPass):
    def __init__(self, *, optimize_level: int = 2) -> None:
        super().__init__()
        self._optimize_level = optimize_level

    def run(self, dag):
        optimized = optimize_circuit(
            dag_to_circuit(dag),
            optimize_level=self._optimize_level,
            allowed_gates=tuple(_ZXH_SUPPORTED_GATES),
        )
        return circuit_to_dag(_normalize_circuit(optimized))


class ZXHPostSchedulingPlugin(PassManagerStagePlugin):
    def pass_manager(self, pass_manager_config, optimization_level=None) -> PassManager | None:
        plugin_manager = PassManagerStagePluginManager()
        base = plugin_manager.get_passmanager_stage(
            "scheduling",
            "default",
            pass_manager_config,
            optimization_level,
        )
        if base is None:
            base = PassManager()
        base.append(ZXHOptimizePass(optimize_level=2))
        return base


class ZXHJob(JobV1):
    __circuits: list[QuantumCircuit]
    __options: dict[str, object]
    __result: Result | None

    def __init__(
        self,
        backend: "ZXHQiskitBackend",
        circuits: list[QuantumCircuit],
        options: dict[str, object],
    ) -> None:
        super().__init__(backend=backend, job_id=str(uuid.uuid4()))
        self.__circuits = circuits
        self.__options = options
        self.__result = None
        self._qobj_id = str(uuid.uuid4())

    def submit(self) -> None:
        if self.__result is not None:
            raise JobError("Job already submitted")
        self.__result = self._run_job()

    def status(self) -> JobStatus:
        if self.__result is None:
            return JobStatus.INITIALIZING
        return JobStatus.DONE

    def result(self) -> Result:
        if self.__result is None:
            raise JobError("Job not submitted")
        return self.__result

    def _run_job(self) -> Result:
        if not _active():
            _init()

        shots = int(self.__options.get("shots", 1))
        seed_simulator = self.__options.get("seed_simulator")

        results: list[ExperimentResult] = []
        backend = self.backend()
        for circuit in self.__circuits:
            counts, sample_time = backend._run_circuit(
                circuit,
                shots=shots,
                seed_simulator=seed_simulator,
            )
            results.append(
                ExperimentResult(
                    shots=shots,
                    success=True,
                    data=ExperimentResultData(counts=counts),
                    metadata={"sample_time": sample_time},
                    seed=self.__options.get("seed_simulator"),
                )
            )

        return Result(
            backend_name=self.backend().name,
            backend_version=self.backend().backend_version,
            job_id=self.job_id(),
            qobj_id=self._qobj_id,
            success=True,
            results=results,
        )


class ZXHQiskitBackend(BackendV2):
    def __init__(
        self,
        *,
        disable_x: bool = False,
        eager_expand_all: bool = False,
    ) -> None:
        super().__init__(
            name="zxh",
            description="ZXH Qiskit Backend",
            backend_version=_core.__version__,
        )
        self._target = _build_target()
        self._disable_x = disable_x
        self._eager_expand_all = eager_expand_all
        self._sim: ZXH | None = None

    @property
    def target(self) -> Target:
        return self._target

    @property
    def max_circuits(self) -> None:
        return None

    @property
    def operation_names(self) -> list[str]:
        return sorted(_ZXH_SUPPORTED_GATES)

    @classmethod
    def _default_options(cls) -> Options:
        return Options(
            shots=1,
            seed_simulator=None,
        )

    def get_scheduling_stage_plugin(self) -> str:
        return ZXH_SCHEDULING_PLUGIN_NAME

    def _get_or_create_sim(self, num_qubits: int) -> ZXH:
        if self._sim is None:
            self._sim = ZXH(
                num_qubits,
                disable_x=self._disable_x,
                eager_expand_all=self._eager_expand_all,
            )
            return self._sim

        if self._sim.num_qubits() != num_qubits:
            raise JobError(
                "ZXH backend caches a single simulator instance. "
                f"Expected num_qubits={self._sim.num_qubits()}, got num_qubits={num_qubits}."
            )

        return self._sim

    def _run_circuit(
        self,
        circuit: QuantumCircuit,
        *,
        shots: int,
        seed_simulator,
    ) -> tuple[dict[str, int], float]:
        sim = self._get_or_create_sim(circuit.num_qubits)
        if seed_simulator is None:
            clear_seed = getattr(sim, "clear_seed", None)
            if clear_seed is not None:
                clear_seed()
            else:
                sim.set_seed(secrets.randbits(64))
        else:
            sim.set_seed(int(seed_simulator))
        sim.clear_gates()
        load_circuit_transpiled(sim, circuit)
        sim.execute()
        sample_t0 = time.perf_counter()
        counts = {
            str(bitstring): int(count)
            for bitstring, count in sim.sample_counts(shots).items()
        }
        return counts, time.perf_counter() - sample_t0

    def run(self, run_input, **options) -> ZXHJob:
        invalid_run_options = {"disable_x", "eager_expand_all"} & set(options)
        if invalid_run_options:
            invalid = ", ".join(sorted(invalid_run_options))
            raise JobError(
                f"{invalid} is a backend construction parameter for ZXH, not a run() option."
            )
        circuits = _coerce_circuits(run_input)
        job = ZXHJob(self, circuits, {**self.options, **options})
        job.submit()
        return job


def _coerce_circuits(run_input) -> list[QuantumCircuit]:
    if isinstance(run_input, QuantumCircuit):
        return [_normalize_circuit(run_input)]
    if isinstance(run_input, Iterable):
        circuits = [item for item in run_input]
        if all(isinstance(item, QuantumCircuit) for item in circuits):
            return [_normalize_circuit(item) for item in circuits]
    raise TypeError(f"Unsupported run_input type for ZXH backend: {type(run_input)!r}")


def make_zxh_backend(
    *,
    disable_x: bool = False,
    eager_expand_all: bool = False,
) -> ZXHQiskitBackend:
    return ZXHQiskitBackend(
        disable_x=disable_x,
        eager_expand_all=eager_expand_all,
    )


ZXH = _core.ZXH


def _init() -> None:
    fn = getattr(_core, "init", None)
    if fn is not None:
        fn()


def _active() -> bool:
    fn = getattr(_core, "active", None)
    if fn is not None:
        return bool(fn())
    return False
