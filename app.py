import json
import os
import subprocess
import sys

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
import income_goal

app = Flask(__name__)


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def run_script(script_path):
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__) or ".",
    )
    return result


# ── Static files ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "combined.html")


@app.route("/positions")
def positions():
    return send_from_directory(".", "positions.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(".", "dashboard.html")


@app.route("/output/<path:filename>")
def output_files(filename):
    return send_from_directory("output", filename)


# ── Config ───────────────────────────────────────────────────────────────────

@app.route("/api/config")
def get_config():
    data = read_json("config.json")
    if data is None:
        return jsonify({"error": "config.json not found"}), 404
    return jsonify(data)


@app.route("/api/config", methods=["POST"])
def save_config():
    config = read_json("config.json") or {}
    body = request.get_json(force=True)
    if "account_balance" in body:
        config["account_balance"] = float(body["account_balance"])
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    return jsonify({"ok": True})


# ── Data endpoints ───────────────────────────────────────────────────────────

@app.route("/api/summary")
def get_summary():
    data = read_json("output/summary.json")
    if data is None:
        return jsonify({"error": "Run parse_trades.py + calculate_premium.py"}), 404
    return jsonify(data)


@app.route("/api/scanner")
def get_scanner():
    data = read_json("output/scanner_results.json")
    if data is None:
        return jsonify({"error": "Run scan_options.py"}), 404
    return jsonify(data)


@app.route("/api/trade-data")
def get_trade_data():
    data = read_json("output/trade_data.json")
    if data is None:
        return jsonify({"error": "Run collateral.py"}), 404
    return jsonify(data)


@app.route("/api/fear-greed")
def get_fear_greed():
    data = read_json("output/fear_greed.json")
    return jsonify(data)  # null if not found — handled gracefully in UI


@app.route("/api/breadth")
def get_breadth():
    data = read_json("output/breadth.json")
    return jsonify(data)


@app.route("/api/goal-metrics")
def get_goal_metrics():
    config = read_json("config.json")
    summary = read_json("output/summary.json")
    scanner = read_json("output/scanner_results.json")
    trade_data = read_json("output/trade_data.json") or {}

    if not config:
        return jsonify({"error": "config.json not found"}), 500
    if not summary:
        return jsonify({"error": "Run parse_trades.py + calculate_premium.py"}), 500
    if not scanner:
        return jsonify({"error": "Run scan_options.py"}), 500

    metrics = income_goal.compute_metrics(config, summary, scanner, trade_data)
    return jsonify(metrics)


# ── Refresh actions ──────────────────────────────────────────────────────────

@app.route("/api/refresh/scanner", methods=["POST"])
def refresh_scanner():
    result = run_script("scripts/scan_options.py")
    if result.returncode != 0:
        return jsonify({"ok": False, "error": result.stderr}), 500
    return jsonify({"ok": True, "output": result.stdout})


@app.route("/api/refresh/fear-greed", methods=["POST"])
def refresh_fear_greed():
    result = run_script("scripts/fetch_fear_greed.py")
    if result.returncode != 0:
        return jsonify({"ok": False, "error": result.stderr}), 500
    return jsonify({"ok": True, "output": result.stdout})


@app.route("/api/refresh/breadth", methods=["POST"])
def refresh_breadth():
    result = run_script("scripts/fetch_breadth.py")
    if result.returncode != 0:
        return jsonify({"ok": False, "error": result.stderr}), 500
    return jsonify({"ok": True, "output": result.stdout})


@app.route("/api/refresh/trades", methods=["POST"])
def refresh_trades():
    for script in ["scripts/parse_trades.py", "scripts/calculate_premium.py", "scripts/collateral.py"]:
        result = run_script(script)
        if result.returncode != 0:
            return jsonify({"ok": False, "error": f"{script}: {result.stderr}"}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("Starting Options Dashboard at http://localhost:5000")
    app.run(debug=True, port=5000)
