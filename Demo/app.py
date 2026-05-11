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