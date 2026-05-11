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
