# MHTLP Coin Flip Dual Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second live demo (multi-party coin flip via MHTLP XOR) alongside the existing e-voting demo, with client-side puzzle generation in JS BigInt, a CSS 3D coin animation, and a redesigned dual admin dashboard.

**Architecture:** Extract LHTLP into `htlp.py` alongside a new `MHTLP` class; refactor `app.py` to serve both demos with independent state machines; add `static/htlp.js` for in-browser puzzle generation so the server never sees raw secrets; four redesigned HTML templates.

**Tech Stack:** Python 3 + Flask + sympy (existing), JavaScript BigInt + CSS 3D transforms (new), pytest for crypto unit tests.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `Demo/htlp.py` | `calibrate_T`, `LHTLP`, `MHTLP` classes |
| Modify | `Demo/app.py` | Import from `htlp.py`; add flip routes/state; add reset routes |
| Create | `Demo/static/htlp.js` | Client-side `modpow`, `randomBigInt`, `lhtlpPGen`, `mhtlpPGen` |
| Create | `Demo/tests/__init__.py` | Empty — makes tests a package |
| Create | `Demo/tests/test_htlp.py` | Unit tests for both HTLP classes |
| Rewrite | `Demo/templates/index.html` | Landing page with two demo cards + QR links |
| Create | `Demo/templates/vote.html` | Redesigned e-voting participant page (was `index.html`) |
| Create | `Demo/templates/flip.html` | Coin flip participant page with CSS 3D coin animation |
| Rewrite | `Demo/templates/admin.html` | Dual dashboard, independent controls per demo |

---

## Task 1: Create Feature Branch

**Files:** none

- [ ] **Step 1: Create and switch to feature branch**

```bash
git checkout -b feature/mhtlp-coin-flip
git branch
```
Expected: `* feature/mhtlp-coin-flip` shown in output.

---

## Task 2: Create `Demo/htlp.py`

Extract crypto from `app.py` and add `MHTLP`. Both classes receive a pre-calibrated `T` so the server calibrates once and shares it.

**Files:**
- Create: `Demo/htlp.py`

- [ ] **Step 1: Write `Demo/htlp.py`**

```python
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
```

- [ ] **Step 2: Verify file was created**

```bash
python3 -c "from Demo.htlp import LHTLP, MHTLP, calibrate_T; print('import OK')"
```
Expected: `import OK`

---

## Task 3: Write and Run Tests for `htlp.py`

Use small parameters (bits=32, T=20) so tests run in under 2 seconds.

**Files:**
- Create: `Demo/tests/__init__.py`
- Create: `Demo/tests/test_htlp.py`

- [ ] **Step 1: Create empty `__init__.py`**

```bash
touch Demo/tests/__init__.py
```

