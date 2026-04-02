"""
HTTP server on port 8080 — receives N8N callback when CSV is ready.
N8N final node posts: {"csv_url": "..."} or {"sheet_id": "..."}
Systemd: see deploy/indeed-webhook.service
"""
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("LISTEN_PORT", 8080))
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ApplyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/apply":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "invalid json"}')
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "accepted"}')

        csv_url = payload.get("csv_url") or payload.get("sheet_id")
        if csv_url:
            runner = os.path.join(SCRIPT_DIR, "src", "apply_runner.py")
            venv_python = os.path.join(SCRIPT_DIR, "venv", "bin", "python")
            python = venv_python if os.path.exists(venv_python) else sys.executable
            subprocess.Popen([python, runner, csv_url], cwd=SCRIPT_DIR)
            print(f"[webhook] Spawned apply_runner for: {csv_url}")
        else:
            print(f"[webhook] WARNING: no csv_url in payload: {payload}")

    def log_message(self, format, *args):
        print(f"[{self.client_address[0]}] {format % args}")


if __name__ == "__main__":
    print(f"Webhook server listening on 0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), ApplyHandler).serve_forever()
