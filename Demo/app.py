import time
import random
import threading
from flask import Flask, render_template, request, jsonify
from sympy import isprime, randprime

app = Flask(__name__)

# Allow the presentation (loaded from file://) to poll the API.
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# --- Cryptography Setup ---
def generate_strong_prime(bits):
    while True:
        p_prime = randprime(2**(bits-2), 2**(bits-1))
        p = 2 * p_prime + 1
        if isprime(p): return p, p_prime

def mod_inverse(a, m):
    return pow(a, -1, m)

class LHTLP:
    def __init__(self, bits=128, target_seconds=150):
        print("Calibrating CPU and generating primes... Please wait.")
        test_N = generate_strong_prime(128)[0] * generate_strong_prime(128)[0]
        test_val = random.randrange(2, test_N)
        squarings = 0
        calib_start = time.time()
        while time.time() - calib_start < 1.0:
            test_val = pow(test_val, 2, test_N)
            squarings += 1
            
        self.T = squarings * target_seconds
        self.current_iteration = 0  # <--- NEW: Tracks solving progress
        print(f"Set T = {self.T} for ~{target_seconds} seconds of solving time.")

        p, _ = generate_strong_prime(bits)
        q, _ = generate_strong_prime(bits)
        self.N = p * q
        self.N2 = self.N ** 2
        order_JN = ((p - 1) * (q - 1)) // 2
        
        while True:
            g_tilde = random.randrange(2, self.N)
            self.g = (-pow(g_tilde, 2, self.N)) % self.N
            if self.g > 1: break
                
        self.h = pow(self.g, pow(2, self.T, order_JN), self.N)
        print("Setup complete. Server is ready.")
        
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
            if i % update_interval == 0:
                self.current_iteration += update_interval
                if progress_cb is not None:
                    progress_cb(i + update_interval)
        if progress_cb is not None:
            progress_cb(self.T)

        w_N_inv = mod_inverse(pow(w, self.N, self.N2), self.N2)
        return (((v * w_N_inv) % self.N2) - 1) // self.N

# --- Startup prompt: ask for tally duration ---
def prompt_target_minutes():
    print()
    print("=" * 60)
    print(" HTLP Demo - tally duration configuration")
    print("=" * 60)
    print(" Total time the audience waits while both Codex's and")
    print(" Claude's puzzles are solved. Each puzzle gets half of this.")
    while True:
        raw = input(" Total tally time in MINUTES [default 5]: ").strip()
        if not raw:
            return 5.0
        try:
            v = float(raw)
            if v <= 0:
                print("  -> Please enter a positive number.")
                continue
            return v
        except ValueError:
            print("  -> Please enter a number (e.g. 5 or 2.5).")

def fmt_per_puzzle(seconds):
    """Human-readable label used inside status messages."""
    if seconds < 60:
        return f"~{int(round(seconds))}s"
    minutes = seconds / 60
    if abs(minutes - round(minutes)) < 0.05:
        return f"~{int(round(minutes))} min"
    return f"~{minutes:.1f} min"

target_total_minutes = prompt_target_minutes()
target_total_seconds = max(4, int(round(target_total_minutes * 60)))
target_per_puzzle = max(2, target_total_seconds // 2)
per_puzzle_label = fmt_per_puzzle(target_per_puzzle)
print(f" Target: {target_total_minutes:g} min total ({per_puzzle_label} per puzzle)")
print()

# Initialize HTLP
htlp = LHTLP(bits=128, target_seconds=target_per_puzzle)

# --- Global State ---
votes = []
is_solving = False
results = None
progress_msg = "Waiting for votes..."
solve_progress = {"Codex": 0, "Claude": 0}  # per-candidate squaring counter

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html', solving=is_solving)

@app.route('/vote', methods=['POST'])
def cast_vote():
    if is_solving:
        return jsonify({"status": "error", "message": "Voting is closed!"}), 400
    
    candidate = request.form.get('candidate')
    if candidate == 'Codex':
        vote_vector = (htlp.PGen(1), htlp.PGen(0))
    elif candidate == 'Claude':
        vote_vector = (htlp.PGen(0), htlp.PGen(1))
    else:
        return jsonify({"status": "error"}), 400
        
    votes.append(vote_vector)
    return jsonify({"status": "success", "total_votes": len(votes)})

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/start_tally', methods=['POST'])
def start_tally():
    global is_solving, progress_msg
    if not is_solving and votes:
        is_solving = True
        htlp.current_iteration = 0
        solve_progress["Codex"] = 0
        solve_progress["Claude"] = 0
        progress_msg = "Homomorphically adding puzzles..."
        threading.Thread(target=run_tally).start()
    return jsonify({"status": "started"})

@app.route('/status')
def status():
    if results:
        codex_pct = 100.0
        claude_pct = 100.0
        remaining_seconds = 0.0
    elif is_solving and htlp.T:
        codex_frac = min(1.0, solve_progress["Codex"] / htlp.T)
        claude_frac = min(1.0, solve_progress["Claude"] / htlp.T)
        codex_pct = codex_frac * 100.0
        claude_pct = claude_frac * 100.0
        remaining_seconds = ((1.0 - codex_frac) + (1.0 - claude_frac)) * target_per_puzzle
    else:
        codex_pct = 0.0
        claude_pct = 0.0
        remaining_seconds = float(target_total_seconds)

    combined = (codex_pct + claude_pct) / 2.0

    return jsonify({
        "solving": is_solving,
        "results": results,
        "votes": len(votes),
        "message": progress_msg,
        "progress": round(combined, 2),
        "codex_progress": round(codex_pct, 2),
        "claude_progress": round(claude_pct, 2),
        "target_per_puzzle": target_per_puzzle,
        "target_total": target_total_seconds,
        "remaining_seconds": round(remaining_seconds, 2),
    })

def run_tally():
    global results, is_solving, progress_msg

    codex_eval = htlp.PEval([v[0] for v in votes])
    claude_eval = htlp.PEval([v[1] for v in votes])

    progress_msg = f"Solving time-lock for Codex ({per_puzzle_label})..."
    codex_total = htlp.PSolve(
        codex_eval,
        progress_cb=lambda n: solve_progress.update({"Codex": n}),
    )

    progress_msg = f"Solving time-lock for Claude ({per_puzzle_label})..."
    claude_total = htlp.PSolve(
        claude_eval,
        progress_cb=lambda n: solve_progress.update({"Claude": n}),
    )

    results = {"Codex": codex_total, "Claude": claude_total}
    progress_msg = "Tally complete!"
    is_solving = False

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

#ngrok http --url=marley-choleric-leigh.ngrok-free.dev 5000