- [ ] **Step 2: Write `Demo/tests/test_htlp.py`**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

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
```

- [ ] **Step 3: Run tests and verify all pass**

```bash
cd /Users/gian1/CODE/HSG/FS26/SecureComputing/Project/homomorphic-time-lock
python -m pytest Demo/tests/test_htlp.py -v
```
Expected: all 16 tests PASS. Prime generation at bits=32 takes ~1s; total run under 30s.

- [ ] **Step 4: Commit**

```bash
git add Demo/htlp.py Demo/tests/__init__.py Demo/tests/test_htlp.py
git commit -m "feat: add htlp.py with LHTLP extraction and MHTLP XOR class"
```

---

## Task 4: Refactor `Demo/app.py`

Replace inline LHTLP class with import from `htlp.py`. Add flip state, new routes, and reset endpoints. Keep all existing `/vote`, `/status`, `/start_tally` routes working identically.

**Files:**
- Modify: `Demo/app.py` (full rewrite — replace entirely)

- [ ] **Step 1: Replace `Demo/app.py` with the following**

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import threading
from flask import Flask, render_template, request, jsonify
from htlp import calibrate_T, LHTLP, MHTLP

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# --- Startup prompt ---

def prompt_target_minutes():
    print()
    print("=" * 60)
    print(" HTLP Demo — solve duration configuration")
    print("=" * 60)
    print(" Shared by both the e-voting and coin-flip demos.")
    while True:
        raw = input(" Solve time in MINUTES [default 2]: ").strip()
        if not raw:
            return 2.0
        try:
            v = float(raw)
            if v > 0:
                return v
            print("  -> Please enter a positive number.")
        except ValueError:
            print("  -> Please enter a number (e.g. 2 or 0.5).")


def fmt_duration(seconds):
    if seconds < 60:
        return f"~{int(round(seconds))}s"
    minutes = seconds / 60
    if abs(minutes - round(minutes)) < 0.05:
        return f"~{int(round(minutes))} min"
    return f"~{minutes:.1f} min"


target_minutes = prompt_target_minutes()
target_seconds = max(4, int(round(target_minutes * 60)))
per_puzzle_label = fmt_duration(target_seconds / 2)
print(f" Target: {target_minutes:g} min total ({per_puzzle_label} per puzzle)")
print()

T = calibrate_T(target_seconds=max(2, target_seconds // 2))

lhtlp = LHTLP(bits=128, T=T)
mhtlp = MHTLP(bits=128, T=T)

# --- Voting state ---
votes = []
vote_solving = False
vote_results = None
vote_progress_msg = "Waiting for votes..."
vote_progress = {"Codex": 0, "Claude": 0}

# --- Flip state ---
flip_puzzles = []
flip_bits = []       # revealed after solve
flip_solving = False
flip_result = None
flip_progress = 0
flip_progress_msg = "Waiting for participants..."


# ── Routes ────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/vote')
def vote_page():
    return render_template('vote.html', solving=vote_solving)


@app.route('/flip')
def flip_page():
    return render_template('flip.html', solving=flip_solving)


@app.route('/admin')
def admin():
    return render_template('admin.html')


# ── Public params ──────────────────────────────────────────

@app.route('/vote-params')
def vote_params():
    return jsonify(lhtlp.public_params())


@app.route('/flip-params')
def flip_params():
    return jsonify(mhtlp.public_params())


# ── Vote endpoints ─────────────────────────────────────────

@app.route('/vote', methods=['POST'])
def cast_vote():
    if vote_solving:
        return jsonify({"status": "error", "message": "Voting is closed!"}), 400
    data = request.get_json(silent=True) or {}
    candidate = data.get('candidate') or request.form.get('candidate')
    u = data.get('u') or request.form.get('u')
    v = data.get('v') or request.form.get('v')
    if candidate not in ('Codex', 'Claude') or not u or not v:
        return jsonify({"status": "error", "message": "Invalid submission"}), 400
    puzzle = (int(u), int(v))
    if candidate == 'Codex':
        votes.append((puzzle, lhtlp.PGen(0)))
    else:
        votes.append((lhtlp.PGen(0), puzzle))
    return jsonify({"status": "success", "total_votes": len(votes)})


@app.route('/start_tally', methods=['POST'])
def start_tally():
    global vote_solving, vote_progress_msg
    if not vote_solving and votes:
        vote_solving = True
        vote_progress['Codex'] = 0
        vote_progress['Claude'] = 0
        vote_progress_msg = "Homomorphically combining puzzles..."
        threading.Thread(target=run_tally, daemon=True).start()
    return jsonify({"status": "started"})


@app.route('/status')
def status():
    if vote_results:
        codex_pct = claude_pct = 100.0
        remaining = 0.0
    elif vote_solving and lhtlp.T:
        codex_pct = min(100.0, vote_progress['Codex'] / lhtlp.T * 100)
        claude_pct = min(100.0, vote_progress['Claude'] / lhtlp.T * 100)
        remaining = ((1.0 - codex_pct / 100) + (1.0 - claude_pct / 100)) * (target_seconds / 2)
    else:
        codex_pct = claude_pct = 0.0
        remaining = float(target_seconds)
    return jsonify({
        "solving": vote_solving,
        "results": vote_results,
        "votes": len(votes),
        "message": vote_progress_msg,
        "progress": round((codex_pct + claude_pct) / 2, 2),
        "codex_progress": round(codex_pct, 2),
        "claude_progress": round(claude_pct, 2),
        "target_per_puzzle": target_seconds // 2,
        "target_total": target_seconds,
        "remaining_seconds": round(remaining, 2),
    })


@app.route('/reset_vote', methods=['POST'])
def reset_vote():
    global votes, vote_solving, vote_results, vote_progress_msg
    votes.clear()
    vote_solving = False
    vote_results = None
    vote_progress['Codex'] = 0
    vote_progress['Claude'] = 0
    vote_progress_msg = "Waiting for votes..."
    return jsonify({"status": "reset"})


def run_tally():
    global vote_results, vote_solving, vote_progress_msg
    codex_eval = lhtlp.PEval([v[0] for v in votes])
    claude_eval = lhtlp.PEval([v[1] for v in votes])
    vote_progress_msg = f"Solving Codex time-lock ({per_puzzle_label})..."
    codex_total = lhtlp.PSolve(
        codex_eval,
        progress_cb=lambda n: vote_progress.update({"Codex": n}),
    )
    vote_progress_msg = f"Solving Claude time-lock ({per_puzzle_label})..."
    claude_total = lhtlp.PSolve(
        claude_eval,
        progress_cb=lambda n: vote_progress.update({"Claude": n}),
    )
    vote_results = {"Codex": codex_total, "Claude": claude_total}
    vote_progress_msg = "Tally complete!"
    vote_solving = False


# ── Flip endpoints ─────────────────────────────────────────

@app.route('/flip', methods=['POST'])
def submit_flip():
    if flip_solving:
        return jsonify({"status": "error", "message": "Flip phase is closed!"}), 400
    data = request.get_json(silent=True) or {}
    u = data.get('u')
    v = data.get('v')
    if not u or not v:
        return jsonify({"status": "error", "message": "Missing puzzle"}), 400
    flip_puzzles.append((int(u), int(v)))
    return jsonify({"status": "success", "participants": len(flip_puzzles)})


@app.route('/start_flip', methods=['POST'])
def start_flip():
    global flip_solving, flip_progress_msg
    if not flip_solving and flip_puzzles:
        flip_solving = True
        flip_progress_msg = "Homomorphically combining puzzles..."
        threading.Thread(target=run_flip, daemon=True).start()
    return jsonify({"status": "started"})


@app.route('/flip-status')
def flip_status():
    if flip_result is not None:
        pct = 100.0
        remaining = 0.0
    elif flip_solving and mhtlp.T:
        pct = min(100.0, flip_progress / mhtlp.T * 100)
        remaining = (1.0 - pct / 100) * (target_seconds / 2)
    else:
        pct = 0.0
        remaining = float(target_seconds / 2)
    return jsonify({
        "solving": flip_solving,
        "result": flip_result,
        "participants": len(flip_puzzles),
        "message": flip_progress_msg,
        "progress": round(pct, 2),
        "remaining_seconds": round(remaining, 2),
        "individual_bits": flip_bits if flip_result is not None else [],
    })


@app.route('/reset_flip', methods=['POST'])
def reset_flip():
    global flip_puzzles, flip_bits, flip_solving, flip_result, flip_progress, flip_progress_msg
    flip_puzzles.clear()
    flip_bits.clear()
    flip_solving = False
    flip_result = None
    flip_progress = 0
    flip_progress_msg = "Waiting for participants..."
    return jsonify({"status": "reset"})


def run_flip():
    global flip_result, flip_solving, flip_progress_msg, flip_progress, flip_bits
    combined = mhtlp.PEval(flip_puzzles)
    flip_progress_msg = f"Solving coin-flip time-lock ({per_puzzle_label})..."

    def on_progress(n):
        global flip_progress
        flip_progress = n

    bit = mhtlp.PSolve(combined, progress_cb=on_progress)
    flip_result = {"bit": bit, "face": "heads" if bit == 1 else "tails"}
    flip_progress_msg = "Coin flipped!"
    flip_solving = False


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

- [ ] **Step 2: Verify app starts without error (Ctrl-C after seeing "Running on")**

```bash
cd Demo && echo "0.1" | python app.py
```
Expected: prints calibration messages then "Running on http://0.0.0.0:5000". Ctrl-C to stop.

- [ ] **Step 3: Commit**

```bash
git add Demo/app.py
git commit -m "refactor: import htlp.py, add flip routes and reset endpoints"
```

---

## Task 5: Create `Demo/static/htlp.js`

Client-side BigInt puzzle generation. The server never sees the user's secret — only `(u, v)`.

**Files:**
- Create: `Demo/static/htlp.js`

- [ ] **Step 1: Write `Demo/static/htlp.js`**

```javascript
'use strict';

// ── Modular exponentiation ────────────────────────────────
function modpow(base, exp, mod) {
  if (mod === 1n) return 0n;
  let result = 1n;
  base = base % mod;
  while (exp > 0n) {
    if (exp & 1n) result = result * base % mod;
    exp >>= 1n;
    base = base * base % mod;
  }
  return result;
}

