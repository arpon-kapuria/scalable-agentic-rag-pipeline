"""
A minimal Flask server that receives LLM-generated code via HTTP, executes it in a disposable child process with a 5-second timeout, captures the stdout, and returns the output — killing the process immediately if it hangs or exceeds the timeout.
- /execute receives code via HTTP POST from the API
- Spawns a child process with an empty local namespace to run the code
- Captures all print() output into a StringIO buffer
- Parent blocks for max 5 seconds — terminates child and returns 408 if it hangs
- Result passed back via multiprocessing.Queue and returned as JSON
- /health endpoint confirms the container is alive for Kubernetes health checks
"""

from flask import Flask, request, jsonify
import io
import contextlib
import multiprocessing
import yaml

app = Flask(__name__)

with open("limits.yaml") as f:
    limits = yaml.safe_load(f)

def execute_code_safe(code: str, queue):
    """
    Runs code in a separate process to allow hard timeouts.
    Captures stdout.
    """
    # Redirect stdout to capture print() statements
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            # Dangerous! Only run this in isolated container.
            # Restricted globals can add slight safety layer.
            exec(code, {"__builtins__": __builtins__}, {})
        queue.put({"status": "success", "output": buffer.getvalue()})
    except Exception as e:
        queue.put({"status": "error", "output": str(e)})

SOFT_TIMEOUT = limits["runtime"]["soft_timeout_seconds"]

@app.route("/execute", methods=["POST"])
def run_code():
    data = request.json
    code = data.get("code", "")

    if not code or not isinstance(code, str):
        return jsonify({"output": "Error: No code provided."}), 400

    queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=execute_code_safe, args=(code, queue))
    p.start()

    # Soft kill — graceful SIGTERM
    p.join(SOFT_TIMEOUT)
    
    if p.is_alive():
        p.terminate()     # SIGTERM — graceful
        p.join(2)         # wait 2 seconds
        if p.is_alive():
            p.kill()      # SIGKILL — force kill
        return jsonify({"output": "Error: Execution timed out."}), 408

    if not queue.empty():
        result = queue.get()
        return jsonify(result)

    return jsonify({"output": "No output produced."})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    # Run on port 8080
    app.run(host="0.0.0.0", port=8080)