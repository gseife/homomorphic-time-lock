# Homomorphic Time-Lock Puzzles

Implementation of the **Linearly Homomorphic Time-Lock Puzzle (LHTLP)** and **Multiplicatively Homomorphic Time-Lock Puzzle (MHTLP)** from Malavolta & Thyagarajan (2019), plus a live web demo with two applications.

---

## Repository Structure

```
homomorphic-time-lock/
├── Implementation.ipynb      # Step-by-step notebook (main reference)
├── Demo/
│   ├── app.py                # Flask web server
│   ├── htlp.py               # LHTLP and MHTLP classes
│   ├── templates/            # HTML pages (index, vote, flip, admin)
│   ├── static/htlp.js        # Client-side puzzle encryption
│   └── tests/                # pytest suite
└── papers/                   # RSW96.pdf and Malavolta & Thyagarajan 2019
```

---

## Notebook (`Implementation.ipynb`)

A self-contained walkthrough of the construction, intended to be read top to bottom.

| Section | Content |
|---------|---------|
| 1 | Common helpers: safe-prime generation, CPU calibration (`calibrate_T`) |
| 2 | LHTLP — additive homomorphism over Paillier-style encoding (`PSetup`, `PGen`, `PEval`, `PSolve`) |
| 3 | MHTLP — multiplicative homomorphism with ±1 XOR encoding |
| 4 | Application 1: privacy-preserving e-voting (Codex vs. Claude) |
| 5 | Application 2: multi-party fair coin flip |
| 6.1 | Detailed trace of the e-voting example with tiny parameters |
| 6.2 | Detailed trace of the coin-flip example, step-by-step squarings shown |

### Running the notebook

```bash
pip install sympy jupyterlab
jupyter lab Implementation.ipynb
```

Run cells in order. Sections 2–3 take a few seconds each for key generation; sections 4–5 run a full timed solve, which takes as long as the calibrated `T` implies (~seconds with default small parameters).

---

## Demo (Flask Web App)

An interactive multi-user demo with two scenarios that run in a browser.

### Scenarios

**E-Voting** (`/vote`)
Each participant encrypts their vote (Codex or Claude) client-side into an LHTLP puzzle using the server's public parameters. The server homomorphically combines all puzzles with `PEval` — without ever seeing individual votes — then solves the combined puzzle to reveal the tally after a configurable delay.

**Coin Flip** (`/flip`)
Each participant encrypts a random bit into an MHTLP puzzle. The server combines them with `PEval` (XOR of all bits) and solves after a delay, producing a single fair bit. No participant can bias the result, and no result is revealed early.

**Admin Panel** (`/admin`)
Controls for starting the tally/flip and monitoring solve progress in real time.

### Running the demo

**Dependencies**

```bash
pip install flask sympy
```

**Start the server**

```bash
cd Demo
python app.py
```

On startup the server asks for a solve duration (default: 2 minutes). It then calibrates `T` (number of sequential squarings) to match that duration on the current CPU, generates LHTLP and MHTLP parameters, and starts listening on port 5001.

```
==============================
 HTLP Demo — solve duration configuration
==============================
 Solve time in MINUTES [default 2]: 
```

Open `http://localhost:5001` in a browser. Share the URL with other participants on the same network to collect multiple votes or flip contributions before triggering the solve from the admin panel.

### Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page — links to both demos |
| `/vote` | Cast a vote (client-side encryption) |
| `/flip` | Submit a coin-flip contribution |
| `/admin` | Start tally/flip, monitor progress |

### Running the tests

```bash
pip install pytest
pytest Demo/tests/
```

16 tests covering `LHTLP` and `MHTLP`: key generation, puzzle solve correctness, homomorphic combination.

---

## Security properties of the demo

### Client-side encryption

Secrets never leave the browser in plaintext. When a participant casts a vote or submits a coin-flip bit, `htlp.js` fetches the server's public parameters (`N`, `g`, `h`, `T`) and runs `PGen` locally in the browser to produce the puzzle `(u, v)`. Only the encrypted puzzle is sent to the server. The server has no way to extract the secret from `(u, v)` without performing the full sequential squaring computation — which takes as long as the configured solve time by construction.

### Homomorphic aggregation (`PEval`) is public

`PEval` combines puzzles by multiplying their components modulo `N` (or `N²`). This operation requires only the public parameters and the puzzle ciphertexts — no secret key is involved. In principle any participant or observer could perform the aggregation themselves. The server is not trusted for this step; it is merely convenient.

### Timed release — no early reveal possible

The result is protected by the sequential-squaring assumption (RSW): computing `g^{2^T} mod N` cannot be sped up by parallelism or pre-computation because each squaring depends on the previous one, and the factorisation of `N` (which would allow a shortcut via Euler's theorem) is discarded after setup. This means:

- The server cannot reveal the tally or flip outcome early, even if it wanted to.
- An adversary who intercepts all submitted puzzles also cannot learn the result faster than the honest solver.
- Increasing `T` directly increases the guaranteed delay; decreasing it shortens it.

### Individual vote / bit privacy

Even after the tally is published, individual votes remain hidden. `PEval` maps `n` puzzles to a single combined puzzle encoding only the aggregate. There is no operation that recovers individual secrets from the combined puzzle, so ballot secrecy holds as long as no participant reveals their own randomness.

### Trust assumptions

- The server generates and publishes the public parameters honestly. A malicious server could choose weak primes for `N`, making the puzzle solvable early. In a production deployment the parameter generation would be verifiable or done by a trusted third party.
- Clients must use fresh randomness in `PGen`. Reusing `r` across two puzzles leaks the secret.
- The hardness guarantee degrades if the attacker has hardware orders of magnitude faster than the machine that ran `calibrate_T`. `T` should be set conservatively for the expected adversary.

---

## How the primitives work

A time-lock puzzle (RSW 1996) encodes a secret `s` such that solving requires `T` sequential modular squarings — inherently non-parallelisable. The homomorphic extension (Malavolta & Thyagarajan 2019) adds a public `PEval` operation so that `n` independently-encrypted puzzles can be combined into one without solving any of them. Solving the combined puzzle recovers the aggregate (sum for LHTLP, XOR for MHTLP); individual secrets are never revealed.

Key parameters from `PSetup`: RSA modulus `N = pq` (strong primes, factorisation discarded), generator `g`, and `h = g^{2^T} mod N` (computed once using the known order, before the factorisation is discarded). Clients encrypt with `PGen`; the server aggregates with `PEval` and solves with `PSolve`.

---

## References

Ronald L. Rivest, Adi Shamir & David A. Wagner. *Time-lock puzzles and timed-release crypto.* MIT Technical Report, 1996. (`papers/RSW96.pdf`)

Giulio Malavolta & Sri Aravinda Krishnan Thyagarajan. *Homomorphic Time-Lock Puzzles and Applications.* CRYPTO 2019. (`papers/2019-635.pdf`)