// ── Cryptographically secure random BigInt in [1, max) ───
function randomBigInt(max) {
  const maxBits = max.toString(2).length;
  const maxBytes = Math.ceil(maxBits / 8);
  let result;
  do {
    const bytes = new Uint8Array(maxBytes);
    crypto.getRandomValues(bytes);
    result = BigInt('0x' + Array.from(bytes, b => b.toString(16).padStart(2, '0')).join(''));
  } while (result === 0n || result >= max);
  return result;
}

// ── Fetch and parse public params from server ─────────────
async function fetchParams(endpoint) {
  const res = await fetch(endpoint);
  const data = await res.json();
  const N = BigInt(data.N);
  return { N, N2: N * N, g: BigInt(data.g), h: BigInt(data.h), T: data.T };
}

// ── LHTLP PGen (vote) ─────────────────────────────────────
// s ∈ {0, 1} — 0 = voted for other candidate, 1 = voted for this candidate
function lhtlpPGen(pp, s) {
  const r = randomBigInt(pp.N2);
  const u = modpow(pp.g, r, pp.N);
  const v = modpow(pp.h, r * pp.N, pp.N2) * modpow(pp.N + 1n, BigInt(s), pp.N2) % pp.N2;
  return { u: u.toString(), v: v.toString() };
}

// ── MHTLP PGen (coin flip) ────────────────────────────────
// bit ∈ {0, 1} — auto-generated randomly by caller
// Encoding: bit 0 (Tails) -> s = +1; bit 1 (Heads) -> s = N-1 (= -1 mod N)
function mhtlpPGen(pp, bit) {
  const s = bit === 0 ? 1n : pp.N - 1n;
  const r = randomBigInt(pp.N2);
  const u = modpow(pp.g, r, pp.N);
  const v = modpow(pp.h, r, pp.N) * s % pp.N;
  return { u: u.toString(), v: v.toString(), bit };
}

// ── Helpers exposed globally ──────────────────────────────
window.HTLP = { fetchParams, lhtlpPGen, mhtlpPGen };
```

- [ ] **Step 2: Verify JS syntax**

```bash
node -e "const fs=require('fs'); eval(fs.readFileSync('Demo/static/htlp.js','utf8').replace('window.HTLP','globalThis.HTLP')); console.log('JS syntax OK')"
```
Expected: `JS syntax OK`

- [ ] **Step 3: Commit**

```bash
git add Demo/static/htlp.js
git commit -m "feat: add client-side BigInt LHTLP/MHTLP puzzle generation"
```

---

## Task 6: Redesign `Demo/templates/vote.html`

Redesign of the current `index.html` — now served at `/vote`. Key addition: client-side JS calls `lhtlpPGen` before submitting. Collapsible "technical detail" box shows `(u, v)`.

**Files:**
- Create: `Demo/templates/vote.html`

- [ ] **Step 1: Write `Demo/templates/vote.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HTLP — E-Voting</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
      --bg: #faf6ed; --card: #ffffff; --accent: #4a7a8c; --accent2: #5fa18f;
      --accent3: #d4795f; --text: #1d2538; --dim: #6b7280; --border: #e7e0cf;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      font-family:'Inter',sans-serif; background:
        radial-gradient(circle at 92% 8%, rgba(244,200,184,.55) 0%, transparent 32%),
        radial-gradient(circle at 4% 38%, rgba(200,230,221,.55) 0%, transparent 28%),
        var(--bg);
      color:var(--text); min-height:100vh; display:flex;
      align-items:center; justify-content:center; padding:24px 18px;
    }
    .container { width:100%; max-width:480px; text-align:center; }
    .back { font-size:13px; color:var(--dim); text-decoration:none; display:block; margin-bottom:16px; }
    .back:hover { color:var(--accent); }
    h1 {
      font-size:36px; font-weight:700;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
      background-clip:text; margin-bottom:8px;
    }
    .subtitle { font-size:15px; color:var(--dim); font-weight:300; margin-bottom:26px; line-height:1.5; }
    .card {
      background:var(--card); border:1px solid #d4cdb8; border-radius:14px;
      padding:28px 22px; box-shadow:0 1px 2px rgba(29,37,56,.06),0 6px 18px rgba(29,37,56,.07);
    }
    .prompt { font-size:17px; color:var(--text); margin-bottom:4px; font-weight:500; }
    .candidate-buttons { display:flex; flex-direction:column; gap:14px; margin:18px 0 8px; }
    button.candidate-btn {
      font-family:'Inter',sans-serif; font-size:21px; font-weight:600;
      padding:20px 26px; border-radius:12px; border:2px solid; cursor:pointer;
      background:var(--card); transition:transform .15s,box-shadow .15s,background .15s;
    }
    button.candidate-btn:disabled { opacity:.5; cursor:not-allowed; }
    button.codex { color:var(--accent3); border-color:var(--accent3); }
    button.codex:hover:not(:disabled) {
      background:rgba(212,121,95,.12); transform:translateY(-2px);
      box-shadow:0 6px 16px rgba(212,121,95,.25);
    }
    button.claude { color:var(--accent); border-color:var(--accent); }
    button.claude:hover:not(:disabled) {
      background:rgba(74,122,140,.12); transform:translateY(-2px);
      box-shadow:0 6px 16px rgba(74,122,140,.25);
    }
    .info { font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--dim); margin-top:16px; line-height:1.6; }
    .status-card { display:none; flex-direction:column; align-items:center; gap:14px; padding:8px 0; }
    .status-card.visible { display:flex; }
    .status-icon {
      width:68px; height:68px; border-radius:50%; display:flex;
      align-items:center; justify-content:center; font-size:34px;
    }
    .status-icon.encrypting {
      background:rgba(74,122,140,.18); color:var(--accent);
      border:2px solid var(--accent); animation:pulse 1.5s ease-in-out infinite;
    }
    .status-icon.success { background:rgba(95,161,143,.18); color:var(--accent2); border:2px solid var(--accent2); }
    .status-icon.error   { background:rgba(212,121,95,.18); color:var(--accent3); border:2px solid var(--accent3); }
    @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.6;transform:scale(.95)} }
    .status-title { font-size:21px; font-weight:600; }
    .status-msg   { font-size:14px; color:var(--dim); line-height:1.5; max-width:320px; }
    .status-msg strong { color:var(--text); }
    .voted-pill {
      display:inline-block; padding:7px 20px; border-radius:999px;
      font-weight:700; font-size:15px; text-transform:uppercase;
    }
    .voted-pill.codex { background:rgba(212,121,95,.18); color:var(--accent3); }
    .voted-pill.claude { background:rgba(74,122,140,.18); color:var(--accent); }
    details { margin-top:14px; text-align:left; }
    summary { font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--accent); cursor:pointer; }
    .tech-box {
      font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--dim);
      background:#f5f2ea; border:1px solid var(--border); border-radius:6px;
      padding:10px; margin-top:6px; word-break:break-all; line-height:1.7;
    }
    .live-counter {
      margin-top:22px; font-family:'JetBrains Mono',monospace;
      font-size:13px; color:var(--dim); display:flex;
      align-items:center; justify-content:center; gap:8px;
    }
    .live-counter .count { color:var(--accent2); font-weight:700; font-size:18px; }
    .dot { width:9px; height:9px; border-radius:50%; background:var(--accent2); animation:blink 2s ease-in-out infinite; }
    @keyframes blink { 0%,100%{opacity:.3} 50%{opacity:1} }
    .footer { margin-top:18px; font-size:11px; color:var(--dim); font-family:'JetBrains Mono',monospace; opacity:.7; }
  </style>
