from __future__ import annotations


def bit(mask: int, index: int) -> int:
    return (mask >> index) & 1


def format_mask(mask: int, width: int) -> str:
    if width <= 0:
        return ""
    return format(mask, f"0{width}b")


class AffineAddressMap:
    def __init__(self, num_qubits: int) -> None:
        self.num_qubits = num_qubits
        self.reset()

    def reset(self) -> None:
        self.width = 0
        self.rows = [0] * self.num_qubits
        self.offset_mask = 0

    def row_xor(self, dst: int, src: int) -> None:
        self.rows[dst] ^= self.rows[src]

    def append_col(self, col_mask: int) -> None:
        new_bit = 1 << self.width
        for row in range(self.num_qubits):
            if bit(col_mask, row):
                self.rows[row] |= new_bit
        self.width += 1

    def solve(self, rhs_mask: int) -> tuple[bool, int]:
        if self.width == 0:
            return (rhs_mask == 0), 0

        mat = list(self.rows)
        bvec = [bit(rhs_mask, row) for row in range(self.num_qubits)]
        pivot_for_col = [-1] * self.width
        row = 0

        for col in range(self.width):
            pivot = row
            while pivot < self.num_qubits and not bit(mat[pivot], col):
                pivot += 1
            if pivot == self.num_qubits:
                continue

            if pivot != row:
                mat[pivot], mat[row] = mat[row], mat[pivot]
                bvec[pivot], bvec[row] = bvec[row], bvec[pivot]

            for other in range(self.num_qubits):
                if other != row and bit(mat[other], col):
                    mat[other] ^= mat[row]
                    bvec[other] ^= bvec[row]

            pivot_for_col[col] = row
            row += 1
            if row == self.num_qubits:
                break

        for eqn in range(self.num_qubits):
            if mat[eqn] == 0 and bvec[eqn]:
                return False, 0

        x = 0
        for col, pivot in enumerate(pivot_for_col):
            if pivot >= 0 and bvec[pivot]:
                x |= 1 << col
        return True, x

    def requires_expansion(self, qubit: int) -> bool:
        solvable, _ = self.solve(1 << qubit)
        return not solvable

    def expand_for_qubit(self, qubit: int) -> bool:
        if not self.requires_expansion(qubit):
            return False
        self.append_col(1 << qubit)
        return True

    def x(self, q: int) -> None:
        self.offset_mask ^= 1 << q

    def cx(self, cq: int, q: int) -> None:
        self.row_xor(q, cq)
        if bit(self.offset_mask, cq):
            self.offset_mask ^= 1 << q

    def get_row(self, row: int) -> int:
        return self.rows[row]
