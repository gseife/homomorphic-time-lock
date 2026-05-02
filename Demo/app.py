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
        
    def PSolve(self, puzzle):
        u, v = puzzle
        w = u
        
        # <--- NEW: Update progress efficiently (every 1% to avoid lagging)
        update_interval = max(1, self.T // 100) 
        for i in range(self.T):
            w = pow(w, 2, self.N)
            if i % update_interval == 0:
                self.current_iteration += update_interval

        w_N_inv = mod_inverse(pow(w, self.N, self.N2), self.N2)
        return (((v * w_N_inv) % self.N2) - 1) // self.N

# Initialize HTLP 
htlp = LHTLP(bits=128, target_seconds=150)

# --- Global State ---
votes = []          
is_solving = False
results = None
progress_msg = "Waiting for votes..."

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html', solving=is_solving)

@app.route('/vote', methods=['POST'])
def cast_vote():
    if is_solving:
        return jsonify({"status": "error", "message": "Voting is closed!"}), 400
    
    candidate = request.form.get('candidate')
    if candidate == 'Alice':
        vote_vector = (htlp.PGen(1), htlp.PGen(0))
    elif candidate == 'Bob':
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
        htlp.current_iteration = 0  # Reset progress tracker
        progress_msg = "Homomorphically adding puzzles..."
        threading.Thread(target=run_tally).start()
    return jsonify({"status": "started"})

@app.route('/status')
def status():
    # <--- NEW: Calculate percentage based on 2 puzzles (Alice + Bob)
    if is_solving:
        total_squarings_needed = htlp.T * 2
        pct = int((htlp.current_iteration / total_squarings_needed) * 100)
        pct = min(100, pct)
    else:
        pct = 100 if results else 0

    return jsonify({
        "solving": is_solving, 
        "results": results, 
        "votes": len(votes),
        "message": progress_msg,
        "progress": pct  # <--- NEW: Send to frontend
    })

def run_tally():
    global results, is_solving, progress_msg
    
    alice_eval = htlp.PEval([v[0] for v in votes])
    bob_eval = htlp.PEval([v[1] for v in votes])
    
    progress_msg = "Solving time-lock for Alice (~2.5 mins)..."
    alice_total = htlp.PSolve(alice_eval)
    
    progress_msg = "Solving time-lock for Bob (~2.5 mins)..."
    bob_total = htlp.PSolve(bob_eval)
    
    results = {"Alice": alice_total, "Bob": bob_total}
    progress_msg = "Tally complete!"
    is_solving = False

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

#ngrok http --url=marley-choleric-leigh.ngrok-free.dev 5000