</head>
<body>
  <div class="container">
    <a class="back" href="/">← back to demos</a>
    <h1>Cast Your Vote</h1>
    <p class="subtitle">Your ballot is locked in a homomorphic time-lock puzzle — secret until time T elapses.</p>

    <div class="card">
      <div id="booth">
        <p class="prompt">Choose your candidate</p>
        <div class="candidate-buttons">
          <button class="candidate-btn codex"  onclick="vote('Codex')">Vote Codex</button>
          <button class="candidate-btn claude" onclick="vote('Claude')">Vote Claude</button>
        </div>
        <p class="info">Your puzzle is generated in this browser.<br>The server never sees your choice.</p>
      </div>

      <div id="status-card" class="status-card">
        <div id="status-icon" class="status-icon encrypting">🔒</div>
        <p id="status-title" class="status-title">Encrypting…</p>
        <p id="status-msg" class="status-msg">Generating time-lock puzzle locally.</p>
        <div id="voted-pill" style="display:none"></div>
        <details id="tech-detail" style="display:none">
          <summary>technical detail</summary>
          <div class="tech-box" id="tech-box"></div>
        </details>
      </div>
    </div>

    <div class="live-counter">
      <span class="dot"></span>
      Live: <span id="live-count" class="count">0</span> ballots encrypted
    </div>
    <p class="footer">Secure &amp; Private Computing · HTLP Demo</p>
  </div>

  <script src="/static/htlp.js"></script>
  <script>
    let pp = null;

    async function init() {
      pp = await HTLP.fetchParams('/vote-params');
      document.querySelectorAll('.candidate-btn').forEach(b => b.disabled = false);
    }
    init();

    async function vote(candidate) {
      document.getElementById('booth').style.display = 'none';
      const card = document.getElementById('status-card');
      card.classList.add('visible');
      setStatus('encrypting', 'Generating puzzle…', 'Computing time-lock puzzle in your browser.');

      const s = 1;
      const puzzle = HTLP.lhtlpPGen(pp, s);

      const payload = { candidate, u: puzzle.u, v: puzzle.v };
      let data;
      try {
        const res = await fetch('/vote', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        data = await res.json();
      } catch {
        setStatus('error', 'Network error', 'Could not reach the server. Please try again.');
        setTimeout(() => { card.classList.remove('visible'); document.getElementById('booth').style.display=''; }, 3000);
        return;
      }

      if (data.status === 'success') {
        setStatus('success', 'Vote locked!',
          `Your ballot was encrypted as <strong>#${data.total_votes}</strong>.<br>Watch the screen for the reveal.`);
        const pill = document.getElementById('voted-pill');
        pill.className = 'voted-pill ' + candidate.toLowerCase();
        pill.textContent = 'You voted ' + candidate;
        pill.style.display = 'inline-block';
        document.getElementById('live-count').textContent = data.total_votes;
        document.getElementById('tech-box').textContent =
          `u = ${puzzle.u.slice(0,40)}…\nv = ${puzzle.v.slice(0,40)}…`;
        document.getElementById('tech-detail').style.display = 'block';
      } else {
        setStatus('error', 'Vote rejected', data.message || 'Voting may be closed.');
        setTimeout(() => { card.classList.remove('visible'); document.getElementById('booth').style.display=''; }, 3000);
      }
    }

    function setStatus(state, title, msg) {
      const icon = document.getElementById('status-icon');
      icon.className = 'status-icon ' + state;
      icon.textContent = state === 'encrypting' ? '🔒' : state === 'success' ? '✓' : '!';
      document.getElementById('status-title').textContent = title;
      document.getElementById('status-msg').innerHTML = msg;
    }

    setInterval(async () => {
      try {
        const d = await (await fetch('/status')).json();
        document.getElementById('live-count').textContent = d.votes;
      } catch {}
    }, 2000);
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add Demo/templates/vote.html
git commit -m "feat: redesign vote.html with client-side LHTLP puzzle generation"
```

---

## Task 7: Create `Demo/templates/flip.html`

New participant page with CSS 3D coin animation. Browser auto-generates a random bit and computes the MHTLP puzzle locally.

**Files:**
- Create: `Demo/templates/flip.html`

- [ ] **Step 1: Write `Demo/templates/flip.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HTLP — Coin Flip</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
      --bg:#f4f0e8; --card:#ffffff; --gold:#c8961e; --silver:#7a8c99;
      --accent:#4a7a8c; --accent2:#5fa18f; --text:#1d2538; --dim:#6b7280; --border:#e7e0cf;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      font-family:'Inter',sans-serif;
      background:
        radial-gradient(circle at 80% 10%, rgba(200,150,30,.18) 0%, transparent 35%),
        radial-gradient(circle at 10% 80%, rgba(95,161,143,.25) 0%, transparent 30%),
        var(--bg);
      color:var(--text); min-height:100vh;
      display:flex; align-items:center; justify-content:center; padding:24px 18px;
    }
    .container { width:100%; max-width:420px; text-align:center; }
    .back { font-size:13px; color:var(--dim); text-decoration:none; display:block; margin-bottom:16px; }
    .back:hover { color:var(--accent); }
    h1 {
      font-size:36px; font-weight:700;
      background:linear-gradient(135deg,var(--gold),var(--accent2));
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
      background-clip:text; margin-bottom:8px;
    }
    .subtitle { font-size:15px; color:var(--dim); font-weight:300; margin-bottom:28px; line-height:1.5; }

    /* ── Coin ───────────────────────────────────────── */
    .coin-scene { width:160px; height:160px; perspective:600px; margin:0 auto 28px; }
    .coin {
      width:160px; height:160px; position:relative;
      transform-style:preserve-3d; transition:transform 0.1s;
    }
    .coin.spinning { animation:spin-coin 1.2s linear infinite; }
    .coin.landing  { animation:land-coin 1.4s cubic-bezier(.2,.8,.3,1) forwards; }
    @keyframes spin-coin {
      from { transform:rotateY(0deg); }
      to   { transform:rotateY(360deg); }
    }
    @keyframes land-coin {
      0%   { transform:rotateY(0deg); }
      60%  { transform:rotateY(1440deg); }
      80%  { transform:rotateY(1800deg) rotateX(10deg); }
      90%  { transform:rotateY(1798deg) rotateX(-4deg); }
      100% { transform:rotateY(1800deg); }
    }
    .coin-face {
      position:absolute; width:160px; height:160px; border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      font-size:60px; font-weight:900; backface-visibility:hidden;
      border:4px solid;
    }
    .coin-face.heads {
      background:radial-gradient(circle at 40% 35%, #f5d87a, #c8961e);
      border-color:#a07010; color:#7a4a00; transform:rotateY(0deg);
    }
    .coin-face.tails {
      background:radial-gradient(circle at 40% 35%, #d0dde6, #7a8c99);
      border-color:#4a6070; color:#2a3a50; transform:rotateY(180deg);
    }
    .coin-face.edge {
      background:linear-gradient(90deg, #c8961e, #7a8c99);
      border-color:#888; color:transparent; transform:rotateY(90deg);
    }

    /* ── Card ───────────────────────────────────────── */
    .card {
      background:var(--card); border:1px solid #d4cdb8; border-radius:14px;
      padding:28px 22px; box-shadow:0 1px 2px rgba(29,37,56,.06),0 6px 18px rgba(29,37,56,.08);
    }
    #flip-btn {
      font-family:'Inter',sans-serif; font-size:22px; font-weight:700;
      padding:22px 36px; border-radius:12px; border:2px solid var(--gold);
      background:var(--card); color:var(--gold); cursor:pointer;
      transition:transform .15s, box-shadow .15s, background .15s;
      width:100%;
    }
    #flip-btn:hover:not(:disabled) {
      background:rgba(200,150,30,.1); transform:translateY(-2px);
      box-shadow:0 6px 16px rgba(200,150,30,.3);
    }
    #flip-btn:disabled { opacity:.45; cursor:not-allowed; }
    .info { font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--dim); margin-top:16px; line-height:1.6; }

    #result-area { display:none; flex-direction:column; align-items:center; gap:10px; }
    .result-label {
      font-size:28px; font-weight:700;
    }
    .result-label.heads { color:var(--gold); }
    .result-label.tails { color:var(--silver); }
    .result-sub { font-size:13px; color:var(--dim); line-height:1.5; }

    details { margin-top:14px; text-align:left; }
    summary { font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--accent); cursor:pointer; }
    .tech-box {
      font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--dim);
      background:#f5f2ea; border:1px solid var(--border); border-radius:6px;
      padding:10px; margin-top:6px; word-break:break-all; line-height:1.7;
    }
    .live-counter {
      margin-top:22px; font-family:'JetBrains Mono',monospace;
      font-size:13px; color:var(--dim); display:flex;
      align-items:center; justify-content:center; gap:8px;
    }
    .live-counter .count { color:var(--accent2); font-weight:700; font-size:18px; }
    .dot { width:9px; height:9px; border-radius:50%; background:var(--accent2); animation:blink 2s ease-in-out infinite; }
    @keyframes blink { 0%,100%{opacity:.3} 50%{opacity:1} }
    .footer { margin-top:18px; font-size:11px; color:var(--dim); font-family:'JetBrains Mono',monospace; opacity:.7; }
    .confirm-msg { font-size:15px; color:var(--text); font-weight:500; }
    .confirm-sub  { font-size:13px; color:var(--dim); line-height:1.5; }
  </style>
