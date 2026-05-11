# MHTLP Coin Flip + Dual Demo Design

**Date:** 2026-05-11  
**Status:** Approved  
**Branch:** `feature/mhtlp-coin-flip`

## Overview

Extend the existing HTLP demo (LHTLP e-voting) with a second demo: multi-party coin flipping using Multiplicatively Homomorphic Time-Lock Puzzles (MHTLP). Both demos run off the same Flask server with independent state machines. Puzzle generation moves client-side for both schemes (JS BigInt). Website is redesigned to be cleaner and clearer.

---

## 1. Architecture

```
Demo/
├── app.py              # extends existing Flask app with flip routes
├── htlp.py             # new: LHTLP + MHTLP classes extracted here
├── templates/
│   ├── index.html      # landing page (links to both demos with QR codes)
│   ├── vote.html       # LHTLP e-voting (redesigned)
│   ├── flip.html       # MHTLP coin flip (new)
│   └── admin.html      # dual dashboard (redesigned)
└── static/
    └── htlp.js         # client-side BigInt PGen for both schemes
```

---

## 2. Cryptographic Implementation

### MHTLP (new Python class)

Uses Blum integer N — automatically satisfied since safe primes p = 2p'+1 always have p ≡ 3 mod 4. Same prime generation as LHTLP.

```
PGen(s):  s ∈ {1, N−1}  — bit 0 → +1 (Tails), bit 1 → N−1 (Heads)
  r ← random [1, N²]
  u = g^r mod N
  v = h^r · s mod N
  return (u, v)

PEval(Z₁…Zₙ):
  ũ = ∏ uᵢ mod N
  ṽ = ∏ vᵢ mod N
  return (ũ, ṽ)

PSolve(Z):
  w = u^(2^T) mod N
  s = v · w⁻¹ mod N
  return 0 (Tails) if s == 1 else 1 (Heads)
```

### Client-side (htlp.js)

- `modpow(base, exp, mod)` — BigInt square-and-multiply
- `randomBigInt(max)` — uses `crypto.getRandomValues` for security
- `lhtlpPGen(pp, s)` — LHTLP puzzle generation in browser
- `mhtlpPGen(pp, bit)` — MHTLP puzzle generation in browser; bit auto-generated randomly

Server never sees the user's secret — only (u, v) is submitted.

---

## 3. Website

### `/` — Landing page
Two cards: "E-Voting Demo" and "Coin Flip Demo". QR codes for phone access. No crypto jargon.

### `/vote` — E-voting participant (redesign)
Pick candidate → browser generates LHTLP puzzle → locked confirmation. Collapsible technical detail shows actual (u, v). Live ballot counter.

### `/flip` — Coin flip participant (new)
One "Add my secret" button. Browser auto-generates random bit, computes MHTLP puzzle, submits. Confirmation: "Your bit is locked." Collapsible (u, v) detail. Live participant counter.

**Coin animation:**
- Commitment phase: static coin (edge view)
- Solving phase: CSS 3D `rotateY` continuous spin, accelerating with progress
- Reveal: spin decelerates, coin lands flat — gold face = Heads (1), silver face = Tails (0)
- Large text: "Heads — 1" or "Tails — 0" with participant XOR explanation

**Convention:** Heads = 1, Tails = 0

### `/admin` — Dual dashboard (redesign)
Two side-by-side panels, one per demo. Each shows: participant count, phase indicator (OPEN → SOLVING → REVEALED), progress bar, result. Independent "Close & Solve" buttons. Independent reset buttons.

---

## 4. Data Flow & State

**Two independent state machines:** VOTING and FLIP, each: OPEN → SOLVING → DONE

### Routes

```
GET  /                → landing page
GET  /vote            → e-voting participant
GET  /flip            → coin flip participant
GET  /admin           → dual dashboard

GET  /vote-params     → {N, g, h, T} for LHTLP (public)
GET  /flip-params     → {N, g, h, T} for MHTLP (public)

POST /vote            → submit {u, v} (LHTLP)
POST /flip            → submit {u, v} (MHTLP)

POST /start_tally     → close voting, start solving
POST /start_flip      → close flip, start solving

GET  /status          → voting status/results
GET  /flip-status     → flip status/result + individual bits post-reveal

POST /reset_vote      → reset voting state
POST /reset_flip      → reset flip state
```

### Flip solve result
```json
{
  "phase": "done",
  "result": {"bit": 1, "face": "heads"},
  "participants": 12,
  "individual_bits": [1, 0, 1, 1, 0]
}
```
Individual bits revealed only post-solve so participants can verify their contribution.

---

## 5. Branch Strategy

- Branch: `feature/mhtlp-coin-flip` off `main`
- Commit plan:
  1. Extract LHTLP + add MHTLP → `htlp.py`
  2. Add flip routes + state → `app.py`
  3. Client-side BigInt PGen → `static/htlp.js`
  4. Redesign `vote.html` + new landing `index.html`
  5. New `flip.html` with coin animation
  6. Redesign `admin.html` (dual dashboard)
