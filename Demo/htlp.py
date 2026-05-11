import time
import random
from sympy import isprime, randprime


def generate_strong_prime(bits):
    while True:
        p_prime = randprime(2 ** (bits - 2), 2 ** (bits - 1))
        p = 2 * p_prime + 1
        if isprime(p):
            return p, p_prime


def calibrate_T(target_seconds, bits=128):
    """Return T (number of squarings) calibrated to ~target_seconds on this CPU."""
    print("Calibrating CPU speed... (1 second)")
    test_N = generate_strong_prime(bits)[0] * generate_strong_prime(bits)[0]
    test_val = random.randrange(2, test_N)
    squarings = 0
    start = time.time()
    while time.time() - start < 1.0:
        test_val = pow(test_val, 2, test_N)
        squarings += 1
    return squarings * target_seconds


class LHTLP:
    """Linearly Homomorphic Time-Lock Puzzle (Paillier-based, Section 4.1)."""

    def __init__(self, bits, T):
        print("Generating LHTLP parameters...")
        p, _ = generate_strong_prime(bits)
        q, _ = generate_strong_prime(bits)
        self.N = p * q
        self.N2 = self.N ** 2
        self.T = T
        order_JN = ((p - 1) * (q - 1)) // 2
        while True:
            g_tilde = random.randrange(2, self.N)
            self.g = (-pow(g_tilde, 2, self.N)) % self.N
            if self.g > 1:
                break
        self.h = pow(self.g, pow(2, self.T, order_JN), self.N)
        print("LHTLP ready.")

    def public_params(self):
        return {"N": str(self.N), "g": str(self.g), "h": str(self.h), "T": self.T}

    def PGen(self, s):
        r = random.randrange(1, self.N2)
        u = pow(self.g, r, self.N)
        v = (pow(self.h, r * self.N, self.N2) * pow(1 + self.N, s, self.N2)) % self.N2
        return (u, v)

    def PEval(self, puzzles):
        u_tilde, v_tilde = 1, 1
        for u, v in puzzles:
            u_tilde = (u_tilde * u) % self.N
            v_tilde = (v_tilde * v) % self.N2
        return (u_tilde, v_tilde)

    def PSolve(self, puzzle, progress_cb=None):
        u, v = puzzle
        w = u
        update_interval = max(1, self.T // 100)
        for i in range(self.T):
            w = pow(w, 2, self.N)
            if progress_cb and i % update_interval == 0:
                progress_cb(i + update_interval)
        if progress_cb:
            progress_cb(self.T)
        w_N_inv = pow(w, self.N, self.N2)
        w_N_inv = pow(w_N_inv, -1, self.N2)
        return (((v * w_N_inv) % self.N2) - 1) // self.N


class MHTLP:
    """Multiplicatively Homomorphic Time-Lock Puzzle — XOR variant (Section 4.2).

    Encoding: bit 0 -> s = +1, bit 1 -> s = N-1 (= -1 mod N).
    PEval multiplies secrets, so the combined puzzle encodes XOR of all bits.
    Requires Blum integer N (p ≡ q ≡ 3 mod 4).
    Safe primes p = 2p'+1 with odd p' always satisfy p ≡ 3 mod 4, so the
    same generate_strong_prime() function works without modification.
    """

    def __init__(self, bits, T):
        print("Generating MHTLP parameters...")
        p, _ = generate_strong_prime(bits)
        q, _ = generate_strong_prime(bits)
        self.N = p * q
        self.T = T
        order_JN = ((p - 1) * (q - 1)) // 2
        while True:
            g_tilde = random.randrange(2, self.N)
            self.g = (-pow(g_tilde, 2, self.N)) % self.N
            if self.g > 1:
                break
        self.h = pow(self.g, pow(2, self.T, order_JN), self.N)
        print("MHTLP ready.")

    def public_params(self):
        return {"N": str(self.N), "g": str(self.g), "h": str(self.h), "T": self.T}

    def PGen(self, bit):
        """bit ∈ {0, 1}. Encodes as s = +1 (Tails) or N-1 (Heads)."""
        s = 1 if bit == 0 else self.N - 1
        r = random.randrange(1, self.N * self.N)
        u = pow(self.g, r, self.N)
        v = (pow(self.h, r, self.N) * s) % self.N
        return (u, v)

    def PEval(self, puzzles):
        u_tilde, v_tilde = 1, 1
        for u, v in puzzles:
            u_tilde = (u_tilde * u) % self.N
            v_tilde = (v_tilde * v) % self.N
        return (u_tilde, v_tilde)

    def PSolve(self, puzzle, progress_cb=None):
        """Returns 0 (Tails) or 1 (Heads)."""
        u, v = puzzle
        w = u
        update_interval = max(1, self.T // 100)
        for i in range(self.T):
            w = pow(w, 2, self.N)
            if progress_cb and i % update_interval == 0:
                progress_cb(i + update_interval)
        if progress_cb:
            progress_cb(self.T)
        w_inv = pow(w, -1, self.N)
        s = (v * w_inv) % self.N
        return 0 if s == 1 else 1