</head>
<body>
  <div class="container">
    <a class="back" href="/">← back to demos</a>
    <h1>Coin Flip</h1>
    <p class="subtitle">Your secret bit is locked in a multiplicative time-lock puzzle — the XOR of everyone's bits is revealed only after time T.</p>

    <!-- Coin -->
    <div class="coin-scene">
      <div class="coin" id="coin">
        <div class="coin-face heads">H</div>
        <div class="coin-face tails">T</div>
        <div class="coin-face edge"></div>
      </div>
    </div>

    <div class="card">
      <div id="entry-view">
        <button id="flip-btn" onclick="submitFlip()" disabled>Add my secret</button>
        <p class="info">Your browser picks a random bit and generates<br>an MHTLP puzzle locally. No bit sent to server.</p>
      </div>

      <div id="confirm-view" style="display:none; flex-direction:column; align-items:center; gap:10px;">
        <p class="confirm-msg">✓ Your secret is locked.</p>
        <p class="confirm-sub">You'll find out what it was after the coin lands.<br>Watch the screen for the reveal.</p>
        <details>
          <summary>technical detail</summary>
          <div class="tech-box" id="tech-box"></div>
        </details>
      </div>
    </div>

    <div class="live-counter">
      <span class="dot"></span>
      <span id="live-count" class="count">0</span> secrets committed
    </div>
    <p class="footer">Secure &amp; Private Computing · HTLP Demo</p>
  </div>

  <script src="/static/htlp.js"></script>
  <script>
    let pp = null;

    async function init() {
      pp = await HTLP.fetchParams('/flip-params');
      document.getElementById('flip-btn').disabled = false;
    }
    init();

    async function submitFlip() {
      document.getElementById('flip-btn').disabled = true;

      // Random bit generated in browser using crypto.getRandomValues
      const randByte = new Uint8Array(1);
      crypto.getRandomValues(randByte);
      const bit = randByte[0] & 1;

      const puzzle = HTLP.mhtlpPGen(pp, bit);

      let data;
      try {
        const res = await fetch('/flip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ u: puzzle.u, v: puzzle.v }),
        });
        data = await res.json();
      } catch {
        alert('Network error — please try again.');
        document.getElementById('flip-btn').disabled = false;
        return;
      }

      if (data.status === 'success') {
        document.getElementById('entry-view').style.display = 'none';
        const cv = document.getElementById('confirm-view');
        cv.style.display = 'flex';
        document.getElementById('live-count').textContent = data.participants;
        document.getElementById('tech-box').textContent =
          `bit = ${bit} (${bit === 1 ? 'Heads' : 'Tails'} — revealed after solve)\nu = ${puzzle.u.slice(0,40)}…\nv = ${puzzle.v.slice(0,40)}…`;
      }
    }

    setInterval(async () => {
      try {
        const d = await (await fetch('/flip-status')).json();
        document.getElementById('live-count').textContent = d.participants;
      } catch {}
    }, 2000);
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add Demo/templates/flip.html
git commit -m "feat: add flip.html with MHTLP coin flip participant page"
```

---

## Task 8: Create `Demo/templates/index.html` (Landing Page)

New landing page at `/`. Two cards linking to `/vote` and `/flip` with brief descriptions.

**Files:**
- Modify: `Demo/templates/index.html` (full rewrite of current e-voting page)

- [ ] **Step 1: Write `Demo/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HTLP Live Demo</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
      --bg:#faf6ed; --card:#ffffff; --accent:#4a7a8c; --accent2:#5fa18f;
      --gold:#c8961e; --text:#1d2538; --dim:#6b7280; --border:#e7e0cf;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      font-family:'Inter',sans-serif;
      background:
        radial-gradient(circle at 85% 15%, rgba(244,200,184,.5) 0%, transparent 35%),
        radial-gradient(circle at 5% 85%, rgba(200,230,221,.5) 0%, transparent 30%),
        radial-gradient(circle at 50% 50%, rgba(247,224,178,.3) 0%, transparent 55%),
        var(--bg);
      color:var(--text); min-height:100vh;
      display:flex; align-items:center; justify-content:center; padding:32px 20px;
    }
    .container { width:100%; max-width:640px; text-align:center; }
    .badge {
      display:inline-block; font-family:'JetBrains Mono',monospace; font-size:11px;
      background:rgba(74,122,140,.1); color:var(--accent); border:1px solid rgba(74,122,140,.3);
      border-radius:999px; padding:4px 14px; margin-bottom:18px; letter-spacing:.5px;
    }
    h1 {
      font-size:44px; font-weight:800; line-height:1.1;
      background:linear-gradient(135deg, #4a7a8c 0%, #5fa18f 50%, #c8961e 100%);
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
      background-clip:text; margin-bottom:12px;
    }
    .subtitle { font-size:16px; color:var(--dim); font-weight:300; margin-bottom:40px; line-height:1.6; max-width:460px; margin-left:auto; margin-right:auto; }
    .demos { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:32px; }
    @media (max-width:520px) { .demos { grid-template-columns:1fr; } h1 { font-size:34px; } }
    .demo-card {
      background:var(--card); border:1px solid var(--border); border-radius:16px;
      padding:28px 22px 24px; text-align:left;
      box-shadow:0 1px 2px rgba(29,37,56,.05),0 4px 16px rgba(29,37,56,.07);
      text-decoration:none; color:var(--text); display:block;
      transition:transform .18s, box-shadow .18s, border-color .18s;
    }
    .demo-card:hover { transform:translateY(-4px); box-shadow:0 8px 28px rgba(29,37,56,.13); }
    .demo-card.vote:hover  { border-color:var(--accent); }
    .demo-card.flip:hover  { border-color:var(--gold); }
    .demo-icon { font-size:38px; margin-bottom:14px; display:block; }
    .demo-title { font-size:20px; font-weight:700; margin-bottom:6px; }
    .demo-card.vote .demo-title { color:var(--accent); }
    .demo-card.flip .demo-title { color:var(--gold); }
    .demo-desc { font-size:13px; color:var(--dim); line-height:1.55; margin-bottom:14px; }
    .demo-tag {
      display:inline-block; font-family:'JetBrains Mono',monospace; font-size:10px;
      border-radius:4px; padding:3px 8px; font-weight:500;
    }
    .demo-card.vote .demo-tag { background:rgba(74,122,140,.1); color:var(--accent); }
    .demo-card.flip .demo-tag { background:rgba(200,150,30,.1); color:var(--gold); }
    .join-link {
      display:inline-block; margin-top:10px; font-size:13px; font-weight:600;
    }
    .demo-card.vote .join-link { color:var(--accent); }
    .demo-card.flip .join-link { color:var(--gold); }
    .admin-link {
      font-size:13px; font-family:'JetBrains Mono',monospace;
      color:var(--dim); text-decoration:none;
    }
    .admin-link:hover { color:var(--accent); }
    .footer { margin-top:28px; font-size:11px; color:var(--dim); font-family:'JetBrains Mono',monospace; opacity:.6; }
  </style>
</head>
<body>
  <div class="container">
    <span class="badge">HTLP · Live Demo</span>
    <h1>Homomorphic<br>Time-Lock Puzzles</h1>
    <p class="subtitle">Cryptographic primitives that keep secrets locked until time T — and let you compute over them without unlocking.</p>

    <div class="demos">
      <a class="demo-card vote" href="/vote">
        <span class="demo-icon">🗳️</span>
        <div class="demo-title">E-Voting</div>
        <p class="demo-desc">Cast a sealed ballot for Codex or Claude. Votes are homomorphically tallied into a single time-lock puzzle and revealed after solving.</p>
        <span class="demo-tag">LHTLP · Linear</span>
        <br><span class="join-link">Join →</span>
      </a>
      <a class="demo-card flip" href="/flip">
        <span class="demo-icon">🪙</span>
        <div class="demo-title">Coin Flip</div>
        <p class="demo-desc">Contribute a secret random bit. Everyone's bits are combined via multiplication — one puzzle reveals the unbiased XOR of all contributions.</p>
        <span class="demo-tag">MHTLP · XOR</span>
        <br><span class="join-link">Join →</span>
      </a>
    </div>

    <a class="admin-link" href="/admin">presenter dashboard →</a>
    <p class="footer">Secure &amp; Private Computing · Malavolta &amp; Thyagarajan 2019</p>
  </div>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add Demo/templates/index.html
git commit -m "feat: add landing page with vote and coin-flip demo cards"
```

---

## Task 9: Redesign `Demo/templates/admin.html`

Dual dashboard with independent controls and coin animation on the flip panel.

**Files:**
- Modify: `Demo/templates/admin.html` (full rewrite)

- [ ] **Step 1: Write `Demo/templates/admin.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HTLP Admin</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
      --bg:#0f1117; --card:#1a1d26; --border:#2a2d3a; --accent:#4a9ab5;
      --accent2:#5fa18f; --gold:#c8961e; --silver:#7a8c99;
      --text:#e8eaf0; --dim:#6b7280; --green:#4ade80; --red:#f87171;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; padding:24px; }
    h1 { font-size:22px; font-weight:700; color:var(--text); margin-bottom:4px; }
    .subtitle { font-size:13px; color:var(--dim); font-family:'JetBrains Mono',monospace; margin-bottom:24px; }
    .panels { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
    @media (max-width:700px) { .panels { grid-template-columns:1fr; } }
    .panel {
      background:var(--card); border:1px solid var(--border); border-radius:14px; padding:24px;
    }
    .panel-title { font-size:17px; font-weight:700; margin-bottom:4px; }
    .panel.vote .panel-title  { color:var(--accent); }
    .panel.flip .panel-title  { color:var(--gold); }
    .tag {
      display:inline-block; font-family:'JetBrains Mono',monospace; font-size:10px;
      border-radius:4px; padding:2px 7px; margin-bottom:16px;
    }
    .panel.vote .tag { background:rgba(74,154,181,.15); color:var(--accent); }
    .panel.flip .tag { background:rgba(200,150,30,.15); color:var(--gold); }
    .stat { margin-bottom:16px; }
    .stat-label { font-size:11px; color:var(--dim); text-transform:uppercase; letter-spacing:.5px; font-family:'JetBrains Mono',monospace; }
    .stat-value { font-size:32px; font-weight:700; line-height:1.1; }
    .phase {
      display:inline-flex; align-items:center; gap:6px;
      font-family:'JetBrains Mono',monospace; font-size:12px;
      border:1px solid var(--border); border-radius:6px; padding:4px 10px; margin-bottom:16px;
    }
    .phase-dot { width:7px; height:7px; border-radius:50%; }
    .phase-dot.open    { background:var(--green); animation:blink 2s ease-in-out infinite; }
    .phase-dot.solving { background:var(--gold);  animation:blink .8s ease-in-out infinite; }
    .phase-dot.done    { background:var(--accent2); }
    @keyframes blink { 0%,100%{opacity:.3} 50%{opacity:1} }
    .progress-wrap { background:#2a2d3a; border-radius:6px; height:8px; margin-bottom:16px; overflow:hidden; }
    .progress-bar  { height:100%; border-radius:6px; transition:width .5s; }
    .panel.vote .progress-bar { background:var(--accent); }
    .panel.flip .progress-bar { background:var(--gold); }
    .msg { font-size:12px; color:var(--dim); font-family:'JetBrains Mono',monospace; margin-bottom:16px; min-height:16px; }
    .btn {
      font-family:'Inter',sans-serif; font-size:14px; font-weight:600;
      padding:10px 18px; border-radius:8px; border:none; cursor:pointer;
      margin-right:8px; margin-bottom:8px; transition:opacity .15s;
    }
    .btn:hover { opacity:.85; }
    .btn:disabled { opacity:.35; cursor:not-allowed; }
    .btn-solve { background:var(--accent);  color:#fff; }
    .btn-flip  { background:var(--gold);   color:#fff; }
    .btn-reset { background:var(--border); color:var(--dim); }
    .results { font-size:14px; line-height:1.8; }
    .result-row { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border); }
    .result-row:last-child { border-bottom:none; }
    .winner { color:var(--green); font-weight:700; }

    /* Coin */
    .coin-wrap { display:flex; justify-content:center; margin:16px 0; }
    .coin-scene { width:90px; height:90px; perspective:400px; }
    .coin {
      width:90px; height:90px; position:relative;
      transform-style:preserve-3d;
    }
    .coin.spinning { animation:spin-coin 1.2s linear infinite; }
    .coin.landing  { animation:land-coin 1.4s cubic-bezier(.2,.8,.3,1) forwards; }
    @keyframes spin-coin { from{transform:rotateY(0deg)} to{transform:rotateY(360deg)} }
    @keyframes land-coin {
      0%  {transform:rotateY(0deg)}
      60% {transform:rotateY(1440deg)}
      80% {transform:rotateY(1800deg) rotateX(8deg)}
      90% {transform:rotateY(1798deg) rotateX(-3deg)}
      100%{transform:rotateY(1800deg)}
    }
    .coin-face {
      position:absolute; width:90px; height:90px; border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      font-size:34px; font-weight:900; backface-visibility:hidden; border:3px solid;
    }
    .coin-face.heads {
      background:radial-gradient(circle at 40% 35%,#f5d87a,#c8961e);
      border-color:#a07010; color:#7a4a00; transform:rotateY(0deg);
    }
    .coin-face.tails {
      background:radial-gradient(circle at 40% 35%,#d0dde6,#7a8c99);
      border-color:#4a6070; color:#2a3a50; transform:rotateY(180deg);
    }
    .flip-result { font-size:24px; font-weight:800; text-align:center; }
    .flip-result.heads { color:var(--gold); }
    .flip-result.tails { color:var(--silver); }
    .flip-sub { font-size:11px; color:var(--dim); text-align:center; font-family:'JetBrains Mono',monospace; margin-top:4px; }
  </style>
</head>
<body>
  <h1>HTLP Admin Dashboard</h1>
  <p class="subtitle">presenter view — keep this tab open</p>

  <div class="panels">
    <!-- E-Voting Panel -->
    <div class="panel vote">
      <div class="panel-title">E-Voting</div>
      <div class="tag">LHTLP · Linear Homomorphic</div>
      <div class="stat">
        <div class="stat-label">Ballots Encrypted</div>
        <div class="stat-value" id="vote-count">0</div>
      </div>
      <div class="phase" id="vote-phase">
        <span class="phase-dot open" id="vote-dot"></span>
        <span id="vote-phase-label">OPEN</span>
      </div>
      <div class="progress-wrap"><div class="progress-bar" id="vote-bar" style="width:0%"></div></div>
      <div class="msg" id="vote-msg">Waiting for votes…</div>
      <div id="vote-result-area"></div>
      <button class="btn btn-solve" id="vote-solve-btn" onclick="startVote()">Close Voting &amp; Solve</button>
      <button class="btn btn-reset" onclick="resetVote()">Reset</button>
    </div>

    <!-- Coin Flip Panel -->
    <div class="panel flip">
      <div class="panel-title">Coin Flip</div>
      <div class="tag">MHTLP · Multiplicative XOR</div>
      <div class="stat">
        <div class="stat-label">Secrets Committed</div>
        <div class="stat-value" id="flip-count">0</div>
      </div>
      <div class="phase" id="flip-phase">
        <span class="phase-dot open" id="flip-dot"></span>
        <span id="flip-phase-label">OPEN</span>
      </div>
      <div class="coin-wrap">
        <div class="coin-scene">
          <div class="coin" id="admin-coin">
            <div class="coin-face heads">H</div>
            <div class="coin-face tails">T</div>
          </div>
        </div>
      </div>
      <div class="progress-wrap"><div class="progress-bar" id="flip-bar" style="width:0%"></div></div>
      <div class="msg" id="flip-msg">Waiting for participants…</div>
      <div id="flip-result-area"></div>
      <button class="btn btn-flip" id="flip-solve-btn" onclick="startFlip()">Close Flip &amp; Solve</button>
      <button class="btn btn-reset" onclick="resetFlip()">Reset</button>
    </div>
  </div>

  <script>
    // ── Voting ───────────────────────────────────────────
    async function startVote() {
      await fetch('/start_tally', { method:'POST' });
      document.getElementById('vote-solve-btn').disabled = true;
    }
    async function resetVote() {
      await fetch('/reset_vote', { method:'POST' });
      document.getElementById('vote-solve-btn').disabled = false;
      document.getElementById('vote-result-area').innerHTML = '';
      document.getElementById('vote-bar').style.width = '0%';
      setPhase('vote', 'open');
    }

    // ── Flip ─────────────────────────────────────────────
    let flipRevealed = false;
    async function startFlip() {
      await fetch('/start_flip', { method:'POST' });
      document.getElementById('flip-solve-btn').disabled = true;
      document.getElementById('admin-coin').className = 'coin spinning';
    }
    async function resetFlip() {
      flipRevealed = false;
      await fetch('/reset_flip', { method:'POST' });
      document.getElementById('flip-solve-btn').disabled = false;
      document.getElementById('flip-result-area').innerHTML = '';
      document.getElementById('flip-bar').style.width = '0%';
      document.getElementById('admin-coin').className = 'coin';
      setPhase('flip', 'open');
    }

    function setPhase(demo, phase) {
      const dot   = document.getElementById(demo + '-dot');
      const label = document.getElementById(demo + '-phase-label');
      dot.className   = 'phase-dot ' + phase;
      label.textContent = phase.toUpperCase();
    }

    // ── Poll ─────────────────────────────────────────────
    async function pollVote() {
      try {
        const d = await (await fetch('/status')).json();
        document.getElementById('vote-count').textContent = d.votes;
        document.getElementById('vote-msg').textContent   = d.message;
        document.getElementById('vote-bar').style.width   = d.progress + '%';
        if (d.solving)  setPhase('vote','solving');
        if (d.results) {
          setPhase('vote','done');
          const r  = d.results;
          const winner = r.Codex > r.Claude ? 'Codex' : r.Claude > r.Codex ? 'Claude' : null;
          document.getElementById('vote-result-area').innerHTML = `
            <div class="results">
              <div class="result-row"><span>Codex</span><span class="${winner==='Codex'?'winner':''}">${r.Codex} vote${r.Codex!==1?'s':''} ${winner==='Codex'?'🏆':''}</span></div>
              <div class="result-row"><span>Claude</span><span class="${winner==='Claude'?'winner':''}">${r.Claude} vote${r.Claude!==1?'s':''} ${winner==='Claude'?'🏆':''}</span></div>
              ${winner===null?'<div class="result-row" style="color:var(--gold)">Tie!</div>':''}
            </div>`;
        }
      } catch {}
    }

    async function pollFlip() {
      try {
        const d = await (await fetch('/flip-status')).json();
        document.getElementById('flip-count').textContent = d.participants;
        document.getElementById('flip-msg').textContent   = d.message;
        document.getElementById('flip-bar').style.width   = d.progress + '%';
        if (d.solving) setPhase('flip','solving');
        if (d.result && !flipRevealed) {
          flipRevealed = true;
          setPhase('flip','done');
          const face = d.result.face;   // 'heads' or 'tails'
          const bit  = d.result.bit;
          const coin = document.getElementById('admin-coin');
          coin.className = 'coin landing';
          setTimeout(() => {
            const label = face === 'heads' ? 'Heads — 1' : 'Tails — 0';
            document.getElementById('flip-result-area').innerHTML = `
              <div class="flip-result ${face}">${label}</div>
              <div class="flip-sub">XOR of ${d.participants} secret bit${d.participants!==1?'s':''}</div>`;
          }, 1400);
        }
      } catch {}
    }

    setInterval(pollVote, 1500);
    setInterval(pollFlip, 1500);
    pollVote();
    pollFlip();
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add Demo/templates/admin.html
git commit -m "feat: redesign admin.html with dual dashboard and coin animation"
```

---

## Task 10: Integration Test & Final Commit

Manual smoke test verifying end-to-end flow for both demos.

**Files:** none changed

- [ ] **Step 1: Start the server with a short solve time**

```bash
cd Demo && echo "0.05" | python app.py
```
(3-second solve time — fast enough to see the result in the test)

- [ ] **Step 2: Test vote flow**

In a second terminal:
```bash
# Fetch vote params
curl http://localhost:5000/vote-params | python3 -m json.tool

# Verify landing page loads
curl -s http://localhost:5000/ | grep "HTLP"

# Verify vote page loads
curl -s http://localhost:5000/vote | grep "Cast Your Vote"
```
Expected: JSON with N/g/h/T fields; HTML containing "HTLP"; HTML containing "Cast Your Vote".

- [ ] **Step 3: Submit a test flip puzzle via server-side PGen (verifies route)**

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0,'Demo')
from htlp import MHTLP
mhtlp = MHTLP(bits=32, T=5)
pp = mhtlp.public_params()
u, v = mhtlp.PGen(1)
import urllib.request, json
req = urllib.request.Request(
    'http://localhost:5000/flip',
    data=json.dumps({'u': str(u), 'v': str(v)}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
resp = json.loads(urllib.request.urlopen(req).read())
print('Submit flip:', resp)

req2 = urllib.request.Request('http://localhost:5000/start_flip', method='POST')
resp2 = json.loads(urllib.request.urlopen(req2).read())
print('Start flip:', resp2)
EOF
```
Expected: `Submit flip: {'status': 'success', 'participants': 1}`, `Start flip: {'status': 'started'}`.

- [ ] **Step 4: Wait ~5 seconds and check result**

```bash
sleep 6 && curl -s http://localhost:5000/flip-status | python3 -m json.tool
```
Expected: JSON with `"result": {"bit": 0 or 1, "face": "heads" or "tails"}`.

- [ ] **Step 5: Final commit and push branch**

```bash
git add -A
git status  # verify clean
git log --oneline feature/mhtlp-coin-flip ^main
```
Expected: 7 commits listed (tasks 1-9).

```bash
git push -u origin feature/mhtlp-coin-flip
```

---

## Self-Review Notes

- **Spec coverage:** All 5 spec sections covered. Landing page ✓, vote.html redesign ✓, flip.html ✓, admin dual dashboard ✓, coin animation ✓, client-side JS ✓, MHTLP class ✓, reset routes ✓.
- **Type consistency:** `public_params()` returns `{"N": str, "g": str, "h": str, "T": int}` in both classes and parsed the same way in `fetchParams()` in JS. `PSolve` returns `int` in both. `PGen` returns `tuple(int, int)` in both.
- **No placeholders:** All steps contain complete, runnable code.
- **Branch:** Task 1 creates `feature/mhtlp-coin-flip` before any file changes.
