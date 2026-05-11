import pytest
from Demo.htlp import LHTLP, MHTLP

BITS = 32
T = 20


@pytest.fixture(scope="module")
def lhtlp():
    return LHTLP(bits=BITS, T=T)


@pytest.fixture(scope="module")
def mhtlp():
    return MHTLP(bits=BITS, T=T)


# --- LHTLP ---

def test_lhtlp_pgen_returns_tuple(lhtlp):
    puzzle = lhtlp.PGen(1)
    assert isinstance(puzzle, tuple)
    assert len(puzzle) == 2


def test_lhtlp_psolve_recovers_zero(lhtlp):
    puzzle = lhtlp.PGen(0)
    assert lhtlp.PSolve(puzzle) == 0


def test_lhtlp_psolve_recovers_one(lhtlp):
    puzzle = lhtlp.PGen(1)
    assert lhtlp.PSolve(puzzle) == 1


def test_lhtlp_psolve_recovers_large_secret(lhtlp):
    s = 42
    puzzle = lhtlp.PGen(s)
    assert lhtlp.PSolve(puzzle) == s


def test_lhtlp_peval_sums_secrets(lhtlp):
    puzzles = [lhtlp.PGen(s) for s in [3, 5, 7]]
    combined = lhtlp.PEval(puzzles)
    assert lhtlp.PSolve(combined) == 15


def test_lhtlp_peval_single_puzzle_unchanged(lhtlp):
    puzzle = lhtlp.PGen(9)
    combined = lhtlp.PEval([puzzle])
    assert lhtlp.PSolve(combined) == 9


def test_lhtlp_public_params_has_required_keys(lhtlp):
    pp = lhtlp.public_params()
    assert set(pp.keys()) == {"N", "g", "h", "T"}
    assert all(isinstance(v, str) or isinstance(v, int) for v in pp.values())


# --- MHTLP ---

def test_mhtlp_pgen_returns_tuple(mhtlp):
    puzzle = mhtlp.PGen(0)
    assert isinstance(puzzle, tuple)
    assert len(puzzle) == 2


def test_mhtlp_psolve_recovers_zero(mhtlp):
    puzzle = mhtlp.PGen(0)
    assert mhtlp.PSolve(puzzle) == 0


def test_mhtlp_psolve_recovers_one(mhtlp):
    puzzle = mhtlp.PGen(1)
    assert mhtlp.PSolve(puzzle) == 1


def test_mhtlp_peval_xor_two_same_bits(mhtlp):
    # 0 XOR 0 = 0
    combined = mhtlp.PEval([mhtlp.PGen(0), mhtlp.PGen(0)])
    assert mhtlp.PSolve(combined) == 0


def test_mhtlp_peval_xor_different_bits(mhtlp):
    # 0 XOR 1 = 1
    combined = mhtlp.PEval([mhtlp.PGen(0), mhtlp.PGen(1)])
    assert mhtlp.PSolve(combined) == 1


def test_mhtlp_peval_xor_one_then_zero(mhtlp):
    # 1 XOR 0 = 1
    combined = mhtlp.PEval([mhtlp.PGen(1), mhtlp.PGen(0)])
    assert mhtlp.PSolve(combined) == 1


def test_mhtlp_peval_xor_three_bits(mhtlp):
    # 1 XOR 1 XOR 1 = 1
    combined = mhtlp.PEval([mhtlp.PGen(1), mhtlp.PGen(1), mhtlp.PGen(1)])
    assert mhtlp.PSolve(combined) == 1


def test_mhtlp_peval_xor_even_ones_is_zero(mhtlp):
    # 1 XOR 1 = 0
    combined = mhtlp.PEval([mhtlp.PGen(1), mhtlp.PGen(1)])
    assert mhtlp.PSolve(combined) == 0


def test_mhtlp_public_params_has_required_keys(mhtlp):
    pp = mhtlp.public_params()
    assert set(pp.keys()) == {"N", "g", "h", "T"}
    assert all(isinstance(v, str) or isinstance(v, int) for v in pp.values())
